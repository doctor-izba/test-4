# Lean controller contracts

This directory contains a repaired and expanded baseline of the earlier
mathematical verification project. Lean/mathlib are pinned to 4.34.0. Compilation
status is recorded in local-verification.json when a local check is run; a source
file alone is not evidence that a proof passed.

The public theorems cover differential-drive inverse kinematics, common scaling,
sensor clearance algebra, heading wrapping with exactly the [-pi,pi) convention,
CCW rotation orientation and squared norms, final command protection in every
controller state, invalid/turn permission fallback, lost-wall timer progress, and
both wheel bounds after common-denominator limiting.

The crucial controller contract is `step = protect(policy(state))`: for every
state and every proposed policy, a front distance at/below the braking threshold
prevents positive final forward velocity. This is a command-level property. It is
not a collision-free physical theorem; a real robot also needs coverage, delay,
actuation and stopping-distance assumptions.

The real-valued definitions are mathematical contracts, not verified IEEE-754
MATLAB/Python implementations. Cross-language differential tests must connect
runtime code to them. No ground-truth pose occurs in the pure policy inputs, but
that does not certify that a separate implementation never reads ground truth.
There are no assumptions of MATLAB correctness or simulator fidelity hidden in
the theorem statements.

## Run

From this directory run `lake exe cache get`, `lake build`, and
`lake env lean AxiomAudit.lean`. The final command prints actual dependencies of
every public theorem. Standard mathematical axioms such as `propext`,
`Classical.choice` and `Quot.sound` are reported, rather than claiming no axioms.
There are no `sorry`, `admit`, custom axioms or `native_decide` proof shortcuts.

The cloud workflow may additionally use Lean's compiled-environment checker and
the official axiom-audit action. Final acceptance must include those real logs
and agreement with the simulation/controller tests.
