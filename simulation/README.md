# Free headless supplementary simulation

Run `python -m unittest discover -s simulation -p test_simulation.py -v`, then
`python simulation/simulate.py --output output/surrogate`. Requires only Python
3.10+ standard library. Output is four CSV traces, four SVG equal-scale trajectory
plots and metrics.json. No API key, GUI, paid simulator or scientific package is
required. Optional `--slip 0.02` reduces actual translation by 2% while wheel
encoder odometry continues integrating measured wheel rotations.

The model uses midpoint differential-drive integration, a rectangular footprint,
solid wall polygons, ideal front and dual left ray sensors, common wheel limiting,
feedback goal reaching, approach/stop and left-wall following around a joined
inside corner at 0.08 and 0.14 m/s. Policy inputs are odometry and proximity only;
the ground-truth pose is used by the simulator to generate observations and by
evaluation to measure clearance/contact. No ground-truth pose enters Policy.step.

The fixture dimensions are declared approximations, not calibrated Pioneer
measurements. Wheel actuation is instantaneous, slip defaults to zero, sensors
have no volume or noise, and contact evaluation checks polygons at sampled poses.
The stationary corner-turn gate uses a conservative swept-circle bound assuming
the sensed walls are aligned with the current rays. There is no general swept
collision detector between moving samples and no rigid-body dynamics.

The regression tests exercise CCW rotation, polygon crossing/containment,
no-detection, common wheel limits, midpoint encoder integration, final front
protection, lost-wall timeout and the [-pi,pi) endpoint. Four explicit incorrect
mutants are rejected: reversed rotation, overwritten front protection, frozen
lost timer and atan2's +pi endpoint. These tests do not constitute a proof that
every possible source-level mutation is detected.

Baseline locally executed results (re-run results take precedence): all four cases
complete and hold zero commands for one second without sampled geometric contact.
Goal error is 0.03989 m and 2.705 degrees. Approach final clearance is 0.20181 m.
The corner runs progress ~2.12 m before turning and ~1.18 m parallel to the second
wall. The second-wall distance transient is large: final clearance ~0.43 m versus
the 0.30 m target; this limitation is retained in the traces and statistics rather
than called successful accurate wall tracking. Zero baseline odometry error is a
consequence of the ideal no-slip shared kinematics, not a real calibration result.

**Assignment compliance:** the actual assignment explicitly requires MATLAB for
control/sensing/odometry/logging, CoppeliaSim for simulation, three saved scenes and
a real simulation video. These supplementary surrogate results cannot satisfy
those deliverables unless the instructor authorizes a platform change. Preserve
and finish the actual MATLAB/CoppeliaSim track separately.

reference_checks.m can run in GNU Octave or MATLAB to cross-check a small numerical
subset of the equations. Octave execution has not been performed locally unless
a corresponding CI log is present. It is not an Octave/CoppeliaSim adapter.
