from __future__ import annotations
from engine.primitives import Proposal


class BoundaryPrimitive:
    """Boundary: nodes can only influence claims they are adjacent to in the network.
    Since network adjacency is handled in the model's visible_claims, this primitive
    enforces that proposals are only for claims the node can actually see."""
    name = "boundary"

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        result = []
        for p in proposals:
            node = nodes.get(p.node_id)
            if node and p.claim_id in node.visible_claims:
                result.append(p)
        return result

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        return proposals

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        return proposals, []

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        return []

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        return {cid: c.state.value for cid, c in claims.items()}
