# test-4: evidence-driven robotics agents

This public workspace runs DeepSeek research, Lean, simulation, review and report
agents on standard GitHub Actions Linux runners. It is a working research project,
not a claim that an assignment or its proofs have already passed.

## Work performed

1. Research agent: acquire accessible primary sources, make cited engineering decisions.
2. Lean agent: repair and extend actual compiling proofs, document their exact scope.
3. Simulation agent: run a free headless Python differential-drive test bench.
4. Reviewer: independently inspect the first three contributions and measured failures.
5. Writer: author the complete report and explanation, using actual accepted evidence.

DeepSeek-V4.1-Flash is accessed through the user's Nube API. Model inference is
paid, with a conservative single-authorized-run budget of USD 3.70, below the user's
USD 4 ceiling. GitHub-hosted standard compute in this public repository is free;
no GPU, paid runner, external VM, or paid simulator is requested. API pricing is
user-supplied: USD 0.135/M uncached input, 0.0027/M cached input, 0.540/M output.
Usage accounting and uncertainty must be reported. This does not promise unlimited
work or that all requirements can be satisfied before the budget/time limits.

## Run and progress

Use the **Cloud robotics team** workflow under Actions. It has no automatic or
scheduled trigger. A repository-level one-shot budget claim prevents another paid
run from starting silently, including reruns of a used authorization. The secret
`NUBE_API_KEY` is stored in Actions Secrets, never in this repository or agent chats.
The budget and sandbox tests execute before inference. Worker progress appears in
the live Actions log; outputs and diagnostics are collected even when a worker fails.

The first three agents own distinct directories. Their commands run in a Linux
bubblewrap sandbox with a sanitized environment and no network. Research downloads
go through a separate URL-fetch tool. Only the trusted coordinator talks to Nube.
The runner's GitHub publishing credential is supplied only to trusted workflow steps.

### Telegram progress (optional)

The separate **Telegram progress monitor** workflow reads an existing Actions run
and edits one Telegram message on actual stage changes/completion. No VPS, webhook,
paid model or persistent local process is needed. It uses `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` stored only as Actions Secrets. A local masked setup dialog binds
the private chat using a unique START link, then installs the secrets and dispatches
the monitor. Do not paste the token into issues, commits, logs or public chat.

For the current research run, the monitor sees workflow stages, not each worker's
internal live messages. Detailed live worker actions remain in the Actions log.
Final per-worker states and token cost are included when the evidence branch exists.
The monitor does not restart/cancel agents or bypass the repository budget guard.

## What the free simulator means

`simulation/` is a deterministic, simplified 2D model for controller development,
geometry, threshold, state-machine and regression testing. Its traces are labelled
surrogate results. They are not CoppeliaSim dynamics or proof of MATLAB equivalence.
The original assignment explicitly requires MATLAB control and CoppeliaSim scenes,
logs and video. Those final canonical experiments remain local unless the instructor
accepts an alternative. GNU Octave/Webots alternatives are investigated separately.

Lean proves stated mathematical properties. A compiling theorem does not by itself
verify MATLAB floating-point code, unmodelled physics, sensors or collision coverage.
The report must distinguish proofs, differential tests, trace checks and simulation.

## Sources and provenance

Initial public scaffolding was prepared by Codex. Paid cloud worker contributions
are separately identified in run logs; they must not be misattributed to DeepSeek
before those workers actually execute. Only original engineering notes, code and
results are published. Private course PDFs, subscription text, API keys, `.lake`
caches and original third-party books are excluded from published artifacts.

See `tasks/PROJECT_BRIEF.md` for the engineering contract. The existing Lean baseline
contained compiler errors; cloud work must repair and compile it, not label it verified.
