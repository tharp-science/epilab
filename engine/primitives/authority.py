from __future__ import annotations
from engine.primitives import Proposal

# Which authority types are relevant for each transition
TRANSITION_AUTHORITY: dict[tuple[str, str], list[str]] = {
    ("unknown", "hypothesised"): ["signal", "perceptual"],
    ("hypothesised", "contested"): ["signal", "perceptual"],
    ("contested", "provisionally_accepted"): ["control", "temporal"],
    ("provisionally_accepted", "operationalised"): ["control", "temporal"],
    ("operationalised", "revisable"): ["perceptual", "signal"],
    ("operationalised", "archived"): ["control", "temporal"],
    ("revisable", "contested"): ["signal", "perceptual"],
}


class AuthorityPrimitive:
    """Authority: weights proposals by authority type match and weight."""
    name = "authority"

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        return proposals

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        weighted = []
        for p in proposals:
            node = nodes.get(p.node_id)
            if not node:
                weighted.append(p)
                continue
            key = (p.from_state, p.to_state)
            relevant_types = TRANSITION_AUTHORITY.get(key, [])
            # check if node has any relevant authority type
            has_authority = any(t in node.authority_types for t in relevant_types)
            if has_authority or not relevant_types:
                # set confidence score weighted by authority_weight
                p = Proposal(
                    node_id=p.node_id,
                    claim_id=p.claim_id,
                    from_state=p.from_state,
                    to_state=p.to_state,
                    confidence_score=p.confidence_score * node.authority_weight,
                    authority_invoked=next((t for t in relevant_types if t in node.authority_types), None),
                )
                weighted.append(p)
            # if node lacks authority for this transition type, drop the proposal
        return weighted

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
