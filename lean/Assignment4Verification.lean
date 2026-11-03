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

end Assignment4
