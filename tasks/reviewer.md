# Independent evidence reviewer

Own review/. Initial workers have finished or stopped; inspect actual artifacts.
Read their handoff files, compiler logs, simulation CSV/metrics and research notes.
Use shell to inspect output/run-summary if available or output/*-result.json when
read_file does not permit the coordinator's output/ directory. Never read credentials.
Source exists != run passed. Agent final text != independent acceptance.

Independently rerun simulation unit tests and experiments with outputs written to
review/rerun (not another worker's owned directory). Check source controller inputs,
front priority in every state, timer accumulation, wrap endpoints, footprint CCW
rotation/intersection and turning footprint. Independently recompute selected CSV
metrics and contiguous1s zero holds. Test mutation detection for known defects.
Inspect Lean theorem strength, compiler/axioms logs, the exact wrap convention,
and gaps between Lean math and floating controller. You may invoke Lean source
checks from read-only lean/ but build output must go under review/ or use existing
compiled environment; report write/sandbox limits accurately instead of faking pass.

Create review/requirements.json with passed/failed/untested per PROJECT_BRIEF item,
evidence path, scope (mathematical/implementation test/surrogate/local-required).
Create review/REVIEW.md with prioritized concrete bugs, independent results and
what prevents final assignment completion. Do not edit others' files or claim this
supplemental cloud project alone satisfies mandatory MATLAB/Coppelia deliverables.
Send a precise handoff for the writer. Do not approve unexecuted tests or pretend
simulated encoders establish real sensor noise/latency assumptions.
