from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

PERSONA_DEFAULTS: dict[str, dict] = {
    "founding_node": {
        "authority_types": ["signal", "temporal", "control", "perceptual"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.25,
        "reversibility_tolerance": 0.15,
        "temporal_position": 0.90,
        "compounding_rate": 0.02,
    },
    "peripheral_node": {
        "authority_types": ["signal"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.70,
        "reversibility_tolerance": 0.65,
        "temporal_position": 0.10,
        "compounding_rate": 0.00,
    },
    "mediating_node": {
        "authority_types": ["control"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.50,
        "reversibility_tolerance": 0.50,
        "temporal_position": 0.40,
        "compounding_rate": 0.00,
    },
    "skeptical_peer": {
        "authority_types": ["signal", "perceptual"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.80,
        "reversibility_tolerance": 0.70,
        "temporal_position": 0.30,
        "compounding_rate": 0.00,
    },
    "fast_mover": {
        "authority_types": ["signal", "temporal"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.20,
        "reversibility_tolerance": 0.10,
        "temporal_position": 0.50,
        "compounding_rate": 0.05,
    },
    "latecomer": {
        "authority_types": ["signal"],
        "authority_weight": 1.0,
        "confidence_threshold": 0.55,
        "reversibility_tolerance": 0.45,
        "temporal_position": 0.05,
        "compounding_rate": 0.00,
    },
}


@dataclass
class Node:
    id: str
    authority_types: list[str]
    authority_weight: float
    confidence_threshold: float
    reversibility_tolerance: float
    temporal_position: float
    compounding_rate: float
    # runtime state
    visible_claims: list[str] = field(default_factory=list)  # claim ids this node can see


def node_from_config(cfg: dict) -> Node:
    """Build a Node from config dict, applying persona defaults if specified."""
    persona = cfg.get("persona")
    if persona and persona in PERSONA_DEFAULTS:
        defaults = dict(PERSONA_DEFAULTS[persona])
    else:
        defaults = {
            "authority_types": [],
            "authority_weight": 1.0,
            "confidence_threshold": 0.5,
            "reversibility_tolerance": 0.5,
            "temporal_position": 0.0,
            "compounding_rate": 0.0,
        }
    # override with explicit values
    for key in ["authority_types", "authority_weight", "confidence_threshold",
                "reversibility_tolerance", "temporal_position", "compounding_rate"]:
        if key in cfg:
            defaults[key] = cfg[key]
    return Node(
        id=cfg["id"],
        authority_types=defaults["authority_types"],
        authority_weight=defaults["authority_weight"],
        confidence_threshold=defaults["confidence_threshold"],
        reversibility_tolerance=defaults["reversibility_tolerance"],
        temporal_position=defaults["temporal_position"],
        compounding_rate=defaults["compounding_rate"],
    )
