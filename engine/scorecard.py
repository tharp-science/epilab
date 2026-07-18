from __future__ import annotations
import json
import math
import re
from pathlib import Path
from collections import defaultdict, Counter


# ---------------------------------------------------------------------------
# Hypothesis verdict engine
# ---------------------------------------------------------------------------

_EXPR_RE = re.compile(r'^(>=|<=|>|<)\s*([0-9]*\.?[0-9]+)$')


def _evaluate_hypothesis(h: dict, metrics: dict) -> str:
    """
    Score a single hypothesis against computed metrics.

    Supported predicted_direction values
    -------------------------------------
    increasing     metric_end > metric_start  (uses {metric}_start key in metrics;
                   falls back to h["threshold"] if no start is tracked)
    decreasing     metric_end < metric_start  (same fallback)
    flat           |metric_end - metric_start| <= tolerance  (default tol 0.1;
                   falls back to h["min_value"] as a lower-bound check when no
                   start is tracked)
    low            metric_end < cutoff  (default 0.4; override with h["threshold"])
    high           metric_end > cutoff  (default 0.4; override with h["threshold"])
    > x            metric_end > x   (x parsed from the direction string)
    >= x           metric_end >= x
    < x            metric_end < x
    <= x           metric_end <= x
    anything else  "untestable"  (e.g. cross-experiment: lower_than_exp_001)

    Returns one of: "supported" | "falsified" | "untested" | "untestable"
    """
    metric_name = h["metric"]
    metric_val = metrics.get(metric_name)
    if metric_val is None:
        return "untested"

    direction = h.get("predicted_direction", "").strip()
    explicit_threshold = h.get("threshold")          # optional numeric override
    metric_start = metrics.get(f"{metric_name}_start")  # tracked start, if any

    # --- Expression-style directions: "> 0.4", ">= 0.8", "< 0.3", "<= 0.5" ---
    m = _EXPR_RE.match(direction)
    if m:
        op, val = m.group(1), float(m.group(2))
        if op == ">":  return "supported" if metric_val > val  else "falsified"
        if op == ">=": return "supported" if metric_val >= val else "falsified"
        if op == "<":  return "supported" if metric_val < val  else "falsified"
        if op == "<=": return "supported" if metric_val <= val else "falsified"

    # --- Directional ---
    if direction == "increasing":
        if metric_start is not None:
            return "supported" if metric_val > metric_start else "falsified"
        if explicit_threshold is not None:
            return "supported" if metric_val > explicit_threshold else "falsified"
        return "untested"

    if direction == "decreasing":
        if metric_start is not None:
            return "supported" if metric_val < metric_start else "falsified"
        if explicit_threshold is not None:
            return "supported" if metric_val < explicit_threshold else "falsified"
        return "untested"

    # --- Flat (stable): within tolerance of start, or above min_value if no start ---
    if direction == "flat":
        tolerance = h.get("tolerance", 0.1)
        if metric_start is not None:
            return "supported" if abs(metric_val - metric_start) <= tolerance else "falsified"
        min_val = h.get("min_value")
        if min_val is not None:
            return "supported" if metric_val >= min_val else "falsified"
        return "untested"  # no reference point — cannot evaluate

    # --- Named threshold bands ---
    if direction == "low":
        cutoff = explicit_threshold if explicit_threshold is not None else 0.4
        return "supported" if metric_val < cutoff else "falsified"

    if direction == "high":
        cutoff = explicit_threshold if explicit_threshold is not None else 0.4
        return "supported" if metric_val > cutoff else "falsified"

    # --- Cross-experiment or unrecognised directions ---
    return "untestable"


def _effective_claims(config: dict) -> list[dict]:
    """Return flat claim list from either ``claims`` or ``claim_groups``."""
    if "claims" in config:
        return config["claims"]
    result: list[dict] = []
    for group in config.get("claim_groups", []):
        count = group["count"]
        prefix = group["id_prefix"]
        width = len(str(count))
        base = {k: v for k, v in group.items() if k not in ("count", "id_prefix")}
        for i in range(1, count + 1):
            cfg = dict(base)
            cfg["id"] = f"{prefix}{str(i).zfill(width)}"
            result.append(cfg)
    return result


