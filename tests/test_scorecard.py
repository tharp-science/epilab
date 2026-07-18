"""
Verdict engine unit tests — synthetic scorecard inputs with known expected verdicts.
All four comparison types are covered:
  - point equality / named bands  (low, high)
  - directional                   (increasing, decreasing)
  - minimum threshold             (> x, >= x)
  - range / stable                (flat, <= x)
  - cross-experiment / unknown    (untestable)
  - missing data                  (untested)
"""
import pytest
from engine.scorecard import _evaluate_hypothesis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hyp(direction, metric="score", **kwargs):
    h = {"id": "H_test", "metric": metric, "predicted_direction": direction}
    h.update(kwargs)
    return h


def metrics(**kwargs):
    return dict(kwargs)


# ---------------------------------------------------------------------------
# increasing / decreasing — uses {metric}_start when present
# ---------------------------------------------------------------------------

def test_increasing_supported_when_end_exceeds_start():
    assert _evaluate_hypothesis(
        hyp("increasing", metric="authority_concentration_gini"),
        metrics(authority_concentration_gini=0.3, authority_concentration_gini_start=0.1),
    ) == "supported"


def test_increasing_falsified_when_end_below_start():
    assert _evaluate_hypothesis(
        hyp("increasing", metric="authority_concentration_gini"),
        metrics(authority_concentration_gini=0.05, authority_concentration_gini_start=0.1),
    ) == "falsified"


def test_increasing_no_start_uses_explicit_threshold():
    assert _evaluate_hypothesis(
        hyp("increasing", metric="score", threshold=0.5),
        metrics(score=0.6),
    ) == "supported"


def test_increasing_no_start_no_threshold_is_untested():
    assert _evaluate_hypothesis(
        hyp("increasing", metric="score"),
        metrics(score=0.9),
    ) == "untested"


def test_decreasing_supported_when_end_below_start():
    assert _evaluate_hypothesis(
        hyp("decreasing", metric="score"),
        metrics(score=0.2, score_start=0.8),
    ) == "supported"


def test_decreasing_falsified_when_end_exceeds_start():
    assert _evaluate_hypothesis(
        hyp("decreasing", metric="score"),
        metrics(score=0.9, score_start=0.5),
    ) == "falsified"


# ---------------------------------------------------------------------------
# flat — uses {metric}_start with tolerance, or min_value fallback
# ---------------------------------------------------------------------------

def test_flat_supported_within_tolerance():
    assert _evaluate_hypothesis(
        hyp("flat", metric="score"),
        metrics(score=0.55, score_start=0.5),
    ) == "supported"


def test_flat_falsified_outside_tolerance():
    assert _evaluate_hypothesis(
        hyp("flat", metric="score"),
        metrics(score=0.95, score_start=0.5),
    ) == "falsified"


def test_flat_custom_tolerance():
    assert _evaluate_hypothesis(
        hyp("flat", metric="score", tolerance=0.3),
        metrics(score=0.75, score_start=0.5),
    ) == "supported"


def test_flat_no_start_uses_min_value():
    # ESI-style: no start tracked, but hypothesis provides min_value
    assert _evaluate_hypothesis(
        hyp("flat", metric="epistemic_stability_index", min_value=0.8),
        metrics(epistemic_stability_index=1.0),
    ) == "supported"


def test_flat_no_start_min_value_falsified():
    assert _evaluate_hypothesis(
        hyp("flat", metric="epistemic_stability_index", min_value=0.8),
        metrics(epistemic_stability_index=0.5),
    ) == "falsified"


def test_flat_no_start_no_min_value_is_untested():
    # Regression: ESI 1.0 was incorrectly marked "falsified" against gini_start 0.057
    assert _evaluate_hypothesis(
        hyp("flat", metric="epistemic_stability_index"),
        metrics(
            epistemic_stability_index=1.0,
            authority_concentration_gini=0.175,
            authority_concentration_gini_start=0.057,
        ),
    ) == "untested"


# ---------------------------------------------------------------------------
# low / high — named threshold bands with optional override
# ---------------------------------------------------------------------------

def test_low_supported_below_default_threshold():
    assert _evaluate_hypothesis(
        hyp("low", metric="epistemic_stability_index"),
        metrics(epistemic_stability_index=0.2),
    ) == "supported"


def test_low_falsified_above_default_threshold():
    assert _evaluate_hypothesis(
        hyp("low", metric="epistemic_stability_index"),
        metrics(epistemic_stability_index=0.9),
    ) == "falsified"


def test_low_explicit_threshold():
    assert _evaluate_hypothesis(
        hyp("low", metric="score", threshold=0.7),
        metrics(score=0.65),
    ) == "supported"


