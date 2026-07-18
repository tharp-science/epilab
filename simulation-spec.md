# Simulation Specification

*Experimental framework for computational testing of the systems thinking vault*

---

## Purpose

This document specifies an agent-based simulation framework for testing the vault's theoretical claims. The framework has three design requirements:

1. **Reproducibility** — experiment parameters are fully serialised and replayable under changed conditions
2. **Swappability** — system components (authority types, primitive modules, network topologies, persona bundles) can be enabled, disabled, or replaced without code changes
3. **Auditability** — results are recorded as structured event logs that constitute falsification evidence, not just observational summaries

The simulation tests *failure emergence*, not success. The central question for every experiment is: under what conditions do systems break, and do the primitives change when and how they break?

---

## v1 Scope Limitation — Shared Semantic Substrate

This framework assumes a common ontology across all nodes: every node interprets state labels (Contested, Operationalised, etc.) identically, reads primitive modules as objective infrastructure, and understands claim identities to be stable over time.

This is a deliberate simplification. It is not a neutral assumption — it removes one of the hardest real-world failure modes from the test surface. In actual organisations, actors regularly disagree about what a claim even is, whether something constitutes a decision or a hypothesis, and what "authority" means in a given context. Semantic drift of this kind happens upstream of mediation, before the governance primitives engage.

**What v1 therefore tests:** Given shared semantics, do the primitives generate the predicted structural effects — authority gravity, lineage necessity, inner sanctum dynamics, mediation irreducibility?

**What v1 cannot test:** Whether the primitives are sufficient under contested semantics — when actors disagree on claim identity, state-label meaning, or what counts as a valid authority invocation. That is a v2 question, requiring an interpretive schema variance layer per node (heterogeneous `operationalised_threshold`, `authority_preference`, `ambiguity_tolerance`) and a claim deformation mechanism.

**Overclaiming risk:** Results from this battery support "the primitives produce predicted structural effects under shared semantics." They do not support "the primitives are sufficient for real organisational governance." The second claim requires v2.

This limitation is noted in `unresolved-tensions.md`.

---

## Architecture Overview

```
experiment.yaml
     │
     ├── node registry (personas)
     ├── claim space
     ├── network topology
     ├── primitive module set (enabled / disabled / weakened)
     ├── trust network config
     ├── shock event schedule
     └── run parameters (ticks, seed)
          │
          ▼
    simulation engine
          │
          ├── event_log.jsonl        ← append-only, one event per tick-action
          ├── state_snapshots.jsonl  ← full system state at configurable intervals
          └── scorecard.json         ← hypothesis verdicts against event log
```

The simulation engine reads the config, instantiates agents, runs the tick loop, and writes output. It never modifies the config. All variation between runs is expressed as config differences, not code differences.

---

## Tick Execution Order

Because primitives interact, evaluation order within a tick produces materially different outcomes. The engine implements a fixed ten-step sequence per tick:

```
1. Observe       — Nodes read current claim states (observation module applies accuracy filter here)
2. Propose       — Each node proposes candidate state transitions for claims it can see
3. Boundary      — Boundary module filters which proposals reach which claims
4. Weight        — Authority weight applied to surviving proposals
5. Mediate       — Mediation invoked for claims in contested state
6. Threshold     — Confidence thresholds evaluated against weighted proposals
7. Resolve       — Transitions accepted or blocked; claim states updated
8. Record        — Lineage entry written for each accepted transition
9. Trust update  — Trust network updated based on transition outcomes
10. Log          — All events written to event log; snapshot written if at record_interval
```

Primitive modules govern whether proposed transitions succeed. They do not govern whether proposals exist. Any node can propose a transition for any claim it can observe; the primitives determine what happens to that proposal.

**Node activation order within each step** is randomised per tick (shuffled at step 1). This prevents scheduling artefacts from masquerading as structural effects. The seed governs the shuffle sequence, so activation order is deterministic across replays but not fixed across ticks.

---

## Claim State Machine

Allowed transitions between epistemic states. The engine rejects any proposed transition not on this graph before primitive evaluation begins.

