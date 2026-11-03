# Design decisions and derivations (working draft, cycle 1)

Status: **partial but usable**. Sections 1–8 are written from sources already
downloaded into `research/raw/`. Section 9 (controller comparison), the full
source/decision/test map and the Octave/Webots boundary discussion are being
extended in later cycles. Every citation below was inspected in the saved copy;
page/equation numbers are the printed numbers of the source, not PDF indices.

Project constraint that dominates everything here: the assignment asks for a
**MATLAB + CoppeliaSim** implementation with three saved scenes, a real video and
measured encoders. The cloud work can supply mathematics, a headless surrogate,
Lean contracts and reproducible checks. It **cannot** certify the MATLAB or
CoppeliaSim deliverables. Those remain a local-workstation obligation and are
never described as done in these notes.

## 1. Symbols, frames and units

All quantities SI: metres, seconds, radians. World frame `{s}` has `+x` right,
`+y` up; heading `θ` is CCW from world `+x`, so body axes are
`x̂_b = (cos θ, sin θ)`, `ŷ_b = (−sin θ, cos θ)`.

| symbol | meaning | value used by surrogate |
|---|---|---|
| `r` | driven wheel radius | 0.0975 m (declared, not measured) |
| `b` | wheel separation (track) | 0.381 m (declared, not measured) |
| `L`, `W` | footprint full length, width | 0.46 m, 0.38 m (declared) |
| `a = L/2`, `c = W/2` | footprint half-length, half-width | 0.23 m, 0.19 m |
| `d_f`, `d_lf`, `d_lb` | sensor offsets from axle midpoint | 0.23, 0.16 forward; 0.19 left |
| `v`, `ω` | axle-midpoint forward speed, CCW yaw rate | commanded/estimated |
| `ω_L`, `ω_R` | left/right wheel angular rates | limited to ±6 rad/s |
| `Δθ_L`, `Δθ_R` | **measured** encoder increments | from odometry source |

These dimensions are fixture approximations. They must be replaced by measured
Pioneer values on the local workstation before any physical claim; the report
must label them "declared surrogate parameters", never "measured".

## 2. Differential-drive geometry and inverse kinematics

`Modern Robotics` (Dec 2019 preprint), §13.3.1.2, eq. (13.14), p. 525, with
wheel separation `2d` there (so `b = 2d`), body twist
`V_b = (ω, v_x, v_y)` and `v_y = 0`:

```
q̇ = [φ̇, ẋ, ẏ, θ̇_L, θ̇_R]ᵀ
   = [ −r/(2d)   r/(2d) ]          (row φ̇)
     [  r/2 cosφ  r/2 cosφ ]       (row ẋ)
     [  r/2 sinφ  r/2 sinφ ]       (row ẏ)
     [   1         0       ]       (row θ̇_L)
     [   0         1       ]       (row θ̇_R)   · (u_L, u_R)ᵀ
```

The text immediately below eq. (13.14) states: "A positive angular speed of each
wheel corresponds to forward motion at that wheel." Dropping the wheel-angle rows
gives eq. (13.15), the unicycle form `φ̇ = ω`, `ẋ = v cosφ`, `ẏ = v sinφ`.
§13.4 eq. (13.34), p. 549, gives the same map in twist coordinates:

```
V_b = (ω_bz, v_bx, v_by) = r [ −1/(2d)  1/(2d) ] (Δθ_L, Δθ_R)ᵀ
                              [   1/2     1/2   ]
                              [    0       0    ]
```

With `b = 2d` this is exactly the assignment's convention:

```
v = r (ω_L + ω_R) / 2
ω = r (ω_R − ω_L) / b
ω_L = (v − b ω / 2) / r
ω_R = (v + b ω / 2) / r
```

Design consequences:

* Use `b` (full track) consistently. Mixing `d` and `2d` produces a factor-2 yaw
  error; the Lean file names the parameter `b` and uses `b*ω/2`.
* Positive `ω` is CCW, so the **right** wheel must be faster: `ω_R − ω_L > 0`.
  A common mutant flips this; the surrogate test `test_rotation_direction`
  rotates +90° and checks the footprint transform, not only wheel signs
  (see §11).
