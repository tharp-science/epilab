from __future__ import annotations
from engine.primitives import Proposal
from engine.claims import EpistemicState


class ObservationPrimitive:
    """Observation: models perceptual accuracy; nodes may misread current state."""
    name = "observation"

    def __init__(self, accuracy_mean: float = 1.0, accuracy_variance: float = 0.0):
        self.accuracy_mean = accuracy_mean
        self.accuracy_variance = accuracy_variance

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
        return proposals, []

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        """Return perceived states, potentially with errors based on accuracy."""
        import numpy as np
        all_states = [s.value for s in EpistemicState]
        result = {}
        for cid, claim in claims.items():
            accuracy = self.accuracy_mean
            if self.accuracy_variance > 0:
                accuracy = np.clip(rng.normal(self.accuracy_mean, self.accuracy_variance**0.5), 0, 1)
            if rng.random() < accuracy:
                result[cid] = claim.state.value
            else:
                # misread: pick a random nearby state
                current_idx = all_states.index(claim.state.value)
                # pick adjacent state index
                offset = rng.choice([-1, 1])
                wrong_idx = max(0, min(len(all_states)-1, current_idx + offset))
                result[cid] = all_states[wrong_idx]
        return result