```
unknown ──────────────→ hypothesised
hypothesised ─────────→ contested
contested ────────────→ provisionally_accepted
provisionally_accepted → operationalised
operationalised ──────→ revisable
revisable ────────────→ contested
operationalised ──────→ archived
```

No skip transitions (e.g. `unknown → operationalised`) are permitted. This ensures all experiments operate on a consistent epistemic model matching the seven-state sequence in `epistemic-transition-hypothesis.md`.

---

## Experiment Config Schema

Every experiment is a single YAML file. Required fields are marked `[R]`.

```yaml
experiment:
  id: [R]         # unique identifier, used as output directory name
  seed: [R]       # integer, for deterministic RNG replay
  description:    # human-readable statement of what is being tested
  ticks: [R]      # number of simulation steps
  record_interval: 10   # how often to write a full state snapshot

nodes:            # [R] list of node definitions
  - id: [R]
    persona:      # named persona bundle (see Component Registry)
    # or inline parameter override:
    authority_types: []         # subset of [signal, temporal, control, perceptual] — categorical, determines which transitions this node can influence
    authority_weight: 1.0       # numeric influence magnitude during transition evaluation; Gini metrics calculated over this value
    confidence_threshold: 0.0   # 0.0–1.0; minimum confidence to accept a state transition
    reversibility_tolerance: 0.0 # 0.0–1.0; willingness to revert a transition
    temporal_position: 0.0      # 0.0–1.0; starting value only — compounds if lineage enabled
    compounding_rate: 0.0       # rate at which temporal position grows per tick

claims:           # [R] list of propositions the system manages collectively
  - id: [R]
    initial_state: [R]  # one of: unknown | hypothesised | contested | provisionally_accepted | operationalised | archived | revisable
    ground_truth:       # true | false | null; enables accuracy tracking if set
    domain:             # optional tag for domain-scoped analysis
    difficulty: 0.5     # 0.0–1.0; scales confidence required for transition
    ambiguity: 0.5      # 0.0–1.0; scales observation error probability and mediation load

network:
  topology: [R]   # small_world | scale_free | ring | complete | random | custom
  # topology-specific params:
  k: 4            # (small_world) mean degree
  p: 0.1          # (small_world) rewiring probability
  m: 2            # (scale_free) edges per new node
  custom_edges:   # list of [source, target] pairs for custom topology

primitives:
  # Each primitive can be: true (full strength) | false (null/disabled) | parameterised
  boundary: true
  lineage:
    enabled: true
    retention_probability: 1.0  # 0.0–1.0; probability that any given transition is recorded
  authority: true
  mediation:
    enabled: true
    mode: structured        # structured | majority_vote | none
  confidence:
    enabled: true
    threshold_mean: 0.5     # mean confidence threshold across nodes
    threshold_variance: 0.0 # variance; set > 0 for heterogeneous populations
  reversibility: true
  observation:
    enabled: false          # candidate seventh primitive; off by default
    accuracy_mean: 1.0      # mean perceptual accuracy across nodes (1.0 = perfect)
    accuracy_variance: 0.0  # variance; set > 0 to degrade observation quality

trust_network:
  dynamic: false            # if true, trust weights update through interaction
  update_rule: null         # successful_transition | null
  initial_weights: uniform  # uniform | random | hierarchy

events:           # scheduled shocks injected at specified ticks
  - tick: 150
    type: authority_removal   # see Event Types below
    target_node: founding_node
  - tick: 200
    type: attention_shock
    contested_claim_burst: 8  # inject N new contested claims simultaneously
  # other event types: network_fragmentation | claim_burst | node_arrival | node_departure

hypotheses:       # what this experiment is testing; used to generate scorecard
  - id: H1
    description: "Authority gravity emerges without explicit accumulation rule"
    metric: "authority_concentration_gini"
    predicted_direction: increasing
    window: [0, 500]
```

---

## Component Registry

Components are named bundles referenced by the config. New components are added to the registry without touching the engine.

