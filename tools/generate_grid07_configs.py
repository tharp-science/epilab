#!/usr/bin/env python3
"""Generate Grid-07 point configs from manifest and canonical scaffold."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import argparse
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _make_node_groups(x: int) -> list[dict]:
    groups: list[dict] = []

    fn_low = 8 - x
    if fn_low > 0:
        groups.append({"persona": "founding_node", "count": fn_low, "id_prefix": "fnl_"})
    if x > 0:
        groups.append({"persona": "founding_node", "count": x, "id_prefix": "fnh_", "reversibility_tolerance": 0.65})

    groups.append({
        "persona": "peripheral_node",
        "count": 52,
        "id_prefix": "pn_",
        "authority_types": ["signal", "temporal"],
    })
    groups.append({"persona": "mediating_node", "count": 20, "id_prefix": "mn_"})
    groups.append({"persona": "skeptical_peer", "count": 12, "id_prefix": "sp_"})

    fm_low = 8 - x
    if fm_low > 0:
        groups.append({"persona": "fast_mover", "count": fm_low, "id_prefix": "fml_"})
    if x > 0:
        groups.append({"persona": "fast_mover", "count": x, "id_prefix": "fmh_", "reversibility_tolerance": 0.65})

    return groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="configs/exp_007_grid07_manifest.yaml")
    parser.add_argument("--outdir", default="configs")
    parser.add_argument("--seed", type=int, default=2, help="Default config seed; runtime can override via --seed")
    args = parser.parse_args()

    manifest = _load_yaml(ROOT / args.manifest)
    scaffold_path = ROOT / manifest["baseline_scaffold"]["canonical_scaffold_source"]
    scaffold = _load_yaml(scaffold_path)

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    for point in manifest["grid_points"]:
        gid = point["id"]
        x = int(point["x"])
        cfg = deepcopy(scaffold)

        cfg["experiment"]["id"] = f"exp_007_{gid}_x{x}"
        cfg["experiment"]["seed"] = args.seed
        cfg["experiment"]["description"] = (
            "Batch-07 Grid-07 point "
            f"{gid} (x={x}): fn/fm high-tolerance split on canonical 006c-derived scaffold."
        )

        cfg["node_groups"] = _make_node_groups(x)

        # Explicit analysis settings for early-capture diagnostics.
        cfg["analysis"] = {
            "channel_capture_share_threshold": 0.8,
            "channel_early_horizon_tick": 500,
        }

        # Keep hypotheses empty for Grid-07 mapping runs; aggregation is metric-based.
        cfg["hypotheses"] = []

        out_path = outdir / f"exp_007_{gid}_x{x}.yaml"
        with open(out_path, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

        print(out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