* The assignment mandates uniform wheel scaling `s·(ω_L, ω_R)` when the requested
  ratio changes by `s`; the Lean theorems `wl_scale`, `wr_scale`,
  `curvature_scale` cover this. Scaling must be applied to **both** wheels by the
  same factor; per-wheel clipping would change the curvature and is forbidden.
* Real wheel signs on a Pioneer are not assumed from this math. A local
  calibration must record which hardware sign makes positive `ω_L` advance that
  wheel forward, and whether the left encoder counts up for forward motion. The
  real adapter must apply the identified sign, and the report must state it.

## 3. Midpoint encoder odometry

Inputs are **measured** encoder increments, never commanded rates. With
`Δs_L = r Δθ_L`, `Δs_R = r Δθ_R`:

```
Δs = (Δs_L + Δs_R)/2
Δθ = (Δs_R − Δs_L)/b
θ_m = θ_k + Δθ/2                       (midpoint heading)
x_{k+1} = x_k + Δs cos θ_m
y_{k+1} = y_k + Δs sin θ_m
θ_{k+1} = wrap(θ_k + Δθ)
```

Equivalence to `Modern Robotics` §13.4: eq. (13.34) supplies the constant body
twist over the sample, eq. (13.35) integrates it exactly, and eq. (13.36)
transforms the body displacement into `{s}` using the previous heading. For the
diff-drive case `v_by = 0`, eq. (13.35) reduces to
`Δx_b = v_bx sin(ω_bz)/ω_bz`, `Δy_b = v_bx (1 − cos ω_bz)/ω_bz`, and the
midpoint formula above is the standard closed form of that arc. It is therefore
**exact for constant wheel rates over one sample**, not merely Euler
integration. For `|Δθ|` tiny the runtime uses the straight-line branch to avoid
`0/0`; the conservative bound `|Δs|` is then correct to first order, and the
implemented surrogate uses the midpoint form directly (no division by `Δθ`).

Important limitations, stated in MR §13.4 p. 548: odometry accumulates slip,
skid and integration error and should be corrected by exteroceptive sensing in a
filter. The assignment forbids correcting odometry with ground truth; the
surrogate's default no-slip model therefore yields zero odometry error, which is
a **model artifact, not a calibration result**. A slip run (e.g. 2%) exercises
the separation between encoder odometry and true pose while the controller is
still allowed to use only encoders and proximity.

Wrap convention: exactly `[-π, π)` with `−π` included and `+π` mapped to `−π`.
The Lean `wrap` is `toIcoMod two_pi_pos (−π)`; `wrap_pi` proves `wrap π = −π`.
The Python runtime uses `(θ + π) mod 2π − π`; the Octave reference must use
`mod(θ + pi, 2*pi) - pi` (Octave `mod` takes the sign of the divisor, unlike
`rem`), which the local Octave check can confirm. A runtime differential test
must include `θ = π`, `−π`, `3π` and values just below/above the boundary.

## 4. Proximity range versus footprint clearance

This is the most common source of false "safe" readings. A sensor at body offset
`s = (s_x, s_y)` and ray direction unit vector `u = (cos ψ, sin ψ)` returns a
range `ρ` measured from the sensor origin, not from the axle and not from the
bumper. Define the wall's inward unit normal `n` (pointing into free space) and
signed offset `h` such that wall points satisfy `n·p = h`. For a ray hit,

```
ρ = (h − n·s) / (n·u),        n·u > 0
```

and the perpendicular signed distance from a body point `p` to the wall is
`h − n·p`. The **footprint clearance** is

```
clearance(n) = h − max_{q ∈ footprint} n·q
             = h − (n·p_ref + support_footprint(n))
```

where `p_ref` is the axle midpoint (body origin) and the support function of the
rectangle is `a|n·x̂_b| + c|n·ŷ_b|`. Substituting the ray equation gives the
inverse relation used to derive a trigger threshold:

```
ρ_trigger = (d_desired + a|n·x̂_b| + c|n·ŷ_b| − n·s) / (n·u)
```

For the head-on case (`n = x̂_b`, `u = x̂_b`, front sensor at `s_x = a`), this
reduces to `ρ_trigger = d_desired`: the front sensor sits on the bumper plane and
its range is already the bumper clearance. For a sensor mounted behind the
bumper, add the offset `a − s_x`. For a sensor looking sideways at a parallel
wall (`n = ŷ_b`, `u = ŷ_b`, `s_y = c`), `ρ_trigger = d_desired` as well. In
general the same `ρ` maps to a **different** clearance when the wall is oblique;
using `ρ` directly as clearance is conservative only when the sensor is at or
ahead of the support plane along the wall normal.

