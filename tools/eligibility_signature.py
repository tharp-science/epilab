#!/usr/bin/env python3
"""Compute eligibility-topology signature for an experiment config.

This tool formalizes the Batch-07 control parameters from config alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.agents import PERSONA_DEFAULTS

S_TYPES = {"signal", "perceptual"}
C_TYPES = {"control", "temporal"}
REVERSION_THRESHOLD = 0.3


def _expand_nodes(config: dict) -> list[dict]:
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


def _materialize_node(node_cfg: dict) -> dict:
    persona = node_cfg.get("persona")
    defaults = PERSONA_DEFAULTS.get(persona, {})
    authority_types = set(node_cfg.get("authority_types", defaults.get("authority_types", [])))
    reversibility_tolerance = node_cfg.get(
        "reversibility_tolerance",
        defaults.get("reversibility_tolerance", 0.5),
    )
    return {
        "persona": persona,
        "authority_types": authority_types,
        "reversibility_tolerance": reversibility_tolerance,
    }


def _ratio(n: int, d: int) -> float | None:
    return (n / d) if d > 0 else None


def build_signature(config: dict) -> dict:
    node_cfgs = _expand_nodes(config)
    nodes = [_materialize_node(n) for n in node_cfgs]

    n_total = len(nodes)
    s_count = 0
    c_count = 0
    r_count = 0
    cr_count = 0
    sr_count = 0

    by_persona: dict[str, dict[str, int]] = {}

    for node in nodes:
        persona = node.get("persona") or "unknown"
        stats = by_persona.setdefault(
            persona,
            {
                "count": 0,
                "s_eligible": 0,
                "c_eligible": 0,
                "r_eligible": 0,
                "cr_eligible": 0,
                "sr_eligible": 0,
            },
        )
        stats["count"] += 1

        has_s = len(node["authority_types"] & S_TYPES) > 0
        has_c = len(node["authority_types"] & C_TYPES) > 0
        has_r = node["reversibility_tolerance"] >= REVERSION_THRESHOLD
        has_cr = has_c and has_r
        has_sr = has_s and has_r

        s_count += int(has_s)
        c_count += int(has_c)
        r_count += int(has_r)
        cr_count += int(has_cr)
        sr_count += int(has_sr)

        stats["s_eligible"] += int(has_s)
        stats["c_eligible"] += int(has_c)
        stats["r_eligible"] += int(has_r)
        stats["cr_eligible"] += int(has_cr)
        stats["sr_eligible"] += int(has_sr)

    c_or_r = c_count + r_count - cr_count
    jaccard_c_r = _ratio(cr_count, c_or_r)

    # Distribution of CR-eligible actors across personas (captures concentration/asymmetry).
    cr_distribution = {
        persona: (_ratio(stats["cr_eligible"], cr_count) if cr_count > 0 else 0.0)
        for persona, stats in by_persona.items()
    }
    cr_hhi = sum(v * v for v in cr_distribution.values()) if cr_distribution else 0.0

    persona_ratios: dict[str, dict[str, float | None]] = {}
    for persona, stats in by_persona.items():
        count = stats["count"]
        persona_ratios[persona] = {
            "rho_s": _ratio(stats["s_eligible"], count),
            "rho_c": _ratio(stats["c_eligible"], count),
            "rho_r": _ratio(stats["r_eligible"], count),
            "rho_cr": _ratio(stats["cr_eligible"], count),
            "rho_sr": _ratio(stats["sr_eligible"], count),
            "count": count,
        }

    return {
        "experiment_id": config.get("experiment", {}).get("id"),
        "n_nodes": n_total,
        "reversion_threshold": REVERSION_THRESHOLD,
        "overall": {
            "rho_s": _ratio(s_count, n_total),
            "rho_c": _ratio(c_count, n_total),
            "rho_r": _ratio(r_count, n_total),
            "rho_cr": _ratio(cr_count, n_total),
            "rho_sr": _ratio(sr_count, n_total),
            "jaccard_c_r": jaccard_c_r,
            "cr_persona_hhi": cr_hhi,
        },
        "persona_ratios": persona_ratios,
        "cr_persona_distribution": cr_distribution,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Path to YAML experiment config")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    signature = build_signature(config)
    if args.pretty:
        print(json.dumps(signature, indent=2, sort_keys=True))
    else:
        print(json.dumps(signature))


if __name__ == "__main__":
    main()