def compute_gini(values: list[float]) -> float:
    """Compute Gini coefficient for a list of non-negative values."""
    if not values or sum(values) == 0:
        return 0.0
    n = len(values)
    values = sorted(values)
    total = sum(values)
    # Standard formula: G = (2 * sum((i+1) * x_i)) / (n * sum(x_i)) - (n+1)/n
    weighted_sum = sum((i + 1) * v for i, v in enumerate(values))
    return (2.0 * weighted_sum) / (n * total) - (n + 1) / n


def _top_owner(counts: Counter[str]) -> tuple[str | None, int]:
    """Return deterministic top owner from a counter (tie-break by node id)."""
    if not counts:
        return None, 0
    node_id, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return node_id, count


def _total_variation_distance(left: Counter[str], right: Counter[str]) -> float | None:
    """Return TVD between two ownership distributions (0=identical, 1=disjoint)."""
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total == 0 or right_total == 0:
        return None
    universe = set(left.keys()) | set(right.keys())
    return 0.5 * sum(
        abs(left.get(node_id, 0) / left_total - right.get(node_id, 0) / right_total)
        for node_id in universe
    )


def compute_scorecard(event_log_path: Path, config: dict) -> dict:
    """Read event log and compute output metrics."""
    events = []
    if event_log_path.exists():
        with open(event_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    # Build time-series of authority weights from snapshots
    authority_snapshots: list[dict[str, float]] = []
    claim_states_over_time: dict[str, list[tuple[int, str]]] = defaultdict(list)
    state_transitions: list[dict] = []       # all transitions (governance + cycling)
    governance_transitions: list[dict] = []  # agent-sourced transitions only
    cycling_events: list[dict] = []          # __dynamics__ transitions only (B4)
    reversions: list[dict] = []              # governance-sourced reversions only (B4)
    operationalised_ticks: dict[str, int] = {}  # claim_id -> tick when operationalised

    for event in events:
        etype = event.get("event_type")
        if etype == "system_snapshot":
            authority_snapshots.append(event.get("authority_weights", {}))
            tick = event.get("tick", 0)
            for cid, state in event.get("claims", {}).items():
                claim_states_over_time[cid].append((tick, state))
        elif etype == "state_transition":
            state_transitions.append(event)
            is_dynamics = event.get("node_id") == "__dynamics__"
            if is_dynamics:
                cycling_events.append(event)
            else:
                governance_transitions.append(event)
            if event.get("to_state") == "operationalised":
                operationalised_ticks[event["claim_id"]] = event["tick"]
            to_s = event.get("to_state", "")
            from_s = event.get("from_state", "")
            # B4 fix: only count governance-sourced transitions as reversions.
            # __dynamics__ cycling events are a mechanical heartbeat, not contested semantics.
            if (not is_dynamics
                    and to_s in ("revisable", "contested")
                    and from_s in ("operationalised", "revisable")):
                reversions.append(event)

    # Channel ownership breakdown (governance transitions only).
    # Forward channel: all governance transitions except reversion edges.
    # Reversion channel: operationalised->revisable and revisable->contested.
    analysis_cfg = config.get("analysis", {})
    capture_share_threshold = float(analysis_cfg.get("channel_capture_share_threshold", 0.8))
    early_horizon_tick = int(analysis_cfg.get("channel_early_horizon_tick", min(500, config["experiment"]["ticks"])))

    reversion_pairs = {("operationalised", "revisable"), ("revisable", "contested")}
    forward_owner_counts: Counter[str] = Counter()
    reversion_owner_counts: Counter[str] = Counter()
    forward_owner_counts_early: Counter[str] = Counter()
    reversion_owner_counts_early: Counter[str] = Counter()

    forward_total = 0
    reversion_total = 0
    forward_top1_node = None
    reversion_top1_node = None
    forward_top1_count = 0
    reversion_top1_count = 0
    forward_capture_tick = None
    reversion_capture_tick = None

    for event in governance_transitions:
        node_id = event.get("node_id")
        tick = int(event.get("tick", 0))
        from_s = event.get("from_state", "")
        to_s = event.get("to_state", "")
        if not node_id:
            continue

        is_reversion = (from_s, to_s) in reversion_pairs
        if is_reversion:
            reversion_owner_counts[node_id] += 1
            reversion_total += 1
            c = reversion_owner_counts[node_id]
            if c > reversion_top1_count or (c == reversion_top1_count and (reversion_top1_node is None or node_id < reversion_top1_node)):
                reversion_top1_node = node_id
                reversion_top1_count = c
            if reversion_capture_tick is None and reversion_total > 0 and (reversion_top1_count / reversion_total) >= capture_share_threshold:
                reversion_capture_tick = tick
            if tick <= early_horizon_tick:
                reversion_owner_counts_early[node_id] += 1
        else:
            forward_owner_counts[node_id] += 1
            forward_total += 1
            c = forward_owner_counts[node_id]
            if c > forward_top1_count or (c == forward_top1_count and (forward_top1_node is None or node_id < forward_top1_node)):
                forward_top1_node = node_id
                forward_top1_count = c
            if forward_capture_tick is None and forward_total > 0 and (forward_top1_count / forward_total) >= capture_share_threshold:
                forward_capture_tick = tick
            if tick <= early_horizon_tick:
                forward_owner_counts_early[node_id] += 1

    forward_top1_share = (forward_top1_count / forward_total) if forward_total > 0 else None
    reversion_top1_share = (reversion_top1_count / reversion_total) if reversion_total > 0 else None

    if forward_top1_node is None or reversion_top1_node is None:
        channel_top1_owner_overlap = None
    else:
        channel_top1_owner_overlap = 1.0 if forward_top1_node == reversion_top1_node else 0.0

    forward_top1_node_early, _ = _top_owner(forward_owner_counts_early)
    reversion_top1_node_early, _ = _top_owner(reversion_owner_counts_early)
    if forward_top1_node_early is None or reversion_top1_node_early is None:
        channel_top1_owner_overlap_early = None
    else:
        channel_top1_owner_overlap_early = 1.0 if forward_top1_node_early == reversion_top1_node_early else 0.0

    # Channel specialization metric: ownership distribution divergence across channels.
    channel_specialization_tvd = _total_variation_distance(forward_owner_counts, reversion_owner_counts)

    # 1. authority_concentration_gini at end
    if authority_snapshots:
        last_weights = authority_snapshots[-1]
        gini_end = compute_gini(list(last_weights.values()))
        gini_start = compute_gini(list(authority_snapshots[0].values())) if authority_snapshots else 0.0
    else:
        gini_end = 0.0
        gini_start = 0.0

    # 2. epistemic_accuracy
    total_claims = _effective_claims(config)
    ground_truth_map = {c["id"]: c.get("ground_truth") for c in total_claims}
    operationalised_claims = set(operationalised_ticks.keys())
    correct = sum(1 for cid in operationalised_claims if ground_truth_map.get(cid) is True)
    total_op = len(operationalised_claims)
    epistemic_accuracy = correct / total_op if total_op > 0 else 0.0

    # 3. epistemic_stability_index
    # claims_operationalised_for_>N_ticks_without_reversion / total_claims
    # B5: reverted_claims uses governance reversions only (cycling events excluded via B4 fix).
    total_ticks = config["experiment"]["ticks"]
    dynamics_cfg = config.get("dynamics", {})
    window_fraction = dynamics_cfg.get("stability_window_fraction", None)
    N_ticks = int(total_ticks * window_fraction) if window_fraction is not None else 50
    # B5: check co-design constraint — stability window must be shorter than cycling period.
    revisability_rate = dynamics_cfg.get("revisability_rate", 0.0)
    b5_constraint_violated = (
        revisability_rate > 0.0 and N_ticks >= (1.0 / revisability_rate)
    )
    reverted_claims = {r["claim_id"] for r in reversions}
    stable_claims = sum(
        1 for cid, tick_op in operationalised_ticks.items()
        if cid not in reverted_claims and (total_ticks - tick_op) >= N_ticks
    )
    n_claims = len(total_claims)
    epistemic_stability_index = stable_claims / n_claims if n_claims > 0 else 0.0

    # 4. contested_claim_resolution_rate
    # Use governance_transitions only — cycling events are not claim resolutions.
    contested_to_resolved = sum(
        1 for e in governance_transitions
        if e.get("from_state") == "contested"
    )
    contested_claim_resolution_rate = contested_to_resolved / total_ticks if total_ticks > 0 else 0.0

    # 5. interpretive_drift_rate (B4 fix)
    # Numerator:   governance reversions only (not __dynamics__ cycling).
    # Denominator: governance transitions only (cycling events are not agent decisions).
    total_transitions = len(state_transitions)       # all events, for total count
    total_reversions = len(reversions)               # governance reversions only
    total_cycling_events = len(cycling_events)       # __dynamics__ heartbeat events
    n_gov_transitions = len(governance_transitions)
    interpretive_drift_rate = total_reversions / n_gov_transitions if n_gov_transitions > 0 else 0.0

    # B3: absorbing-state artefact check.
    # If total transitions <= total_claims × 10, the system completed fewer than
    # one full claim cycle on average — ESI, drift rate, and accuracy are unreliable.
    b3_absorbing_state_artefact = (total_transitions <= n_claims * 10) if n_claims > 0 else False

    metrics = {
        "authority_concentration_gini": gini_end,
        "authority_concentration_gini_start": gini_start,
        "epistemic_accuracy": epistemic_accuracy,
        "epistemic_stability_index": epistemic_stability_index,
        # B5: flag if stability window >= cycling period — ESI reading is structurally suppressed
        "esi_b5_constraint_violated": b5_constraint_violated,
        # B3: flag if system absorbed before completing enough cycles for reliable metrics
        "b3_absorbing_state_artefact": b3_absorbing_state_artefact,
        "contested_claim_resolution_rate": contested_claim_resolution_rate,
        "interpretive_drift_rate": interpretive_drift_rate,
        "total_state_transitions": total_transitions,
        "total_reversions": total_reversions,
        "forward_channel_transitions": forward_total,
        "reversion_channel_transitions": reversion_total,
        "channel_top1_owner_overlap": channel_top1_owner_overlap,
        "channel_top1_owner_overlap_early": channel_top1_owner_overlap_early,
        "channel_specialization_tvd": channel_specialization_tvd,
        "forward_channel_top1_share": forward_top1_share,
        "reversion_channel_top1_share": reversion_top1_share,
        "forward_capture_tick_top1_ge_threshold": forward_capture_tick,
        "reversion_capture_tick_top1_ge_threshold": reversion_capture_tick,
        "channel_capture_share_threshold": capture_share_threshold,
        "channel_early_horizon_tick": early_horizon_tick,
        # B4: cycling events counted separately, not merged into reversions
        "cycling_events_count": total_cycling_events,
        "claims_operationalised": total_op,
        "total_claims": n_claims,
    }

    # Evaluate hypotheses
    hypothesis_results = []
    for h in config.get("hypotheses", []):
        result = _evaluate_hypothesis(h, metrics)
        hypothesis_results.append({
            "id": h["id"],
            "description": h.get("description", ""),
            "metric": h["metric"],
            "predicted_direction": h.get("predicted_direction", ""),
            "observed_value": metrics.get(h["metric"]),
            "result": result,
        })

    return {
        "experiment_id": config["experiment"]["id"],
        "seed": config["experiment"]["seed"],
        "ticks": config["experiment"]["ticks"],
        "metrics": metrics,
        "hypotheses": hypothesis_results,
    }
