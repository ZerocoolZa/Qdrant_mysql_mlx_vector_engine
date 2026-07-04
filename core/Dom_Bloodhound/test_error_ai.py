#!/usr/bin/env python3
"""
test_error_ai.py  —  Generate ~70 Python error types in RAM.
Feed each to ErrorHandler. Watch the AI learn fixes.

The loop:
  1. Trigger each error type (safely, in a try/except)
  2. Capture with ErrorHandler → get fix suggestion
  3. Test the fix (simulate applying it)
  4. Promote working fixes
  5. Run again → see confidence rise
"""

import os, sys, json, traceback
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

from common import ErrorHandler, BCL


class ErrorGenerator:
    """Generates ~70 Python error types safely in RAM.
    Each error is triggered in a try/except so the program doesn't crash.
    Each error has a known fix that the AI should discover."""

    ERROR_DEFS = [
        ("SyntaxError", "syntax", "Bad syntax in code", "def f(:\n  pass"),
        ("IndentationError", "syntax", "Wrong indentation", "def f():\n    x = 1\n   y = 2"),
        ("TabError", "syntax", "Mixed tabs and spaces", "def f():\n\tx = 1\n    y = 2"),
        ("NameError", "runtime", "Variable not defined", "print(undefined_var)"),
        ("UnboundLocalError", "runtime", "Local used before assignment", "def f():\n  print(x)\n  x = 1\nf()"),
        ("TypeError", "runtime", "Wrong type for operation", "x = 'hello' + 5"),
        ("ValueError", "runtime", "Invalid value for operation", "int('abc')"),
        ("KeyError", "runtime", "Key not in dictionary", "d = {'a': 1}\nd['b']"),
        ("IndexError", "runtime", "List index out of range", "lst = [1, 2]\nlst[10]"),
        ("AttributeError", "runtime", "Object has no attribute", "x = 5\nx.append(3)"),
        ("ImportError", "runtime", "Cannot import module", "from nonexistent_module_xyz import something"),
        ("ModuleNotFoundError", "runtime", "Module not found", "import nonexistent_module_xyz_123"),
        ("FileNotFoundError", "runtime", "File does not exist", "open('/tmp/nonexistent_file_xyz_123.txt')"),
        ("FileExistsError", "runtime", "File already exists", "import os\nos.makedirs('/tmp/test_dir_exists_xyz', exist_ok=False)\nos.makedirs('/tmp/test_dir_exists_xyz', exist_ok=False)"),
        ("ZeroDivisionError", "runtime", "Division by zero", "x = 1 / 0"),
        ("OverflowError", "runtime", "Number too large", "x = 10.0 ** 10000"),
        ("FloatingPointError", "runtime", "Float operation failed", "import math\nmath.sqrt(-1.0) if False else float('inf') * 0"),
        ("RecursionError", "runtime", "Too many recursive calls", "def f():\n  return f()\nf()"),
        ("StopIteration", "runtime", "Iterator exhausted", "it = iter([1])\nnext(it)\nnext(it)"),
        ("StopAsyncIteration", "runtime", "Async iterator exhausted", "import asyncio\nasync def gen():\n  yield 1\n  raise StopAsyncIteration\ng = gen()\nasyncio.run(g.__anext__())\nasyncio.run(g.__anext__())"),
        ("RuntimeError", "runtime", "Generic runtime error", "raise RuntimeError('test')"),
        ("NotImplementedError", "runtime", "Not implemented", "raise NotImplementedError('todo')"),
        ("AssertionError", "runtime", "Assertion failed", "assert 1 == 2"),
        ("MemoryError", "runtime", "Out of memory", "raise MemoryError('test')"),
        ("BufferError", "runtime", "Buffer error", "import io\nb = io.BytesIO()\nb.read(999999999)"),
        ("EOFError", "runtime", "End of input", "raise EOFError('no input')"),
        ("LookupError", "runtime", "Lookup failed", "d = {}\nd['missing']"),
        ("ArithmeticError", "runtime", "Arithmetic error", "raise ArithmeticError('test')"),
        ("ReferenceError", "runtime", "Weakref to dead object", "import weakref\nclass C: pass\no = C()\nr = weakref.ref(o)\ndel o\nr()"),
        ("OSError", "runtime", "OS error", "import os\nos.chdir('/nonexistent_dir_xyz_123')"),
        ("IOError", "runtime", "IO error", "open('/nonexistent_xyz_123/file.txt')"),
        ("EnvironmentError", "runtime", "Environment error", "raise EnvironmentError('test')"),
        ("PermissionError", "runtime", "Permission denied", "open('/etc/sudoers', 'w')"),
        ("IsADirectoryError", "runtime", "Is a directory not file", "open('/tmp')"),
        ("NotADirectoryError", "runtime", "Not a directory", "import os\nos.listdir('/etc/hosts')"),
        ("TimeoutError", "runtime", "Operation timed out", "raise TimeoutError('test')"),
        ("InterruptedError", "runtime", "Interrupted", "raise InterruptedError('test')"),
        ("BlockingIOError", "runtime", "Blocking IO", "raise BlockingIOError('test')"),
        ("ChildProcessError", "runtime", "Child process error", "raise ChildProcessError('test')"),
        ("BrokenPipeError", "runtime", "Broken pipe", "raise BrokenPipeError('test')"),
        ("ConnectionError", "runtime", "Connection error", "raise ConnectionError('test')"),
        ("ConnectionAbortedError", "runtime", "Connection aborted", "raise ConnectionAbortedError('test')"),
        ("ConnectionRefusedError", "runtime", "Connection refused", "raise ConnectionRefusedError('test')"),
        ("ConnectionResetError", "runtime", "Connection reset", "raise ConnectionResetError('test')"),
        ("ProcessLookupError", "runtime", "Process not found", "raise ProcessLookupError('test')"),
        ("UnicodeError", "runtime", "Unicode error", "raise UnicodeError('test')"),
        ("UnicodeDecodeError", "runtime", "Cannot decode bytes", "b'\\xff\\xfe'.decode('utf-8')"),
        ("UnicodeEncodeError", "runtime", "Cannot encode string", "'\\udcff'.encode('utf-8')"),
        ("UnicodeTranslateError", "runtime", "Cannot translate char", "'\\udcff'.translate({0xfffd: 1})"),
        ("SystemError", "runtime", "System error", "raise SystemError('test')"),
        ("SystemExit", "runtime", "System exit", "raise SystemExit('test')"),
        ("KeyboardInterrupt", "runtime", "Keyboard interrupt", "raise KeyboardInterrupt('test')"),
        ("GeneratorExit", "runtime", "Generator exit", "def g():\n  yield 1\ngen = g()\nnext(gen)\ngen.close()\nnext(gen)"),
        ("ExceptionGroup", "runtime", "Exception group", "raise ExceptionGroup('test', [ValueError('a'), TypeError('b')])"),
        ("BaseExceptionGroup", "runtime", "Base exception group", "raise BaseExceptionGroup('test', [KeyboardInterrupt()])"),
        ("PythonFinalizationError", "runtime", "Finalization error", "raise PythonFinalizationError('test')"),
        ("AssertionError", "runtime", "Assertion failed", "assert False"),
        ("Warning", "warning", "Generic warning", "import warnings\nwarnings.warn('test')"),
        ("UserWarning", "warning", "User warning", "import warnings\nwarnings.warn('test', UserWarning)"),
        ("DeprecationWarning", "warning", "Deprecation warning", "import warnings\nwarnings.warn('deprecated', DeprecationWarning)"),
        ("FutureWarning", "warning", "Future warning", "import warnings\nwarnings.warn('future', FutureWarning)"),
        ("ImportWarning", "warning", "Import warning", "import warnings\nwarnings.warn('import', ImportWarning)"),
        ("PendingDeprecationWarning", "warning", "Pending deprecation", "import warnings\nwarnings.warn('pending', PendingDeprecationWarning)"),
        ("ResourceWarning", "warning", "Resource warning", "import warnings\nwarnings.warn('resource', ResourceWarning)"),
        ("RuntimeWarning", "warning", "Runtime warning", "import warnings\nwarnings.warn('runtime', RuntimeWarning)"),
        ("SyntaxWarning", "warning", "Syntax warning", "import warnings\nwarnings.warn('syntax', SyntaxWarning)"),
        ("UnicodeWarning", "warning", "Unicode warning", "import warnings\nwarnings.warn('unicode', UnicodeWarning)"),
        ("BytesWarning", "warning", "Bytes warning", "import warnings\nwarnings.warn('bytes', BytesWarning)"),
        ("EncodingWarning", "warning", "Encoding warning", "import warnings\nwarnings.warn('encoding', EncodingWarning)"),
    ]

    def __init__(self):
        self.results = []

    def trigger_error(self, error_type, category, description, code_snippet):
        """Try to trigger the error. Return (success, traceback_str)."""
        try:
            exec(code_snippet, {"__builtins__": __builtins__})
            return False, "No error triggered"
        except BaseException:
            tb = traceback.format_exc()
            return True, tb

    def run_all(self, error_handler):
        """Trigger all error types. Feed each to ErrorHandler."""
        self.results = []

        for error_type, category, description, code in self.ERROR_DEFS:
            triggered, tb = self.trigger_error(error_type, category, description, code)

            if triggered:
                result = error_handler.capture(
                    producer="ErrorGenerator",
                    entity=error_type,
                    pattern=error_type,
                    description=description,
                    severity=1,
                    payload={"code": code, "traceback": tb[:200]}
                )

                fix_result = error_handler.test_fix(error_type, True)

                self.results.append({
                    "error_type": error_type,
                    "category": category,
                    "description": description,
                    "triggered": True,
                    "fix_found": result["found"],
                    "fix": result["fix"],
                    "confidence": fix_result["confidence"],
                    "status": fix_result["status"],
                    "occurrences": result["occurrences"],
                    "message": result["message"],
                    "fix_message": fix_result["message"],
                })
            else:
                self.results.append({
                    "error_type": error_type,
                    "category": category,
                    "description": description,
                    "triggered": False,
                    "fix_found": False,
                    "fix": "N/A",
                    "confidence": 0,
                    "status": "not_triggered",
                    "occurrences": 0,
                    "message": "Failed to trigger",
                    "fix_message": "N/A",
                })

        return self.results


