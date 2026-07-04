#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_repair.py
# Domain:   efl_brain
# Authority: Repair brother — takes diff results + graph + RAM AI learned fixes
#            and generates actual code fixes for each gap.
# DB:       efl_brain.db (reads diff_results, learned_fixes, agent_prediction_links;
#            writes agent_generated_fixes)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths (all from Config_efl_brain.py)
#   @cstyle   — Coding style compliant
# ============================================================================

"""
Repair Brother — generates code fixes for gaps found by the diff engine.

Pipeline:
  1. Read diff_results from efl_brain.db (gaps: MISSING methods, edges, units)
  2. Read learned_fixes from efl_brain.db (patterns with confidence)
  3. Read agent_prediction_links from efl_brain.db (fragility data)
  4. For each gap:
     a. Find matching learned fix by keyword/pattern
     b. Use the graph to understand dependencies
     c. Generate code stub for the missing element
     d. Validate with AST (syntax check)
     e. Write to agent_generated_fixes table
  5. Report: how many gaps fixed, how many skipped, confidence per fix

Usage:
  python3 Efi_repair.py              — run full repair pipeline
  python3 Efi_repair.py run repair   — same, via Run() dispatch
  python3 Efi_repair.py run report   — show last repair results
"""

import os
import sys
import ast
import sqlite3
import textwrap
from collections import defaultdict

from Config_efl_brain import DB_PATH

# Table name constants — no hardcoding (R7 compliance)
DIFF_RESULTS_TABLE = "diff_results"
LEARNED_FIXES_TABLE = "learned_fixes"
PREDICTION_LINKS_TABLE = "agent_prediction_links"
GENERATED_FIXES_TABLE = "agent_generated_fixes"


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  RepairEngine
# Domain: efl_brain
# Authority: Generates code fixes for gaps found by the diff engine
# Dependencies: sqlite3, ast, Config_efl_brain
# ============================================================================


