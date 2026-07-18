"""
find_k1_seed.py — Find seeds that produce the k=1 dominant-node case.

Background (LN-003):
    The authority fixed point depends on whether the first signal-eligible node
    in the tick-0 shuffle holds temporal/control authority (k=1 case) or not (k=2 case).

    k=2 (observed at seeds 42, 123, 7): S* is pn or sp → Gini_end = 49/675 ≈ 0.0726
    k=1 (predicted, not yet observed):  S* is fn or fm → Gini_end = 99/2600 ≈ 0.0381

This script simulates only the tick-0 shuffle (no full simulation) and identifies
which seeds produce k=1. Run this before committing to a full 5000-tick simulation.

Usage:
    python tools/find_k1_seed.py                # scan seeds 0–99
    python tools/find_k1_seed.py --max 500      # scan seeds 0–499
    python tools/find_k1_seed.py --seed 42      # check a single specific seed
"""

import random
import argparse


# Authority types as configured in PERSONA_DEFAULTS (engine/agents.py)
PERSONA_AUTHORITY_TYPES: dict[str, list[str]] = {
    "founding_node":   ["signal", "temporal", "control", "perceptual"],
    "peripheral_node": ["signal"],
    "mediating_node":  ["control"],
    "skeptical_peer":  ["signal", "perceptual"],
    "fast_mover":      ["signal", "temporal"],
}

# Transition authority groups (engine/primitives/authority.py TRANSITION_AUTHORITY)
# S-group: signal or perceptual required
# C-group: control or temporal required
S_GROUP_TYPES = {"signal", "perceptual"}
C_GROUP_TYPES = {"control", "temporal"}


def build_node_list(composition: list[tuple[str, int, str]]) -> list[dict]:
    """Build the ordered node list matching _expand_nodes() output.

    Args:
        composition: list of (persona, count, id_prefix) tuples, in config order.
    """
    nodes = []
    for persona, count, prefix in composition:
        width = len(str(count))
        for i in range(1, count + 1):
            nodes.append({
                "id": f"{prefix}{str(i).zfill(width)}",
                "persona": persona,
                "authority_types": PERSONA_AUTHORITY_TYPES[persona],
            })
    return nodes


def first_signal_eligible(node_ids: list[str], nodes_by_id: dict) -> dict | None:
    """Return the first node in the shuffled list with signal or perceptual authority."""
    for nid in node_ids:
        node = nodes_by_id[nid]
        if S_GROUP_TYPES & set(node["authority_types"]):
            return node
    return None


def check_seed(seed: int, nodes: list[dict]) -> tuple[str, bool]:
    """Return (persona_of_S_star, is_k1) for the given seed."""
    nodes_by_id = {n["id"]: n for n in nodes}
    node_ids = [n["id"] for n in nodes]

    rng = random.Random(seed)
    rng.shuffle(node_ids)

    s_star = first_signal_eligible(node_ids, nodes_by_id)
    if s_star is None:
        return ("none", False)

    # k=1 if S* also has temporal or control authority (wins C-group transitions too)
    has_c_group = bool(C_GROUP_TYPES & set(s_star["authority_types"]))
    return (s_star["persona"], has_c_group)


def main():
    parser = argparse.ArgumentParser(description="Find seeds producing k=1 authority dominant-node case.")
    parser.add_argument("--max", type=int, default=100, help="Scan seeds 0 to max-1 (default: 100)")
    parser.add_argument("--seed", type=int, default=None, help="Check a single seed and exit")
    args = parser.parse_args()

    # Batch 04 reference composition (exp_004a/b/c/d)
    composition = [
        ("founding_node",   8,  "fn_"),
        ("peripheral_node", 52, "pn_"),
        ("mediating_node",  20, "mn_"),
        ("skeptical_peer",  12, "sp_"),
        ("fast_mover",       8, "fm_"),
    ]
    nodes = build_node_list(composition)

    if args.seed is not None:
        persona, is_k1 = check_seed(args.seed, nodes)
        case = "k=1 ✓" if is_k1 else "k=2"
        print(f"Seed {args.seed:4d}: S* persona = {persona:<20s}  →  {case}")
        return

    k1_seeds = []
    k2_seeds = []
    for seed in range(args.max):
        persona, is_k1 = check_seed(seed, nodes)
        if is_k1:
            k1_seeds.append((seed, persona))
        else:
            k2_seeds.append((seed, persona))

    print(f"\nScanned {args.max} seeds (0–{args.max-1})")
    print(f"k=1 seeds ({len(k1_seeds)} found, expected ≈ {args.max * 0.20:.0f}):")
    for seed, persona in k1_seeds:
        print(f"  seed {seed:4d} — S* = {persona}")

    print(f"\nk=2 seeds: {len(k2_seeds)}")
    if k1_seeds:
        print(f"\nRecommended seed for exp_004d: {k1_seeds[0][0]}  (S* = {k1_seeds[0][1]})")
        print(f"  Update exp_004d_k1_sweep.yaml: seed: {k1_seeds[0][0]}")


if __name__ == "__main__":
    main()
