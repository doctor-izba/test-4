import Mathlib.Basic.Real.Basic
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Algebra.Order.ToIntervalMod
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! Mathematical controller contracts. These definitions do not certify MATLAB,
CoppeliaSim physics, sensors or the provenance of experiment logs. -/
noncomputable section
namespace Assignment4

def wl (v w b r : ℝ) : ℝ := (v - b * w / 2) / r
def wr (v w b r : ℝ) : ℝ := (v + b * w / 2) / r
def vBody (omegaL omegaR r : ℝ) : ℝ := r * (omegaL + omegaR) / 2
def wBody (omegaL omegaR b r : ℝ) : ℝ := r * (omegaR - omegaL) / b

theorem vBody_of_wl_wr (v w b r : ℝ) (hr : r ≠ 0) :
    vBody (wl v w b r) (wr v w b r) r = v := by
  unfold vBody wl wr
  field_simp [hr]
  <;> ring

theorem wBody_of_wl_wr (v w b r : ℝ) (hb : b ≠ 0) (hr : r ≠ 0) :
    wBody (wl v w b r) (wr v w b r) b r = w := by
  unfold wBody wl wr
  field_simp [hb, hr]
  <;> ring

theorem wl_compose (omegaL omegaR b r : ℝ) (hb : b ≠ 0) (hr : r ≠ 0) :
    wl (vBody omegaL omegaR r) (wBody omegaL omegaR b r) b r = omegaL := by
  unfold wl vBody wBody
  field_simp [hb, hr]
  <;> ring

theorem wr_compose (omegaL omegaR b r : ℝ) (hb : b ≠ 0) (hr : r ≠ 0) :
    wr (vBody omegaL omegaR r) (wBody omegaL omegaR b r) b r = omegaR := by
  unfold wr vBody wBody
  field_simp [hb, hr]
  <;> ring

theorem wl_scale (v w b r s : ℝ) :
    wl (s * v) (s * w) b r = s * wl v w b r := by unfold wl; ring
theorem wr_scale (v w b r s : ℝ) :
    wr (s * v) (s * w) b r = s * wr v w b r := by unfold wr; ring
theorem curvature_scale (v w s : ℝ) (hv : v ≠ 0) (hs : s ≠ 0) :
    (s * w) / (s * v) = w / v := by field_simp [hv, hs]

theorem front_clearance_identity (W sX f rho c : ℝ)
    (hray : sX + rho * c = W) : W - f = rho * c + sX - f := by linarith
theorem front_range_for_clearance (W sX f c rho d : ℝ) (hc : c ≠ 0)
    (hclr : W - f = d) (hray : sX + rho * c = W) :
    rho = (d + f - sX) / c := by
  apply (eq_div_iff hc).2
  linarith
theorem side_clearance_identity (hw yOff rho : ℝ) :
    rho - (hw - yOff) = rho + yOff - hw := by ring

/-! The chosen wrap is [-π,π), including the left endpoint. -/
def wrap (theta : ℝ) : ℝ := toIcoMod Real.two_pi_pos (-Real.pi) theta
theorem wrap_range (theta : ℝ) : -Real.pi ≤ wrap theta ∧ wrap theta < Real.pi := by
  have h := toIcoMod_mem_Ico Real.two_pi_pos (-Real.pi) theta
  change -Real.pi ≤ wrap theta ∧ wrap theta < -Real.pi + 2 * Real.pi at h
  constructor
  · exact h.1
  · linarith [h.2]
theorem wrap_abs_le_pi (theta : ℝ) : |wrap theta| ≤ Real.pi := by
  exact abs_le.2 ⟨(wrap_range theta).1, le_of_lt (wrap_range theta).2⟩
theorem wrap_neg_pi : wrap (-Real.pi) = -Real.pi := by
  exact toIcoMod_apply_left Real.two_pi_pos (-Real.pi)
theorem wrap_pi : wrap Real.pi = -Real.pi := by
  have h := toIcoMod_apply_right Real.two_pi_pos (-Real.pi)
  unfold wrap
  convert h using 1 <;> ring
