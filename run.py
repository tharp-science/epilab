#!/usr/bin/env python3
"""Entry point for running an experiment from a YAML config."""
from __future__ import annotations

import json
import os
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from engine.model import SimulationModel
from engine.scorecard import compute_scorecard

RAW_ROOT = Path(os.environ.get('EGLAB_RAW_ROOT', '/srv/eglab/data'))
RUNS_DIR = Path(os.environ.get('EGLAB_RUNS_DIR', str(RAW_ROOT / 'runs')))
CONFIG_SNAPSHOTS_DIR = Path(
    os.environ.get('EGLAB_CONFIG_SNAPSHOTS_DIR', str(RAW_ROOT / 'config_snapshots'))
)

# Backward-compatible aliases for existing imports in watcher.py
ARCHIVE_CONFIGS = CONFIG_SNAPSHOTS_DIR
ARCHIVE_RESULTS = RUNS_DIR


def make_out_dir(exp_id: str, seed: int) -> Path:
    """Create a unique run directory directly in the raw data store."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_dir = RUNS_DIR / f'{exp_id}_{seed}_{ts}'
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def archive_run(config_path: Path, out_dir: Path) -> None:
    """Persist the exact config snapshot for a run in raw data store."""
    CONFIG_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = out_dir.name
    shutil.copy2(config_path, CONFIG_SNAPSHOTS_DIR / f'{stem}.yaml')


def main(config_path: str, seed_override: int | None = None) -> None:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    exp_id = config['experiment']['id']
    seed = seed_override if seed_override is not None else config['experiment']['seed']
    config['experiment']['seed'] = seed
    out_dir = make_out_dir(exp_id, seed)

    random.seed(seed)
    np.random.seed(seed)

    model = SimulationModel(config=config, out_dir=out_dir)
    model.run()

    scorecard = compute_scorecard(out_dir / f'{exp_id}_event_log.jsonl', config)
    scorecard_path = out_dir / f'{exp_id}_scorecard.json'
    with open(scorecard_path, 'w') as f:
        json.dump(scorecard, f, indent=2)

    archive_run(Path(config_path), out_dir)

    print(f'Experiment {exp_id} complete. Results in {out_dir}/')
    print(f'Config snapshot: {CONFIG_SNAPSHOTS_DIR / (out_dir.name + ".yaml")}')
    print(f'Scorecard: {json.dumps(scorecard["metrics"], indent=2)}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Path to YAML config')
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Override the seed in the config (for multi-seed runs)',
    )
    args = parser.parse_args()
    main(args.config, seed_override=args.seed)
