from __future__ import annotations
from engine.primitives import Proposal


class LineagePrimitive:
    """Lineage: records transition history. Enables challenge-by-origin."""
    name = "lineage"

    def __init__(self, retention_probability: float = 1.0):
        self.retention_probability = retention_probability
        self._history: dict[str, list[dict]] = {}  # claim_id -> list of transition records

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        return proposals

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        return proposals

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        return proposals, []

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        import random
        events = []
        for p in accepted:
            if random.random() < self.retention_probability:
                record = {
                    "tick": tick,
                    "claim_id": p.claim_id,
                    "node_id": p.node_id,
                    "from_state": p.from_state,
                    "to_state": p.to_state,
                }
                self._history.setdefault(p.claim_id, []).append(record)
        return events

    def get_history(self, claim_id: str) -> list[dict]:
        return self._history.get(claim_id, [])

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        return proposals, []

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        return {cid: c.state.value for cid, c in claims.items()}
