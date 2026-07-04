# [@GHOST]{[@file<Neo4jGraph.py>][@domain<Dom_Unified>][@role<neo4j_graph_backend>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<neo4j_graph_backend>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Neo4jGraph — native graph database backend for MagneticGraph. Loads MySQL graph data into Neo4j and provides Cypher-based multi-hop traversal. Replaces SQL JOINs with native graph traversal.}
# [@CLASS]{Neo4jGraph}
# [@METHOD]{Run,load_all,load_class_graph,load_bcl_edges,load_graph_nodes,load_graph_edges,load_know_edges,traverse,search,read_state,set_config}

"""
Neo4jGraph — Native graph backend for the magnetic search system.

MySQL stores graph data in tables (class_graph, bcl_edges, graph_edges, know_edges).
Neo4j stores graph data as nodes and edges — traversal is O(hops) not O(table scan).

This class:
  1. Loads MySQL graph data into Neo4j (one-time or incremental)
  2. Provides Cypher-based traversal replacing MagneticGraph's SQL hops
  3. Adds full-text search on node properties

Schema:
  Nodes:
    (:Class {name, description, source_file})
    (:Method {name, bcl_stamp, file_path, line_start})
    (:Token {name, type})
    (:Rule {pattern, fix, confidence})
    (:Chat {session, row_id, role, preview})

  Edges:
    (:Class)-[:RELATES_TO {type}]->(:Class)
    (:Method)-[:CALLS {line}]->(:Method)
    (:Method)-[:IMPORTS {resource}]->(:Resource)
    (:Method)-[:READS_STATE]->(:StateKey)
    (:Token)-[:CO_OCCURS {weight, context}]->(:Token)
    (:Class)-[:HAS_METHOD]->(:Method)
    (:Rule)-[:ORIGINATED_FROM]->(:Chat)

USAGE:
  from Dom_Unified import Neo4jGraph

  ng = Neo4jGraph()

  # One-time load from MySQL
  ng.Run("load_all")

  # Traverse — single Cypher query replaces 7 SQL hops
  ng.Run("traverse", {"query": "MemUnit", "max_hops": 3})

  # Search nodes by name
  ng.Run("search", {"query": "MemUnit", "limit": 10})
"""

