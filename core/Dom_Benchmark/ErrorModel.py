#[@GHOST]{file_path="core/Dom_Benchmark/ErrorModel.py" date="2026-07-04" author="Devin" session_id="benchmark-framework" context="Error model for benchmark framework. Represents a single error test case: broken code, expected exception, fix candidates, validation results, confidence, traceback fingerprint."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ErrorModel.py" domain="dom_benchmark" authority="ErrorModel"}
#[@SUMMARY]{summary="Error model — represents a single error test case with broken code, expected exception, family, severity, fix candidates, validation results, confidence scoring, traceback fingerprinting, and AST analysis."}
#[@CLASS]{class="ErrorModel" domain="dom_benchmark" authority="model"}
#[@METHOD]{method="fingerprint" type="analyzer"}
#[@METHOD]{method="ast_analysis" type="analyzer"}
#[@METHOD]{method="to_bcl" type="serializer"}
#[@METHOD]{method="from_bcl" type="deserializer"}
#[@METHOD]{method="to_dict" type="serializer"}
#[@METHOD]{method="from_dict" type="deserializer"}

"""ErrorModel — A single error test case for the benchmark framework.

Each ErrorModel represents one verified Python exception case:
  - broken_code: code that triggers the error
  - expected_exception: the exception class name
  - family: runtime, syntax, import, os, warning, async, threading, encoding
  - severity: 1-5 (5 = crash, 1 = warning)
  - fix_candidates: list of FixCandidate objects
  - validation_results: list of ValidationResult objects
  - confidence: 0.0-1.0
  - traceback_fingerprint: hash of the traceback for dedup
  - ast_analysis: structural analysis of the broken code

Pipeline: Generator → Trigger → Capture → AI Fix → Apply → Re-run → Validate
"""

import ast
import hashlib
import re
import traceback as tb_module
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import Config
except ImportError:
    from . import Config


@dataclass
class FixCandidate:
    """A single proposed fix for an error."""
    strategy: str = ""
    fixed_code: str = ""
    score: int = 0
    changes: int = 0
    attempts: int = 0
    passed: bool = False
    remaining_errors: int = 0
    source: str = ""
    confidence: float = 0.0
    timestamp: str = ""
    ast_valid: bool = False
    compiles: bool = False
    self_validating: bool = False
    timing_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "fixed_code": self.fixed_code,
            "score": self.score,
            "changes": self.changes,
            "attempts": self.attempts,
            "passed": self.passed,
            "remaining_errors": self.remaining_errors,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "ast_valid": self.ast_valid,
            "compiles": self.compiles,
            "self_validating": self.self_validating,
            "timing_ms": self.timing_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FixCandidate":
        return cls(
            strategy=d.get("strategy", ""),
            fixed_code=d.get("fixed_code", ""),
            score=d.get("score", 0),
            changes=d.get("changes", 0),
            attempts=d.get("attempts", 0),
            passed=d.get("passed", False),
            remaining_errors=d.get("remaining_errors", 0),
            source=d.get("source", ""),
            confidence=d.get("confidence", 0.0),
            timestamp=d.get("timestamp", ""),
            ast_valid=d.get("ast_valid", False),
            compiles=d.get("compiles", False),
            self_validating=d.get("self_validating", False),
            timing_ms=d.get("timing_ms", 0.0),
        )


@dataclass
class ValidationResult:
    """Result of validating a fix candidate."""
    candidate_strategy: str = ""
    py_compile_passed: bool = False
    ast_parse_passed: bool = False
    re_run_passed: bool = False
    self_validating_passed: bool = False
    false_positive: bool = False
    syntax_error: Optional[str] = None
    runtime_error: Optional[str] = None
    output: str = ""
    timing_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_strategy": self.candidate_strategy,
            "py_compile_passed": self.py_compile_passed,
            "ast_parse_passed": self.ast_parse_passed,
            "re_run_passed": self.re_run_passed,
            "self_validating_passed": self.self_validating_passed,
            "false_positive": self.false_positive,
            "syntax_error": self.syntax_error,
            "runtime_error": self.runtime_error,
            "output": self.output,
            "timing_ms": self.timing_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationResult":
        return cls(
            candidate_strategy=d.get("candidate_strategy", ""),
            py_compile_passed=d.get("py_compile_passed", False),
            ast_parse_passed=d.get("ast_parse_passed", False),
            re_run_passed=d.get("re_run_passed", False),
            self_validating_passed=d.get("self_validating_passed", False),
            false_positive=d.get("false_positive", False),
            syntax_error=d.get("syntax_error"),
            runtime_error=d.get("runtime_error"),
            output=d.get("output", ""),
            timing_ms=d.get("timing_ms", 0.0),
        )


