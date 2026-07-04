#!/usr/bin/env python3
"""
In-RAM SQLite Mix & Match Convergence.

Load methods into :memory: SQLite, then iteratively:
  1. MERGE — collapse duplicate fingerprints into one row
  2. SPLIT — break low-cohesion classes into new class rows
  3. COMBINE — merge methods with 50%+ shared calls in same class
  4. Repeat until zero changes

Each pass actually mutates the in-RAM table. Track row count at each step.
"""

import sqlite3
import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple


SCHEMA = """
CREATE TABLE ci_methods (
    def_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    class_name  TEXT NOT NULL,
    qualname    TEXT NOT NULL,
    cyclomatic  INTEGER NOT NULL DEFAULT 0,
    max_nesting INTEGER NOT NULL DEFAULT 0,
    body_lines  INTEGER NOT NULL DEFAULT 0,
    arg_count   INTEGER NOT NULL DEFAULT 0,
    arg_names   TEXT,
    returns     TEXT,
    call_count  INTEGER NOT NULL DEFAULT 0,
    call_names  TEXT,
    recursive   INTEGER NOT NULL DEFAULT 0,
    decorators  TEXT,
    has_docstring INTEGER NOT NULL DEFAULT 0,
    docstring   TEXT,
    is_empty    INTEGER NOT NULL DEFAULT 0,
    source_code TEXT,
    ast_hash    TEXT
);
CREATE INDEX idx_name ON ci_methods(name);
CREATE INDEX idx_class ON ci_methods(class_name);
CREATE INDEX idx_qual ON ci_methods(qualname);
CREATE INDEX idx_cx ON ci_methods(cyclomatic);
CREATE INDEX idx_asthash ON ci_methods(ast_hash);
"""


