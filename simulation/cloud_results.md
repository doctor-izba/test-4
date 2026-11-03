# Free-run surrogate results (Python/Octave) — working report

Status: **partial, revision in progress**. Every number below was produced by the
commands shown on this machine. This is an ideal 2-D kinematic surrogate, **not**
MATLAB and **not** CoppeliaSim evidence. The assignment's mandated MATLAB control /
sensing / odometry / logging and CoppeliaSim scenes remain a separate local-track
obligation.

## 1. Baseline failure being repaired (retained, not deleted)

The pre-revision baseline is preserved under `baseline_frozen/` and
`baseline-cloud/`. Its own `results/metrics.json` records:

| case | completed | collision | final body clearance | mean abs straight clearance error | max abs straight clearance error |
|---|---|---|---|---|---|
| goal | true | false | n/a | n/a | n/a |
| approach | true | false | 0.20181 m | n/a | n/a |
| corner_slow (0.08 m/s) | true | false | **0.43060 m** vs target 0.30 m | 0.07925 m | 0.38466 m |
| corner_fast (0.14 m/s) | true | false | **0.42967 m** vs target 0.30 m | 0.08034 m | 0.38366 m |

The `corner_slow` trace transitioned `follow_first -> corner_turn` at t=26.50 s with
`x=2.120 m, y=0.310 m`, `follow_second` at t=29.60 s with `x=2.120, y=0.310,
theta=-1.547 rad`, and `hold` at t=44.70 s with `x=2.3534, y=-0.8694,
theta=-1.4517 rad`. At the stop, `left_front_range=0.442 m` and
`left_back_range=0.480 m` against a 0.30 m range target; the final footprint
clearance was 0.4306 m. The second-wall segment therefore ended while still
converging, and the heading was 7.7 deg off wall-parallel.

Diagnosis recorded for the repair: the old law
`omega = 1.8*(mean_range-0.30) - 2.5*heading` makes the cross-track error settle on
`e = (k_heading/k_dist)*heading`. That is an effective look-ahead of
`2.5/1.8 = 1.39 m`; with `v=0.08 m/s` the approach time constant is about
`1.39/0.08 = 17 s`, longer than the ~15 s spent on the second wall. The baseline is
also sampled-collision-only, ignores outboard wheel geometry, and has no explicit
reacquire state.

## 2. Commands used so far

```bash
cd simulation
python3 -m unittest discover -s . -p 'test_simulation.py' -v
python3 simulate.py --output results
octave --no-gui --quiet --eval "run('reference_checks.m')"
```

Octave 8.4.0 is installed; the executed transcript is recorded in section 5 after
the next run. Baseline Python numbers above are from the restored `results/` and
`baseline_frozen/` artifacts.

## 3. Revision design (to be filled with post-run numbers)

- Wall distance estimated from the two left range hits as a line in the robot frame
  (perpendicular center-to-wall distance, not raw range along a rotated ray).
- Target center distance includes the rotated footprint support
  `0.19*cos(delta) + 0.23*|sin(delta)|`, so the controlled quantity is the true
  footprint clearance.
- Faster cross-track gain with the same gains at both speeds.
- Explicit `avoid`, `reacquire`, `stop` states with differing enter/exit thresholds
  (hysteresis) and a bounded lost-wall timeout.
- Final front guard returns zero forward **and** zero steering when triggered.
- Dense sub-sample (20 per 0.05 s) swept clearance evaluation for body plus wheels,
  reported separately from the sampled control-rate clearance.
- Goal and approach actual-vs-estimated errors reported separately.

## 4. Gaps / limitations (must survive into the final report)

- No contact dynamics; "collision" is a geometric intersection at densely sampled poses.
- No sensor noise/beam volume in the canonical cases; perturbation cases are
  deterministic and supplemental.
- No calibrated Pioneer dimensions; declared values are assumptions.
- Zero odometry error in no-slip canonical runs is a property of the ideal actuator,
  not a calibration result.
- MATLAB/CoppeliaSim scene, video and remote-API evidence are not produced here.