class ErrorModel:
    """A single error test case for the benchmark framework.

    Attributes:
        case_id: unique identifier (e.g. "RUNTIME-001")
        family: error family (runtime, syntax, import, os, etc.)
        expected_exception: exception class name (e.g. "NameError")
        broken_code: Python code that triggers the error
        fixed_code: known-good fix (if available)
        description: human-readable description
        severity: 1-5
        platform_compat: list of platforms this case applies to
        python_versions: list of (major, minor) tuples this case applies to
        fix_candidates: list of FixCandidate objects
        validation_results: list of ValidationResult objects
        confidence: 0.0-1.0
        traceback_fingerprint: hash for dedup
        ast_info: structural analysis
        tags: list of string tags
        created_at: timestamp
        last_run_at: timestamp
        run_count: how many times this case has been run
        pass_count: how many times a fix was found
        fail_count: how many times no fix was found
        best_score: highest score achieved
        best_strategy: strategy that achieved best_score
    """

    def __init__(
        self,
        case_id: str = "",
        family: str = "",
        expected_exception: str = "",
        broken_code: str = "",
        fixed_code: str = "",
        description: str = "",
        severity: int = 3,
        platform_compat: Optional[List[str]] = None,
        python_versions: Optional[List[Tuple[int, int]]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.case_id = case_id
        self.family = family
        self.expected_exception = expected_exception
        self.broken_code = broken_code
        self.fixed_code = fixed_code
        self.description = description
        self.severity = severity
        self.platform_compat = platform_compat or ["Darwin", "Linux", "Windows"]
        self.python_versions = python_versions or [(3, 9), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14)]
        self.tags = tags or []
        self.fix_candidates: List[FixCandidate] = []
        self.validation_results: List[ValidationResult] = []
        self.confidence = Config.INITIAL_CONFIDENCE
        self.traceback_fingerprint = ""
        self.ast_info: Dict[str, Any] = {}
        self.created_at = datetime.utcnow().isoformat(timespec="seconds")
        self.last_run_at = ""
        self.run_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.best_score = 0
        self.best_strategy = ""
        self.triggered_exception = ""
        self.triggered_traceback = ""
        self.trigger_timing_ms = 0.0

    def is_compatible(self) -> bool:
        """Check if this case is compatible with the current platform + Python version."""
        if Config.PLATFORM_NAME not in self.platform_compat:
            return False
        if self.python_versions:
            if Config.CURRENT_PYTHON not in self.python_versions:
                return False
        return True

    def fingerprint(self) -> str:
        """Generate a traceback fingerprint for dedup.

        The fingerprint is based on:
        - expected_exception
        - family
        - a normalized version of broken_code (whitespace-stripped)
        This allows detecting duplicate patterns.
        """
        normalized = re.sub(r"\s+", " ", self.broken_code.strip())
        raw = f"{self.expected_exception}|{self.family}|{normalized}"
        return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]

    def ast_analysis(self) -> Dict[str, Any]:
        """Analyze the broken code's AST structure.

        Returns:
            dict with keys:
              - parseable: bool (can ast.parse succeed?)
              - node_count: int
              - node_types: list of str
              - has_class: bool
              - has_function: bool
              - has_import: bool
              - has_try: bool
              - has_async: bool
              - has_with: bool
              - max_depth: int
              - syntax_error: str or None
        """
        info: Dict[str, Any] = {
            "parseable": False,
            "node_count": 0,
            "node_types": [],
            "has_class": False,
            "has_function": False,
            "has_import": False,
            "has_try": False,
            "has_async": False,
            "has_with": False,
            "max_depth": 0,
            "syntax_error": None,
        }
        try:
            tree = ast.parse(self.broken_code)
            info["parseable"] = True
            node_types = set()
            max_depth = 0

            def walk(node, depth):
                nonlocal max_depth
                max_depth = max(max_depth, depth)
                info["node_count"] += 1
                node_types.add(type(node).__name__)
                if isinstance(node, ast.ClassDef):
                    info["has_class"] = True
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info["has_function"] = True
                if isinstance(node, ast.AsyncFunctionDef):
                    info["has_async"] = True
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    info["has_import"] = True
                if isinstance(node, ast.Try):
                    info["has_try"] = True
                if isinstance(node, ast.With):
                    info["has_with"] = True
                for child in ast.iter_child_nodes(node):
                    walk(child, depth + 1)

            walk(tree, 0)
            info["node_types"] = sorted(node_types)
            info["max_depth"] = max_depth
        except SyntaxError as exc:
            info["syntax_error"] = str(exc)
        except Exception as exc:
            info["syntax_error"] = str(exc)
        self.ast_info = info
        return info

    def trigger(self) -> Tuple[bool, str, str, float]:
        """Trigger the error by executing broken_code in a sandbox.

        Returns:
            (success, exception_name, traceback_text, timing_ms)
            success = True if the expected exception was raised
        """
        import time
        import subprocess
        import tempfile
        import os

        start = time.perf_counter()
        exception_name = ""
        traceback_text = ""

        fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bench_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(self.broken_code)
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=Config.SANDBOX_TIMEOUT_SEC,
            )
            if proc.returncode != 0:
                stderr = proc.stderr
                lines = stderr.strip().split("\n")
                for line in lines:
                    if line.startswith("Traceback"):
                        traceback_text = stderr
                        break
                if not traceback_text:
                    traceback_text = stderr
                match = re.search(r"(\w+Error|\w+Exception|SystemExit|KeyboardInterrupt|GeneratorExit|StopIteration|StopAsyncIteration|Warning):", stderr)
                if match:
                    exception_name = match.group(1)
                else:
                    for line in reversed(lines):
                        line = line.strip()
                        if line and not line.startswith(" ") and not line.startswith("^"):
                            exception_name = line
                            break
        except subprocess.TimeoutExpired:
            exception_name = "TimeoutError"
            traceback_text = "Execution timed out after {}s".format(Config.SANDBOX_TIMEOUT_SEC)
        except Exception as exc:
            exception_name = type(exc).__name__
            traceback_text = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
        finally:
            if Config.SANDBOX_CLEANUP and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        elapsed = time.perf_counter() - start
        timing_ms = round(elapsed * 1000, Config.TIMING_PRECISION)

        self.triggered_exception = exception_name
        self.triggered_traceback = traceback_text
        self.trigger_timing_ms = timing_ms
        self.traceback_fingerprint = self.fingerprint()

        success = exception_name == self.expected_exception
        return (success, exception_name, traceback_text, timing_ms)

    def add_candidate(self, candidate: FixCandidate) -> None:
        """Add a fix candidate and update best score."""
        self.fix_candidates.append(candidate)
        if candidate.score > self.best_score:
            self.best_score = candidate.score
            self.best_strategy = candidate.strategy
        if candidate.passed:
            self.pass_count += 1
        else:
            self.fail_count += 1

    def add_validation(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.validation_results.append(result)

    def update_confidence(self, success: bool) -> None:
        """Update confidence based on success/failure.

        Success: confidence *= BOOST (capped at MAX)
        Failure: confidence *= DECAY (floored at MIN)
        """
        if success:
            self.confidence = min(
                self.confidence * Config.CONFIDENCE_BOOST,
                Config.MAX_CONFIDENCE,
            )
        else:
            self.confidence = max(
                self.confidence * Config.CONFIDENCE_DECAY,
                Config.MIN_CONFIDENCE,
            )

    def should_promote(self) -> bool:
        """Check if this case should be promoted to permanent knowledge."""
        return self.confidence >= Config.PROMOTE_THRESHOLD and self.pass_count >= 2

    def should_demote(self) -> bool:
        """Check if this case should be demoted."""
        return self.confidence <= Config.DEMOTE_THRESHOLD and self.run_count >= 3

    def is_duplicate_of(self, other: "ErrorModel") -> bool:
        """Check if this case is a duplicate of another."""
        return self.traceback_fingerprint == other.traceback_fingerprint

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "case_id": self.case_id,
            "family": self.family,
            "expected_exception": self.expected_exception,
            "broken_code": self.broken_code,
            "fixed_code": self.fixed_code,
            "description": self.description,
            "severity": self.severity,
            "platform_compat": self.platform_compat,
            "python_versions": self.python_versions,
            "tags": self.tags,
            "fix_candidates": [c.to_dict() for c in self.fix_candidates],
            "validation_results": [v.to_dict() for v in self.validation_results],
            "confidence": self.confidence,
            "traceback_fingerprint": self.traceback_fingerprint,
            "ast_info": self.ast_info,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "run_count": self.run_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "best_score": self.best_score,
            "best_strategy": self.best_strategy,
            "triggered_exception": self.triggered_exception,
            "triggered_traceback": self.triggered_traceback,
            "trigger_timing_ms": self.trigger_timing_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ErrorModel":
        """Deserialize from dict."""
        model = cls(
            case_id=d.get("case_id", ""),
            family=d.get("family", ""),
            expected_exception=d.get("expected_exception", ""),
            broken_code=d.get("broken_code", ""),
            fixed_code=d.get("fixed_code", ""),
            description=d.get("description", ""),
            severity=d.get("severity", 3),
            platform_compat=d.get("platform_compat"),
            python_versions=[tuple(v) for v in d.get("python_versions", [])] or None,
            tags=d.get("tags"),
        )
        model.fix_candidates = [FixCandidate.from_dict(c) for c in d.get("fix_candidates", [])]
        model.validation_results = [ValidationResult.from_dict(v) for v in d.get("validation_results", [])]
        model.confidence = d.get("confidence", Config.INITIAL_CONFIDENCE)
        model.traceback_fingerprint = d.get("traceback_fingerprint", "")
        model.ast_info = d.get("ast_info", {})
        model.created_at = d.get("created_at", "")
        model.last_run_at = d.get("last_run_at", "")
        model.run_count = d.get("run_count", 0)
        model.pass_count = d.get("pass_count", 0)
        model.fail_count = d.get("fail_count", 0)
        model.best_score = d.get("best_score", 0)
        model.best_strategy = d.get("best_strategy", "")
        model.triggered_exception = d.get("triggered_exception", "")
        model.triggered_traceback = d.get("triggered_traceback", "")
        model.trigger_timing_ms = d.get("trigger_timing_ms", 0.0)
        return model

    def to_bcl(self) -> str:
        """Serialize to BCL packet."""
        lines = []
        lines.append("[@TEST_CASE]{")
        lines.append("[@CASE_ID]{" + self.case_id + "}")
        lines.append("[@FAMILY]{" + self.family + "}")
        lines.append("[@EXPECTED]{" + self.expected_exception + "}")
        lines.append("[@SEVERITY]{" + str(self.severity) + "}")
        lines.append("[@CONFIDENCE]{" + str(round(self.confidence, 4)) + "}")
        lines.append("[@RUN_COUNT]{" + str(self.run_count) + "}")
        lines.append("[@PASS_COUNT]{" + str(self.pass_count) + "}")
        lines.append("[@FAIL_COUNT]{" + str(self.fail_count) + "}")
        lines.append("[@BEST_SCORE]{" + str(self.best_score) + "}")
        lines.append("[@BEST_STRATEGY]{" + self.best_strategy + "}")
        lines.append("[@FINGERPRINT]{" + self.traceback_fingerprint + "}")
        if self.description:
            lines.append("[@DESCRIPTION]{" + self.description + "}")
        if self.tags:
            lines.append("[@TAGS]{" + ",".join(self.tags) + "}")
        lines.append("[@BROKEN_CODE]{" + self.broken_code.replace("{", "(").replace("}", ")") + "}")
        if self.fixed_code:
            lines.append("[@FIXED_CODE]{" + self.fixed_code.replace("{", "(").replace("}", ")") + "}")
        lines.append("}")
        return "".join(lines)

    @classmethod
    def from_bcl(cls, bcl: str) -> "ErrorModel":
        """Deserialize from BCL packet."""
        tags = {
            "CASE_ID": "", "FAMILY": "", "EXPECTED": "", "SEVERITY": "3",
            "CONFIDENCE": "0.5", "RUN_COUNT": "0", "PASS_COUNT": "0",
            "FAIL_COUNT": "0", "BEST_SCORE": "0", "BEST_STRATEGY": "",
            "FINGERPRINT": "", "DESCRIPTION": "", "TAGS": "",
            "BROKEN_CODE": "", "FIXED_CODE": "",
        }
        for key in tags:
            pattern = r"\[@" + key + r"\]\{([^}]*)\}"
            match = re.search(pattern, bcl)
            if match:
                tags[key] = match.group(1)
        model = cls(
            case_id=tags["CASE_ID"],
            family=tags["FAMILY"],
            expected_exception=tags["EXPECTED"],
            broken_code=tags["BROKEN_CODE"].replace("(", "{").replace(")", "}"),
            fixed_code=tags["FIXED_CODE"].replace("(", "{").replace(")", "}") if tags["FIXED_CODE"] else "",
            description=tags["DESCRIPTION"],
            severity=int(tags["SEVERITY"]),
            tags=tags["TAGS"].split(",") if tags["TAGS"] else [],
        )
        model.confidence = float(tags["CONFIDENCE"])
        model.run_count = int(tags["RUN_COUNT"])
        model.pass_count = int(tags["PASS_COUNT"])
        model.fail_count = int(tags["FAIL_COUNT"])
        model.best_score = int(tags["BEST_SCORE"])
        model.best_strategy = tags["BEST_STRATEGY"]
        model.traceback_fingerprint = tags["FINGERPRINT"]
        return model

    def __repr__(self) -> str:
        status = "PASS" if self.pass_count > 0 else "FAIL" if self.run_count > 0 else "NEW"
        return "ErrorModel({}/{}, {}, conf={:.2f}, {}/{}/{})".format(
            self.case_id, self.family, self.expected_exception,
            self.confidence, self.run_count, self.pass_count, self.fail_count,
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, ErrorModel):
            return False
        return self.case_id == other.case_id

    def __hash__(self) -> int:
        return hash(self.case_id)


import sys
