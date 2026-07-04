#[@GHOST] file=core/Dom_Bloodhound/test_error_ai_v3.py date=2026-07-04
#[@VBSTYLE] version=3
#[@FILEID] id=ERRORAI_V3
#[@SUMMARY] Real self-learning error AI — discovers fixes from candidates, validates by re-running
#[@CLASS] Scenario ErrorAI Benchmark
#[@METHOD] encounter try_fix build_scenarios run_benchmark Run

import os, sys, traceback, warnings, tempfile
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
from common import BCL


class Scenario:
    def __init__(self, name, family, broken_code, expected_error, fix_candidates, result_checker):
        self.name = name
        self.family = family
        self.broken_code = broken_code
        self.expected_error = expected_error
        self.fix_candidates = fix_candidates
        self.result_checker = result_checker

    def trigger(self):
        try:
            exec(self.broken_code, {})
            return False, None, "No error"
        except BaseException as e:
            return True, type(e).__name__, traceback.format_exc()

    def try_fix(self, fix_code):
        try:
            ns = {}
            exec(fix_code, ns)
        except BaseException as e:
            return False, False, f"fix raised {type(e).__name__}"
        try:
            correct = self.result_checker(ns)
        except BaseException as e:
            return True, False, f"checker raised {type(e).__name__}"
        return True, correct, "ok" if correct else "result wrong"


class ErrorAI:
    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.state = {"knowledge": {}, "encounters": 0, "fixes_found": 0,
                       "fixes_failed": 0, "no_fix_count": 0, "history": []}
        bcl_path = param.get("bcl_path", "error_ai_v3_knowledge.bcl") if param else "error_ai_v3_knowledge.bcl"
        self.state["bcl_path"] = bcl_path
        self.bcl = BCL(param={"file_path": bcl_path})
        self._load_knowledge()

    def Run(self, command, params=None):
        dispatch = {
            "encounter": lambda: self.encounter(params.get("scenario")),
            "get_stats": lambda: self.get_stats(),
            "report": lambda: self.report(),
        }
        if command in dispatch:
            return (1, dispatch[command](), None)
        return (0, None, (404, f"Unknown: {command}", 0))

    def _load_knowledge(self):
        for ct, d in self.bcl.read_all():
            if ct == "ERRORAI":
                p = d.get("pattern", "")
                if p:
                    self.state["knowledge"][p] = {
                        "best_fix": d.get("best_fix", ""),
                        "working": d.get("working_fixes", "").split("|") if d.get("working_fixes") else [],
                        "failed": d.get("failed_fixes", "").split("|") if d.get("failed_fixes") else [],
                        "success_count": int(d.get("success_count", "0")),
                        "fail_count": int(d.get("fail_count", "0")),
                        "confidence": float(d.get("confidence", "0.0")),
                        "encounters": int(d.get("encounters", "0")),
                    }

    def _save_knowledge(self):
        containers = []
        for p, k in self.state["knowledge"].items():
            containers.append(("ERRORAI", {
                "pattern": p,
                "best_fix": k.get("best_fix", ""),
                "working_fixes": "|".join(k.get("working", [])),
                "failed_fixes": "|".join(k.get("failed", [])),
                "success_count": str(k.get("success_count", 0)),
                "fail_count": str(k.get("fail_count", 0)),
                "confidence": f"{k.get('confidence', 0.0):.3f}",
                "encounters": str(k.get("encounters", 0)),
                "last_seen": datetime.now().isoformat(),
            }))
        self.bcl.rewrite_all(containers)

    def encounter(self, scenario):
        self.state["encounters"] += 1
        triggered, actual, tb = scenario.trigger()
        if not triggered:
            r = {"name": scenario.name, "triggered": False, "matched": False,
                 "fix_found": False, "fix_name": "N/A", "result_correct": False,
                 "detail": "not triggered", "learned": False}
            self.state["history"].append(r)
            return r

        matched = (actual == scenario.expected_error)
        pattern = scenario.name
        known = self.state["knowledge"].get(pattern)

        if known and known.get("best_fix"):
            for fname, fcode in scenario.fix_candidates:
                if fname == known["best_fix"]:
                    no_err, correct, detail = scenario.try_fix(fcode)
                    if no_err and correct:
                        known["success_count"] += 1
                        known["encounters"] += 1
                        known["confidence"] = known["success_count"] / max(1, known["success_count"] + known["fail_count"])
                        self.state["fixes_found"] += 1
                        self._save_knowledge()
                        r = {"name": scenario.name, "triggered": True, "matched": matched,
                             "fix_found": True, "fix_name": fname, "result_correct": True,
                             "detail": f"known fix works: {fname}", "learned": False}
                        self.state["history"].append(r)
                        return r
                    else:
                        known["fail_count"] += 1
                        known["encounters"] += 1
                        known["confidence"] = known["success_count"] / max(1, known["success_count"] + known["fail_count"])
                        known["best_fix"] = ""
                        self.state["fixes_failed"] += 1

        working = []
        failing = []
        for fname, fcode in scenario.fix_candidates:
            no_err, correct, detail = scenario.try_fix(fcode)
            if no_err and correct:
                working.append(fname)
            else:
                failing.append(fname)

        if working:
            self.state["fixes_found"] += 1
            self.state["knowledge"][pattern] = {
                "best_fix": working[0], "working": working, "failed": failing,
                "success_count": 1, "fail_count": 0,
                "confidence": 1.0 / len(scenario.fix_candidates),
                "encounters": 1,
            }
            detail = f"discovered: {working[0]} ({len(working)} work, {len(failing)} fail)"
            fix_name = working[0]
            result_correct = True
        else:
            self.state["no_fix_count"] += 1
            self.state["fixes_failed"] += 1
            self.state["knowledge"][pattern] = {
                "best_fix": "", "working": [], "failed": failing,
                "success_count": 0, "fail_count": len(failing),
                "confidence": 0.0, "encounters": 1,
            }
            detail = f"NO WORKING FIX ({len(failing)} tried, all failed)"
            fix_name = "NONE"
            result_correct = False

        self._save_knowledge()
        r = {"name": scenario.name, "triggered": True, "matched": matched,
             "fix_found": len(working) > 0, "fix_name": fix_name,
             "result_correct": result_correct, "detail": detail, "learned": True}
        self.state["history"].append(r)
        return r

    def get_stats(self):
        k = self.state["knowledge"]
        total = len(k)
        with_fix = sum(1 for v in k.values() if v.get("best_fix"))
        without_fix = sum(1 for v in k.values() if not v.get("best_fix"))
        avg_conf = sum(v.get("confidence", 0) for v in k.values()) / max(1, total)
        return {"encounters": self.state["encounters"],
                "fixes_found": self.state["fixes_found"],
                "fixes_failed": self.state["fixes_failed"],
                "no_fix_count": self.state["no_fix_count"],
                "known_patterns": total, "with_fix": with_fix,
                "without_fix": without_fix, "avg_confidence": avg_conf}

    def report(self):
        s = self.get_stats()
        lines = [f"Encounters: {s['encounters']}", f"Fixes found: {s['fixes_found']}",
                 f"Fixes failed: {s['fixes_failed']}", f"No fix: {s['no_fix_count']}",
                 f"Known: {s['known_patterns']}", f"With fix: {s['with_fix']}",
                 f"Without fix: {s['without_fix']}", f"Avg conf: {s['avg_confidence']:.3f}", ""]
        for p, k in sorted(self.state["knowledge"].items()):
            lines.append(f"  {p:25s} best={k.get('best_fix','NONE'):18s} conf={k.get('confidence',0):.2f} enc={k.get('encounters',0)}")
        return "\n".join(lines)


