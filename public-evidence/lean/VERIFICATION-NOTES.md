# Lean verification notes (worker: lean) — cycle 1

Status snapshot written before the fresh build of this cycle. Everything below is
copied from files that exist in `lean/`; nothing is inferred from a source file
alone.

## 1. What is already in the tree

`Assignment4Verification.lean` (528 lines, build target of `lakefile.toml`) contains
definitions and theorems for:

| Obligation (brief) | Declaration(s) |
|---|---|
| inverse kinematics round trip | `vBody_of_wl_wr`, `wBody_of_wl_wr`, `wl_compose`, `wr_compose` |
| uniform scaling / zero | `wl_scale`, `wr_scale`, `curvature_scale`, `limited_zero`, `limited_ratio`, `body_ratio_div` |
| limiter bounds both wheels | `limitDenom_positive`, `limited_wheel_bound`, `limitDenom_inside_bounds`, `vBody_div` |
| final front guard in every state | `protect_front_nonforward`, `every_state_front_nonforward`, `final_guard_overrides_policy`, `final_guard_rejects_positive_policy`, `final_limited_nonforward` |
| [-pi,pi) wrap convention | `wrap_range`, `wrap_abs_le_pi`, `wrap_neg_pi`, `wrap_pi`, `wrap_add`, `wrap_wrap` |
| CCW rotation / rejected row-vector sign | `rot_zero`, `rot_quarter`, `rot_inverse`, `rot_compose`, `rot_preserves_squared_norm`, `row_rotation_wrong_at_ninety`, `nonsquare_corner_rot90` |
| measured-wheel odometry heading | `measuredCenterIncrement`, `measuredHeadingIncrement`, `equal_measured_increments_no_turn`, `opposite_measured_increments_no_translation`, `zero_measured_increments`, `measuredHeadingIncrement_add`, `odomHeading_compose`, `odomHeading_range` |
| lost-wall timer advance/reset + bounded stop | `lostTimer_reset`, `lostTimer_advances`, `lostTimer_nondecreasing`, `lostTimer_reset_then_advance`, `lostTimer_iterate`, `lostTimer_reaches_timeout`, `timeoutStop_stops` |
| zero-command contiguous hold | `holdRun_ge_lastAllTrue`, `holdRun_success_contiguous`, `holdRun_reset`, `holdStep_le`, `zero_command_zero_wheels` |
| sensor absence ≠ zero distance | `frontGate_none`, `frontGate_some_nonforward`, `frontGate_some_forward`, `minReadings_eq_none_iff` |
| braking distance vs threshold | `stopDistance_le_threshold`, `braking_distance_identity` |
| swept turning footprint | `swept_radius_sq`, `corner_within_swept_radius` |

## 2. Evidence currently on disk, and its exact limits

`build.log` and `final-build.log` both end with
`Build completed successfully (1964 jobs).` with warnings only (three unused simp
args, several `tac1 <;> tac2` linter notes, one `ring` -> `ring_nf` info at
line 74). `final-build.log` says `Replayed Assignment4Verification`, i.e. it was a
cache replay, not a fresh elaboration.

`axioms.log` / `final-axioms.log` are the transcript of an axiom audit; they are
the same file (6209 bytes each).

**Known defect in existing evidence:** `local-verification.json` records
`"command": "lake env lean CombinedAudit.lean"` with `"exit_code": 1`. There is no
`CombinedAudit.lean` in this directory, so that JSON is stale output from an
earlier layout and must not be cited as a verification result. It is being
replaced by a fresh `lake build` + `lake env lean AxiomAudit.lean` transcript in
this cycle (`verification.log`, `axioms.log`).

## 3. Honest scope boundary

* These are real-valued mathematical contracts. They say nothing about IEEE-754
  doubles in MATLAB/Python, about sensor latency, about tyre slip, or about
  CoppeliaSim dynamics.
* `protect`/`step` is a command-level property; the physical "no collision"
  claim needs the explicit hypotheses in `stopDistance_le_threshold` (latency,
  deceleration, v ≤ vmax) plus a sensor-coverage assumption. The brief requires
  those assumptions to be explicit, not hidden axioms — they are theorem
  hypotheses here and still have to be tied to measured robot parameters.
* No theorem states that the runtime controller *is* `step`; that link is made
  only by the boundary-vector differential test (see §4).

## 4. Next concrete work in this cycle

1. Fresh `lake build` and `lake env lean AxiomAudit.lean`; save real logs.
2. Add an executable discrete reference checker over `Rat`/`Int` for the front
   gate, timer ticks, and wheel limiter, with `#eval`-generated boundary vectors
   exported to a machine-readable file so the simulation worker can diff against
   its actual Python functions.
3. Fix the stale `local-verification.json` and the linter warnings.
