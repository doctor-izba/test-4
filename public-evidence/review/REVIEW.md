# Independent evidence review (cycle 1, PARTIAL — not an acceptance)

Reviewer-owned artifacts only. Nothing in another worker's directory was modified.
This file is deliberately marked partial: every item below states exactly what the
reviewer executed or read, and what is still unverified.

## 0. Evidence actually inspected by the reviewer so far

| Path | What it is | How inspected |
|---|---|---|
| `review/rerun/unit-tests.log` | prior review rerun of `simulation/test_simulation.py` | read: 9 tests, `OK` |
| `review/rerun/results/metrics.json` | prior review rerun metrics, 4 cases | read: numbers quoted below |
| `review/rerun/simulate-stdout.json` | same metrics, stdout copy | read: identical case values |
| `simulation/handoff.md` | simulation worker handoff | read |
| `research/handoff.md` | research worker handoff | read |
| `simulation/README.md` | declared surrogate scope | read |

**Provenance caveat (unresolved, finding R4):** the rerun CSVs/metrics were produced
by an earlier review pass whose command line I have not yet reproduced. Until the
reviewer reruns `simulate.py` from the current `simulation/` source and hashes the
input source, `rerun/results/*` is *not* established to correspond to the current
controller. Treat its numbers as "reported", not yet "independently reproduced".

## 1. Numbers read directly from `review/rerun/results/metrics.json`

Declared scope string in that file:
`"Supplementary surrogate only. Assignment explicitly requires MATLAB and CoppeliaSim."`

| case | state | collision | min clearance (m) | final clearance (m) | est. goal pos err (m) | est. goal hdg err (deg) | odom err |
|---|---|---|---|---|---|---|---|
| goal | hold | false | n/a | n/a | 0.039889 | 2.7055 | [0,0,0] |
| approach | hold | false | 0.201811 | 0.201811 | n/a | n/a | [0,0,0] |
| corner_slow (0.08 m/s) | hold | false | 0.191673 | 0.430596 | n/a | n/a | [0,0,0] |
| corner_fast (0.14 m/s) | hold | false | 0.191673 | 0.429669 | n/a | n/a | [0,0,0] |

Corner straight-section statistics as reported:

| case | mean abs clearance err (m) | max abs clearance err (m) | 1st-section progress (m) | 2nd-wall parallel progress (m) |
|---|---|---|---|---|
| corner_slow | 0.079247 | **0.384663** | 2.1200 | 1.17940 |
| corner_fast | 0.080339 | **0.383663** | 2.1210 | 1.17963 |

## 2. Prioritized findings (each is a concrete action, not a style note)

### R1 (HIGH, metric integrity) — max straight-section clearance error is ~0.385 m while the mean is ~0.079 m
A 4.8x mean/max ratio in both speeds suggests the "straight section" segmentation
window still contains the initial convergence transient (or the first samples where
the wall was not yet acquired), not a steady-state tracking excursion. If so, the
reported max is *technically* from data inside the declared window but is not a
meaningful wall-following error, and the segmentation rule is not yet the explicit
rule the brief requires ("exclude the corner with an explicit segmentation rule").
Conversely, if the 0.385 m excursion is inside the genuinely straight, wall-visible
portion, then tracking is much worse than the mean suggests and the report must say so.
**Action:** read `simulation/simulate.py` segmentation code, recompute the metric
independently from `review/rerun/results/corner_*.csv`, and record which hypothesis
holds. Do not accept the metric until this is resolved.

### R2 (HIGH, scope/claim integrity) — odometry error is identically `[0,0,0]` in all four cases
`final_estimated_pose == final_actual_pose` exactly in every case. This is expected
when slip is zero and encoders are ideal, but it means the surrogate provides **zero
evidence** about odometry behaviour under wheel slip, encoder quantization, or sensor
latency. It must be labelled as a tautology of the ideal model, never as an odometry
accuracy result. The README does say this; the metrics/report must repeat it and a
slip/quantization case must exist in the rerun set before any robustness claim.
**Action:** require at least one perturbation run (slip>0 and/or encoder quantization)
in `review/rerun`; verify odometry error becomes nonzero while control uses encoders only.

### R3 (MEDIUM, Test 3 tracking) — corner min clearance 0.1917 m against a declared 0.30 m follow target
No sampled contact, which is the hard safety requirement, but the controller is
~0.11 m inside its own declared follow distance at the corner and ends ~0.43 m from
the second wall. Test 3 does not itself mandate 0.30 m, but the report must not
describe this as accurate wall following. Also verify how the swept turning footprint
is measured (dense substeps vs sampled poses) — the README admits there is no general
swept collision detector between samples.

### R4 (MEDIUM, provenance) — rerun must be tied to current source
Need `sha256sum simulation/simulate.py simulation/test_simulation.py` recorded next to
a fresh rerun, plus the exact command. Otherwise a controller edit invalidates every
number above without any visible change in this review.

### R5 (MEDIUM, test strength) — 9/9 unit tests pass, but mutation coverage is asserted, not reviewed
`review/rerun/unit-tests.log` shows 9 tests OK (CCW transform, intersection/containment,
no-detection, wheel-limit ratio, front gate, midpoint odometry, swept-circle refusal,
frozen-timer mutant, wrap endpoint mutant). I have not yet verified that the mutation
tests exercise the *real* policy functions rather than reimplementations, nor that
"front protection applied last" is checked in **every** state.

### R6 (pending, Lean) — no independent Lean check yet
`lean/build.log`, `lean/axioms.log`, `lean/Verification-NOTES.md` exist. I have not yet
(a) independently rebuilt from read-only `lean/` with output under `review/`,
(b) confirmed no `sorry`/`admit`/custom axioms, (c) confirmed the wrap theorem states
`[-pi, pi)` and not just some interval, (d) confirmed theorems are not assumptions of
the conclusion. `review/lean-check/` from a prior pass exists; contents not yet audited.

## 3. What is still untested / missing (blocks a final verdict)

- Fresh rerun from current source with input hashes (R4).
- Independent CSV metric recomputation, incl. contiguous 1 s zero-command hold (R1/R2).
- Wrapped heading error at the `-pi`/`+pi` endpoints from actual traces.
- Footprint CCW rotation at heading 90 deg with a non-square footprint (test exists; not independently re-derived here).
- Segment-distance crossing/containment (test exists; not independently re-derived here).
- Joined-corner wall geometry: no gap between the two walls (brief lists a 0.2075 m gap defect).
- Collision checking covers body **and both wheels**, at dense substeps.
- Sensor-threshold derivation for Test 2 from offsets/directions/footprint.
- No-detection != distance zero in the *controller* (not only the ray helper).
- Lean scope vs float controller gap; executable discrete reference vs runtime vectors.
- MATLAB/CoppeliaSim: **absent by construction**; supplemental cloud surrogate cannot satisfy the mandatory platform deliverable.

## 4. Verdict

**NOT ACCEPTED / NOT REJECTED — review incomplete.** Current evidence supports:
surrogate runs complete with zero sampled contact and a pass of the literal Test 1
numeric thresholds *in the ideal model only*; 9/9 unit tests pass. It does not yet
support any claim about odometry robustness, wall-following accuracy, real sensor
latency, or the mandatory MATLAB/CoppeliaSim submission.
