#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/ClassTest.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="ClassTest wraps the ClassTester from Reports v4 for in-Python testing. Calls the bcl_tool binary via subprocess to run import, class, error, and state tests, plus coverage reports."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ClassTest.py" domain="dom_common" authority="ClassTest"}
#[@SUMMARY]{summary="ClassTest — Wraps ClassTester (Reports v4) via bcl_tool subprocess. Runs test, test_class, test_method, assert_pass, assert_no_errors, coverage commands. Parses BCL output with regex."}
#[@CLASS]{class="ClassTest" domain="dom_common" authority="tester"}
#[@METHOD]{method="test" type="test"}
#[@METHOD]{method="test_class" type="test"}
#[@METHOD]{method="test_method" type="test"}
#[@METHOD]{method="assert_pass" type="assert"}
#[@METHOD]{method="assert_no_errors" type="assert"}
#[@METHOD]{method="coverage" type="report"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}

"""ClassTest — Wraps ClassTester (Reports v4) via bcl_tool subprocess.

Calls the bcl_tool binary to run import, class, error, and state
tests on a target path. Parses BCL output using regex to extract
test results. Supports filtering by class or method, assertion of
pass/no-error status, and coverage reports from MySQL.
"""

import re
import subprocess

try:
    from Config import BCL_TOOL_PATH
except ImportError:
    from .Config import BCL_TOOL_PATH

# ── Error Codes ──
ERR_UNKNOWN_CMD = "TEST_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "TEST_BAD_PARAMS"
ERR_SUBPROCESS = "TEST_SUBPROCESS_ERROR"
ERR_PARSE = "TEST_PARSE_ERROR"
ERR_NOT_FOUND = "TEST_NOT_FOUND"
ERR_NO_TOOL = "TEST_NO_TOOL"

# ── BCL Command Templates ──
CMD_TEST = "reports test"
CMD_COVERAGE = "reports coverage"

# ── BCL Tags (from Reports v4 ClassTester) ──
TAG_IMPORT_TEST = "IMPORT_TEST"
TAG_CLASS_TEST = "CLASS_TEST"
TAG_ERROR_TEST = "ERROR_TEST"
TAG_STATE_TEST = "STATE_TEST"
TAG_SUMMARY = "SUMMARY"
TAG_CLASS_NAME = "CLASS"
TAG_METHOD = "METHOD"
TAG_PASSED = "PASSED"
TAG_FAILED = "FAILED"
TAG_FACTS = "FACTS"
TAG_ERRORS = "ERRORS"
TAG_RULES = "RULES"
TAG_CLASSES = "CLASSES"
TAG_METHODS = "METHODS"
TAG_RATIO = "RATIO"

# ── Regex for BCL tag extraction ──
RE_TAG = r'\[@TAG\]\{([^}]*)\}'


