#!/usr/bin/env python3
"""
BCL 3-Pass Code Builder — Staged Compiler for Software Assembly

PASS 1: Structure Pass  — class skeletons, method signatures, no logic
PASS 2: Method Binding   — fill method bodies, self-contained, no orchestration
PASS 3: Section Fill     — integration, orchestration, CLI glue

Guard rules enforced per pass to prevent cognitive task leakage.
"""
import os
import re
import sys
import json
import hashlib
import textwrap
from datetime import datetime
from collections import OrderedDict

# ── PATHS ──

BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
SPEC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs")

# ── PASS GUARD RULES ──

PASS_RULES = {
    1: {
        "name": "STRUCTURE",
        "forbidden": ["return ", "print(", "import "],
        "forbidden_desc": "no logic, no returns, no imports, no print",
        "required": ["class ", "def ", "pass"],
        "required_desc": "class declarations, method signatures, pass placeholders",
        "rule": "No implementation allowed. Only declarations and placeholders.",
    },
    2: {
        "name": "METHOD_BINDING",
        "forbidden": ["if __name__", "argparse", "sys.argv"],
        "forbidden_desc": "no CLI, no orchestration, no cross-method coordination",
        "required": ["return ", "re.", "def "],
        "required_desc": "logic inside each function, self-contained computation",
        "rule": "Each method is self-contained and independent. No system glue.",
    },
    3: {
        "name": "SECTION_FILL",
        "forbidden": ["pass  # [SECTION:", "TODO: implement"],
        "forbidden_desc": "no leftover placeholders, no unimplemented sections",
        "required": ["if __name__", "def run", "def main"],
        "required_desc": "orchestration logic, integration, pipeline, entry point",
        "rule": "Replace all placeholders with integration logic. Connect all pieces.",
    },
}

# ── SPEC FORMAT ──

DEFAULT_SPEC = {
    "module_name": "code_analyzer",
    "description": "C code static analysis engine",
    "classes": [
        {
            "name": "CodeAnalyzer",
            "description": "Single orchestrator for all analysis passes",
            "methods": [
                {"name": "extract_functions", "signature": "(self, code: str)", "returns": "list", "desc": "Extract function names with positions"},
                {"name": "function_body_ranges", "signature": "(self, code: str)", "returns": "list", "desc": "Find function body ranges via brace matching"},
                {"name": "function_arity", "signature": "(self, code: str)", "returns": "dict", "desc": "Count parameters per function"},
                {"name": "static_vs_exported", "signature": "(self, code: str)", "returns": "dict", "desc": "Classify visibility of each function"},
                {"name": "extract_struct_fields", "signature": "(self, code: str)", "returns": "dict", "desc": "Extract struct names and their fields"},
                {"name": "extract_enums", "signature": "(self, code: str)", "returns": "dict", "desc": "Extract enum names and constants"},
                {"name": "extract_global_vars", "signature": "(self, code: str)", "returns": "list", "desc": "Extract global/static variable declarations"},
                {"name": "build_call_graph", "signature": "(self, code: str)", "returns": "dict", "desc": "Build function-to-function call graph"},
                {"name": "dead_functions", "signature": "(self, code: str)", "returns": "list", "desc": "Find functions defined but never called"},
                {"name": "circular_dependencies", "signature": "(self, graph: dict)", "returns": "list", "desc": "DFS cycle detection in call graph"},
                {"name": "extract_todos", "signature": "(self, code: str)", "returns": "list", "desc": "Extract TODO/FIXME/HACK markers"},
                {"name": "extract_sql_queries", "signature": "(self, code: str)", "returns": "list", "desc": "Extract SQL query strings"},
                {"name": "extract_mysql_tables", "signature": "(self, code: str)", "returns": "list", "desc": "Extract table names from SQL"},
                {"name": "extract_ifdef_blocks", "signature": "(self, code: str)", "returns": "list", "desc": "Extract preprocessor conditional blocks"},
                {"name": "max_nesting_depth", "signature": "(self, code: str)", "returns": "int", "desc": "Count maximum brace nesting depth"},
                {"name": "header_dependency_tree", "signature": "(self, code: str)", "returns": "list", "desc": "Extract #include dependencies"},
                {"name": "extract_bcl_packets", "signature": "(self, code: str)", "returns": "list", "desc": "Extract BCL packet patterns"},
                {"name": "run_all", "signature": "(self, code: str)", "returns": "dict", "desc": "Orchestrate all analysis methods, return unified report"},
            ],
        },
        {
            "name": "ReportEngine",
            "description": "Markdown report generator from analysis results",
            "methods": [
                {"name": "generate_summary", "signature": "(self, data: dict)", "returns": "str", "desc": "Generate overview metrics section"},
                {"name": "generate_per_file", "signature": "(self, data: dict)", "returns": "str", "desc": "Generate per-file detail sections"},
                {"name": "generate_call_graph", "signature": "(self, data: dict)", "returns": "str", "desc": "Generate cross-file call graph section"},
                {"name": "write_report", "signature": "(self, data: dict, path: str)", "returns": "None", "desc": "Write full markdown report to file"},
            ],
        },
        {
            "name": "CLI",
            "description": "Command-line interface orchestrator",
            "methods": [
                {"name": "run", "signature": "(self, args: list)", "returns": "int", "desc": "Parse args, run analysis, write report"},
                {"name": "run_full_build", "signature": "(self, spec_path: str)", "returns": "dict", "desc": "Execute 3-pass build from spec file"},
            ],
        },
    ],
}

