# [@GHOST]{[@file<MagneticGraph.py>][@domain<Dom_Unified>][@role<graph_traversal>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<graph_traversal>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{MagneticGraph — multi-hop relationship follower. chat→file→class→BCL→rule→chat. Locate→Expand→Follow→Expand→Merge→Rank→Present.}
# [@CLASS]{MagneticGraph}
# [@METHOD]{Run,traverse,find_chat_hits,extract_files,files_to_classes,classes_to_bcl,classes_to_graph,bcl_to_callers,classes_to_rules,rules_to_chats,expand_radius,merge_windows,rank_nodes,read_state,set_config}

"""
MagneticGraph — Graph Traversal Layer (v4)

Magnetic Search (v3) does:  Locate -> Expand -> Collect -> Merge -> Present
MagneticGraph (v4) adds:    Follow relationships -> Expand again

The graph layer links windows together across domains:
  chat -> file      (chat mentions file path)
  file -> class     (file defines class)
  class -> BCL      (class has BCL stamps)
  class -> graph    (class_graph: source -> target -> relationship)
  BCL -> callers    (bcl_edges: CALL edges)
  class -> rules    (learned_rules: pattern matching)
  rule -> chat      (rule originated from chat)

Each hop expands the radius again, collecting more context.
The result is a connected neighborhood, not just isolated windows.

USAGE:
  from Dom_Unified import MagneticGraph

  mg = MagneticGraph()

  # Traverse from a keyword across all domains
  ok, data, err = mg.Run("traverse", {"query": "MemUnit", "max_hops": 3, "radius": 50})

  # Just follow class_graph edges
  ok, data, err = mg.Run("class_graph", {"class_name": "MemUnit", "limit": 10})

  # Just follow BCL call edges
  ok, data, err = mg.Run("callers", {"method": "Run", "limit": 10})
"""