class RamMixMatch:

    def __init__(self, source_db: str = "/tmp/methods.sqlite"):
        self.ram = sqlite3.connect(":memory:")
        self.ram.row_factory = sqlite3.Row
        self.ram.executescript(SCHEMA)
        self.ram.commit()
        self.source_db = source_db
        self.history = []

    def load(self) -> int:
        """Load all methods from disk SQLite into in-RAM SQLite."""
        src = sqlite3.connect(self.source_db)
        src.row_factory = sqlite3.Row
        rows = src.execute("SELECT * FROM ci_methods").fetchall()
        for r in rows:
            self.ram.execute(
                "INSERT INTO ci_methods "
                "(def_id, name, class_name, qualname, cyclomatic, max_nesting, body_lines, "
                "arg_count, arg_names, returns, call_count, call_names, recursive, "
                "decorators, has_docstring, docstring, is_empty, source_code, ast_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                tuple(r)
            )
        self.ram.commit()
        src.close()
        return len(rows)

    def count(self) -> int:
        return self.ram.execute("SELECT COUNT(*) FROM ci_methods").fetchone()[0]

    def class_count(self) -> int:
        return self.ram.execute("SELECT COUNT(DISTINCT class_name) FROM ci_methods").fetchone()[0]

    def _calls(self, row: dict) -> Set[str]:
        return set(c.strip() for c in (row["call_names"] or "").split(",") if c.strip())

    def _fingerprint(self, row: dict) -> Tuple:
        return (
            row["name"], row["arg_count"], row["cyclomatic"],
            row["body_lines"] // 10 * 10, row["call_count"],
        )

    def _ast_hash(self, row: dict) -> str:
        return row.get("ast_hash", "") or ""

    # -----------------------------------------------------------------------
    # PASS 1: MERGE — delete duplicates, keep one per fingerprint group
    # -----------------------------------------------------------------------

    def merge_pass(self) -> dict:
        """Find identical AST hashes across classes. Keep 1, delete rest.
        This is TRUE identity — same AST structure, not just similar metrics."""
        rows = self.ram.execute("SELECT * FROM ci_methods").fetchall()
        by_hash: Dict[str, List[dict]] = defaultdict(list)
        for r in rows:
            r = dict(r)
            h = self._ast_hash(r)
            if h:
                by_hash[h].append(r)

        deleted = 0
        groups_merged = 0
        for h, group in by_hash.items():
            if len(group) < 2:
                continue
            classes = set(g["class_name"] for g in group)
            if len(classes) < 2:
                continue
            # Keep the one with the lowest def_id (first created)
            keeper = min(group, key=lambda g: g["def_id"])
            # Delete the rest
            for g in group:
                if g["def_id"] != keeper["def_id"]:
                    self.ram.execute("DELETE FROM ci_methods WHERE def_id = ?", (g["def_id"],))
                    deleted += 1
            groups_merged += 1

        self.ram.commit()
        return {"deleted": deleted, "groups_merged": groups_merged}

    # -----------------------------------------------------------------------
    # PASS 2: SPLIT — rename methods in weak classes to new class names
    # -----------------------------------------------------------------------

    def split_pass(self) -> dict:
        """Find classes with <0.1 cohesion. Rename methods to new class groups."""
        classes = self.ram.execute(
            "SELECT DISTINCT class_name FROM ci_methods"
        ).fetchall()

        splits = 0
        new_classes = 0

        for (class_name,) in classes:
            methods = self.ram.execute(
                "SELECT * FROM ci_methods WHERE class_name = ?", (class_name,)
            ).fetchall()
            methods = [dict(m) for m in methods]
            if len(methods) < 5:
                continue

            method_names = set(m["name"] for m in methods)
            internal = 0
            external = 0
            for m in methods:
                calls = self._calls(m)
                internal += len(calls & method_names)
                external += len(calls - method_names)

            total = internal + external
            cohesion = internal / total if total > 0 else 0
            if cohesion > 0.1:
                continue

            # Group by primary external call
            groups: Dict[str, List[dict]] = defaultdict(list)
            for m in methods:
                calls = self._calls(m)
                ext = calls - method_names
                if ext:
                    primary = sorted(ext)[0]
                    groups[primary].append(m)
                else:
                    groups["_internal"].append(m)

            if len(groups) < 2:
                continue

            # Only split if at least 2 groups have 2+ methods
            valid = 0
            for target, gmethods in groups.items():
                if len(gmethods) >= 2:
                    valid += 1
            if valid < 2:
                continue

            # Apply: rename methods to new class
            for target, gmethods in groups.items():
                if len(gmethods) < 2:
                    continue
                new_class = f"{class_name}_{target.capitalize()}"
                if new_class != class_name:
                    for m in gmethods:
                        new_qual = f"{new_class}.{m['name']}"
                        self.ram.execute(
                            "UPDATE ci_methods SET class_name = ?, qualname = ? WHERE def_id = ?",
                            (new_class, new_qual, m["def_id"])
                        )
                    new_classes += 1
            splits += 1

        self.ram.commit()
        return {"splits": splits, "new_classes": new_classes}

    # -----------------------------------------------------------------------
    # PASS 3: COMBINE — merge methods in same class with 50%+ shared calls
    # -----------------------------------------------------------------------

    def combine_pass(self) -> dict:
        """Find methods in same class with same AST hash OR 70%+ shared calls. Delete duplicate."""
        classes = self.ram.execute(
            "SELECT DISTINCT class_name FROM ci_methods"
        ).fetchall()

        combined = 0

        for (class_name,) in classes:
            methods = self.ram.execute(
                "SELECT * FROM ci_methods WHERE class_name = ?", (class_name,)
            ).fetchall()
            methods = [dict(m) for m in methods]
            if len(methods) < 2:
                continue

            # Compare each pair
            to_delete = set()
            for i in range(len(methods)):
                if methods[i]["def_id"] in to_delete:
                    continue
                for j in range(i + 1, len(methods)):
                    if methods[j]["def_id"] in to_delete:
                        continue
                    a, b = methods[i], methods[j]

                    # Check 1: same AST hash = true duplicate
                    if self._ast_hash(a) and self._ast_hash(a) == self._ast_hash(b):
                        to_delete.add(b["def_id"])
                        combined += 1
                        break

                    # Check 2: same name + 70%+ shared calls
                    a_calls = self._calls(a)
                    b_calls = self._calls(b)
                    if not a_calls or not b_calls:
                        continue
                    shared = a_calls & b_calls
                    min_calls = min(len(a_calls), len(b_calls))
                    if min_calls > 0 and len(shared) / min_calls > 0.7:
                        if a["name"] == b["name"]:
                            to_delete.add(b["def_id"])
                            combined += 1
                            break

            for did in to_delete:
                self.ram.execute("DELETE FROM ci_methods WHERE def_id = ?", (did,))

        self.ram.commit()
        return {"combined": combined}

    # -----------------------------------------------------------------------
    # CONVERGE — loop until stable
    # -----------------------------------------------------------------------

    def converge(self) -> dict:
        """Run all passes until zero changes. Track every iteration."""
        initial = self.count()
        initial_classes = self.class_count()
        iteration = 0

        while True:
            iteration += 1
            before = self.count()
            before_classes = self.class_count()

            m = self.merge_pass()
            s = self.split_pass()
            c = self.combine_pass()

            after = self.count()
            after_classes = self.class_count()

            total_changes = m["deleted"] + s["new_classes"] + c["combined"]

            self.history.append({
                "iteration": iteration,
                "before": before,
                "after": after,
                "before_classes": before_classes,
                "after_classes": after_classes,
                "merged": m["deleted"],
                "merge_groups": m["groups_merged"],
                "split": s["splits"],
                "new_classes": s["new_classes"],
                "combined": c["combined"],
                "total_changes": total_changes,
            })

            if total_changes == 0:
                break
            if iteration > 20:
                break

        final = self.count()
        final_classes = self.class_count()

        return {
            "initial_methods": initial,
            "final_methods": final,
            "eliminated": initial - final,
            "initial_classes": initial_classes,
            "final_classes": final_classes,
            "iterations": iteration,
            "history": self.history,
            "converged": total_changes == 0,
        }

    # -----------------------------------------------------------------------
    # REPORT
    # -----------------------------------------------------------------------

    def report(self):
        """Print full convergence report."""
        result = self.converge()

        print("=" * 70)
        print("IN-RAM MIX & MATCH CONVERGENCE")
        print("=" * 70)
        print()
        print(f"  Start:     {result['initial_methods']:5d} methods, {result['initial_classes']:4d} classes")
        print(f"  End:       {result['final_methods']:5d} methods, {result['final_classes']:4d} classes")
        print(f"  Eliminated: {result['eliminated']:4d} methods")
        print(f"  Iterations: {result['iterations']}")
        print(f"  Converged:  {result['converged']}")
        print()

        print("  ITERATION HISTORY:")
        print(f"  {'Iter':>4}  {'Before':>6}  {'After':>6}  {'Classes':>8}  {'Merged':>7}  {'Split':>6}  {'Combined':>9}  {'Total':>6}")
        print(f"  {'----':>4}  {'------':>6}  {'-----':>6}  {'-------':>8}  {'------':>7}  {'-----':>6}  {'--------':>9}  {'-----':>6}")
        for h in result["history"]:
            print(f"  {h['iteration']:4d}  {h['before']:6d}  {h['after']:6d}  "
                  f"{h['before_classes']:3d}→{h['after_classes']:3d}  "
                  f"{h['merged']:7d}  {h['new_classes']:6d}  {h['combined']:9d}  {h['total_changes']:6d}")

        print()
        print("  FINAL STATE:")
        stats = self.ram.execute(
            "SELECT COUNT(*) as total, "
            "COUNT(DISTINCT class_name) as classes, "
            "COUNT(DISTINCT name) as unique_names, "
            "COUNT(DISTINCT ast_hash) as unique_hashes, "
            "AVG(cyclomatic) as avg_cx, MAX(cyclomatic) as max_cx, "
            "SUM(recursive) as recursive, SUM(is_empty) as empty, "
            "SUM(has_docstring) as documented "
            "FROM ci_methods"
        ).fetchone()
        print(f"    Methods:          {stats['total']}")
        print(f"    Classes:          {stats['classes']}")
        print(f"    Unique names:     {stats['unique_names']}")
        print(f"    Unique AST hashes:{stats['unique_hashes']}")
        print(f"    Avg complexity:   {stats['avg_cx']:.1f}")
        print(f"    Max complexity:   {stats['max_cx']}")
        print(f"    Recursive:        {stats['recursive']}")
        print(f"    Empty:            {stats['empty']}")
        print(f"    Documented:       {stats['documented']}")

        print()
        print("  TOP 10 CLASSES (by method count after convergence):")
        rows = self.ram.execute(
            "SELECT class_name, COUNT(*) as cnt, AVG(cyclomatic) as avg_cx "
            "FROM ci_methods GROUP BY class_name ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"    {r['cnt']:3d} methods  cx={r['avg_cx']:.1f}  {r['class_name']}")

        print()
        print("  TOP 10 GOD METHODS (after convergence):")
        rows = self.ram.execute(
            "SELECT qualname, cyclomatic, body_lines, call_count "
            "FROM ci_methods ORDER BY cyclomatic DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"    cx={r['cyclomatic']:3d} lines={r['body_lines']:4d} calls={r['call_count']:3d}  {r['qualname']}")

        print()
        print("  TOP 10 REMAINING DUPLICATES (same hash, different classes):")
        rows = self.ram.execute(
            "SELECT ast_hash, COUNT(*) as cnt, name, "
            "GROUP_CONCAT(DISTINCT class_name) as classes "
            "FROM ci_methods WHERE ast_hash != '' "
            "GROUP BY ast_hash HAVING cnt > 1 ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            cls_list = r['classes'][:80] if r['classes'] else ''
            print(f"    {r['cnt']:3d} copies  {r['name']:25s}  classes: {cls_list}...")

        print()
        reduction = (1 - result['final_methods'] / result['initial_methods']) * 100
        print(f"  REDUCTION: {result['initial_methods']} → {result['final_methods']} ({reduction:.1f}% eliminated)")
        print(f"  CLASSES:   {result['initial_classes']} → {result['final_classes']}")


if __name__ == "__main__":
    t0 = time.time()
    engine = RamMixMatch("/tmp/methods.sqlite")
    loaded = engine.load()
    t1 = time.time()
    print(f"Loaded {loaded} methods into RAM in {t1-t0:.3f}s")
    print()
    engine.report()
    t2 = time.time()
    print(f"\nTotal time: {t2-t0:.3f}s (convergence: {t2-t1:.3f}s)")
    engine.ram.close()
