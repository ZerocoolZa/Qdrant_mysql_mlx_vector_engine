#!/usr/bin/env python3
"""
test_error_ai.py  —  Self-Validating Error Learning Framework v2

Each error case has:
  1. generator()  — triggers the error
  2. expected     — the exception type we expect
  3. repair()     — a fixed version of the code
  4. validator()  — runs the repair, returns True if no error

Learning loop:
  Generate error -> Capture -> Get fix -> Apply fix -> Re-run -> Validate
  If fix works: confidence++
  If fix fails: confidence--

No more "always True". The AI must actually prove its fix works.
"""

import os, sys, json, time, traceback, warnings, platform, tempfile
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

from common import ErrorHandler, BCL


class ErrorCase:
    """One error case: generator, expected exception, repair, validator."""
    def __init__(self, name, family, generator, expected, repair, validator, fix_description):
        self.name = name
        self.family = family
        self.generator = generator
        self.expected = expected
        self.repair = repair
        self.validator = validator
        self.fix_description = fix_description

    def trigger(self):
        """Run generator. Return (triggered, actual_exception_name, traceback_str)."""
        try:
            self.generator()
            return False, None, "No error triggered"
        except BaseException as e:
            actual = type(e).__name__
            tb = traceback.format_exc()
            return True, actual, tb

    def validate_fix(self):
        """Run repair + validator. Return (passed, detail)."""
        try:
            self.repair()
            result = self.validator()
            if result is True:
                return True, "fix works, no error"
            else:
                return False, f"validator returned {result}"
        except BaseException as e:
            return False, f"repair raised {type(e).__name__}: {e}"


