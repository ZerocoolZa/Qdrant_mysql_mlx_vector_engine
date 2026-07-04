#!/usr/bin/env python3
# [@GHOST]{[@file<BclReportPacket.py>][@domain<Dom_Bcl>][@role<packet>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<bcl-report>]}
# [@VBSTYLE]{[@auth<devin>][@role<packet>][@return<tuple3>][@orch<DiagnosticDB>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{BclReportPacket — generates a [@REPORT] BCL packet from a report ID in diagnostic_kb. The packet carries entity references (IDs), not data. The report engine resolves the IDs to reconstruct the story.}
# [@CLASS]{BclReportPacket}
# [@METHOD]{Run,Generate,Resolve,ReadPacket,read_state,set_config}
# [@FILEID]{core/Dom_Bcl/BclReportPacket.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mysql.connector
from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser


class BclReportPacket:
    """Generates and resolves BCL report packets.

    Generate: report_id → [@REPORT]{...} BCL text (references only)
    Resolve:  [@REPORT]{...} BCL text → story dict (data resolved from DB)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "diagnostic_kb",
                "db_socket": "/tmp/mysql.sock",
            },
            "conn": None,
            "packet": "",
            "story": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "generate":
            return self.Generate(params)
        elif command == "resolve":
            return self.Resolve(params)
        elif command == "read_packet":
            return self.ReadPacket(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def _connect(self):
        if self.state["conn"] is None or not self.state["conn"].is_connected():
            cfg = self.state["config"]
            self.state["conn"] = mysql.connector.connect(
                host=cfg["db_host"], user=cfg["db_user"], password=cfg["db_password"],
                database=cfg["db_name"], unix_socket=cfg.get("db_socket", "/tmp/mysql.sock")
            )
        return self.state["conn"]

    def _ids_to_tuples(self, ids):
        """Convert a list of IDs to BCL tuple lines."""
        lines = []
        for entity_id in ids:
            lines.append("        (\"id\";%d)" % entity_id)
        return lines

    def Generate(self, params):
        """Generate a [@REPORT] BCL packet from a report_id."""
        report_id = self._p(params, "report_id")
        if report_id is None:
            return (0, None, ("MISSING_PARAM", "report_id required", 0))

        conn = self._connect()
        cur = conn.cursor(dictionary=True)

        # ── Get report root ──
        cur.execute("SELECT * FROM report WHERE id=%s", (report_id,))
        report = cur.fetchone()
        if not report:
            cur.close()
            return (0, None, ("NOT_FOUND", "Report %d not found" % report_id, 0))

        # ── Get linked entity IDs from join tables ──
        join_queries = {
            "ERRORS": "SELECT error_id as id FROM report_error WHERE report_id=%s ORDER BY sort_order",
            "PROBLEMS": "SELECT problem_id as id FROM report_problem WHERE report_id=%s ORDER BY problem_id",
            "CAUSES": "SELECT cause_id as id FROM report_cause WHERE report_id=%s ORDER BY cause_id",
            "FIXES": "SELECT fix_id as id FROM report_fix WHERE report_id=%s ORDER BY sort_order",
            "PREVENTIONS": "SELECT prevention_id as id FROM report_prevention WHERE report_id=%s ORDER BY prevention_id",
            "FACTS": "SELECT fact_id as id FROM report_fact WHERE report_id=%s ORDER BY sort_order",
            "ANSWERS": "SELECT answer_id as id FROM report_answer WHERE report_id=%s ORDER BY answer_id",
            "EVIDENCE": "SELECT evidence_id as id FROM report_evidence WHERE report_id=%s ORDER BY evidence_id",
            "RULES": "SELECT rule_id as id FROM report_rule WHERE report_id=%s ORDER BY rule_id",
            "QUESTIONS": "SELECT question_id as id FROM report_question WHERE report_id=%s ORDER BY question_id",
        }

        entity_ids = {}
        for tag, query in join_queries.items():
            cur.execute(query, (report_id,))
            rows = cur.fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                entity_ids[tag] = ids

        cur.close()

        # ── Build BCL packet ──
        # Format: one container per entity type, one tuple with all IDs.
        # Variable-length tuple: (91;94;97) — no repeated "id" key.
        # The container name tells the resolver what entity to look up.
        lines = []
        lines.append("[@REPORT]")
        lines.append("{")
        lines.append("    (\"title\";\"%s\")" % (report["title"] or ""))
        if report["incident_id"]:
            lines.append("    (\"incident\";%d)" % report["incident_id"])
        if report["status_id"]:
            lines.append("    (\"status_id\";%d)" % report["status_id"])
        if report["severity_id"]:
            lines.append("    (\"severity_id\";%d)" % report["severity_id"])

        for tag, ids in entity_ids.items():
            id_str = ";".join(str(i) for i in ids)
            lines.append("")
            lines.append("    [@%s]" % tag)
            lines.append("    {")
            lines.append("        (%s)" % id_str)
            lines.append("    }")

        lines.append("}")

        packet = "\n".join(lines)
        self.state["packet"] = packet
        return (1, packet, None)

    def Resolve(self, params):
        """Resolve a [@REPORT] BCL packet into a story dict."""
        packet = self._p(params, "packet") or self.state["packet"]
        if not packet:
            return (0, None, ("MISSING_PARAM", "packet required (run generate first or pass packet)", 0))

        # ── Parse the BCL packet ──
        lexer = BCLTokenizer()
        lex_result = lexer.Run("tokenize", {"text": packet})
        if lex_result[0] == 0:
            return (0, None, lex_result[2])

        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": lex_result[1]["tokens"]})
        if parse_result[0] == 0:
            return (0, None, parse_result[2])

        root = parse_result[1]["root"]
        if not root.state["children"]:
            return (0, None, ("PARSE_ERROR", "No REPORT container found", 0))

        report_node = root.state["children"][0]

        # ── Extract references from the packet ──
        # Format: [@ERRORS]{(91;94;97)} — one tuple, variable-length, all IDs
        # The container name is the entity type. The tuple is the ID list.
        refs = {}
        incident_id = None
        title = ""

        for t in report_node.state["tuples"]:
            if t and t[0] == "title":
                title = t[1] if len(t) > 1 else ""
            elif t and t[0] == "incident":
                incident_id = t[1] if len(t) > 1 else None

        for child in report_node.state["children"]:
            tag = child.state["name"]
            ids = []
            for t in child.state["tuples"]:
                # Variable-length tuple: all values are IDs
                ids.extend(t)
            if ids:
                refs[tag] = ids

        # ── Resolve references against the database ──
        conn = self._connect()
        cur = conn.cursor(dictionary=True)

        story = {"title": title, "incident": None, "entities": {}}

        # Resolve incident
        if incident_id:
            cur.execute("""
                SELECT i.*, s.name as status_name, sev.name as severity_name, sev.level as sev_level,
                       d.name as domain_name
                FROM incident i
                LEFT JOIN status s ON i.status_id=s.id
                LEFT JOIN severity sev ON i.severity_id=sev.id
                LEFT JOIN domain d ON i.domain_id=d.id
                WHERE i.id=%s
            """, (incident_id,))
            story["incident"] = cur.fetchone()

        # Resolve each entity type
        entity_resolvers = {
            "ERRORS": ("error", "e", """
                SELECT e.*, d.name as domain, c.name as category, t.name as type,
                       s.name as status, sev.name as severity, sev.level as sev_level, p.name as priority
                FROM error e
                LEFT JOIN domain d ON e.domain_id=d.id
                LEFT JOIN category c ON e.category_id=c.id
                LEFT JOIN type t ON e.type_id=t.id
                LEFT JOIN status s ON e.status_id=s.id
                LEFT JOIN severity sev ON e.severity_id=sev.id
                LEFT JOIN priority p ON e.priority_id=p.id
                WHERE e.id IN (%s)
            """),
            "PROBLEMS": ("problem", "p", "SELECT * FROM problem WHERE id IN (%s)"),
            "CAUSES": ("cause", "c", "SELECT * FROM cause WHERE id IN (%s)"),
            "FIXES": ("fix", "f", "SELECT * FROM fix WHERE id IN (%s)"),
            "PREVENTIONS": ("prevention", "pr", "SELECT * FROM prevention WHERE id IN (%s)"),
            "FACTS": ("fact", "f", "SELECT * FROM fact WHERE id IN (%s)"),
            "ANSWERS": ("answer", "a", "SELECT * FROM answer WHERE id IN (%s)"),
            "EVIDENCE": ("evidence", "ev", "SELECT * FROM evidence WHERE id IN (%s)"),
            "RULES": ("rule", "r", "SELECT * FROM rule WHERE id IN (%s)"),
        }

        for tag, ids in refs.items():
            if tag not in entity_resolvers:
                continue
            entity_name, alias, query_template = entity_resolvers[tag]
            placeholders = ",".join(["%s"] * len(ids))
            query = query_template % placeholders
            cur.execute(query, ids)
            rows = cur.fetchall()
            story["entities"][entity_name] = rows

        cur.close()

        self.state["story"] = story
        return (1, story, None)

    def ReadPacket(self, params=None):
        """Return the last generated packet."""
        return (1, self.state["packet"], None)
