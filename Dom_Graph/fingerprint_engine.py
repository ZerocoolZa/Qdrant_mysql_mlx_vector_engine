#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/fingerprint_engine.py"
# date="2026-06-26" author="Devin" session_id="phase2-graph"
# context="Project Digital Twin Phase 2 Section 17 Fingerprint Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="fingerprint_engine.py" domain="twin_fingerprint" authority="FingerprintEngine"}
# [@SUMMARY]{summary="Fingerprint authority that hashes all project entities (files, classes, methods, BCL, dependencies, graph) and verifies integrity."}
# [@CLASS]{class="FingerprintEngine" domain="fingerprint" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="fingerprint_project" type="command"}
# [@METHOD]{method="fingerprint_file" type="command"}
# [@METHOD]{method="fingerprint_class" type="command"}
# [@METHOD]{method="fingerprint_method" type="command"}
# [@METHOD]{method="compare_fingerprints" type="command"}
# [@METHOD]{method="verify_integrity" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<FingerprintEngine: hashes project entities (files/classes/methods/BCL/dependencies/graph) and verifies integrity. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
FingerprintEngine -- authority for project fingerprinting and integrity.
Implements Section 17 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: fingerprint_project, fingerprint_file, fingerprint_class,
          fingerprint_method, compare_fingerprints, verify_integrity.