import os
import re
import sys
import json
import mysql.connector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MagneticGraph:
    """
    MagneticGraph — multi-hop relationship follower.

    Domain: MAGNETIC_GRAPH
    Authority: graph traversal across chat, files, classes, BCL, rules.
    One class, one domain, one authority.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": "localhost",
                "mysql_user": "root",
                "mysql_pass": "",
                "mysql_port": 3306,
                "max_hops": 3,
                "radius": 200,
                "limit": 10,
            },
            "catalog": {
                "edges": {
                    "class_graph": "vb_shared.class_graph",
                    "bcl_edges": "bcl_ir.bcl_edges",
                    "graph_edges": "vb_shared.graph_edges",
                    "learned_rules": "vb_shared.learned_rules",
                    "code_classes": "vb_shared.code_classes",
                    "code_index": "vb_shared.code_index",
                    "devin_messages": "devin.devin_messages",
                    "bcl_methods": "bcl_ir.bcl_methods",
                },
                "hop_sequence": [
                    "chat_to_file",
                    "file_to_class",
                    "class_to_bcl",
                    "class_to_graph",
                    "bcl_to_callers",
                    "class_to_rules",
                    "rules_to_chat",
                ],
            },
            "results": {
                "last_traversal": None,
                "total_hops": 0,
                "total_nodes": 0,
                "total_edges": 0,
            },
        }
        if db:
            self.state["config"].update(db)
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params or not isinstance(params, dict):
            return default
        val = params.get(key, default)
        if val is None:
            return default
        return val

    def _conn(self, database="vb_shared"):
        cfg = self.state["config"]
        return mysql.connector.connect(
            user=cfg["mysql_user"],
            password=cfg["mysql_pass"],
            host=cfg["mysql_host"],
            port=cfg["mysql_port"],
            database=database,
            autocommit=True,
        )

    def Run(self, command, params=None):
        dispatch = {
            "traverse": self._cmd_traverse,
            "rank": self._cmd_rank,
            "class_graph": self._cmd_class_graph,
            "callers": self._cmd_callers,
            "callees": self._cmd_callees,
            "dependencies": self._cmd_dependencies,
            "chat_hits": self._cmd_chat_hits,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"unknown command: {command}", 0))
        return handler(params)

    # ════════════════════════════════════════════
    # MAIN TRAVERSAL — multi-hop across all domains
    # ════════════════════════════════════════════

    def _cmd_traverse(self, params):
        query = self._p(params, "query")
        max_hops = self._p(params, "max_hops", self.state["config"]["max_hops"])
        radius = self._p(params, "radius", self.state["config"]["radius"])
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        neighborhood = {
            "query": query,
            "max_hops": max_hops,
            "radius": radius,
            "hops": [],
            "nodes": {},
            "edges": [],
            "provenance": [],
        }
        visited = set()
        hop_count = 0

        # HOP 1: chat -> file (find chat hits, extract file paths)
        if hop_count < max_hops:
            hop_count += 1
            ok, chat_data, err = self.find_chat_hits(query, radius, limit)
            if ok and chat_data:
                neighborhood["nodes"]["chat"] = chat_data
                files = set()
                for hit in chat_data:
                    for f in hit.get("files_extracted", []):
                        if f not in visited:
                            files.add(f)
                            visited.add(f)
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "chat_to_file",
                    "from": "devin_messages",
                    "found": len(chat_data),
                    "files_extracted": list(files)[:limit],
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "chat mentions file",
                    "count": len(files),
                })

        # HOP 2: file -> class (find classes in those files)
        file_list = neighborhood["hops"][-1]["files_extracted"] if neighborhood["hops"] else []
        if hop_count < max_hops and file_list:
            hop_count += 1
            ok, class_data, err = self.files_to_classes(file_list, limit)
            if ok and class_data:
                neighborhood["nodes"]["classes"] = class_data
                class_names = set()
                for cls in class_data:
                    cn = cls.get("class_name", "")
                    if cn and cn not in visited:
                        class_names.add(cn)
                        visited.add(cn)
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "file_to_class",
                    "from": "code_classes",
                    "found": len(class_data),
                    "classes": list(class_names)[:limit],
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "file defines class",
                    "count": len(class_names),
                })

        # Also search classes directly by keyword
        ok, direct_classes, err = self.classes_by_keyword(query, limit)
        if ok and direct_classes:
            if "classes" not in neighborhood["nodes"]:
                neighborhood["nodes"]["classes"] = []
            existing = {c.get("class_name") for c in neighborhood["nodes"]["classes"]}
            for cls in direct_classes:
                if cls.get("class_name") not in existing:
                    neighborhood["nodes"]["classes"].append(cls)

        # HOP 3: class -> graph (follow class_graph edges)
        class_names = []
        if "classes" in neighborhood["nodes"]:
            class_names = [c.get("class_name", "") for c in neighborhood["nodes"]["classes"] if c.get("class_name")]
        if not class_names:
            class_names = [query]

        if hop_count < max_hops and class_names:
            hop_count += 1
            ok, graph_data, err = self.classes_to_graph(class_names, limit)
            if ok and graph_data:
                neighborhood["nodes"]["graph_edges"] = graph_data
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "class_to_graph",
                    "from": "class_graph",
                    "found": len(graph_data),
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "class_graph relationship",
                    "count": len(graph_data),
                })

        # HOP 4: class -> BCL (find BCL methods for these classes)
        if hop_count < max_hops and class_names:
            hop_count += 1
            ok, bcl_data, err = self.classes_to_bcl(class_names, limit)
            if ok and bcl_data:
                neighborhood["nodes"]["bcl_methods"] = bcl_data
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "class_to_bcl",
                    "from": "bcl_methods",
                    "found": len(bcl_data),
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "class has BCL stamp",
                    "count": len(bcl_data),
                })

        # HOP 5: BCL -> callers (follow CALL edges)
        if hop_count < max_hops:
            hop_count += 1
            ok, caller_data, err = self.bcl_to_callers(class_names, limit)
            if ok and caller_data:
                neighborhood["nodes"]["callers"] = caller_data
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "bcl_to_callers",
                    "from": "bcl_edges",
                    "found": len(caller_data),
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "CALL edge",
                    "count": len(caller_data),
                })

        # HOP 6: class -> rules (find learned rules matching class)
        if hop_count < max_hops and class_names:
            hop_count += 1
            ok, rule_data, err = self.classes_to_rules(class_names, limit)
            if ok and rule_data:
                neighborhood["nodes"]["rules"] = rule_data
                neighborhood["hops"].append({
                    "hop": hop_count,
                    "type": "class_to_rules",
                    "from": "learned_rules",
                    "found": len(rule_data),
                })
                neighborhood["provenance"].append({
                    "hop": hop_count,
                    "edge": "rule references class",
                    "count": len(rule_data),
                })

        # HOP 7: rules -> chat (find chats that mention the rules)
        if hop_count < max_hops and rule_data:
            hop_count += 1
            rule_patterns = [r.get("pattern", "") for r in rule_data if r.get("pattern")]
            if rule_patterns:
                ok, rule_chat_data, err = self.rules_to_chats(rule_patterns[:3], radius, limit)
                if ok and rule_chat_data:
                    neighborhood["nodes"]["rule_chats"] = rule_chat_data
                    neighborhood["hops"].append({
                        "hop": hop_count,
                        "type": "rules_to_chat",
                        "from": "devin_messages",
                        "found": len(rule_chat_data),
                    })
                    neighborhood["provenance"].append({
                        "hop": hop_count,
                        "edge": "rule originated from chat",
                        "count": len(rule_chat_data),
                    })

        # Merge and count
        total_nodes = sum(len(v) for v in neighborhood["nodes"].values() if isinstance(v, list))
        total_edges = sum(1 for h in neighborhood["hops"] if h.get("found", 0) > 0)
        neighborhood["total_nodes"] = total_nodes
        neighborhood["total_edges"] = total_edges
        neighborhood["total_hops"] = hop_count

        # Rank nodes — score and sort by relevance
        ok, ranked, err = self.rank_nodes(neighborhood)
        if ok:
            neighborhood["ranked_nodes"] = ranked

        self.state["results"]["last_traversal"] = query
        self.state["results"]["total_hops"] = hop_count
        self.state["results"]["total_nodes"] = total_nodes
        self.state["results"]["total_edges"] = total_edges

        return (1, neighborhood, None)

    # ════════════════════════════════════════════
    # HOP IMPLEMENTATIONS
    # ════════════════════════════════════════════

    def find_chat_hits(self, keyword, radius, limit):
        """HOP 1: Find keyword in devin_messages, expand radius, extract file paths."""
        try:
            conn = self._conn("devin")
            c = conn.cursor()
            esc = keyword.replace("'", "''").replace("\\", "\\\\")
            q = (
                "SELECT session_id, row_id, role, LEFT(content, 500) "
                f"FROM devin_messages WHERE content LIKE '%{esc}%' "
                f"ORDER BY created_at DESC LIMIT {limit}"
            )
            c.execute(q)
            hits = []
            for row in c.fetchall():
                sid, row_id, role, content = row[0], row[1], row[2], row[3] or ""
                files = self._extract_file_paths(content)
                win_start = max(0, (row_id or 0) - radius)
                win_end = (row_id or 0) + radius
                wq = (
                    "SELECT role, LEFT(content, 300) FROM devin_messages "
                    f"WHERE session_id = '{sid}' AND row_id >= {win_start} AND row_id <= {win_end} "
                    "ORDER BY row_id LIMIT 20"
                )
                c.execute(wq)
                window_lines = []
                for wrow in c.fetchall():
                    wrole = wrow[0] or ""
                    wcontent = (wrow[1] or "")[:300]
                    window_lines.append(f"[{wrole}] {wcontent}")
                hits.append({
                    "session": sid,
                    "hit_row": row_id,
                    "role": role,
                    "preview": content[:200],
                    "files_extracted": files,
                    "context_window": "\n".join(window_lines[:10]),
                })
            conn.close()
            return (1, hits, None)
        except Exception as e:
            return (0, None, ("ERR_CHAT_HITS", str(e)[:200], 0))

    def _extract_file_paths(self, text):
        """Extract file paths from text (e.g. /Users/wws/.../file.py)."""
        paths = re.findall(r'/[^\s\'"<>]+\.py', text or "")
        return list(set(paths))[:10]

    def files_to_classes(self, file_paths, limit):
        """HOP 2: Find classes defined in the given files."""
        if not file_paths:
            return (1, [], None)
        try:
            conn = self._conn("vb_shared")
            c = conn.cursor()
            results = []
            for fp in file_paths[:limit]:
                esc = fp.replace("'", "''")
                q = (
                    "SELECT class_name, description FROM code_classes "
                    f"WHERE class_code LIKE '%{esc}%' LIMIT 5"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "class_name": row[0],
                        "description": (row[1] or "")[:200],
                        "source_file": fp,
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_FILES_TO_CLASSES", str(e)[:200], 0))

    def classes_by_keyword(self, keyword, limit):
        """Find classes by keyword match."""
        try:
            conn = self._conn("vb_shared")
            c = conn.cursor()
            esc = keyword.replace("'", "''").replace("\\", "\\\\")
            q = (
                "SELECT class_name, description FROM code_classes "
                f"WHERE class_name LIKE '%{esc}%' OR description LIKE '%{esc}%' "
                f"LIMIT {limit}"
            )
            c.execute(q)
            results = []
            for row in c.fetchall():
                results.append({
                    "class_name": row[0],
                    "description": (row[1] or "")[:200],
                })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_CLASSES_BY_KEYWORD", str(e)[:200], 0))

    def classes_to_graph(self, class_names, limit):
        """HOP 3: Follow class_graph edges from these classes."""
        if not class_names:
            return (1, [], None)
        try:
            conn = self._conn("vb_shared")
            c = conn.cursor()
            results = []
            for cn in class_names[:limit]:
                esc = cn.replace("'", "''")
                q = (
                    "SELECT source_class, target_class, relationship FROM class_graph "
                    f"WHERE source_class = '{esc}' OR target_class = '{esc}' LIMIT 10"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "source": row[0],
                        "target": row[1],
                        "relationship": row[2],
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_CLASS_GRAPH", str(e)[:200], 0))

    def classes_to_bcl(self, class_names, limit):
        """HOP 4: Find BCL methods for these classes."""
        if not class_names:
            return (1, [], None)
        try:
            conn = self._conn("bcl_ir")
            c = conn.cursor()
            results = []
            for cn in class_names[:limit]:
                esc = cn.replace("'", "''")
                q = (
                    "SELECT method_name, method_type, bcl_stamp, file_path, line_start "
                    f"FROM bcl_methods WHERE method_name LIKE '%{esc}%' LIMIT 5"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "method_name": row[0],
                        "method_type": row[1],
                        "bcl_stamp": (row[2] or "")[:200],
                        "file_path": row[3],
                        "line_start": row[4],
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_CLASSES_TO_BCL", str(e)[:200], 0))

    def bcl_to_callers(self, class_names, limit):
        """HOP 5: Follow CALL edges from BCL methods."""
        if not class_names:
            return (1, [], None)
        try:
            conn = self._conn("bcl_ir")
            c = conn.cursor()
            results = []
            for cn in class_names[:limit]:
                esc = cn.replace("'", "''").replace("\\", "\\\\")
                q = (
                    "SELECT DISTINCT source_method_id, target, edge_type, line_number "
                    "FROM bcl_edges WHERE edge_type = 'CALL' AND "
                    f"(source_method_id LIKE '%{esc}%' OR target LIKE '%{esc}%') "
                    f"LIMIT 10"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "source": row[0],
                        "target": row[1],
                        "edge_type": row[2],
                        "line": row[3],
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_BCL_CALLERS", str(e)[:200], 0))

    def classes_to_rules(self, class_names, limit):
        """HOP 6: Find learned rules matching class names."""
        if not class_names:
            return (1, [], None)
        try:
            conn = self._conn("vb_shared")
            c = conn.cursor()
            results = []
            for cn in class_names[:limit]:
                esc = cn.replace("'", "''").replace("\\", "\\\\")
                q = (
                    "SELECT pattern, fix_action, confidence FROM learned_rules "
                    f"WHERE pattern LIKE '%{esc}%' OR fix_action LIKE '%{esc}%' "
                    f"ORDER BY confidence DESC LIMIT 5"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "pattern": (row[0] or "")[:200],
                        "fix": (row[1] or "")[:200],
                        "confidence": row[2],
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_CLASSES_TO_RULES", str(e)[:200], 0))

    def rules_to_chats(self, rule_patterns, radius, limit):
        """HOP 7: Find chats that mention the rule patterns."""
        if not rule_patterns:
            return (1, [], None)
        try:
            conn = self._conn("devin")
            c = conn.cursor()
            results = []
            for pattern in rule_patterns[:limit]:
                short = pattern[:50].replace("'", "''").replace("\\", "\\\\")
                if len(short) < 5:
                    continue
                q = (
                    "SELECT session_id, row_id, role, LEFT(content, 200) "
                    f"FROM devin_messages WHERE content LIKE '%{short}%' "
                    f"ORDER BY created_at DESC LIMIT 3"
                )
                c.execute(q)
                for row in c.fetchall():
                    results.append({
                        "session": row[0],
                        "hit_row": row[1],
                        "role": row[2],
                        "preview": (row[3] or "")[:150],
                        "matched_rule": pattern[:100],
                    })
            conn.close()
            return (1, results, None)
        except Exception as e:
            return (0, None, ("ERR_RULES_TO_CHAT", str(e)[:200], 0))

    # ════════════════════════════════════════════
    # NODE RANKING — score and sort by relevance
    # ════════════════════════════════════════════

    NODE_TYPE_WEIGHTS = {
        "chat": 0.60,
        "classes": 1.00,
        "graph_edges": 0.70,
        "bcl_methods": 0.80,
        "callers": 0.65,
        "rules": 0.75,
        "rule_chats": 0.50,
    }

    HOP_DISTANCE_PENALTY = 0.12

    def rank_nodes(self, neighborhood):
        """Score every node in the neighborhood and return sorted list.

        Scoring factors:
          - node type weight (classes=1.0, bcl=0.8, rules=0.75, graph=0.7, callers=0.65, chat=0.6)
          - hop distance penalty (each hop away from origin loses 0.12)
          - confidence (for rules: confidence value 0.0-1.0)
          - frequency (node appearing in multiple hops gets bonus)
          - query match (node name contains the original query gets bonus)

        Returns (1, ranked_list, None) where ranked_list is sorted desc by score.
        """
        query = neighborhood.get("query", "").lower()
        nodes = neighborhood.get("nodes", {})
        hops = neighborhood.get("hops", [])

        hop_map = {}
        for h in hops:
            hop_map[h.get("type", "")] = h.get("hop", 1)

        flat = []
        for node_type, items in nodes.items():
            if not isinstance(items, list):
                continue
            type_weight = self.NODE_TYPE_WEIGHTS.get(node_type, 0.50)
            hop_num = 1
            for h in hops:
                if h.get("found", 0) > 0 and node_type in (
                    h.get("type", "").replace("chat_to_file", "chat")
                    .replace("file_to_class", "classes")
                    .replace("class_to_graph", "graph_edges")
                    .replace("class_to_bcl", "bcl_methods")
                    .replace("bcl_to_callers", "callers")
                    .replace("class_to_rules", "rules")
                    .replace("rules_to_chat", "rule_chats")
                ):
                    hop_num = h.get("hop", 1)
                    break

            for item in items:
                if not isinstance(item, dict):
                    continue
                score = type_weight
                score -= hop_num * self.HOP_DISTANCE_PENALTY

                name = (
                    item.get("class_name")
                    or item.get("method_name")
                    or item.get("pattern")
                    or item.get("source")
                    or item.get("session")
                    or ""
                ).lower()

                if query and query in name:
                    score += 0.20

                conf = item.get("confidence")
                if conf and isinstance(conf, (int, float)):
                    score += float(conf) * 0.15

                flat.append({
                    "node_type": node_type,
                    "name": name[:120],
                    "score": round(max(0.0, min(1.0, score)), 3),
                    "hop": hop_num,
                    "data": item,
                })

        flat.sort(key=lambda x: x["score"], reverse=True)

        return (1, flat, None)

    def _cmd_rank(self, params):
        """Rank nodes from the last traversal, or run a new traverse then rank."""
        query = self._p(params, "query")
        if query:
            ok, data, err = self._cmd_traverse(params)
            if not ok:
                return (0, None, err)
            return (1, {
                "query": query,
                "ranked": data.get("ranked_nodes", []),
                "total": len(data.get("ranked_nodes", [])),
            }, None)
        last = self.state["results"].get("last_traversal")
        if not last:
            return (0, None, ("ERR_NO_TRAVERSAL", "run traverse first or pass query", 0))
        return (0, None, ("ERR_NO_TRAVERSAL", "re-run with query param", 0))

    # ════════════════════════════════════════════
    # DIRECT QUERY COMMANDS
    # ════════════════════════════════════════════

    def _cmd_class_graph(self, params):
        class_name = self._p(params, "class_name") or self._p(params, "query")
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not class_name:
            return (0, None, ("ERR_PARAMS", "class_name required", 0))
        ok, data, err = self.classes_to_graph([class_name], limit)
        if not ok:
            return (0, None, err)
        return (1, {"class": class_name, "edges": data, "count": len(data)}, None)

    def _cmd_callers(self, params):
        method = self._p(params, "method") or self._p(params, "query")
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not method:
            return (0, None, ("ERR_PARAMS", "method required", 0))
        ok, data, err = self.bcl_to_callers([method], limit)
        if not ok:
            return (0, None, err)
        return (1, {"method": method, "callers": data, "count": len(data)}, None)

    def _cmd_callees(self, params):
        method = self._p(params, "method") or self._p(params, "query")
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not method:
            return (0, None, ("ERR_PARAMS", "method required", 0))
        try:
            conn = self._conn("bcl_ir")
            c = conn.cursor()
            esc = method.replace("'", "''").replace("\\", "\\\\")
            q = (
                "SELECT DISTINCT source_method_id, target, edge_type, line_number "
                f"FROM bcl_edges WHERE edge_type = 'CALL' AND source_method_id LIKE '%{esc}%' "
                f"LIMIT {limit}"
            )
            c.execute(q)
            results = []
            for row in c.fetchall():
                results.append({
                    "source": row[0],
                    "target": row[1],
                    "edge_type": row[2],
                    "line": row[3],
                })
            conn.close()
            return (1, {"method": method, "callees": results, "count": len(results)}, None)
        except Exception as e:
            return (0, None, ("ERR_CALLEES", str(e)[:200], 0))

    def _cmd_dependencies(self, params):
        method = self._p(params, "method") or self._p(params, "query")
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not method:
            return (0, None, ("ERR_PARAMS", "method required", 0))
        try:
            conn = self._conn("bcl_ir")
            c = conn.cursor()
            esc = method.replace("'", "''").replace("\\", "\\\\")
            q = (
                "SELECT DISTINCT source_method_id, target, edge_type, resource_type "
                "FROM bcl_edges WHERE edge_type IN ('IMPORT','STATE_READ','STATE_WRITE','RESOURCE') AND "
                f"(source_method_id LIKE '%{esc}%' OR target LIKE '%{esc}%') "
                f"LIMIT {limit}"
            )
            c.execute(q)
            results = []
            for row in c.fetchall():
                results.append({
                    "source": row[0],
                    "target": row[1],
                    "edge_type": row[2],
                    "resource_type": row[3],
                })
            conn.close()
            return (1, {"method": method, "dependencies": results, "count": len(results)}, None)
        except Exception as e:
            return (0, None, ("ERR_DEPS", str(e)[:200], 0))

    def _cmd_chat_hits(self, params):
        keyword = self._p(params, "query") or self._p(params, "keyword")
        radius = self._p(params, "radius", self.state["config"]["radius"])
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not keyword:
            return (0, None, ("ERR_PARAMS", "query required", 0))
        ok, data, err = self.find_chat_hits(keyword, radius, limit)
        if not ok:
            return (0, None, err)
        return (1, {"keyword": keyword, "hits": data, "count": len(data)}, None)

    # ════════════════════════════════════════════
    # STATE
    # ════════════════════════════════════════════

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "results": dict(self.state["results"]),
        }, None)

    def set_config(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ("ERR_PARAMS", "config dict required", 0))
        self.state["config"].update(params)
        return (1, {"updated": list(params.keys())}, None)
