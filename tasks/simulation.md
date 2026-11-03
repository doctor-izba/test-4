# Free simulation and controller worker

Own simulation/. Read actual code, tests, README, ALTERNATIVES and current results.
The existing ideal2D baseline has useful runs but poor second-wall tracking (~0.43m
for desired0.30m). Investigate and improve this if possible, retaining baseline and
failed results. Do not blindly replace well-tested geometry/encoder code.
All work must be reproducible with Python in this free runner. Octave is installed;
execute the optional reference_checks.m and record its actual result.

Run unit/regression/mutation tests and all four surrogate cases. Compare two forward
speeds with frozen geometry/start/gains/thresholds. Use correct evaluation footprint
distance with crossing/containment; detect collisions rather than hardcode zero.
Ground truth may only feed evaluation and simulated sensor generation, never the
controller/odometry state. Demonstrate this dependency boundary through testing.
If changing controllers, regenerate CSV/metrics/trajectory SVGs; preserve failures.
Add perturbation/lost-detection and turning-clearance cases as supplemental evidence.
Make plotting artifacts with matplotlib if helpful, but prioritize meaningful checks.

Create simulation/cloud_results.md with exact commands, measured results, gain
choices, state transitions, important negative tests, limitations. Export selected
PNG plots so report author can embed them. Avoid claims about real Pioneer dynamics
or assignment-compliant MATLAB/Coppelia runs. Prepare executable reusable control
equations/adapter plan for those required local tools, without fabricating scenes.
