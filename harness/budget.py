"""Thread-safe pessimistic reservations for one explicitly authorized run."""
from decimal import Decimal
from pathlib import Path
import json
import threading


class BudgetStopped(RuntimeError):
    pass


class Budget:
    def __init__(self, path, limit="3.70"):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.limit = Decimal(str(limit))
        if self.limit <= 0 or self.limit > Decimal("3.70"):
            raise ValueError("Run ceiling must be positive and at most $3.70")
        self.spent = Decimal(0)
        self.reservations = {}
        self.reservation_states = {}
        self.calls = []
        self.reason = None
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.spent = Decimal(data["confirmed_usd"])
            self.reservations = {k: Decimal(v) for k, v in data["reservations"].items()}
            self.calls = data.get("calls", [])
            self.reason = data.get("stop_reason")
            self.reservation_states = data.get("reservation_states", {})
            # An interrupted HTTP request may have been charged. Keep its entire
            # pessimistic reservation; never silently forgive or replay its cost.
            for call_id in self.reservations:
                if self.reservation_states.get(call_id, "active") == "active":
                    self.reservation_states[call_id] = "interrupted_uncertain"
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"limit_usd": str(self.limit), "confirmed_usd": str(self.spent),
                "reserved_usd": str(sum(self.reservations.values(), Decimal(0))),
                "reservations": {k: str(v) for k, v in self.reservations.items()},
                "reservation_states": self.reservation_states,
                "stop_reason": self.reason, "calls": self.calls,
                "rates_usd_per_million": {"uncached_input": ".135", "cached_input": ".0027", "output": ".540"},
                "pricing_basis": "User-supplied Nube rates; not independently verified billing"}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def reserve(self, call_id, request_bytes, max_output):
        # Byte-based input upper bound plus generous chat/token framing allowance.
        # Every byte is charged as an uncached input token; output includes reasoning.
        input_bound = request_bytes + 4096
        cost = (Decimal(input_bound) * Decimal(".135") + Decimal(max_output) * Decimal(".540")) / Decimal(1_000_000)
        with self.lock:
            if self.reason:
                raise BudgetStopped(self.reason)
            if call_id in self.reservations:
                raise BudgetStopped("Duplicate request reservation")
            if self.spent + sum(self.reservations.values(), Decimal(0)) + cost > self.limit:
                raise BudgetStopped("Run budget cannot cover worst-case next request")
            self.reservations[call_id] = cost
            self.reservation_states[call_id] = "active"
            self.save()
        return input_bound

    def available(self):
        with self.lock:
            return self.limit - self.spent - sum(self.reservations.values(), Decimal(0))

    def active_count(self):
        with self.lock:
            return sum(state == "active" for state in self.reservation_states.values())

    def stop(self, cause):
        with self.lock:
            self.reason = str(cause)
            self.save()

    def settle(self, call_id, usage, input_bound, max_output):
        with self.lock:
            # Reconcile an archived response after process interruption exactly
            # once. Re-reading a settled response must not charge it twice.
            if call_id not in self.reservations and any(item.get("id") == call_id and "usd" in item for item in self.calls):
                return
            try:
                prompt = usage["prompt_tokens"]
                output = usage["completion_tokens"]
                cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (prompt, output, cached)):
                    raise ValueError("Invalid usage counters")
                if cached > prompt or prompt > input_bound or output > max_output:
                    raise ValueError("Usage exceeds reserved bounds")
                cost = (Decimal(prompt - cached) * Decimal(".135") + Decimal(cached) * Decimal(".0027") + Decimal(output) * Decimal(".540")) / Decimal(1_000_000)
                if cost > self.reservations[call_id]:
                    raise ValueError("Cost exceeds reservation")
            except (KeyError, TypeError, ValueError, AttributeError):
                self.reason = "Missing/invalid usage; uncertain request reservation retained"
                self.save()
                raise BudgetStopped(self.reason)
            self.spent += cost
            del self.reservations[call_id]
            self.reservation_states.pop(call_id, None)
            self.calls.append({"id": call_id, "prompt_tokens": prompt, "completion_tokens": output,
                               "cached_tokens": cached, "usd": str(cost)})
            self.save()

    def uncertain(self, call_id, cause, halt=True):
        with self.lock:
            if halt:
                self.reason = "Uncertain request outcome: " + str(cause)
            if call_id in self.reservations:
                self.reservation_states[call_id] = "uncertain"
            self.calls.append({"id": call_id, "state": "uncertain", "cause": str(cause)})
            self.save()

