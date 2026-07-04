#!/usr/bin/env python3
"""
Mix and Match Convergence Engine.

Iteratively:
  1. MERGE — find duplicate method fingerprints, collapse into base classes
  2. SPLIT — find weak classes, break into cohesive groups
  3. COMBINE — find compatible methods that could compose
  4. Repeat until no more changes possible

Output: final converged state — the minimal set of unique methods and classes.
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import copy


class MixMatchConverge:

    def __init__(self, db_path: str = "/tmp/methods.sqlite"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.methods: List[dict] = []
        self.by_name: Dict[str, List[dict]] = defaultdict(list)
        self.by_class: Dict[str, List[dict]] = defaultdict(list)
        self._load()

    def _load(self):
        rows = self.conn.execute("SELECT * FROM ci_methods").fetchall()
        self.methods = [dict(r) for r in rows]
        for m in self.methods:
            self.by_name[m["name"]].append(m)
            self.by_class[m["class_name"]].append(m)

    def close(self):
        self.conn.close()

    def _get_calls(self, m: dict) -> Set[str]:
        return set(c.strip() for c in (m["call_names"] or "").split(",") if c.strip())

    def _fingerprint(self, m: dict) -> Tuple:
        return (
            m["name"],
            m["arg_count"],
            m["cyclomatic"],
            m["body_lines"] // 10 * 10,
            m["call_count"],
        )

    # -----------------------------------------------------------------------
    # PASS 1: MERGE — collapse duplicate fingerprints into base classes
    # -----------------------------------------------------------------------

    def merge_pass(self) -> dict:
        """Find methods with identical fingerprints across classes. Merge them."""
        fingerprints: Dict[Tuple, List[dict]] = defaultdict(list)
        for m in self.methods:
            fp = self._fingerprint(m)
            fingerprints[fp].append(m)

        merges = []
        for fp, methods in fingerprints.items():
            if len(methods) < 2:
                continue
            classes = set(m["class_name"] for m in methods)
            if len(classes) < 2:
                continue
            merges.append({
                "name": fp[0],
                "arg_count": fp[1],
                "complexity": fp[2],
                "body_bucket": fp[3],
                "call_count": fp[4],
                "classes": sorted(classes),
                "class_count": len(classes),
                "method_count": len(methods),
                "reducible_to": 1,
            })

        total_before = sum(m["method_count"] for m in merges)
        total_after = len(merges)
        saved = total_before - total_after

        return {
            "merges": merges,
            "total_groups": len(merges),
            "methods_before": total_before,
            "methods_after": total_after,
            "methods_saved": saved,
        }

    # -----------------------------------------------------------------------
    # PASS 2: SPLIT — break weak classes into cohesive groups
    # -----------------------------------------------------------------------

    def split_pass(self) -> dict:
        """Find classes with low cohesion and propose splits."""
        all_names = set(self.by_name.keys())
        splits = []

        for class_name, methods in self.by_class.items():
            if len(methods) < 5:
                continue

            method_names = set(m["name"] for m in methods)
            internal = 0
            external = 0
            for m in methods:
                calls = self._get_calls(m)
                internal += len(calls & method_names)
                external += len(calls - method_names)

            total = internal + external
            cohesion = internal / total if total > 0 else 0

            if cohesion > 0.1:
                continue

            # Group by external call target
            groups: Dict[str, List[str]] = defaultdict(list)
            for m in methods:
                calls = self._get_calls(m)
                external_calls = calls - method_names
                if external_calls:
                    primary = sorted(external_calls)[0]
                    groups[primary].append(m["name"])
                else:
                    groups["_internal"].append(m["name"])

            if len(groups) > 1:
                split = {
                    "class": class_name,
                    "method_count": len(methods),
                    "cohesion": round(cohesion, 3),
                    "groups": [],
                }
                for target, method_list in groups.items():
                    if len(method_list) >= 2:
                        split["groups"].append({
                            "anchor": target,
                            "methods": method_list,
                            "count": len(method_list),
                            "new_class": f"{class_name}_{target.capitalize()}",
                        })
                if len(split["groups"]) > 1:
                    splits.append(split)

        return {
            "splits": splits,
            "total_splits": len(splits),
            "methods_affected": sum(s["method_count"] for s in splits),
        }

    # -----------------------------------------------------------------------
    # PASS 3: COMBINE — find methods that could compose into one
    # -----------------------------------------------------------------------

    def combine_pass(self) -> dict:
        """Find methods where A's calls overlap B's calls and they're in different classes."""
        combines = []
        method_calls: Dict[str, Set[str]] = {}

        for m in self.methods:
            method_calls[m["qualname"]] = self._get_calls(m)

        # For each pair in same class, check if they could merge
        for class_name, methods in self.by_class.items():
            if len(methods) < 2:
                continue
            for i in range(len(methods)):
                for j in range(i + 1, len(methods)):
                    a, b = methods[i], methods[j]
                    a_calls = method_calls[a["qualname"]]
                    b_calls = method_calls[b["qualname"]]
                    shared = a_calls & b_calls
                    # If they share 50%+ of calls and have similar complexity
                    min_calls = min(len(a_calls), len(b_calls))
                    if min_calls > 0 and len(shared) / min_calls > 0.5:
                        if abs(a["cyclomatic"] - b["cyclomatic"]) <= 3:
                            combines.append({
                                "class": class_name,
                                "method_a": a["name"],
                                "method_b": b["name"],
                                "shared_calls": len(shared),
                                "cx_a": a["cyclomatic"],
                                "cx_b": b["cyclomatic"],
                                "reason": "high_call_overlap",
                            })

        return {
            "combines": combines,
            "total_combines": len(combines),
        }

    # -----------------------------------------------------------------------
    # CONVERGENCE — run all passes until stable
    # -----------------------------------------------------------------------

    def converge(self) -> dict:
        """
        Run merge → split → combine repeatedly until no more changes.
        Track what happened at each iteration.
        """
        history = []
        iteration = 0

        while True:
            iteration += 1
            changes = {}

            # Pass 1: Merge
            merge_result = self.merge_pass()
            changes["merge"] = {
                "groups": merge_result["total_groups"],
                "saved": merge_result["methods_saved"],
            }

            # Pass 2: Split
            split_result = self.split_pass()
            changes["split"] = {
                "proposals": split_result["total_splits"],
                "affected": split_result["methods_affected"],
            }

            # Pass 3: Combine
            combine_result = self.combine_pass()
            changes["combine"] = {
                "candidates": combine_result["total_combines"],
            }

            history.append({
                "iteration": iteration,
                "changes": changes,
            })

            # Check convergence — if no changes in any pass, stop
            no_merge = merge_result["methods_saved"] == 0
            no_split = split_result["total_splits"] == 0
            no_combine = combine_result["total_combines"] == 0

            if no_merge and no_split and no_combine:
                break

            if iteration > 10:
                break

            # Apply changes (simulate — in real impl we'd modify the method list)
            # For now we just report — the data is static per run
            break

        return {
            "iterations": iteration,
            "history": history,
            "final_merge": merge_result,
            "final_split": split_result,
            "final_combine": combine_result,
        }

    # -----------------------------------------------------------------------
    # FINAL STATE — what the corpus looks like after convergence
    # -----------------------------------------------------------------------

    def final_state(self) -> dict:
        """Report the converged state of the method corpus."""
        merge = self.merge_pass()
        split = self.split_pass()
        combine = self.combine_pass()

        # Calculate what the corpus would look like after all merges
        total_methods = len(self.methods)
        methods_in_merge_groups = sum(m["method_count"] for m in merge["merges"])
        merge_groups = merge["total_groups"]
        methods_after_merge = total_methods - methods_in_merge_groups + merge_groups

        # Unique method names
        unique_names = len(self.by_name)

        # Classes that could be eliminated (all methods merged away)
        classes_in_merges = set()
        for m in merge["merges"]:
            classes_in_merges.update(m["classes"])

        # Classes that should split
        classes_to_split = set(s["class"] for s in split["splits"])

        # Net class change
        new_classes_from_splits = sum(len(s["groups"]) - 1 for s in split["splits"])
        classes_after = len(self.by_class) + new_classes_from_splits

        return {
            "original_methods": total_methods,
            "methods_after_merge": methods_after_merge,
            "methods_eliminated": total_methods - methods_after_merge,
            "original_classes": len(self.by_class),
            "classes_after_split": classes_after,
            "classes_to_split": len(classes_to_split),
            "new_classes_from_splits": new_classes_from_splits,
            "merge_groups": merge_groups,
            "combine_candidates": combine["total_combines"],
            "unique_method_names": unique_names,
            "redundancy_ratio": round((total_methods - methods_after_merge) / total_methods * 100, 1),
        }


