import Assignment4Verification

open Assignment4

def ratAbs (q : Rat) : Rat := if q < 0 then -q else q
def ratLimitDenom (l r limit : Rat) : Rat := max 1 (max (ratAbs l) (ratAbs r) / limit)
def ratFrontGate (reading : Option Rat) (brake v : Rat) : Rat :=
  match reading with
  | none => 0
  | some d => if d ≤ brake then min v 0 else v
def ratLostTimer (detected : Bool) (elapsed dt : Rat) : Rat :=
  if detected then 0 else elapsed + max 0 dt

def showQ (q : Rat) : String := s!"{q.num}/{q.den}"

def main : IO Unit := do
  IO.println s!"gate_none={showQ (ratFrontGate none (12/100) (1/2))}"
  IO.println s!"gate_low={showQ (ratFrontGate (some (1/10)) (12/100) (1/2))}"
  IO.println s!"gate_high={showQ (ratFrontGate (some (1/5)) (12/100) (1/2))}"
  IO.println s!"limit={showQ (ratLimitDenom (3/2) (-9/2) 6)}"
  IO.println s!"timer={showQ (ratLostTimer false (1/2) (1/20))}"