theorem heading_command_bounded (k theta : ℝ) (hk : 0 ≤ k) :
    |k * wrap theta| ≤ k * Real.pi := by
  rw [abs_mul, abs_of_nonneg hk]
  exact mul_le_mul_of_nonneg_left (wrap_abs_le_pi theta) hk

/-! Correct CCW transform; translation is deliberately separate. -/
def rotX (theta x y : ℝ) : ℝ := x * Real.cos theta - y * Real.sin theta
def rotY (theta x y : ℝ) : ℝ := x * Real.sin theta + y * Real.cos theta
theorem rot_zero (x y : ℝ) : rotX 0 x y = x ∧ rotY 0 x y = y := by
  simp [rotX, rotY]
theorem rot_quarter (x y : ℝ) :
    rotX (Real.pi / 2) x y = -y ∧ rotY (Real.pi / 2) x y = x := by
  simp [rotX, rotY]
theorem rot_preserves_squared_norm (theta x y : ℝ) :
    rotX theta x y ^ 2 + rotY theta x y ^ 2 = x ^ 2 + y ^ 2 := by
  unfold rotX rotY
  calc
    _ = (x ^ 2 + y ^ 2) * (Real.sin theta ^ 2 + Real.cos theta ^ 2) := by ring
    _ = x ^ 2 + y ^ 2 := by rw [Real.sin_sq_add_cos_sq]; ring

inductive State where
  | approach | follow | corner | reacquire | stopped | failed
  deriving DecidableEq
structure Command where
  v : ℝ
  w : ℝ

-- This must be the LAST behavior-independent gate before wheel conversion.
def protect (valid : Bool) (front brake : ℝ) (turnClear : Bool) (cmd : Command) : Command :=
  if valid then
    { v := if front ≤ brake then min cmd.v 0 else cmd.v
      w := if turnClear then cmd.w else 0 }
  else { v := 0, w := 0 }

theorem protect_front_nonforward (front brake : ℝ) (turnClear : Bool) (cmd : Command)
    (h : front ≤ brake) : (protect true front brake turnClear cmd).v ≤ 0 := by
  simp only [protect, ite_true, h]
  exact min_le_right _ _
theorem protect_invalid (front brake : ℝ) (turnClear : Bool) (cmd : Command) :
    (protect false front brake turnClear cmd).v = 0 ∧
    (protect false front brake turnClear cmd).w = 0 := by simp [protect]
theorem protect_unconfirmed_turn (valid : Bool) (front brake : ℝ) (cmd : Command) :
    (protect valid front brake false cmd).w = 0 := by cases valid <;> simp [protect]
def step (policy : State → Command) (state : State) (front brake : ℝ) : Command :=
  protect true front brake true (policy state)
theorem every_state_front_nonforward (policy : State → Command) (state : State)
    (front brake : ℝ) (h : front ≤ brake) : (step policy state front brake).v ≤ 0 :=
  protect_front_nonforward front brake true (policy state) h

def lostTimer (detected : Bool) (elapsed dt : ℝ) : ℝ :=
  if detected then 0 else elapsed + max 0 dt
theorem lostTimer_reset (elapsed dt : ℝ) : lostTimer true elapsed dt = 0 := by
  simp [lostTimer]
theorem lostTimer_advances (elapsed dt : ℝ) (hdt : 0 ≤ dt) :
    lostTimer false elapsed dt = elapsed + dt := by simp [lostTimer, max_eq_right hdt]
theorem lostTimer_nondecreasing (elapsed dt : ℝ) :
    elapsed ≤ lostTimer false elapsed dt := by
  simp only [lostTimer, Bool.false_eq_true, ite_false]
  linarith [le_max_left (0 : ℝ) dt]

def limitDenom (omegaL omegaR limit : ℝ) : ℝ :=
  max 1 (max |omegaL| |omegaR| / limit)
theorem limitDenom_positive (omegaL omegaR limit : ℝ) :
    0 < limitDenom omegaL omegaR limit := by
  have h : (1 : ℝ) ≤ limitDenom omegaL omegaR limit := le_max_left _ _
  linarith