import os
import sys
import json
import mysql.connector
from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class Neo4jGraph:
    """
    Neo4jGraph — native graph database backend.

    Domain: NEO4J_GRAPH
    Authority: load MySQL graph data into Neo4j, provide Cypher traversal.
    One class, one domain, one authority.
    """

    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_AUTH = None

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "neo4j_uri": self.NEO4J_URI,
                "neo4j_auth": self.NEO4J_AUTH,
                "mysql_host": "localhost",
                "mysql_user": "root",
                "mysql_pass": "",
                "mysql_port": 3306,
                "max_hops": 3,
                "limit": 10,
                "batch_size": 500,
            },
            "results": {
                "last_load": None,
                "total_nodes_loaded": 0,
                "total_edges_loaded": 0,
                "last_traversal": None,
            },
            "driver": None,
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

    def _mysql(self, database="vb_shared"):
        cfg = self.state["config"]
        return mysql.connector.connect(
            user=cfg["mysql_user"],
            password=cfg["mysql_pass"],
            host=cfg["mysql_host"],
            port=cfg["mysql_port"],
            database=database,
            autocommit=True,
        )

    def _neo4j(self):
        if self.state["driver"] is None:
            cfg = self.state["config"]
            self.state["driver"] = GraphDatabase.driver(
                cfg["neo4j_uri"], auth=cfg["neo4j_auth"]
            )
        return self.state["driver"]

    def Run(self, command, params=None):
        dispatch = {
            "load_all": self._cmd_load_all,
            "load_class_graph": self._cmd_load_class_graph,
            "load_bcl_edges": self._cmd_load_bcl_edges,
            "load_graph_nodes": self._cmd_load_graph_nodes,
            "load_graph_edges": self._cmd_load_graph_edges,
            "load_know_edges": self._cmd_load_know_edges,
            "traverse": self._cmd_traverse,
            "search": self._cmd_search,
            "stats": self._cmd_stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"unknown command: {command}", 0))
        return handler(params)

    # ════════════════════════════════════════════
    # SCHEMA
    # ════════════════════════════════════════════

    def _ensure_schema(self, session):
        constraints = [
            "CREATE CONSTRAINT class_name IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT method_name IF NOT EXISTS FOR (m:Method) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT token_name IF NOT EXISTS FOR (t:Token) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT rule_pattern IF NOT EXISTS FOR (r:Rule) REQUIRE r.pattern IS UNIQUE",
        ]
        for cypher in constraints:
            try:
                session.run(cypher)
            except Exception:
                pass

        indexes = [
            "CREATE INDEX chat_session IF NOT EXISTS FOR (c:Chat) ON (c.session)",
            "CREATE INDEX method_file IF NOT EXISTS FOR (m:Method) ON (m.file_path)",
        ]
        for cypher in indexes:
            try:
                session.run(cypher)
            except Exception:
                pass

    # ════════════════════════════════════════════
    # LOAD — MySQL → Neo4j
    # ════════════════════════════════════════════

    def _cmd_load_all(self, params=None):
        driver = self._neo4j()
        with driver.session() as session:
            self._ensure_schema(session)

        results = {}
        total_nodes = 0
        total_edges = 0

        for cmd_name in [
            "load_class_graph", "load_bcl_edges",
            "load_graph_nodes", "load_graph_edges", "load_know_edges"
        ]:
            ok, data, err = self.Run(cmd_name, params)
            if ok:
                results[cmd_name] = data
                total_nodes += data.get("nodes", 0)
                total_edges += data.get("edges", 0)
            else:
                results[cmd_name] = {"error": str(err)}

        self.state["results"]["last_load"] = "complete"
        self.state["results"]["total_nodes_loaded"] = total_nodes
        self.state["results"]["total_edges_loaded"] = total_edges

        return (1, {
            "status": "loaded",
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "details": results,
        }, None)

    def _cmd_load_class_graph(self, params=None):
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute("SELECT source_class, target_class, relationship FROM class_graph")
        rows = c.fetchall()
        conn.close()

        driver = self._neo4j()
        with driver.session() as session:
            for source, target, rel in rows:
                rel_safe = (rel or "RELATES_TO").replace(" ", "_").upper()
                session.run(
                    f"MERGE (s:Class {{name: $source}}) "
                    f"MERGE (t:Class {{name: $target}}) "
                    f"MERGE (s)-[:RELATES_TO {{type: $rel}}]->(t)",
                    source=source, target=target, rel=rel_safe
                )

        return (1, {"nodes": len(rows) * 2, "edges": len(rows), "source": "class_graph"}, None)

    def _cmd_load_bcl_edges(self, params=None):
        limit = self._p(params, "limit", 50000)
        conn = self._mysql("bcl_ir")
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT source_method_id, target, edge_type, line_number "
            "FROM bcl_edges WHERE edge_type = 'CALL' LIMIT %s", (limit,)
        )
        rows = c.fetchall()
        conn.close()

        driver = self._neo4j()
        batch = self.state["config"]["batch_size"]
        with driver.session() as session:
            for i in range(0, len(rows), batch):
                chunk = rows[i:i+batch]
                for source, target, edge_type, line in chunk:
                    if not source or not target:
                        continue
                    session.run(
                        "MERGE (s:Method {name: $source}) "
                        "MERGE (t:Method {name: $target}) "
                        "MERGE (s)-[:CALLS {line: $line}]->(t)",
                        source=str(source)[:200], target=str(target)[:200],
                        line=line or 0
                    )

        return (1, {"nodes": len(rows) * 2, "edges": len(rows), "source": "bcl_edges"}, None)

    def _cmd_load_graph_nodes(self, params=None):
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute("SELECT id, node_type, name FROM graph_nodes")
        rows = c.fetchall()
        conn.close()

        driver = self._neo4j()
        with driver.session() as session:
            for rid, node_type, name in rows:
                label = (node_type or "Token").capitalize()
                session.run(
                    f"MERGE (n:{label} {{name: $name}}) SET n.source_id = $rid",
                    name=name, rid=rid
                )

        return (1, {"nodes": len(rows), "edges": 0, "source": "graph_nodes"}, None)

    def _cmd_load_graph_edges(self, params=None):
        limit = self._p(params, "limit", 10000)
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute(
            "SELECT ge.from_node, ge.to_node, ge.edge_type, ge.weight, ge.context "
            "FROM graph_edges ge LIMIT %s", (limit,)
        )
        rows = c.fetchall()
        conn.close()

        node_map = {}
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute("SELECT id, node_type, name FROM graph_nodes")
        for row in c.fetchall():
            node_map[row[0]] = {"type": row[1], "name": row[2]}
        conn.close()

        driver = self._neo4j()
        with driver.session() as session:
            for from_id, to_id, edge_type, weight, context in rows:
                from_node = node_map.get(from_id, {})
                to_node = node_map.get(to_id, {})
                from_name = from_node.get("name", str(from_id))
                to_name = to_node.get("name", str(to_id))
                from_label = (from_node.get("type") or "Token").capitalize()
                to_label = (to_node.get("type") or "Token").capitalize()
                rel_type = (edge_type or "CO_OCCURS").replace(" ", "_").upper()
                session.run(
                    f"MERGE (s:{from_label} {{name: $from_name}}) "
                    f"MERGE (t:{to_label} {{name: $to_name}}) "
                    f"MERGE (s)-[:{rel_type} {{weight: $weight, context: $context}}]->(t)",
                    from_name=from_name, to_name=to_name,
                    weight=weight or 1, context=context or ""
                )

        return (1, {"nodes": 0, "edges": len(rows), "source": "graph_edges"}, None)

    def _cmd_load_know_edges(self, params=None):
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute("SELECT from_node_id, to_node_id, relation_type FROM know_edges LIMIT 5000")
        rows = c.fetchall()
        conn.close()

        node_map = {}
        conn = self._mysql("vb_shared")
        c = conn.cursor()
        c.execute("SELECT id, node_type, name FROM graph_nodes")
        for row in c.fetchall():
            node_map[row[0]] = {"type": row[1], "name": row[2]}
        conn.close()

        driver = self._neo4j()
        with driver.session() as session:
            for from_id, to_id, rel_type in rows:
                from_node = node_map.get(from_id, {})
                to_node = node_map.get(to_id, {})
                from_name = from_node.get("name", str(from_id))
                to_name = to_node.get("name", str(to_id))
                rel = (rel_type or "KNOWS").replace(" ", "_").upper()
                session.run(
                    "MERGE (s:Token {name: $from_name}) "
                    "MERGE (t:Token {name: $to_name}) "
                    f"MERGE (s)-[:{rel}]->(t)",
                    from_name=from_name, to_name=to_name
                )

        return (1, {"nodes": 0, "edges": len(rows), "source": "know_edges"}, None)

    # ════════════════════════════════════════════
    # TRAVERSE — Cypher-based multi-hop
    # ════════════════════════════════════════════

    def _cmd_traverse(self, params):
        query = self._p(params, "query")
        max_hops = self._p(params, "max_hops", self.state["config"]["max_hops"])
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        driver = self._neo4j()
        with driver.session() as session:
            cypher = (
                "MATCH (n) WHERE n.name CONTAINS $search_term "
                "CALL { WITH n MATCH path = (n)-[*1.." + str(max_hops) + "]-(connected) "
                "RETURN connected, length(path) as hop_dist "
                "ORDER BY hop_dist LIMIT $limit } "
                "RETURN DISTINCT connected, hop_dist, labels(connected) as labels, "
                "properties(connected) as props "
                "ORDER BY hop_dist"
            )
            result = session.run(cypher, search_term=query, limit=limit)
            nodes = []
            for record in result:
                props = dict(record["props"])
                props["hop_distance"] = record["hop_dist"]
                props["labels"] = record["labels"]
                nodes.append(props)

        self.state["results"]["last_traversal"] = query

        return (1, {
            "query": query,
            "max_hops": max_hops,
            "total_nodes": len(nodes),
            "nodes": nodes,
        }, None)

    # ════════════════════════════════════════════
    # SEARCH — find nodes by name
    # ════════════════════════════════════════════

    def _cmd_search(self, params):
        query = self._p(params, "query")
        limit = self._p(params, "limit", self.state["config"]["limit"])
        if not query:
            return (0, None, ("ERR_PARAMS", "query required", 0))

        driver = self._neo4j()
        with driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE n.name CONTAINS $search_term "
                "RETURN labels(n) as labels, properties(n) as props "
                "LIMIT $limit",
                search_term=query, limit=limit
            )
            nodes = []
            for record in result:
                props = dict(record["props"])
                props["labels"] = record["labels"]
                nodes.append(props)

        return (1, {"query": query, "total": len(nodes), "nodes": nodes}, None)

    # ════════════════════════════════════════════
    # STATS
    # ════════════════════════════════════════════

    def _cmd_stats(self, params=None):
        driver = self._neo4j()
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            total_nodes = result.single()["count"]

            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total_edges = result.single()["count"]

            result = session.run(
                "MATCH (n) RETURN DISTINCT labels(n) as labels, count(*) as count "
                "ORDER BY count DESC"
            )
            label_counts = [{"labels": r["labels"], "count": r["count"]} for r in result]

            result = session.run(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) as type, count(*) as count "
                "ORDER BY count DESC"
            )
            edge_counts = [{"type": r["type"], "count": r["count"]} for r in result]

        return (1, {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_labels": label_counts,
            "edge_types": edge_counts,
        }, None)

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