# ── PASS 1: STRUCTURE GENERATOR ──

def pass1_structure(spec: dict) -> str:
    """Generate skeleton: classes, method signatures, pass placeholders.
    NO implementation. NO imports. NO logic."""
    lines = []
    lines.append(f'"""')
    lines.append(f'{spec["module_name"]} — {spec["description"]}')
    lines.append(f'PASS 1 OUTPUT: Structure skeleton. No implementation.')
    lines.append(f'Generated: {datetime.now().isoformat()}')
    lines.append(f'"""')
    lines.append("")
    lines.append("# [SECTION:IMPORTS]")
    lines.append("pass  # [SECTION:IMPORTS]")
    lines.append("")

    for cls in spec["classes"]:
        lines.append(f'class {cls["name"]}:')
        lines.append(f'    """{cls["description"]}"""')
        lines.append("")

        for method in cls["methods"]:
            lines.append(f'    def {method["name"]}{method["signature"]}:')
            lines.append(f'        """{method["desc"]}"""')
            lines.append(f'        # [SECTION:{method["name"].upper()}]')
            lines.append(f'        pass  # [SECTION:{method["name"].upper()}]')
            lines.append("")

        lines.append("")

    lines.append("# [SECTION:ENTRY_POINT]")
    lines.append("pass  # [SECTION:ENTRY_POINT]")
    lines.append("")

    return "\n".join(lines)

# ── PASS 2: METHOD BINDING ──

# Implementation registry — each method gets its logic here
# Keyed by method_name, value is the function body (indented, no def line)

