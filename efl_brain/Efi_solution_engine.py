#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     config_solution_engine.py
# Domain:   Analysis
# Authority: Detects config rule violations and generates concrete fixes
# DB:       None (analysis only)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths
#   @cstyle   — Coding style compliant
# ============================================================================

"""
Config Solution Engine — scans real folders, detects violations, generates fixes.

For each violation found, it outputs:
  - What is wrong
  - Which rule is violated
  - The exact code to add/change to fix it
  - Which file to edit

Usage:
  python3 config_solution_engine.py <folder>
  python3 config_solution_engine.py --all
"""

import os
import ast
import sys
import re
import hashlib
from pathlib import Path
from collections import defaultdict
import Config_efl_brain as Config

# No cross-imports — the solution engine reads fragility data from efl_brain.db
# AgentGraph is imported lazily inside AnalyzeBlastRadius() when needed


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  ConfigSolutionEngine
# Domain: Analysis
# Authority: Scans folders for config rule violations and generates fixes
# Dependencies: os, ast, sys, re, hashlib
# ============================================================================


class ConfigSolutionEngine:
    """Scans Python folders for config rule violations and generates fixes."""

    def __init__(self):
        self.state = {}
        self.state["violations"] = []
        self.state["fixes"] = []
        self.state["files_scanned"] = 0
        self.state["folder"] = ""

    # ------------------------------------------------------------------------
    # Scanner — scan a single Python file for all violations
    # ------------------------------------------------------------------------

    def ScanFile(self, file_path, relative_name):
        """Scan one Python file for all rule violations."""
        self.state["files_scanned"] += 1

        with open(file_path, "r") as f:
            content = f.read()
            lines = content.split("\n")

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            self.state["violations"].append({
                "file": relative_name,
                "line": e.lineno,
                "rule": "SYNTAX",
                "violation": f"Syntax error: {e.msg}",
                "fix": f"Fix syntax error on line {e.lineno}: {e.msg}",
                "fix_type": "manual",
            })
            return

        # --- R1: Config Presence (checked at folder level, not file) ---

        # --- H1: Ghost Header ---
        if "GHOST HEADER" not in content[:500]:
            self.state["violations"].append({
                "file": relative_name,
                "line": 1,
                "rule": "H1",
                "violation": "Missing Ghost Header",
                "fix": self.FixGhostHeader(relative_name),
                "fix_type": "prepend",
            })

        # --- H2: VBStyle Header ---
        if "VBSTYLE HEADER" not in content[:1000]:
            self.state["violations"].append({
                "file": relative_name,
                "line": 1,
                "rule": "H2",
                "violation": "Missing VBStyle Header",
                "fix": self.FixVBStyleHeader(relative_name),
                "fix_type": "prepend",
            })

        # --- H4: Class Headers ---
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                preceding_lines = lines[max(0, node.lineno - 5):node.lineno - 1]
                has_class_header = any("CLASSES HEADER" in l or "Class:" in l for l in preceding_lines)
                if not has_class_header:
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": node.lineno,
                        "rule": "H4",
                        "violation": f"Class '{node.name}' missing Class Header",
                        "fix": self.FixClassHeader(node.name, node.lineno),
                        "fix_type": "insert",
                    })

        # --- H5: Method Headers ---
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.lineno < len(lines) and not lines[node.lineno].strip().startswith('"""') and not lines[node.lineno].strip().startswith("'''"):
                    next_line = lines[node.lineno] if node.lineno < len(lines) else ""
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        self.state["violations"].append({
                            "file": relative_name,
                            "line": node.lineno,
                            "rule": "H5",
                            "violation": f"Method '{node.name}' missing docstring",
                            "fix": self.FixMethodDocstring(node.name, node.lineno),
                            "fix_type": "insert",
                        })

        # --- N1: PascalCase Classes ---
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not node.name[0].isupper() or "_" in node.name:
                    fixed = "".join(word.capitalize() for word in node.name.split("_"))
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": node.lineno,
                        "rule": "N1",
                        "violation": f"Class '{node.name}' not PascalCase",
                        "fix": f"Rename class '{node.name}' to '{fixed}' in {relative_name}",
                        "fix_type": "rename",
                    })

        # --- N2: UPPERCASE Constants ---
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name.isupper() is False and name[0].isupper() and "_" in name and not name.startswith("__"):
                            if not name[0].islower():
                                self.state["violations"].append({
                                    "file": relative_name,
                                    "line": node.lineno,
                                    "rule": "N2",
                                    "violation": f"Constant '{name}' should be UPPERCASE",
                                    "fix": f"Rename '{name}' to '{name.upper()}' in {relative_name}",
                                    "fix_type": "rename",
                                })

        # --- C1: No Print ---
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("print(") and not stripped.startswith("#"):
                self.state["violations"].append({
                    "file": relative_name,
                    "line": i,
                    "rule": "C1",
                    "violation": f"print() statement found",
                    "fix": f"Replace print() on line {i} with logging.info() or return value.\n"
                           f"  OLD: {stripped}\n"
                           f"  NEW: logging.info({stripped[6:-1]})  # or remove if not needed",
                    "fix_type": "replace_line",
                })

        # --- C2: No Decorators ---
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("@") and not stripped.startswith("@GHOST") and not stripped.startswith("@vbsty"):
                if not any(kw in stripped for kw in ["@property"]):
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": i,
                        "rule": "C2",
                        "violation": f"Decorator found: {stripped}",
                        "fix": f"Remove decorator on line {i}: '{stripped}'.\n"
                               f"  If @staticmethod: move logic to standalone function.\n"
                               f"  If @classmethod: pass cfg as parameter instead.",
                        "fix_type": "remove_line",
                    })

        # --- C3: No Hardcoded Values ---
        hardcoded_patterns = [
            (r'["\']localhost["\']', "localhost", "MYSQL_HOST from config"),
            (r'["\']127\.0\.0\.1["\']', "127.0.0.1", "MYSQL_HOST from config"),
            (r'["\']root["\']', "root (username)", "MYSQL_USER from config"),
            (r'["\']password["\']', "password", "MYSQL_PASSWORD from env var"),
            (r'["\']vb_shared["\']', "vb_shared (db name)", "MYSQL_DB from config"),
            (r'["\']3306["\']', "3306 (port)", "MYSQL_PORT from config"),
            (r'\b3306\b', "3306 (port)", "MYSQL_PORT from config"),
        ]

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern, value, fix_target in hardcoded_patterns:
                if re.search(pattern, line):
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": i,
                        "rule": "C3/R7",
                        "violation": f"Hardcoded value: {value}",
                        "fix": f"Replace '{value}' on line {i} with cfg.{fix_target}\n"
                               f"  OLD: {stripped}\n"
                               f"  NEW: {stripped.replace(value, f'cfg.{fix_target.split()[0]}')}",
                        "fix_type": "replace_line",
                    })
                    break

        # --- C4: No Tabs ---
        for i, line in enumerate(lines, 1):
            if "\t" in line:
                self.state["violations"].append({
                    "file": relative_name,
                    "line": i,
                    "rule": "C4",
                    "violation": "Tab character found (use spaces)",
                    "fix": f"Replace tabs with 4 spaces on line {i}",
                    "fix_type": "replace_line",
                })

        # --- C6: No Enums ---
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "enum" in node.module:
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": node.lineno,
                        "rule": "C6",
                        "violation": "Enum import found — use string/integer constants instead",
                        "fix": f"Remove enum import on line {node.lineno}.\n"
                               f"  Replace with UPPERCASE constants in config:\n"
                               f"  STATUS_ACTIVE = 'active'\n"
                               f"  STATUS_PENDING = 'pending'",
                        "fix_type": "remove_and_replace",
                    })

        # --- C7: No Hidden Imports ---
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        self.state["violations"].append({
                            "file": relative_name,
                            "line": child.lineno,
                            "rule": "C7",
                            "violation": f"Import inside function '{node.name}'",
                            "fix": f"Move import from line {child.lineno} to top of file",
                            "fix_type": "move",
                        })

        # --- D1-D4: Documentation Constants (config files only) ---
        if relative_name.lower().startswith("config"):
            if "ABOUT" not in content:
                self.state["violations"].append({
                    "file": relative_name,
                    "line": 0,
                    "rule": "D1/D2",
                    "violation": "Config file missing ABOUT constant",
                    "fix": f"Add to {relative_name}:\n"
                           f'  ABOUT = """One-paragraph description of what this system is."""',
                    "fix_type": "add_constant",
                })
            if "HELP" not in content:
                self.state["violations"].append({
                    "file": relative_name,
                    "line": 0,
                    "rule": "D1/D3",
                    "violation": "Config file missing HELP constant",
                    "fix": f"Add to {relative_name}:\n"
                           f'  HELP = """Quick start + command reference."""',
                    "fix_type": "add_constant",
                })
            if "README" not in content:
                self.state["violations"].append({
                    "file": relative_name,
                    "line": 0,
                    "rule": "D1/D4",
                    "violation": "Config file missing README constant",
                    "fix": f"Add to {relative_name}:\n"
                           f'  README = """Full project documentation."""',
                    "fix_type": "add_constant",
                })

        # --- R3: FILE_INDEX (config files only) ---
        if relative_name.lower().startswith("config"):
            if "FILE_INDEX" not in content:
                self.state["violations"].append({
                    "file": relative_name,
                    "line": 0,
                    "rule": "R3",
                    "violation": "Config file missing FILE_INDEX constant",
                    "fix": self.FixFileIndex(self.state["folder"]),
                    "fix_type": "add_constant",
                })

        # --- R7: No Hardcoding — SQL table names in queries ---
        sql_table_pattern = r'(FROM|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+)'
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            matches = re.findall(sql_table_pattern, line, re.IGNORECASE)
            for _, table_name in matches:
                if table_name.lower() not in ("config", "sqlite_master", "dual"):
                    if not any(c in table_name for c in ["_TABLE", "TABLE_"]):
                        self.state["violations"].append({
                            "file": relative_name,
                            "line": i,
                            "rule": "R7",
                            "violation": f"Hardcoded table name '{table_name}' in SQL",
                            "fix": f"Define '{table_name.upper()}_TABLE = \"{table_name}\"' in config\n"
                                   f"  Then use: ... FROM {{cfg.{table_name.upper()}_TABLE}} ...",
                            "fix_type": "extract_constant",
                        })

        # --- R15: TODO/FIXME/HACK ---
        for i, line in enumerate(lines, 1):
            for marker in ["TODO", "FIXME", "HACK", "XXX"]:
                if marker in line and "#" in line:
                    comment = line.split("#", 1)[1].strip() if "#" in line else ""
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": i,
                        "rule": "R15",
                        "violation": f"{marker} found: {comment}",
                        "fix": f"Track in FILE_INDEX technical debt section.\n"
                               f"  File: {relative_name}, Line: {i}, Marker: {marker}",
                        "fix_type": "track",
                    })

        # --- R17: File Size Limit ---
        line_count = len(lines)
        if line_count > 1000:
            self.state["violations"].append({
                "file": relative_name,
                "line": 0,
                "rule": "R17",
                "violation": f"File has {line_count} lines (max 1000)",
                "fix": f"Split {relative_name} into smaller files.\n"
                       f"  Suggested split: {line_count // 500} files of ~500 lines each.\n"
                       f"  Group by class or domain.",
                "fix_type": "split_file",
            })

        # --- R17: Method count per class ---
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > 30:
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": node.lineno,
                        "rule": "R17",
                        "violation": f"Class '{node.name}' has {len(methods)} methods (max 30)",
                        "fix": f"Split class '{node.name}' into {len(methods) // 20} classes.\n"
                               f"  Group methods by responsibility.",
                        "fix_type": "split_class",
                    })

        # --- R17: Parameter count ---
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                param_count = len(node.args.args)
                if param_count > 7:
                    self.state["violations"].append({
                        "file": relative_name,
                        "line": node.lineno,
                        "rule": "R17",
                        "violation": f"Method '{node.name}' has {param_count} parameters (max 7)",
                        "fix": f"Replace {param_count} parameters with a params dict:\n"
                               f"  OLD: def {node.name}(self, {', '.join(a.arg for a in node.args.args)})\n"
                               f"  NEW: def {node.name}(self, params: dict)\n"
                               f"  Access: params['{node.args.args[1].arg}'], params['{node.args.args[2].arg}'], ...",
                        "fix_type": "refactor_params",
                    })

    # ------------------------------------------------------------------------
    # Fix Generators — produce concrete fix text
    # ------------------------------------------------------------------------

    def FixGhostHeader(self, filename):
        return (
            f"Prepend to {filename}:\n"
            f"  #!/usr/bin/env python3\n"
            f"  # ============================================================================\n"
            f"  # GHOST HEADER\n"
            f"  # ----------------------------------------------------------------------------\n"
            f"  # File:     {filename}\n"
            f"  # Domain:   <domain>\n"
            f"  # Authority: <what this file controls>\n"
            f"  # DB:       <database or None>\n"
        )

    def FixVBStyleHeader(self, filename):
        return (
            f"Prepend to {filename} (after Ghost Header):\n"
            f"  # VBSTYLE HEADER\n"
            f"  # ----------------------------------------------------------------------------\n"
            f"  # Rules followed:\n"
            f"  #   @ghost    — Ghost Header present\n"
            f"  #   @vbsty    — VBStyle Header present\n"
            f"  #   @hardcode — NO hardcoded paths\n"
            f"  #   @cstyle   — Coding style compliant\n"
        )

    def FixClassHeader(self, class_name, line):
        return (
            f"Insert before line {line}:\n"
            f"  # ============================================================================\n"
            f"  # CLASSES HEADER\n"
            f"  # ----------------------------------------------------------------------------\n"
            f"  # Class:  {class_name}\n"
            f"  # Domain: <domain>\n"
            f"  # Authority: <what this class controls>\n"
            f"  # Dependencies: <imports>\n"
            f"  # ============================================================================\n"
        )

    def FixMethodDocstring(self, method_name, line):
        return (
            f"Insert docstring on line {line + 1}:\n"
            f'  def {method_name}(self, ...):\n'
            f'      """Brief description of what this method does."""\n'
        )

    def FixFileIndex(self, folder):
        py_files = [f for f in os.listdir(folder) if f.endswith(".py")]
        entries = []
        for f in sorted(py_files):
            entries.append(
                f'    {{"file": "{f}", "purpose": "<describe>", "classes": [], "methods": [], '
                f'"functions": [], "created": "", "modified": "", "size": 0, "lines": 0}}'
            )
        return (
            f"Add to config file:\n"
            f"  FILE_INDEX = [\n"
            + "\n".join(entries) + "\n"
            f"  ]\n"
            f"\n"
            f"  def GetFileIndex(self):\n"
            f"      return self.FILE_INDEX\n"
            f"\n"
            f"  def GetFileList(self):\n"
            f"      return [entry['file'] for entry in self.FILE_INDEX]\n"
        )

    # ------------------------------------------------------------------------
    # Folder Scanner — scan entire folder
    # ------------------------------------------------------------------------

    def ScanFolder(self, folder_path):
        """Scan all Python files in a folder for violations."""
        self.state["folder"] = folder_path
        self.state["violations"] = []
        self.state["files_scanned"] = 0

        py_files = [f for f in os.listdir(folder_path) if f.endswith(".py")]

        if not py_files:
            return (False, None, f"No Python files in {folder_path}")

        # R1: Check config presence
        config_files = [f for f in py_files if f.lower().startswith("config")]
        if not config_files:
            self.state["violations"].append({
                "file": "(folder)",
                "line": 0,
                "rule": "R1",
                "violation": f"No Config file found in {folder_path}",
                "fix": (
                    f"Create Config_{os.path.basename(folder_path)}.py in {folder_path}/\n"
                    f"  Must contain:\n"
                    f"    - Ghost + VBStyle headers\n"
                    f"    - AI Guide block\n"
                    f"    - Config class with all settings\n"
                    f"    - FILE_INDEX listing all files\n"
                    f"    - SCHEMA_SQL (if DB used)\n"
                    f"    - ABOUT, HELP, README constants\n"
                    f"    - Singleton: cfg = Config()\n"
                ),
                "fix_type": "create_file",
            })

        # Scan each file
        for f in sorted(py_files):
            file_path = os.path.join(folder_path, f)
            self.ScanFile(file_path, f)

        # R9: Check for external .sql files
        sql_files = [f for f in os.listdir(folder_path) if f.endswith(".sql")]
        for sf in sql_files:
            self.state["violations"].append({
                "file": sf,
                "line": 0,
                "rule": "R9/S1",
                "violation": f"External .sql file found — must be embedded in config",
                "fix": (
                    f"Move contents of {sf} into config as:\n"
                    f"  SCHEMA_SQL = \"\"\"\n"
                    f"  <paste SQL here>\n"
                    f"  \"\"\"\n"
                    f"Then delete {sf}"
                ),
                "fix_type": "embed_and_delete",
            })

        # R9: Check for external .md files (documentation)
        md_files = [f for f in os.listdir(folder_path) if f.endswith(".md") and f != "README.md"]
        for mf in md_files:
            self.state["violations"].append({
                "file": mf,
                "line": 0,
                "rule": "R9/D1",
                "violation": f"External .md file found — must be embedded in config",
                "fix": (
                    f"Move contents of {mf} into config as:\n"
                    f"  {mf.replace('.md', '').upper()} = \"\"\"\n"
                    f"  <paste markdown here>\n"
                    f"  \"\"\"\n"
                    f"Then delete {mf}"
                ),
                "fix_type": "embed_and_delete",
            })

        return (True, self.GenerateReport(), "")

    # ------------------------------------------------------------------------
    # Report Generator
    # ------------------------------------------------------------------------

    def GenerateReport(self):
        """Generate full violation report with fixes."""
        violations = self.state["violations"]

        by_rule = {}
        for v in violations:
            rule = v["rule"]
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(v)

        by_file = {}
        for v in violations:
            file = v["file"]
            if file not in by_file:
                by_file[file] = []
            by_file[file].append(v)

        return {
            "folder": self.state["folder"],
            "files_scanned": self.state["files_scanned"],
            "total_violations": len(violations),
            "by_rule": {rule: len(items) for rule, items in by_rule.items()},
            "by_file": {file: len(items) for file, items in by_file.items()},
            "violations": violations,
        }

    def AnalyzeBlastRadius(self, folder_path):
        """Use the AgentGraph to compute blast radius of each violated file.
        Tells you: if this file breaks, what else goes down.
        Lazy import — no module-level coupling to Efi_agent_graph.py."""
        from Efi_agent_graph import AgentGraph
        ag = AgentGraph()
        ag.Build(folder_path)
        blast_report = {}
        for v in self.state["violations"]:
            file_path = v["file"]
            # Find the node matching this file
            for nid, node in ag.nodes.items():
                if node.path == file_path or nid == file_path:
                    blast = ag.BlastRadius(nid)
                    blast_report[file_path] = {
                        "violation": v["rule"],
                        "blast_radius": len(blast),
                        "affected": [os.path.basename(b) for b in blast[:10]],
                    }
                    break
        return blast_report

    def WriteToDb(self, db_path=None):
        """Write violations to efl_brain.db (the dinner table).
        Other brothers can read this without importing this file."""
        from Efi_brain_db import BrainDb
        db = BrainDb(db_path)
        db.Connect()
        violations = []
        for v in self.state["violations"]:
            violations.append({
                "file_path": v["file"],
                "rule": v["rule"],
                "severity": v.get("severity", "medium"),
                "fix_action": v.get("fix", ""),
            })
        written = db.WriteViolations(violations)
        db.Disconnect()
        return {"violations_written": written}

    def ReadFragilityFromDb(self, db_path=None):
        """Read prediction links and blast radius from efl_brain.db.
        This tells the solution engine which files are fragile (low confidence)
        without importing the agent graph. The agent graph wrote this data;
        we just read the notes from the dinner table."""
        from Efi_brain_db import BrainDb
        db = BrainDb(db_path)
        db.Connect()

        # Read blast radius for all nodes
        blast = db.ReadBlastRadius()

        # Read prediction links to find low-confidence files
        links = db.ReadPredictionLinks()
        fragile_files = defaultdict(float)
        for link in links:
            if link["confidence"] < 0.3:
                # Low confidence = fragile
                target = link["target_node"]
                fragile_files[target] = max(fragile_files[target], 1.0 - link["confidence"])

        db.Disconnect()
        return {
            "blast_radius": blast,
            "fragile_nodes": dict(fragile_files),
            "total_links": len(links),
        }

    # ------------------------------------------------------------------------
    # Run — dispatch entry
    # ------------------------------------------------------------------------

    def Run(self, command, params):
        """Dispatch entry point — returns Tuple3."""
        DISPATCH = {
            "scan": self.RunScan,
            "report": self.RunReport,
            "fixes": self.RunFixes,
            "summary": self.RunSummary,
        }

        handler = DISPATCH.get(command)
        if handler is None:
            return (False, None, f"Unknown command: {command}")
        return handler(params)

    def RunScan(self, params):
        folder = params.get("folder", "") if params else ""
        if not folder or not os.path.isdir(folder):
            return (False, None, "Invalid folder path")
        return self.ScanFolder(folder)

    def RunReport(self, params):
        return (True, self.GenerateReport(), "")

    def RunFixes(self, params):
        report = self.GenerateReport()
        fixes = []
        for v in report["violations"]:
            fixes.append({
                "file": v["file"],
                "line": v["line"],
                "rule": v["rule"],
                "violation": v["violation"],
                "fix": v["fix"],
                "fix_type": v["fix_type"],
            })
        return (True, {"total_fixes": len(fixes), "fixes": fixes}, "")

    def RunSummary(self, params):
        report = self.GenerateReport()
        return (True, {
            "folder": report["folder"],
            "files_scanned": report["files_scanned"],
            "total_violations": report["total_violations"],
            "by_rule": report["by_rule"],
        }, "")