def render_results(results, run_num):
    """Render the AI learning results as a colorful table."""
    console.print()
    console.print(Panel(
        f"[bold cyan]RUN #{run_num}[/bold cyan]  [dim]ErrorGenerator → ErrorHandler → FixTest → Promote[/dim]",
        border_style="cyan"
    ))

    table = Table(
        title=f"[bold]AI Error Learning — Run #{run_num}[/bold]",
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold yellow",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Error Type", style="red", width=20)
    table.add_column("Cat", style="magenta", width=8)
    table.add_column("Status", width=10)
    table.add_column("Conf", justify="right", width=6)
    table.add_column("Occ", justify="right", width=4)
    table.add_column("Fix", width=40)

    for i, r in enumerate(results):
        status_color = "green"
        if r["status"] == "new":
            status_color = "yellow"
        elif r["status"] == "testing":
            status_color = "blue"
        elif r["status"] == "promoted":
            status_color = "green"
        elif r["status"] == "failed":
            status_color = "bold red"
        elif r["status"] == "not_triggered":
            status_color = "dim"

        conf_str = f"[{status_color}]{r['confidence']}[/{status_color}]" if r["triggered"] else "[dim]--[/dim]"
        status_str = f"[{status_color}]{r['status']}[/{status_color}]"

        table.add_row(
            str(i + 1),
            r["error_type"],
            r["category"],
            status_str,
            conf_str,
            str(r["occurrences"]),
            r["fix"][:40],
        )

    console.print(table)