def test_high_supported_above_default_threshold():
    assert _evaluate_hypothesis(
        hyp("high", metric="epistemic_stability_index"),
        metrics(epistemic_stability_index=0.9),
    ) == "supported"


def test_high_falsified_below_default_threshold():
    assert _evaluate_hypothesis(
        hyp("high", metric="epistemic_stability_index"),
        metrics(epistemic_stability_index=0.1),
    ) == "falsified"


def test_high_explicit_threshold():
    assert _evaluate_hypothesis(
        hyp("high", metric="score", threshold=0.6),
        metrics(score=0.8),
    ) == "supported"


# ---------------------------------------------------------------------------
# Expression-style thresholds: > x, >= x, < x, <= x
# ---------------------------------------------------------------------------

def test_expr_gt_supported():
    assert _evaluate_hypothesis(hyp("> 0.4", metric="score"), metrics(score=0.5)) == "supported"


def test_expr_gt_falsified():
    assert _evaluate_hypothesis(hyp("> 0.4", metric="score"), metrics(score=0.4)) == "falsified"


def test_expr_gte_supported_at_boundary():
    assert _evaluate_hypothesis(hyp(">= 0.8", metric="score"), metrics(score=0.8)) == "supported"


def test_expr_gte_falsified_below():
    assert _evaluate_hypothesis(hyp(">= 0.8", metric="score"), metrics(score=0.79)) == "falsified"


def test_expr_lt_supported():
    assert _evaluate_hypothesis(hyp("< 0.3", metric="score"), metrics(score=0.2)) == "supported"


def test_expr_lt_falsified():
    assert _evaluate_hypothesis(hyp("< 0.3", metric="score"), metrics(score=0.3)) == "falsified"


def test_expr_lte_supported_at_boundary():
    assert _evaluate_hypothesis(hyp("<= 0.5", metric="score"), metrics(score=0.5)) == "supported"


def test_expr_lte_falsified_above():
    assert _evaluate_hypothesis(hyp("<= 0.5", metric="score"), metrics(score=0.51)) == "falsified"


# ---------------------------------------------------------------------------
# Regression: exp_001c specific failures that prompted this fix
# ---------------------------------------------------------------------------

def test_regression_exp001c_h2_gini_should_be_falsified():
    """
    H2: Gini should continue to increase beyond 0.226.
    Observed: 0.175 (< start of 0.057? No — 0.175 > 0.057 so 'increasing' gives 'supported').
    The real issue: hypothesis predicts > 0.4 but current direction is just 'increasing'.
    Test that 'increasing' correctly uses metric_start (not gini_start) and returns
    'falsified' when end < start of the same metric.
    """
    # Simulating a case where metric_start for a non-gini metric is available
    # and end < start → falsified
    assert _evaluate_hypothesis(
        hyp("increasing", metric="custom_metric"),
        metrics(custom_metric=0.175, custom_metric_start=0.226),
    ) == "falsified"


def test_regression_exp001c_h3_esi_flat_no_start_is_untested_not_falsified():
    """
    H3: ESI should remain flat (≥ 0.8). ESI = 1.0.
    Old bug: compared ESI against authority_concentration_gini_start (0.057),
    so abs(1.0 - 0.057) = 0.943 ≥ 0.1 → wrongly "falsified".
    Fixed: with no {epistemic_stability_index}_start and no min_value → "untested".
    """
    result = _evaluate_hypothesis(
        hyp("flat", metric="epistemic_stability_index"),
        metrics(
            epistemic_stability_index=1.0,
            authority_concentration_gini=0.175,
            authority_concentration_gini_start=0.057,
        ),
    )
    assert result == "untested", f"Expected 'untested', got '{result}'"


# ---------------------------------------------------------------------------
# Cross-experiment and missing data
# ---------------------------------------------------------------------------

def test_cross_experiment_direction_is_untestable():
    assert _evaluate_hypothesis(
        hyp("lower_than_exp_001", metric="score"),
        metrics(score=0.5),
    ) == "untestable"


def test_higher_than_cross_experiment_is_untestable():
    assert _evaluate_hypothesis(
        hyp("higher_than_exp_001", metric="score"),
        metrics(score=0.9),
    ) == "untestable"


def test_missing_metric_is_untested():
    assert _evaluate_hypothesis(
        hyp("increasing", metric="nonexistent"),
        metrics(score=0.5),
    ) == "untested"


def test_unknown_direction_is_untestable():
    assert _evaluate_hypothesis(
        hyp("sideways", metric="score"),
        metrics(score=0.5),
    ) == "untestable"