METHOD_IMPLEMENTATIONS = {
    "extract_functions": '''        import re
        pattern = re.compile(r'\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(([^)]*)\\)\\s*\\{')
        return [(m.group(1), m.group(2), m.start()) for m in pattern.finditer(code)]''',

    "function_body_ranges": '''        import re
        pattern = re.compile(r'\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(([^)]*)\\)\\s*\\{')
        funcs = []
        for m in pattern.finditer(code):
            name = m.group(1)
            start = m.end() - 1
            depth = 0
            for i in range(start, len(code)):
                if code[i] == '{':
                    depth += 1
                elif code[i] == '}':
                    depth -= 1
                    if depth == 0:
                        funcs.append((name, start, i))
                        break
        return funcs''',

    "function_arity": '''        import re
        pattern = re.compile(r'\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(([^)]*)\\)\\s*\\{')
        result = {}
        for m in pattern.finditer(code):
            params = m.group(2).strip()
            if params in ('void', ''):
                result[m.group(1)] = 0
            else:
                result[m.group(1)] = len([p for p in params.split(',') if p.strip() and p.strip() != 'void'])
        return result''',

    "static_vs_exported": '''        import re
        pattern = re.compile(r'^(.*)\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(([^)]*)\\)\\s*\\{', re.MULTILINE)
        result = {}
        for m in pattern.finditer(code):
            prefix = m.group(1)
            result[m.group(2)] = "static" if "static" in prefix else "exported"
        return result''',

    "extract_struct_fields": '''        import re
        pattern = re.compile(r'\\bstruct\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\{')
        structs = {}
        for m in pattern.finditer(code):
            name = m.group(1)
            body_start = m.end()
            depth = 1
            for i in range(body_start, len(code)):
                if code[i] == '{':
                    depth += 1
                elif code[i] == '}':
                    depth -= 1
                    if depth == 0:
                        break
            block = code[body_start:i]
            fields = []
            for line in block.splitlines():
                line = line.strip().strip(';')
                if line and not line.startswith('//'):
                    fields.append(line)
            structs[name] = fields
        return structs''',

    "extract_enums": '''        import re
        pattern = re.compile(r'\\benum\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\{')
        enums = {}
        for m in pattern.finditer(code):
            name = m.group(1)
            body = code[m.end():]
            block = body.split('}')[0]
            enums[name] = [x.strip() for x in block.split(',') if x.strip()]
        return enums''',

    "extract_global_vars": '''        import re
        pattern = re.compile(
            r'^(?:static\\s+)?(?:const\\s+)?(?:unsigned\\s+|signed\\s+)?'
            r'(?:int|char|double|float|size_t|long|short|FILE\\s*\\*|'
            r'sqlite3\\s*\\*|MYSQL\\s*\\*|struct\\s+\\w+|'
            r'\\w+_\\w+\\s*\\*?|const\\s+char\\s*\\*|unsigned\\s+char\\s*\\*|char\\s*\\*)\\s+'
            r'(\\w+)(?:\\s*\\[)?(?:\\s*=)?',
            re.MULTILINE
        )
        return [m.group(0).strip() for m in pattern.finditer(code)]''',

    "build_call_graph": '''        import re
        from collections import defaultdict
        func_pattern = re.compile(r'\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(([^)]*)\\)\\s*\\{')
        call_pattern = re.compile(r'\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(')
        funcs = [(m.group(1), m.start(), m.end()) for m in func_pattern.finditer(code)]
        graph = defaultdict(set)
        for name, start, end in funcs:
            brace_start = code.find('{', end - 1)
            if brace_start == -1:
                continue
            depth = 0
            body_end = brace_start
            for i in range(brace_start, len(code)):
                if code[i] == '{':
                    depth += 1
                elif code[i] == '}':
                    depth -= 1
                    if depth == 0:
                        body_end = i
                        break
            body = code[brace_start:body_end]
            for c in call_pattern.findall(body):
                if c != name:
                    graph[name].add(c)
        return dict(graph)''',

    "dead_functions": '''        funcs = set(f[0] for f in self.extract_functions(code))
        graph = self.build_call_graph(code)
        called = set()
        for targets in graph.values():
            called.update(targets)
        return list(funcs - called)''',

    "circular_dependencies": '''        visited = set()
        stack = set()
        cycles = []
        def dfs(node, path):
            if node in stack:
                cycles.append(path + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for nxt in graph.get(node, []):
                dfs(nxt, path + [node])
            stack.remove(node)
        for n in graph:
            dfs(n, [])
        return cycles''',

    "extract_todos": '''        import re
        pattern = re.compile(r'(TODO|FIXME|HACK|XXX|BUG|NOTE)\\s*[:\\-]?\\s*(.*)', re.IGNORECASE)
        return [(m.group(1), m.group(2).strip()) for m in pattern.finditer(code)]''',

    "extract_sql_queries": '''        import re
        pattern = re.compile(r'"((?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|SHOW|DESCRIBE)\\s[^"]{5,})"', re.IGNORECASE)
        return pattern.findall(code)''',

    "extract_mysql_tables": '''        import re
        pattern = re.compile(r'(?:FROM|JOIN|INTO|UPDATE|TABLE)\\s+(\\w+)', re.IGNORECASE)
        return list(dict.fromkeys(pattern.findall(code)))''',

    "extract_ifdef_blocks": '''        import re
        pattern = re.compile(r'^\\s*#(?:ifdef|ifndef|if)\\s+(.+)$', re.MULTILINE)
        endif = re.compile(r'^\\s*#endif', re.MULTILINE)
        blocks = []
        stack = []
        lines = code.splitlines()
        for i, line in enumerate(lines):
            m = pattern.match(line)
            if m:
                stack.append((m.group(1).strip(), i + 1))
            elif endif.match(line) and stack:
                cond, start = stack.pop()
                blocks.append({"condition": cond, "start_line": start, "end_line": i + 1})
        return blocks''',

    "max_nesting_depth": '''        depth = 0
        max_depth = 0
        for ch in code:
            if ch == '{':
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == '}':
                depth -= 1
        return max_depth''',

    "header_dependency_tree": '''        import re
        pattern = re.compile(r'#include\\s+[<"]([^">]+)[">]')
        return pattern.findall(code)''',

    "extract_bcl_packets": '''        import re
        pattern = re.compile(r'\\[@(\\w+)\\]\\{([^}]+)\\}')
        return [(m.group(1), m.group(2)) for m in pattern.finditer(code)]''',

    "run_all": '''        return {
            "functions": self.extract_functions(code),
            "function_ranges": self.function_body_ranges(code),
            "arity": self.function_arity(code),
            "visibility": self.static_vs_exported(code),
            "structs": self.extract_struct_fields(code),
            "enums": self.extract_enums(code),
            "globals": self.extract_global_vars(code),
            "call_graph": self.build_call_graph(code),
            "dead_functions": self.dead_functions(code),
            "circular": self.circular_dependencies(self.build_call_graph(code)),
            "todos": self.extract_todos(code),
            "sql": self.extract_sql_queries(code),
            "mysql_tables": self.extract_mysql_tables(code),
            "ifdef": self.extract_ifdef_blocks(code),
            "max_nesting": self.max_nesting_depth(code),
            "headers": self.header_dependency_tree(code),
            "bcl_packets": self.extract_bcl_packets(code),
        }''',

    "generate_summary": '''        lines = ["## Overview\\n"]
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for key, val in data.items():
            if isinstance(val, (int, str, float)):
                lines.append(f"| {key} | {val} |")
            elif isinstance(val, list):
                lines.append(f"| {key} | {len(val)} |")
            elif isinstance(val, dict):
                lines.append(f"| {key} | {len(val)} |")
        return "\\n".join(lines)''',

    "generate_per_file": '''        lines = ["## Per-File Details\\n"]
        for fname, details in data.get("files", {}).items():
            lines.append(f"### {fname}")
            for key, val in details.items():
                lines.append(f"- **{key}**: {val}")
            lines.append("")
        return "\\n".join(lines)''',

    "generate_call_graph": '''        lines = ["## Call Graph\\n"]
        lines.append("| Caller | Callee |")
        lines.append("|---|---|")
        for caller, callees in data.get("call_graph", {}).items():
            for callee in sorted(callees) if isinstance(callees, set) else [callees]:
                lines.append(f"| {caller} | {callee} |")
        return "\\n".join(lines)''',

    "write_report": '''        with open(path, "w") as f:
            f.write(f"# Analysis Report\\n\\n")
            f.write(self.generate_summary(data))
            f.write("\\n\\n")
            f.write(self.generate_call_graph(data))
            f.write("\\n\\n")
            f.write(self.generate_per_file(data))
            f.write("\\n")''',

    "run": '''        import sys
        if not args:
            print("Usage: bcl_3pass_builder.py <directory> [--output FILE]")
            return 1
        directory = args[0]
        output = "analysis_report.md"
        if "--output" in args:
            output = args[args.index("--output") + 1]
        analyzer = CodeAnalyzer()
        all_data = {"files": {}}
        for root, _, files in os.walk(directory):
            for fn in sorted(files):
                if fn.endswith('.c'):
                    path = os.path.join(root, fn)
                    with open(path, "r", errors="ignore") as f:
                        code = f.read()
                    all_data["files"][fn] = analyzer.run_all(code)
        report = ReportEngine()
        report.write_report(all_data, output)
        print(f"Report written to {output}")
        return 0''',

    "run_full_build": '''        with open(spec_path, "r") as f:
            spec = json.load(f)
        p1 = pass1_structure(spec)
        p2 = pass2_methods(p1, spec)
        p3 = pass3_sections(p2, spec)
        os.makedirs(BUILD_DIR, exist_ok=True)
        with open(os.path.join(BUILD_DIR, "pass1_structure.py"), "w") as f:
            f.write(p1)
        with open(os.path.join(BUILD_DIR, "pass2_methods.py"), "w") as f:
            f.write(p2)
        with open(os.path.join(BUILD_DIR, "pass3_integrated.py"), "w") as f:
            f.write(p3)
        return {"pass1": len(p1), "pass2": len(p2), "pass3": len(p3)}''',
}

