import pytest
import yaml
import json
import shutil
import copy
from pathlib import Path
from engine.model import SimulationModel
from engine.scorecard import compute_scorecard


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run_experiment(config: dict, tmp_path: Path) -> dict:
    out_dir = tmp_path / f"{config['experiment']['id']}_{config['experiment']['seed']}"
    model = SimulationModel(config=config, out_dir=out_dir)
    model.run()
    exp_id = config["experiment"]["id"]
    return compute_scorecard(out_dir / f"{exp_id}_event_log.jsonl", config)


def test_exp000_no_authority_accumulation(tmp_path):
    """Exp-000 (null governance) should show no Gini growth — authority primitive is off.

    The previous assertion (ESI < 0.4) relied on hash-seed-dependent set
    iteration order to produce cycling behaviour.  With sorted transitions
    (deterministic), null governance archives claims cleanly (ESI ≈ 1.0), which
    is not chaos in the cycling sense but is equally ungoverned: there is no
    quality filtering.  The stable, falsifiable signal for null governance is
    that authority_concentration_gini does NOT grow — no accumulation mechanism
    exists when the authority primitive is disabled.
    """
    config = load_config("configs/exp_000.yaml")
    scorecard = run_experiment(config, tmp_path)
    gini_start = scorecard["metrics"]["authority_concentration_gini_start"]
    gini_end = scorecard["metrics"]["authority_concentration_gini"]
    assert gini_end <= gini_start + 0.05, (
        f"Exp-000 Gini should not grow without authority primitive: "
        f"start={gini_start:.4f}, end={gini_end:.4f}"
    )


def test_exp001_order(tmp_path):
    """Exp-001 (full governance) should produce higher stability and Gini growth."""
    config_000 = load_config("configs/exp_000.yaml")
    config_001 = load_config("configs/exp_001.yaml")

    sc_000 = run_experiment(config_000, tmp_path)
    sc_001 = run_experiment(config_001, tmp_path)

    esi_000 = sc_000["metrics"]["epistemic_stability_index"]
    esi_001 = sc_001["metrics"]["epistemic_stability_index"]

    gini_start = sc_001["metrics"]["authority_concentration_gini_start"]
    gini_end = sc_001["metrics"]["authority_concentration_gini"]

    assert esi_001 >= esi_000, (
        f"Exp-001 should have >= stability vs Exp-000: ESI_001={esi_001}, ESI_000={esi_000}"
    )
    assert gini_end >= gini_start, (
        f"Exp-001 Gini should grow: start={gini_start}, end={gini_end}"
    )


def test_authority_weight_cap_is_configurable(tmp_path):
    """Authority accumulation should respect dynamics.weight_cap when provided."""
    base_config = {
        "experiment": {
            "id": "test_weight_cap",
            "seed": 1,
            "ticks": 30,
            "record_interval": 1000,
        },
        "nodes": [
            {
                "id": "n1",
                "persona": "founding_node",
                "confidence_threshold": 0.0,
                "reversibility_tolerance": 1.0,
            }
        ],
        "claims": [
            {
                "id": "c1",
                "initial_state": "unknown",
                "ground_truth": True,
                "difficulty": 0.5,
                "ambiguity": 0.5,
            }
        ],
        "network": {"topology": "complete"},
        "primitives": {
            "boundary": True,
            "lineage": {"enabled": True, "retention_probability": 1.0},
            "authority": True,
            "mediation": {"enabled": True, "mode": "structured"},
            "confidence": {"enabled": True, "threshold_mean": 0.0, "threshold_variance": 0.0},
            "reversibility": False,
            "observation": False,
        },
        "trust_network": {"dynamic": False, "update_rule": None, "initial_weights": "uniform"},
        "dynamics": {"revisability_rate": 0.0, "min_ticks_before_archive": 0},
        "events": [],
        "hypotheses": [],
    }

    capped_cfg = copy.deepcopy(base_config)
    capped_cfg["dynamics"]["weight_cap"] = 1.2
    capped_model = SimulationModel(config=capped_cfg, out_dir=tmp_path / "cap_on")
    capped_model.run()

    uncapped_cfg = copy.deepcopy(base_config)
    uncapped_model = SimulationModel(config=uncapped_cfg, out_dir=tmp_path / "cap_off")
    uncapped_model.run()

    assert capped_model.nodes["n1"].authority_weight == pytest.approx(1.2)
    assert uncapped_model.nodes["n1"].authority_weight > 1.2


def _logging_mode_config(mode: str) -> dict:
    return {
        "experiment": {
            "id": f"test_transition_logging_{mode}",
            "seed": 1,
            "ticks": 20,
            "record_interval": 1000,
        },
        "logging": {
            "state_transition_logging_mode": mode,
        },
        "nodes": [
            {
                "id": "n1",
                "persona": "founding_node",
                "confidence_threshold": 0.0,
                "reversibility_tolerance": 1.0,
            }
        ],
        "claims": [
            {
                "id": "c1",
                "initial_state": "unknown",
                "ground_truth": True,
                "difficulty": 0.5,
                "ambiguity": 0.5,
            }
        ],
        "network": {"topology": "complete"},
        "primitives": {
            "boundary": True,
            "lineage": {"enabled": True, "retention_probability": 1.0},
            "authority": True,
            "mediation": {"enabled": True, "mode": "structured"},
            "confidence": {"enabled": True, "threshold_mean": 0.0, "threshold_variance": 0.0},
            "reversibility": False,
            "observation": False,
        },
        "trust_network": {"dynamic": False, "update_rule": None, "initial_weights": "uniform"},
        "dynamics": {"revisability_rate": 0.0, "min_ticks_before_archive": 0},
        "events": [],
        "hypotheses": [],
    }


