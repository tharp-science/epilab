from __future__ import annotations
from engine.primitives import Proposal


class ReversibilityPrimitive:
    """Reversibility: enables state retreat; tracks reversion cost."""
    name = "reversibility"

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        return proposals

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        return proposals

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        return proposals, []

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        return []

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        """Allow reversions based on node's reversibility_tolerance.
        A reversion is when a claim moves to a less resolved state (operationalised -> revisable).
        """
        allowed = []
        reversion_events = []
        # Define "less resolved" transitions
        reversion_transitions = {("operationalised", "revisable"), ("revisable", "contested")}
        for p in proposals:
            key = (p.from_state, p.to_state)
            if key in reversion_transitions:
                node = nodes.get(p.node_id)
                tolerance = node.reversibility_tolerance if node else 0.0
                # Reversion allowed if node has sufficient tolerance
                if tolerance >= 0.3:  # threshold for allowing reversion proposals
                    allowed.append(p)
                    reversion_events.append({
                        "type": "reversion",
                        "claim_id": p.claim_id,
                        "node_id": p.node_id,
                        "from_state": p.from_state,
                        "to_state": p.to_state,
                        "tick": tick,
                    })
            else:
                allowed.append(p)
        return allowed, reversion_events

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        return {cid: c.state.value for cid, c in claims.items()}