def pass2_methods(pass1_code: str, spec: dict) -> str:
    """Fill in method bodies. Each method self-contained.
    No CLI, no orchestration, no cross-method calls (except within same class)."""
    code = pass1_code

    # Replace imports placeholder
    code = code.replace("pass  # [SECTION:IMPORTS]", "import os\nimport re\nimport sys\nimport json\nfrom collections import defaultdict\nfrom datetime import datetime")

    # Replace each method placeholder with implementation
    for cls in spec["classes"]:
        for method in cls["methods"]:
            section_tag = f"# [SECTION:{method['name'].upper()}]"
            impl = METHOD_IMPLEMENTATIONS.get(method["name"], f'        raise NotImplementedError("{method["name"]} not yet implemented")')

            # Replace the pass placeholder + section comment
            pattern = f"        {section_tag}\n        pass  # [SECTION:{method['name'].upper()}]"
            replacement = f"        {section_tag}\n{impl}"
            code = code.replace(pattern, replacement)

    return code

# ── PASS 3: SECTION FILL (Integration) ──

def pass3_sections(pass2_code: str, spec: dict) -> str:
    """Replace remaining placeholders with orchestration logic.
    Connect all methods into a working system."""
    code = pass2_code

    # Replace entry point
    entry_section = '''def main():
    """Entry point — orchestrate the full analysis pipeline."""
    cli = CLI()
    return cli.run(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(main())'''

    code = code.replace("pass  # [SECTION:ENTRY_POINT]", entry_section)

    # Verify no placeholders remain
    remaining = re.findall(r'# \[SECTION:\w+\]', code)
    if remaining:
        # Log warning but don't fail
        for r in remaining:
            if "pass  # [SECTION:" in code:
                code = code.replace(f"pass  # {r}", f'        # WARNING: Unresolved section {r}')
                code = code.replace(r, f'# RESOLVED: {r}')

    return code