### Persona Bundles

| Name | Authority Types | Confidence Threshold | Reversibility Tolerance | Temporal Position (start) | Compounding Rate |
|---|---|---|---|---|---|
| `founding_node` | all four | 0.25 | 0.15 | 0.90 | 0.02 |
| `peripheral_node` | signal only | 0.70 | 0.65 | 0.10 | 0.00 |
| `mediating_node` | control only | 0.50 | 0.50 | 0.40 | 0.00 |
| `skeptical_peer` | signal, perceptual | 0.80 | 0.70 | 0.30 | 0.00 |
| `fast_mover` | signal, temporal | 0.20 | 0.10 | 0.50 | 0.05 |
| `latecomer` | signal only | 0.55 | 0.45 | 0.05 | 0.00 |

*Note on authority: `authority_types` (categorical) and `authority_weight` (numeric) are distinct parameters. Authority type determines which transitions a node is eligible to influence — a node with only `signal` authority cannot invoke `control` authority during mediation. Authority weight determines how much influence the node exerts when it does participate. All distribution metrics (Gini coefficient, concentration indices) are calculated over `authority_weight`, not over the count or breadth of authority types.*

*Note: `temporal_position` in the persona is a starting value only. If the `lineage` primitive is enabled and `compounding_rate > 0`, temporal position evolves from this starting point through the mechanism — it is not fixed. This distinction matters: Exp-003 tests whether temporal advantage compounds from unequal starts; a future experiment variant could test whether it emerges from equal starts through differential early activity.*

### Network Topologies

| Name | Description | When to Use |
|---|---|---|
| `small_world` | Watts-Strogatz; clustered with short paths | Most organisational simulations |
| `scale_free` | Barabási-Albert; power-law degree distribution | Hub-dominant systems |
| `ring` | Each node connected to k neighbours only | Sequential handoff systems |
| `complete` | Every node connected to every other | Small committees, consensus bodies |
| `random` | Erdős-Rényi | Baseline / null model |

### Primitive Modules

Each primitive is implemented as a swappable module with a defined interface:

| Primitive | Function in engine | Null replacement behaviour |
|---|---|---|
| `boundary` | Governs which nodes can influence which claims | All nodes influence all claims |
| `lineage` | Records transition history; enables challenge-by-origin | No history recorded; no origin challenges |
| `authority` | Weights influence by authority type match | All influence weighted equally |
| `mediation` | Requires a mediating node for contested transitions | Contested transitions resolve directly (or by majority vote depending on `mode`) |
| `confidence` | Applies threshold before accepting transitions | All proposed transitions accepted |
| `reversibility` | Enables state retreat; tracks reversion cost | No reversion; transitions are permanent |
| `observation` | Models perceptual accuracy; nodes may misread current state | All nodes have perfect state visibility |

### Claim Difficulty × Ambiguity — Domain Reference

| Domain type | Difficulty | Ambiguity | Expected behaviour |
|---|---|---|---|
| Physics / hard science | High | Low | Slow convergence to accurate consensus |
| Geopolitics | Medium | Very high | High mediation load; frequent observation errors |
| Internal org policy | Low | High | Fast transitions; high authority misattribution risk |
| Legal interpretation | High | High | Mediation-dependent; strong lineage reliance |

---

## Event Log Format

Every state-changing action produces one JSONL event. The log is append-only. Fields:

```json
{
  "tick": 45,
  "event_type": "state_transition",
  "node_id": "founding_node",
  "claim_id": "claim_001",
  "from_state": "contested",
  "to_state": "provisionally_accepted",
  "authority_invoked": "signal",
  "confidence_score": 0.74,
  "claim_difficulty": 0.6,
  "claim_ambiguity": 0.3,
  "influencing_nodes": ["node_003", "node_007"],
  "mediated_by": null,
  "lineage_challenge": false,
  "trust_weights_at_tick": {"node_003": 0.71, "node_007": 0.44},
  "primitive_modules_active": {
    "boundary": true,
    "lineage": {"enabled": true, "retention_probability": 0.8},
    "authority": true,
    "mediation": {"enabled": true, "mode": "structured"},
    "confidence": {"enabled": true, "threshold_mean": 0.5},
    "reversibility": true,
    "observation": false
  }
}
```

