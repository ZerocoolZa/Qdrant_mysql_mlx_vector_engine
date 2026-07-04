#[@GHOST]{file_path="core/Dom_Benchmark/Runner.py" date="2026-07-04" author="Devin" session_id="benchmark-framework" context="Core runner engine for benchmark framework. Orchestrates the full pipeline: Generator → Trigger → Capture → AI Fix → Apply → Re-run → Validate. Manages test cases, sandbox execution, timing, and result collection."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="Runner.py" domain="dom_benchmark" authority="Runner"}
#[@SUMMARY]{summary="Core runner engine — orchestrates the full benchmark pipeline. Generator → Trigger → Capture → AI Fix → Apply → Re-run → Validate. Manages test cases, sandbox execution, timing, result collection, and statistics."}
#[@CLASS]{class="Runner" domain="dom_benchmark" authority="runner"}
#[@METHOD]{method="run_case" type="executor"}
#[@METHOD]{method="run_batch" type="executor"}
#[@METHOD]{method="run_family" type="executor"}
#[@METHOD]{method="run_all" type="executor"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}

"""Runner — Core benchmark runner engine.

Orchestrates the full pipeline for each test case:
  1. GENERATE  — create or load the error test case
  2. TRIGGER   — execute broken code in sandbox, capture exception
  3. CAPTURE   — record traceback, exception name, timing
  4. AI FIX    — generate fix candidates (via repair engine)
  5. APPLY     — apply each candidate to the broken code
  6. RE-RUN    — execute fixed code in sandbox
  7. VALIDATE  — py_compile, ast.parse, re-run check, self-validation

The runner is the central orchestrator. It does NOT implement the repair
engine or validation engine itself — those are plugged in via set_repair_engine()
and set_validation_engine(). This keeps the runner focused on orchestration.
"""

import os
import sys
import time
import json
import subprocess
import tempfile
import traceback as tb_module
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import Config
    from ErrorModel import ErrorModel, FixCandidate, ValidationResult
    from Scoring import Scoring
except ImportError:
    from . import Config
    from .ErrorModel import ErrorModel, FixCandidate, ValidationResult
    from .Scoring import Scoring


