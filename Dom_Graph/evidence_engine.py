#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/evidence_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 57 Digital Evidence Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="evidence_engine.py" domain="twin_evidence" authority="EvidenceEngine"}
# [@SUMMARY]{summary="Digital evidence authority that verifies evidence chains, gets audit trails, links evidence, and finds unlinked entities."}
# [@CLASS]{class="EvidenceEngine" domain="evidence" authority="single"}
# [@METHOD]{method="verify_evidence_chain" type="command"}
# [@METHOD]{method="get_audit_trail" type="command"}
# [@METHOD]{method="link_evidence" type="command"}
# [@METHOD]{method="find_unlinked" type="command"}
# [@METHOD]{method="get_evidence_for_error" type="command"}
# [@METHOD]{method="get_evidence_for_fix" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<EvidenceEngine: verifies evidence chains, gets audit trails, links evidence, finds unlinked entities. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
EvidenceEngine -- Digital evidence chain authority.
Implements Section 57 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: verify_evidence_chain, get_audit_trail, link_evidence, find_unlinked,
          get_evidence_for_error, get_evidence_for_fix.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class EvidenceEngine:
    """Digital evidence chain authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "verify_evidence_chain":
            return self.VerifyEvidenceChain(params)
        elif command == "get_audit_trail":
            return self.GetAuditTrail(params)
        elif command == "link_evidence":
            return self.LinkEvidence(params)
        elif command == "find_unlinked":
            return self.FindUnlinked(params)
        elif command == "get_evidence_for_error":
            return self.GetEvidenceForError(params)
        elif command == "get_evidence_for_fix":
            return self.GetEvidenceForFix(params)

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

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def VerifyEvidenceChain(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if not knowledge_id:
            return (0, None, ("NO_PARAM", "knowledge_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, evidence, file_id, class_id, "
                    "method_id, error_type FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
        krow = cur.fetchone()
        if not krow:
            return (0, None, ("NOT_FOUND", "knowledge entry not found", 0))
        chain = {"knowledge_id": krow[0], "problem": krow[1], "answer": krow[2],
                 "has_evidence": bool(krow[3]), "file_id": krow[4],
                 "class_id": krow[5], "method_id": krow[6], "error_type": krow[7]}
        links = {"evidence_present": bool(krow[3])}
        method_id = krow[6]
        class_id = krow[5]
        file_id = krow[4]
        if method_id:
            cur.execute("SELECT method_id, method_name, class_id, file_id, bcl, method_code "
                        "FROM methods WHERE method_id=?", (method_id,))
            mrow = cur.fetchone()
            links["method_exists"] = mrow is not None
            if mrow:
                links["method_has_bcl"] = bool(mrow[4])
                links["method_has_code"] = bool(mrow[5])
                if class_id is None:
                    class_id = mrow[2]
                if file_id is None:
                    file_id = mrow[3]
        else:
            links["method_exists"] = False
        if class_id:
            cur.execute("SELECT class_id, class_name, file_id FROM classes WHERE class_id=?",
                        (class_id,))
            crow = cur.fetchone()
            links["class_exists"] = crow is not None
            if crow and file_id is None:
                file_id = crow[2]
        else:
            links["class_exists"] = False
        if file_id:
            cur.execute("SELECT file_id, file_name, path FROM files WHERE file_id=?", (file_id,))
            frow = cur.fetchone()
            links["file_exists"] = frow is not None
        else:
            links["file_exists"] = False
        cur.execute("SELECT COUNT(*) FROM attempts WHERE knowledge_id=?", (knowledge_id,))
        links["fix_linked_to_error"] = cur.fetchone()[0] > 0
        if method_id:
            cur.execute("SELECT COUNT(*) FROM edges WHERE (src_type='method' AND src_id=?) "
                        "OR (dst_type='method' AND dst_id=?)", (method_id, method_id))
            links["source_linked_to_graph"] = cur.fetchone()[0] > 0
            cur.execute("SELECT COUNT(*) FROM edges WHERE ((src_type='method' AND src_id=?) "
                        "OR (dst_type='method' AND dst_id=?)) AND evidence IS NOT NULL "
                        "AND evidence != '' AND (evidence LIKE '%BCL%' OR evidence LIKE '%@BCL%')",
                        (method_id, method_id))
            links["graph_linked_to_bcl"] = cur.fetchone()[0] > 0
        else:
            links["source_linked_to_graph"] = False
            links["graph_linked_to_bcl"] = False
        cur.execute("SELECT COUNT(*) FROM attempts WHERE method_id=? "
                    "AND (before_code IS NOT NULL OR after_code IS NOT NULL)", (method_id,))
        links["code_change_linked_to_snapshot"] = cur.fetchone()[0] > 0
        verified = all(links.values())
        chain["links"] = links
        chain["verified"] = verified
        return (1, chain, None)

    def GetAuditTrail(self, params):
        method_id = self._p(params, "method_id")
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT k.knowledge_id, k.problem, k.answer, k.error_type, k.fix_result, "
                        "k.created AS knowledge_created, "
                        "a.attempt_id, a.action, a.compile_result, a.test_result, "
                        "a.rollback, a.created AS attempt_created, "
                        "o.observation_id, o.observation_type, o.subject, o.created AS observation_created, "
                        "s.snapshot_id, s.snapshot_type, s.created AS snapshot_created, s.notes "
                        "FROM knowledge k LEFT JOIN attempts a ON k.knowledge_id=a.knowledge_id "
                        "LEFT JOIN observations o ON k.method_id=o.method_id "
                        "LEFT JOIN snapshots s ON a.method_id=s.method_id "
                        "WHERE k.method_id=? ORDER BY k.created, a.created, o.created, s.created LIMIT ?",
                        (method_id, limit))
        else:
            cur.execute("SELECT k.knowledge_id, k.problem, k.answer, k.error_type, k.fix_result, "
                        "k.created AS knowledge_created, "
                        "a.attempt_id, a.action, a.compile_result, a.test_result, "
                        "a.rollback, a.created AS attempt_created, "
                        "o.observation_id, o.observation_type, o.subject, o.created AS observation_created, "
                        "s.snapshot_id, s.snapshot_type, s.created AS snapshot_created, s.notes "
                        "FROM knowledge k LEFT JOIN attempts a ON k.knowledge_id=a.knowledge_id "
                        "LEFT JOIN observations o ON k.method_id=o.method_id "
                        "LEFT JOIN snapshots s ON a.method_id=s.method_id "
                        "ORDER BY k.created, a.created, o.created, s.created LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"audit_trail": results, "count": len(results)}, None)

    def LinkEvidence(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        evidence_text = self._p(params, "evidence", "")
        if not knowledge_id:
            return (0, None, ("NO_PARAM", "knowledge_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE knowledge SET evidence=? WHERE knowledge_id=?",
                    (evidence_text, knowledge_id))
        conn.commit()
        return (1, {"linked": True, "knowledge_id": knowledge_id}, None)

    def FindUnlinked(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem FROM knowledge "
                    "WHERE evidence IS NULL OR evidence = ''")
        no_evidence = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT attempt_id, method_id FROM attempts WHERE knowledge_id IS NULL")
        unlinked_attempts = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT knowledge_id, problem FROM knowledge "
                    "WHERE file_id IS NULL AND class_id IS NULL AND method_id IS NULL")
        no_source = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
                    "(SELECT DISTINCT src_id FROM edges WHERE src_type='method') "
                    "AND method_id NOT IN (SELECT DISTINCT dst_id FROM edges WHERE dst_type='method')")
        no_edges = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT method_id, method_name FROM methods "
                    "WHERE bcl IS NULL OR bcl = ''")
        no_bcl = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.execute("SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE evidence IS NULL OR evidence = '' "
                    "OR (evidence NOT LIKE '%BCL%' AND evidence NOT LIKE '%@BCL%')")
        no_bcl_edges = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"no_evidence": no_evidence, "unlinked_attempts": unlinked_attempts,
                    "no_source": no_source, "no_edges": no_edges,
                    "no_bcl": no_bcl, "no_bcl_edges": no_bcl_edges}, None)

    def GetEvidenceForError(self, params):
        error_type = self._p(params, "error_type")
        if not error_type:
            return (0, None, ("NO_PARAM", "error_type required", 0))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT k.knowledge_id, k.problem, k.answer, k.evidence, k.confidence, "
                    "k.fix_result, k.error_type, k.error_text, "
                    "m.method_name, c.class_name, f.file_name "
                    "FROM knowledge k LEFT JOIN methods m ON k.method_id=m.method_id "
                    "LEFT JOIN classes c ON k.class_id=c.class_id "
                    "LEFT JOIN files f ON k.file_id=f.file_id "
                    "WHERE k.error_type=? ORDER BY k.confidence DESC LIMIT ?",
                    (error_type, limit))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"evidence_for_error": results, "error_type": error_type,
                    "count": len(results)}, None)

    def GetEvidenceForFix(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT k.knowledge_id, k.problem, k.answer, k.evidence, k.confidence, "
                    "k.fix_applied, k.fix_result, k.resolution_time_ms, "
                    "a.attempt_id, a.action, a.compile_result, a.test_result, "
                    "a.before_code, a.after_code, a.rollback "
                    "FROM knowledge k LEFT JOIN attempts a ON k.knowledge_id=a.knowledge_id "
                    "WHERE k.knowledge_id=? ORDER BY a.created", (fix_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"evidence_for_fix": results, "fix_id": fix_id,
                    "count": len(results)}, None)

