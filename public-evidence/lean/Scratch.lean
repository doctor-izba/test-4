import Mathlib.Algebra.Order.ToIntervalMod
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Tactic

noncomputable section
namespace T

def wrap (theta : ℝ) : ℝ := toIcoMod Real.two_pi_pos (-Real.pi) theta

theorem wrap_add (x y : ℝ) : wrap (x + y) = wrap (wrap x + y) := by
  unfold wrap
  rw [toIcoMod_eq_iff]
  constructor
  · exact toIcoMod_mem_Ico _ _ _
  · have hx : ∃ z : ℤ, x = toIcoMod Real.two_pi_pos (-Real.pi) x + z • (2 * Real.pi) := by
      have := (toIcoMod_eq_iff (p := 2 * Real.pi) (hp := Real.two_pi_pos) (a := -Real.pi) (b := x) (c := toIcoMod Real.two_pi_pos (-Real.pi) x)).1 rfl
      exact this.2
    have hy : ∃ z : ℤ, toIcoMod Real.two_pi_pos (-Real.pi) x + y =
        toIcoMod Real.two_pi_pos (-Real.pi) (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + z • (2 * Real.pi) := by
      have := (toIcoMod_eq_iff (p := 2 * Real.pi) (hp := Real.two_pi_pos) (a := -Real.pi)
        (b := toIcoMod Real.two_pi_pos (-Real.pi) x + y)
        (c := toIcoMod Real.two_pi_pos (-Real.pi) (toIcoMod Real.two_pi_pos (-Real.pi) x + y))).1 rfl
      exact this.2
    obtain ⟨z, hz⟩ := hx
    obtain ⟨z', hz'⟩ := hy
    refine ⟨z' + z, ?_⟩
    calc x + y = (toIcoMod Real.two_pi_pos (-Real.pi) x + z • (2 * Real.pi)) + y := by nth_rewrite 1 [hz]; rfl
      _ = (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + z • (2 * Real.pi) := by abel
      _ = (toIcoMod Real.two_pi_pos (-Real.pi) (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + z' • (2 * Real.pi)) + z • (2 * Real.pi) := by nth_rewrite 1 [hz']; rfl
      _ = toIcoMod Real.two_pi_pos (-Real.pi) (toIcoMod Real.two_pi_pos (-Real.pi) x + y) + (z' + z) • (2 * Real.pi) := by simp only [add_zsmul]; abel

#check exists_nat_gt
#check Nat.iterate
#check Real.cos_neg
#check Real.sin_neg
#check Real.cos_add
#check Real.sin_add
#check Real.cos_pi_div_two
#check Real.sin_pi_div_two

def rotX (theta x y : ℝ) : ℝ := x * Real.cos theta - y * Real.sin theta
def rotY (theta x y : ℝ) : ℝ := x * Real.sin theta + y * Real.cos theta

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

end T

namespace T

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
          | false =>
              simp [holdRun, holdStep] at h
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

theorem holdStep_le (limit held : ℕ) (b : Bool) : holdStep limit held b ≤ limit := by
  cases b <;> simp [holdStep]

end T

namespace T

def lostTimer (detected : Bool) (elapsed dt : ℝ) : ℝ :=
  if detected then 0 else elapsed + max 0 dt

theorem lostTimer_iterate (dt : ℝ) (hdt : 0 ≤ dt) (n : ℕ) :
    Nat.iterate (fun e => lostTimer false e dt) n 0 = (n : ℝ) * dt := by
  induction n with
  | zero => simp
  | succ n ih =>
      rw [Function.iterate_succ_apply']
      simp [lostTimer, hdt, ih]
      ring

theorem lostTimer_reaches_timeout (dt timeout : ℝ) (hdt : 0 < dt) :
    ∃ n : ℕ, timeout ≤ Nat.iterate (fun e => lostTimer false e dt) n 0 := by
  obtain ⟨n, hn⟩ := exists_nat_gt (timeout / dt)
  refine ⟨n, ?_⟩
  rw [lostTimer_iterate dt (le_of_lt hdt)]
  have hlt : timeout < (n : ℝ) * dt := by
    have h := mul_lt_mul_of_pos_right hn hdt
    rwa [div_mul_cancel₀ _ (ne_of_gt hdt)] at h
  linarith

structure Cmd where
  v : ℝ
  w : ℝ

def timeoutStop (timeout elapsed : ℝ) (cmd : Cmd) : Cmd :=
  if timeout ≤ elapsed then { v := 0, w := 0 } else cmd

theorem timeoutStop_stops (timeout elapsed : ℝ) (cmd : Cmd) (h : timeout ≤ elapsed) :
    (timeoutStop timeout elapsed cmd).v = 0 ∧ (timeoutStop timeout elapsed cmd).w = 0 := by
  simp [timeoutStop, h]

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

theorem braking_distance_identity (v decel latency : ℝ) (hd : decel ≠ 0) :
    v * latency + (v * (v / decel) - decel * (v / decel) ^ 2 / 2)
      = stopDistance v latency decel := by
  unfold stopDistance
  field_simp
  ring

end T

namespace T

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

def measuredHeadingIncrement (b r dL dR : ℝ) : ℝ := (dR - dL) / b

def odomHeading (b r theta dL dR : ℝ) : ℝ :=
  wrap (theta + measuredHeadingIncrement b r dL dR)

theorem measuredHeadingIncrement_add (b r aL aR bL bR : ℝ) :
    measuredHeadingIncrement b r (aL + bL) (aR + bR)
      = measuredHeadingIncrement b r aL aR + measuredHeadingIncrement b r bL bR := by
  unfold measuredHeadingIncrement
  ring

theorem odomHeading_compose (b r theta aL aR bL bR : ℝ) :
    odomHeading b r (odomHeading b r theta aL aR) bL bR
      = odomHeading b r theta (aL + bL) (aR + bR) := by
  unfold odomHeading
  rw [measuredHeadingIncrement_add]
  rw [← wrap_add]
  congr 1
  ring

def vBody (omegaL omegaR wheelRadius : ℝ) : ℝ :=
  (omegaL + omegaR) * wheelRadius / 2

def wBody (omegaL omegaR wheelBase : ℝ) : ℝ :=
  (omegaR - omegaL) / wheelBase

def limitDenom (omegaL omegaR limit : ℝ) : ℝ :=
  max 1 (max (|omegaL|) (|omegaR|) / limit)

theorem limitDenom_pos (omegaL omegaR limit : ℝ) (h : 0 < limit) :
    0 < limitDenom omegaL omegaR limit := by
  unfold limitDenom
  have h1 : 0 ≤ max (|omegaL|) (|omegaR|) / limit :=
    div_nonneg (le_trans (abs_nonneg omegaL) (le_max_left _ _)) (le_of_lt h)
  have h2 : 1 ≤ max 1 (max (|omegaL|) (|omegaR|) / limit) := le_max_left _ _
  linarith

theorem limited_zero (limit : ℝ) (h : 0 < limit) :
    (0 / limitDenom 0 0 limit) = 0 := by
  simp

theorem limited_ratio (omegaL omegaR limit : ℝ) (hr : omegaR ≠ 0) (h : 0 < limit) :
    (omegaL / limitDenom omegaL omegaR limit) /
        (omegaR / limitDenom omegaL omegaR limit) = omegaL / omegaR := by
  have hd : limitDenom omegaL omegaR limit ≠ 0 := ne_of_gt (limitDenom_pos omegaL omegaR limit h)
  field_simp [hd]

theorem vBody_div (omegaL omegaR wheelRadius d : ℝ) (hd : d ≠ 0) :
    vBody (omegaL / d) (omegaR / d) wheelRadius = vBody omegaL omegaR wheelRadius / d := by
  unfold vBody
  field_simp [hd]

theorem wBody_div (omegaL omegaR wheelBase d : ℝ) (hd : d ≠ 0) :
    wBody (omegaL / d) (omegaR / d) wheelBase = wBody omegaL omegaR wheelBase / d := by
  unfold wBody
  field_simp [hd]

theorem body_ratio_div (omegaL omegaR wheelBase wheelRadius d : ℝ)
    (hd : d ≠ 0) (hw : wBody omegaL omegaR wheelBase ≠ 0) :
    vBody (omegaL / d) (omegaR / d) wheelRadius /
        wBody (omegaL / d) (omegaR / d) wheelBase =
      vBody omegaL omegaR wheelRadius / wBody omegaL omegaR wheelBase := by
  rw [vBody_div omegaL omegaR wheelRadius d hd,
      wBody_div omegaL omegaR wheelBase d hd]
  field_simp [hd, hw]

def rowRotX (theta x y : ℝ) : ℝ := x * Real.cos theta + y * Real.sin theta

theorem row_rotation_wrong_at_ninety :
    rowRotX (Real.pi / 2) 0 1 = 1 ∧ rotX (Real.pi / 2) 0 1 = -1 := by
  unfold rowRotX rotX
  simp [Real.cos_pi_div_two, Real.sin_pi_div_two]

theorem nonsquare_corner_rot90 (L W : ℝ) :
    rotX (Real.pi / 2) L W = -W ∧ rotY (Real.pi / 2) L W = L := by
  unfold rotX rotY
  simp [Real.cos_pi_div_two, Real.sin_pi_div_two]

end T
