# Lean verification worker

Own lean/. Read all current .lean files and README first. Codex may already have
repaired some baseline errors; inspect and compile before repeating work.
Use actual lake build and lake env lean AxiomAudit.lean with installed pinned
toolchain and predownloaded Mathlib cache. Shell cwd is lean/. Network is unavailable;
do not run lake update or redownload dependencies. Avoid importing all Mathlib.

Repair compiler errors, then make meaningful progress on PROJECT_BRIEF obligations:
all-state final front guard; saturation bounds/scaling/zero; timer advance/reset and
timeout fallback; CCW inverse transform; measured-wheel heading identity; correct
[-pi,pi) wrap and zero-command hold invariants. Prioritize actual complete proofs.
Keep theorem statements useful, state every assumption, no sorry/admit/axioms,
no weakening into tautologies. Generate AxiomAudit.lean listing public acceptance
theorems and retain actual compiler/axiom logs as lean/verification.log and
lean/axioms.log. Build source into the pinned package, don't only #check theorem names.

If feasible write a small executable rational/discrete reference checker for front
gate/timers/bounds and compare boundary vectors with simulation's actual functions.
Document exactly which properties remain mathematical, which correspond via tests,
and what is unproved about floats, sensors/delay/physics and MATLAB/CoppeliaSim.
Update lean/README.md and handoff with exact commands, exit statuses, failures.
The baseline's existing passing declarations are starting material, not evidence
that the whole robotics assignment has been formally verified.