Full event type inventory:

| `event_type` | When emitted |
|---|---|
| `state_transition` | A claim changes epistemic state |
| `transition_blocked` | A proposed transition fails (confidence below threshold, boundary violation, mediation absent) |
| `lineage_challenge` | A node contests a transition by citing origin state |
| `authority_accumulation` | A node gains authority weight through successful transitions |
| `trust_update` | Dynamic trust matrix updated after a successful/failed transition |
| `reversion` | A claim retreats to an earlier state |
| `observation_error` | A node misreads a claim's current state (observation module only) |
| `false_consensus` | A claim reaches `operationalised` based on observation errors (ground_truth = false) |
| `shock_injected` | A scheduled shock event fires |
| `authority_removed` | A node's authority type(s) revoked mid-simulation |
| `network_fragmented` | An edge between nodes is severed |
| `system_snapshot` | Full state dump at record_interval |

---

## Output Metrics

### Per-run scalar metrics

| Metric | Formula | Measures |
|---|---|---|
| `authority_concentration_gini` | Gini coefficient of authority-weight distribution across nodes | Whether authority gravity is occurring |
| `epistemic_accuracy` | `correct_operationalised / total_operationalised` (requires ground_truth) | Whether the system reaches true conclusions |
| `epistemic_stability_index` | `claims_operationalised_for_>N_ticks_without_reversion / total_claims` | Whether the system can sustain knowledge, not just produce it |
| `contested_claim_resolution_rate` | Contested → resolved transitions per tick | Speed and decisiveness of the system |
| `false_consensus_rate` | `false_consensus_events / total_operationalised` | Epistemic hygiene |
| `mediation_load` | Average number of contested claims awaiting mediation per tick | Bottleneck risk |
| `reversion_cascade_depth` | Mean number of downstream state changes triggered by each reversion | Exit cost asymmetry indicator |
| `observation_error_rate` | `observation_error_events / total_state_read_attempts` (observation module only) | Perception reliability |
| `interpretive_drift_rate` | `state_reversions / total_state_transitions` (where a reversion is any transition to a less resolved state) | Internal epistemic instability independent of ground truth — measures contradiction frequency, not accuracy |
| `post_shock_recovery_ticks` | Ticks until epistemic_stability_index returns to pre-shock baseline | System resilience |

### Topology × Primitive Interaction Matrix

*Expected dominant failure mode by topology when key primitives are stressed:*

| Topology | Primitive stressed | Predicted dominant failure |
|---|---|---|
| `scale_free` | authority | Authority gravity — hubs accumulate disproportionately |
| `ring` | confidence | Slow epistemic convergence — transitions stall at ring edges |
| `complete` | mediation | Mediation overload — every contested claim requires full-group process |
| `random` | lineage | Unstable lineage — no stable reference chains form |
| `small_world` | observation | Cluster-local false consensus spreading before correction |

*These are predictions, not assumptions. If the observed failure mode differs, the discrepancy is the finding.*

---

## Canonical Experiment Set

Experiments are ordered by dependency: run Exp-000 first. If the null baseline produces unexpected order, all downstream experiments require reinterpretation.

---

### Exp-000 — Null Governance Baseline

**Question:** Do the primitives actually create order, or does order emerge anyway?

**Config highlights:**
```yaml
primitives:
  boundary: false
  lineage: false
  authority: false
  mediation: false
  confidence: false
  reversibility: false
  observation: false
```
- 7 nodes (mixed personas), 10 claims, small-world topology, 500 ticks

**Predicted behaviour:**
- Extremely fast operationalisation (no confidence gates, no mediation requirement)
- Very low `epistemic_accuracy` (claims resolve quickly but incorrectly)
- Gini coefficient near 0 (no mechanism to accumulate authority)
- `epistemic_stability_index` near 0 (high reversion rate once conflicts surface with no resolution mechanism)
- No stable consensus — system oscillates

