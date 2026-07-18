from __future__ import annotations
from typing import Protocol, runtime_checkable, Any
from dataclasses import dataclass


@dataclass
class Proposal:
    """A node's proposed state transition for a claim."""
    node_id: str
    claim_id: str
    from_state: str
    to_state: str
    confidence_score: float = 1.0
    authority_invoked: str | None = None


@runtime_checkable
class PrimitiveModule(Protocol):
    """Interface all primitive modules must implement."""
    name: str

    def filter_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> list[Proposal]:
        """Boundary: filter which proposals survive."""
        ...

    def weight_proposals(self, proposals: list[Proposal], nodes: dict, claims: dict) -> list[Proposal]:
        """Authority: apply authority weights to proposals."""
        ...

    def mediate(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        """Mediation: process contested claims; return surviving proposals + events."""
        ...

    def check_threshold(self, proposals: list[Proposal], nodes: dict, claims: dict) -> tuple[list[Proposal], list[Proposal]]:
        """Confidence: return (accepted, blocked) proposals."""
        ...

    def record_lineage(self, accepted: list[Proposal], claims: dict, tick: int) -> list[dict]:
        """Lineage: record transition history; return lineage events."""
        ...

    def check_reversibility(self, proposals: list[Proposal], nodes: dict, claims: dict, tick: int) -> tuple[list[Proposal], list[dict]]:
        """Reversibility: check if reversions are allowed; return (allowed, reversion_events)."""
        ...

    def observe(self, node_id: str, claims: dict, rng) -> dict[str, str]:
        """Observation: return {claim_id: perceived_state} for a node (may differ from actual)."""
        ...


def make_primitives(primitives_cfg: dict) -> dict[str, Any]:
    """Factory: return dict of active primitive modules based on config."""
    from engine.primitives.null import NullPrimitive
    from engine.primitives.boundary import BoundaryPrimitive
    from engine.primitives.lineage import LineagePrimitive
    from engine.primitives.authority import AuthorityPrimitive
    from engine.primitives.mediation import MediationPrimitive
    from engine.primitives.confidence import ConfidencePrimitive
    from engine.primitives.reversibility import ReversibilityPrimitive
    from engine.primitives.observation import ObservationPrimitive

    null = NullPrimitive()
    result = {}

    # boundary
    bcfg = primitives_cfg.get("boundary", False)
    result["boundary"] = BoundaryPrimitive() if bcfg else null

    # lineage
    lcfg = primitives_cfg.get("lineage", False)
    if isinstance(lcfg, dict) and lcfg.get("enabled", False):
        result["lineage"] = LineagePrimitive(retention_probability=lcfg.get("retention_probability", 1.0))
    elif lcfg is True:
        result["lineage"] = LineagePrimitive()
    else:
        result["lineage"] = null

    # authority
    acfg = primitives_cfg.get("authority", False)
    result["authority"] = AuthorityPrimitive() if acfg else null

    # mediation
    mcfg = primitives_cfg.get("mediation", False)
    if isinstance(mcfg, dict) and mcfg.get("enabled", False):
        result["mediation"] = MediationPrimitive(mode=mcfg.get("mode", "structured"))
    elif mcfg is True:
        result["mediation"] = MediationPrimitive()
    else:
        result["mediation"] = null

    # confidence
    ccfg = primitives_cfg.get("confidence", False)
    if isinstance(ccfg, dict) and ccfg.get("enabled", False):
        result["confidence"] = ConfidencePrimitive(
            threshold_mean=ccfg.get("threshold_mean", 0.5),
            threshold_variance=ccfg.get("threshold_variance", 0.0),
        )
    elif ccfg is True:
        result["confidence"] = ConfidencePrimitive()
    else:
        result["confidence"] = null

    # reversibility
    rcfg = primitives_cfg.get("reversibility", False)
    result["reversibility"] = ReversibilityPrimitive() if rcfg else null

    # observation
    ocfg = primitives_cfg.get("observation", False)
    if isinstance(ocfg, dict) and ocfg.get("enabled", False):
        result["observation"] = ObservationPrimitive(
            accuracy_mean=ocfg.get("accuracy_mean", 1.0),
            accuracy_variance=ocfg.get("accuracy_variance", 0.0),
        )
    elif ocfg is True:
        result["observation"] = ObservationPrimitive()
    else:
        result["observation"] = null

    return result
