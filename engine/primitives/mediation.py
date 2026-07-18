from __future__ import annotations
from engine.primitives import Proposal


class MediationPrimitive:
    """Mediation: contested claims require a mediating node (has 'control' authority type)."""
    name = "mediation"

    def __init__(self, mode: str = "structured"):
        self.mode = mode  # structured | majority_vote | none

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        return proposals

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        return proposals

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        """For contested claims, require mediation based on mode."""
        events = []
        if self.mode == "none":
            # Block all contested transitions
            surviving = [p for p in proposals if p.from_state != "contested"]
            return surviving, events

        if self.mode == "majority_vote":
            # Contested transitions resolved by majority
            return proposals, events

        # structured: require at least one node with 'control' authority to be proposing
        contested = [p for p in proposals if p.from_state == "contested"]
        non_contested = [p for p in proposals if p.from_state != "contested"]

        # Group contested proposals by claim
        by_claim: dict[str, list[Proposal]] = {}
        for p in contested:
            by_claim.setdefault(p.claim_id, []).append(p)

        surviving_contested = []
        for claim_id, props in by_claim.items():
            # Check if any proposer has control authority
            has_mediator = any(
                "control" in nodes[p.node_id].authority_types
                for p in props if p.node_id in nodes
            )
            if has_mediator:
                surviving_contested.extend(props)
            # else: all proposals for this contested claim are dropped

        return non_contested + surviving_contested, events

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        return proposals, []

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        return []

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        return {cid: c.state.value for cid, c in claims.items()}