**Why this matters:** Without this baseline, you cannot distinguish "the primitives improve the system" from "the system would have organised itself anyway." If order emerges in Exp-000, the primitives are optimisations, not prerequisites. If chaos persists in Exp-000 and order emerges in Exp-001, the primitives are constitutive.

**Falsification condition:** Exp-000 produces `epistemic_stability_index > 0.4`. This would indicate that self-organisation is sufficient for epistemic stability and the entire governance framework requires re-examination.

---

### Exp-001 — Authority Gravity Emergence

**Question:** Does authority gravity emerge endogenously from the primitive interactions, without any explicit accumulation rule in the engine?

**Config highlights:**
- 1 founding node, 4 peripheral nodes, 2 mediating nodes
- Small-world topology, k=4, p=0.1
- All primitives enabled
- 500 ticks, seed=42

**Hypothesis:** The founding node's authority weight share increases monotonically. By tick 500, Gini coefficient > 0.5 from a starting value near 0.14 (uniform).

**Falsification condition:** Gini coefficient remains flat or decreases. This indicates authority gravity is not structural — it requires an explicit accumulation rule and should be reclassified from emergent mechanism to stipulated rule.

---

### Exp-002 — Lineage Necessity (Gradient)

**Question:** Is there a phase transition in epistemic stability as lineage retention degrades?

**Config highlights:**
- Run five variants, identical except `lineage.retention_probability`: 1.0, 0.8, 0.6, 0.4, 0.2
- All other parameters identical to Exp-001

**Hypothesis:**
```
retention > 0.7  →  stable consensus (epistemic_stability_index > 0.6)
retention < 0.5  →  epistemic churn   (epistemic_stability_index < 0.3)
```
A sharp transition between these regions would constitute a theoretical claim: that lineage integrity has a threshold below which the system cannot sustain knowledge regardless of other primitive strength.

**Falsification condition:** `epistemic_stability_index` decreases linearly and continuously with `retention_probability` — no phase transition detected. This would indicate Lineage has no threshold behaviour and is a smooth performance parameter, not a structural prerequisite.

---

### Exp-003 — Inner Sanctum Dynamics

**Question:** Does temporal position compound into exit-cost asymmetry as predicted?

**Config highlights:**
- 2 founding nodes (temporal_position: 0.90, compounding_rate: 0.05)
- 6 latecomer nodes added at tick 100 (temporal_position: 0.05, compounding_rate: 0.00)
- All primitives enabled
- Measure `reversion_cascade_depth` for founding-node claims vs. latecomer claims at ticks 200, 300, 400

**Hypothesis:** By tick 400, average reversion cascade depth for founding-node claims is > 3× that of latecomer claims. Exit cost asymmetry grows, not shrinks, over time.

**Falsification condition:** Cascade depth ratios are equivalent across node types at all measurement points. This would indicate temporal position does not compound into structural exit asymmetry and the inner sanctum mechanism needs revision.

---

### Exp-004 — Premature Binary Collapse Under Attention Pressure

**Question:** Does confidence threshold degradation under attention pressure produce premature collapse?

**Config highlights:**
- 20 claims, 8 nodes, ring topology
- At tick 100: `attention_shock` event injects 12 new contested claims (from baseline of 3)
- Confidence threshold decays linearly with contested claim backlog (decay function as explicit config parameter, not hardcoded)
- Measure: reversion rate in ticks 100–200 vs. baseline ticks 0–100

**Hypothesis:** Post-shock reversion rate is significantly higher than baseline. The faster transitions induced by confidence decay produce more subsequent reversions — the system resolves problems it hasn't actually solved.

**Falsification condition:** Post-shock reversion rate is not significantly elevated. This would indicate premature binary collapse requires a different causal mechanism than confidence threshold decay.

---

### Exp-005 — Observation Degradation

**Question:** Does perceptual accuracy degrade systems faster than structural primitive weakening? Is Observation a meta-primitive?

