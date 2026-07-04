#!/usr/bin/env python3
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/SessionMiner.py";"identity=SessionMiner";"purpose=Stage 3c: Mine devin_messages for bugs/gotchas/fixes about each method. Store as MINED tier stamps.";"date=2026-06-27";"version=1.0";"author=Devin";"chat_link=mysql://devin/devin_messages")}
#[@VBSTYLE]{("auth=Devin";"role=tool";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=code-graph-pipeline";"context=Code Graph Pipeline Stage 3c";"purpose=Mine past Devin sessions for findings about each method")}
#[@SUMMARY]{("Stage 3c of the code graph pipeline. Scans devin_messages (38K+ rows) for bug reports, gotchas, and fixes about each METHOD unit. Searches for patterns: 'Found a bug in X', 'X doesn't work because', 'The fix is X', 'X is wrong because', 'I discovered that X'. Stores findings as MINED tier stamps with tags [@KnownBugs], [@Gotchas], [@FixesApplied].")}
"""
import os
import re
import sqlite3
import subprocess
import sys
import hashlib
import argparse
from datetime import datetime, timezone


DB_PATH = "code_graph.db"

MINED_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mined_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    finding_text TEXT NOT NULL,
    session_id TEXT,
    message_role TEXT,
    created_at TEXT,
    confidence REAL DEFAULT 0.7,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES code_units(id)
);
CREATE INDEX IF NOT EXISTS idx_mined_unit ON mined_findings(unit_id);
CREATE INDEX IF NOT EXISTS idx_mined_type ON mined_findings(finding_type);
CREATE INDEX IF NOT EXISTS idx_mined_hash ON mined_findings(content_hash);
"""

PATTERNS = [
    ("KnownBugs", [
        r"(?:found|hit|encountered) (?:a |an )?bug",
        r"bug (?:in|with)",
        r"is wrong because",
        r"doesn'?t work because",
        r"fails when",
        r"error (?:in|with|from)",
        r"is broken",
        r"(?:raised|threw|triggered) (?:an? )?(?:error|exception)",
        r"returned (?:an? )?error",
        r"failed (?:to|in)",
        r"crash(?:ed)?",
        r"problem (?:with|in)",
        r"has (?:a |an )?(?:bug|issue|problem)",
        r"Traceback",
        r"SyntaxError",
        r"AttributeError",
        r"TypeError",
        r"ValueError",
        r"ImportError",
        r"ModuleNotFoundError",
    ]),
    ("Gotchas", [
        r"looks? fine but",
        r"gotcha",
        r"watch out for",
        r"will bite you",
        r"i discovered that",
        r"surprising",
        r"tricky",
        r"has a quirk",
        r"is tricky",
        r"is surprising",
        r"careful (?:with|about)",
        r"requires?\s+(?:care|caution|attention)",
        r"is (?:subtle|deceptive|misleading)",
        r"is not (?:obvious|intuitive)",
        r"note that",
        r"important (?:to|that)",
        r"be aware",
        r"keep in mind",
    ]),
    ("FixesApplied", [
        r"(?:the )?fix (?:is|was|for)",
        r"fixed\b",
        r"to fix",
        r"should be",
        r"needs to be",
        r"must be",
        r"has to be",
        r"changed\b",
        r"updated\b",
        r"replaced\b",
        r"removed\b",
        r"added\b",
        r"is now",
        r"was (?:changed|updated|fixed|replaced)",
        r"now (?:uses|returns|calls|takes)",
        r"the fix",
        r"fixed the",
        r"fixed this",
    ]),
]