Two failure modes are explicit design requirements:

1. **No detection is not distance zero.** CoppeliaSim's
   `sim.readProximitySensor` returns `(res, dist, point, obj, n)`; `dist` is
   meaningful only when `res == 1`. The runtime must represent "no hit within
   max range" as `None`/`inf`, never as `0.0`, and must not treat it as either
   "very close" or "verified far". In the surrogate, `ray_range` returns `None`
   when no wall is hit within `max_range`; the controller uses a separate
   `valid` flag and the front gate takes `d = +inf` only for the forward-stop
   test, never for a clearance statistic.
2. **Minimum statistics must not be seeded with a dummy 0.** The previous
   implementation inserted an initial clearance of `0.0`, corrupting the
   minimum. The surrogate computes statistics only from real samples, and a
   missing reading is excluded and logged as missing, not filled with zero.

CoppeliaSim `sim.checkCollision(entity1, entity2)` returns
`(result, collidingObjectHandles)`; at the scene level the robot must be a
**collection/compound that includes the chassis and both wheels**, not just the
root object. Checking only the root shape was the earlier defect. The surrogate
checks the rectangle footprint against every wall edge, including crossings and
full containment, so a wall entirely inside the footprint or a footprint corner
crossing a wall edge both return distance zero (see §11).

## 5. Final front-protection gate

The behavior policy is untrusted: any state may propose a positive forward
velocity while the front is close. The design applies a **last** command
transformation, after all behavior steering and after any wall-following yaw
command:

```
step(state) = protect(policy(state))
protect(cmd) = { v := if d_front ≤ d_brake then min(cmd.v, 0) else cmd.v
               , ω := if turnClear then cmd.ω else 0 }   (valid sensors)
             = { v := 0, ω := 0 }                        (invalid sensors)
```

Ordering is part of the contract: `protect` is the last function before wheel
conversion, so no state can overwrite it. This is proved in Lean as
`step = protect ∘ policy` and `every_state_front_nonforward`: for **every**
state and every policy, `d_front ≤ d_brake` implies final `v ≤ 0`. The gate does
not by itself prove physical collision-freedom: it needs assumptions on sensor
latency, braking distance, footprint and wall geometry. Those assumptions must
be stated in the report, not hidden as axioms.

`min(cmd.v, 0)` rather than `v := 0` is deliberate: a behavior may command a
small reverse to escape, and the gate only forbids positive forward motion. The
Lean theorem `protect_front_nonforward` proves the `≤ 0` property. The
`turnClear` branch handles the conservative turning footprint; when clearance is
unconfirmed the yaw command is zeroed rather than allowed to sweep the body.

Braking distance: with a command update period `Δt` and maximum deceleration
`a_dec`, a sufficient conservative trigger distance is
`d_brake ≥ v_max Δt + v_max²/(2 a_dec) + ε_latency`. The surrogate is
kinematic and instantaneous, so it uses a static `d_brake` margin; the real
adapter must measure `Δt`, deceleration and sensor latency and recompute this
bound. The Lean theorem is parameterized by `d_brake` precisely so this physical
obligation is not disguised as a proof.

## 6. Lost-wall timing and bounded fallback

Wall following distinguishes four behaviors explicitly:
`FOLLOW` (wall acquired, steer to hold clearance), `AVOID` (too close, steer
away), `REACQUIRE` (lost, search with bounded forward motion and yaw), and
`STOP` (lost timeout or front protection). Hysteresis bands:
`d_follow ± h`, `d_avoid < d_follow − h`, `d_reacquire > d_follow + h`; the
band prevents chatter at a single threshold. On each control tick:

```
if reading valid and in band:  lost_ticks := 0; state := FOLLOW/AVOID
else if reading valid far:     lost_ticks := 0; state := REACQUIRE
else:                          lost_ticks := lost_ticks + 1
if lost_ticks > N_lost:        state := STOP; v := 0; ω := 0
```

