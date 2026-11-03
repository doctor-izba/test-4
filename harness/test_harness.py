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
from run import Client, Events, MODEL, run_loop


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

    def test_resume_unsettled_request_is_fail_closed(self):
        budget = Budget(self.path)
        budget.reserve("unfinished", 100, 20)
        resumed = Budget(self.path)
        with self.assertRaises(BudgetStopped):
            resumed.reserve("next", 100, 20)


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
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, transport=fake_transport)
        tools = Tools(self.root, "review", self.events.redact)
        result = run_loop(client, "fixture", tools, [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}], self.events, preflight=True)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(requests[0]["reasoning_effort"], "high")
        self.assertEqual(len(self.budget.calls), 2)
        for path in self.output.glob("*"):
            self.assertNotIn(self.secret, path.read_text())

    def test_failed_request_retains_charge_reservation(self):
        def fake_transport(encoded):
            raise TimeoutError("Do not print " + self.secret)
        client = Client(self.secret, self.budget, self.output, self.events, time.monotonic() + 60, transport=fake_transport)
        with self.assertRaises(BudgetStopped):
            client.chat("fixture", [{"role": "user", "content": "test"}])
        self.assertEqual(len(self.budget.reservations), 1)
        self.assertNotIn(self.secret, (self.output / "usage.json").read_text())


if __name__ == "__main__":
    unittest.main()