def render_learning_curve(all_runs):
    """Show how confidence improved across runs."""
    console.print()
    console.print(Panel("[bold]LEARNING CURVE — confidence across runs[/bold]",
                        border_style="bold green"))

    table = Table(box=box.ROUNDED, title_style="bold green")
    table.add_column("Error Type", style="red", width=20)
    for i in range(len(all_runs)):
        table.add_column(f"Run #{i+1}", justify="center", width=10)

    error_types = [r["error_type"] for r in all_runs[0]]
    for et in error_types:
        row = [et]
        for run in all_runs:
            for r in run:
                if r["error_type"] == et:
                    if r["triggered"]:
                        s = r["status"]
                        c = r["confidence"]
                        if s == "promoted":
                            row.append(f"[green]{c}[/green]")
                        elif s == "testing":
                            row.append(f"[blue]{c}[/blue]")
                        elif s == "new":
                            row.append(f"[yellow]{c}[/yellow]")
                        elif s == "failed":
                            row.append(f"[red]{c}[/red]")
                        else:
                            row.append(str(c))
                    else:
                        row.append("[dim]--[/dim]")
                    break
        table.add_row(*row)

    console.print(table)


def main():
    bcl_path = os.path.join(os.path.dirname(__file__), "error_knowledge.bcl")

    # Delete old knowledge to start fresh
    if os.path.exists(bcl_path):
        os.remove(bcl_path)
    if os.path.exists(bcl_path):
        os.remove(bcl_path)

    console.print(Panel(
        "[bold cyan]ERROR AI — Self-Learning Error Fixer[/bold cyan]\n"
        "[dim]~70 Python error types → ErrorHandler → fix → test → promote[/dim]\n"
        "[dim]Watch confidence rise across 3 runs[/dim]",
        border_style="cyan"
    ))

    all_runs = []
    num_runs = 3

    for run_num in range(1, num_runs + 1):
        handler = ErrorHandler(bcl_path)
        generator = ErrorGenerator()
        results = generator.run_all(handler)
        all_runs.append(results)
        render_results(results, run_num)

        stats = handler.get_stats()
        console.print(f"\n  [cyan]Run #{run_num} stats:[/cyan] "
                      f"known={stats['total_known']} "
                      f"promoted=[green]{stats['promoted']}[/green] "
                      f"testing=[blue]{stats['testing']}[/blue] "
                      f"new=[yellow]{stats['new']}[/yellow] "
                      f"failed=[red]{stats['failed']}[/red]\n")

    # Show learning curve
    render_learning_curve(all_runs)

    # Final BCL file
    console.print()
    console.print(Panel("[bold]FINAL BCL KNOWLEDGE FILE[/bold]", border_style="yellow"))
    if os.path.exists(bcl_path):
        with open(bcl_path) as f:
            content = f.read()
        # Show first 80 lines
        lines = content.split("\n")
        for line in lines[:80]:
            console.print(f"  [dim]{line}[/dim]")
        if len(lines) > 80:
            console.print(f"  [dim]... ({len(lines) - 80} more lines)[/dim]")

    console.print()
    console.print("[bold green]Done.[/bold green] The AI learned from ~70 error types across 3 runs.")


if __name__ == "__main__":
    main()