The earlier defect reset the timer but never advanced it, so the fallback was
unreachable. The Lean model proves (a) a valid in-band reading resets the timer
to zero, (b) an invalid reading increments it by one, and (c) once the counter
exceeds `N_lost` the emitted command is zero and stays zero unless a valid
reading explicitly reacquires. `N_lost` must be derived from the control period
and a chosen maximum dead-reckoning distance, not invented at runtime; the
report records the derivation. The fallback is **bounded**: no unbounded spin,
no unbounded forward search. Reacquisition only accepts a side reading inside
the hysteresis band and may require two consecutive valid samples to reject a
single spurious return; the surrogate logs the timer and state each tick.

## 7. Conservative turning footprint

When the robot rotates in place about the axle midpoint, every footprint point
sweeps a circle. For a rectangle with half-length `a` and half-width `c`, the
farthest point is a corner at radius

```
R_sweep = sqrt(a² + c²) = sqrt(0.23² + 0.19²) ≈ 0.2983 m
```

using the declared surrogate dimensions. A sufficient condition for a full
in-place rotation to avoid a wall whose shortest distance from the axle midpoint
is `d_pivot` is `d_pivot > R_sweep + margin`. For a partial rotation between
headings `θ1` and `θ2`, the swept region is an annular sector; a cheaper
conservative test is to sample the rectangle at a finite set of headings
(including both endpoints) and check each polygon against the walls, or to use
the full circle bound when the required turn is large. The surrogate's
`turn_clear` uses the circle bound for the stationary corner-turn gate, with the
stated assumption that sensed walls are aligned with the current rays; this is
**conservative only under that assumption** and is not a general swept-volume
collision proof. A local CoppeliaSim run must verify the actual wheel and
chassis meshes against the joined corner, because the footprint rectangle is an
outer bound, not the true Pioneer outline.

The corner itself is a **joined** inside corner: two perpendicular wall
segments share the corner vertex exactly (gap 0). The previous 0.2075 m gap was
a geometry bug that let the robot cut the corner. The surrogate constructs the
corner from shared endpoints and a regression test asserts the wall endpoints
coincide to within 1e-12 and that the polygon distance at the corner is 0.

## 8. Goal test and success hold

For Test 1, the goal is `(0.8, 0.5)`; the controller drives midpoint position
error to a tolerance and then commands zero. The evaluation separates:

* **estimated position error** `‖p_est − goal‖ ≤ 0.05 m` and
  `|wrap(θ_est − θ_goal)| ≤ 5°` at the moment the zero-command hold begins;
* **actual final error** `‖p_true − goal‖`, reported separately, never used to
  steer.

The success hold must be continuous for 1 s: the implementation records a
`hold_ticks` counter that increments only while `v == 0 && ω == 0` and the
tolerance is still satisfied; any nonzero command resets it. A single instant of
zero command does not satisfy the requirement. The Lean `hold` predicate
captures "contiguous run of at least N samples", and a runtime test feeds a
one-tick nonzero command in the middle and checks the run restarts.

Wrap: `wrap(θ_est − θ_goal)` with the `[-π, π)` convention; `+π` must not be
reported as a success when the bound is exactly 5° (it is not, but the test must
still pin the convention because `atan2` returns `+π` on the negative x-axis).
The Lean development deliberately avoids an `atan2` API: the pinned mathlib
revision inspected locally has no `Real.atan2` under `Mathlib/`, so the proofs
use `sin`/`cos` and `toIcoMod` algebra instead of inventing an API. Runtime
`atan2` is tested separately against the wrap convention at the branch cut.

## 9. Controller comparison (draft; to be completed)

Candidate approaches considered:

| approach | strengths | weaknesses for this assignment |
|---|---|---|
| goal-directed proportional (`v = k_p e`, `ω = k_θ wrap(θ_goal − θ)`) | simple, few parameters, easy to prove bounded | no obstacle awareness; needs front gate; heading wrap |
| pure pursuit / carrot | smooth paths, good for following | requires a path/waypoints; not needed for point goal and wall follow |
| potential fields | reactive, combines goal and obstacles | local minima at inside corners; no explicit lost-wall state; hard to bound |
| Bug2 / wall-following hybrid | complete under ideal sensing | needs robust wall-follow controller and reacquire logic; sensor noise |
| hysteresis state machine (chosen) | explicit states, bounded lost behavior, testable | tuning; corner transient; needs conservative turn gate |