def _cleanup_temp_files():
    tmp = tempfile.gettempdir()
    for f in os.listdir(tmp):
        if f.startswith('nonexist_v3') or f.startswith('also_nonexist') or f.startswith('v3_test'):
            try:
                os.remove(os.path.join(tmp, f))
            except OSError:
                pass


def build_scenarios():
    _cleanup_temp_files()
    tmp = tempfile.gettempdir()
    S = Scenario
    scenarios = []

    scenarios.append(S("ZeroDivisionError", "arithmetic",
        "result = 10 / 0", "ZeroDivisionError",
        [("safe_div", "divisor = 1\nresult = 10 / divisor"),
         ("check_zero", "divisor = 0\nresult = 10 / divisor if divisor != 0 else 0"),
         ("wrong_op", "result = 10 * 0"),
         ("skip", "result = 10"),
         ("still_bad", "result = 10 / 0")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), (int, float)) and ns.get("result") != 10))

    scenarios.append(S("KeyError", "runtime",
        "d = {'a': 1}\nvalue = d['b']", "KeyError",
        [("add_key", "d = {'a': 1, 'b': 2}\nvalue = d['b']"),
         ("use_get", "d = {'a': 1}\nvalue = d.get('b', 0)"),
         ("use_default", "d = {'a': 1}\nvalue = d.get('b') or 0"),
         ("wrong_key", "d = {'a': 1}\nvalue = d['a']"),
         ("still_bad", "d = {'a': 1}\nvalue = d['b']")],
        lambda ns: ns.get("value") is not None and ns.get("value") != 1))

    scenarios.append(S("IndexError", "runtime",
        "lst = [1, 2]\nvalue = lst[10]", "IndexError",
        [("bounds_check", "lst = [1, 2]\nvalue = lst[min(10, len(lst)-1)]"),
         ("extend_list", "lst = [1, 2]\nlst.extend([0]*10)\nvalue = lst[10]"),
         ("wrong_index", "lst = [1, 2]\nvalue = lst[0]"),
         ("still_bad", "lst = [1, 2]\nvalue = lst[10]"),
         ("empty_fix", "lst = [1, 2]\nvalue = None")],
        lambda ns: ns.get("value") is not None and ns.get("value") in (1, 2, 0)))

    scenarios.append(S("TypeError", "runtime",
        "result = 'hello' + 5", "TypeError",
        [("cast_int", "result = 'hello' + str(5)"),
         ("cast_str", "result = str('hello') + str(5)"),
         ("wrong_order", "result = str(5) + 'hello'"),
         ("wrong_op", "result = 'hello' * 5"),
         ("still_bad", "result = 'hello' + 5")],
        lambda ns: ns.get("result") == "hello5"))

    scenarios.append(S("ValueError", "runtime",
        "result = int('abc')", "ValueError",
        [("valid_input", "result = int('123')"),
         ("hex_parse", "result = int('abc', 16)"),
         ("try_except", "try:\n    result = int('abc')\nexcept ValueError:\n    result = 0"),
         ("still_bad", "result = int('abc')"),
         ("wrong_fix", "result = float('abc')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), (int, float)) and ns.get("result") > 0))

    scenarios.append(S("NameError", "runtime",
        "result = undefined_var_xyz", "NameError",
        [("define_var", "undefined_var_xyz = 42\nresult = undefined_var_xyz"),
         ("use_literal", "result = 42"),
         ("wrong_name", "result = other_var"),
         ("still_bad", "result = undefined_var_xyz"),
         ("string_fix", "result = 'undefined_var_xyz'")],
        lambda ns: ns.get("result") == 42))

    scenarios.append(S("AttributeError", "runtime",
        "x = 5\nx.append(3)", "AttributeError",
        [("use_list", "x = [5]\nx.append(3)\nresult = x"),
         ("use_extend", "x = [5]\nx.extend([3])\nresult = x"),
         ("wrong_method", "x = 5\nresult = x + 3"),
         ("still_bad", "x = 5\nx.append(3)"),
         ("wrong_type", "x = '5'\nresult = x + '3'")],
        lambda ns: ns.get("result") == [5, 3] or ns.get("x") == [5, 3]))

    unique_file = f"{tmp}/v3_test_{datetime.now().strftime('%H%M%S%f')}_nonexist.txt"
    scenarios.append(S("FileNotFoundError", "os",
        f"f = open('{unique_file}')\ndata = f.read()", "FileNotFoundError",
        [("create_file", f"with open('{unique_file}', 'w') as f:\n    f.write('created')\nf = open('{unique_file}')\ndata = f.read()"),
         ("use_exists", f"import os\ndata = 'default' if not os.path.exists('{unique_file}') else open('{unique_file}').read()"),
         ("wrong_path", f"f = open('{tmp}/also_nonexist_{datetime.now().strftime('%H%M%S%f')}.txt')\ndata = f.read()"),
         ("still_bad", f"f = open('{unique_file}')\ndata = f.read()"),
         ("skip_read", "data = ''")],
        lambda ns: ns.get("data") is not None and len(ns.get("data", "")) > 0))

    scenarios.append(S("OverflowError", "arithmetic",
        "result = 10.0 ** 10000", "OverflowError",
        [("small_exp", "result = 10.0 ** 100"),
         ("use_int", "result = 10 ** 10000"),
         ("use_math", "import math\nresult = math.pow(10.0, 100)"),
         ("still_bad", "result = 10.0 ** 10000"),
         ("wrong_fix", "result = 10.0 ** 100000")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), (int, float)) and ns.get("result") > 0))

    scenarios.append(S("RecursionError", "runtime",
        "def f():\n    return f()\nresult = f()", "RecursionError",
        [("add_base_case", "def f(n=0):\n    return n if n > 100 else f(n+1)\nresult = f()"),
         ("use_loop", "result = 100"),
         ("wrong_fix", "def f():\n    return f()\nresult = f()"),
         ("add_limit", "import sys\nsys.setrecursionlimit(100)\ndef f(n=0):\n    return n if n > 50 else f(n+1)\nresult = f()"),
         ("still_bad", "def f():\n    return f()\nresult = f()")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), int)))

    scenarios.append(S("StopIteration", "runtime",
        "it = iter([1])\nfirst = next(it)\nsecond = next(it)", "StopIteration",
        [("bigger_iter", "it = iter([1, 2])\nfirst = next(it)\nsecond = next(it)"),
         ("use_default", "it = iter([1])\nfirst = next(it)\nsecond = next(it, None)"),
         ("use_for", "it = iter([1])\nfirst = next(it)\nsecond = None\nfor x in it:\n    second = x"),
         ("still_bad", "it = iter([1])\nfirst = next(it)\nsecond = next(it)"),
         ("wrong_fix", "it = iter([1])\nfirst = next(it)\nsecond = first")],
        lambda ns: ns.get("second") is not None and ns.get("second") != ns.get("first")))

    scenarios.append(S("AssertionError", "runtime",
        "assert 1 == 2", "AssertionError",
        [("fix_assert", "assert 1 == 1"),
         ("remove_assert", "pass"),
         ("fix_value", "x = 1\nassert x == 1"),
         ("still_bad", "assert 1 == 2"),
         ("wrong_fix", "assert 2 == 3")],
        lambda ns: True))

    scenarios.append(S("UnicodeDecodeError", "unicode",
        "data = b'\\xff\\xfe'.decode('utf-8')", "UnicodeDecodeError",
        [("use_replace", "data = b'\\xff\\xfe'.decode('utf-8', errors='replace')"),
         ("use_ignore", "data = b'\\xff\\xfe'.decode('utf-8', errors='ignore')"),
         ("use_latin1", "data = b'\\xff\\xfe'.decode('latin-1')"),
         ("still_bad", "data = b'\\xff\\xfe'.decode('utf-8')"),
         ("wrong_fix", "data = b'\\xff\\xfe'.decode('ascii')")],
        lambda ns: ns.get("data") is not None and isinstance(ns.get("data"), str)))

    scenarios.append(S("TypeErrorArgs", "runtime",
        "result = len(42)", "TypeError",
        [("convert_str", "result = len(str(42))"),
         ("convert_list", "result = len([42])"),
         ("use_str", "result = len('42')"),
         ("still_bad", "result = len(42)"),
         ("wrong_fix", "result = 42")],
        lambda ns: ns.get("result") is not None and ns.get("result") > 0 and isinstance(ns.get("result"), int)))

    # GENUINE NO-FIX: segfault-like — all fixes produce wrong result or crash
    scenarios.append(S("NoFixAvailable", "runtime",
        "import ctypes\nptr = ctypes.cast(0, ctypes.POINTER(ctypes.c_int))\nresult = ptr[0]", "SegmentationError",
        [("try_except", "try:\n    import ctypes\n    ptr = ctypes.cast(0, ctypes.POINTER(ctypes.c_int))\n    result = ptr[0]\nexcept:\n    result = 'caught'"),
         ("use_null", "import ctypes\nptr = ctypes.pointer(ctypes.c_int(0))\nresult = ptr[0]"),
         ("still_bad", "import ctypes\nptr = ctypes.cast(0, ctypes.POINTER(ctypes.c_int))\nresult = ptr[0]"),
         ("wrong_fix", "import ctypes\nresult = ctypes.c_int(0)"),
         ("skip", "result = 0")],
        lambda ns: ns.get("result") is not None and ns.get("result") == 42))

    scenarios.append(S("KeyErrorNested", "runtime",
        "config = {'db': {'host': 'localhost'}}\nport = config['db']['port']", "KeyError",
        [("add_port", "config = {'db': {'host': 'localhost', 'port': 5432}}\nport = config['db']['port']"),
         ("use_get", "config = {'db': {'host': 'localhost'}}\nport = config['db'].get('port', 5432)"),
         ("use_default", "config = {'db': {'host': 'localhost'}}\nport = config.get('db', {}).get('port', 5432)"),
         ("wrong_key", "config = {'db': {'host': 'localhost'}}\nport = config['db']['host']"),
         ("still_bad", "config = {'db': {'host': 'localhost'}}\nport = config['db']['port']")],
        lambda ns: ns.get("port") is not None and ns.get("port") != "localhost"))

    scenarios.append(S("ValueErrorRange", "runtime",
        "import datetime\nresult = datetime.datetime(2026, 13, 1)", "ValueError",
        [("fix_month", "import datetime\nresult = datetime.datetime(2026, 12, 1)"),
         ("fix_to_jan", "import datetime\nresult = datetime.datetime(2026, 1, 1)"),
         ("use_try", "import datetime\ntry:\n    result = datetime.datetime(2026, 13, 1)\nexcept ValueError:\n    result = datetime.datetime(2026, 12, 1)"),
         ("still_bad", "import datetime\nresult = datetime.datetime(2026, 13, 1)"),
         ("wrong_fix", "import datetime\nresult = datetime.datetime(2026, 13, 32)")],
        lambda ns: ns.get("result") is not None and hasattr(ns.get("result"), "month") and ns.get("result").month <= 12))

    scenarios.append(S("ImportError", "runtime",
        "try:\n    from nonexistent_xyz import something\nexcept ModuleNotFoundError:\n    raise ImportError('forced')", "ImportError",
        [("use_stdlib", "import json\nresult = json.dumps({'ok': True})"),
         ("try_except", "try:\n    from nonexistent_xyz import something\nexcept ImportError:\n    result = 'handled'"),
         ("wrong_fix", "from nonexistent_xyz import something_else"),
         ("still_bad", "try:\n    from nonexistent_xyz import something\nexcept ModuleNotFoundError:\n    raise ImportError('forced')"),
         ("skip_import", "result = 'no import'")],
        lambda ns: ns.get("result") is not None))

    scenarios.append(S("RuntimeError", "runtime",
        "raise RuntimeError('custom error')", "RuntimeError",
        [("catch_it", "try:\n    raise RuntimeError('custom error')\nexcept RuntimeError:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("raise_diff", "try:\n    raise RuntimeError('custom error')\nexcept RuntimeError as e:\n    result = str(e)"),
         ("still_bad", "raise RuntimeError('custom error')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    scenarios.append(S("SyntaxError", "syntax",
        "exec('def broken(:')", "SyntaxError",
        [("fix_syntax", "exec('def fixed():\\n    pass')"),
         ("fix_return", "exec('def fixed():\\n    return None')"),
         ("still_bad", "exec('def broken(:')"),
         ("wrong_fix", "exec('def broken() pass')"),
         ("remove_def", "exec('x = 1')")],
        lambda ns: True))

    # --- 20 MORE SCENARIOS ---

    # 21. PermissionError
    scenarios.append(S("PermissionError", "os",
        f"f = open('/etc/sudoers', 'w')\ndata = f.write('test')", "PermissionError",
        [("use_tmp", f"f = open('{tmp}/v3_perm_ok.txt', 'w')\ndata = f.write('test')"),
         ("check_perm", "import os\nif os.access('/etc/sudoers', os.W_OK):\n    f = open('/etc/sudoers', 'w')\n    data = f.write('test')\nelse:\n    data = 'no_perm'"),
         ("try_except", "try:\n    f = open('/etc/sudoers', 'w')\n    data = f.write('test')\nexcept PermissionError:\n    data = 'handled'"),
         ("still_bad", f"f = open('/etc/sudoers', 'w')\ndata = f.write('test')"),
         ("wrong_fix", "data = 'test'")],
        lambda ns: ns.get("data") is not None))

    # 22. IsADirectoryError
    scenarios.append(S("IsADirectoryError", "os",
        f"f = open('/tmp')\ndata = f.read()", "IsADirectoryError",
        [("use_file", f"f = open('{tmp}/v3_dir_ok.txt', 'w')\nf.write('ok')\nf.close()\nf = open('{tmp}/v3_dir_ok.txt')\ndata = f.read()"),
         ("list_dir", "import os\ndata = str(os.listdir('/tmp')[:5])"),
         ("try_except", "try:\n    f = open('/tmp')\n    data = f.read()\nexcept IsADirectoryError:\n    data = 'is_dir'"),
         ("still_bad", f"f = open('/tmp')\ndata = f.read()"),
         ("wrong_fix", "data = '/tmp'")],
        lambda ns: ns.get("data") is not None and isinstance(ns.get("data"), str) and len(ns.get("data", "")) > 0))

    # 23. UnicodeEncodeError
    scenarios.append(S("UnicodeEncodeError", "unicode",
        "data = '\\udcff'.encode('utf-8')", "UnicodeEncodeError",
        [("use_replace", "data = '\\udcff'.encode('utf-8', errors='replace')"),
         ("use_ignore", "data = '\\udcff'.encode('utf-8', errors='ignore')"),
         ("use_latin1", "data = '\\udcff'.encode('latin-1')"),
         ("still_bad", "data = '\\udcff'.encode('utf-8')"),
         ("wrong_fix", "data = '\\udcff'.encode('ascii')")],
        lambda ns: ns.get("data") is not None and isinstance(ns.get("data"), bytes)))

    # 24. ConnectionError
    scenarios.append(S("ConnectionError", "connection",
        "import socket\ns = socket.socket()\ns.settimeout(1)\ns.connect(('127.0.0.1', 59999))\nresult = s.recv(1024)", "ConnectionError",
        [("try_except", "import socket\ntry:\n    s = socket.socket()\n    s.settimeout(1)\n    s.connect(('127.0.0.1', 59999))\n    result = s.recv(1024)\nexcept ConnectionError:\n    result = 'conn_failed'"),
         ("use_timeout", "import socket\ntry:\n    s = socket.socket()\n    s.settimeout(0.1)\n    s.connect(('127.0.0.1', 59999))\n    result = s.recv(1024)\nexcept:\n    result = 'timeout'"),
         ("wrong_port", "import socket\ntry:\n    s = socket.socket()\n    s.settimeout(1)\n    s.connect(('127.0.0.1', 80))\n    result = s.recv(1024)\nexcept:\n    result = 'also_failed'"),
         ("still_bad", "import socket\ns = socket.socket()\ns.settimeout(1)\ns.connect(('127.0.0.1', 59999))\nresult = s.recv(1024)"),
         ("skip", "result = 'skipped'")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), (str, bytes)) and len(str(ns.get("result"))) > 0 and ns.get("result") != 'also_failed'))

    # 25. TimeoutError
    scenarios.append(S("TimeoutError", "connection",
        "import socket\ns = socket.socket()\ns.settimeout(0.001)\ns.connect(('8.8.8.8', 9999))\nresult = 'connected'", "TimeoutError",
        [("try_except", "import socket\ntry:\n    s = socket.socket()\n    s.settimeout(0.001)\n    s.connect(('8.8.8.8', 9999))\n    result = 'connected'\nexcept TimeoutError:\n    result = 'timed_out'"),
         ("longer_timeout", "import socket\ntry:\n    s = socket.socket()\n    s.settimeout(5)\n    s.connect(('8.8.8.8', 9999))\n    result = 'connected'\nexcept:\n    result = 'still_failed'"),
         ("skip", "result = 'skipped'"),
         ("still_bad", "import socket\ns = socket.socket()\ns.settimeout(0.001)\ns.connect(('8.8.8.8', 9999))\nresult = 'connected'"),
         ("wrong_fix", "result = 'connected'")],
        lambda ns: ns.get("result") is not None and ns.get("result") != 'connected'))

    # 26. NotImplementedError
    scenarios.append(S("NotImplementedError", "runtime",
        "class Animal:\n    def speak(self):\n        raise NotImplementedError()\na = Animal()\nresult = a.speak()", "NotImplementedError",
        [("implement", "class Animal:\n    def speak(self):\n        return 'roar'\na = Animal()\nresult = a.speak()"),
         ("override", "class Animal:\n    def speak(self):\n        raise NotImplementedError()\nclass Dog(Animal):\n    def speak(self):\n        return 'woof'\nd = Dog()\nresult = d.speak()"),
         ("try_except", "class Animal:\n    def speak(self):\n        raise NotImplementedError()\na = Animal()\ntry:\n    result = a.speak()\nexcept NotImplementedError:\n    result = 'not_impl'"),
         ("still_bad", "class Animal:\n    def speak(self):\n        raise NotImplementedError()\na = Animal()\nresult = a.speak()"),
         ("wrong_fix", "class Animal:\n    pass\na = Animal()\nresult = a")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str) and len(ns.get("result")) > 0))

    # 27. EOFError
    scenarios.append(S("EOFError", "runtime",
        "raise EOFError('end of input')", "EOFError",
        [("catch_it", "try:\n    raise EOFError('end of input')\nexcept EOFError:\n    result = 'caught_eof'"),
         ("dont_raise", "result = 'ok'"),
         ("use_default", "try:\n    raise EOFError('end of input')\nexcept EOFError as e:\n    result = str(e)"),
         ("still_bad", "raise EOFError('end of input')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 28. UnboundLocalError
    scenarios.append(S("UnboundLocalError", "runtime",
        "def f():\n    print(x)\n    x = 1\nresult = f()", "UnboundLocalError",
        [("init_first", "def f():\n    x = 1\n    print(x)\nresult = f()"),
         ("use_param", "def f(x=1):\n    print(x)\nresult = f()"),
         ("use_global", "x = 1\ndef f():\n    print(x)\nresult = f()"),
         ("still_bad", "def f():\n    print(x)\n    x = 1\nresult = f()"),
         ("wrong_fix", "def f():\n    result = 1\nf()")],
        lambda ns: ns.get("result") is None or ns.get("result") == 1))

    # 29. TabError
    scenarios.append(S("TabError", "syntax",
        "compile('def f():\\n\\tif True:\\n        pass\\n', '<t>', 'exec')", "TabError",
        [("fix_tabs", "compile('def f():\\n    if True:\\n        pass\\n', '<t>', 'exec')"),
         ("fix_all_tabs", "compile('def f():\\n\\tif True:\\n\\t\\tpass\\n', '<t>', 'exec')"),
         ("still_bad", "compile('def f():\\n\\tif True:\\n        pass\\n', '<t>', 'exec')"),
         ("wrong_fix", "compile('def f(): pass', '<t>', 'exec')"),
         ("skip", "x = 1")],
        lambda ns: True))

    # 30. GENUINE NO-FIX: impossible result required
    scenarios.append(S("NoFixImpossibleResult", "arithmetic",
        "result = 100 / 0", "ZeroDivisionError",
        [("safe_div", "result = 100 / 1"),
         ("check_zero", "result = 100 / 0 if 0 != 0 else 0"),
         ("still_bad", "result = 100 / 0"),
         ("wrong_op", "result = 100 * 0"),
         ("skip", "result = 100")],
        lambda ns: ns.get("result") is not None and ns.get("result") == -1))

    # 31. IndentationError
    scenarios.append(S("IndentationError", "syntax",
        "exec('def f():\\n   x = 1\\n    y = 2')", "IndentationError",
        [("fix_indent", "exec('def f():\\n    x = 1\\n    y = 2')"),
         ("fix_tabs", "exec('def f():\\n\\tx = 1\\n\\ty = 2')"),
         ("still_bad", "exec('def f():\\n   x = 1\\n    y = 2')"),
         ("wrong_fix", "exec('def f(): x = 1 y = 2')"),
         ("remove_func", "exec('x = 1\\ny = 2')")],
        lambda ns: True))

    # 32. ArithmeticError
    scenarios.append(S("ArithmeticError", "arithmetic",
        "raise ArithmeticError('calc failed')", "ArithmeticError",
        [("catch", "try:\n    raise ArithmeticError('calc failed')\nexcept ArithmeticError:\n    result = 'caught'"),
         ("dont_raise", "result = 1 + 1"),
         ("use_try", "try:\n    raise ArithmeticError('calc failed')\nexcept ArithmeticError as e:\n    result = str(e)"),
         ("still_bad", "raise ArithmeticError('calc failed')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None))

    # 33. FloatingPointError (triggers as ValueError)
    scenarios.append(S("FloatingPointError", "arithmetic",
        "import math\nresult = math.sqrt(-1)", "ValueError",
        [("use_abs", "import math\nresult = math.sqrt(abs(-1))"),
         ("use_cmath", "import cmath\nresult = cmath.sqrt(-1)"),
         ("try_except", "import math\ntry:\n    result = math.sqrt(-1)\nexcept ValueError:\n    result = 0"),
         ("still_bad", "import math\nresult = math.sqrt(-1)"),
         ("wrong_fix", "import math\nresult = math.sqrt(-2)")],
        lambda ns: ns.get("result") is not None))

    # 34. SystemExit
    scenarios.append(S("SystemExit", "system",
        "raise SystemExit(1)", "SystemExit",
        [("catch", "try:\n    raise SystemExit(1)\nexcept SystemExit:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("use_code", "try:\n    raise SystemExit(0)\nexcept SystemExit as e:\n    result = f'code={e.code}'"),
         ("still_bad", "raise SystemExit(1)"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 35. KeyboardInterrupt
    scenarios.append(S("KeyboardInterrupt", "system",
        "raise KeyboardInterrupt()", "KeyboardInterrupt",
        [("catch", "try:\n    raise KeyboardInterrupt()\nexcept KeyboardInterrupt:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("use_handler", "import signal\nresult = 'handler_set'"),
         ("still_bad", "raise KeyboardInterrupt()"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 36. GENUINE NO-FIX: MemoryError with impossible result
    scenarios.append(S("NoFixMemoryExhaustion", "runtime",
        "raise MemoryError('out of memory')", "MemoryError",
        [("catch", "try:\n    raise MemoryError('oom')\nexcept MemoryError:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("free_mem", "import gc\ngc.collect()\nresult = 'freed'"),
         ("still_bad", "raise MemoryError('out of memory')"),
         ("wrong_fix", "result = 42")],
        lambda ns: ns.get("result") is not None and ns.get("result") == 'IMPOSSIBLE_RESULT'))

    # 37. LookupError
    scenarios.append(S("LookupError", "runtime",
        "raise LookupError('lookup failed')", "LookupError",
        [("catch", "try:\n    raise LookupError('lookup failed')\nexcept LookupError:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("use_key", "try:\n    raise LookupError('lookup failed')\nexcept LookupError as e:\n    result = str(e)"),
         ("still_bad", "raise LookupError('lookup failed')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 38. BufferError
    scenarios.append(S("BufferError", "runtime",
        "raise BufferError('buffer issue')", "BufferError",
        [("catch", "try:\n    raise BufferError('buffer issue')\nexcept BufferError:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("use_msg", "try:\n    raise BufferError('buffer issue')\nexcept BufferError as e:\n    result = str(e)"),
         ("still_bad", "raise BufferError('buffer issue')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 39. ReferenceError
    scenarios.append(S("ReferenceError", "runtime",
        "import weakref\nclass O: pass\no = O()\np = weakref.proxy(o)\ndel o\nresult = str(p)", "ReferenceError",
        [("use_ref", "import weakref\nclass O: pass\no = O()\nr = weakref.ref(o)\nresult = str(r())"),
         ("keep_ref", "import weakref\nclass O: pass\no = O()\np = weakref.proxy(o)\nresult = str(p)\ndel o"),
         ("try_except", "import weakref\nclass O: pass\no = O()\np = weakref.proxy(o)\ndel o\ntry:\n    result = str(p)\nexcept ReferenceError:\n    result = 'dead_ref'"),
         ("still_bad", "import weakref\nclass O: pass\no = O()\np = weakref.proxy(o)\ndel o\nresult = str(p)"),
         ("wrong_fix", "result = 'ok'")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    # 40. GeneratorExit
    scenarios.append(S("GeneratorExit", "system",
        "raise GeneratorExit('test')", "GeneratorExit",
        [("catch", "try:\n    raise GeneratorExit('test')\nexcept GeneratorExit:\n    result = 'caught'"),
         ("dont_raise", "result = 'ok'"),
         ("use_msg", "try:\n    raise GeneratorExit('test')\nexcept GeneratorExit as e:\n    result = str(e)"),
         ("still_bad", "raise GeneratorExit('test')"),
         ("wrong_fix", "raise ValueError('wrong')")],
        lambda ns: ns.get("result") is not None and isinstance(ns.get("result"), str)))

    return scenarios


def run_benchmark(ai, scenarios):
    return [ai.encounter(s) for s in scenarios]


def render_results(results, run_num):
    console.print()
    console.print(Panel(f"[bold cyan]RUN #{run_num}[/bold cyan]", border_style="cyan"))
    table = Table(title=f"ErrorAI v3 — Run #{run_num}", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Error", style="red", width=22)
    table.add_column("Trig", justify="center", width=5)
    table.add_column("Match", justify="center", width=5)
    table.add_column("Fix", justify="center", width=5)
    table.add_column("Fix Name", width=16)
    table.add_column("Correct", justify="center", width=7)
    table.add_column("Detail", width=45)
    for i, r in enumerate(results):
        t = "[green]Y[/green]" if r["triggered"] else "[dim]N[/dim]"
        m = "[green]Y[/green]" if r["matched"] else "[red]N[/red]" if r["triggered"] else "[dim]-[/dim]"
        f = "[green]Y[/green]" if r["fix_found"] else "[red]N[/red]"
        c = "[green]Y[/green]" if r["result_correct"] else "[red]N[/red]"
        table.add_row(str(i+1), r["name"][:22], t, m, f, r["fix_name"][:16], c, r["detail"][:45])
    console.print(table)


def main():
    bcl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_ai_v3_knowledge.bcl")
    if os.path.exists(bcl_path):
        os.remove(bcl_path)

    console.print(Panel(
        "[bold cyan]ERROR AI v3 — REAL Self-Learning[/bold cyan]\n"
        "[dim]AI tries multiple fix candidates, validates results, learns which work[/dim]\n"
        "[dim]Some fixes are WRONG. Some scenarios have NO working fix.[/dim]",
        border_style="cyan"))

    scenarios = build_scenarios()
    console.print(f"\n[bold]{len(scenarios)}[/bold] scenarios loaded.\n")

    all_runs = []
    for run_num in range(1, 11):
        ai = ErrorAI(param={"bcl_path": bcl_path})
        results = run_benchmark(ai, scenarios)
        all_runs.append(results)
        render_results(results, run_num)
        stats = ai.get_stats()
        triggered = sum(1 for r in results if r["triggered"])
        matched = sum(1 for r in results if r["matched"])
        fixed = sum(1 for r in results if r["fix_found"])
        correct = sum(1 for r in results if r["result_correct"])
        no_fix = sum(1 for r in results if r["triggered"] and not r["fix_found"])
        console.print(f"\n  [cyan]Run #{run_num}:[/cyan] trig={triggered} match={matched} "
                      f"fixed=[green]{fixed}[/green] correct=[green]{correct}[/green] "
                      f"no_fix=[red]{no_fix}[/red] avg_conf=[yellow]{stats['avg_confidence']:.3f}[/yellow]\n")

    # Learning curve
    console.print(Panel("[bold]LEARNING CURVE[/bold]", border_style="green"))
    table = Table(box=box.ROUNDED)
    table.add_column("Error", style="red", width=22)
    for i in range(len(all_runs)):
        table.add_column(f"R{i+1}", justify="center", width=10)
    for si, s in enumerate(scenarios):
        row = [s.name[:22]]
        for run in all_runs:
            r = run[si]
            if not r["triggered"]:
                row.append("[dim]N/A[/dim]")
            elif r["fix_found"] and r["result_correct"]:
                row.append(f"[green]{r['fix_name'][:10]}[/green]")
            elif r["fix_found"]:
                row.append(f"[yellow]{r['fix_name'][:10]}[/yellow]")
            else:
                row.append("[red]NONE[/red]")
        table.add_row(*row)
    console.print(table)

    # Final summary
    console.print(Panel("[bold]FINAL SUMMARY[/bold]", border_style="yellow"))
    final = all_runs[-1]
    total = len(final)
    triggered = sum(1 for r in final if r["triggered"])
    matched = sum(1 for r in final if r["matched"])
    fixed = sum(1 for r in final if r["fix_found"])
    correct = sum(1 for r in final if r["result_correct"])
    no_fix = sum(1 for r in final if r["triggered"] and not r["fix_found"])

    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="bold")
    summary.add_row("Total scenarios", str(total))
    summary.add_row("Triggered", f"[green]{triggered}[/green]")
    summary.add_row("Matched", f"[green]{matched}[/green]")
    summary.add_row("Fix found", f"[green]{fixed}[/green]")
    summary.add_row("Result correct", f"[green]{correct}[/green]")
    summary.add_row("No fix found", f"[red]{no_fix}[/red]")
    summary.add_row("Fix rate", f"{fixed/triggered*100:.1f}%" if triggered else "N/A")
    summary.add_row("Correct rate", f"{correct/triggered*100:.1f}%" if triggered else "N/A")
    console.print(summary)

    # Show knowledge base
    console.print(f"\n[bold]Knowledge Base ({bcl_path}):[/bold]")
    ai_final = ErrorAI(param={"bcl_path": bcl_path})
    console.print(ai_final.report())

    console.print(f"\n[bold green]Done.[/bold green] {total} scenarios, {triggered} triggered, {fixed} fixed, {no_fix} no fix.")


if __name__ == "__main__":
    main()