# ── GUARD RULE VALIDATION ──

def validate_pass(code: str, pass_num: int) -> dict:
    """Validate code against pass guard rules.
    Strips docstrings and comments before checking forbidden patterns."""
    rules = PASS_RULES[pass_num]
    violations = []

    # Strip docstrings and comments for forbidden-pattern checks
    check_code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
    check_code = re.sub(r"'''.*?'''", '', check_code, flags=re.DOTALL)
    check_code = re.sub(r'#.*', '', check_code)

    for pattern in rules["forbidden"]:
        count = check_code.count(pattern)
        if count > 0:
            violations.append(f"FORBIDDEN in PASS {pass_num}: '{pattern}' found {count}x — {rules['forbidden_desc']}")

    for pattern in rules["required"]:
        if pattern not in code:
            violations.append(f"REQUIRED in PASS {pass_num}: '{pattern}' NOT found — {rules['required_desc']}")

    return {
        "pass": pass_num,
        "name": rules["name"],
        "valid": len(violations) == 0,
        "violations": violations,
        "code_size": len(code),
        "line_count": len(code.splitlines()),
    }

# ── BUILD RUNNER ──

def build(spec: dict, validate: bool = True) -> dict:
    """Execute all 3 passes and return results."""
    os.makedirs(BUILD_DIR, exist_ok=True)

    results = {}

    # PASS 1
    p1 = pass1_structure(spec)
    p1_path = os.path.join(BUILD_DIR, "pass1_structure.py")
    with open(p1_path, "w") as f:
        f.write(p1)
    results["pass1"] = {"path": p1_path, "size": len(p1), "lines": len(p1.splitlines())}
    if validate:
        results["pass1"]["validation"] = validate_pass(p1, 1)

    # PASS 2
    p2 = pass2_methods(p1, spec)
    p2_path = os.path.join(BUILD_DIR, "pass2_methods.py")
    with open(p2_path, "w") as f:
        f.write(p2)
    results["pass2"] = {"path": p2_path, "size": len(p2), "lines": len(p2.splitlines())}
    if validate:
        results["pass2"]["validation"] = validate_pass(p2, 2)

    # PASS 3
    p3 = pass3_sections(p2, spec)
    p3_path = os.path.join(BUILD_DIR, "pass3_integrated.py")
    with open(p3_path, "w") as f:
        f.write(p3)
    results["pass3"] = {"path": p3_path, "size": len(p3), "lines": len(p3.splitlines())}
    if validate:
        results["pass3"]["validation"] = validate_pass(p3, 3)

    return results

