#!/usr/bin/env python3
"""Bounded DeepSeek team: three parallel workers, then reviewer and writer."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import ctypes
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.request
import uuid

from budget import Budget, BudgetStopped
from tools import Tools, SCHEMAS

MODEL = "DeepSeek-V4.1-Flash"
ROLES = {"research": "research", "lean": "lean", "simulation": "simulation", "reviewer": "review", "writer": "reports"}
BASE_INSTRUCTIONS = """You are a DeepSeek worker completing a real robotics assignment project.
Write complete useful files, run the available checks, and make claims only from
actual evidence. Lean files existing in this repo are a failing baseline: repair
proofs rather than declaring success. No sorry/admit/custom axioms or weakening
theorem conclusions to make checks pass. Do not invent simulation measurements,
compiler results, source pages, citations, or a passing report. Label limitations.
Read tasks/PROJECT_BRIEF.md and your role task before working. Read relevant other
worker files freely, but write only in your owned directory. Your shell cwd is
that directory; read_file/write_file paths are repository-relative. Shell runs
inside a Linux bubblewrap sandbox with no network; installed software, parent
repo and toolchains are read-only. fetch_url can acquire public HTTPS resources
into your owned directory. Do not attempt authentication/paywall bypasses,
credential access, process/environment inspection, privilege escalation, another
agent/API process, or changes to the harness/workflows. Every request costs part
of one shared budget: make bounded useful progress and avoid dumping huge files.
Use original prose and short relevant citations. End by writing handoff.md in
your owned directory: changed files, exact commands/results, failures, remaining
work and evidence paths. Completion requires evidence, not just a source file.
"""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Events:
    def __init__(self, output, redact):
        self.output = output
        self.redact = redact
        self.lock = threading.RLock()
        self.states = {}

    def emit(self, role, event, **details):
        with self.lock:
            record = {"time": timestamp(), "role": role, "event": event, **details}
            serialized = self.redact(json.dumps(record, ensure_ascii=False))
            with (self.output / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
            self.states[role] = json.loads(serialized)
            temporary = self.output / "status.tmp"
            temporary.write_text(json.dumps(self.states, indent=2), encoding="utf-8")
            temporary.replace(self.output / "status.json")
            # Concise live GitHub Actions log; tool contents remain in output files.
            print(self.redact(f"[{record['time']}] {role}: {event} {details.get('summary', '')}"), flush=True)


class Client:
    def __init__(self, secret, budget, output, events, deadline, thinking="high", transport=None):
        self.secret = secret
        self.budget = budget
        self.output = output
        self.events = events
        self.deadline = deadline
        self.thinking = thinking
        self.transport = transport or self.request

    def request(self, payload):
        request = urllib.request.Request("https://ai.nube-api.com/v1/chat/completions", data=payload,
            headers={"Authorization": "Bearer " + self.secret, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)

    def chat(self, role, messages, max_tokens=8192, tool_choice=None):
        if time.monotonic() >= self.deadline:
            raise BudgetStopped("Run deadline reached")
        max_tokens = min(max(1, max_tokens), 8192)
        payload = {"model": MODEL, "messages": messages, "tools": SCHEMAS,
                   "max_tokens": max_tokens, "stream": False}
        if self.thinking != "off":
            payload["reasoning_effort"] = self.thinking
        if tool_choice:
            payload["tool_choice"] = tool_choice
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(encoded) > 200000:
            raise BudgetStopped("Request history exceeds 200 KB bound; write a handoff and start a smaller task")
        call_id = role + "-" + uuid.uuid4().hex[:12]
        bound = self.budget.reserve(call_id, len(encoded), max_tokens)
        self.events.emit(role, "request", call_id=call_id, request_bytes=len(encoded), requested_reasoning=self.thinking)
        try:
            data = self.transport(encoded)
        except Exception as error:
            # Response bodies, URLs and exception strings can contain credentials.
            self.budget.uncertain(call_id, type(error).__name__)
            raise BudgetStopped("API request failed; reservation retained: " + type(error).__name__) from None
        self.budget.settle(call_id, data.get("usage"), bound, max_tokens)
        if str(data.get("model", "")).lower() != MODEL.lower():
            self.budget.uncertain(call_id, "Unexpected response model")
            raise BudgetStopped("Unexpected response model; no silent provider/model substitution")
        if not isinstance(data.get("choices"), list) or not data["choices"]:
            raise BudgetStopped("API returned no choices")
        message = data["choices"][0].get("message", {})
        if message.get("role") != "assistant":
            raise BudgetStopped("Invalid assistant response")
        safe = {key: message[key] for key in ("role", "content", "tool_calls", "reasoning_content") if key in message}
        history = {"call_id": call_id, "request": payload, "response": data}
        (self.output / (call_id + ".json")).write_text(self.events.redact(json.dumps(history, ensure_ascii=False, indent=2)), encoding="utf-8")
        self.events.emit(role, "response", call_id=call_id, usage=data["usage"], finish_reason=data["choices"][0].get("finish_reason"))
        return safe


def run_loop(client, role, tools, messages, events, max_steps=35, preflight=False):
    final_text = ""
    tool_count = 0
    for step in range(max_steps):
        if time.monotonic() >= client.deadline:
            raise BudgetStopped("Run deadline reached")
        choice = {"type": "function", "function": {"name": "read_file"}} if preflight and step == 0 else None
        message = client.chat(role, messages, max_tokens=1024 if preflight else 8192, tool_choice=choice)
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            final_text = message.get("content") or ""
            events.emit(role, "finished", summary=final_text[:300], steps=step + 1, tool_calls=tool_count)
            return {"state": "finished", "steps": step + 1, "tool_calls": tool_count, "final_text": final_text}
        if len(calls) > 12:
            raise BudgetStopped("Assistant requested too many tools in one turn")
        for call in calls:
            tool_count += 1
            function = call.get("function", {})
            name = function.get("name", "")
            try:
                args = json.loads(function.get("arguments", "{}"))
                if not isinstance(args, dict):
                    raise ValueError("Tool arguments must be an object")
                result = tools.call(name, args)
            except (ValueError, TypeError):
                result = json.dumps({"error": "Invalid JSON tool arguments"})
            events.emit(role, "tool", name=name, summary=result[:200], result=result)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        # Keep complete assistant/tool blocks; earlier blocks are on disk and in files.
        if len(json.dumps(messages).encode()) > 140000:
            starts = [i for i, item in enumerate(messages[2:], start=2) if item.get("role") == "assistant"]
            if len(starts) > 5:
                messages[:] = messages[:2] + [{"role": "user", "content": "Earlier tool blocks are omitted to bound context. Read your owned files and handoff for accumulated work; do not repeat completed work."}] + messages[starts[-5]:]
    events.emit(role, "step_limit", steps=max_steps)
    return {"state": "step_limit", "steps": max_steps, "tool_calls": tool_count, "final_text": final_text}


def task_text(root, role):
    parts = []
    for name in ["PROJECT_BRIEF", role]:
        path = root / "tasks" / (name + ".md")
        if path.exists():
            parts.append(f"\n## tasks/{name}.md\n" + path.read_text(encoding="utf-8")[:40000])
    return "\n".join(parts) or "Inspect the repository and perform your named role with honest evidence."


def run_agent(root, role, client, events, max_steps):
    events.emit(role, "started", owned_directory=ROLES[role])
    tools = Tools(root, ROLES[role], events.redact, require_sandbox=True)
    messages = [{"role": "system", "content": BASE_INSTRUCTIONS + "\nYour role is " + role + "; owned directory: " + ROLES[role]},
                {"role": "user", "content": task_text(root, role)}]
    try:
        result = run_loop(client, role, tools, messages, events, max_steps)
    except Exception as error:
        result = {"state": "stopped", "error_type": type(error).__name__, "message": events.redact(str(error))}
        events.emit(role, "stopped", summary=result["message"])
    (client.output / (role + "-result.json")).write_text(events.redact(json.dumps(result, indent=2)), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--budget", default="3.70")
    parser.add_argument("--minutes", type=int, default=170)
    parser.add_argument("--steps", type=int, default=35)
    parser.add_argument("--reasoning", choices=["high", "medium", "low", "off"], default="high")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = root / "output"
    output.mkdir(exist_ok=True)
    secret = os.environ.pop("NUBE_API_KEY", "")
    if not secret:
        parser.error("NUBE_API_KEY must be supplied through the GitHub Actions secret")
    if sys.platform != "linux":
        parser.error("Production tool execution requires Linux and bubblewrap")
    try:
        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE=0: protect parent /proc credentials.
    except Exception:
        pass
    # Do not make unrelated workflow credentials available to agent tool processes.
    for name in list(os.environ):
        if any(term in name.upper() for term in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
            os.environ.pop(name, None)
    redact = lambda value: str(value).replace(secret, "[REDACTED]")
    events = Events(output, redact)
    budget = Budget(output / "usage.json", args.budget)
    deadline = time.monotonic() + min(max(args.minutes, 1), 180) * 60
    client = Client(secret, budget, output, events, deadline, args.reasoning)
    # Validate Linux shell isolation before any paid request.
    probe = Tools(root, "review", redact).shell("printf SANDBOX_OK", timeout=10)
    if probe.get("exit_code") != 0 or "SANDBOX_OK" not in probe.get("output", ""):
        events.emit("coordinator", "sandbox_failed", summary=str(probe))
        return 2
    preflight_tools = Tools(root, "review", redact)
    messages = [{"role": "system", "content": "Test API tool calling. Call read_file on README.md, then reply exactly PREFLIGHT_OK. Do not write files or run shell commands."},
                {"role": "user", "content": "Perform the read_file tool test now."}]
    try:
        preflight = run_loop(client, "preflight", preflight_tools, messages, events, max_steps=3, preflight=True)
        if preflight["tool_calls"] < 1 or preflight["final_text"].strip() != "PREFLIGHT_OK":
            raise RuntimeError("Tool-call/reasoning-history preflight did not complete")
    except Exception as error:
        events.emit("coordinator", "preflight_failed", summary=redact(str(error)))
        return 2
    if args.preflight_only:
        events.emit("coordinator", "preflight_passed", summary="Tool loop passed; requested reasoning level is not independently attested by API")
        return 0
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run_agent, root, role, client, events, args.steps): role for role in ["research", "lean", "simulation"]}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    for role in ["reviewer", "writer"]:
        if budget.reason or time.monotonic() >= deadline:
            events.emit(role, "skipped", summary="Global budget uncertainty or deadline")
            results[role] = {"state": "skipped"}
        else:
            results[role] = run_agent(root, role, client, events, args.steps)
    summary = {"time": timestamp(), "model": MODEL, "requested_reasoning": args.reasoning,
               "roles": results, "note": "Agent turn completion is not independent acceptance of the assignment. Consult reviewer evidence and actual compiler/test logs."}
    (output / "run-summary.json").write_text(redact(json.dumps(summary, indent=2)), encoding="utf-8")
    events.emit("coordinator", "run_finished", summary="Review generated files, compiler evidence, and usage ledger")
    return 0 if all(result.get("state") == "finished" for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
