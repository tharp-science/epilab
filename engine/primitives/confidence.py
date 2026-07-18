from __future__ import annotations
from engine.primitives import Proposal


class ConfidencePrimitive:
    """Confidence: applies threshold before accepting transitions."""
    name = "confidence"

    def __init__(self, threshold_mean: float = 0.5, threshold_variance: float = 0.0):
        self.threshold_mean = threshold_mean
        self.threshold_variance = threshold_variance

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        return proposals

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        return proposals

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        """Accept proposals where confidence_score meets the threshold."""
        accepted = []
        blocked = []
        for p in proposals:
            node = nodes.get(p.node_id)
            # Use node's confidence threshold if available, else use mean
            threshold = node.confidence_threshold if node else self.threshold_mean
            # Scale threshold by claim difficulty
            claim = claims.get(p.claim_id)
            difficulty = claim.difficulty if claim else 0.5
            effective_threshold = threshold * (1.0 + difficulty) / 2.0  # blend
            if p.confidence_score >= effective_threshold:
                accepted.append(p)
            else:
                blocked.append(p)
        return accepted, blocked

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        return []

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        return {cid: c.state.value for cid, c in claims.items()}