theorem limited_wheel_bound (omegaL omegaR limit : ℝ) (hl : 0 < limit) :
    |omegaL / limitDenom omegaL omegaR limit| ≤ limit ∧
    |omegaR / limitDenom omegaL omegaR limit| ≤ limit := by
  have hd := limitDenom_positive omegaL omegaR limit
  have hm : max |omegaL| |omegaR| / limit ≤ limitDenom omegaL omegaR limit :=
    le_max_right _ _
  have hbound := (div_le_iff₀ hl).1 hm
  have hL := le_max_left |omegaL| |omegaR|
  have hR := le_max_right |omegaL| |omegaR|
  rw [abs_div, abs_of_pos hd, abs_div, abs_of_pos hd]
  constructor
  · apply (div_le_iff₀ hd).2
    nlinarith
  · apply (div_le_iff₀ hd).2
    nlinarith
theorem common_scale_preserves_nonforward (v denom : ℝ) (hv : v ≤ 0) (hd : 0 < denom) :
    v / denom ≤ 0 := div_nonpos_of_nonpos_of_nonneg hv (le_of_lt hd)

theorem limitDenom_inside_bounds (omegaL omegaR limit : ℝ) (hl : 0 < limit)
    (hL : |omegaL| ≤ limit) (hR : |omegaR| ≤ limit) :
    limitDenom omegaL omegaR limit = 1 := by
  unfold limitDenom
  apply max_eq_left
  apply (div_le_one₀ hl).2
  exact max_le hL hR

theorem vBody_div (omegaL omegaR r denom : ℝ) :
    vBody (omegaL / denom) (omegaR / denom) r = vBody omegaL omegaR r / denom := by
  unfold vBody
  ring

-- Protection survives the complete body->wheels->common-limit->body path.
theorem final_limited_nonforward (policy : State → Command) (state : State)
    (front brake b r limit : ℝ) (hr : r ≠ 0) (h : front ≤ brake) :
    let cmd := step policy state front brake
    let left := wl cmd.v cmd.w b r
    let right := wr cmd.v cmd.w b r
    let denom := limitDenom left right limit
    vBody (left / denom) (right / denom) r ≤ 0 := by
  dsimp only
  rw [vBody_div, vBody_of_wl_wr _ _ _ _ hr]
  exact common_scale_preserves_nonforward _ _
    (every_state_front_nonforward policy state front brake h)
    (limitDenom_positive _ _ _)

-- The increments here represent measured encoder differences, not commands.
def measuredCenterIncrement (r deltaL deltaR : ℝ) : ℝ := r * (deltaL + deltaR) / 2
def measuredHeadingIncrement (b r deltaL deltaR : ℝ) : ℝ := r * (deltaR - deltaL) / b
theorem equal_measured_increments_no_turn (b r delta : ℝ) :
    measuredHeadingIncrement b r delta delta = 0 := by simp [measuredHeadingIncrement]
theorem opposite_measured_increments_no_translation (r delta : ℝ) :
    measuredCenterIncrement r delta (-delta) = 0 := by simp [measuredCenterIncrement]
theorem zero_measured_increments (b r : ℝ) :
    measuredCenterIncrement r 0 0 = 0 ∧ measuredHeadingIncrement b r 0 0 = 0 := by
  simp [measuredCenterIncrement, measuredHeadingIncrement]

/-! ## Wrap homomorphism and idempotence