# ── CLI ──

def main():
    args = sys.argv[1:]

    if not args:
        print("BCL 3-Pass Code Builder")
        print("")
        print("Usage:")
        print("  bcl_3pass_builder.py build [--spec FILE] [--no-validate]")
        print("  bcl_3pass_builder.py validate --pass N --file FILE")
        print("  bcl_3pass_builder.py spec --show")
        print("")
        print("Commands:")
        print("  build       Run all 3 passes, output to build/ directory")
        print("  validate    Validate a file against pass N guard rules")
        print("  spec        Show or save the default spec")
        print("")
        return 0

    cmd = args[0]

    if cmd == "build":
        spec = DEFAULT_SPEC
        do_validate = "--no-validate" not in args

        if "--spec" in args:
            spec_path = args[args.index("--spec") + 1]
            with open(spec_path, "r") as f:
                spec = json.load(f)

        print("BCL 3-Pass Code Builder")
        print(f"Module: {spec['module_name']}")
        print(f"Classes: {len(spec['classes'])}")
        total_methods = sum(len(c['methods']) for c in spec['classes'])
        print(f"Methods: {total_methods}")
        print("")

        results = build(spec, validate=do_validate)

        for pass_num in [1, 2, 3]:
            key = f"pass{pass_num}"
            r = results[key]
            rules = PASS_RULES[pass_num]
            print(f"PASS {pass_num} — {rules['name']}")
            print(f"  Output: {r['path']}")
            print(f"  Size: {r['size']} bytes, {r['lines']} lines")

            if do_validate and "validation" in r:
                v = r["validation"]
                if v["valid"]:
                    print(f"  Validation: PASS ✓")
                else:
                    print(f"  Validation: FAIL ✗")
                    for violation in v["violations"]:
                        print(f"    - {violation}")
            print("")

        print(f"Build complete. Output in {BUILD_DIR}/")
        return 0

    elif cmd == "validate":
        if "--pass" not in args or "--file" not in args:
            print("Usage: validate --pass N --file FILE")
            return 1

        pass_num = int(args[args.index("--pass") + 1])
        file_path = args[args.index("--file") + 1]

        with open(file_path, "r") as f:
            code = f.read()

        result = validate_pass(code, pass_num)
        print(f"PASS {pass_num} — {result['name']}")
        print(f"Valid: {result['valid']}")
        if result["violations"]:
            print("Violations:")
            for v in result["violations"]:
                print(f"  - {v}")
        return 0 if result["valid"] else 1

    elif cmd == "spec":
        if "--show" in args:
            print(json.dumps(DEFAULT_SPEC, indent=2))
            return 0

        if "--save" in args:
            path = args[args.index("--save") + 1] if args.index("--save") + 1 < len(args) else "spec.json"
            os.makedirs(SPEC_DIR, exist_ok=True)
            full_path = os.path.join(SPEC_DIR, path)
            with open(full_path, "w") as f:
                json.dump(DEFAULT_SPEC, f, indent=2)
            print(f"Spec saved to {full_path}")
            return 0

        print("Usage: spec --show | spec --save FILENAME")
        return 1

    else:
        print(f"Unknown command: {cmd}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
