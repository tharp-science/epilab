import json
from pathlib import Path

from engine.scorecard import compute_scorecard


def _base_config(exp_id: str) -> dict:
    return {
        "experiment": {"id": exp_id, "seed": 1, "ticks": 10, "record_interval": 10},
        "claims": [
            {
                "id": "c1",
                "initial_state": "unknown",
                "ground_truth": True,
                "difficulty": 0.5,
                "ambiguity": 0.5,
            }
        ],
        "hypotheses": [],
        "dynamics": {},
    }


def _write_events(path: Path, events: list[dict]) -> None:
    with open(path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def test_channel_specialization_metrics_detect_merged_ownership(tmp_path):
    config = _base_config("merged_case")
    log_path = tmp_path / "merged_case_event_log.jsonl"

    events = [
        {"event_type": "system_snapshot", "tick": 0, "authority_weights": {"n1": 1.0, "n2": 1.0}, "claims": {"c1": "unknown"}},
        {"event_type": "state_transition", "tick": 1, "node_id": "n1", "claim_id": "c1", "from_state": "unknown", "to_state": "hypothesised"},
        {"event_type": "state_transition", "tick": 2, "node_id": "n1", "claim_id": "c1", "from_state": "contested", "to_state": "provisionally_accepted"},
        {"event_type": "state_transition", "tick": 3, "node_id": "n1", "claim_id": "c1", "from_state": "operationalised", "to_state": "revisable"},
        {"event_type": "state_transition", "tick": 4, "node_id": "n1", "claim_id": "c1", "from_state": "revisable", "to_state": "contested"},
    ]
    _write_events(log_path, events)

    scorecard = compute_scorecard(log_path, config)
    metrics = scorecard["metrics"]

    assert metrics["forward_channel_transitions"] == 2
    assert metrics["reversion_channel_transitions"] == 2
    assert metrics["channel_top1_owner_overlap"] == 1.0
    assert metrics["channel_top1_owner_overlap_early"] == 1.0
    assert metrics["channel_specialization_tvd"] == 0.0
    assert metrics["forward_channel_top1_share"] == 1.0
    assert metrics["reversion_channel_top1_share"] == 1.0
    assert metrics["forward_capture_tick_top1_ge_threshold"] == 1
    assert metrics["reversion_capture_tick_top1_ge_threshold"] == 3
    assert metrics["channel_capture_share_threshold"] == 0.8
    assert metrics["channel_early_horizon_tick"] == 10


def test_channel_specialization_metrics_detect_split_ownership(tmp_path):
    config = _base_config("split_case")
    log_path = tmp_path / "split_case_event_log.jsonl"

    events = [
        {"event_type": "system_snapshot", "tick": 0, "authority_weights": {"n1": 1.0, "n2": 1.0}, "claims": {"c1": "unknown"}},
        {"event_type": "state_transition", "tick": 1, "node_id": "n1", "claim_id": "c1", "from_state": "unknown", "to_state": "hypothesised"},
        {"event_type": "state_transition", "tick": 2, "node_id": "n1", "claim_id": "c1", "from_state": "contested", "to_state": "provisionally_accepted"},
        {"event_type": "state_transition", "tick": 3, "node_id": "n2", "claim_id": "c1", "from_state": "operationalised", "to_state": "revisable"},
        {"event_type": "state_transition", "tick": 4, "node_id": "n2", "claim_id": "c1", "from_state": "revisable", "to_state": "contested"},
    ]
    _write_events(log_path, events)

    scorecard = compute_scorecard(log_path, config)
    metrics = scorecard["metrics"]

    assert metrics["forward_channel_transitions"] == 2
    assert metrics["reversion_channel_transitions"] == 2
    assert metrics["channel_top1_owner_overlap"] == 0.0
    assert metrics["channel_top1_owner_overlap_early"] == 0.0
    assert metrics["channel_specialization_tvd"] == 1.0
    assert metrics["forward_channel_top1_share"] == 1.0
    assert metrics["reversion_channel_top1_share"] == 1.0
    assert metrics["forward_capture_tick_top1_ge_threshold"] == 1
    assert metrics["reversion_capture_tick_top1_ge_threshold"] == 3
    assert metrics["channel_capture_share_threshold"] == 0.8
    assert metrics["channel_early_horizon_tick"] == 10
