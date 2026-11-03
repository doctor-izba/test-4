# DeepSeek cloud team harness

This is a small auditable Python harness for the explicitly authorized Nube run,
not Pi. It implements the requested multi-agent workflow directly rather than
pretending Pi core has a built-in team scheduler. It uses only Python's standard
library. No model/provider substitution is allowed.

Run on Linux with bubblewrap, a preinstalled pinned Lean toolchain/mathlib cache,
and the dependencies required by the simulation task:

```
python3 harness/run.py --root . --budget 3.70 --minutes 100 --steps 35 --reasoning high
```

Supply `NUBE_API_KEY` through a GitHub Actions secret. Never pass it on the command
line or write it to the repository. The parent workflow must enforce a one-shot
repository-wide spending claim: this harness's ledger controls one run, not all
possible future workflow dispatches. Reruns require reconciliation/authorization.

1. Before spending, test the Linux bubblewrap sandbox.
2. Preflight two-turn tool calling with actual API usage and reasoning history.
3. Research, Lean and simulation workers run in parallel with separate writable
   directories; reviewer then writer run against their completed artifacts.
4. Save sanitized provider requests, tool results, per-role status and a usage
   ledger under `output/`. GitHub logs show concise live events.

Prompts are read from `tasks/PROJECT_BRIEF.md` and `tasks/<role>.md`. Roles own
`research/`, `lean/`, `simulation/`, `review/` and `reports/`, respectively. All
shell tools have read-only OS/repository views, a role-owned writable subtree,
private `/tmp` and PID namespace, and no network. `fetch_url` is a broker for
public unauthenticated HTTPS files, validates redirect destinations and rejects
private network addresses. Installed Lean/toolchains are available read-only;
workers cannot install dependencies over the shell network. Download source
files through `fetch_url`, then use installed PDF/text tools in the sandbox.

## Budget accounting

Prices are the user's stated Nube tariffs, not an independent provider billing
attestation: uncached input $0.135/M, cache-hit input $0.0027/M, all output
including reasoning $0.540/M. Before dispatch, reserve uncached input at one
token per serialized request byte plus 4096 framing tokens, and full declared
maximum output. Reservations and confirmed costs share a locked $3.70 ceiling.
Usage is settled from actual counters. Missing/invalid usage, transport failures
or an interrupted in-flight request retain reservations and halt further calls.
No automatic API retry is made. Prices/tax/provider billing changes are outside
what a local token ledger can guarantee; the $0.30 margin is not a billing API.

`reasoning_effort: high` is requested and the provider's `reasoning_content` is
preserved across tool turns. A successful response does not independently prove
that the provider honored high effort; requested and observed fields are saved.

`output/usage.json` contains `confirmed_usd`, `reserved_usd`, `reservations`,
`stop_reason` and per-call counters. These describe tokens/cost, not correctness.
`finished` means an agent stopped normally; independent theorem/experiment
acceptance still requires compiler/checker outputs and reviewer evidence.

## Offline verification

```
python3 -m unittest discover -s harness -p 'test_*.py' -v
```

Tests cover concurrent reservations, unknown usage, interrupted-run fail-closed,
cache/output arithmetic, path ownership, environment stripping, sandbox refusal,
private-address fetch refusal, multi-turn reasoning preservation, failed-call
reservations and log secret redaction. They spend no API tokens. Actual Linux
sandbox isolation and actual Nube compatibility are checked in the cloud job
before the workers are dispatched.