`wrap` is `toIcoMod` on `[-π, π)`.  The two lemmas below are the algebraic
facts needed to compose measured heading increments without leaving the
canonical interval. -/
theorem wrap_add (x y : ℝ) : wrap (x + y) = wrap (wrap x + y) := by
  unfold wrap
  rw [toIcoMod_eq_iff]
  constructor
  · exact toIcoMod_mem_Ico _ _ _
  · have hx : ∃ z : ℤ, x = toIcoMod Real.two_pi_pos (-Real.pi) x + z • (2 * Real.pi) := by
      have := (toIcoMod_eq_iff (p := 2 * Real.pi) (hp := Real.two_pi_pos) (a := -Real.pi)
        (b := x) (c := toIcoMod Real.two_pi_pos (-Real.pi) x)).1 rfl
      exact this.2
    have hy : ∃ z : ℤ, toIcoMod Real.two_pi_pos (-Real.pi) x + y =
        toIcoMod Real.two_pi_pos (-Real.pi) (toIcoMod Real.two_pi_pos (-Real.pi) x + y)
          + z • (2 * Real.pi) := by
      have := (toIcoMod_eq_iff (p := 2 * Real.pi) (hp := Real.two_pi_pos) (a := -Real.pi)
        (b := toIcoMod Real.two_pi_pos (-Real.pi) x + y)
        (c := toIcoMod Real.two_pi_pos (-Real.pi)
          (toIcoMod Real.two_pi_pos (-Real.pi) x + y))).1 rfl
      exact this.2
    obtain ⟨z, hz⟩ := hx
    obtain ⟨z', hz'⟩ := hy
    refine ⟨z' + z, ?_⟩
    calc x + y = (toIcoMod Real.two_pi_pos (-Real.pi) x + z • (2 * Real.pi)) + y := by
          nth_rewrite 1 [hz]; rfl
      _ = (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + z • (2 * Real.pi) := by abel
      _ = (toIcoMod Real.two_pi_pos (-Real.pi)
            (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + z' • (2 * Real.pi))
            + z • (2 * Real.pi) := by nth_rewrite 1 [hz']; rfl
      _ = toIcoMod Real.two_pi_pos (-Real.pi)
            (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + (z' + z) • (2 * Real.pi) := by
          simp only [add_zsmul]; abel

theorem wrap_wrap (x : ℝ) : wrap (wrap x) = wrap x := by
  unfold wrap
  rw [toIcoMod_eq_iff]
  exact ⟨toIcoMod_mem_Ico _ _ _, ⟨0, by simp⟩⟩

/-! ## Rotation: inverse, composition, and the rejected row-vector sign -/
theorem rot_inverse (theta x y : ℝ) :
    rotX (-theta) (rotX theta x y) (rotY theta x y) = x ∧
    rotY (-theta) (rotX theta x y) (rotY theta x y) = y := by
  unfold rotX rotY
  rw [Real.cos_neg, Real.sin_neg]
  constructor
  · ring_nf
    linear_combination x * Real.sin_sq_add_cos_sq theta
  · ring_nf
    linear_combination y * Real.sin_sq_add_cos_sq theta

theorem rot_compose (theta phi x y : ℝ) :
    rotX (theta + phi) x y = rotX theta (rotX phi x y) (rotY phi x y) ∧
    rotY (theta + phi) x y = rotY theta (rotX phi x y) (rotY phi x y) := by
  unfold rotX rotY
  rw [Real.cos_add, Real.sin_add]
  constructor <;> ring

/-- The old row-vector formula.  It is retained only to state the rejection
test: on `(0,1)` at `+90°` it returns `+1`, whereas the correct CCW map
returns `-1`. -/
def rowRotX (theta x y : ℝ) : ℝ := x * Real.cos theta + y * Real.sin theta

theorem row_rotation_wrong_at_ninety :
    rowRotX (Real.pi / 2) 0 1 = 1 ∧ rotX (Real.pi / 2) 0 1 = -1 := by
  unfold rowRotX rotX
  simp [Real.cos_pi_div_two, Real.sin_pi_div_two]

theorem nonsquare_corner_rot90 (L W : ℝ) :
    rotX (Real.pi / 2) L W = -W ∧ rotY (Real.pi / 2) L W = L := by
  unfold rotX rotY
  simp [Real.cos_pi_div_two, Real.sin_pi_div_two]

/-! ## Sensor semantics: absence of a detection is not a zero distance

`frontGate` is a total function on `Option ℝ`.  `none` means "no valid
detection" and is conservatively converted to zero forward command, never to
a numeric zero distance.  `minReadings` keeps `none` out of the minimum
statistic entirely. -/
def frontGate (reading : Option ℝ) (brake v : ℝ) : ℝ :=
  match reading with
  | none => 0
  | some d => if d ≤ brake then min v 0 else v

theorem frontGate_none (brake v : ℝ) : frontGate none brake v = 0 := rfl

theorem frontGate_some_nonforward (d brake v : ℝ) (h : d ≤ brake) :
    frontGate (some d) brake v ≤ 0 := by
  simp [frontGate, h]

theorem frontGate_some_forward (d brake v : ℝ) (h : brake < d) :
    frontGate (some d) brake v = v := by
  simp [frontGate, not_le_of_gt h]

def minOpt : Option ℝ → Option ℝ → Option ℝ
  | none, b => b
  | some a, none => some a
  | some a, some b => some (min a b)

def minReadings : List (Option ℝ) → Option ℝ
  | [] => none
  | r :: rs => minOpt r (minReadings rs)

theorem minReadings_eq_none_iff (xs : List (Option ℝ)) :
    minReadings xs = none ↔ ∀ r ∈ xs, r = none := by
  induction xs with
  | nil => simp [minReadings]
  | cons r rs ih =>
      cases r with
      | none => simp [minReadings, minOpt, ih]
      | some a =>
          cases h : minReadings rs with
          | none => simp [minReadings, minOpt, h, ih]
          | some m => simp [minReadings, minOpt, h]

/-! ## Final guard ordering and positive-command override -/
theorem protect_zeroes_positive (front brake : ℝ) (turnClear : Bool) (cmd : Command)
    (h : front ≤ brake) (hp : 0 < cmd.v) :
    (protect true front brake turnClear cmd).v = 0 := by
  simp [protect, h, min_eq_right (le_of_lt hp)]

/-- The final gate is the last operation on the policy command: when the front
reading is at or below the braking threshold, the resulting forward speed is
the minimum of the proposed speed and zero, independently of the state and of
the side-steering permission. -/
theorem final_guard_overrides_policy (policy : State → Command) (state : State)
    (front brake : ℝ) (h : front ≤ brake) :
    (step policy state front brake).v = min (policy state).v 0 := by
  simp [step, protect, h]

theorem final_guard_rejects_positive_policy (policy : State → Command) (state : State)
    (front brake : ℝ) (h : front ≤ brake) (hp : 0 < (policy state).v) :
    (step policy state front brake).v = 0 :=
  protect_zeroes_positive front brake true (policy state) h hp

/-! ## Lost-wall timer: reset/advance cycle, unbounded liveness, bounded stop -/
theorem lostTimer_reset_then_advance (elapsed dt : ℝ) (hdt : 0 ≤ dt) :
    lostTimer false (lostTimer true elapsed dt) dt = dt := by
  simp [lostTimer, max_eq_right hdt]

theorem lostTimer_iterate (dt : ℝ) (hdt : 0 ≤ dt) (n : ℕ) :
    Nat.iterate (fun e => lostTimer false e dt) n 0 = (n : ℝ) * dt := by
  induction n with
  | zero => simp
  | succ n ih =>
      rw [Function.iterate_succ_apply']
      simp [lostTimer, hdt, ih]
      ring

/-- With a positive sample period, repeated non-detection eventually reaches
any positive timeout.  This is an existential liveness statement, not a claim
that a particular real-time scheduler fires on time. -/
theorem lostTimer_reaches_timeout (dt timeout : ℝ) (hdt : 0 < dt) :
    ∃ n : ℕ, timeout ≤ Nat.iterate (fun e => lostTimer false e dt) n 0 := by
  obtain ⟨n, hn⟩ := exists_nat_gt (timeout / dt)
  refine ⟨n, ?_⟩
  rw [lostTimer_iterate dt (le_of_lt hdt)]
  have hlt : timeout < (n : ℝ) * dt := by
    have h := mul_lt_mul_of_pos_right hn hdt
    rwa [div_mul_cancel₀ _ (ne_of_gt hdt)] at h
  linarith

def timeoutStop (timeout elapsed : ℝ) (cmd : Command) : Command :=
  if timeout ≤ elapsed then { v := 0, w := 0 } else cmd

theorem timeoutStop_stops (timeout elapsed : ℝ) (cmd : Command)
    (h : timeout ≤ elapsed) :
    (timeoutStop timeout elapsed cmd).v = 0 ∧
    (timeoutStop timeout elapsed cmd).w = 0 := by
  simp [timeoutStop, h]

/-! ## Uniform limiter: zero, ratio and body-ratio preservation -/
theorem limited_zero (limit : ℝ) : 0 / limitDenom 0 0 limit = 0 := by
  simp

theorem limited_ratio (omegaL omegaR limit : ℝ) (hr : omegaR ≠ 0) :
    (omegaL / limitDenom omegaL omegaR limit) /
        (omegaR / limitDenom omegaL omegaR limit) = omegaL / omegaR := by
  have hd : limitDenom omegaL omegaR limit ≠ 0 :=
    ne_of_gt (limitDenom_positive omegaL omegaR limit)
  field_simp [hd]

theorem wBody_div (omegaL omegaR b r d : ℝ) (hd : d ≠ 0) :
    wBody (omegaL / d) (omegaR / d) b r = wBody omegaL omegaR b r / d := by
  unfold wBody
  field_simp [hd]

/-- The common denominator scales both body velocities by the same factor, so
the requested `v:w` relation is unchanged whenever `w ≠ 0`. -/
theorem body_ratio_div (omegaL omegaR b r d : ℝ)
    (hd : d ≠ 0) (hw : wBody omegaL omegaR b r ≠ 0) :
    vBody (omegaL / d) (omegaR / d) r / wBody (omegaL / d) (omegaR / d) b r =
      vBody omegaL omegaR r / wBody omegaL omegaR b r := by
  rw [vBody_div, wBody_div omegaL omegaR b r d hd]
  field_simp [hd, hw]

/-! ## Discrete zero-command success hold

A run is accepted only if the last `limit` samples are all good.  The
executable counter resets on any bad sample and saturates at `limit`. -/
def holdStep (limit held : ℕ) (good : Bool) : ℕ :=
  if good then min (held + 1) limit else 0

def holdRun (limit : ℕ) : List Bool → ℕ
  | [] => 0
  | b :: bs => holdStep limit (holdRun limit bs) b

def LastAllTrue : ℕ → List Bool → Prop
  | 0, _ => True
  | _ + 1, [] => False
  | n + 1, b :: bs => b = true ∧ LastAllTrue n bs

theorem holdRun_ge_lastAllTrue (limit n : ℕ) (bs : List Bool)
    (hn : n ≤ limit) (h : n ≤ holdRun limit bs) : LastAllTrue n bs := by
  induction bs generalizing n with
  | nil =>
      simp [holdRun] at h
      subst h
      simp [LastAllTrue]
  | cons b bs ih =>
      cases n with
      | zero => simp [LastAllTrue]
      | succ n =>
          cases b with
          | false => simp [holdRun, holdStep] at h
          | true =>
              have h' : n + 1 ≤ min (holdRun limit bs + 1) limit := by
                simpa [holdRun, holdStep] using h
              have h1 : n ≤ holdRun limit bs := by
                have := le_trans h' (min_le_left (holdRun limit bs + 1) limit)
                omega
              have h2 : n ≤ limit := by
                have := le_trans h' (min_le_right (holdRun limit bs + 1) limit)
                omega
              exact ⟨rfl, ih n h2 h1⟩

theorem holdRun_success_contiguous (limit : ℕ) (bs : List Bool)
    (h : holdRun limit bs = limit) : LastAllTrue limit bs := by
  apply holdRun_ge_lastAllTrue limit limit bs le_rfl
  omega

theorem holdRun_reset (limit : ℕ) (bs : List Bool) :
    holdRun limit (false :: bs) = 0 := by
  simp [holdRun, holdStep]

theorem holdStep_le (limit held : ℕ) (b : Bool) :
    holdStep limit held b ≤ limit := by
  cases b <;> simp [holdStep]

/-- Zero body commands map to zero measured wheel-rate targets. -/
theorem zero_command_zero_wheels (b r : ℝ) :
    wl 0 0 b r = 0 ∧ wr 0 0 b r = 0 := by
  simp [wl, wr]

/-! ## Measured-wheel odometry composition -/
def odomHeading (b r theta dL dR : ℝ) : ℝ :=
  wrap (theta + measuredHeadingIncrement b r dL dR)

theorem measuredHeadingIncrement_add (b r aL aR bL bR : ℝ) :
    measuredHeadingIncrement b r (aL + bL) (aR + bR)
      = measuredHeadingIncrement b r aL aR +
        measuredHeadingIncrement b r bL bR := by
  unfold measuredHeadingIncrement
  ring

/-- Two measured-increment odometry updates compose into one update whose
increments are the sums.  This is a statement about the exact real arithmetic;
encoder quantization, slip and timing remain outside the model. -/
theorem odomHeading_compose (b r theta aL aR bL bR : ℝ) :
    odomHeading b r (odomHeading b r theta aL aR) bL bR
      = odomHeading b r theta (aL + bL) (aR + bR) := by
  unfold odomHeading
  rw [measuredHeadingIncrement_add]
  rw [← wrap_add]
  congr 1
  ring

theorem odomHeading_range (b r theta dL dR : ℝ) :
    -Real.pi ≤ odomHeading b r theta dL dR ∧
    odomHeading b r theta dL dR < Real.pi :=
  wrap_range _

/-! ## Conditional stopping-distance safety

`stopDistance` models latency plus constant-deceleration braking.  The theorem
is conditional on the stated latency, speed bound and positive deceleration;
it does not model tyre slip, actuator delay distribution or sensing latency. -/
def stopDistance (v latency decel : ℝ) : ℝ :=
  v * latency + v ^ 2 / (2 * decel)

def brakeThreshold (vmax latency decel : ℝ) : ℝ :=
  stopDistance vmax latency decel

theorem stopDistance_le_threshold (v vmax latency decel : ℝ)
    (hv0 : 0 ≤ v) (hvv : v ≤ vmax) (hl : 0 ≤ latency) (hd : 0 < decel) :
    stopDistance v latency decel ≤ brakeThreshold vmax latency decel := by
  simp only [stopDistance, brakeThreshold]
  have h1 : v * latency ≤ vmax * latency := mul_le_mul_of_nonneg_right hvv hl
  have h2 : v ^ 2 ≤ vmax ^ 2 := by nlinarith
  have h3 : v ^ 2 / (2 * decel) ≤ vmax ^ 2 / (2 * decel) :=
    div_le_div_of_nonneg_right h2 (by positivity)
  linarith

/-- Kinematic identity for the braking phase: with constant deceleration
`decel`, travelling for `v / decel` seconds covers `v^2 / (2 * decel)`. -/
theorem braking_distance_identity (v decel latency : ℝ) (hd : decel ≠ 0) :
    v * latency + (v * (v / decel) - decel * (v / decel) ^ 2 / 2)
      = stopDistance v latency decel := by
  unfold stopDistance
  field_simp
  ring

/-! ## Swept turning footprint

The farthest point of an axis-aligned footprint with half-length `L` and
half-width `W` from the axle midpoint is the corner at distance
`sqrt (L^2 + W^2)`.  This is a geometric bound; collision checking still has
to use the actual wall distance. -/
theorem swept_radius_sq (L W : ℝ) :
    (Real.sqrt (L ^ 2 + W ^ 2)) ^ 2 = L ^ 2 + W ^ 2 := by
  rw [Real.sq_sqrt]
  positivity

theorem corner_within_swept_radius (L W x y : ℝ)
    (hx : x ^ 2 ≤ L ^ 2) (hy : y ^ 2 ≤ W ^ 2) :
    x ^ 2 + y ^ 2 ≤ (Real.sqrt (L ^ 2 + W ^ 2)) ^ 2 := by
  rw [swept_radius_sq]
  linarith


end Assignment4