# ============================================================================
# REPORT PRINTER
# ============================================================================

def PrintReport(report):
    """Print a human-readable violation report with fixes."""
    print(f"\n{'=' * 70}")
    print(f"  CONFIG SOLUTION ENGINE — {report['folder']}")
    print(f"{'=' * 70}")
    print(f"\n  Files scanned: {report['files_scanned']}")
    print(f"  Total violations: {report['total_violations']}")

    if report["total_violations"] == 0:
        print("\n  ✅ ALL CLEAN — no violations found")
        print(f"{'=' * 70}\n")
        return

    print(f"\n  By Rule:")
    for rule, count in sorted(report["by_rule"].items()):
        print(f"    {rule}: {count} violation(s)")

    print(f"\n  By File:")
    for file, count in sorted(report["by_file"].items()):
        print(f"    {file}: {count} violation(s)")

    print(f"\n{'─' * 70}")
    print(f"  VIOLATIONS + FIXES:")
    print(f"{'─' * 70}")

    current_file = ""
    for v in report["violations"]:
        if v["file"] != current_file:
            current_file = v["file"]
            print(f"\n  📄 {current_file}")

        print(f"\n  ❌ Line {v['line']} | Rule {v['rule']}: {v['violation']}")
        print(f"  ✅ FIX ({v['fix_type']}):")
        for fix_line in v["fix"].split("\n"):
            print(f"     {fix_line}")

    print(f"\n{'=' * 70}")
    print(f"  {report['total_violations']} violations found — fixes generated above")
    print(f"{'=' * 70}\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    engine = ConfigSolutionEngine()

    if len(sys.argv) < 2:
        print("Usage: python3 config_solution_engine.py <folder>")
        print("       python3 config_solution_engine.py --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        workspace = os.path.dirname(os.path.abspath(__file__))
        folders = [
            d for d in os.listdir(workspace)
            if os.path.isdir(os.path.join(workspace, d))
            and not d.startswith(".")
            and d not in ("mcp-server-email", "code_store_variations", "logs")
        ]

        total_violations = 0
        for folder in sorted(folders):
            folder_path = os.path.join(workspace, folder)
            ok, report, err = engine.Run("scan", {"folder": folder_path})
            if ok and report["total_violations"] > 0:
                PrintReport(report)
                total_violations += report["total_violations"]
                engine = ConfigSolutionEngine()  # reset for next folder

        print(f"\n{'=' * 70}")
        print(f"  TOTAL VIOLATIONS ACROSS ALL FOLDERS: {total_violations}")
        print(f"{'=' * 70}\n")

    else:
        folder = sys.argv[1]
        if not os.path.isabs(folder):
            folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)

        ok, report, err = engine.Run("scan", {"folder": folder})
        if not ok:
            print(f"ERROR: {err}")
            sys.exit(1)

        PrintReport(report)
