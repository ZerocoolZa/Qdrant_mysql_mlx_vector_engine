#!/usr/bin/env python3
"""
Class Discovery — find latent classes hidden in the method corpus.

Given 9,000+ methods, discover which ones belong together as classes
based on:
  1. Call affinity — methods that call each other frequently
  2. API affinity — methods using the same libraries
  3. Name patterns — methods with similar naming conventions
  4. Complexity clustering — methods with similar size/complexity
  5. Shared state — methods that call the same internal methods

Output: proposed class groupings with cohesion scores.
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class ClassDiscovery:

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

    # -----------------------------------------------------------------------
    # 1. EXISTING CLASS COHESION — how well do current classes hold?
    # -----------------------------------------------------------------------

    def existing_class_cohesion(self) -> List[dict]:
        """
        Score each existing class by:
        - internal calls (methods calling siblings)
        - shared APIs (methods using same libraries)
        - avg complexity
        - method count
        High cohesion = methods belong together. Low = class should split.
        """
        results = []
        all_names = set(self.by_name.keys())

        for class_name, methods in self.by_class.items():
            if len(methods) < 3:
                continue

            # Internal calls: how many methods call other methods in same class
            internal = 0
            external = 0
            shared_apis = defaultdict(int)
            total_cx = 0

            for m in methods:
                calls = self._get_calls(m)
                method_names_in_class = set(mm["name"] for mm in methods)
                internal += len(calls & method_names_in_class)
                external += len(calls - method_names_in_class)
                total_cx += m["cyclomatic"]
                for c in calls:
                    shared_apis[c] += 1

            # Cohesion = internal / (internal + external)
            total_calls = internal + external
            cohesion = internal / total_calls if total_calls > 0 else 0
            avg_cx = total_cx / len(methods)
            shared_api_count = sum(1 for v in shared_apis.values() if v > 1)

            results.append({
                "class_name": class_name,
                "method_count": len(methods),
                "internal_calls": internal,
                "external_calls": external,
                "cohesion": round(cohesion, 3),
                "avg_complexity": round(avg_cx, 1),
                "shared_apis": shared_api_count,
                "verdict": "STRONG" if cohesion > 0.3 else ("MODERATE" if cohesion > 0.1 else "WEAK"),
            })

        results.sort(key=lambda x: x["cohesion"])
        return results

    # -----------------------------------------------------------------------
    # 2. DISCOVER LATENT CLASSES — group methods that don't share a class
    # -----------------------------------------------------------------------

    def discover_latent_classes(self, min_cluster: int = 3) -> List[dict]:
        """
        Find methods across DIFFERENT classes that call each other heavily.
        These are latent classes — methods that belong together but are split.
        """
        # Build call affinity: which method names call which
        caller_to_callees: Dict[str, Set[str]] = defaultdict(set)
        callee_to_callers: Dict[str, Set[str]] = defaultdict(set)

        all_names = set(self.by_name.keys())
        for m in self.methods:
            calls = self._get_calls(m)
            for c in calls:
                if c in all_names:
                    caller_to_callees[m["name"]].add(c)
                    callee_to_callers[c].add(m["name"])

        # Find clusters: methods that mutually call each other
        visited = set()
        clusters = []

        def bfs_cluster(start: str) -> Set[str]:
            queue = [start]
            cluster = set()
            while queue:
                name = queue.pop(0)
                if name in visited:
                    continue
                visited.add(name)
                cluster.add(name)
                # Add methods this one calls
                for callee in caller_to_callees.get(name, []):
                    if callee not in visited:
                        queue.append(callee)
                # Add methods that call this one
                for caller in callee_to_callers.get(name, []):
                    if caller not in visited:
                        queue.append(caller)
            return cluster

        for name in all_names:
            if name in visited:
                continue
            cluster = bfs_cluster(name)
            if len(cluster) >= min_cluster:
                # Find which classes these methods span
                classes_involved = set()
                method_details = []
                for cname in cluster:
                    for m in self.by_name.get(cname, []):
                        classes_involved.add(m["class_name"])
                        method_details.append({
                            "name": m["name"],
                            "class": m["class_name"],
                            "qualname": m["qualname"],
                            "cx": m["cyclomatic"],
                            "calls": m["call_count"],
                        })

                if len(classes_involved) > 1:
                    clusters.append({
                        "method_names": list(cluster),
                        "size": len(cluster),
                        "classes_spanned": list(classes_involved),
                        "class_count": len(classes_involved),
                        "methods": method_details[:20],
                    })

        clusters.sort(key=lambda x: x["size"], reverse=True)
        return clusters

    # -----------------------------------------------------------------------
    # 3. PROPOSE NEW CLASSES — from weak existing classes
    # -----------------------------------------------------------------------

    def propose_splits(self) -> List[dict]:
        """
        For classes with low cohesion, propose how to split them.
        Group methods by their external call targets.
        """
        cohesion = self.existing_class_cohesion()
        weak = [c for c in cohesion if c["verdict"] == "WEAK" and c["method_count"] >= 5]

        proposals = []
        for w in weak:
            class_name = w["class_name"]
            methods = self.by_class[class_name]

            # Group by primary external call target
            groups: Dict[str, List[dict]] = defaultdict(list)
            for m in methods:
                calls = self._get_calls(m)
                # Find the most common external call
                external = [c for c in calls if c not in set(mm["name"] for mm in methods)]
                if external:
                    # Group by the most frequent external call
                    primary = max(external, key=lambda c: 1)
                    groups[primary].append(m)
                else:
                    groups["_internal"].append(m)

            if len(groups) > 1:
                proposal = {
                    "original_class": class_name,
                    "method_count": len(methods),
                    "cohesion": w["cohesion"],
                    "proposed_groups": [],
                }
                for target, group_methods in groups.items():
                    if len(group_methods) >= 2:
                        proposal["proposed_groups"].append({
                            "anchor_call": target,
                            "methods": [m["name"] for m in group_methods],
                            "count": len(group_methods),
                            "suggested_name": f"{class_name}_{target.capitalize()}",
                        })
                if len(proposal["proposed_groups"]) > 1:
                    proposals.append(proposal)

        return proposals

    # -----------------------------------------------------------------------
    # 4. GENERATE CLASS CODE — write actual Python class from discovered cluster
    # -----------------------------------------------------------------------

    def generate_class_code(self, cluster: dict, class_name: str = None) -> str:
        """
        Generate Python class code from a discovered method cluster.
        This is the synthesis step — write actual code.
        """
        if not class_name:
            classes = cluster.get("classes_spanned", ["Discovered"])
            class_name = classes[0] + "Unified"

        lines = []
        lines.append(f"class {class_name}:")
        lines.append(f'    """Auto-discovered class from {cluster["size"]} methods across {cluster["class_count"]} classes."""')
        lines.append("")

        for m in cluster.get("methods", []):
            name = m["name"]
            cx = m["cx"]
            calls = m["calls"]
            lines.append(f"    def {name}(self):")
            lines.append(f'        """cx={cx} calls={calls} — from {m["class"]}"""')
            lines.append(f"        # TODO: merge implementation from {m['qualname']}")
            lines.append("        pass")
            lines.append("")

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # 5. METHOD FINGERPRINT — signature shape for dedup/merge
    # -----------------------------------------------------------------------

    def method_fingerprints(self) -> List[dict]:
        """
        Find methods with identical fingerprints (same name, same arg count,
        same complexity, same call count) across different classes.
        These are merge candidates — same logic duplicated.
        """
        fingerprints: Dict[Tuple, List[dict]] = defaultdict(list)

        for m in self.methods:
            fp = (
                m["name"],
                m["arg_count"],
                m["cyclomatic"],
                m["body_lines"] // 10 * 10,  # bucket by 10-line ranges
                m["call_count"],
            )
            fingerprints[fp].append(m)

        dups = []
        for fp, methods in fingerprints.items():
            if len(methods) > 1:
                classes = set(m["class_name"] for m in methods)
                if len(classes) > 1:
                    dups.append({
                        "name": fp[0],
                        "arg_count": fp[1],
                        "complexity": fp[2],
                        "body_lines_bucket": fp[3],
                        "call_count": fp[4],
                        "classes": list(classes),
                        "class_count": len(classes),
                        "methods": [{"qualname": m["qualname"], "class": m["class_name"]} for m in methods],
                    })

        dups.sort(key=lambda x: x["class_count"], reverse=True)
        return dups


if __name__ == "__main__":
    cd = ClassDiscovery()

    print("=== EXISTING CLASS COHESION (bottom 15 — weakest) ===")
    cohesion = cd.existing_class_cohesion()
    for c in cohesion[:15]:
        print(f"  {c['verdict']:8s} coh={c['cohesion']:.3f} {c['method_count']:3d} methods  {c['class_name']}")

    print(f"\n  STRONG: {sum(1 for c in cohesion if c['verdict']=='STRONG')}")
    print(f"  MODERATE: {sum(1 for c in cohesion if c['verdict']=='MODERATE')}")
    print(f"  WEAK: {sum(1 for c in cohesion if c['verdict']=='WEAK')}")

    print("\n=== LATENT CLASSES (top 10 — methods that belong together) ===")
    latent = cd.discover_latent_classes(min_cluster=5)
    for cluster in latent[:10]:
        print(f"  {cluster['size']:3d} methods across {cluster['class_count']:3d} classes: {cluster['classes_spanned'][:5]}")
        for m in cluster["methods"][:3]:
            print(f"       {m['qualname']} (cx={m['cx']})")

    print(f"\n  Total latent clusters (5+ methods): {len(latent)}")

    print("\n=== PROPOSED SPLITS (weak classes that should break apart) ===")
    splits = cd.propose_splits()
    for p in splits[:5]:
        print(f"\n  {p['original_class']} (cohesion={p['cohesion']:.3f}, {p['method_count']} methods)")
        for g in p["proposed_groups"]:
            print(f"    -> {g['suggested_name']} ({g['count']} methods, anchor={g['anchor_call']})")
            print(f"       methods: {g['methods'][:5]}")

    print(f"\n  Total split proposals: {len(splits)}")

    print("\n=== DUPLICATE FINGERPRINTS (merge candidates) ===")
    dups = cd.method_fingerprints()
    for d in dups[:10]:
        print(f"  {d['name']:25s} cx={d['complexity']:2d} args={d['arg_count']} calls={d['call_count']} in {d['class_count']} classes:")
        for m in d["methods"][:5]:
            print(f"       {m['qualname']}")

    print(f"\n  Total duplicate fingerprints: {len(dups)}")

    print("\n=== GENERATED CLASS from top latent cluster ===")
    if latent:
        code = cd.generate_class_code(latent[0])
        print(code[:500])

    cd.close()
