from __future__ import annotations
import random
import numpy as np
import networkx as nx
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from engine.claims import Claim, EpistemicState, validate_transition
from engine.agents import Node, node_from_config
from engine.primitives import Proposal, make_primitives
from engine.events import EventLog
from engine.trust import TrustNetwork


def _state_transition_logging_mode(config: dict) -> str:
    logging_cfg = config.get("logging", {})
    explicit = None
    if isinstance(logging_cfg, dict):
        explicit = logging_cfg.get("state_transition_logging_mode")
    if explicit is None:
        explicit = config.get("experiment", {}).get("state_transition_logging_mode")
    mode = str(explicit or "").strip().lower()
    if mode in {"full", "reduced", "off"}:
        return mode

    exp_id = str(config.get("experiment", {}).get("id") or "").lower()
    description = str(config.get("experiment", {}).get("description") or "").lower()
    replication_markers = ("boundary_densify", "replication", "densify", "follow_up", "follow-up")
    if any(marker in exp_id or marker in description for marker in replication_markers):
        return "reduced"
    return "full"


def _expand_nodes(config: dict) -> list[dict]:
    """Return a flat list of node config dicts.

    Supports both the legacy ``nodes`` list and the compact ``node_groups``
    format, which expands each group into individually-identified nodes using
    zero-padded indices (e.g. id_prefix="fn_", count=8 → fn_01 … fn_08).
    """
    if "nodes" in config:
        return config["nodes"]
    result: list[dict] = []
    for group in config.get("node_groups", []):
        count = group["count"]
        prefix = group["id_prefix"]
        width = len(str(count))
        base = {k: v for k, v in group.items() if k not in ("count", "id_prefix")}
        for i in range(1, count + 1):
            node_cfg = dict(base)
            node_cfg["id"] = f"{prefix}{str(i).zfill(width)}"
            result.append(node_cfg)
    return result


def _expand_claims(config: dict) -> list[dict]:
    """Return a flat list of claim config dicts.

    Supports both the legacy ``claims`` list and the compact ``claim_groups``
    format, which expands each group into individually-identified claims using
    zero-padded indices (e.g. id_prefix="cl_easy_", count=12 → cl_easy_01 … cl_easy_12).
    """
    if "claims" in config:
        return config["claims"]
    result: list[dict] = []
    for group in config.get("claim_groups", []):
        count = group["count"]
        prefix = group["id_prefix"]
        width = len(str(count))
        base = {k: v for k, v in group.items() if k not in ("count", "id_prefix")}
        for i in range(1, count + 1):
            claim_cfg = dict(base)
            claim_cfg["id"] = f"{prefix}{str(i).zfill(width)}"
            result.append(claim_cfg)
    return result