def test_reduced_transition_logging_preserves_scorecard_metrics(tmp_path):
    full_cfg = _logging_mode_config("full")
    reduced_cfg = _logging_mode_config("reduced")

    full_dir = tmp_path / "full"
    reduced_dir = tmp_path / "reduced"
    SimulationModel(config=full_cfg, out_dir=full_dir).run()
    SimulationModel(config=reduced_cfg, out_dir=reduced_dir).run()

    full_scorecard = compute_scorecard(full_dir / f"{full_cfg['experiment']['id']}_event_log.jsonl", full_cfg)
    reduced_scorecard = compute_scorecard(reduced_dir / f"{reduced_cfg['experiment']['id']}_event_log.jsonl", reduced_cfg)

    for metric in [
        "total_state_transitions",
        "forward_channel_transitions",
        "reversion_channel_transitions",
        "interpretive_drift_rate",
        "epistemic_stability_index",
    ]:
        assert reduced_scorecard["metrics"][metric] == full_scorecard["metrics"][metric]


def test_reduced_transition_logging_strips_bulky_fields(tmp_path):
    cfg = _logging_mode_config("reduced")
    out_dir = tmp_path / "reduced_fields"
    SimulationModel(config=cfg, out_dir=out_dir).run()

    log_path = out_dir / f"{cfg['experiment']['id']}_event_log.jsonl"
    transitions = []
    with log_path.open() as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("event_type") == "state_transition":
                transitions.append(event)
    assert transitions
    sample = transitions[0]
    assert {"tick", "event_type", "node_id", "claim_id", "from_state", "to_state"} <= set(sample.keys())
    assert "trust_weights_at_tick" not in sample
    assert "influencing_nodes" not in sample
    assert "claim_difficulty" not in sample


def test_off_transition_logging_disables_transition_events(tmp_path):
    cfg = _logging_mode_config("off")
    out_dir = tmp_path / "off"
    SimulationModel(config=cfg, out_dir=out_dir).run()

    log_path = out_dir / f"{cfg['experiment']['id']}_event_log.jsonl"
    with log_path.open() as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    assert all(event.get("event_type") != "state_transition" for event in events)


def test_persona_weight_cap_overrides_global_weight_cap(tmp_path):
    """Persona-specific cap should take precedence over global weight_cap."""
    config = {
        "experiment": {
            "id": "test_weight_cap_by_persona_override",
            "seed": 1,
            "ticks": 30,
            "record_interval": 1000,
        },
        "nodes": [
            {
                "id": "n1",
                "persona": "founding_node",
                "confidence_threshold": 0.0,
                "reversibility_tolerance": 1.0,
            }
        ],
        "claims": [
            {
                "id": "c1",
                "initial_state": "unknown",
                "ground_truth": True,
                "difficulty": 0.5,
                "ambiguity": 0.5,
            }
        ],
        "network": {"topology": "complete"},
        "primitives": {
            "boundary": True,
            "lineage": {"enabled": True, "retention_probability": 1.0},
            "authority": True,
            "mediation": {"enabled": True, "mode": "structured"},
            "confidence": {"enabled": True, "threshold_mean": 0.0, "threshold_variance": 0.0},
            "reversibility": False,
            "observation": False,
        },
        "trust_network": {"dynamic": False, "update_rule": None, "initial_weights": "uniform"},
        "dynamics": {
            "revisability_rate": 0.0,
            "min_ticks_before_archive": 0,
            "weight_cap": 1.05,
            "weight_cap_by_persona": {"founding_node": 1.2},
        },
        "events": [],
        "hypotheses": [],
    }
    model = SimulationModel(config=config, out_dir=tmp_path / "cap_persona_override")
    model.run()
    assert model.nodes["n1"].authority_weight == pytest.approx(1.2)


def test_persona_weight_cap_falls_back_to_global_when_missing(tmp_path):
    """Global weight_cap should apply when persona is absent from cap map."""
    config = {
        "experiment": {
            "id": "test_weight_cap_by_persona_fallback",
            "seed": 1,
            "ticks": 30,
            "record_interval": 1000,
        },
        "nodes": [
            {
                "id": "n1",
                "persona": "founding_node",
                "confidence_threshold": 0.0,
                "reversibility_tolerance": 1.0,
            }
        ],
        "claims": [
            {
                "id": "c1",
                "initial_state": "unknown",
                "ground_truth": True,
                "difficulty": 0.5,
                "ambiguity": 0.5,
            }
        ],
        "network": {"topology": "complete"},
        "primitives": {
            "boundary": True,
            "lineage": {"enabled": True, "retention_probability": 1.0},
            "authority": True,
            "mediation": {"enabled": True, "mode": "structured"},
            "confidence": {"enabled": True, "threshold_mean": 0.0, "threshold_variance": 0.0},
            "reversibility": False,
            "observation": False,
        },
        "trust_network": {"dynamic": False, "update_rule": None, "initial_weights": "uniform"},
        "dynamics": {
            "revisability_rate": 0.0,
            "min_ticks_before_archive": 0,
            "weight_cap": 1.1,
            "weight_cap_by_persona": {"peripheral_node": 1.8},
        },
        "events": [],
        "hypotheses": [],
    }
    model = SimulationModel(config=config, out_dir=tmp_path / "cap_persona_fallback")
    model.run()
    assert model.nodes["n1"].authority_weight == pytest.approx(1.1)
