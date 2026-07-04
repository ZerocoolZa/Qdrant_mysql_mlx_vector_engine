class DomTesting:
    """Testing operations: assertions, benchmarks, coverage, fixtures, mocks, reports."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._fixtures = {}
        self._mocks = {}
        self._results = []

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "assert": self.assert_,
            "benchmark": self.benchmark,
            "coverage": self.coverage,
            "fixture": self.fixture,
            "integration": self.integration,
            "mock": self.mock,
            "report": self.report,
            "skip": self.skip,
            "teardown": self.teardown,
            "unit": self.unit,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def assert_(self, params=None):
        params = params or {}
        try:
            actual = params.get("actual")
            expected = params.get("expected")
            op = params.get("op", "eq")
            ok = False
            if op == "eq":
                ok = actual == expected
            elif op == "ne":
                ok = actual != expected
            elif op == "gt":
                ok = actual is not None and expected is not None and actual > expected
            elif op == "lt":
                ok = actual is not None and expected is not None and actual < expected
            elif op == "gte":
                ok = actual is not None and expected is not None and actual >= expected
            elif op == "lte":
                ok = actual is not None and expected is not None and actual <= expected
            elif op == "in":
                ok = actual in expected
            elif op == "is_none":
                ok = actual is None
            elif op == "is_not_none":
                ok = actual is not None
            elif op == "true":
                ok = bool(actual)
            entry = {"name": params.get("name", "assert"), "op": op, "passed": ok}
            self._results.append(entry)
            result = {"domain": "testing", "method": "assert", "data": entry}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ASSERT_ERROR", str(e), 0))

    def benchmark(self, params=None):
        params = params or {}
        try:
            import time
            iterations = int(params.get("iterations", 100))
            func = params.get("func")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            if not callable(func):
                return (0, None, ("BENCHMARK_ERROR", "func not callable", 0))
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                func(*args, **kwargs)
                times.append(time.perf_counter() - start)
            avg = sum(times) / len(times) if times else 0
            mn = min(times) if times else 0
            mx = max(times) if times else 0
            result = {"domain": "testing", "method": "benchmark", "data": {"iterations": iterations, "avg_sec": avg, "min_sec": mn, "max_sec": mx}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BENCHMARK_ERROR", str(e), 0))

    def coverage(self, params=None):
        params = params or {}
        try:
            lines = params.get("lines", [])
            executed = params.get("executed", [])
            total = len(lines)
            covered = sum(1 for l in executed if l in lines)
            pct = round((covered / total) * 100, 2) if total else 0.0
            missing = [l for l in lines if l not in executed]
            result = {"domain": "testing", "method": "coverage", "data": {"total": total, "covered": covered, "percent": pct, "missing": missing}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COVERAGE_ERROR", str(e), 0))

    def fixture(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            action = params.get("action", "set")
            if action == "set":
                self._fixtures[name] = params.get("data")
                result = {"domain": "testing", "method": "fixture", "data": {"name": name, "action": "set", "stored": True}}
            elif action == "get":
                result = {"domain": "testing", "method": "fixture", "data": {"name": name, "action": "get", "data": self._fixtures.get(name)}}
            elif action == "clear":
                self._fixtures.pop(name, None)
                result = {"domain": "testing", "method": "fixture", "data": {"name": name, "action": "clear", "cleared": True}}
            else:
                return (0, None, ("FIXTURE_ERROR", f"unknown action: {action}", 0))
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIXTURE_ERROR", str(e), 0))

    def integration(self, params=None):
        params = params or {}
        try:
            steps = params.get("steps", [])
            results = []
            passed = 0
            for step in steps:
                name = step.get("name", "step")
                func = step.get("func")
                try:
                    if callable(func):
                        out = func(*step.get("args", []), **step.get("kwargs", {}))
                        results.append({"name": name, "passed": True, "output": out})
                        passed += 1
                    else:
                        results.append({"name": name, "passed": False, "error": "not callable"})
                except Exception as se:
                    results.append({"name": name, "passed": False, "error": str(se)})
            result = {"domain": "testing", "method": "integration", "data": {"steps": results, "passed": passed, "total": len(steps)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INTEGRATION_ERROR", str(e), 0))

    def mock(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            action = params.get("action", "set")
            if action == "set":
                self._mocks[name] = params.get("returns")
                result = {"domain": "testing", "method": "mock", "data": {"name": name, "action": "set", "mocked": True}}
            elif action == "call":
                result = {"domain": "testing", "method": "mock", "data": {"name": name, "action": "call", "returns": self._mocks.get(name)}}
            elif action == "clear":
                self._mocks.pop(name, None)
                result = {"domain": "testing", "method": "mock", "data": {"name": name, "action": "clear", "cleared": True}}
            else:
                return (0, None, ("MOCK_ERROR", f"unknown action: {action}", 0))
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MOCK_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            total = len(self._results)
            passed = sum(1 for r in self._results if r.get("passed"))
            failed = total - passed
            result = {"domain": "testing", "method": "report", "data": {"total": total, "passed": passed, "failed": failed, "results": self._results}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def skip(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "test")
            reason = params.get("reason", "")
            entry = {"name": name, "passed": None, "skipped": True, "reason": reason}
            self._results.append(entry)
            result = {"domain": "testing", "method": "skip", "data": entry}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SKIP_ERROR", str(e), 0))

    def teardown(self, params=None):
        params = params or {}
        try:
            self._fixtures.clear()
            self._mocks.clear()
            cleared_results = len(self._results)
            self._results.clear()
            result = {"domain": "testing", "method": "teardown", "data": {"fixtures_cleared": True, "mocks_cleared": True, "results_cleared": cleared_results}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEARDOWN_ERROR", str(e), 0))

    def unit(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "unit")
            func = params.get("func")
            args = params.get("args", [])
            kwargs = params.get("kwargs", {})
            if not callable(func):
                return (0, None, ("UNIT_ERROR", "func not callable", 0))
            try:
                out = func(*args, **kwargs)
                entry = {"name": name, "passed": True, "output": out}
            except Exception as se:
                entry = {"name": name, "passed": False, "error": str(se)}
            self._results.append(entry)
            result = {"domain": "testing", "method": "unit", "data": entry}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNIT_ERROR", str(e), 0))
