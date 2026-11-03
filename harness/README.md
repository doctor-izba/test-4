# Durable DeepSeek cloud team

This is an auditable Python-standard-library harness, not Pi. Research, Lean and
simulation workers take parallel cooperative slices; reviewer and writer then
inspect real artifacts. New cycles repair findings and develop meaningful extra
checks. A worker saying `finished` does not end the team or certify the assignment.

```
python3 harness/run.py --root . --budget 3.23 --deadline-utc "$DEADLINE_UTC" \
  --steps 0 --slice-rounds 12 --max-output-tokens 393216 \
  --context-tokens 1048576 --reasoning max --retries 5 --work-until-deadline
```

The parent workflow sets an absolute deadline from actual job start, reserving
time for final evidence saving within GitHub's six-hour job limit. The budget
argument is the authorization for this run, after accounting for prior usage and
uncertain requests. It must not be copied blindly to a new paid run.

Supply `NUBE_API_KEY` as a GitHub Actions secret, never a command argument. The
parent supervisor supplies no GitHub/Telegram credentials to the worker. Worker
shells use bubblewrap: read-only OS/repository, role-owned writable subtree, private
PID and temporary namespaces, no network and a minimal environment. Public HTTPS
research downloads use a redirect-checked broker which rejects private addresses.

## Persistence and continuity

Prompts: `tasks/PROJECT_BRIEF.md` and each `tasks/<role>.md`. Owned directories:
`research/`, `lean/`, `simulation/`, `review/`, `reports/`.

Complete sanitized conversations and provider responses remain under `output/`.
`output/sessions/` checkpoints every response/tool boundary and keeps a full
journal. An interrupted running tool has an unknown outcome and is never blindly
replayed. Completed tool results and archived responses can be recovered without
executing tools or settling the same cost twice. A `output/STOP` file or SIGTERM
stops starting new work; already checkpointed uncertainty remains explicit.

There is no 40-step, 170-minute, 8K-output or 200KB-request ceiling. Twelve-turn
slices yield durable state, rather than failing the worker. Context is compacted
before the joint model input/output capacity using factual handoffs and persisted
files; oversized old response blocks are removed from active context while the
complete journal remains. Shell defaults to 900 seconds and can be given a longer
timeout up to the remaining job deadline. Stdout goes directly to owned log files;
only a tail enters model context.

## Streaming and retries

The cheap preflight first tries SSE with `stream_options.include_usage=true`. If
the provider rejects SSE with HTTP 502/400, transport switches to compatible JSON
for the rest of the run, and this decision persists across worker restarts.
Actual Nube probes observed SSE failures while JSON worked; SSE support must not
be presented as verified. The SSE parser
reconstructs fragmented content, reasoning, indexed function names/arguments and
final usage chunks, including empty `choices` usage chunks. Stream progress is
reported periodically without dumping reasoning into console logs.

All HTTP 5xx (including Cloudflare 520–527), 408, 409, 425, 429 and transport
interruptions retry with capped exponential backoff. A retry batch exhausting its
allowance pauses that role for the next coordinator cycle, rather than globally
ending the run. 401/402/403 and other definitive failures halt paid requests.
Interrupted SSE/malformed partial data is a transport failure. An explicitly
completed response lacking valid final usage halts accounting conservatively.

Ordinary requests use the configured 393216 output ceiling and requested `max`
reasoning effort. Only reconnection retries temporarily lower their output ceiling
to 65536 so repeated uncertain connections do not each reserve another full 384K
output. JSON retries also request `high` instead of `max` effort. These are not
permanent restrictions of successful ordinary requests.
An API accepting a field does not independently attest how much effort it used.

## Cost accounting

User-supplied tariffs: uncached input $0.135/M, cached input $0.0027/M, output
including reasoning $0.540/M. Before each attempt a locked ledger reserves one
uncached input token per serialized request byte plus framing allowance, and the
entire declared output ceiling. Remaining money and joint context can reduce a
request's maximum output. Actual reported usage settles successful responses.

Failed/unknown requests retain pessimistic reservations across retries/restarts.
They do not silently disappear or get counted as free. Missing/invalid final usage
halts further calls. `output/usage.json` records `confirmed_usd`, `reserved_usd`,
reservation states, per-call counters and any stop reason. Provider pricing/tax
changes are outside a token ledger; the parent must enforce authorization across
all separate runs as well as this run's ledger.

## Offline tests

```
python3 -m unittest discover -s harness -p 'test_*.py' -v
```

Tests spend no API tokens. They cover concurrent reservations, unknown usage,
restart uncertainty, cache arithmetic, path ownership, environment isolation,
required sandbox, private-address refusal, tool-loop reasoning preservation,
secret redaction, 401 fatal handling, 429/500/524 recovery, retry ceilings,
fragmented SSE multi-tools/reasoning/final usage, large contexts, length
continuation, unknown-tool non-replay, repair cycles and non-livelocking compaction.
