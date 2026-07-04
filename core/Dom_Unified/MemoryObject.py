# [@GHOST]{[@file<MemoryObject.py>][@domain<Dom_Unified>][@role<memory_compiler>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<memory_compiler>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{MemoryObject — persistent evolving memory. Compile once, recall instantly, update incrementally, evolve over time. Not search — memory cognition infrastructure.}
# [@CLASS]{MemoryObject}
# [@METHOD]{Run,compile,recall,update,evolve,diff,list,forget,read_state,set_config}

"""
MemoryObject — Persistent Evolving Memory Compiler

Magnetic Search (v3) reconstructs context per query.
MagneticGraph (v4) follows relationships per query.
MemoryObject (v5) COMPILES the result into a persistent object that:
  1. Compiles once — first query creates the memory object
  2. Recalls instantly — subsequent queries load from storage (no recomputation)
  3. Updates incrementally — new data merges into existing object
  4. Evolves over time — versioned changes recorded in evolution log
  5. Preserves provenance — where each piece came from
  6. Preserves blast-radius context — the ±N message windows
  7. Preserves graph edges — the relationships

This is NOT search. This is memory cognition infrastructure.

USAGE:
  from Dom_Unified import MemoryObject

  mo = MemoryObject()

  # Compile — run magnetic search, store result as persistent object
  ok, data, err = mo.Run("compile", {"query": "MemUnit", "mode": "magnetic", "radius": 50})

  # Recall — load from storage instantly (no recomputation)
  ok, data, err = mo.Run("recall", {"query": "MemUnit"})

  # Update — check for new data since last update, merge incrementally
  ok, data, err = mo.Run("update", {"query": "MemUnit"})

  # Evolve — show what changed over time
  ok, data, err = mo.Run("evolve", {"query": "MemUnit"})

  # Diff — compare current version to previous
  ok, data, err = mo.Run("diff", {"query": "MemUnit"})

  # List — all memory objects
  ok, data, err = mo.Run("list", {"limit": 10})

  # Forget — delete a memory object
  ok, data, err = mo.Run("forget", {"query": "MemUnit"})
"""