"""
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"


class FingerprintEngine:
    """Authority for hashing project entities and verifying integrity."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "fingerprint_project":
            return self.FingerprintProject(params)
        elif command == "fingerprint_file":
            return self.FingerprintFile(params)
        elif command == "fingerprint_class":
            return self.FingerprintClass(params)
        elif command == "fingerprint_method":
            return self.FingerprintMethod(params)
        elif command == "compare_fingerprints":
            return self.CompareFingerprints(params)
        elif command == "verify_integrity":
            return self.VerifyIntegrity(params)
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

    def HashText(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def FingerprintProject(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT hash FROM files ORDER BY file_id")
        file_hashes = [r[0] or "" for r in cur.fetchall()]
        cur.execute("SELECT hash FROM classes ORDER BY class_id")
        class_hashes = [r[0] or "" for r in cur.fetchall()]
        cur.execute("SELECT hash FROM methods ORDER BY method_id")
        method_hashes = [r[0] or "" for r in cur.fetchall()]
        cur.execute("SELECT bcl FROM files WHERE bcl IS NOT NULL AND bcl != ''")
        bcl_hashes = [self.HashText(r[0]) for r in cur.fetchall()]
        cur.execute("SELECT src_type, src_id, dst_type, dst_id, edge_type FROM edges ORDER BY edge_id")
        edge_data = "|".join(":".join(str(x) for x in row) for row in cur.fetchall())
        combined = "\n".join(file_hashes + class_hashes + method_hashes + bcl_hashes)
        combined += "\n" + edge_data
        project_hash = self.HashText(combined)
        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        class_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        method_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        edge_count = cur.fetchone()[0]
        record = {
            "project_hash": project_hash,
            "file_count": file_count,
            "class_count": class_count,
            "method_count": method_count,
            "edge_count": edge_count,
            "graph_hash": self.HashText(edge_data),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["catalog"].append(record)
        return (1, record, None)

    def FingerprintFile(self, params):
        file_id = self._p(params, "file_id")
        if file_id is None:
            return (0, None, ("MISSING_PARAM", "file_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_name, path, hash, bcl FROM files WHERE file_id=?",
                    (file_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "file_id not found", 0))
        fname, path, stored_hash, bcl = row
        bcl_hash = self.HashText(bcl) if bcl else ""
        record = {
            "file_id": file_id,
            "file_name": fname,
            "path": path,
            "hash": stored_hash,
            "bcl_hash": bcl_hash,
        }
        return (1, record, None)

    def FingerprintClass(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT class_name, hash, bcl, start_line, end_line, "
                    "method_count, parent FROM classes WHERE class_id=?",
                    (class_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "class_id not found", 0))
        cname, stored_hash, bcl, start_line, end_line, method_count, parent = row
        bcl_hash = self.HashText(bcl) if bcl else ""
        cur.execute("SELECT method_id, method_name, signature, parameters, "
                    "method_code, hash FROM methods WHERE class_id=? "
                    "ORDER BY method_id", (class_id,))
        method_rows = cur.fetchall()
        method_list = []
        signature_list = []
        code_parts = []
        method_hashes = []
        for mrow in method_rows:
            mid, mname, sig, pparams, mcode, mhash = mrow
            method_list.append(mname or "")
            signature_list.append(sig or "")
            code_parts.append(mcode or "")
            method_hashes.append(mhash or "")
        method_list_hash = self.HashText("|".join(method_list))
        signature_hash = self.HashText("|".join(signature_list))
        code_hash = self.HashText("\n".join(code_parts))
        methods_hash = self.HashText("|".join(method_hashes))
        record = {
            "class_id": class_id,
            "class_name": cname,
            "hash": stored_hash,
            "bcl_hash": bcl_hash,
            "method_count": method_count,
            "parent": parent,
            "start_line": start_line,
            "end_line": end_line,
            "method_list": method_list,
            "method_list_hash": method_list_hash,
            "signature_hash": signature_hash,
            "code_hash": code_hash,
            "methods_hash": methods_hash,
            "composite_hash": self.HashText(
                "|".join([stored_hash or "", bcl_hash, method_list_hash,
                          signature_hash, code_hash])),
        }
        return (1, record, None)

    def FingerprintMethod(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, hash, bcl, signature, parameters, "
                    "method_code, return_type, start_line, end_line, "
                    "line_count, is_vbstyle, returns_tuple3 FROM methods "
                    "WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "method_id not found", 0))
        (mname, stored_hash, bcl, signature, parameters, method_code,
         return_type, start_line, end_line, line_count,
         is_vbstyle, returns_tuple3) = row
        bcl_hash = self.HashText(bcl) if bcl else ""
        signature_hash = self.HashText(signature) if signature else ""
        parameters_hash = self.HashText(parameters) if parameters else ""
        code_hash = self.HashText(method_code) if method_code else ""
        composite = self.HashText("|".join([
            stored_hash or "", bcl_hash, signature_hash,
            parameters_hash, code_hash,
        ]))
        record = {
            "method_id": method_id,
            "method_name": mname,
            "hash": stored_hash,
            "bcl_hash": bcl_hash,
            "signature": signature,
            "signature_hash": signature_hash,
            "parameters": parameters,
            "parameters_hash": parameters_hash,
            "method_code_hash": code_hash,
            "return_type": return_type,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": line_count,
            "is_vbstyle": is_vbstyle,
            "returns_tuple3": returns_tuple3,
            "composite_hash": composite,
        }
        return (1, record, None)

    def CompareFingerprints(self, params):
        fp_a = self._p(params, "fingerprint_a")
        fp_b = self._p(params, "fingerprint_b")
        if fp_a is None or fp_b is None:
            return (0, None, ("MISSING_PARAM",
                              "fingerprint_a and fingerprint_b required", 0))
        changes = {}
        for key in ("project_hash", "graph_hash"):
            va = fp_a.get(key)
            vb = fp_b.get(key)
            if va != vb:
                changes[key] = {"before": va, "after": vb}
        for key in ("file_count", "class_count", "method_count", "edge_count"):
            va = fp_a.get(key, 0)
            vb = fp_b.get(key, 0)
            if va != vb:
                changes[key] = {"before": va, "after": vb, "delta": vb - va}
        record = {
            "identical": len(changes) == 0,
            "changes": changes,
            "change_count": len(changes),
        }
        return (1, record, None)

    def VerifyIntegrity(self, params):
        stored = self._p(params, "stored_fingerprint")
        if stored is None:
            return (0, None, ("MISSING_PARAM", "stored_fingerprint required", 0))
        current = self.FingerprintProject(params)
        if current[0] != 1:
            return current
        compare = self.CompareFingerprints({
            "fingerprint_a": stored,
            "fingerprint_b": current[1],
        })
        if compare[0] != 1:
            return compare
        record = {
            "intact": compare[1]["identical"],
            "changes": compare[1]["changes"],
            "current": current[1],
        }
        return (1, record, None)
