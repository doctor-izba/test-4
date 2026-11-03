"""Durable model/tool state; never replay a tool whose outcome is unknown."""
from pathlib import Path
import json
import threading
from datetime import datetime, timezone


def atomic_json(path, value, redact=lambda text: text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(redact(json.dumps(value, ensure_ascii=False, indent=2)), encoding="utf-8")
    temporary.replace(path)


class Session:
    def __init__(self, directory, role, initial, redact=lambda text: text):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.role = role
        self.path = self.directory / (role + ".json")
        self.journal = self.directory / (role + ".events.jsonl")
        self.redact = redact
        self.lock = threading.RLock()
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data["resumed"] = True
        else:
            self.data = {"version": 2, "role": role, "messages": initial, "pending_tools": [],
                         "pending_request": None, "model_turns": 0, "tool_count": 0,
                         "state": "ready", "compactions": 0, "last_finish_reason": None}
        self.flush()

    @property
    def messages(self):
        return self.data["messages"]

    def flush(self):
        with self.lock:
            self.data["checkpoint_utc"] = datetime.now(timezone.utc).isoformat()
            atomic_json(self.path, self.data, self.redact)

    def record(self, kind, **details):
        with self.lock:
            entry = {"kind": kind, "time": datetime.now(timezone.utc).isoformat(), **details}
            with self.journal.open("a", encoding="utf-8") as stream:
                stream.write(self.redact(json.dumps(entry, ensure_ascii=False)) + "\n")

    def add(self, message):
        self.messages.append(message)
        self.record("message", message=message)
        self.flush()

    def request_started(self, call_id):
        self.data["pending_request"] = call_id
        self.data["state"] = "requesting"
        self.flush()

    def response(self, message, call_id, finish_reason):
        # Idempotent recovery from the archived provider response.
        if self.data.get("last_response_id") == call_id:
            return
        self.messages.append(message)
        self.data["last_response_id"] = call_id
        self.data["pending_request"] = None
        self.data["model_turns"] += 1
        self.data["last_finish_reason"] = finish_reason
        self.data["pending_tools"] = [{"id": call["id"], "function": call.get("function", {}), "state": "pending"}
                                      for call in (message.get("tool_calls") or [])]
        self.data["state"] = "tools_pending" if self.data["pending_tools"] else "responded"
        self.record("response", call_id=call_id, message=message, finish_reason=finish_reason)
        self.flush()

    def tool_started(self, tool):
        tool["state"] = "running"
        self.data["state"] = "tool_running"
        self.flush()

    def tool_finished(self, tool, result):
        tool["result"] = result
        tool["state"] = "completed"
        self.data["tool_count"] += 1
        self.record("tool_result", tool_id=tool["id"], result=result)
        self.flush()
        self.append_tool_result(tool)

    def append_tool_result(self, tool):
        if any(message.get("role") == "tool" and message.get("tool_call_id") == tool["id"] for message in self.messages):
            return
        self.add({"role": "tool", "tool_call_id": tool["id"], "content": tool["result"]})

    def recover_tools(self):
        for tool in self.data.get("pending_tools", []):
            if tool["state"] == "running":
                tool["state"] = "unknown"
                tool["result"] = json.dumps({"interrupted_unknown_outcome": True,
                    "instruction": "This tool may already have changed files before coordinator interruption. It WILL NOT be replayed. Inspect the existing artifacts and .tool-logs before choosing a safe next action."})
                self.record("tool_interrupted", tool_id=tool["id"])
                self.flush()
            if tool["state"] in {"completed", "unknown"}:
                self.append_tool_result(tool)

    def compact(self, handoff):
        # Save complete history before replacing only the active model context.
        self.record("pre_compaction", messages=self.messages)
        first = self.messages[:2]
        starts = [i for i in range(2, len(self.messages)) if self.messages[i].get("role") == "assistant"]
        tail = self.messages[starts[-3]:] if len(starts) >= 3 else []
        self.data["messages"] = first + [{"role": "user", "content": handoff}] + tail
        self.data["compactions"] += 1
        self.record("compacted_context", messages=self.messages)
        self.flush()
