# Engineering contract

Produce the strongest defensible differential-drive robotics solution that can be
supported by evidence. Work, run tools and write actual files; do not return only a plan.
No fabricated experiments, citations, compiler success, API usage or submission claims.

## Continuing the previous interrupted run

Prior work stopped because the coordinator imposed 40 model turns, not because the
budget was spent. Source, CSVs, proof logs and partial review files have been restored.
Inspect existing files and continue; do not repeat a long orientation pass. Research
notes and the authored report were missing at interruption. Produce original usable
files incrementally now: the researcher must save real notes after a few sources;
the writer must draft report.md early and revise it against later evidence. Never
spend an entire slice only reading/listing files or rerunning the same baseline.
Every slice must improve an artifact or record a concrete unresolved defect with
evidence. Write/update your owned handoff.md each slice. A slice yield is not failure.

Use the full available job window for meaningful research, controller improvements,
proof/runtime correspondence, robustness experiments, independent checks and report
revision. The coordinator repeats repair cycles; there is no global 40-turn ceiling.
Do not invent extra tasks or idle to inflate runtime. If canonical MATLAB/Coppelia
experiments require the local workstation, clearly record that boundary and improve
the cloud-verifiable work instead of repeatedly rediscovering the same limitation.

## Model and mandatory local assignment conditions

Pioneer robot, axle midpoint reference. SI units. Heading CCW from world +x.
Document measured wheel radius r, separation b, footprint, joint signs, wheel limits.
Inverse kinematics wl=(v-b*w/2)/r, wr=(v+b*w/2)/r. Uniform wheel scaling preserves
the requested v:w relation. Measured encoder increments feed midpoint odometry.
Do not use commanded rates as a substitute for measured odometry in the real adapter.
Only encoders, sensor readings and simulation time can influence control or state.
Ground-truth pose is solely evaluation/logging; do not correct odometry with it.

Test 1: q0=(0,0,0), goal=(0.8,0.5,0); estimated position error<=0.05m,
abs wrapped heading error<=5deg; zero commands and continuous 1s tolerance hold.
Record actual final error separately. Wrap interval is [-pi,pi).

Test 2: perpendicular wide wall; initial footprint clearance about1.5m; desired
final body-to-wall clearance0.20m; slow, stop, no contact, zero-command 1s hold.
Derive sensor range thresholds using sensor offsets/directions and footprint.
No detection must not be mistaken for distance zero. Evaluation uses shortest
footprint-to-wall distance, not range or axle-to-wall distance.

Test 3: two joined perpendicular inside-corner walls; follow same side around
corner; at least1m on both straight sections. Explicit follow/avoid/reacquire/stop
states, hysteresis, bounded lost-wall behavior. Front protection applied last must
override all side-wall steering and forward motion. Check swept turning footprint.
End via measured-wheel odometry condition. Compare two speeds with identical
geometry, initial pose, gains and thresholds. Preserve failed runs.

Record time, encoder motion, estimated/true pose, sensor ranges/detection flags,
wheel commands, state and collisions. For all tests final odometry error=estimate-GT,
heading wrapped. Goal actual error=GT-goal. Straight wall-following mean/max absolute
clearance errors exclude the corner with an explicit segmentation rule.

## Known previous implementation defects to reject

- Row-vector footprint rotation had wrong sign. Test heading90deg non-square shape.
- Segment distance ignored crossings/containment. Overlap must be distance zero.
- Side steering overwrote front protection in some states. Apply a final guard.
- Lost-wall timer reset but never advanced; reacquisition lacked bounded stop.
- Intended corner walls had a0.2075m gap. Verify joined geometry.
- Root robot object alone did not establish collision checking of all body/wheels.
- Dummy initial clearance0 corrupted minimum statistics.
- Lean variables shadowed wl/wr functions; division proof invalid; atan2 API absent.
- Old video captured an empty stopped scene; actual frames must show the experiment.

## Meaningful Lean obligations

Compile modular definitions/proofs. Protect(v,w,d) prevents positive forward v when
d<=brake in every behavior state. Uniform limiter bounds both wheel rates and
preserves zero and scaling relation. Lost-wall timer advances/resets and bounded
fallback stops. Correct CCW/inverse geometry; odometry heading identity; [-pi,pi)
wrap convention; contiguous zero-command success hold. Conditional physical safety
requires explicit sensor latency/deceleration/footprint assumptions, not hidden axioms.
No sorry/admit/custom axioms, no theorem that just assumes the desired conclusion.
Standard logical axioms propext, Classical.choice, Quot.sound must be reported.
Connect an executable discrete Lean reference to runtime boundary vectors if feasible.
A differential test is not a proof of MATLAB floating-point refinement.

## Actual deliverables

Research: lawful downloaded sources plus original cited notes and source-decision-test map.
Lean: source, actual build result, theorem/axiom transcript, scope and missing obligations.
Simulation: executable surrogate, CSVs, metrics, meaningful boundary/mutation tests.
Review: independent defects, accepted/failed/untested requirement table.
Report: full original write-up, derivations, design decisions, plots, state machine,
dimensioned layout, results and limitations, reproduction instructions and defense guide.
Every numerical result must come from an actual run. Keep canonical/local Coppelia
evidence separate from surrogate outputs. Never claim the free model satisfies the
specified MATLAB/CoppeliaSim submission requirement.