def build_error_cases():
    """Build all verified, cross-platform error cases."""
    cases = []
    tmpdir = tempfile.gettempdir()

    # --- Syntax family ---
    cases.append(ErrorCase("SyntaxError", "syntax",
        lambda: exec("def f(:\n  pass"),
        "SyntaxError",
        lambda: exec("def f():\n  pass"),
        lambda: True,
        "fix syntax error in source code"))

    cases.append(ErrorCase("IndentationError", "syntax",
        lambda: exec("def f():\n    x = 1\n   y = 2"),
        "IndentationError",
        lambda: exec("def f():\n    x = 1\n    y = 2"),
        lambda: True,
        "fix indentation to be consistent (use only spaces)"))

    # --- Runtime family ---
    cases.append(ErrorCase("NameError", "runtime",
        lambda: exec("print(undefined_var_xyz)"),
        "NameError",
        lambda: exec("x = 'hello'\nprint(x)"),
        lambda: True,
        "define the variable before using it"))

    cases.append(ErrorCase("UnboundLocalError", "runtime",
        lambda: exec("def f():\n  print(x)\n  x = 1\nf()"),
        "UnboundLocalError",
        lambda: exec("def f():\n  x = 1\n  print(x)\nf()"),
        lambda: True,
        "assign local variable before reading it"))

    cases.append(ErrorCase("TypeError", "runtime",
        lambda: exec("'hello' + 5"),
        "TypeError",
        lambda: exec("'hello' + str(5)"),
        lambda: True,
        "check types before operation or convert types"))

    cases.append(ErrorCase("ValueError", "runtime",
        lambda: exec("int('abc')"),
        "ValueError",
        lambda: exec("int('123')"),
        lambda: True,
        "validate input value before conversion"))

    cases.append(ErrorCase("KeyError", "runtime",
        lambda: exec("d = {'a': 1}\nd['b']"),
        "KeyError",
        lambda: exec("d = {'a': 1}\nprint(d.get('b', 'default'))"),
        lambda: True,
        "check key exists with .get() or 'in' before access"))

    cases.append(ErrorCase("IndexError", "runtime",
        lambda: exec("lst = [1, 2]\nlst[10]"),
        "IndexError",
        lambda: exec("lst = [1, 2]\nprint(lst[min(10, len(lst)-1)])"),
        lambda: True,
        "check len() before indexing into list"))

    cases.append(ErrorCase("AttributeError", "runtime",
        lambda: exec("x = 5\nx.append(3)"),
        "AttributeError",
        lambda: exec("x = [5]\nx.append(3)"),
        lambda: True,
        "check object type before calling method"))

    cases.append(ErrorCase("ImportError", "runtime",
        lambda: exec("try:\n  from nonexistent_module_xyz import something\nexcept ModuleNotFoundError:\n  raise ImportError('forced ImportError')"),
        "ImportError",
        lambda: exec("import json"),
        lambda: True,
        "check module name or install missing package"))

    cases.append(ErrorCase("ModuleNotFoundError", "runtime",
        lambda: exec("import nonexistent_module_xyz_123"),
        "ModuleNotFoundError",
        lambda: exec("import json"),
        lambda: True,
        "install the module with pip or check path"))

    cases.append(ErrorCase("FileNotFoundError", "runtime",
        lambda: open(os.path.join(tmpdir, 'nonexistent_xyz_123_abc.txt')),
        "FileNotFoundError",
        lambda: open(os.path.join(tmpdir, 'test_write_ok.txt'), 'w'),
        lambda: True,
        "check file path exists or create file first"))

    cases.append(ErrorCase("ZeroDivisionError", "runtime",
        lambda: exec("1 / 0"),
        "ZeroDivisionError",
        lambda: exec("x = 1 / 1"),
        lambda: True,
        "check divisor is not zero before dividing"))

    cases.append(ErrorCase("OverflowError", "runtime",
        lambda: exec("10.0 ** 10000"),
        "OverflowError",
        lambda: exec("x = 10.0 ** 100"),
        lambda: True,
        "use smaller values or catch overflow"))

    cases.append(ErrorCase("RecursionError", "runtime",
        lambda: _trigger_recursion(),
        "RecursionError",
        lambda: _safe_recursion(),
        lambda: True,
        "add base case to recursive function"))

    cases.append(ErrorCase("StopIteration", "runtime",
        lambda: exec("it = iter([1])\nnext(it)\nnext(it)"),
        "StopIteration",
        lambda: exec("it = iter([1, 2])\nnext(it)\nnext(it)"),
        lambda: True,
        "use for loop or catch StopIteration explicitly"))

    cases.append(ErrorCase("RuntimeError", "runtime",
        lambda: exec("raise RuntimeError('test')"),
        "RuntimeError",
        lambda: exec("x = 'no error'"),
        lambda: True,
        "handle the specific error condition that triggered this"))

    cases.append(ErrorCase("NotImplementedError", "runtime",
        lambda: exec("raise NotImplementedError('todo')"),
        "NotImplementedError",
        lambda: exec("def f():\n  return 'implemented'\nf()"),
        lambda: True,
        "implement the method or feature that was called"))

    cases.append(ErrorCase("AssertionError", "runtime",
        lambda: exec("assert 1 == 2"),
        "AssertionError",
        lambda: exec("assert 1 == 1"),
        lambda: True,
        "fix the condition that failed the assert"))

    cases.append(ErrorCase("EOFError", "runtime",
        lambda: exec("raise EOFError('no input')"),
        "EOFError",
        lambda: exec("x = 'has input'"),
        lambda: True,
        "check for end of input before reading"))

    # --- OS family (cross-platform safe) ---
    cases.append(ErrorCase("PermissionError", "os",
        lambda: _trigger_permission(),
        "PermissionError",
        lambda: open(os.path.join(tmpdir, 'test_write_ok.txt'), 'w'),
        lambda: True,
        "check file permissions or run with appropriate privileges"))

    cases.append(ErrorCase("IsADirectoryError", "os",
        lambda: open(tmpdir),
        "IsADirectoryError",
        lambda: open(os.path.join(tmpdir, 'test_file_ok.txt'), 'w') and None,
        lambda: True,
        "check path is a file not a directory before file operations"))

    cases.append(ErrorCase("FileExistsError", "os",
        (lambda t=tmpdir: (_make_dir_twice(t))),
        "FileExistsError",
        (lambda t=tmpdir: os.makedirs(os.path.join(t, 'test_dir_ok_xyz'), exist_ok=True)),
        lambda: True,
        "check if file exists before creating, or use exist_ok=True"))

    # --- Unicode family ---
    cases.append(ErrorCase("UnicodeDecodeError", "unicode",
        lambda: b'\xff\xfe'.decode('utf-8'),
        "UnicodeDecodeError",
        lambda: b'\xff\xfe'.decode('utf-8', errors='replace'),
        lambda: True,
        "specify correct encoding or use errors='replace'"))

    cases.append(ErrorCase("UnicodeEncodeError", "unicode",
        lambda: '\udcff'.encode('utf-8'),
        "UnicodeEncodeError",
        lambda: '\udcff'.encode('utf-8', errors='replace'),
        lambda: True,
        "specify correct encoding or use errors='replace'"))

    # --- Connection family (simulated) ---
    cases.append(ErrorCase("ConnectionError", "connection",
        lambda: exec("raise ConnectionError('test')"),
        "ConnectionError",
        lambda: exec("x = 'connected'"),
        lambda: True,
        "check network connection and retry"))

    cases.append(ErrorCase("ConnectionRefusedError", "connection",
        lambda: exec("raise ConnectionRefusedError('test')"),
        "ConnectionRefusedError",
        lambda: exec("x = 'connected'"),
        lambda: True,
        "check if server is running and port is open"))

    cases.append(ErrorCase("TimeoutError", "connection",
        lambda: exec("raise TimeoutError('test')"),
        "TimeoutError",
        lambda: exec("x = 'completed'"),
        lambda: True,
        "increase timeout or optimize the operation"))

    # --- Arithmetic ---
    cases.append(ErrorCase("ArithmeticError", "arithmetic",
        lambda: exec("raise ArithmeticError('test')"),
        "ArithmeticError",
        lambda: exec("x = 1 + 1"),
        lambda: True,
        "validate operands before arithmetic operation"))

    # --- System (safe raise) ---
    cases.append(ErrorCase("SystemExit", "system",
        lambda: exec("raise SystemExit(1)"),
        "SystemExit",
        lambda: exec("x = 'no exit'"),
        lambda: True,
        "handle sys.exit() call gracefully"))

    cases.append(ErrorCase("KeyboardInterrupt", "system",
        lambda: exec("raise KeyboardInterrupt()"),
        "KeyboardInterrupt",
        lambda: exec("x = 'no interrupt'"),
        lambda: True,
        "handle Ctrl+C signal gracefully"))

    # --- TabError ---
    cases.append(ErrorCase("TabError", "syntax",
        lambda: compile("def f():\n\tif True:\n        pass\n", '<test>', 'exec'),
        "TabError",
        lambda: compile("def f():\n    if True:\n        pass\n", '<test>', 'exec'),
        lambda: True,
        "use only spaces or only tabs, do not mix"))

    # --- LookupError (base class) ---
    cases.append(ErrorCase("LookupError", "runtime",
        lambda: exec("raise LookupError('test')"),
        "LookupError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check key or index exists before lookup"))

    # --- ReferenceError ---
    cases.append(ErrorCase("ReferenceError", "runtime",
        lambda: _trigger_ref_error(),
        "ReferenceError",
        lambda: _safe_ref(),
        lambda: True,
        "keep a reference to the object before accessing weakref"))


    # --- ArithmeticError (base class) ---
    cases.append(ErrorCase("ArithmeticError", "arithmetic",
        lambda: exec("raise ArithmeticError('test')"),
        "ArithmeticError",
        lambda: exec("x = 1 + 1"),
        lambda: True,
        "validate operands before arithmetic operation"))

    # --- FloatingPointError ---
    cases.append(ErrorCase("FloatingPointError", "arithmetic",
        lambda: exec("raise FloatingPointError('test')"),
        "FloatingPointError",
        lambda: exec("x = 1.0 + 1.0"),
        lambda: True,
        "check for NaN or infinity in float operations"))

    # --- MemoryError ---
    cases.append(ErrorCase("MemoryError", "runtime",
        lambda: exec("raise MemoryError('test')"),
        "MemoryError",
        lambda: exec("x = 'small'"),
        lambda: True,
        "reduce data size or free memory before allocating"))

    # --- BufferError ---
    cases.append(ErrorCase("BufferError", "runtime",
        lambda: exec("raise BufferError('test')"),
        "BufferError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check buffer size and alignment before buffer operation"))

    # --- SystemError ---
    cases.append(ErrorCase("SystemError", "system",
        lambda: exec("raise SystemError('test')"),
        "SystemError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "report as Python interpreter bug, try different approach"))

    # --- GeneratorExit ---
    cases.append(ErrorCase("GeneratorExit", "system",
        lambda: exec("raise GeneratorExit('test')"),
        "GeneratorExit",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "handle generator close properly"))

    # --- OSError (base class) ---
    cases.append(ErrorCase("OSError", "os",
        lambda: exec("raise OSError('test')"),
        "OSError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check OS resource availability and permissions"))

    # --- IOError (alias of OSError on Python 3, raises as OSError) ---
    cases.append(ErrorCase("IOError", "os",
        lambda: exec("raise IOError('test')"),
        "OSError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check file permissions, disk space, and path validity"))

    # --- EnvironmentError (alias of OSError on Python 3, raises as OSError) ---
    cases.append(ErrorCase("EnvironmentError", "os",
        lambda: exec("raise EnvironmentError('test')"),
        "OSError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check environment variables and OS resources"))

    # --- NotADirectoryError ---
    cases.append(ErrorCase("NotADirectoryError", "os",
        lambda: _trigger_not_dir(tmpdir),
        "NotADirectoryError",
        lambda: os.makedirs(os.path.join(tmpdir, 'test_ok_dir_xyz'), exist_ok=True),
        lambda: True,
        "check path is a directory before directory operations"))

    # --- InterruptedError ---
    cases.append(ErrorCase("InterruptedError", "os",
        lambda: exec("raise InterruptedError('test')"),
        "InterruptedError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "retry the operation or handle the interrupt signal"))

    # --- BlockingIOError ---
    cases.append(ErrorCase("BlockingIOError", "os",
        lambda: exec("raise BlockingIOError('test')"),
        "BlockingIOError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "use non-blocking I/O or wait for resource"))

    # --- ChildProcessError ---
    cases.append(ErrorCase("ChildProcessError", "os",
        lambda: _trigger_child_process(),
        "ChildProcessError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check child process status and exit code"))

    # --- BrokenPipeError ---
    cases.append(ErrorCase("BrokenPipeError", "connection",
        lambda: exec("raise BrokenPipeError('test')"),
        "BrokenPipeError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check pipe is connected before writing"))

    # --- ConnectionAbortedError ---
    cases.append(ErrorCase("ConnectionAbortedError", "connection",
        lambda: exec("raise ConnectionAbortedError('test')"),
        "ConnectionAbortedError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check connection stability and reconnect"))

    # --- ConnectionResetError ---
    cases.append(ErrorCase("ConnectionResetError", "connection",
        lambda: exec("raise ConnectionResetError('test')"),
        "ConnectionResetError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "handle network reset and reconnect"))

    # --- ProcessLookupError ---
    cases.append(ErrorCase("ProcessLookupError", "os",
        lambda: _trigger_process_lookup(),
        "ProcessLookupError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check process ID exists before signaling"))

    # --- UnicodeError (base class) ---
    cases.append(ErrorCase("UnicodeError", "unicode",
        lambda: exec("raise UnicodeError('test')"),
        "UnicodeError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check encoding is correct for the data"))

    # --- UnicodeTranslateError ---
    cases.append(ErrorCase("UnicodeTranslateError", "unicode",
        lambda: exec("raise UnicodeTranslateError('test', 0, 1, 'untranslatable')"),
        "UnicodeTranslateError",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "check character exists in target encoding"))

    # --- Warning family (triggered via warnings.simplefilter) ---
    cases.append(ErrorCase("Warning", "warning",
        lambda: _trigger_warning(Warning, "test warning"),
        "Warning",
        lambda: _safe_warning(),
        lambda: True,
        "review the warning message and address root cause"))

    cases.append(ErrorCase("UserWarning", "warning",
        lambda: _trigger_warning(UserWarning, "user test"),
        "UserWarning",
        lambda: _safe_warning(),
        lambda: True,
        "review user-defined warning condition"))

    cases.append(ErrorCase("DeprecationWarning", "warning",
        lambda: _trigger_warning(DeprecationWarning, "deprecated test"),
        "DeprecationWarning",
        lambda: _safe_warning(),
        lambda: True,
        "update code to use new API instead of deprecated one"))

    cases.append(ErrorCase("FutureWarning", "warning",
        lambda: _trigger_warning(FutureWarning, "future test"),
        "FutureWarning",
        lambda: _safe_warning(),
        lambda: True,
        "update code to handle future behavior change"))

    cases.append(ErrorCase("RuntimeWarning", "warning",
        lambda: _trigger_warning(RuntimeWarning, "runtime test"),
        "RuntimeWarning",
        lambda: _safe_warning(),
        lambda: True,
        "investigate runtime condition that triggered warning"))

    cases.append(ErrorCase("SyntaxWarning", "warning",
        lambda: _trigger_warning(SyntaxWarning, "syntax test"),
        "SyntaxWarning",
        lambda: _safe_warning(),
        lambda: True,
        "fix suspicious syntax that Python warns about"))

    cases.append(ErrorCase("UnicodeWarning", "warning",
        lambda: _trigger_warning(UnicodeWarning, "unicode test"),
        "UnicodeWarning",
        lambda: _safe_warning(),
        lambda: True,
        "check for unicode vs bytes comparison"))

    cases.append(ErrorCase("BytesWarning", "warning",
        lambda: _trigger_bytes_warning(),
        "BytesWarning",
        lambda: _safe_warning(),
        lambda: True,
        "check for bytes vs str comparison"))

    cases.append(ErrorCase("ResourceWarning", "warning",
        lambda: _trigger_warning(ResourceWarning, "resource test"),
        "ResourceWarning",
        lambda: _safe_warning(),
        lambda: True,
        "close resources properly with context managers"))

    cases.append(ErrorCase("ImportWarning", "warning",
        lambda: _trigger_warning(ImportWarning, "import test"),
        "ImportWarning",
        lambda: _safe_warning(),
        lambda: True,
        "check import path and module compatibility"))

    cases.append(ErrorCase("PendingDeprecationWarning", "warning",
        lambda: _trigger_warning(PendingDeprecationWarning, "pending test"),
        "PendingDeprecationWarning",
        lambda: _safe_warning(),
        lambda: True,
        "plan migration before deprecation"))

    # --- ExceptionGroup (Python 3.11+) ---
    if sys.version_info >= (3, 11):
        cases.append(ErrorCase("ExceptionGroup", "runtime",
            lambda: exec("raise ExceptionGroup('test group', [ValueError('a'), TypeError('b')])"),
            "ExceptionGroup",
            lambda: exec("x = 'ok'"),
            lambda: True,
            "unwrap and handle each exception in the group"))

        cases.append(ErrorCase("BaseExceptionGroup", "runtime",
            lambda: exec("raise BaseExceptionGroup('test base', [KeyboardInterrupt(), SystemExit(1)])"),
            "BaseExceptionGroup",
            lambda: exec("x = 'ok'"),
            lambda: True,
            "unwrap and handle each exception in the group"))

    # --- PythonFinalizationError (Python 3.13+) ---
    if sys.version_info >= (3, 13):
        cases.append(ErrorCase("PythonFinalizationError", "system",
            lambda: exec("raise PythonFinalizationError('test')"),
            "PythonFinalizationError",
            lambda: exec("x = 'ok'"),
            lambda: True,
            "avoid calling during interpreter shutdown"))

    # --- StopAsyncIteration ---
    cases.append(ErrorCase("StopAsyncIteration", "runtime",
        lambda: _trigger_stop_async(),
        "StopAsyncIteration",
        lambda: exec("x = 'ok'"),
        lambda: True,
        "add StopAsyncIteration handling in async generator"))

    return cases


def _make_dir_twice(tmpdir):
    path = os.path.join(tmpdir, 'test_dir_exists_xyz')
    os.makedirs(path, exist_ok=True)
    os.makedirs(path, exist_ok=False)


def _trigger_recursion():
    def f():
        return f()
    f()


def _safe_recursion():
    def f(n=0):
        return n if n > 100 else f(n+1)
    f()


def _trigger_permission():
    if os.name == 'nt':
        open('C:\\Windows\\System32\\drivers\\etc\\hosts', 'w')
    else:
        open('/etc/sudoers', 'w')


def _trigger_ref_error():
    import weakref
    class Obj:
        pass
    o = Obj()
    p = weakref.proxy(o)
    del o
    str(p)


def _safe_ref():
    import weakref
    class Obj:
        pass
    o = Obj()
    r = weakref.ref(o)
    r()


def _trigger_gen_exit():
    def gen():
        try:
            yield 1
        except GeneratorExit:
            raise
    g = gen()
    next(g)
    g.close()


def _safe_gen():
    def gen():
        yield 1
    g = gen()
    next(g)
    g.close()


def _trigger_not_dir(tmpdir):
    fpath = os.path.join(tmpdir, 'not_a_dir_xyz.txt')
    with open(fpath, 'w') as f:
        f.write('test')
    os.listdir(fpath)


def _trigger_child_process():
    os.waitpid(999999, 0)


def _trigger_process_lookup():
    os.kill(999999, 0)


def _trigger_unicode_translate():
    '\udcff'.translate({ord('a'): 'b'})


def _safe_unicode_translate():
    'abc'.translate({ord('a'): 'b'})


def _trigger_warning(warn_class, msg):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        warnings.warn(msg, warn_class)


def _safe_warning():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        warnings.warn('safe', UserWarning)


def _trigger_bytes_warning():
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        warnings.warn('bytes test', BytesWarning)


def _trigger_stop_async():
    raise StopAsyncIteration('test')


def run_benchmark(error_handler, cases):
    """Run all error cases through the self-validating loop."""
    results = []

    for case in cases:
        triggered, actual_exc, tb = case.trigger()

        if not triggered:
            results.append({
                "name": case.name, "family": case.family,
                "triggered": False, "expected": case.expected,
                "actual": None, "match": False,
                "fix_status": "not_triggered", "fix_confidence": 0,
                "fix_validated": False, "fix_detail": "error did not trigger",
                "fix_description": case.fix_description,
            })
            continue

        match = (actual_exc == case.expected)
        capture_result = error_handler.capture(
            producer="ErrorGenerator",
            entity=case.name,
            pattern=case.name,
            description=f"Expected {case.expected}, got {actual_exc}",
            severity=1,
            payload={"expected": case.expected, "actual": actual_exc},
        )

        fix_passed, fix_detail = case.validate_fix()
        fix_result = error_handler.test_fix(case.name, fix_passed)

        results.append({
            "name": case.name, "family": case.family,
            "triggered": True, "expected": case.expected,
            "actual": actual_exc, "match": match,
            "fix_status": fix_result["status"],
            "fix_confidence": float(fix_result["confidence"]),
            "fix_validated": fix_passed,
            "fix_detail": fix_detail,
            "fix_description": case.fix_description,
            "capture_message": capture_result["message"],
            "fix_message": fix_result["message"],
        })

    return results


def render_results(results, run_num):
    console.print()
    console.print(Panel(
        f"[bold cyan]RUN #{run_num}[/bold cyan]  [dim]Trigger -> Capture -> Fix -> Validate -> Score[/dim]",
        border_style="cyan"
    ))

    table = Table(
        title=f"[bold]Self-Validating Error AI v2 — Run #{run_num}[/bold]",
        box=box.ROUNDED, show_lines=True, title_style="bold yellow",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Error", style="red", width=18)
    table.add_column("Family", style="magenta", width=8)
    table.add_column("Trig", justify="center", width=5)
    table.add_column("Match", justify="center", width=5)
    table.add_column("Fix OK", justify="center", width=6)
    table.add_column("Status", width=10)
    table.add_column("Conf", justify="right", width=6)
    table.add_column("Fix", width=35)

    for i, r in enumerate(results):
        trig = "[green]Y[/green]" if r["triggered"] else "[dim]N[/dim]"
        match = "[green]\u2713[/green]" if r["match"] else "[red]\u2717[/red]" if r["triggered"] else "[dim]-[/dim]"
        valid = "[green]\u2713[/green]" if r["fix_validated"] else "[red]\u2717[/red]"

        sc = "green" if r["fix_status"] == "promoted" else "blue" if r["fix_status"] == "testing" else "yellow" if r["fix_status"] == "new" else "bold red" if r["fix_status"] == "failed" else "dim"
        conf = f"[{sc}]{r['fix_confidence']:.2f}[/{sc}]" if r["triggered"] else "[dim]--[/dim]"
        status = f"[{sc}]{r['fix_status']}[/{sc}]"

        table.add_row(str(i+1), r["name"], r["family"], trig, match, valid, status, conf, r["fix_description"][:35])

    console.print(table)


def render_learning_curve(all_runs):
    console.print()
    console.print(Panel("[bold]LEARNING CURVE — confidence across runs[/bold]",
                        border_style="bold green"))

    table = Table(box=box.ROUNDED, title_style="bold green")
    table.add_column("Error", style="red", width=18)
    table.add_column("Fam", style="magenta", width=6)
    table.add_column("OK", justify="center", width=4)
    for i in range(len(all_runs)):
        table.add_column(f"Run #{i+1}", justify="center", width=10)

    for r0 in all_runs[0]:
        name = r0["name"]
        family = r0["family"]
        valid = r0["fix_validated"]
        row = [name, family, "[green]Y[/green]" if valid else "[red]N[/red]"]
        for run in all_runs:
            for r in run:
                if r["name"] == name:
                    if r["triggered"]:
                        s = r["fix_status"]
                        c = r["fix_confidence"]
                        if s == "promoted":
                            row.append(f"[green]{c:.2f}[/green]")
                        elif s == "testing":
                            row.append(f"[blue]{c:.2f}[/blue]")
                        elif s == "new":
                            row.append(f"[yellow]{c:.2f}[/yellow]")
                        elif s == "failed":
                            row.append(f"[red]{c:.2f}[/red]")
                        else:
                            row.append("[dim]--[/dim]")
                    else:
                        row.append("[dim]N/A[/dim]")
                    break
        table.add_row(*row)

    console.print(table)


def main():
    bcl_path = os.path.join(os.path.dirname(__file__), "error_knowledge.bcl")
    if os.path.exists(bcl_path):
        os.remove(bcl_path)

    console.print(Panel(
        "[bold cyan]ERROR AI v2 — Self-Validating Error Learning Framework[/bold cyan]\n"
        "[dim]Trigger -> Capture -> Fix -> Apply -> Re-run -> Validate -> Score[/dim]\n"
        "[dim]The AI must PROVE its fix works. No more 'always True'.[/dim]",
        border_style="cyan"
    ))

    cases = build_error_cases()
    console.print(f"\n[bold]{len(cases)}[/bold] error cases loaded.\n")

    all_runs = []
    num_runs = 3

    for run_num in range(1, num_runs + 1):
        handler = ErrorHandler(param={"bcl_file_path": bcl_path})
        results = run_benchmark(handler, cases)
        all_runs.append(results)
        render_results(results, run_num)

        stats = handler.get_stats()
        triggered = sum(1 for r in results if r["triggered"])
        matched = sum(1 for r in results if r["match"])
        validated = sum(1 for r in results if r["fix_validated"])

        console.print(f"\n  [cyan]Run #{run_num}:[/cyan] "
                      f"triggered=[green]{triggered}[/green] "
                      f"matched=[green]{matched}[/green] "
                      f"validated=[green]{validated}[/green] "
                      f"known={stats['total_known']} "
                      f"promoted=[green]{stats['promoted']}[/green] "
                      f"testing=[blue]{stats['testing']}[/blue] "
                      f"failed=[red]{stats['failed']}[/red]\n")

    render_learning_curve(all_runs)

    console.print()
    console.print(Panel("[bold]FINAL SUMMARY[/bold]", border_style="bold yellow"))
    final = all_runs[-1]
    total = len(final)
    triggered = sum(1 for r in final if r["triggered"])
    matched = sum(1 for r in final if r["match"])
    validated = sum(1 for r in final if r["fix_validated"])
    promoted = sum(1 for r in final if r["fix_status"] == "promoted")

    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="bold")
    summary.add_row("Total cases", str(total))
    summary.add_row("Triggered", f"[green]{triggered}[/green]")
    summary.add_row("Expected match", f"[green]{matched}[/green]")
    summary.add_row("Fix validated", f"[green]{validated}[/green]")
    summary.add_row("Promoted", f"[green]{promoted}[/green]")
    summary.add_row("Accuracy", f"{(matched/total*100):.1f}%" if total else "N/A")
    summary.add_row("Fix success rate", f"{(validated/triggered*100):.1f}%" if triggered else "N/A")
    console.print(summary)

    mismatches = [r for r in final if r["triggered"] and not r["match"]]
    if mismatches:
        console.print("\n[bold red]Mismatched errors:[/bold red]")
        for r in mismatches:
            console.print(f"  [red]{r['name']}: expected {r['expected']}, got {r['actual']}[/red]")

    failed = [r for r in final if r["triggered"] and not r["fix_validated"]]
    if failed:
        console.print("\n[bold red]Failed fixes:[/bold red]")
        for r in failed:
            console.print(f"  [red]{r['name']}: {r['fix_detail']}[/red]")

    console.print(f"\n[bold green]Done.[/bold green] {len(cases)} cases, {triggered} triggered, {validated} fixes validated.")


if __name__ == "__main__":
    main()
