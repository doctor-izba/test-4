"""Durable, deadline-driven DeepSeek team with constructive repair cycles."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import ctypes
import hashlib
import json
import os
import signal
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

from budget import Budget, BudgetStopped
from tools import Tools, SCHEMAS
from sessions import Session, atomic_json

MODEL = "DeepSeek-V4.1-Flash"
ROLES = {"research": "research", "lean": "lean", "simulation": "simulation", "reviewer": "review", "writer": "reports"}
BASE_INSTRUCTIONS = """You are a DeepSeek worker producing a real robotics solution, not just discussing it.
Work from existing artifacts and fix concrete failures. Do not repeatedly reread the
same files. Within your first eight tools write a useful partial artifact (notes,
proof changes, tests, review, or report), then improve it. Save useful files and a
handoff frequently; a long thought process without files is not progress.
No invented measurements, compiler passes, sources or citations. No sorry/admit,
custom axioms, or weakened theorem statements to disguise missing proofs. Preserve
the assignment requirements and label what a substitute simulation does not prove.
Read tasks/PROJECT_BRIEF.md and your own task. Write only your owned directory.
The shell cwd is that directory; file-tool paths are relative to repository root.
Shell has a read-only repository/OS, writable own subtree, private PID/tmp namespaces,
and no network. Dependencies/toolchains are preinstalled. Use fetch_url for lawful
public HTTPS resources; no access-control/paywall bypass, credentials, environment/
process inspection, privilege escalation, other agent/API processes or harness edits.
Requested output/reasoning capacity is a maximum, not a reason to dump huge text.
Prefer actual files, targeted compiler/tests and precise cited research notes.
Work proceeds in checkpointed slices: yielding is not failure. Later cycles return
with review findings, and you must repair them rather than simply saying done.
When you finish a turn, state changed files, exact checks, failures and next actions.
Tool calls marked interrupted/unknown WILL NOT be replayed: inspect files/logs first.
"""


class DeadlineReached(RuntimeError):
    pass


class RetryExhausted(RuntimeError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Events:
    def __init__(self, output, redact):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.redact = redact
        self.lock = threading.RLock()
        try:
            self.states = json.loads((self.output / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.states = {}

    def emit(self, role, event, **details):
        with self.lock:
            record = {"time": timestamp(), "role": role, "event": event, **details}
            serialized = self.redact(json.dumps(record, ensure_ascii=False))
            with (self.output / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
            self.states[role] = json.loads(serialized)
            atomic_json(self.output / "status.json", self.states, self.redact)
            print(self.redact(f"[{record['time']}] {role}: {event} {details.get('summary', '')}"), flush=True)


def response_message(data):
    if str(data.get("model", "")).lower() != MODEL.lower():
        raise ValueError("Unexpected response model; substitution is forbidden")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Provider returned no choices")
    message = choices[0].get("message", {})
    if message.get("role") != "assistant":
        raise ValueError("Invalid assistant response")
    for call in message.get("tool_calls") or []:
        if not isinstance(call.get("id"), str) or not isinstance(call.get("function"), dict):
            raise ValueError("Invalid provider tool-call structure")
    return {key: message[key] for key in ("role", "content", "tool_calls", "reasoning_content") if key in message}, choices[0].get("finish_reason")


class Client:
    def __init__(self, secret, budget, output, events, deadline, thinking="max", transport=None,
                 max_output_tokens=393216, context_tokens=1048576, retries=5, retry_base=2, sleep=time.sleep):
        self.secret, self.budget, self.output, self.events = secret, budget, Path(output), events
        self.deadline, self.thinking = deadline, thinking
        self.max_output_tokens = int(max_output_tokens)
        self.context_tokens = int(context_tokens)
        if not 1 <= self.max_output_tokens < self.context_tokens:
            raise ValueError("Output limit must be positive and below total model context")
        self.retries, self.retry_base, self.sleep = max(0, int(retries)), max(0, float(retry_base)), sleep
        self.transport = transport or self.request
        self.local = threading.local()
        self.reconcile_archives()

    def remaining(self):
        if (self.output / "STOP").exists():
            self.deadline = min(self.deadline, time.monotonic())
            raise DeadlineReached("Operator STOP marker received")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise DeadlineReached("Absolute job deadline reached")
        return remaining

    def request(self, payload):
        request = urllib.request.Request("https://ai.nube-api.com/v1/chat/completions", data=payload,
            headers={"Authorization": "Bearer " + self.secret, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        # Long reasoning is allowed to use the remaining authorized job time.
        with urllib.request.urlopen(request, timeout=self.remaining()) as response:
            return json.load(response)

    def reconcile_archives(self):
        for call_id in list(self.budget.reservations):
            path = self.output / (call_id + ".json")
            if not path.exists():
                continue
            try:
                archive = json.loads(path.read_text(encoding="utf-8"))
                if "response" in archive:
                    self.budget.settle(call_id, archive["response"].get("usage"), archive["input_bound"], archive["max_output_tokens"])
            except BudgetStopped:
                raise
            except (ValueError, KeyError, TypeError):
                self.budget.stop("Invalid archived response during restart reconciliation")
                raise BudgetStopped(self.budget.reason)

    def recover_session(self, session):
        call_id = session.data.get("pending_request")
        if call_id:
            path = self.output / (call_id + ".json")
            if path.exists():
                archive = json.loads(path.read_text(encoding="utf-8"))
                if "response" in archive:
                    message, finish = response_message(archive["response"])
                    session.response(message, call_id, finish)
            if session.data.get("pending_request"):
                session.data["pending_request"] = None
                session.data["state"] = "request_interrupted"
                session.record("request_interrupted", call_id=call_id,
                    instruction="Provider outcome unknown. Full reservation retained; no tools from an unconfirmed response are executed.")
                session.flush()
        session.recover_tools()

    def chat(self, role, messages, max_tokens=None, tool_choice=None, session=None):
        desired = int(max_tokens if max_tokens is not None else self.max_output_tokens)
        desired = min(desired, self.max_output_tokens)
        for attempt in range(self.retries + 1):
            self.remaining()
            payload = {"model": MODEL, "messages": messages, "tools": SCHEMAS, "max_tokens": desired, "stream": False}
            if self.thinking != "off":
                payload["reasoning_effort"] = self.thinking
            if tool_choice:
                payload["tool_choice"] = tool_choice
            initial_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            input_bound = initial_bytes + 4096
            output_room = self.context_tokens - input_bound
            if output_room < 1:
                raise ValueError("Conservative input bound exceeds model context; compact session before dispatch")
            # Financial/context bounds are real constraints. Adapt output to the
            # remaining shared budget, rather than imposing an unrelated 8K cap.
            while True:
                self.remaining()
                with self.budget.lock:
                    if self.budget.reason:
                        raise BudgetStopped(self.budget.reason)
                    available = self.budget.available()
                    money_output = int((available * Decimal(1_000_000) - Decimal(input_bound) * Decimal(".135")) / Decimal(".540"))
                    allowed = min(desired, output_room, money_output)
                    if allowed >= 1:
                        payload["max_tokens"] = allowed
                        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                        call_id = role + "-" + uuid.uuid4().hex[:12]
                        try:
                            input_bound = self.budget.reserve(call_id, len(encoded), allowed)
                            break
                        except BudgetStopped:
                            if self.budget.reason:
                                raise
                    active = self.budget.active_count()
                    if active == 0:
                        self.budget.stop("Run budget cannot cover another pessimistically reserved request")
                        raise BudgetStopped(self.budget.reason)
                self.sleep(min(.25, self.remaining()))
            if session:
                session.request_started(call_id)
            self.events.emit(role, "request", call_id=call_id, attempt=attempt + 1,
                request_bytes=len(encoded), input_bound=input_bound, max_output_tokens=allowed, requested_reasoning=self.thinking)
            try:
                data = self.transport(encoded)
            except Exception as error:
                code = error.code if isinstance(error, urllib.error.HTTPError) else None
                transient = (code in {429, 500, 502, 503, 504}) if code is not None else isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError))
                cause = f"HTTP {code}" if code is not None else type(error).__name__
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                self.budget.uncertain(call_id, cause, halt=not transient)
                atomic_json(self.output / (call_id + ".json"), {"call_id": call_id, "state": "uncertain", "cause": cause,
                    "input_bound": input_bound, "max_output_tokens": allowed}, self.events.redact)
                if session:
                    session.data["pending_request"] = None
                    session.flush()
                self.events.emit(role, "request_retry" if transient else "request_fatal", call_id=call_id, summary=cause,
                    reservation_retained=True, attempt=attempt + 1)
                if not transient:
                    raise BudgetStopped("Provider refused request: " + cause) from None
                if attempt >= self.retries:
                    raise RetryExhausted("Transient retry allowance exhausted; all uncertain reservations retained") from None
                delay = min(60, self.retry_base * (2 ** attempt), self.remaining())
                self.sleep(delay)
                continue
            # Persist the response before accounting/session transitions so restart
            # can settle and recover it without repeating provider calls or tools.
            archive = {"call_id": call_id, "request": payload, "response": data,
                       "input_bound": input_bound, "max_output_tokens": allowed}
            atomic_json(self.output / (call_id + ".json"), archive, self.events.redact)
            self.budget.settle(call_id, data.get("usage") if isinstance(data, dict) else None, input_bound, allowed)
            try:
                message, finish = response_message(data)
            except (TypeError, ValueError) as error:
                self.budget.stop(type(error).__name__ + ": invalid provider response/model")
                raise BudgetStopped(self.budget.reason) from None
            self.local.last_call_id, self.local.finish_reason = call_id, finish
            if session:
                session.response(message, call_id, finish)
            self.events.emit(role, "response", call_id=call_id, usage=data["usage"], finish_reason=finish)
            return message
        raise RetryExhausted("No provider attempt completed")


def task_text(root, role):
    parts = []
    for name in ["PROJECT_BRIEF", role]:
        path = root / "tasks" / (name + ".md")
        if path.exists():
            parts.append(f"\n## tasks/{name}.md\n" + path.read_text(encoding="utf-8"))
    return "\n".join(parts) or "Inspect existing work, perform your named role, and save useful artifacts and honest checks."


def owned_files(root, owned):
    base = root / owned
    result = []
    for directory, dirs, names in os.walk(base):
        dirs[:] = [name for name in dirs if name not in {".lake", ".home", ".tool-logs", "__pycache__", ".git"}]
        for name in names:
            path = Path(directory) / name
            try:
                stat = path.stat()
                result.append({"path": path.relative_to(root).as_posix(), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
            except OSError:
                continue
    return sorted(result, key=lambda item: item["path"])


def compact_if_needed(client, session, root, owned):
    estimate = len(json.dumps({"messages": session.messages, "tools": SCHEMAS}, ensure_ascii=False).encode()) + 4096
    input_capacity = client.context_tokens - client.max_output_tokens
    if estimate <= max(1, int(input_capacity * .70)):
        return
    handoff_path = root / owned / "handoff.md"
    handoff = handoff_path.read_text(encoding="utf-8", errors="replace") if handoff_path.exists() else "No authored handoff exists yet. Inspect existing files, then write one before more exploration."
    handoff_budget = max(512, min(64000, input_capacity // 8))
    if len(handoff.encode()) > handoff_budget:
        handoff = handoff[:handoff_budget // 8] + "\n[Full authored handoff remains on disk; excerpt shortened for active context.]\n" + handoff[-handoff_budget // 8:]
    recent_tools = [message for message in session.messages if message.get("role") == "tool"][-12:]
    factual = {"instruction": "Active model context compacted before capacity; COMPLETE original conversation remains in the durable session journal. Continue from actual files and these tool results, not from a fresh reread of everything.",
        "owned_files": owned_files(root, owned), "authored_handoff": handoff,
        "recent_tool_results": [{"id": item.get("tool_call_id"), "result": item.get("content", "")[-3000:]} for item in recent_tools]}
    session.compact(json.dumps(factual, ensure_ascii=False))
    # A single long assistant/tool block can itself be larger than the remaining
    # input window. Do not retain that block forever and livelock on compaction.
    def active_bytes():
        return len(json.dumps({"messages": session.messages, "tools": SCHEMAS}, ensure_ascii=False).encode()) + 4096
    if active_bytes() > input_capacity * .70:
        session.data["messages"] = session.messages[:3]  # Initial task + factual checkpoint; entire tail stays in journal.
        session.record("compaction_dropped_large_tail", messages=session.messages)
        session.flush()
    if active_bytes() > input_capacity * .70:
        session.data["messages"] = session.messages[:2] + [{"role": "user", "content":
            f"Continue from existing {owned}/ files and {owned}/handoff.md. Complete prior conversation is archived. Read targeted files and address review/REVIEW.md; do not repeat completed tools."}]
        session.record("compaction_minimal_context", messages=session.messages)
        session.flush()
    if active_bytes() > input_capacity:
        client.budget.stop("Fixed task prompt exceeds configured model input capacity even after full tail compaction")
        raise BudgetStopped(client.budget.reason)
    client.events.emit(session.role, "context_compacted", summary=f"Conservative input estimate {estimate}; model total context {client.context_tokens}")


def process_pending(session, tools, events, deadline, slice_deadline=None):
    if not session.data.get("pending_tools"):
        return True
    for tool in session.data.get("pending_tools", []):
        if tool["state"] in {"completed", "unknown"}:
            session.append_tool_result(tool)
            continue
        if (events.output / "STOP").exists():
            raise DeadlineReached("Operator STOP marker received before next tool")
        if time.monotonic() >= deadline:
            raise DeadlineReached("Job deadline reached before next tool")
        if slice_deadline is not None and time.monotonic() >= slice_deadline:
            return False
        session.tool_started(tool)
        function = tool.get("function", {})
        name = function.get("name", "")
        try:
            args = json.loads(function.get("arguments", "{}"))
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be an object")
            result = tools.call(name, args)
        except (ValueError, TypeError):
            result = json.dumps({"error": "Invalid/incomplete JSON tool arguments. No tool was run; request this tool again with complete JSON."})
        session.tool_finished(tool, result)
        events.emit(session.role, "tool", name=name, summary=result[:200], result=result)
    session.data["pending_tools"] = []
    session.data["state"] = "ready"
    session.flush()
    return True


def run_loop(client, role, tools, messages, events, max_steps=0, preflight=False, session=None, slice_deadline=None):
    if session is None:
        session = Session(client.output / "sessions", role, messages, events.redact)
    client.recover_session(session)
    start_tools = session.data["tool_count"]
    initial_fingerprint = owned_files(tools.root, tools.owned.relative_to(tools.root).as_posix())
    rounds = 0
    while max_steps == 0 or rounds < max_steps:
        client.remaining()
        if not process_pending(session, tools, events, client.deadline, slice_deadline):
            break
        if slice_deadline is not None and time.monotonic() >= slice_deadline:
            break
        finish = session.data.get("last_finish_reason")
        if finish == "length":
            session.add({"role": "user", "content": "The previous response hit its allowed output/context limit. Continue from the saved files and completed tools; split the next edit into complete smaller tool arguments. Do not repeat completed non-idempotent tools. Produce useful artifacts rather than restating the plan."})
            session.data["last_finish_reason"] = None
            session.flush()
        elif session.messages[-1].get("role") == "assistant" and not session.messages[-1].get("tool_calls"):
            final_text = session.messages[-1].get("content") or ""
            events.emit(role, "turn_finished", summary=final_text[:300], rounds=rounds, total_turns=session.data["model_turns"])
            return {"state": "finished", "steps": rounds, "tool_calls": session.data["tool_count"], "final_text": final_text}
        if not preflight:
            compact_if_needed(client, session, tools.root, tools.owned.relative_to(tools.root).as_posix())
            if session.data["tool_count"] - start_tools >= 8 and owned_files(tools.root, tools.owned.relative_to(tools.root).as_posix()) == initial_fingerprint:
                session.add({"role": "user", "content": "Supervisor correction: at least eight tools have produced no changed owned artifact. Stop rereading. Write a useful partial notes/proof/test/review/report file now with exact evidence and remaining problems, then address the highest-priority concrete failure."})
                start_tools = session.data["tool_count"]
        choice = {"type": "function", "function": {"name": "read_file"}} if preflight and rounds == 0 and session.data["model_turns"] == 0 else None
        client.chat(role, session.messages, max_tokens=1024 if preflight else None, tool_choice=choice, session=session)
        rounds += 1
        # Persist and execute complete tool calls even on the last slice round;
        # if the time slice expires they remain pending for exact-once resume.
        if not process_pending(session, tools, events, client.deadline, slice_deadline):
            break
        if not session.data.get("pending_tools") and session.data.get("last_finish_reason") != "length":
            last = session.messages[-1]
            if last.get("role") == "assistant" and not last.get("tool_calls"):
                final_text = last.get("content") or ""
                session.data["state"] = "turn_finished"
                session.flush()
                events.emit(role, "turn_finished", summary=final_text[:300], rounds=rounds)
                return {"state": "finished", "steps": rounds, "tool_calls": session.data["tool_count"], "final_text": final_text}
    session.data["state"] = "yielded"
    session.flush()
    events.emit(role, "slice_yielded", rounds=rounds, summary="Durable checkpoint saved; continue in the next constructive cycle")
    return {"state": "yielded", "steps": rounds, "tool_calls": session.data["tool_count"] - start_tools, "final_text": ""}


def review_feedback(root):
    parts = []
    for name in ["next_tasks.json", "acceptance.json", "REVIEW.md", "review.md", "handoff.md"]:
        path = root / "review" / name
        if path.exists():
            parts.append(f"## review/{name}\n" + path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts) or "No independent review exists yet. Write useful first deliverables so reviewer/writer can inspect real work in this cycle."


def run_agent(root, role, client, events, slice_rounds=12, slice_minutes=8, cycle=1):
    events.emit(role, "started", owned_directory=ROLES[role], cycle=cycle)
    tools = Tools(root, ROLES[role], events.redact, require_sandbox=True, deadline=client.deadline)
    initial = [{"role": "system", "content": BASE_INSTRUCTIONS + "\nYour role: " + role + "; owned directory: " + ROLES[role]},
               {"role": "user", "content": task_text(root, role)}]
    session = Session(client.output / "sessions", role, initial, events.redact)
    client.recover_session(session)
    # A user follow-up can only appear after all tool-call results are appended.
    if not session.data.get("pending_tools"):
        session.add({"role": "user", "content": f"Constructive work cycle {cycle}. Continue existing artifacts; do not restart research or reread all files. Save a useful partial artifact within eight tools and update handoff. Address these actual independent review findings, or if none exist produce the missing required first deliverables:\n" + review_feedback(root)})
    try:
        result = run_loop(client, role, tools, session.messages, events, max_steps=slice_rounds,
            session=session, slice_deadline=min(client.deadline, time.monotonic() + slice_minutes * 60))
    except DeadlineReached as error:
        result = {"state": "deadline", "message": str(error)}
        events.emit(role, "deadline", summary=str(error))
    except RetryExhausted as error:
        result = {"state": "retry_paused", "message": str(error)}
        events.emit(role, "retry_paused", summary=str(error))
    except Exception as error:
        result = {"state": "stopped", "error_type": type(error).__name__, "message": events.redact(str(error))}
        events.emit(role, "stopped", summary=result["message"])
    result.update({"cycle": cycle, "session_turns": session.data["model_turns"], "session_tools": session.data["tool_count"]})
    atomic_json(client.output / (role + "-result.json"), result, events.redact)
    return result


def accepted_cloud_work(root):
    """A review signal is insufficient without referenced files and trusted checks.

    A parent supervisor can write output/trusted-acceptance.json only after its
    actual independent compiler/tests pass for the current source hashes. Model
    roles cannot write output through their file or shell tool write permissions.
    """
    path = root / "output/trusted-acceptance.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        if data.get("accepted") is not True or data.get("scope") != "cloud_work":
            return False
        required = {"lean_build", "lean_axioms", "simulation_tests", "research_notes", "report"}
        checks = data.get("checks", [])
        if not required.issubset({item["id"] for item in checks if item.get("passed") is True}):
            return False
        for relative, digest in data.get("source_sha256", {}).items():
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                return False
        return bool(data.get("source_sha256"))
    except (ValueError, KeyError, TypeError, OSError):
        return False


def coordinate(root, client, events, slice_rounds=12, slice_minutes=8, work_until_deadline=False, runner=run_agent, max_cycles=0):
    cycle = 0
    summary_path = client.output / "run-summary.json"
    if summary_path.exists():
        try:
            cycle = int(json.loads(summary_path.read_text()).get("cycle", 0))
        except (ValueError, TypeError):
            pass
    results = {}
    start_cycle = cycle
    while time.monotonic() < client.deadline and not client.budget.reason:
        cycle += 1
        events.emit("coordinator", "cycle_started", cycle=cycle, summary="Research/proof/simulation slice, then independent review and report")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(runner, root, role, client, events, slice_rounds, slice_minutes, cycle): role for role in ["research", "lean", "simulation"]}
            for future in as_completed(futures):
                role = futures[future]
                try:
                    results[role] = future.result()
                except Exception as error:
                    results[role] = {"state": "stopped", "error_type": type(error).__name__}
                    events.emit(role, "stopped", summary=type(error).__name__)
        for role in ["reviewer", "writer"]:
            if client.budget.reason or time.monotonic() >= client.deadline:
                results[role] = {"state": "skipped", "reason": "Global deadline/budget/auth stop"}
            else:
                results[role] = runner(root, role, client, events, slice_rounds, slice_minutes, cycle)
        summary = {"time": timestamp(), "version": 2, "cycle": cycle, "model": MODEL,
            "requested_reasoning": client.thinking, "max_output_tokens": client.max_output_tokens,
            "model_context_tokens": client.context_tokens, "roles": results,
            "state": "cycling", "note": "Finished/yielded refers to a worker turn, not accepted assignment completion. Read actual compiler/tests/review evidence."}
        atomic_json(summary_path, summary, events.redact)
        if not work_until_deadline and accepted_cloud_work(root):
            summary["state"] = "accepted_cloud_work"
            atomic_json(summary_path, summary, events.redact)
            events.emit("coordinator", "cloud_work_accepted", summary="Trusted independent checks and current source hashes match")
            return summary
        if max_cycles and cycle - start_cycle >= max_cycles:
            break
        # Never treat role 'finished' as overall completion: the next cycle repairs
        # findings and develops concrete additional checks/hypothesis tests.
        events.emit("coordinator", "repair_cycle_queued", cycle=cycle, summary="Continue concrete review backlog; no idle completion loop")
    state = "budget_or_auth_stopped" if client.budget.reason else ("deadline" if time.monotonic() >= client.deadline else "checkpointed")
    summary = {"time": timestamp(), "version": 2, "cycle": cycle, "model": MODEL, "roles": results,
               "state": state, "stop_reason": client.budget.reason, "note": "Saved artifacts remain reviewable; no unsupported claim that the assignment is complete."}
    atomic_json(summary_path, summary, events.redact)
    events.emit("coordinator", "run_checkpointed", summary=state)
    return summary


def parse_deadline(value, fallback_minutes):
    if value:
        target = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if target.tzinfo is None:
            raise ValueError("--deadline-utc must include Z or an explicit UTC offset")
        remaining = (target - datetime.now(timezone.utc)).total_seconds()
    else:
        remaining = fallback_minutes * 60
    return time.monotonic() + max(0, remaining)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--budget", default="3.52")
    parser.add_argument("--deadline-utc", help="Absolute ISO8601 deadline including Z; job start + 355 minutes is recommended")
    parser.add_argument("--minutes", type=float, default=355, help="Fallback only when no absolute deadline is provided")
    parser.add_argument("--steps", type=int, default=0, help="Compatibility option: 0 means unlimited total turns; no artificial turn-stop is imposed")
    parser.add_argument("--slice-rounds", type=int, default=12, help="Cooperative checkpoint/yield interval, not a failure limit")
    parser.add_argument("--slice-minutes", type=float, default=8, help="Yield between tools/requests for review/report fairness; does not kill running tools")
    parser.add_argument("--max-output-tokens", type=int, default=393216)
    parser.add_argument("--context-tokens", type=int, default=1048576)
    parser.add_argument("--reasoning", choices=["max", "high", "medium", "low", "off"], default="max")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-base", type=float, default=2)
    parser.add_argument("--work-until-deadline", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.steps < 0 or args.slice_rounds < 1 or args.slice_minutes <= 0:
        parser.error("Invalid turn/slice settings")
    root = Path(args.root).resolve()
    output = root / "output"
    output.mkdir(exist_ok=True)
    secret = os.environ.pop("NUBE_API_KEY", "")
    if not secret:
        parser.error("NUBE_API_KEY must be supplied through the GitHub secret")
    if sys.platform != "linux":
        parser.error("Production tools require Linux and bubblewrap")
    try:
        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)
    except Exception:
        pass
    for name in list(os.environ):
        if any(term in name.upper() for term in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
            os.environ.pop(name, None)
    redact = lambda value: str(value).replace(secret, "[REDACTED]")
    events = Events(output, redact)
    budget = Budget(output / "usage.json", args.budget)
    deadline = parse_deadline(args.deadline_utc, args.minutes)
    client = Client(secret, budget, output, events, deadline, args.reasoning,
        max_output_tokens=args.max_output_tokens, context_tokens=args.context_tokens,
        retries=args.retries, retry_base=args.retry_base)
    def shutdown(signum, frame):
        # Provider/tool boundaries are already durable; never replay running tools.
        client.deadline = min(client.deadline, time.monotonic())
        atomic_json(output / "shutdown.json", {"time": timestamp(), "signal": signum,
            "note": "Stop requested; session checkpoints are authoritative. Unknown running tools must not be replayed."})
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    probe = Tools(root, "review", redact, deadline=deadline).shell("printf SANDBOX_OK", timeout=10)
    if probe.get("exit_code") != 0 or "SANDBOX_OK" not in probe.get("output", ""):
        events.emit("coordinator", "sandbox_failed", summary=str(probe))
        return 2
    preflight_path = output / "preflight-passed.json"
    if not preflight_path.exists():
        initial = [{"role": "system", "content": "Test actual API tool calling: read_file on README.md, then reply exactly PREFLIGHT_OK. Do not write or shell."}, {"role": "user", "content": "Perform this tool test."}]
        try:
            preflight = run_loop(client, "preflight", Tools(root, "review", redact, deadline=deadline), initial, events, max_steps=3, preflight=True)
            if preflight["tool_calls"] < 1 or preflight["final_text"].strip() != "PREFLIGHT_OK":
                raise RuntimeError("Actual tool/reasoning-history preflight did not finish")
            atomic_json(preflight_path, {"time": timestamp(), "model": MODEL, "reasoning_requested": args.reasoning,
                "max_output_configured": args.max_output_tokens, "context_configured": args.context_tokens}, redact)
        except Exception as error:
            events.emit("coordinator", "preflight_failed", summary=redact(str(error)))
            return 2
    if args.preflight_only:
        return 0
    summary = coordinate(root, client, events, args.slice_rounds, args.slice_minutes, args.work_until_deadline)
    return 0 if summary["state"] in {"accepted_cloud_work", "deadline"} else 1