import os
import sys
import json
import hashlib
import mysql.connector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MemoryObject:
    """
    MemoryObject — persistent evolving memory compiler.

    Domain: MEMORY_OBJECT
    Authority: compile, store, recall, update, evolve memory objects.
    One class, one domain, one authority.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": "localhost",
                "mysql_user": "root",
                "mysql_pass": "",
                "mysql_port": 3306,
                "mysql_db": "vb_shared",
                "default_radius": 200,
                "default_mode": "magnetic",
                "default_limit": 10,
            },
            "results": {
                "last_compile": None,
                "last_recall": None,
                "total_objects": 0,
                "total_compiles": 0,
                "total_recalls": 0,
                "total_updates": 0,
                "total_evolutions": 0,
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

    def _conn(self):
        cfg = self.state["config"]
        return mysql.connector.connect(
            user=cfg["mysql_user"],
            password=cfg["mysql_pass"],
            host=cfg["mysql_host"],
            port=cfg["mysql_port"],
            database=cfg["mysql_db"],
            autocommit=True,
        )

    def _query_key(self, query, mode):
        raw = f"{query.lower()}:{mode}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def Run(self, command, params=None):
        dispatch = {
            "compile": self._cmd_compile,
            "recall": self._cmd_recall,
            "update": self._cmd_update,
            "evolve": self._cmd_evolve,
            "diff": self._cmd_diff,
            "list": self._cmd_list,
            "forget": self._cmd_forget,
            "decay": self._cmd_decay,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"unknown command: {command}", 0))
        return handler(params)

    # ════════════════════════════════════════════
    # COMPILE — run magnetic search, store as persistent object
    # ════════════════════════════════════════════

    def _cmd_compile(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        radius = self._p(params, "radius", self.state["config"]["default_radius"])
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        force = self._p(params, "force", False)
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)

        # Check if already exists
        existing = self._load_object(qkey)
        if existing and not force:
            # Already compiled — recall instead
            self.state["results"]["last_compile"] = query
            return (1, {
                "query": query,
                "mode": mode,
                "status": "already_compiled",
                "object_id": existing["id"],
                "version": existing["version"],
                "section_counts": existing.get("section_counts", {}),
                "access_count": existing["access_count"],
                "created_at": existing["created_at"],
                "updated_at": existing["updated_at"],
            }, None)

        # Run magnetic search to get the packet
        packet = self._run_magnetic(query, mode, radius, limit)
        if not packet:
            return (0, None, ("ERR_COMPILE", "magnetic search returned no data", 0))

        provenance = self._build_provenance(packet)
        graph_edges = self._extract_graph_edges(packet)
        section_counts = self._count_sections(packet)

        # Store in MySQL
        conn = self._conn()
        c = conn.cursor()
        if existing and force:
            # Force recompile — update existing
            c.execute(
                "UPDATE memory_objects SET packet = %s, provenance = %s, graph_edges = %s, "
                "section_counts = %s, version = version + 1, radius = %s WHERE id = %s",
                (json.dumps(packet), json.dumps(provenance), json.dumps(graph_edges),
                 json.dumps(section_counts), radius, existing["id"])
            )
            obj_id = existing["id"]
            new_version = existing["version"] + 1
            change_type = "recompiled"
            change_summary = f"Force recompiled with radius={radius}"
        else:
            # New object
            c.execute(
                "INSERT INTO memory_objects (query_key, query_text, mode, radius, packet, "
                "provenance, graph_edges, section_counts, version) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)",
                (qkey, query, mode, radius, json.dumps(packet),
                 json.dumps(provenance), json.dumps(graph_edges),
                 json.dumps(section_counts))
            )
            obj_id = c.lastrowid
            new_version = 1
            change_type = "compiled"
            change_summary = f"Initial compilation with mode={mode}, radius={radius}"

        # Record evolution
        c.execute(
            "INSERT INTO memory_object_evolution (memory_object_id, version, change_type, "
            "change_summary, sections_affected, delta_count) VALUES (%s, %s, %s, %s, %s, %s)",
            (obj_id, new_version, change_type, change_summary,
             ",".join(section_counts.keys()), sum(section_counts.values()))
        )

        conn.close()

        self.state["results"]["last_compile"] = query
        self.state["results"]["total_compiles"] += 1

        return (1, {
            "query": query,
            "mode": mode,
            "status": "compiled" if not existing else "recompiled",
            "object_id": obj_id,
            "version": new_version,
            "radius": radius,
            "section_counts": section_counts,
            "total_nodes": sum(section_counts.values()),
            "provenance": provenance,
        }, None)

    # ════════════════════════════════════════════
    # RECALL — load from storage instantly (no recomputation)
    # ════════════════════════════════════════════

    def _cmd_recall(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)
        obj = self._load_object(qkey)
        if not obj:
            return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}' (mode={mode}). Compile first.", 0))

        # Increment access count, update last_accessed_at, recalculate decay
        conn = self._conn()
        c = conn.cursor()
        decay = self._compute_decay(obj)
        c.execute(
            "UPDATE memory_objects SET access_count = access_count + 1, "
            "last_accessed_at = NOW(), decay_score = %s WHERE id = %s",
            (decay["decay_score"], obj["id"])
        )
        conn.close()

        packet = obj.get("packet", {})
        if isinstance(packet, str):
            packet = json.loads(packet)

        self.state["results"]["last_recall"] = query
        self.state["results"]["total_recalls"] += 1

        return (1, {
            "query": query,
            "mode": mode,
            "status": "recalled",
            "object_id": obj["id"],
            "version": obj["version"],
            "access_count": obj["access_count"] + 1,
            "created_at": obj["created_at"],
            "updated_at": obj["updated_at"],
            "section_counts": obj.get("section_counts", {}),
            "packet": packet,
            "provenance": obj.get("provenance", {}),
            "graph_edges": obj.get("graph_edges", {}),
            "decay": decay,
        }, None)

    # ════════════════════════════════════════════
    # UPDATE — check for new data, merge incrementally
    # ════════════════════════════════════════════

    def _cmd_update(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        radius = self._p(params, "radius", self.state["config"]["default_radius"])
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)
        obj = self._load_object(qkey)
        if not obj:
            return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}'. Compile first.", 0))

        old_packet = obj.get("packet", {})
        if isinstance(old_packet, str):
            old_packet = json.loads(old_packet)

        # Run magnetic search again to get fresh data
        new_packet = self._run_magnetic(query, mode, radius, limit)
        if not new_packet:
            return (0, None, ("ERR_UPDATE", "magnetic search returned no data", 0))

        # Diff the packets
        changes = self._diff_packets(old_packet, new_packet)

        if not changes["has_changes"]:
            self.state["results"]["total_updates"] += 1
            return (1, {
                "query": query,
                "status": "no_changes",
                "object_id": obj["id"],
                "version": obj["version"],
                "checked_at": obj["updated_at"],
            }, None)

        # Merge: update the stored object
        new_provenance = self._build_provenance(new_packet)
        new_graph = self._extract_graph_edges(new_packet)
        new_counts = self._count_sections(new_packet)

        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "UPDATE memory_objects SET packet = %s, provenance = %s, graph_edges = %s, "
            "section_counts = %s, version = version + 1, radius = %s WHERE id = %s",
            (json.dumps(new_packet), json.dumps(new_provenance), json.dumps(new_graph),
             json.dumps(new_counts), radius, obj["id"])
        )
        new_version = obj["version"] + 1

        # Record evolution
        sections_changed = ",".join(changes["sections_changed"])
        c.execute(
            "INSERT INTO memory_object_evolution (memory_object_id, version, change_type, "
            "change_summary, sections_affected, delta_count) VALUES (%s, %s, %s, %s, %s, %s)",
            (obj["id"], new_version, "incremental_update",
             changes["summary"], sections_changed, changes["delta_count"])
        )
        conn.close()

        self.state["results"]["total_updates"] += 1

        return (1, {
            "query": query,
            "status": "updated",
            "object_id": obj["id"],
            "version": new_version,
            "changes": changes,
            "new_section_counts": new_counts,
        }, None)

    # ════════════════════════════════════════════
    # EVOLVE — show evolution history
    # ════════════════════════════════════════════

    def _cmd_evolve(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)
        obj = self._load_object(qkey)
        if not obj:
            return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}'. Compile first.", 0))

        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT version, change_type, change_summary, sections_affected, delta_count, changed_at "
            "FROM memory_object_evolution WHERE memory_object_id = %s ORDER BY version ASC",
            (obj["id"],)
        )
        evolution = []
        for row in c.fetchall():
            evolution.append({
                "version": row[0],
                "change_type": row[1],
                "summary": row[2],
                "sections_affected": row[3],
                "delta_count": row[4],
                "changed_at": row[5],
            })
        conn.close()

        self.state["results"]["total_evolutions"] += 1

        return (1, {
            "query": query,
            "object_id": obj["id"],
            "current_version": obj["version"],
            "access_count": obj["access_count"],
            "created_at": obj["created_at"],
            "updated_at": obj["updated_at"],
            "evolution_history": evolution,
            "total_evolutions": len(evolution),
        }, None)

    # ════════════════════════════════════════════
    # DIFF — compare current to previous version
    # ════════════════════════════════════════════

    def _cmd_diff(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)
        obj = self._load_object(qkey)
        if not obj:
            return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}'. Compile first.", 0))

        conn = self._conn()
        c = conn.cursor()
        # Get last two evolution entries
        c.execute(
            "SELECT version, change_type, change_summary, sections_affected, delta_count, changed_at "
            "FROM memory_object_evolution WHERE memory_object_id = %s ORDER BY version DESC LIMIT 2",
            (obj["id"],)
        )
        rows = c.fetchall()
        conn.close()

        if len(rows) < 2:
            return (1, {
                "query": query,
                "status": "no_previous_version",
                "current_version": obj["version"],
                "message": "Only one version exists — no diff available",
            }, None)

        current = {
            "version": rows[0][0], "change_type": rows[0][1], "summary": rows[0][2],
            "sections": rows[0][3], "delta": rows[0][4], "changed_at": rows[0][5],
        }
        previous = {
            "version": rows[1][0], "change_type": rows[1][1], "summary": rows[1][2],
            "sections": rows[1][3], "delta": rows[1][4], "changed_at": rows[1][5],
        }

        return (1, {
            "query": query,
            "current": current,
            "previous": previous,
            "version_delta": current["version"] - previous["version"],
            "delta_count_delta": current["delta"] - previous["delta"],
        }, None)

    # ════════════════════════════════════════════
    # LIST — all memory objects
    # ════════════════════════════════════════════

    def _cmd_list(self, params):
        limit = self._p(params, "limit", 20)
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, query_text, mode, version, access_count, "
            "section_counts, created_at, updated_at "
            "FROM memory_objects ORDER BY updated_at DESC LIMIT %s",
            (limit,)
        )
        objects = []
        for row in c.fetchall():
            counts = row[5]
            if isinstance(counts, str):
                counts = json.loads(counts)
            objects.append({
                "id": row[0],
                "query": row[1],
                "mode": row[2],
                "version": row[3],
                "access_count": row[4],
                "section_counts": counts or {},
                "total_nodes": sum(counts.values()) if counts else 0,
                "created_at": row[6],
                "updated_at": row[7],
            })
        c.execute("SELECT COUNT(*) FROM memory_objects")
        total = c.fetchone()[0]
        conn.close()

        self.state["results"]["total_objects"] = total

        return (1, {"objects": objects, "total": total, "returned": len(objects)}, None)

    # ════════════════════════════════════════════
    # FORGET — delete a memory object
    # ════════════════════════════════════════════

    def _cmd_forget(self, params):
        query = self._p(params, "query")
        mode = self._p(params, "mode", self.state["config"]["default_mode"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        qkey = self._query_key(query, mode)
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM memory_objects WHERE query_key = %s", (qkey,))
        row = c.fetchone()
        if not row:
            conn.close()
            return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}'", 0))
        obj_id = row[0]
        c.execute("DELETE FROM memory_object_evolution WHERE memory_object_id = %s", (obj_id,))
        c.execute("DELETE FROM memory_objects WHERE id = %s", (obj_id,))
        conn.close()

        return (1, {"query": query, "status": "forgotten", "object_id": obj_id}, None)

    # ════════════════════════════════════════════
    # INTERNAL HELPERS
    # ════════════════════════════════════════════

    def _load_object(self, qkey):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, query_text, mode, radius, packet, provenance, graph_edges, "
            "section_counts, version, access_count, created_at, updated_at, "
            "last_accessed_at, decay_score, importance_weight "
            "FROM memory_objects WHERE query_key = %s",
            (qkey,)
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "query": row[1], "mode": row[2], "radius": row[3],
            "packet": row[4], "provenance": row[5], "graph_edges": row[6],
            "section_counts": row[7], "version": row[8], "access_count": row[9],
            "created_at": str(row[10]), "updated_at": str(row[11]),
            "last_accessed_at": str(row[12]) if row[12] else None,
            "decay_score": float(row[13]) if row[13] is not None else 1.0,
            "importance_weight": float(row[14]) if row[14] is not None else 0.5,
        }

    def _run_magnetic(self, query, mode, radius, limit):
        """Run magnetic search via msearch binary and return the packet."""
        import subprocess
        binary = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Cascade_toolStack", "Built_tools", "msearch"
        )
        if not os.path.exists(binary):
            binary = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "Cascade_toolStack", "bin_tools", "msearch"
            )
        if not os.path.exists(binary):
            return None

        cmd = [binary, query, "--magnetic", "--radius", str(radius), "--limit", str(limit), "--json"]
        if mode and mode != "magnetic":
            cmd.extend(["--mode", mode])

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode != 0:
                return None
            text = result.stdout.decode("utf-8", errors="replace").strip()
            # Binary outputs concatenated JSON: [{table...}]{[table...]}
            # Some string values contain unescaped chars, so we use regex to extract tables
            import re
            packet = {}
            # Match each table block: {"table":"name",...} with its rows
            # The pattern finds "table":"xxx" then captures until the next table or end
            table_starts = [(m.start(), m.group(1)) for m in re.finditer(r'"table":"([^"]+)"', text)]
            for i, (start, table_name) in enumerate(table_starts):
                # Find the end: next table start or end of text
                if i + 1 < len(table_starts):
                    end = table_starts[i + 1][0]
                else:
                    end = len(text)
                # Extract the block and try to parse rows
                block = text[start:end]
                # Strip trailing ]} and leading {
                block = block.strip()
                if block.endswith("]}"):
                    block = block[:-2]
                if block.endswith("}"):
                    block = block[:-1]
                # Now block should be {"table":"xxx",...,"rows":[...]
                # Add closing and try parse
                block = "{" + block if not block.startswith("{") else block
                block = block + "}" if not block.endswith("}") else block
                try:
                    obj = json.loads(block)
                    packet[table_name] = obj.get("rows", [])
                except Exception:
                    # Last resort: extract rows by regex
                    rows_match = re.search(r'"rows":\[(.*)\]', block, re.DOTALL)
                    if rows_match:
                        rows_text = "[" + rows_match.group(1) + "]"
                        try:
                            packet[table_name] = json.loads(rows_text)
                        except Exception:
                            packet[table_name] = []
                    else:
                        packet[table_name] = []
            if packet:
                return packet
            return None
        except Exception:
            return None

    def _build_provenance(self, packet):
        """Record where each section came from."""
        provenance = {}
        section_sources = {
            "authority": "class_understandings",
            "chat_context": "devin.devin_messages",
            "graph": "bcl_ir.bcl_edges",
            "code": "vb_shared.code_classes",
            "rules": "vb_shared.learned_rules",
            "methods": "vb_shared.code_index",
            "timeline": "vb_shared.execution_log",
            "related": "vb_shared.code_identifier_frequency",
            "errors": "vb_shared.error_knowledge",
        }
        for section, source in section_sources.items():
            if section in packet:
                items = packet[section]
                count = len(items) if isinstance(items, list) else (1 if items else 0)
                provenance[section] = {"source": source, "count": count}
        return provenance

    def _extract_graph_edges(self, packet):
        """Extract graph edges from the packet."""
        graph = packet.get("graph", {})
        if isinstance(graph, str):
            try:
                graph = json.loads(graph)
            except Exception:
                graph = {}
        edges = []
        callers = graph.get("callers", []) if isinstance(graph, dict) else []
        deps = graph.get("dependencies", []) if isinstance(graph, dict) else []
        for edge in callers:
            edges.append({
                "type": "CALL",
                "source": edge.get("source", ""),
                "target": edge.get("target", ""),
                "line": edge.get("line", 0),
            })
        for edge in deps:
            edges.append({
                "type": edge.get("type", "DEP"),
                "source": edge.get("source", ""),
                "target": edge.get("target", ""),
            })
        return {"total_edges": len(edges), "edges": edges}

    def _count_sections(self, packet):
        """Count items in each section."""
        counts = {}
        for key, val in packet.items():
            if val is None:
                counts[key] = 0
            elif isinstance(val, list):
                counts[key] = len(val)
            elif isinstance(val, dict):
                sub_count = sum(len(v) for v in val.values() if isinstance(v, list))
                counts[key] = sub_count
            else:
                counts[key] = 1
        return counts

    def _diff_packets(self, old_pkt, new_pkt):
        """Diff two magnetic search packets."""
        old_counts = self._count_sections(old_pkt)
        new_counts = self._count_sections(new_pkt)
        sections_changed = []
        deltas = []
        for section in set(list(old_counts.keys()) + list(new_counts.keys())):
            old_n = old_counts.get(section, 0)
            new_n = new_counts.get(section, 0)
            if old_n != new_n:
                sections_changed.append(section)
                deltas.append(f"{section}: {old_n}->{new_n}")
        has_changes = len(sections_changed) > 0
        delta_count = sum(abs(new_counts.get(s, 0) - old_counts.get(s, 0)) for s in sections_changed)
        summary = "; ".join(deltas) if deltas else "no changes"
        return {
            "has_changes": has_changes,
            "sections_changed": sections_changed,
            "delta_count": delta_count,
            "summary": summary,
            "old_counts": old_counts,
            "new_counts": new_counts,
        }

    # ════════════════════════════════════════════
    # DECAY — forgetting curves based on access patterns
    # ════════════════════════════════════════════

    DECAY_HALF_LIFE_DAYS = 30.0
    DECAY_MIN_THRESHOLD = 0.05
    ACCESS_BOOST = 0.03
    VERSION_BOOST = 0.05
    STALE_THRESHOLD = 0.30

    def _compute_decay(self, obj):
        """Compute decay score based on time since last access, access count, and version.

        Formula: e^(-days / half_life) + access_boost + version_boost

        - 0 days since access  → score ~1.0 (fresh)
        - 30 days (half-life)  → score ~0.37 + boosts
        - 90 days              → score ~0.05 + boosts (nearly forgotten)
        - Each access adds +0.03 (capped at 0.15)
        - Each version adds +0.05 (capped at 0.20)
        """
        from datetime import datetime, timedelta

        access_count = obj.get("access_count", 0)
        version = obj.get("version", 1)
        updated_str = obj.get("updated_at") or obj.get("created_at")

        days_since = 0.0
        if updated_str:
            try:
                updated = datetime.strptime(updated_str[:19], "%Y-%m-%d %H:%M:%S")
                days_since = max(0.0, (datetime.now() - updated).total_seconds() / 86400.0)
            except Exception:
                days_since = 0.0

        base_decay = 2.71828 ** (-days_since / self.DECAY_HALF_LIFE_DAYS)

        access_boost = min(0.15, access_count * self.ACCESS_BOOST)
        version_boost = min(0.20, (version - 1) * self.VERSION_BOOST)

        decay_score = min(1.0, base_decay + access_boost + version_boost)
        decay_score = max(0.0, decay_score)

        is_stale = decay_score < self.STALE_THRESHOLD
        should_forget = decay_score < self.DECAY_MIN_THRESHOLD

        if days_since < 1:
            freshness = "fresh"
        elif days_since < 7:
            freshness = "recent"
        elif days_since < 30:
            freshness = "aging"
        elif days_since < 90:
            freshness = "stale"
        else:
            freshness = "forgotten"

        return {
            "decay_score": round(decay_score, 4),
            "base_decay": round(base_decay, 4),
            "access_boost": round(access_boost, 4),
            "version_boost": round(version_boost, 4),
            "days_since_access": round(days_since, 1),
            "freshness": freshness,
            "is_stale": is_stale,
            "should_forget": should_forget,
            "access_count": access_count,
            "version": version,
        }

    def _cmd_decay(self, params):
        """Inspect decay state of a memory object or all objects."""
        query = self._p(params, "query")
        if query:
            mode = self._p(params, "mode", self.state["config"]["default_mode"])
            qkey = self._query_key(query, mode)
            obj = self._load_object(qkey)
            if not obj:
                return (0, None, ("ERR_NOT_FOUND", f"no memory object for '{query}'", 0))
            decay = self._compute_decay(obj)
            return (1, {
                "query": query,
                "object_id": obj["id"],
                "version": obj["version"],
                "access_count": obj["access_count"],
                "updated_at": obj["updated_at"],
                "decay": decay,
            }, None)

        all_decay = self._compute_all_decay()
        return (1, {
            "total": len(all_decay),
            "objects": all_decay,
        }, None)

    def _compute_all_decay(self):
        """Compute decay for all memory objects."""
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT id, query_text, mode, version, access_count, updated_at "
            "FROM memory_objects ORDER BY updated_at DESC"
        )
        results = []
        for row in c.fetchall():
            obj = {
                "id": row[0], "query": row[1], "mode": row[2],
                "version": row[3], "access_count": row[4],
                "updated_at": str(row[5]),
            }
            decay = self._compute_decay(obj)
            results.append({
                "id": obj["id"],
                "query": obj["query"],
                "version": obj["version"],
                "access_count": obj["access_count"],
                "decay_score": decay["decay_score"],
                "freshness": decay["freshness"],
                "is_stale": decay["is_stale"],
                "should_forget": decay["should_forget"],
            })
        conn.close()
        return results

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