class SessionMiner:
    """Stage 3c: Mine past Devin sessions for findings about each method."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": DB_PATH,
                "mysql_user": "root",
                "mysql_db": "devin",
                "batch_size": 500,
            },
            "findings_found": 0,
            "methods_matched": 0,
            "messages_scanned": 0,
            "conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "mine_all":
            return self.MineAll(params)
        elif command == "mine_method":
            return self.MineMethod(params)
        elif command == "query_findings":
            return self.QueryFindings(params)
        elif command == "stats":
            return self.Stats(params)
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

    def _connect_sqlite(self):
        if self.state["conn"] is None:
            db_path = self.state["config"]["db_path"]
            if not os.path.isfile(db_path):
                return (0, None, ("DB_NOT_FOUND", "Database not found: " + db_path, 0))
            self.state["conn"] = sqlite3.connect(db_path)
            self.state["conn"].row_factory = sqlite3.Row
        return self.state["conn"]

    def _init_schema(self):
        conn = self._connect_sqlite()
        if isinstance(conn, tuple):
            return conn
        conn.executescript(MINED_SCHEMA_SQL)
        conn.commit()
        return conn

    def _mysql_query(self, sql):
        user = self.state["config"]["mysql_user"]
        mdb = self.state["config"]["mysql_db"]
        cmd = ["mysql", "-u", user, mdb, "-e", sql]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return None
        return result.stdout

    def _get_method_names(self):
        """Get all unique method names from code_units."""
        conn = self._connect_sqlite()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT method_name FROM code_units "
            "WHERE unit_type='METHOD' AND method_name IS NOT NULL "
            "AND method_name != '' ORDER BY method_name"
        )
        names = [row[0] for row in cur.fetchall()]
        return names

    def _search_messages(self, method_name, limit=20):
        """Search devin_messages for mentions of this method with finding patterns."""
        safe_name = method_name.replace("'", "\\'")
        sql = (
            "SELECT session_id, role, content, created_at_dt "
            "FROM devin_messages "
            "WHERE content LIKE '%" + safe_name + "%' "
            "AND role IN ('user','assistant') "
            "AND LENGTH(content) < 50000 "
            "ORDER BY created_at DESC LIMIT " + str(limit)
        )
        output = self._mysql_query(sql)
        if not output:
            return []
        lines = output.strip().split("\n")
        if len(lines) < 2:
            return []
        results = []
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 4:
                results.append({
                    "session_id": parts[0],
                    "role": parts[1],
                    "content": parts[2],
                    "created_at": parts[3],
                })
        return results

    def _extract_findings(self, method_name, messages):
        """Extract findings from messages about this method.
        Strategy: find each occurrence of method_name in the content,
        then check if any keyword pattern appears within +/- 200 chars.
        """
        findings = []
        seen_snippets = set()
        method_lower = method_name.lower()
        for msg in messages:
            content = msg["content"] or ""
            if method_lower not in content.lower():
                continue
            for match in re.finditer(re.escape(method_name), content, re.IGNORECASE):
                window_start = max(0, match.start() - 200)
                window_end = min(len(content), match.end() + 200)
                window = content[window_start:window_end]
                window_lower = window.lower()
                for finding_type, patterns in PATTERNS:
                    for pattern in patterns:
                        compiled = re.compile(pattern, re.IGNORECASE)
                        if compiled.search(window):
                            snippet = window.replace("\n", " ").strip()
                            snippet_key = snippet[:100]
                            if snippet_key not in seen_snippets:
                                seen_snippets.add(snippet_key)
                                findings.append({
                                    "finding_type": finding_type,
                                    "finding_text": snippet[:400],
                                    "session_id": msg["session_id"],
                                    "message_role": msg["role"],
                                    "created_at": msg["created_at"],
                                })
                                break
                    else:
                        continue
                    break
        return findings

    def MineAll(self, params):
        conn = self._init_schema()
        if isinstance(conn, tuple):
            return conn
        method_names = self._get_method_names()
        if isinstance(method_names, tuple):
            return method_names
        cur = conn.cursor()
        total_findings = 0
        methods_with_findings = 0
        methods_scanned = 0
        batch_size = self._p(params, "batch_size", self.state["config"]["batch_size"])
        max_methods = self._p(params, "max_methods", 0)
        for method_name in method_names:
            if max_methods and methods_scanned >= max_methods:
                break
            methods_scanned += 1
            cur.execute(
                "SELECT id, content_hash FROM code_units "
                "WHERE unit_type='METHOD' AND method_name=?",
                (method_name,)
            )
            units = cur.fetchall()
            messages = self._search_messages(method_name, limit=10)
            if not messages:
                continue
            findings = self._extract_findings(method_name, messages)
            if not findings:
                continue
            methods_with_findings += 1
            for unit in units:
                unit_id = unit["id"]
                content_hash = unit["content_hash"] or ""
                for finding in findings:
                    try:
                        cur.execute(
                            "INSERT INTO mined_findings "
                            "(unit_id, content_hash, finding_type, finding_text, "
                            "session_id, message_role, created_at, confidence) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, 0.7)",
                            (unit_id, content_hash, finding["finding_type"],
                             finding["finding_text"], finding["session_id"],
                             finding["message_role"], finding["created_at"])
                        )
                        total_findings += 1
                    except sqlite3.Error:
                        pass
            if methods_scanned % 50 == 0:
                conn.commit()
                print("  scanned " + str(methods_scanned) + "/" + str(len(method_names)) +
                      " methods, " + str(total_findings) + " findings so far")
        conn.commit()
        self.state["findings_found"] = total_findings
        self.state["methods_matched"] = methods_with_findings
        self.state["messages_scanned"] = methods_scanned
        result = {
            "findings_found": total_findings,
            "methods_with_findings": methods_with_findings,
            "methods_scanned": methods_scanned,
            "total_methods": len(method_names),
        }
        return (1, result, None)

    def MineMethod(self, params):
        method_name = self._p(params, "method_name")
        if not method_name:
            return (0, None, ("MISSING_PARAM", "method_name is required", 0))
        conn = self._init_schema()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute(
            "SELECT id, content_hash FROM code_units "
            "WHERE unit_type='METHOD' AND method_name=?",
            (method_name,)
        )
        units = cur.fetchall()
        if not units:
            return (0, None, ("METHOD_NOT_FOUND", "No METHOD units with name=" + method_name, 0))
        messages = self._search_messages(method_name, limit=20)
        if not messages:
            return (1, {"findings": [], "count": 0, "messages_found": 0}, None)
        findings = self._extract_findings(method_name, messages)
        stored = 0
        for unit in units:
            unit_id = unit["id"]
            content_hash = unit["content_hash"] or ""
            for finding in findings:
                try:
                    cur.execute(
                        "INSERT INTO mined_findings "
                        "(unit_id, content_hash, finding_type, finding_text, "
                        "session_id, message_role, created_at, confidence) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, 0.7)",
                        (unit_id, content_hash, finding["finding_type"],
                         finding["finding_text"], finding["session_id"],
                         finding["message_role"], finding["created_at"])
                    )
                    stored += 1
                except sqlite3.Error:
                    pass
        conn.commit()
        result = {
            "method_name": method_name,
            "findings": findings,
            "count": len(findings),
            "stored": stored,
            "messages_found": len(messages),
        }
        return (1, result, None)

    def QueryFindings(self, params):
        class_name = self._p(params, "class_name")
        method_name = self._p(params, "method_name")
        finding_type = self._p(params, "finding_type")
        conn = self._connect_sqlite()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        sql = (
            "SELECT m.id, m.unit_id, m.finding_type, m.finding_text, "
            "m.session_id, m.message_role, m.created_at, m.confidence, "
            "u.class_name, u.method_name, u.file_path "
            "FROM mined_findings m JOIN code_units u ON m.unit_id=u.id "
            "WHERE 1=1"
        )
        args = []
        if class_name:
            sql += " AND u.class_name=?"
            args.append(class_name)
        if method_name:
            sql += " AND u.method_name=?"
            args.append(method_name)
        if finding_type:
            sql += " AND m.finding_type=?"
            args.append(finding_type)
        sql += " ORDER BY m.created_at DESC LIMIT 100"
        cur.execute(sql, args)
        rows = cur.fetchall()
        findings = []
        for row in rows:
            findings.append(dict(row))
        return (1, {"findings": findings, "count": len(findings)}, None)

    def Stats(self, params):
        conn = self._connect_sqlite()
        if isinstance(conn, tuple):
            return conn
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM mined_findings")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT finding_type, COUNT(*) as cnt FROM mined_findings "
            "GROUP BY finding_type ORDER BY cnt DESC"
        )
        type_dist = []
        for row in cur.fetchall():
            type_dist.append({"finding_type": row[0], "count": row[1]})
        cur.execute(
            "SELECT COUNT(DISTINCT unit_id) FROM mined_findings"
        )
        methods_covered = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM code_units WHERE unit_type='METHOD'")
        total_methods = cur.fetchone()[0]
        result = {
            "total_findings": total,
            "methods_with_findings": methods_covered,
            "total_methods": total_methods,
            "coverage_pct": round((methods_covered / total_methods * 100), 2) if total_methods else 0,
            "type_distribution": type_dist,
        }
        return (1, result, None)


def main():
    parser = argparse.ArgumentParser(description="SessionMiner — Stage 3c mine past sessions")
    parser.add_argument("--db", default=DB_PATH, help="Path to code_graph.db")
    parser.add_argument("--mine-all", action="store_true", help="Mine all method names")
    parser.add_argument("--mine-method", metavar="NAME", help="Mine a specific method")
    parser.add_argument("--stats", action="store_true", help="Show mining statistics")
    parser.add_argument("--query", nargs="*", metavar="KEY=VALUE",
                        help="Query findings (class_name=X method_name=Y finding_type=KnownBugs)")
    parser.add_argument("--max-methods", type=int, default=0, help="Limit methods to scan (0=all)")
    args = parser.parse_args()

    engine = SessionMiner(param={"db_path": args.db})

    if args.mine_all:
        result = engine.Run("mine_all", {"max_methods": args.max_methods})
        if result[0] == 1:
            data = result[1]
            print("MINING COMPLETE:")
            print("  Findings found:       " + str(data["findings_found"]))
            print("  Methods with findings:" + str(data["methods_with_findings"]))
            print("  Methods scanned:      " + str(data["methods_scanned"]))
            print("  Total methods:        " + str(data["total_methods"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.mine_method:
        result = engine.Run("mine_method", {"method_name": args.mine_method})
        if result[0] == 1:
            data = result[1]
            print("MINING: " + args.mine_method)
            print("  Messages found: " + str(data["messages_found"]))
            print("  Findings:       " + str(data["count"]))
            print("  Stored:         " + str(data["stored"]))
            for f in data["findings"][:10]:
                print("  [" + f["finding_type"] + "] " + f["finding_text"][:120])
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.stats:
        result = engine.Run("stats")
        if result[0] == 1:
            data = result[1]
            print("MINING STATISTICS:")
            print("  Total findings:       " + str(data["total_findings"]))
            print("  Methods with findings:" + str(data["methods_with_findings"]))
            print("  Total methods:        " + str(data["total_methods"]))
            print("  Coverage:             " + str(data["coverage_pct"]) + "%")
            print("\n  Type distribution:")
            for item in data["type_distribution"]:
                print("    " + item["finding_type"] + ": " + str(item["count"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    if args.query:
        params = {}
        for arg in args.query:
            if "=" in arg:
                key, value = arg.split("=", 1)
                params[key] = value
        result = engine.Run("query_findings", params)
        if result[0] == 1:
            data = result[1]
            print("FINDINGS: " + str(data["count"]))
            for item in data["findings"][:50]:
                print("  [" + str(item["finding_type"]) + "] " +
                      str(item["class_name"]) + "." + str(item["method_name"]))
                print("      " + str(item["finding_text"][:150]))
                print("      session: " + str(item["session_id"]) +
                      " role: " + str(item["message_role"]))
        else:
            print("ERROR: " + str(result[2]))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
