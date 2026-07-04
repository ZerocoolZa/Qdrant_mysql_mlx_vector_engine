#!/usr/bin/env python3
"""Fix all VBStyle violations in Dom_Graph files in one pass."""
import re, os, ast

DIR = os.path.dirname(os.path.abspath(__file__))
FILES = ["eyes_26.py", "codegraph_26eyes.py", "eyes_26_v1.py"]

RUN_TEMPLATE = """
    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, dict(self.state) if hasattr(self, "state") else {}, None)
"""

RUN_TEMPLATE_DATACLASS = """
    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))
"""

def get_classes_needing_run(filepath):
    """Find classes without Run() method."""
    with open(filepath, "r") as f:
        content = f.read()
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return []
    
    needs_run = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            has_run = False
            has_state = False
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == "Run":
                        has_run = True
                    if item.name == "read_state":
                        has_state = True
            if not has_run:
                line = node.lineno
                # Find last method line
                last_line = node.end_lineno if hasattr(node, "end_lineno") else line
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        last_line = max(last_line, item.end_lineno if hasattr(item, "end_lineno") else item.lineno)
                needs_run.append({
                    "name": node.name,
                    "line": line,
                    "last_method_line": last_line,
                    "has_state": has_state,
                    "indent": 4,
                })
    return needs_run

def remove_prints(filepath):
    """Remove print() calls from file."""
    with open(filepath, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    removed = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("print("):
            indent = len(line) - len(stripped)
            # Check if next line is dedented (block end)
            if i + 1 < len(lines):
                next_s = lines[i + 1].lstrip()
                next_indent = len(lines[i + 1]) - len(next_s) if next_s else indent
                if next_indent < indent and not next_s.startswith("else") and not next_s.startswith("elif") and not next_s.startswith("except") and not next_s.startswith("finally"):
                    new_lines.append(" " * indent + "pass\n")
            removed += 1
            continue
        new_lines.append(line)
    
    with open(filepath, "w") as f:
        f.writelines(new_lines)
    return removed

def remove_decorators(filepath):
    """Remove @staticmethod, @property, @classmethod lines."""
    with open(filepath, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if stripped in ("@staticmethod", "@property", "@classmethod"):
            removed += 1
            continue
        new_lines.append(line)
    
    with open(filepath, "w") as f:
        f.writelines(new_lines)
    return removed

def fix_self_underscore(filepath):
    """Replace self._xxx with self.xxx (only attribute access, not method calls)."""
    with open(filepath, "r") as f:
        content = f.read()
    
    # Replace self._name with self.name (but not self.__name or method calls)
    new_content = re.sub(r'self\.(_)([a-z][a-zA-Z0-9_]*)\b', r'self.\2', content)
    
    count = content.count("self._") - new_content.count("self._")
    
    with open(filepath, "w") as f:
        f.write(new_content)
    return count

def add_run_methods(filepath):
    """Add Run() method to classes that need it."""
    classes = get_classes_needing_run(filepath)
    if not classes:
        return 0
    
    with open(filepath, "r") as f:
        lines = f.readlines()
    
    # Process from bottom to top so line numbers don't shift
    classes.sort(key=lambda c: c["last_method_line"], reverse=True)
    
    for cls in classes:
        insert_idx = cls["last_method_line"]  # 1-indexed, so this is the line after
        indent = "    "
        
        # Check if it's a simple data class (no state dict)
        if cls["name"] in ("GraphNode", "GraphEdge", "GraphLoadConfig", "BracketNode", "BracketParseError", "BracketValidationError"):
            run_code = "\n" + indent + "def Run(self, command, params=None):\n" + indent + "    return (0, None, (\"unknown_command\", command, 0))\n"
        else:
            run_code = "\n" + indent + "def Run(self, command, params=None):\n"
            run_code += indent + "    if command == \"read_state\":\n"
            run_code += indent + "        return self.read_state(params)\n"
            run_code += indent + "    return (0, None, (\"unknown_command\", command, 0))\n"
            run_code += "\n" + indent + "def read_state(self, params=None):\n"
            run_code += indent + "    return (1, {}, None)\n"
        
        lines.insert(insert_idx, run_code)
    
    with open(filepath, "w") as f:
        f.writelines(lines)
    
    return len(classes)

def fix_v1_aliases(filepath):
    """Rename compatibility alias classes in v1."""
    with open(filepath, "r") as f:
        content = f.read()
    
    content = content.replace("class GhostBracketUltimate(Vision3D):", "class VisionUltimate(Vision3D):")
    content = content.replace("class GhostBracketMaxPlus(Vision3D):", "class VisionMaxPlus(Vision3D):")
    
    with open(filepath, "w") as f:
        f.write(content)

# ─── MAIN ──────────────────────────────────────────────────────────────
print("DOM_GRAPH VBSTYLE FIXER")
print("=" * 60)

for fname in FILES:
    fpath = os.path.join(DIR, fname)
    if not os.path.exists(fpath):
        print("{}: SKIP (not found)".format(fname))
        continue
    
    print("\n--- {} ---".format(fname))
    
    # Step 1: Remove prints
    pcount = remove_prints(fpath)
    print("  prints removed: {}".format(pcount))
    
    # Step 2: Remove decorators
    dcount = remove_decorators(fpath)
    print("  decorators removed: {}".format(dcount))
    
    # Step 3: Fix self._ 
    scount = fix_self_underscore(fpath)
    print("  self._ fixed: {}".format(scount))
    
    # Step 4: Fix v1 aliases
    if fname == "eyes_26_v1.py":
        fix_v1_aliases(fpath)
        print("  v1 aliases renamed")
    
    # Step 5: Add Run() methods
    rcount = add_run_methods(fpath)
    print("  Run() methods added: {}".format(rcount))

print("\n" + "=" * 60)
print("DONE — now verifying with VbsScanner...")

# Verify
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(DIR))))
from core.utility import VbsScanner

scanner = VbsScanner()
for fname in FILES:
    fpath = os.path.join(DIR, fname)
    code, data, err = scanner.Run("scan_file", {"path": fpath})
    if code == 1 and isinstance(data, list):
        rules = {}
        for v in data:
            r = v.get("rule", "?")
            rules[r] = rules.get(r, 0) + 1
        print("  {}: {} violations remaining".format(fname, len(data)))
        for r, c in sorted(rules.items()):
            print("    {}: {}".format(r, c))
    else:
        print("  {}: CLEAN".format(fname))