class Runner:
    """Core benchmark runner engine.

    Pipeline per case:
        Generator → Trigger → Capture → AI Fix → Apply → Re-run → Validate

    Attributes:
        cases: list of ErrorModel test cases
        scoring: Scoring engine instance
        repair_engine: callable that takes (broken_code, error_info) → list[FixCandidate]
        validation_engine: callable that takes (candidate, original_code) → ValidationResult
        results: list of run results
        state: runner state dict
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.cases: List[ErrorModel] = []
        self.scoring = Scoring()
        self.repair_engine: Optional[Callable] = None
        self.validation_engine: Optional[Callable] = None
        self.results: List[Dict[str, Any]] = []
        self.state = {
            "class": "Runner",
            "initialized": True,
            "total_runs": 0,
            "total_passed": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "total_false_positives": 0,
            "total_promoted": 0,
            "total_demoted": 0,
            "total_duplicates_merged": 0,
            "avg_score": 0.0,
            "best_score": 0,
            "worst_score": 0,
            "avg_timing_ms": 0.0,
            "total_timing_ms": 0.0,
            "current_case": "",
            "current_family": "",
            "families_run": {},
            "last_error": None,
        }

    def _p(self, label, value):
        """Helper to log state transitions."""
        self.state["last_" + label] = value

    def set_repair_engine(self, engine: Callable) -> None:
        """Set the repair engine callable.

        The callable should accept:
            (broken_code: str, error_info: dict) → list[FixCandidate]

        error_info contains:
            exception_name, traceback_text, family, case_id
        """
        self.repair_engine = engine

    def set_validation_engine(self, engine: Callable) -> None:
        """Set the validation engine callable.

        The callable should accept:
            (candidate: FixCandidate, original_code: str, expected_exception: str) → ValidationResult
        """
        self.validation_engine = engine

    def add_case(self, case: ErrorModel) -> None:
        """Add a test case to the runner."""
        self.cases.append(case)

    def add_cases(self, cases: List[ErrorModel]) -> None:
        """Add multiple test cases."""
        self.cases.extend(cases)

    def clear_cases(self) -> None:
        """Clear all test cases."""
        self.cases = []

    def get_cases_by_family(self, family: str) -> List[ErrorModel]:
        """Get all cases for a specific error family."""
        return [c for c in self.cases if c.family == family]

    def get_case(self, case_id: str) -> Optional[ErrorModel]:
        """Get a case by ID."""
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None

    def merge_duplicates(self) -> int:
        """Merge duplicate test cases (same fingerprint).

        Returns:
            number of duplicates removed
        """
        before = len(self.cases)
        self.cases = self.scoring.merge_duplicates(self.cases)
        after = len(self.cases)
        removed = before - after
        self.state["total_duplicates_merged"] += removed
        return removed

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "run_case": self.cmd_run_case,
            "run_batch": self.cmd_run_batch,
            "run_family": self.cmd_run_family,
            "run_all": self.cmd_run_all,
            "add_case": self.cmd_add_case,
            "add_cases": self.cmd_add_cases,
            "clear_cases": self.cmd_clear_cases,
            "get_cases": self.cmd_get_cases,
            "merge_duplicates": self.cmd_merge_duplicates,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
            "set_repair_engine": self.cmd_set_repair_engine,
            "set_validation_engine": self.cmd_set_validation_engine,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("RUNNER_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        for key, value in params.items():
            self.state[key] = value
        return (1, {"updated": len(params)}, None)

    def cmd_set_repair_engine(self, params):
        engine = params.get("engine")
        if engine:
            self.set_repair_engine(engine)
            return (1, {"set": True}, None)
        return (0, None, ("RUNNER_NO_ENGINE", "no engine provided", 0))

    def cmd_set_validation_engine(self, params):
        engine = params.get("engine")
        if engine:
            self.set_validation_engine(engine)
            return (1, {"set": True}, None)
        return (0, None, ("RUNNER_NO_ENGINE", "no engine provided", 0))

    def cmd_add_case(self, params):
        case = params.get("case")
        if not case:
            return (0, None, ("RUNNER_NO_CASE", "no case provided", 0))
        if isinstance(case, dict):
            case = ErrorModel.from_dict(case)
        self.add_case(case)
        return (1, {"added": 1, "total": len(self.cases)}, None)

    def cmd_add_cases(self, params):
        cases = params.get("cases", [])
        if not cases:
            return (0, None, ("RUNNER_NO_CASES", "no cases provided", 0))
        count = 0
        for c in cases:
            if isinstance(c, dict):
                c = ErrorModel.from_dict(c)
            self.add_case(c)
            count += 1
        return (1, {"added": count, "total": len(self.cases)}, None)

    def cmd_clear_cases(self, params):
        self.clear_cases()
        return (1, {"cleared": True, "total": 0}, None)

    def cmd_get_cases(self, params):
        family = params.get("family")
        if family:
            cases = [c.to_dict() for c in self.get_cases_by_family(family)]
        else:
            cases = [c.to_dict() for c in self.cases]
        return (1, {"cases": cases, "count": len(cases)}, None)

    def cmd_merge_duplicates(self, params):
        removed = self.merge_duplicates()
        return (1, {"removed": removed, "remaining": len(self.cases)}, None)

    def cmd_run_case(self, params):
        case_id = params.get("case_id")
        if not case_id:
            return (0, None, ("RUNNER_NO_CASE_ID", "no case_id provided", 0))
        case = self.get_case(case_id)
        if not case:
            return (0, None, ("RUNNER_CASE_NOT_FOUND", case_id, 0))
        result = self.run_case(case)
        return (1, result, None)

    def cmd_run_batch(self, params):
        case_ids = params.get("case_ids", [])
        if not case_ids:
            return (0, None, ("RUNNER_NO_CASE_IDS", "no case_ids provided", 0))
        results = []
        for cid in case_ids:
            case = self.get_case(cid)
            if case:
                results.append(self.run_case(case))
            else:
                results.append({"case_id": cid, "status": "not_found"})
        return (1, {"results": results, "count": len(results)}, None)

    def cmd_run_family(self, params):
        family = params.get("family")
        if not family:
            return (0, None, ("RUNNER_NO_FAMILY", "no family provided", 0))
        cases = self.get_cases_by_family(family)
        if not cases:
            return (0, None, ("RUNNER_NO_CASES_IN_FAMILY", family, 0))
        results = []
        for case in cases:
            results.append(self.run_case(case))
        passed = sum(1 for r in results if r.get("status") == "pass")
        failed = sum(1 for r in results if r.get("status") == "fail")
        skipped = sum(1 for r in results if r.get("status") == "skip")
        self.state["families_run"][family] = {
            "total": len(cases),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }
        return (1, {
            "family": family,
            "results": results,
            "count": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }, None)

    def cmd_run_all(self, params):
        if not self.cases:
            return (0, None, ("RUNNER_NO_CASES", "no cases loaded", 0))
        results = []
        families = {}
        for case in self.cases:
            result = self.run_case(case)
            results.append(result)
            fam = case.family
            if fam not in families:
                families[fam] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
            families[fam]["total"] += 1
            if result.get("status") == "pass":
                families[fam]["passed"] += 1
            elif result.get("status") == "fail":
                families[fam]["failed"] += 1
            else:
                families[fam]["skipped"] += 1
        self.state["families_run"] = families
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "pass")
        failed = sum(1 for r in results if r.get("status") == "fail")
        skipped = sum(1 for r in results if r.get("status") == "skip")
        return (1, {
            "results": results,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "families": families,
            "avg_score": self.state["avg_score"],
            "avg_timing_ms": self.state["avg_timing_ms"],
        }, None)

    def run_case(self, case: ErrorModel) -> Dict[str, Any]:
        """Run a single test case through the full pipeline.

        Pipeline:
            1. Check compatibility (platform, Python version)
            2. AST analysis of broken code
            3. Trigger the error (execute in sandbox)
            4. Capture exception + traceback
            5. Generate fix candidates (via repair engine)
            6. Apply + validate each candidate
            7. Score candidates
            8. Update confidence
            9. Check promote/demote

        Returns:
            result dict with keys:
                case_id, family, expected_exception, triggered_exception,
                status (pass/fail/skip), best_strategy, best_score,
                candidates_tried, timing_ms, confidence, promoted, demoted
        """
        self.state["current_case"] = case.case_id
        self.state["current_family"] = case.family
        start_time = time.perf_counter()

        result: Dict[str, Any] = {
            "case_id": case.case_id,
            "family": case.family,
            "expected_exception": case.expected_exception,
            "triggered_exception": "",
            "status": "skip",
            "best_strategy": "",
            "best_score": 0,
            "candidates_tried": 0,
            "timing_ms": 0.0,
            "confidence": case.confidence,
            "promoted": False,
            "demoted": False,
            "false_positive": False,
            "error": None,
        }

        # Step 1: Check compatibility
        if not case.is_compatible():
            result["status"] = "skip"
            result["error"] = "incompatible platform/python version"
            self.state["total_skipped"] += 1
            self._update_timing(start_time, result)
            return result

        # Step 2: AST analysis
        case.ast_analysis()

        # Step 3: Trigger the error
        triggered, exc_name, tb_text, trigger_ms = case.trigger()
        result["triggered_exception"] = exc_name

        if not triggered:
            # The expected exception was not raised
            result["status"] = "fail"
            result["error"] = "expected {} but got {}".format(case.expected_exception, exc_name)
            case.run_count += 1
            case.fail_count += 1
            case.update_confidence(False)
            self.state["total_failed"] += 1
            self._update_timing(start_time, result)
            return result

        # Step 4: Capture is done by trigger() — already stored in case

        # Step 5: Generate fix candidates
        case.run_count += 1
        case.last_run_at = datetime.utcnow().isoformat(timespec="seconds")

        candidates = []
        if self.repair_engine:
            try:
                error_info = {
                    "exception_name": exc_name,
                    "traceback_text": tb_text,
                    "family": case.family,
                    "case_id": case.case_id,
                    "broken_code": case.broken_code,
                }
                candidates = self.repair_engine(case.broken_code, error_info) or []
            except Exception as exc:
                result["error"] = "repair engine error: " + str(exc)
        elif case.fixed_code:
            # No repair engine — use the known fix as a single candidate
            candidates = [FixCandidate(
                strategy="known_fix",
                fixed_code=case.fixed_code,
                source="predefined",
                confidence=0.9,
            )]

        result["candidates_tried"] = len(candidates)

        if not candidates:
            result["status"] = "fail"
            result["error"] = "no fix candidates generated"
            case.fail_count += 1
            case.update_confidence(False)
            self.state["total_failed"] += 1
            self._update_timing(start_time, result)
            return result

        # Step 6-7: Apply + validate + score each candidate
        best_score = 0
        best_strategy = ""
        any_passed = False
        false_positive_detected = False

        for candidate in candidates:
            # Apply: check if the fixed code is valid
            candidate.timestamp = datetime.utcnow().isoformat(timespec="seconds")

            # Validate
            validation = None
            if self.validation_engine:
                try:
                    validation = self.validation_engine(candidate, case.broken_code, case.expected_exception)
                except Exception:
                    validation = ValidationResult(candidate_strategy=candidate.strategy)
            else:
                validation = self._default_validation(candidate, case.broken_code, case.expected_exception)

            # Detect false positive
            if self.scoring.detect_false_positive(candidate, validation, case.broken_code):
                candidate.passed = False
                validation.false_positive = True
                false_positive_detected = True
                self.state["total_false_positives"] += 1
            else:
                candidate.passed = (
                    validation.py_compile_passed and
                    validation.ast_parse_passed and
                    validation.re_run_passed
                )

            candidate.self_validating = validation.self_validating_passed

            # Score
            score = self.scoring.score_candidate(candidate, validation, case.broken_code)
            case.add_candidate(candidate)
            case.add_validation(validation)

            if score > best_score:
                best_score = score
                best_strategy = candidate.strategy
            if candidate.passed:
                any_passed = True

        # Step 8: Update confidence
        case.update_confidence(any_passed)
        result["confidence"] = case.confidence

        # Step 9: Promote/demote
        action = self.scoring.promote_demote(case.confidence, case.pass_count, case.run_count)
        if action == "promote":
            result["promoted"] = True
            self.state["total_promoted"] += 1
        elif action == "demote":
            result["demoted"] = True
            self.state["total_demoted"] += 1

        # Set result status
        if any_passed:
            result["status"] = "pass"
            self.state["total_passed"] += 1
        else:
            result["status"] = "fail"
            self.state["total_failed"] += 1

        result["best_strategy"] = best_strategy
        result["best_score"] = best_score
        result["false_positive"] = false_positive_detected

        self.state["total_runs"] += 1
        if best_score > self.state["best_score"]:
            self.state["best_score"] = best_score
        if self.state["worst_score"] == 0 or best_score < self.state["worst_score"]:
            self.state["worst_score"] = best_score

        self._update_timing(start_time, result)
        self.results.append(result)
        return result

    def _default_validation(
        self,
        candidate: FixCandidate,
        original_code: str,
        expected_exception: str,
    ) -> ValidationResult:
        """Default validation when no validation engine is set.

        Checks:
        1. py_compile on fixed code
        2. ast.parse on fixed code
        3. Re-run fixed code in sandbox (should NOT raise expected_exception)
        4. Self-validating: fixed code runs without any exception
        """
        import py_compile
        import tempfile

        result = ValidationResult(candidate_strategy=candidate.strategy)
        val_start = time.perf_counter()

        # 1. py_compile
        if candidate.fixed_code:
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bench_val_")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(candidate.fixed_code)
                try:
                    py_compile.compile(tmp_path, doraise=True)
                    result.py_compile_passed = True
                except py_compile.PyCompileError as exc:
                    result.syntax_error = str(exc)
                    result.py_compile_passed = False
            finally:
                if Config.SANDBOX_CLEANUP and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    cache_path = tmp_path + "c"
                    if os.path.exists(cache_path):
                        os.unlink(cache_path)

        # 2. ast.parse
        if candidate.fixed_code:
            try:
                ast_mod = __import__("ast")
                ast_mod.parse(candidate.fixed_code)
                result.ast_parse_passed = True
            except SyntaxError as exc:
                result.syntax_error = str(exc)
                result.ast_parse_passed = False

        # 3. Re-run in sandbox
        if candidate.fixed_code and result.py_compile_passed:
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bench_rerun_")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(candidate.fixed_code)
                try:
                    proc = subprocess.run(
                        [sys.executable, tmp_path],
                        capture_output=True,
                        text=True,
                        timeout=Config.SANDBOX_TIMEOUT_SEC,
                    )
                    if proc.returncode == 0:
                        result.re_run_passed = True
                        result.self_validating_passed = True
                    else:
                        stderr = proc.stderr
                        result.runtime_error = stderr[:Config.MAX_TRACEBACK_LEN]
                        # Check if the SAME exception is still occurring
                        if expected_exception and expected_exception in stderr:
                            result.re_run_passed = False
                        else:
                            # Different error — the original was fixed but a new one appeared
                            result.re_run_passed = True
                            result.self_validating_passed = False
                    result.output = proc.stdout[:Config.SANDBOX_MAX_OUTPUT_CHARS]
                except subprocess.TimeoutExpired:
                    result.runtime_error = "timeout"
                    result.re_run_passed = False
            finally:
                if Config.SANDBOX_CLEANUP and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        result.timing_ms = round((time.perf_counter() - val_start) * 1000, Config.TIMING_PRECISION)
        return result

    def _update_timing(self, start_time: float, result: Dict[str, Any]) -> None:
        """Update timing statistics."""
        elapsed = time.perf_counter() - start_time
        timing_ms = round(elapsed * 1000, Config.TIMING_PRECISION)
        result["timing_ms"] = timing_ms

        total = self.state["total_runs"]
        if total > 0:
            current_avg = self.state["avg_timing_ms"]
            self.state["avg_timing_ms"] = ((current_avg * (total - 1)) + timing_ms) / total
        else:
            self.state["avg_timing_ms"] = timing_ms
        self.state["total_timing_ms"] += timing_ms

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        total = self.state["total_runs"]
        passed = self.state["total_passed"]
        failed = self.state["total_failed"]
        skipped = self.state["total_skipped"]
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        return {
            "total_runs": total,
            "total_passed": passed,
            "total_failed": failed,
            "total_skipped": skipped,
            "pass_rate": round(pass_rate, 2),
            "avg_score": round(self.state["avg_score"], 2),
            "best_score": self.state["best_score"],
            "worst_score": self.state["worst_score"],
            "avg_timing_ms": round(self.state["avg_timing_ms"], 2),
            "total_timing_ms": round(self.state["total_timing_ms"], 2),
            "total_false_positives": self.state["total_false_positives"],
            "total_promoted": self.state["total_promoted"],
            "total_demoted": self.state["total_demoted"],
            "total_duplicates_merged": self.state["total_duplicates_merged"],
            "families_run": self.state["families_run"],
            "total_cases_loaded": len(self.cases),
        }

    def export_results(self, format_type: str = "json") -> str:
        """Export results in the specified format.

        Args:
            format_type: "json" or "bcl"

        Returns:
            serialized results string
        """
        if format_type == "json":
            return json.dumps({
                "statistics": self.get_statistics(),
                "results": self.results,
                "cases": [c.to_dict() for c in self.cases],
            }, indent=2, default=str)
        elif format_type == "bcl":
            lines = ["[@BENCHMARK_RESULT]{"]
            stats = self.get_statistics()
            for key, value in stats.items():
                if isinstance(value, dict):
                    continue
                lines.append("[@{}]{{{}}}".format(key.upper(), value))
            lines.append("}")
            return "".join(lines)
        else:
            return json.dumps(self.results, indent=2, default=str)
