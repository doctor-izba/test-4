"""Offline tests: no credentials, provider requests, or token expenditure."""
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from budget import Budget, BudgetStopped
from tools import Tools, clean_environment, safe_public_url
from run import Client, Events, MODEL, run_loop, RetryExhausted, coordinate, parse_deadline, compact_if_needed
from sessions import Session
import urllib.error
import io
from sse import parse_sse


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "usage.json"

    def test_concurrent_reservations_cannot_overcommit(self):
        budget = Budget(self.path, ".009")
        barrier = threading.Barrier(12)
        def reserve(index):
            barrier.wait()
            try:
                budget.reserve(str(index), 1000, 8192)
                return True
            except BudgetStopped:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = list(pool.map(reserve, range(12)))
        self.assertEqual(sum(accepted), 1)
        self.assertLessEqual(sum(budget.reservations.values()), budget.limit)

    def test_unknown_usage_retains_reservation_and_stops(self):
        budget = Budget(self.path)
        bound = budget.reserve("one", 100, 20)
        with self.assertRaises(BudgetStopped):
            budget.settle("one", None, bound, 20)
        self.assertIn("one", budget.reservations)
        with self.assertRaises(BudgetStopped):
            budget.reserve("two", 100, 20)

    def test_cached_cost_and_reasoning_are_accounted_once(self):
        budget = Budget(self.path)
        bound = budget.reserve("one", 1000, 100)
        budget.settle("one", {"prompt_tokens": 1000, "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 900}, "completion_tokens_details": {"reasoning_tokens": 90}}, bound, 100)
        self.assertEqual(budget.spent, Decimal("0.00006993"))
        self.assertFalse(budget.reservations)

    def test_usage_above_reservation_stops(self):
        budget = Budget(self.path)
        bound = budget.reserve("one", 100, 20)
        with self.assertRaises(BudgetStopped):
            budget.settle("one", {"prompt_tokens": bound + 1, "completion_tokens": 1}, bound, 20)
        self.assertIn("one", budget.reservations)

    def test_resume_unsettled_request_is_still_reserved(self):
        budget = Budget(self.path)
        budget.reserve("unfinished", 100, 20)
        resumed = Budget(self.path)
        self.assertIn("unfinished", resumed.reservations)
        self.assertEqual(resumed.reservation_states["unfinished"], "interrupted_uncertain")
        resumed.reserve("next", 100, 20)
        self.assertEqual(len(resumed.reservations), 2)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = Tools(self.root, "lean", lambda text: text.replace("secret-test", "[REDACTED]"))

    def test_role_write_and_path_escape(self):
        self.tools.write_file("lean/test.lean", "secret-test")
        self.assertEqual((self.root / "lean/test.lean").read_text(), "[REDACTED]")
        for path in ["../escape.txt", "reports/no.txt", ".git/config", "output/request.json"]:
            with self.assertRaises(ValueError):
                self.tools.write_file(path, "x")

    def test_shell_credentials_are_removed(self):
        env = clean_environment({"PATH": "/bin", "NUBE_API_KEY": "secret", "GITHUB_TOKEN": "secret", "ACTIONS_RUNTIME_TOKEN": "secret", "HOME": "/private", "LANG": "C"})
        self.assertEqual(env, {"PATH": "/bin", "LANG": "C"})

    def test_production_shell_refuses_missing_sandbox(self):
        with patch("tools.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                self.tools.shell("echo hello")

    def test_local_network_fetch_refused(self):
        with self.assertRaises(ValueError):
            safe_public_url("http://example.com/")
        with patch("tools.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                safe_public_url("https://example.com/")


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        (self.root / "README.md").write_text("offline fixture")
        self.secret = "secret-test-123"
        self.events = Events(self.output, lambda value: str(value).replace(self.secret, "[REDACTED]"))
        self.budget = Budget(self.output / "usage.json")

    def test_multiturn_tool_loop_preserves_reasoning_and_redacts(self):
        requests = []
        def fake_transport(encoded):
            payload = json.loads(encoded)
            requests.append(payload)
            if len(requests) == 1:
                message = {"role": "assistant", "content": None, "reasoning_content": "keep this reasoning",
                    "tool_calls": [{"id": "tool_one", "type": "function", "function": {"name": "read_file", "arguments": '{"path":"README.md"}'}}]}
            else:
                self.assertEqual(payload["messages"][-1]["role"], "tool")
                self.assertEqual(payload["messages"][-2]["reasoning_content"], "keep this reasoning")
                message = {"role": "assistant", "content": "PREFLIGHT_OK " + self.secret}
            return {"model": MODEL, "choices": [{"message": message, "finish_reason": "stop"}], "usage": {"prompt_tokens": 50, "completion_tokens": 10}}
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, thinking="high", transport=fake_transport)
        tools = Tools(self.root, "review", self.events.redact)
        result = run_loop(client, "fixture", tools, [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}], self.events, preflight=True)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(requests[0]["reasoning_effort"], "high")
        self.assertEqual(len(self.budget.calls), 2)
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertNotIn(self.secret, path.read_text())

    def test_failed_request_retains_charge_reservation(self):
        def fake_transport(encoded):
            raise TimeoutError("Do not print " + self.secret)
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, transport=fake_transport, retries=0, retry_base=0)
        with self.assertRaises(RetryExhausted):
            client.chat("fixture", [{"role": "user", "content": "test"}])
        self.assertEqual(len(self.budget.reservations), 1)
        self.assertNotIn(self.secret, (self.output / "usage.json").read_text())

    def fixture_response(self, content="DONE", finish="stop", tool_calls=None):
        message = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"model": MODEL, "choices": [{"message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}

    def test_retry_429_500_then_success_retains_failed_reservations(self):
        calls = []
        def transport(encoded):
            calls.append(json.loads(encoded))
            if len(calls) <= 2:
                raise urllib.error.HTTPError("https://example.test", [429, 500][len(calls) - 1], "fixture", {}, None)
            return self.fixture_response()
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=transport, retry_base=0, sleep=lambda delay: None)
        client.chat("retry", [{"role": "user", "content": "test"}])
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(self.budget.reservations), 2)
        self.assertIsNone(self.budget.reason)
        self.assertEqual(calls[0]["max_tokens"], 393216)
        self.assertEqual(calls[0]["reasoning_effort"], "max")

    def test_401_is_fatal_without_retry(self):
        calls = []
        def transport(encoded):
            calls.append(encoded)
            raise urllib.error.HTTPError("https://example.test", 401, "fixture", {}, None)
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=transport, retry_base=0, sleep=lambda delay: None)
        with self.assertRaises(BudgetStopped):
            client.chat("fatal", [{"role": "user", "content": "test"}])
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.budget.reason)

    def test_524_is_transient_then_streaming_success(self):
        requests = []
        def transport(encoded):
            requests.append(json.loads(encoded))
            if len(requests) == 1:
                raise urllib.error.HTTPError("https://example.test", 524, "fixture", {}, None)
            return self.fixture_response()
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=transport, retry_base=0, sleep=lambda delay: None)
        client.chat("cloudflare", [{"role": "user", "content": "test"}])
        self.assertEqual(len(requests), 2)
        self.assertIsNone(self.budget.reason)
        self.assertEqual(len(self.budget.reservations), 1)
        self.assertTrue(requests[0]["stream"])
        self.assertTrue(requests[0]["stream_options"]["include_usage"])
        self.assertEqual(requests[0]["max_tokens"], 393216)
        self.assertEqual(requests[1]["max_tokens"], 65536)

    def test_sse_fragments_reasoning_multiple_tools_and_final_usage(self):
        chunks = [
            {"model": MODEL, "choices": [{"index": 0, "delta": {"role": "assistant", "reasoning_content": "check "}}]},
            {"choices": [{"index": 0, "delta": {"reasoning_content": "both", "tool_calls": [
                {"index": 0, "id": "call_a", "type": "function", "function": {"name": "read_", "arguments": '{"path":'}},
                {"index": 1, "id": "call_b", "function": {"name": "write_file", "arguments": '{"path":"lean/x",'}}]}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 1, "function": {"arguments": '"content":"ok"}'}},
                {"index": 0, "function": {"name": "file", "arguments": '"README.md"}'}}]}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": {"prompt_tokens": 20, "completion_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 10}}},
        ]
        raw = ": keepalive\n\n" + "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        response = parse_sse(io.BytesIO(raw.encode()))
        message = response["choices"][0]["message"]
        self.assertEqual(message["reasoning_content"], "check both")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(json.loads(message["tool_calls"][0]["function"]["arguments"]), {"path": "README.md"})
        self.assertEqual(json.loads(message["tool_calls"][1]["function"]["arguments"]), {"path": "lean/x", "content": "ok"})
        self.assertEqual(response["usage"]["completion_tokens"], 30)

    def test_sse_502_sticky_json_fallback_preserves_actual_payload(self):
        requests = []
        def transport(encoded):
            requests.append(json.loads(encoded))
            if len(requests) == 1:
                raise urllib.error.HTTPError("https://example.test", 502, "fixture", {}, None)
            return self.fixture_response()
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=transport, retry_base=0, sleep=lambda delay: None)
        client.chat("fallback", [{"role": "user", "content": "test"}], max_tokens=1024)
        client.chat("ordinary", [{"role": "user", "content": "test"}])
        self.assertTrue(requests[0]["stream"])
        self.assertFalse(requests[1]["stream"])
        self.assertNotIn("stream_options", requests[1])
        self.assertEqual(requests[1]["reasoning_effort"], "high")
        self.assertFalse(requests[2]["stream"])
        self.assertEqual(requests[2]["max_tokens"], 393216)
        self.assertEqual(requests[2]["reasoning_effort"], "max")
        restored = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=transport, retry_base=0)
        self.assertFalse(restored.streaming_enabled)
        self.assertIsNone(self.budget.reason)
        self.assertEqual(len(self.budget.reservations), 1)

    def test_missing_usage_is_fatal(self):
        response = self.fixture_response()
        del response["usage"]
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=lambda encoded: response, retry_base=0)
        with self.assertRaises(BudgetStopped):
            client.chat("usage", [{"role": "user", "content": "test"}])
        self.assertIn("Missing/invalid usage", self.budget.reason)

    def test_request_larger_than_200kb_is_allowed(self):
        sizes = []
        def transport(encoded):
            sizes.append(len(encoded))
            return self.fixture_response()
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, transport=transport)
        client.chat("large", [{"role": "user", "content": "x" * 250000}])
        self.assertGreater(sizes[0], 200000)

    def test_unlimited_turn_option_and_length_continuation(self):
        requests = []
        def transport(encoded):
            requests.append(json.loads(encoded))
            return self.fixture_response("partial" if len(requests) == 1 else "DONE", "length" if len(requests) == 1 else "stop")
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, transport=transport)
        result = run_loop(client, "continuous", Tools(self.root, "lean"),
            [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}], self.events, max_steps=0)
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["state"], "finished")
        self.assertIn("previous response hit", requests[1]["messages"][-1]["content"])

    def test_resume_unknown_tool_does_not_reexecute(self):
        initial = [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}]
        session = Session(self.output / "sessions", "resume", initial)
        call = {"id": "non_idempotent", "type": "function", "function": {"name": "write_file", "arguments": '{"path":"lean/result.txt","content":"once"}'}}
        session.response({"role": "assistant", "content": None, "tool_calls": [call]}, "archived", "tool_calls")
        session.tool_started(session.data["pending_tools"][0])
        restored = Session(self.output / "sessions", "resume", initial)
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=lambda encoded: self.fixture_response())
        tools = Tools(self.root, "lean")
        with patch.object(tools, "call") as execute:
            result = run_loop(client, "resume", tools, initial, self.events, session=restored)
        execute.assert_not_called()
        self.assertEqual(result["state"], "finished")
        self.assertTrue(any("interrupted_unknown_outcome" in item.get("content", "") for item in restored.messages if item.get("role") == "tool"))

    def test_finished_roles_still_continue_to_review_repair_cycle(self):
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=lambda encoded: self.fixture_response())
        calls = []
        lock = threading.Lock()
        def runner(root, role, client, events, rounds, minutes, cycle):
            with lock:
                calls.append((cycle, role))
            return {"state": "finished"}
        summary = coordinate(self.root, client, self.events, work_until_deadline=True, runner=runner, max_cycles=2)
        self.assertEqual(summary["cycle"], 2)
        self.assertEqual(len(calls), 10)
        for cycle in [1, 2]:
            group = [role for number, role in calls if number == cycle]
            self.assertEqual(group[-2:], ["reviewer", "writer"])

    def test_compaction_drops_oversized_tail_but_keeps_archive(self):
        initial = [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}]
        session = Session(self.output / "sessions", "compact", initial)
        session.add({"role": "assistant", "content": "x" * 800000})
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60,
            transport=lambda encoded: self.fixture_response())
        (self.root / "lean").mkdir(exist_ok=True)
        compact_if_needed(client, session, self.root, "lean")
        self.assertLess(len(json.dumps(session.messages).encode()), 655360)
        self.assertIn("x" * 1000, session.journal.read_text())


if __name__ == "__main__":
    unittest.main()
