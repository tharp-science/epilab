# epilab

An agent-based simulation laboratory for stress-testing epistemic governance.

## At a glance

This repository asks a falsifiable question: do six governance primitives —
boundary, lineage, authority, mediation, confidence and reversibility —
actually produce the structural effects predicted for them in multi-actor
knowledge systems, or does order emerge (or fail) without them?

Observation is implemented as an optional module and treated as a candidate
seventh primitive, off by default. With it disabled, nodes have perfect
visibility of the shared state. Every experiment config in `configs/` disables
it, so the published results study the six primitives with observation held
ideal. The [specification](simulation-spec.md) describes the proposed test of
whether observation is an independent primitive or a performance parameter.

It tests failure emergence, not success. The central question for every
experiment is: under what conditions do systems break, and do the primitives
change when and how they break?

The laboratory is built on [Mesa](https://mesa.readthedocs.io/), with
experiments defined entirely as YAML configs. Nodes with distinct authority
profiles propose state transitions for a shared set of claims; primitive
modules gate which transitions succeed; every event is logged; and a
scorecard adjudicates each experiment's pre-registered hypotheses against the
event log. All variation between runs is expressed as config differences,
never code differences.

## How an experiment works

Claims move through a fixed epistemic state machine:

```text
unknown → hypothesised → contested → provisionally_accepted → operationalised
operationalised → revisable → contested        (revision loop)
operationalised → archived
```

No skip transitions are permitted. Each simulation tick runs a fixed
ten-step sequence — observe, propose, boundary-filter, weight, mediate,
threshold, resolve, record lineage, update trust, log — with node activation
order randomised per tick so scheduling artefacts cannot masquerade as
structural effects. Runs are seed-deterministic and fully replayable.

Every config declares its hypotheses up front, with a target metric and a
predicted direction:

```yaml
hypotheses:
  - id: H1
    description: "Without primitives, system produces chaos (low stability)"
    metric: epistemic_stability_index
    predicted_direction: low
```

The scorecard computes verdicts against the event log, and the pair
(config, scorecard) is the unit of evidence. Predictions are not
assumptions: where the observed failure mode differs from the predicted one,
the discrepancy is the finding.

## The experiment battery

The canonical set is ordered by dependency — run Exp-000 first:

| Experiment | Question |
| --- | --- |
| Exp-000 | Null governance baseline — do primitives create order, or does it emerge anyway? |
| Exp-001 | Authority gravity — does influence concentrate without redistribution mechanisms? |
| Exp-002 | Lineage necessity — what happens to stability as transition records decay? |
| Exp-003 | Inner sanctum dynamics — do founding nodes compound into a closed core? |
| Exp-004 | Premature binary collapse — does attention pressure force early resolution? |
| Exp-005 | Observation degradation — how much perception error can governance absorb? |
| Exp-006 | Mediation mode comparison — structured mediation vs. majority vote vs. none |
| Exp-007 | Primitive scaling — do the effects hold as node and claim counts grow? |

The `configs/` directory holds 45 configs: the canonical battery plus
gradient sweeps and grid variants that probe thresholds rather than binary
necessity. Several configs carry fault annotations in their headers (e.g.
which metrics are invalid for that design and why) — these are part of the
record, not noise.

Metrics include authority concentration (Gini), epistemic accuracy against
ground truth, a stability index, false-consensus rate, mediation load,
reversion cascade depth, and post-shock recovery time. The scorecard also
self-flags known measurement artefacts rather than reporting silently.

## Scope and claims

Version 1 assumes a shared semantic substrate: every node interprets state
labels identically and claim identities are stable. This deliberately removes
one of the hardest real-world failure modes — semantic drift — from the test
surface.

Results therefore support at most: *the primitives produce predicted
structural effects under shared semantics.* They do not support: *the
primitives are sufficient for real organisational governance.* That second
claim would require an interpretive-variance layer per node and a claim
deformation mechanism, which is v2 territory.

The full specification — config schema, tick semantics, metric formulae,
canonical experiment definitions, and sweep methodology — is in
[simulation-spec.md](simulation-spec.md). The spec references companion
research notes that live outside this repository; the laboratory itself
stands alone as code plus configs.

Findings from this laboratory are reported in the companion preprint,
[*Governing Epistemic Systems: Primitive Interaction and the Structural
Dynamics of Distributed
Authority*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6417898)
(Bohle, 2026, SSRN working paper).

## Quick start

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run the null baseline into a local data directory
EGLAB_RAW_ROOT=./data python run.py configs/exp_000.yaml

# run the test suite
python -m pytest
```

A run writes three artefacts: an append-only event log
(`<exp>_event_log.jsonl`), periodic state snapshots, and a scorecard
(`<exp>_scorecard.json`) with hypothesis verdicts, plus an exact snapshot of
the config that produced it. Multi-seed runs use `--seed` to override the
config seed.

Verification for the current snapshot:

```sh
python -m pytest
# 67 passed
```

## Batch mode

`watcher.py` polls an `inbox/` directory, validates any YAML config dropped
into it, runs the experiment, and archives results to the raw data store —
useful for queueing sweeps from other tools or agents.

Data locations are controlled by environment variables: `EGLAB_RAW_ROOT`
(default `/srv/eglab/data`), with `EGLAB_RUNS_DIR` and
`EGLAB_CONFIG_SNAPSHOTS_DIR` for finer control.

## Repository layout

- `engine/` — simulation model, agents, claim state machine, events, trust
  network, scorecard, and one module per primitive under
  `engine/primitives/`.
- `configs/` — the experiment battery: canonical set, gradient sweeps, grid
  variants.
- `tests/` — unit, integration, and scorecard tests.
- `tools/` — config generators and analysis helpers.
- `simulation-spec.md` — the full specification.

## Citation

If you use this laboratory in your own work, please cite the preprint:

> Bohle, Sebastian (2026). *Governing Epistemic Systems: Primitive
> Interaction and the Structural Dynamics of Distributed Authority.* SSRN
> working paper.
> https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6417898

Machine-readable citation metadata is in [CITATION.cff](CITATION.cff);
GitHub's "Cite this repository" button exports APA and BibTeX from it.

## Licence

This repository is licensed under the [MIT License](LICENSE). The companion
preprint is published on SSRN under its own terms.

## Related work

[context-mediation-layer](https://github.com/tharp-science/context-mediation-layer)
is the operational counterpart: where epilab tests governance primitives in
simulation, the Context Mediation Layer implements a governed record surface
for live human-AI coordination.