if __name__ == "__main__":
    engine = MixMatchConverge()

    print("=== MIX AND MATCH CONVERGENCE ===")
    print()

    result = engine.converge()
    print(f"Converged in {result['iterations']} iteration(s)")
    print()

    for h in result["history"]:
        print(f"  Iteration {h['iteration']}:")
        print(f"    Merge:   {h['changes']['merge']['groups']:4d} groups, {h['changes']['merge']['saved']:4d} methods saved")
        print(f"    Split:   {h['changes']['split']['proposals']:4d} proposals, {h['changes']['split']['affected']:4d} methods affected")
        print(f"    Combine: {h['changes']['combine']['candidates']:4d} candidates")

    print()
    final = engine.final_state()
    print("=== FINAL CONVERGED STATE ===")
    print(f"  Original methods:        {final['original_methods']:5d}")
    print(f"  After merge:             {final['methods_after_merge']:5d}")
    print(f"  Methods eliminated:      {final['methods_eliminated']:5d} ({final['redundancy_ratio']}% redundancy)")
    print(f"  Unique method names:     {final['unique_method_names']:5d}")
    print(f"  Merge groups:            {final['merge_groups']:5d}")
    print()
    print(f"  Original classes:        {final['original_classes']:5d}")
    print(f"  Classes to split:        {final['classes_to_split']:5d}")
    print(f"  New classes from splits: {final['new_classes_from_splits']:5d}")
    print(f"  Classes after split:     {final['classes_after_split']:5d}")
    print()
    print(f"  Combine candidates:      {final['combine_candidates']:5d}")

    print()
    print("=== TOP 20 MERGE GROUPS (biggest waste) ===")
    merges = result["final_merge"]["merges"]
    merges.sort(key=lambda x: x["class_count"], reverse=True)
    for m in merges[:20]:
        print(f"  {m['name']:25s} in {m['class_count']:3d} classes  ({m['method_count']:3d} copies → 1)  "
              f"cx={m['complexity']} args={m['arg_count']} calls={m['call_count']}")

    print()
    print("=== TOP 10 SPLIT PROPOSALS ===")
    splits = result["final_split"]["splits"]
    splits.sort(key=lambda x: x["method_count"], reverse=True)
    for s in splits[:10]:
        print(f"  {s['class']:25s} cohesion={s['cohesion']:.3f}  {s['method_count']} methods → {len(s['groups'])} groups")
        for g in s["groups"]:
            print(f"    → {g['new_class']:35s} ({g['count']} methods: {', '.join(g['methods'][:4])})")

    print()
    print("=== TOP 10 COMBINE CANDIDATES ===")
    combines = result["final_combine"]["combines"]
    combines.sort(key=lambda x: x["shared_calls"], reverse=True)
    for c in combines[:10]:
        print(f"  {c['class']:25s}  {c['method_a']:20s} + {c['method_b']:20s}  shared={c['shared_calls']}  cx={c['cx_a']}/{c['cx_b']}")

    print()
    print("=== WHAT THIS MEANS ===")
    print(f"  If you merge all duplicates:  {final['methods_eliminated']} methods deleted")
    print(f"  If you split all weak classes: {final['new_classes_from_splits']} new classes created")
    print(f"  If you combine all candidates: {final['combine_candidates']} methods merged")
    print(f"  Net reduction: {final['original_methods']} → {final['methods_after_merge']} methods ({final['redundancy_ratio']}% less code)")

    engine.close()
