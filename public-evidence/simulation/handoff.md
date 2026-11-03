# Simulation handoff — cycle 1 (continuing restored run)

Status: **working**, canonical v1 results restored and re-verified; v2 controller repair
in progress. This file is the live handoff for the next cycle.

## Files owned / current state

- `simulate.py` — v1 ideal 2-D surrogate (still the executed `results/` source).
  Baseline copy saved as `baseline_frozen/simulate_v1.py`; CSV/SVG/metrics of the
  frozen v1 run are in `baseline_frozen/` and `baseline-cloud/`.
- `test_simulation.py` — 9 stdlib unittest cases, all pass (re-ran this cycle).
- `reference_checks.m` — Octave/MATLAB parity checks; **executed this cycle with
  Octave 8.4.0**: `Octave/MATLAB algebra and endpoint checks passed.`
- `cloud_results.md` — partial; v2 numbers not yet written.
- `ALTERNATIVES.md` / `README.md` — free-tool and scope notes.
- No independent review file exists yet; this cycle must produce reviewable v2
  artifacts.

## Verified baseline problem (must not be papered over)

v1 corner runs end at 0.4306 m (0.08 m/s) and 0.4297 m (0.14 m/s) body clearance
against 0.30 m desired. Root causes identified from source: (a) wall law
`omega = 1.8*(mean-.30) - 2.5*heading` has a non-zero equilibrium
`e = (2.5/1.8)*heading`; (b) turn starts at front range 0.65 m, ~0.39 m too early,
so the second-wall section is spent converging. v1 traces are retained.

## This cycle's plan (ordered)

1. v2 wall estimator: two left ray hits -> wall line in robot frame; perpendicular
   center distance, wall angle, rotated footprint/wheel support, estimated footprint
   clearance. Law `omega = k_e*clearance_error + k_delta*wall_angle` (no steady-state
   offset), same gains at both speeds.
2. Geometry-derived turn trigger `front <= desired + wheel_outer - half_length`
   (=0.273 m with declared numbers) and swept-circle guard; log exact swept turning
   clearance from dense substeps.
3. Explicit `follow`/`avoid`/`reacquire`/`corner_turn`/`hold`/`sensor_failure`/
   `unsafe_turn_stop` machine with hysteresis and bounded lost-wall timeout; final
   front guard zeros v **and** omega in every state.
4. Dense sub-sample collision check over body **and both wheel rectangles**; no
   hardcoded contact.
5. Metrics: est-vs-GT and actual-vs-goal separately, segmented straight-wall error
   excluding corner by explicit rule, state transitions, hold verification.
6. Dependency-boundary test: replay logged odom/ranges through a fresh policy and
   reproduce commands; mutate all GT columns and show commands unchanged.
7. Supplemental perturbation cases: side dropout short/long, front dropout,
   slip+encoder quantization, biased-side turn refusal.
8. PNG plots via matplotlib, v2 results dir, update `cloud_results.md`, README and
   this handoff. Preserve all failed/supplemental runs.

## Exact commands used

```bash
cd simulation
python3 -m unittest discover -s . -p 'test_simulation.py' -v
octave --no-gui --quiet --eval "run('reference_checks.m')"
python3 simulate.py --output results_v2
```

## Known boundary

Surrogate only. No MATLAB/CoppeliaSim scene, no contact dynamics, no calibrated
Pioneer dimensions, no claim that this satisfies the mandated local track.