**Config highlights:**
- Run six variants with `observation.accuracy_mean` at: 1.0, 0.9, 0.8, 0.7, 0.6, 0.5
- All structural primitives at full strength
- Track: `false_consensus_rate`, `authority_misattribution_rate`, `cascade_failure_count`

**Hypothesis:** Observation degradation produces system failure faster than equivalent degradation of any structural primitive. Predicted sequence of emergence as accuracy falls:
1. First: `observation_error` events — local misreadings that self-correct
2. Then: `false_consensus` events — operationalised claims based on shared misreading
3. Then: cascade failures — reversions triggered by belated accurate observations hitting operationalised states built on false consensus

**Predicted degradation ordering across primitives** (steepest failure curve first):

```
Observation > Lineage > Authority > Confidence
```

Rationale: all primitives operate on perceived system state. If observation is unreliable, all downstream mechanisms operate on incorrect inputs. Lineage ranks second because loss of history prevents the system from challenging false operationalisations. Authority ranks third; confidence is most degradation-tolerant because the other primitives partially compensate for weak thresholds.

This ordering is itself a falsifiable claim. If the actual ordering differs, it reranks which primitives are structurally prior.

**Why this supports the Observation primitive:** If the degradation curve is steeper for Observation than for equivalently weakened Lineage or Authority, it provides direct evidence that observation is structurally prior — the other primitives cannot function correctly if the inputs they operate on are systematically wrong.

**Falsification condition:** Observation degradation curve is equivalent to or flatter than Lineage or Authority degradation curves. This would indicate Observation is a performance parameter of the other primitives, not an independent one.

---

### Exp-006 — Mediation Mode Comparison (A/B/C)

**Question:** Does mediation mode qualitatively change failure type — not just failure rate?

**Config highlights:**
Three runs, identical except `mediation.mode`:
- Run A: `structured` (full mediation primitive)
- Run B: `none` (mediation disabled; contested transitions blocked)
- Run C: `majority_vote` (mediation replaced with simple majority)

**Predictions:**

| Run | Predicted outcome |
|---|---|
| A (structured) | Stable consensus; slow but high `epistemic_accuracy` |
| B (none) | Authority collapse — contested claims stall indefinitely; high-authority nodes break deadlock by unilateral transition |
| C (majority_vote) | Premature consensus — contested claims resolve quickly but with lower `epistemic_accuracy`; `false_consensus_rate` elevated |

**What makes this a strong test:** The hypothesis is not just that A outperforms B and C. It's that B and C fail in qualitatively different ways — B through gridlock and authority capture, C through epistemic corruption. If both produce the same failure mode, the structured mediation primitive is doing less distinct work than claimed.

**Falsification condition:** Run B and Run C produce indistinguishable failure distributions. This would indicate that the presence or absence of mediation matters, but the type of mediation does not — weakening the claim that the specific structured mediation mechanism is irreducible.

---

### Exp-007 — Primitive Scaling

**Question:** Do the primitives scale linearly, or do they collapse at scale?

**Config highlights:**
Three runs with identical topology proportions and persona distributions:
- Scale-S: 10 nodes, 15 claims
- Scale-M: 100 nodes, 150 claims
- Scale-L: 1000 nodes, 1500 claims

**Metrics tracked:** `authority_concentration_gini`, `mediation_load`, `contested_claim_resolution_rate`, `epistemic_stability_index`

**Predicted patterns:**
- `authority_concentration_gini`: increases with scale (authority gravity amplifies in larger networks)
- `mediation_load`: may grow superlinearly — a theoretical ceiling exists above which the structured mediation primitive cannot function without bottleneck
- `contested_claim_resolution_rate`: decreases with scale if mediation is the bottleneck
- `epistemic_stability_index`: non-monotonic — may improve at medium scale (more nodes provide more validation signal) before degrading at large scale (coordination costs dominate)

**Why this is a theoretical claim, not just an engineering one:** If primitives that work at Scale-S fail at Scale-L, the framework is not scale-independent. This matters for the substrate hypotheses in `substrate-hypotheses.md` — a federated architecture may be necessary precisely because the primitives have scaling limits.