# Class: RepairEngine — generates code fixes for gaps found by the diff engine
class RepairEngine:
    """Repair brother — generates code fixes from diff gaps and learned fixes.

    self.state holds all working data:
      state["gaps"]        — list of gap dicts from diff_results
      state["fixes"]       — list of learned fix dicts from learned_fixes
      state["generated"]   — list of generated fix dicts
      state["stats"]       — repair statistics
    """

    def __init__(self):
        """Initialize the repair brother with empty state."""
        self.state = {}
        self.state["gaps"] = []
        self.state["fixes"] = []
        self.state["generated"] = []
        self.state["stats"] = {}
        self.state["db_path"] = DB_PATH

    # ----------------------------------------------------------------
    # Read — pull gaps and fixes from the database
    # ----------------------------------------------------------------

    def ReadGaps(self):
        """Read diff_results gaps from efl_brain.db.

        Returns:
            Tuple3 (ok, count, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f"""
                SELECT domain, gap_type, element_name, purpose,
                       status, suggested_action, priority
                FROM {DIFF_RESULTS_TABLE}
                WHERE status = 'MISSING'
                ORDER BY priority DESC, domain
            """)
            rows = c.fetchall()
            self.state["gaps"] = [dict(r) for r in rows]
            conn.close()
            return (True, len(self.state["gaps"]), "")
        except Exception as e:
            return (False, 0, str(e))

    def ReadLearnedFixes(self):
        """Read learned_fixes from efl_brain.db.

        Returns:
            Tuple3 (ok, count, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f"""
                SELECT rule_name, error_pattern, fix_pattern,
                       success_count, failure_count, confidence
                FROM {LEARNED_FIXES_TABLE}
                ORDER BY confidence DESC, success_count DESC
            """)
            rows = c.fetchall()
            self.state["fixes"] = [dict(r) for r in rows]
            conn.close()
            return (True, len(self.state["fixes"]), "")
        except Exception as e:
            return (False, 0, str(e))

    def ReadFragility(self):
        """Read agent_prediction_links to understand which areas are fragile.

        Returns:
            Tuple3 (ok, data, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f"""
                SELECT source_node, target_node, confidence
                FROM {PREDICTION_LINKS_TABLE}
                WHERE confidence < 0.3
            """)
            rows = c.fetchall()
            fragile = [dict(r) for r in rows]
            conn.close()
            return (True, {"fragile_links": len(fragile), "sample": fragile[:10]}, "")
        except Exception as e:
            return (False, None, str(e))

    # ----------------------------------------------------------------
    # Generate — create code fixes for each gap
    # ----------------------------------------------------------------

    def GenerateFix(self, gap):
        """Generate a code fix for a single gap.

        Args:
            gap: dict with domain, gap_type, element_name, suggested_action

        Returns:
            dict with generated_code, fix_type, confidence, valid
        """
        domain = gap.get("domain", "unknown")
        gap_type = gap.get("gap_type", "method")
        element_name = gap.get("element_name", "unknown")
        action = gap.get("suggested_action", "CREATE")
        purpose = gap.get("purpose", "")

        # Find matching learned fix by keyword
        best_fix = None
        best_score = 0.0
        for fix in self.state["fixes"]:
            rule_name = (fix.get("rule_name") or "").lower()
            error_pattern = (fix.get("error_pattern") or "").lower()
            fix_pattern = (fix.get("fix_pattern") or "").lower()

            # Score by keyword overlap
            gap_text = f"{domain} {gap_type} {element_name} {action} {purpose}".lower()
            score = 0.0
            for word in gap_text.split():
                if len(word) > 3 and word in rule_name:
                    score += 0.3
                if len(word) > 3 and word in error_pattern:
                    score += 0.1
                if len(word) > 3 and word in fix_pattern:
                    score += 0.2

            # Boost by confidence
            score *= fix.get("confidence", 0.5)

            if score > best_score:
                best_score = score
                best_fix = fix

        # Generate code based on gap type
        if gap_type == "method":
            code = self._GenerateMethod(element_name, domain, purpose, action)
            fix_type = "CREATE_METHOD"
        elif gap_type == "edge":
            code = self._GenerateEdge(element_name, domain, action)
            fix_type = "CREATE_EDGE"
        elif gap_type == "unit":
            code = self._GenerateUnit(element_name, domain, purpose)
            fix_type = "CREATE_UNIT"
        else:
            code = f"# Unknown gap type: {gap_type}"
            fix_type = "UNKNOWN"

        # Validate with AST
        valid = self._ValidateCode(code)

        # Confidence from best matching fix
        confidence = best_fix["confidence"] if best_fix else 0.3
        matched_rule = best_fix["rule_name"] if best_fix else "none"

        return {
            "domain": domain,
            "gap_type": gap_type,
            "element_name": element_name,
            "fix_type": fix_type,
            "generated_code": code,
            "valid": valid,
            "confidence": round(confidence, 4),
            "matched_rule": matched_rule,
            "match_score": round(best_score, 4),
        }

    def _GenerateMethod(self, name, domain, purpose, action):
        """Generate a method stub for a missing method."""
        if action == "REUSE":
            return textwrap.dedent(f"""\
                # REUSE: {name} — {purpose}
                # Find existing implementation in {domain} domain and wire it
            """)

        return textwrap.dedent(f'''\
            def {name}(self, params: dict):
                """{purpose or f'{name} method for {domain} domain.'}"""
                # Domain: {domain}
                # Generated by Efi_repair.py
                return (True, {{"result": None}}, "")
            ''')

    def _GenerateEdge(self, name, domain, action):
        """Generate an edge wiring for a missing edge."""
        parts = name.split("→")
        src = parts[0].strip() if parts else "source"
        dst = parts[1].strip() if len(parts) > 1 else "target"
        return textwrap.dedent(f"""\
            # CREATE_EDGE: {src} → {dst} in {domain} domain
            # Wire the {src} method to call {dst}
            # In the calling method, add:
            #   result = self.{dst}(params)
            # Generated by Efi_repair.py
            """)

    def _GenerateUnit(self, name, domain, purpose):
        """Generate a unit stub for a missing computational unit."""
        return textwrap.dedent(f"""\
            # CREATE_UNIT: {name} in {domain} domain
            # {purpose}
            # A unit is a group of methods forming a pipeline.
            # Define the unit in the units table with method_ids.
            # Generated by Efi_repair.py
            """)

    def _ValidateCode(self, code):
        """Validate that generated code is syntactically valid Python."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    # ----------------------------------------------------------------
    # Write — save generated fixes to the database
    # ----------------------------------------------------------------

    def WriteFixes(self):
        """Write generated fixes to efl_brain.db (agent_generated_fixes table).

        Returns:
            Tuple3 (ok, count, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            c = conn.cursor()
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS {GENERATED_FIXES_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    gap_type TEXT NOT NULL,
                    element_name TEXT NOT NULL,
                    fix_type TEXT NOT NULL,
                    generated_code TEXT NOT NULL,
                    valid INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.5,
                    matched_rule TEXT,
                    writer TEXT DEFAULT 'repair',
                    written_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(domain, gap_type, element_name)
                )
            """)
            written = 0
            for fix in self.state["generated"]:
                c.execute(f"""
                    INSERT OR REPLACE INTO {GENERATED_FIXES_TABLE}
                        (domain, gap_type, element_name, fix_type, generated_code,
                         valid, confidence, matched_rule, writer, written_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'repair', datetime('now'))
                """, (
                    fix["domain"], fix["gap_type"], fix["element_name"],
                    fix["fix_type"], fix["generated_code"],
                    1 if fix["valid"] else 0,
                    fix["confidence"], fix["matched_rule"],
                ))
                written += 1
            conn.commit()
            conn.close()
            return (True, written, "")
        except Exception as e:
            return (False, 0, str(e))

    # ----------------------------------------------------------------
    # Repair — full pipeline
    # ----------------------------------------------------------------

    def RepairAll(self):
        """Run the full repair pipeline: read gaps, generate fixes, write to DB.

        Returns:
            Tuple3 (ok, data, error)
        """
        # 1. Read gaps
        ok, gap_count, err = self.ReadGaps()
        if not ok:
            return (False, None, f"ReadGaps failed: {err}")

        # 2. Read learned fixes
        ok, fix_count, err = self.ReadLearnedFixes()
        if not ok:
            return (False, None, f"ReadLearnedFixes failed: {err}")

        # 3. Read fragility
        ok, fragility, err = self.ReadFragility()
        if not ok:
            fragility = {"fragile_links": 0}

        # 4. Generate fixes for each gap
        self.state["generated"] = []
        valid_count = 0
        high_confidence_count = 0

        for gap in self.state["gaps"]:
            fix = self.GenerateFix(gap)
            self.state["generated"].append(fix)
            if fix["valid"]:
                valid_count += 1
            if fix["confidence"] > 0.7:
                high_confidence_count += 1

        # 5. Write fixes to DB
        ok, written, err = self.WriteFixes()
        if not ok:
            return (False, None, f"WriteFixes failed: {err}")

        # 6. Stats
        self.state["stats"] = {
            "gaps_found": gap_count,
            "fixes_available": fix_count,
            "fixes_generated": len(self.state["generated"]),
            "fixes_valid": valid_count,
            "fixes_invalid": len(self.state["generated"]) - valid_count,
            "high_confidence": high_confidence_count,
            "fixes_written": written,
            "fragile_links": fragility.get("fragile_links", 0),
        }

        return (True, self.state["stats"], "")

    # ----------------------------------------------------------------
    # Report — show last repair results
    # ----------------------------------------------------------------

    def Report(self):
        """Read agent_generated_fixes from DB and return a report.

        Returns:
            Tuple3 (ok, data, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f"SELECT * FROM {GENERATED_FIXES_TABLE} ORDER BY confidence DESC")
            rows = c.fetchall()
            fixes = [dict(r) for r in rows]
            conn.close()

            by_domain = defaultdict(int)
            by_type = defaultdict(int)
            valid_count = 0
            avg_confidence = 0.0

            for f in fixes:
                by_domain[f["domain"]] += 1
                by_type[f["gap_type"]] += 1
                if f["valid"]:
                    valid_count += 1
                avg_confidence += f["confidence"]

            if fixes:
                avg_confidence /= len(fixes)

            return (True, {
                "total_fixes": len(fixes),
                "valid": valid_count,
                "invalid": len(fixes) - valid_count,
                "avg_confidence": round(avg_confidence, 4),
                "by_domain": dict(by_domain),
                "by_type": dict(by_type),
                "sample": fixes[:5],
            }, "")
        except Exception as e:
            return (False, None, str(e))

    # ----------------------------------------------------------------
    # Run — dispatch entry point
    # ----------------------------------------------------------------

    def Run(self, command, params=None):
        """Dispatch entry point.

        Args:
            command: str — "repair", "report", "read_gaps", "read_fixes"
            params: dict — optional parameters

        Returns:
            Tuple3 (ok, data, error)
        """
        if params is None:
            params = {}

        if command == "repair":
            return self.RepairAll()

        elif command == "report":
            return self.Report()

        elif command == "read_gaps":
            return self.ReadGaps()

        elif command == "read_fixes":
            return self.ReadLearnedFixes()

        else:
            return (False, None, f"Unknown command: {command}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    engine = RepairEngine()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "repair"
    sub = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "run" and sub:
        ok, data, err = engine.Run(sub)
    else:
        ok, data, err = engine.Run(cmd)

    if ok:
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write("  REPAIR BROTHER — Code Fix Generator\n")
        sys.stdout.write("=" * 60 + "\n")
        if isinstance(data, dict):
            for k, v in data.items():
                if k == "sample":
                    sys.stdout.write(f"\n  Sample fixes:\n")
                    for s in v:
                        sys.stdout.write(f"    {s['domain']:12s} {s['gap_type']:8s} {s['element_name']:30s} conf={s['confidence']:.2f} valid={s['valid']}\n")
                elif isinstance(v, dict):
                    sys.stdout.write(f"\n  {k}:\n")
                    for k2, v2 in v.items():
                        sys.stdout.write(f"    {k2:20s} {v2}\n")
                else:
                    sys.stdout.write(f"  {k:25s} {v}\n")
        else:
            sys.stdout.write(f"\n  Result: {data}\n")
        sys.stdout.write("=" * 60 + "\n")
    else:
        sys.stdout.write(f"ERROR: {err}\n")
        sys.exit(1)