class ClassTest:
    """Wraps ClassTester (Reports v4) via bcl_tool subprocess."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.tool_path = BCL_TOOL_PATH
        self.state = {
            "class": "ClassTest",
            "initialized": True,
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "last_path": None,
            "last_error": None,
            "config": {},
        }

    def _p(self, label, value):
        """Helper to log state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "test": self.cmd_test,
            "test_class": self.cmd_test_class,
            "test_method": self.cmd_test_method,
            "assert_pass": self.cmd_assert_pass,
            "assert_no_errors": self.cmd_assert_no_errors,
            "coverage": self.cmd_coverage,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    # ── Commands ──

    def cmd_test(self, params):
        """Run full test suite on a path. Returns parsed BCL results."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'path'", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' key", 0))
        if not isinstance(path, str):
            return (0, None, (ERR_BAD_PARAMS, "path must be a string", 0))
        bcl_cmd = CMD_TEST + ' "[@PATH]{' + path + '}"'
        raw = self._run_bcl(bcl_cmd)
        if raw is None:
            return (0, None, (ERR_SUBPROCESS, "bcl_tool failed for path: " + path, 0))
        parsed = self._parse_test_output(raw)
        parsed["raw"] = raw
        self.state["last_path"] = path
        self.state["total_tests"] = self.state.get("total_tests", 0) + 1
        summary = parsed.get("summary", {})
        if summary.get("passed"):
            self.state["total_passed"] = self.state.get("total_passed", 0) + 1
        else:
            self.state["total_failed"] = self.state.get("total_failed", 0) + 1
        self._p("test", path)
        return (1, parsed, None)

    def cmd_test_class(self, params):
        """Run test, then filter results for a specific class."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        path = params.get("path")
        class_name = params.get("class_name")
        if path is None or class_name is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' or 'class_name'", 0))
        if not isinstance(path, str) or not isinstance(class_name, str):
            return (0, None, (ERR_BAD_PARAMS, "path and class_name must be strings", 0))
        test_result = self.cmd_test({"path": path})
        if test_result[0] != 1:
            return test_result
        data = test_result[1]
        class_tests = data.get("class_tests", [])
        matched = None
        for ct in class_tests:
            if ct.get("class") == class_name:
                matched = ct
                break
        if matched is None:
            return (0, None, (ERR_NOT_FOUND, "class not found: " + class_name, 0))
        result = {
            "class": matched.get("class"),
            "methods": matched.get("methods", []),
            "passed": matched.get("passed", False),
        }
        self._p("test_class", class_name)
        return (1, result, None)

    def cmd_test_method(self, params):
        """Run test, then filter results for a specific method."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        path = params.get("path")
        class_name = params.get("class_name")
        method_name = params.get("method_name")
        if path is None or class_name is None or method_name is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path', 'class_name', or 'method_name'", 0))
        if not isinstance(path, str) or not isinstance(class_name, str) or not isinstance(method_name, str):
            return (0, None, (ERR_BAD_PARAMS, "path, class_name, method_name must be strings", 0))
        class_result = self.cmd_test_class({"path": path, "class_name": class_name})
        if class_result[0] != 1:
            return class_result
        cdata = class_result[1]
        methods = cdata.get("methods", [])
        matched = None
        for m in methods:
            if m.get("method") == method_name:
                matched = m
                break
        if matched is None:
            return (0, None, (ERR_NOT_FOUND, "method not found: " + method_name, 0))
        result = {
            "method": matched.get("method"),
            "passed": matched.get("passed", False),
            "facts": matched.get("facts", 0),
            "errors": matched.get("errors", 0),
        }
        self._p("test_method", method_name)
        return (1, result, None)

    def cmd_assert_pass(self, params):
        """Run test, return whether all tests passed, list failures if any."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'path'", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' key", 0))
        if not isinstance(path, str):
            return (0, None, (ERR_BAD_PARAMS, "path must be a string", 0))
        test_result = self.cmd_test({"path": path})
        if test_result[0] != 1:
            return test_result
        data = test_result[1]
        summary = data.get("summary", {})
        all_pass = summary.get("passed", False)
        failures = []
        class_tests = data.get("class_tests", [])
        for ct in class_tests:
            if not ct.get("passed", False):
                failures.append({
                    "class": ct.get("class"),
                    "methods": [m for m in ct.get("methods", []) if not m.get("passed", False)],
                })
        error_test = data.get("error_test", {})
        if error_test.get("has_errors", False):
            all_pass = False
            failures.append({"error_test": error_test})
        result = {"all_pass": all_pass, "failures": failures}
        self._p("assert_pass", all_pass)
        return (1, result, None)

    def cmd_assert_no_errors(self, params):
        """Run test, check only the error test result."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'path'", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path' key", 0))
        if not isinstance(path, str):
            return (0, None, (ERR_BAD_PARAMS, "path must be a string", 0))
        test_result = self.cmd_test({"path": path})
        if test_result[0] != 1:
            return test_result
        data = test_result[1]
        error_test = data.get("error_test", {})
        has_errors = error_test.get("has_errors", False)
        errors = error_test.get("errors", [])
        result = {"has_errors": has_errors, "errors": errors}
        self._p("assert_no_errors", not has_errors)
        return (1, result, None)

    def cmd_coverage(self, params):
        """Run coverage report from MySQL via bcl_tool."""
        bcl_cmd = CMD_COVERAGE
        raw = self._run_bcl(bcl_cmd)
        if raw is None:
            return (0, None, (ERR_SUBPROCESS, "bcl_tool failed for coverage", 0))
        rules = self._extract_int(raw, TAG_RULES)
        classes = self._extract_int(raw, TAG_CLASSES)
        methods = self._extract_int(raw, TAG_METHODS)
        ratio = self._extract_int(raw, TAG_RATIO)
        result = {
            "rules": rules,
            "classes": classes,
            "methods": methods,
            "ratio": ratio,
        }
        self._p("coverage", ratio)
        return (1, result, None)

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        self.state["config"] = params
        if "tool_path" in params and isinstance(params["tool_path"], str):
            self.tool_path = params["tool_path"]
        self._p("config", list(params.keys()))
        return (1, None, None)

    # ── Internal helpers ──

    def _run_bcl(self, bcl_cmd):
        """Run bcl_tool with a BCL command string. Returns stdout or None."""
        if self.tool_path is None or self.tool_path == "":
            self.state["last_error"] = "no tool path"
            return None
        full_cmd = self.tool_path + " " + bcl_cmd
        try:
            proc = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            self.state["last_error"] = "bcl_tool not found"
            return None
        except subprocess.TimeoutExpired:
            self.state["last_error"] = "bcl_tool timed out"
            return None
        except OSError:
            self.state["last_error"] = "bcl_tool os error"
            return None
        if proc.returncode != 0:
            self.state["last_error"] = "bcl_tool exit code " + str(proc.returncode)
            return None
        return proc.stdout

    def _parse_test_output(self, raw):
        """Parse BCL test output into structured dict."""
        import_test = self._parse_block(raw, TAG_IMPORT_TEST)
        error_test = self._parse_error_test(raw)
        state_test = self._parse_block(raw, TAG_STATE_TEST)
        class_tests = self._parse_class_tests(raw)
        summary = self._parse_summary(raw)
        return {
            "import_test": import_test,
            "class_tests": class_tests,
            "error_test": error_test,
            "state_test": state_test,
            "summary": summary,
        }

    def _parse_block(self, raw, tag):
        """Extract a single BCL block as a dict of key/value pairs."""
        pattern = RE_TAG.replace("TAG", tag)
        matches = re.findall(pattern, raw)
        if len(matches) == 0:
            return {}
        block = matches[0]
        return self._extract_kv(block)

    def _parse_error_test(self, raw):
        """Parse the error test block, extracting has_errors and errors list."""
        block = self._parse_block(raw, TAG_ERROR_TEST)
        has_errors = False
        errors = []
        error_matches = re.findall(RE_TAG.replace("TAG", "ERROR"), raw)
        for em in error_matches:
            errors.append(em)
        if len(errors) > 0:
            has_errors = True
        if block.get("has_errors") == "true" or block.get("has_errors") == "1":
            has_errors = True
        return {"has_errors": has_errors, "errors": errors, "raw": block}

    def _parse_class_tests(self, raw):
        """Parse all class test blocks into a list of class result dicts."""
        pattern = RE_TAG.replace("TAG", TAG_CLASS_TEST)
        matches = re.findall(pattern, raw)
        class_tests = []
        for block in matches:
            kv = self._extract_kv(block)
            class_name = kv.get("class", kv.get("name", ""))
            passed = kv.get("passed", "false") in ("true", "1", "True")
            methods = self._parse_methods(block)
            class_tests.append({
                "class": class_name,
                "methods": methods,
                "passed": passed,
            })
        return class_tests

    def _parse_methods(self, block):
        """Parse method results from within a class test block."""
        pattern = RE_TAG.replace("TAG", TAG_METHOD)
        matches = re.findall(pattern, block)
        methods = []
        for m in matches:
            kv = self._extract_kv(m)
            passed = kv.get("passed", "false") in ("true", "1", "True")
            facts = self._to_int(kv.get("facts", "0"))
            errors = self._to_int(kv.get("errors", "0"))
            methods.append({
                "method": kv.get("method", kv.get("name", "")),
                "passed": passed,
                "facts": facts,
                "errors": errors,
            })
        return methods

    def _parse_summary(self, raw):
        """Parse the summary block for pass/fail counts."""
        block = self._parse_block(raw, TAG_SUMMARY)
        passed = block.get("passed", "false") in ("true", "1", "True")
        total = self._to_int(block.get("total", "0"))
        passed_count = self._to_int(block.get("passed_count", "0"))
        failed_count = self._to_int(block.get("failed_count", "0"))
        return {
            "passed": passed,
            "total": total,
            "passed_count": passed_count,
            "failed_count": failed_count,
        }

    def _extract_kv(self, block):
        """Extract all [@KEY]{value} pairs from a block into a dict."""
        result = {}
        pattern = r'\[@([A-Z_]+)\]\{([^}]*)\}'
        for match in re.finditer(pattern, block):
            key = match.group(1).lower()
            result[key] = match.group(2)
        return result

    def _extract_int(self, raw, tag):
        """Extract first integer value for a BCL tag from raw output."""
        pattern = RE_TAG.replace("TAG", tag)
        matches = re.findall(pattern, raw)
        if len(matches) == 0:
            return 0
        return self._to_int(matches[0].strip())

    def _to_int(self, value):
        """Safely convert a string to int. Returns 0 on failure."""
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except ValueError:
            return 0