**Falsification condition:** All metrics scale linearly (no superlinear growth, no threshold collapse). This would indicate the primitives are scale-invariant and the federation design requirement is an optimisation, not a structural necessity.

---

## Gradient Sweep Methodology

Binary on/off experiments answer necessity questions. Gradient sweeps answer threshold questions. The two complement each other.

For any primitive parameter that accepts a continuous value, a gradient sweep protocol is:

1. Hold all other parameters constant at Exp-001 baseline values
2. Sweep the target parameter across its full range in 10 equal steps
3. Run each step at 5 different seeds (for variance estimation)
4. Plot `epistemic_stability_index` against the parameter value
5. Identify the slope profile: linear (smooth performance parameter), sigmoidal (phase transition), or step (binary threshold)

The slope profile is itself a theoretical claim. A sigmoidal curve with a steep transition zone means the system has a critical threshold — a design implication for how carefully that parameter must be managed in real systems.

---

## Relation to Vault

| Simulation output | Vault document updated |
|---|---|
| Exp-000 scorecard | `primitives.md` — note added on constitutive vs. optimisation status |
| Exp-001 scorecard | `primitive-falsification.md` — Authority necessity table |
| Exp-002 scorecard | `primitive-falsification.md` — Lineage necessity table; `mechanisms.md` — phase transition note if detected |
| Exp-003 scorecard | `mechanisms.md` — Inner sanctum mechanism; `compounding.md` |
| Exp-004 scorecard | `failure-modes.md` — Premature binary collapse entry |
| Exp-005 scorecard | `primitives.md` — Observation primitive status; `epistemic-transition-hypothesis.md` — falsification evidence |
| Exp-006 scorecard | `mechanisms.md` — Confirmation invariant; `primitive-falsification.md` — Mediation necessity |
| Exp-007 scorecard | `substrate-hypotheses.md` — scaling evidence for/against federation requirement |
| Any `failure_modes_observed_not_predicted` | `unresolved-tensions.md` — new entry flagged as simulation-sourced |
| Any unexpected emergent mechanism | `mechanisms.md` — candidate new mechanism, flagged as simulation-sourced |

Simulation evidence does not overwrite theoretical claims. It adds an `evidence` field to each relevant entry, preserving the theoretical argument alongside the empirical result. Discrepancy flags between theoretical predictions and simulation observations are the highest-value output — they mark where the framework needs revision.

---

## Implementation Notes

**Recommended tooling:** Mesa (Python agent-based modelling framework). The config schema above maps directly to Mesa's `Model` and `Agent` classes. The event log maps to Mesa's `DataCollector` with a custom JSONL writer.

**Minimum viable prototype:** Exp-000 and Exp-001 only, 7 nodes, 10 claims, 200 ticks. Estimated ~350 lines of Python. Exp-000 and Exp-001 together constitute the first falsification pair — they test whether the primitives are constitutive (if Exp-000 is chaotic) and whether authority gravity is emergent (if Exp-001 shows Gini growth). Both passing means the engine is sound enough to proceed, not that the engine is fundamentally validated. Confidence in the engine accumulates across experiments; it is not established by the first two alone. All other experiments require only config file changes from that base.

**Seeding:** Python's `random.seed()` and `numpy.random.seed()` called at engine init from the config seed value. Ensures full determinism across runs on the same platform.

**Config versioning:** Experiment config files should be committed to version control alongside their output scorecards. The pair (config, scorecard) is the unit of evidence.

**Shock events:** Scheduled shocks are injected by the engine at the specified tick. The engine does not predict or smooth the shock — it fires instantaneously. This is intentional: governance resilience is measured against sudden discontinuities, not gradual drift.

---

*Links: [[primitives]] · [[mechanisms]] · [[primitive-falsification]] · [[epistemic-transition-hypothesis]] · [[failure-modes]] · [[unresolved-tensions]] · [[substrate-hypotheses]] · [[compounding]]*