@dataclass
class SimulationModel:
    config: dict
    out_dir: Path
    rng: random.Random = field(init=False)
    np_rng: np.random.Generator = field(init=False)
    nodes: dict[str, Node] = field(default_factory=dict)
    node_personas: dict[str, str | None] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    graph: nx.Graph = field(init=False)
    primitives: dict[str, Any] = field(default_factory=dict)
    trust: TrustNetwork = field(init=False)
    event_log: EventLog = field(init=False)
    tick: int = 0

    def __post_init__(self):
        seed = self.config["experiment"]["seed"]
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        random.seed(seed)
        np.random.seed(seed)
        self._build_nodes()
        self._build_claims()
        self._build_network()
        self._assign_visible_claims()
        self.primitives = make_primitives(self.config.get("primitives", {}))
        self._build_trust()
        primitives_active = self._primitives_active_summary()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        exp_id = self.config["experiment"]["id"]
        self.event_log = EventLog(
            self.out_dir / f"{exp_id}_event_log.jsonl",
            primitives_active,
            state_transition_logging_mode=_state_transition_logging_mode(self.config),
        )

    def _build_nodes(self):
        for ncfg in _expand_nodes(self.config):
            node = node_from_config(ncfg)
            self.nodes[node.id] = node
            self.node_personas[node.id] = ncfg.get("persona")

    def _build_claims(self):
        for ccfg in _expand_claims(self.config):
            c = Claim(
                id=ccfg["id"],
                state=EpistemicState(ccfg["initial_state"]),
                ground_truth=ccfg.get("ground_truth"),
                domain=ccfg.get("domain"),
                difficulty=ccfg.get("difficulty", 0.5),
                ambiguity=ccfg.get("ambiguity", 0.5),
            )
            self.claims[c.id] = c

    def _build_network(self):
        net_cfg = self.config.get("network", {})
        topology = net_cfg.get("topology", "complete")
        n = len(self.nodes)
        node_list = list(self.nodes.keys())

        if topology == "small_world":
            k = net_cfg.get("k", 4)
            p = net_cfg.get("p", 0.1)
            g = nx.watts_strogatz_graph(n, min(k, n-1), p, seed=self.config["experiment"]["seed"])
        elif topology == "scale_free":
            m = net_cfg.get("m", 2)
            g = nx.barabasi_albert_graph(n, m, seed=self.config["experiment"]["seed"])
        elif topology == "ring":
            g = nx.cycle_graph(n)
        elif topology == "complete":
            g = nx.complete_graph(n)
        elif topology == "random":
            g = nx.erdos_renyi_graph(n, 0.5, seed=self.config["experiment"]["seed"])
        elif topology == "custom":
            g = nx.Graph()
            g.add_nodes_from(range(n))
            for edge in net_cfg.get("custom_edges", []):
                g.add_edge(*edge)
        else:
            g = nx.complete_graph(n)

        # Relabel nodes to use node ids
        mapping = {i: node_list[i] for i in range(n)}
        self.graph = nx.relabel_nodes(g, mapping)

    def _assign_visible_claims(self):
        """Each node can see all claims (v1 shared semantic substrate)."""
        claim_ids = list(self.claims.keys())
        for node in self.nodes.values():
            node.visible_claims = list(claim_ids)

    def _build_trust(self):
        trust_cfg = self.config.get("trust_network", {})
        self.trust = TrustNetwork(
            node_ids=list(self.nodes.keys()),
            dynamic=trust_cfg.get("dynamic", False),
            update_rule=trust_cfg.get("update_rule"),
            initial_weights=trust_cfg.get("initial_weights", "uniform"),
        )

    def _primitives_active_summary(self) -> dict:
        primitives_cfg = self.config.get("primitives", {})
        return primitives_cfg

    def _authority_enabled(self) -> bool:
        acfg = self.config.get("primitives", {}).get("authority", False)
        return bool(acfg)

    def step(self):
        """Execute one tick of the simulation (10-step sequence)."""
        tick = self.tick
        primitives = self.primitives

        # Step 0 (dynamics pre-step): cycling — eject operationalised claims back to revisable
        # before nodes observe, so ejected claims re-enter the governance queue this tick.
        # Previously ran after transitions (Step 9), so claims were already archived before
        # cycling could fire — root cause of B3 absorbing state artefact.
        revisability_rate = self.config.get("dynamics", {}).get("revisability_rate", 0.0)
        if revisability_rate > 0.0:
            for cid, claim in self.claims.items():
                if claim.state == EpistemicState.OPERATIONALISED:
                    if self.rng.random() < revisability_rate:
                        claim.state = EpistemicState.REVISABLE
                        claim.ticks_in_state = 0
                        claim.last_reversion_tick = tick
                        self.event_log.emit_transition(
                            tick=tick,
                            node_id="__dynamics__",
                            claim_id=cid,
                            from_state="operationalised",
                            to_state="revisable",
                            authority_invoked=None,
                            confidence_score=0.0,
                            claim_difficulty=claim.difficulty,
                            claim_ambiguity=claim.ambiguity,
                            influencing_nodes=[],
                            trust_weights={},
                        )

        # Step 1: Observe — randomise node order
        node_ids = list(self.nodes.keys())
        self.rng.shuffle(node_ids)

        # Build perceived states for each node
        perceived: dict[str, dict[str, str]] = {}
        for nid in node_ids:
            perceived[nid] = primitives["observation"].observe(nid, self.claims, self.np_rng)

        # Step 2: Propose — each node proposes transitions for claims it can see
        proposals: list[Proposal] = []
        for nid in node_ids:
            node = self.nodes[nid]
            for cid in node.visible_claims:
                perceived_state_str = perceived[nid].get(cid)
                if perceived_state_str is None:
                    continue
                try:
                    perceived_state = EpistemicState(perceived_state_str)
                except ValueError:
                    continue
                # Determine next possible states — sorted for deterministic proposal order
                # (set iteration is hash-seed-dependent; sort by value avoids that)
                from engine.claims import TRANSITIONS
                claim = self.claims.get(cid)
                min_ticks_before_archive = self.config.get("dynamics", {}).get(
                    "min_ticks_before_archive", 0
                )
                next_states = sorted(TRANSITIONS.get(perceived_state, set()), key=lambda s: s.value)
                for next_state in next_states:
                    # B3 fix: suppress archive proposals until claim has dwelled long enough.
                    # Without this, 100 nodes simultaneously archive claims in 1 tick,
                    # leaving no operationalised claims for the cycling mechanism to act on.
                    if (next_state == EpistemicState.ARCHIVED
                            and min_ticks_before_archive > 0
                            and claim is not None
                            and claim.ticks_in_state < min_ticks_before_archive):
                        continue
                    if validate_transition(perceived_state, next_state):
                        proposals.append(Proposal(
                            node_id=nid,
                            claim_id=cid,
                            from_state=perceived_state.value,
                            to_state=next_state.value,
                            confidence_score=node.authority_weight,
                        ))

        # Deduplicate: one proposal per (node, claim, to_state)
        seen = set()
        unique_proposals = []
        for p in proposals:
            key = (p.node_id, p.claim_id, p.to_state)
            if key not in seen:
                seen.add(key)
                unique_proposals.append(p)
        proposals = unique_proposals

        # Step 3: Boundary
        proposals = primitives["boundary"].filter_proposals(proposals, self.nodes, self.claims, tick)

        # Step 4: Weight — authority
        proposals = primitives["authority"].weight_proposals(proposals, self.nodes, self.claims)

        # Step 5: Mediate
        proposals, mediation_events = primitives["mediation"].mediate(proposals, self.nodes, self.claims, tick)

        # Step 6: Threshold — confidence
        accepted, blocked = primitives["confidence"].check_threshold(proposals, self.nodes, self.claims)

        # Check reversibility for reversion proposals
        accepted, reversion_events = primitives["reversibility"].check_reversibility(accepted, self.nodes, self.claims, tick)

        # Step 7: Resolve — pick winning proposal per claim (highest confidence_score)
        # Group by claim_id, pick best
        by_claim: dict[str, list[Proposal]] = {}
        for p in accepted:
            by_claim.setdefault(p.claim_id, []).append(p)

        resolved: list[Proposal] = []
        for cid, props in by_claim.items():
            claim = self.claims[cid]
            valid_props = [p for p in props if p.from_state == claim.state.value and validate_transition(claim.state, EpistemicState(p.to_state))]
            if valid_props:
                # Pick highest confidence_score
                best = max(valid_props, key=lambda p: p.confidence_score)
                resolved.append(best)

        # Apply transitions
        actually_transitioned: list[Proposal] = []
        for p in resolved:
            claim = self.claims[p.claim_id]
            new_state = EpistemicState(p.to_state)
            if validate_transition(claim.state, new_state):
                old_state = claim.state
                claim.state = new_state
                claim.ticks_in_state = 0
                if new_state == EpistemicState.OPERATIONALISED:
                    claim.operationalised_at = tick
                if new_state in (EpistemicState.REVISABLE, EpistemicState.CONTESTED) and old_state in (EpistemicState.OPERATIONALISED, EpistemicState.REVISABLE):
                    claim.last_reversion_tick = tick
                actually_transitioned.append(p)

        # Increment ticks_in_state for non-transitioned claims
        transitioned_ids = {p.claim_id for p in actually_transitioned}
        for cid, claim in self.claims.items():
            if cid not in transitioned_ids:
                claim.ticks_in_state += 1

        # Step 8: Record lineage
        primitives["lineage"].record_lineage(actually_transitioned, self.claims, tick)

        # Step 9: Trust update + authority accumulation
        trust_events = []
        dynamics_cfg = self.config.get("dynamics", {})
        weight_cap = dynamics_cfg.get("weight_cap", 5.0)
        persona_weight_caps = dynamics_cfg.get("weight_cap_by_persona", {})
        if not isinstance(persona_weight_caps, dict):
            persona_weight_caps = {}
        for p in actually_transitioned:
            trust_events.extend(self.trust.update(p.node_id, success=True))
            # Authority accumulation: if authority primitive is active,
            # nodes gain weight on successful transitions (creates Gini growth)
            if self._authority_enabled():
                node = self.nodes.get(p.node_id)
                if node:
                    persona = self.node_personas.get(p.node_id)
                    effective_cap = persona_weight_caps.get(persona, weight_cap)
                    node.authority_weight = min(effective_cap, node.authority_weight + 0.05)

        # Update temporal positions if lineage enabled
        lineage_cfg = self.config.get("primitives", {}).get("lineage", False)
        lineage_enabled = (isinstance(lineage_cfg, dict) and lineage_cfg.get("enabled", False)) or lineage_cfg is True
        if lineage_enabled:
            for node in self.nodes.values():
                if node.compounding_rate > 0:
                    node.temporal_position = min(1.0, node.temporal_position + node.compounding_rate * 0.01)

        # Step 10: Log
        for p in actually_transitioned:
            node = self.nodes.get(p.node_id)
            claim = self.claims.get(p.claim_id)
            self.event_log.emit_transition(
                tick=tick,
                node_id=p.node_id,
                claim_id=p.claim_id,
                from_state=p.from_state,
                to_state=p.to_state,
                authority_invoked=p.authority_invoked,
                confidence_score=p.confidence_score,
                claim_difficulty=claim.difficulty if claim else 0.5,
                claim_ambiguity=claim.ambiguity if claim else 0.5,
                influencing_nodes=[p.node_id],
                trust_weights={k[1]: v for k, v in self.trust.weights.items() if k[0] == p.node_id},
            )

        for p in blocked:
            self.event_log.emit_blocked(tick, p.node_id, p.claim_id, p.from_state, p.to_state, reason="confidence_threshold")

        # Snapshot at record_interval
        record_interval = self.config["experiment"].get("record_interval", 10)
        if tick % record_interval == 0:
            self.event_log.emit_snapshot(tick, self.claims, self.nodes, self.trust.snapshot())

        self.tick += 1

    def run(self, ticks: int | None = None):
        """Run the full simulation."""
        n_ticks = ticks or self.config["experiment"]["ticks"]
        for _ in range(n_ticks):
            self.step()
        self.event_log.close()