The chosen design is a goal-directed proportional controller for Test 1, a
front-gated approach for Test 2, and a hysteresis wall-follow state machine for
Test 3, with `protect` shared by all three. The comparison is about
**verifiability**: explicit states and a last gate give small, checkable
invariants; potential fields do not. This section will cite the inspected
robotics sources and add measured surrogate comparisons after the runs.

## 10. Octave numerical parity, Webots/Coppelia alternatives, and boundaries

* **Octave** is used only as an independent numerical cross-check of a small
  equation subset (`simulation/reference_checks.m`), not as the assignment
  implementation. Octave's `mod` follows the divisor's sign and `atan2` has the
  usual `(-π, π]` branch; the reference script must explicitly wrap to
  `[-π, π)` to match. Floating-point parity with MATLAB is not a proof: both are
  IEEE-754 double implementations, but library `atan2`, `mod` and reduction
  details can differ in the last bits. The differential test therefore uses
  tolerances and explicit boundary cases, and the report labels it a numerical
  check, not a refinement proof.
* **CoppeliaSim** is the mandated simulator. Its Python remote API is a legal
  free client, but the assignment requires MATLAB control/sensing/odometry/
  logging and a saved scene/video. A Python/Webots surrogate cannot be
  substituted without instructor authorization. The headless Python surrogate
  in `simulation/` is deliberately labelled a **surrogate**, not CoppeliaSim.
* **Webots** is a free alternative with a differential-wheel model and distance
  sensors, but using it would still not satisfy the CoppeliaSim requirement; it
  is useful only as an optional cross-simulator sanity check on geometry and
  sensor semantics. Its documentation and source are cited in the manifest for
  that limited purpose.

## 11. Requirements → source → design → test map (draft)

| requirement | source inspected | design decision | test/evidence |
|---|---|---|---|
| inverse kinematics, uniform scaling | MR §13.3.1.2 eq. (13.14)–(13.15); Lean `wl`,`wr` | `b` full track, CCW positive, scale both wheels | `wl_compose`, `wr_compose`, `wl_scale`; Python round-trip test |
| measured encoder odometry | MR §13.4 eq. (13.34)–(13.36) | midpoint arc; encoders only; no GT correction | `test_odometry_midpoint`, slip run separates estimate/GT |
| heading wrap `[-π,π)` | Lean `wrap`; Octave `mod` semantics | `toIcoMod` in Lean; `(θ+π) mod 2π−π` runtime | `wrap_pi`, `wrap_neg_pi`; runtime boundary test |
| sensor offset vs footprint | `simReadProximitySensor` res/dist semantics; geometry §4 | convert range to footprint clearance with support function; `None` for no hit | geometry unit tests; no-detection test |
| final front protection | Lean `protect`/`step` | last gate, `v ≤ 0` when `d ≤ brake`, zero yaw if turn unclear | `protect_front_nonforward`, `every_state_front_nonforward`; overwrite mutant rejected |
| lost-wall timer | Lean timer module | increment/reset, bounded STOP | timer progress theorem; frozen-timer mutant rejected |
| joined inside corner | geometry | shared vertex, gap 0 | corner gap regression test |
| collision includes wheels | `simCheckCollision` entities | robot collection, chassis + both wheels | local Coppelia check; surrogate all-edge polygon check |
| no dummy clearance 0 | statistics | exclude missing; do not seed 0 | min-clearance statistic test |
| 1 s zero hold | requirement | contiguous counter, nonzero resets | hold test with injected tick |
| two speeds identical geometry | requirement | same params, only speed differs | slow/fast CSV comparison, failed runs preserved |

## 12. Open obligations for later cycles

1. Finish the controller-comparison citations and add measured surrogate
   comparisons for the slow/fast corner runs.
2. Record exact source hashes/bytes in `source_manifest.json` (in progress).
3. Add the Octave/Webots/Coppelia boundary citations and the exact remote-API
   call sequence (simxStart, simxGetObjectHandle, simxReadProximitySensor,
   simxSetJointTargetVelocity, simxGetJointPosition) from the inspected manual.
4. Cross-check every numeric claim in the report against actual CSV/metrics
   runs; never copy this draft's `R_sweep` or timing constants into results.
