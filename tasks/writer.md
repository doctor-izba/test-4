# Full report and defense-guide author

Own reports/. Read PROJECT_BRIEF, research notes, Lean README/logs, actual simulation
metrics/plots/cloud_results and independent review. Write the whole substantive report,
not an outline. The trusted workflow will render reports/report.md into PDF afterward.
You can run cloud/render_report.py yourself after authoring it. Use English for report,
Russian or English for a short defense guide as appropriate. Original clear prose.

Reports/report.md must contain: goal/scope and compliance limits; notation/units;
robot model and wheel/body derivations; midpoint measured-encoder odometry; goal
controller gains/state transitions/hold; proximity geometry/valid detection/thresholds;
inside corner wall geometry and footprint/collision/turn checks; state diagram and
hysteresis/reacquisition; two-speed controlled comparison; exact executed results
tables, trajectories and error/sensor/command plots if available; meaningful Lean
theorems and actual build/axiom results; correspondence and physics limitations;
independent review failures and remaining work; reuse/source attribution; exact
reproduction commands and software versions. State plots missing if none exist.
Use actual values from CSV/JSON and cite evidence paths; no invented measurements.
Copy selected PNG figures into reports/figures/ for relative embedding. Real source
reference links and actual sections, no long copyrighted passages or full sourcebooks.

Explain clearly that the cloud2D simulator is supplementary; the required local
MATLAB+CoppeliaSim scenes/data/video are not produced by this cloud run. Distinguish
proved math, tested code correspondence, checked traces and empirical simulator
behavior. Never title it a fully verified completed submission if review finds gaps.
Write reports/REPRODUCE.md and reports/DEFENSE_GUIDE.md (what each equation/state
does, why chosen, how to explain error sources and formal guarantees). Keep honest
remaining_work checklist so the local experiment worker can finish the assignment.
