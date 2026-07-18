#!/usr/bin/env python3
"""Polling watcher: monitors inbox/ for YAML configs and writes runs to raw data store."""
from __future__ import annotations

import json
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from engine.claims import EpistemicState
from engine.model import SimulationModel
from engine.scorecard import compute_scorecard
from run import ARCHIVE_CONFIGS, ARCHIVE_RESULTS, archive_run

INBOX = Path('inbox')
OUTBOX = ARCHIVE_RESULTS
POLL_INTERVAL = 5  # seconds

REQUIRED_FIELDS = ['experiment', 'network']
REQUIRED_EXP_FIELDS = ['id', 'seed', 'ticks']
VALID_STATES = {s.value for s in EpistemicState}


def validate_config(config: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in config:
            errors.append(f'Missing required field: {field}')
    has_nodes = 'nodes' in config or 'node_groups' in config
    has_claims = 'claims' in config or 'claim_groups' in config
    if not has_nodes:
        errors.append('Missing required field: nodes or node_groups')
    if not has_claims:
        errors.append('Missing required field: claims or claim_groups')
    exp = config.get('experiment', {})
    for field in REQUIRED_EXP_FIELDS:
        if field not in exp:
            errors.append(f'Missing experiment.{field}')
    for claim in config.get('claims', []):
        state = claim.get('initial_state', '')
        if state not in VALID_STATES:
            errors.append(f"Claim {claim.get('id', '?')}: invalid initial_state '{state}'")
    return errors


def run_config(config_path: Path) -> Path:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    exp_id = config['experiment']['id']
    seed = config['experiment']['seed']
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_dir = OUTBOX / f'{exp_id}_{seed}_{ts}'
    out_dir.mkdir(parents=True, exist_ok=False)

    random.seed(seed)
    np.random.seed(seed)

    model = SimulationModel(config=config, out_dir=out_dir)
    model.run()

    scorecard = compute_scorecard(out_dir / f'{exp_id}_event_log.jsonl', config)
    with open(out_dir / f'{exp_id}_scorecard.json', 'w') as f:
        json.dump(scorecard, f, indent=2)

    return out_dir


def watch(poll_interval: int = POLL_INTERVAL) -> None:
    INBOX.mkdir(exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ARCHIVE_CONFIGS.mkdir(parents=True, exist_ok=True)

    print(f'Watcher started. Polling {INBOX}/ every {poll_interval}s...')
    while True:
        for yaml_path in sorted(INBOX.glob('*.yaml')):
            print(f'Found config: {yaml_path.name}')
            try:
                with open(yaml_path) as f:
                    config = yaml.safe_load(f)
                errors = validate_config(config)
                if errors:
                    print(f'  Validation errors: {errors}')
                    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    dest = ARCHIVE_CONFIGS / f'{yaml_path.stem}_INVALID_{ts}.yaml'
                    shutil.move(str(yaml_path), dest)
                    continue

                out_dir = run_config(yaml_path)
                print(f'  Completed. Results in {out_dir}/')

                archive_run(yaml_path, out_dir)
                print(f'  Config snapshot: {ARCHIVE_CONFIGS / (out_dir.name + ".yaml")}')
                yaml_path.unlink()

            except Exception as e:
                print(f'  Error processing {yaml_path.name}: {e}')
                import traceback

                traceback.print_exc()

        time.sleep(poll_interval)


if __name__ == '__main__':
    import sys

    interval = int(sys.argv[1]) if len(sys.argv) > 1 else POLL_INTERVAL
    watch(interval)
