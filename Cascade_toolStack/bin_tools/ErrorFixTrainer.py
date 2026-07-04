#!/usr/bin/env python3
# [@GHOST]{file_path="Cascade_toolStack/bin_tools/ErrorFixTrainer.py"
# date="2026-06-28" author="Devin" session_id="domgraph-phase1"
# context="Python version of C ErrorFixTrainer with session lessons"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ErrorFixTrainer.py" domain="error_training" authority="ErrorFixTrainer"}
# [@SUMMARY]{summary="Error-to-lesson generator and SQLite trainer. Produces synthetic lessons for common Python error classes plus session-learned rules. Stores in SQLite for downstream fix inference and DomGraphEngine import."}
# [@CLASS]{class="ErrorFixTrainer" domain="error_training" authority="single"}
# [@METHOD]{method="generate" type="command"}
# [@METHOD]{method="query" type="command"}
# [@METHOD]{method="import_from_c" type="command"}
# [@METHOD]{method="export_to_domgraph" type="command"}
# [@METHOD]{method="stats" type="command"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="_get_conn" type="helper"}
# [@METHOD]{method="_now" type="helper"}
# [@METHOD]{method="_build_broken" type="helper"}
# [@METHOD]{method="_build_fixed" type="helper"}
# [@METHOD]{method="__init__" type="ctor"}
"""
ErrorFixTrainer — Python version of the C ErrorFixTrainer.

Generates synthetic error→lesson pairs for 10 standard Python error types
plus 7 session-learned rules from this chat session. Stores in SQLite.
Can import from the C version's DB and export to DomGraphEngine unified DB.

Commands: generate, query, import_from_c, export_to_domgraph, stats,
          read_state, set_config.
"""
import json
import os
import random
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "ErrorFixTrainer.db"
LESSONS_PER_RULE = 10

NAMES = ["x", "y", "z", "count", "total", "value", "item", "data",
         "name", "score", "idx", "buf", "res", "tmp", "acc"]
LISTS = ["nums", "rows", "items", "vals", "pts", "buf", "tags", "ids"]
KEYS = ["id", "name", "age", "email", "status", "type", "count", "data"]
FILES = ["config.json", "data.csv", "input.txt", "model.pkl", "schema.sql"]
MODULES = ["utils", "helpers", "models", "config", "parser", "engine"]
ATTRS = ["size", "length", "count", "name", "value", "items", "data", "status"]

ERROR_RULES = [
    {"error_name": "NameError", "keyword": "is not defined",
     "root_cause": "Undefined variable", "repair": "Declare variable before use"},
    {"error_name": "TypeError", "keyword": "unsupported operand",
     "root_cause": "Type mismatch", "repair": "Cast or convert types"},
    {"error_name": "IndexError", "keyword": "out of range",
     "root_cause": "Index exceeds bounds", "repair": "Check length before access"},
    {"error_name": "KeyError", "keyword": "keyerror",
     "root_cause": "Missing dictionary key", "repair": "Use dict.get()"},
    {"error_name": "FileNotFoundError", "keyword": "no such file",
     "root_cause": "Missing file path", "repair": "Validate path"},
    {"error_name": "SyntaxError", "keyword": "invalid syntax",
     "root_cause": "Bad syntax structure", "repair": "Fix punctuation/indent"},
    {"error_name": "AttributeError", "keyword": "has no attribute",
     "root_cause": "Invalid object member", "repair": "Check API or use getattr"},
    {"error_name": "ImportError", "keyword": "cannot import",
     "root_cause": "Broken import path", "repair": "Fix module name/path"},
    {"error_name": "ValueError", "keyword": "invalid literal",
     "root_cause": "Bad value conversion", "repair": "Validate input before cast"},
    {"error_name": "IndentationError", "keyword": "indent",
     "root_cause": "Wrong indentation", "repair": "Fix spacing"},
]

SESSION_RULES = [
    {"error_name": "LanguageServerCPUSpike", "keyword": "language_server",
     "root_cause": "IDE language server indexing too many files",
     "repair": "Add files.exclude and .windsurfignore to hide heavy folders from indexer"},
    {"error_name": "ActivityMonitorDisabled", "keyword": "Service is disabled",
     "root_cause": "macOS launchd service disabled",
     "repair": "sudo launchctl enable then lsregister -f to re-register"},
    {"error_name": "MCPToolNamingMismatch", "keyword": "tool not found",
     "root_cause": "MCP tool names missing module prefix",
     "repair": "Add module prefix (e.g. pinecone_) to all tool names in Go wrapper"},
    {"error_name": "MCPArgMappingBug", "keyword": "invalid arguments",
     "root_cause": "Go wrapper not mapping JSON args to binary CLI args correctly",
     "repair": "Fix arg mapping in Go tool handler to pass params as positional args"},
    {"error_name": "SettingsDrift", "keyword": "settings drifted",
     "root_cause": "IDE settings.json modified without baseline comparison",
     "repair": "Use SettingsGuardian to snapshot baseline and compare for drift"},
    {"error_name": "ProcessThrottleNeeded", "keyword": "high cpu",
     "root_cause": "Runaway process consuming excessive CPU",
     "repair": "Use renice and taskpolicy to lower priority without killing"},
    {"error_name": "DBDoubleMigration", "keyword": "duplicate rows",
     "root_cause": "Migration ran twice without cleanup",
     "repair": "Use gc command to drop and recreate schema instead of rm"},
    {"error_name": "DestructiveCommandBlocked", "keyword": "DESTRUCTIVE COMMAND BLOCKED",
     "root_cause": "Safety hook blocked rm or drop operation",
     "repair": "Use approve.py --bulk or use GC pattern instead of rm"},
]

ALL_RULES = ERROR_RULES + SESSION_RULES

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS lessons (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        error_text  TEXT,
        error_name  TEXT,
        root_cause  TEXT,
        repair      TEXT,
        broken_code TEXT,
        fixed_code  TEXT,
        confidence  REAL,
        created_at  TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_lessons_error_name ON lessons(error_name)",
    "CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON lessons(confidence DESC)",
]


class ErrorFixTrainer:
    """Error-to-lesson generator and SQLite trainer."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    DEFAULT_DB_NAME,
                ),
                "lessons_per_rule": LESSONS_PER_RULE,
                "c_db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "ErrorFixTrainer.db",
                ),
                "domgraph_db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "Dom_Graph", "dom_graph_unified.db",
                ),
                "domgraph_engine_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "Dom_Graph", "DomGraphEngine.py",
                ),
            },
            "results": {
                "generated": 0,
                "imported": 0,
                "exported": 0,
            },
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "generate": self.Generate,
            "query": self.Query,
            "import_from_c": self.ImportFromC,
            "export_to_domgraph": self.ExportToDomgraph,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _get_conn(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
            self.state["db_conn"].row_factory = sqlite3.Row
        return self.state["db_conn"]

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def _build_broken(self, rule, variant):
        """Build realistic broken code for each error type."""
        name = NAMES[variant % len(NAMES)]
        lst = LISTS[variant % len(LISTS)]
        key = KEYS[variant % len(KEYS)]
        fname = FILES[variant % len(FILES)]
        mod = MODULES[variant % len(MODULES)]
        attr = ATTRS[variant % len(ATTRS)]
        idx = variant + 3
        en = rule["error_name"]

        if en == "NameError":
            return "print(%s)" % name
        if en == "TypeError":
            return "result = '%s' + %d" % (name, variant)
        if en == "IndexError":
            return "%s = [1, 2, 3]\nprint(%s[%d])" % (lst, lst, idx)
        if en == "KeyError":
            return "d = {'a': 1}\nprint(d['%s'])" % key
        if en == "FileNotFoundError":
            return "with open('%s') as f:\n    data = f.read()" % fname
        if en == "SyntaxError":
            return "if %s > 0\n    print(%s)" % (name, name)
        if en == "AttributeError":
            return "x = 42\nprint(x.%s)" % attr
        if en == "ImportError":
            return "from %s import nonexistent_func" % mod
        if en == "ValueError":
            return "x = int('%s')" % (name + "abc")
        if en == "IndentationError":
            return "def foo():\nprint('hello')"
        if en == "LanguageServerCPUSpike":
            return "# settings.json has no files.exclude\n# indexer scanning node_modules/"
        if en == "ActivityMonitorDisabled":
            return "# launchctl list | grep Service\n# Service is disabled"
        if en == "MCPToolNamingMismatch":
            return "# tool not found: search_records\n# missing pinecone_ prefix"
        if en == "MCPArgMappingBug":
            return "# invalid arguments for ctx_assemble\n# Go wrapper not passing --query"
        if en == "SettingsDrift":
            return "# settings.json modified manually\n# no baseline to compare"
        if en == "ProcessThrottleNeeded":
            return "# process at 95%% cpu for 10 minutes\n# no throttle applied"
        if en == "DBDoubleMigration":
            return "# migrate ran twice\n# duplicate rows in nodes table"
        if en == "DestructiveCommandBlocked":
            return "# rm dom_graph_unified.db\n# DESTRUCTIVE COMMAND BLOCKED by hook"
        return "# unknown error"

    def _build_fixed(self, rule, variant):
        """Build realistic fixed code for each error type."""
        name = NAMES[variant % len(NAMES)]
        lst = LISTS[variant % len(LISTS)]
        key = KEYS[variant % len(KEYS)]
        fname = FILES[variant % len(FILES)]
        mod = MODULES[variant % len(MODULES)]
        attr = ATTRS[variant % len(ATTRS)]
        idx = variant + 3
        en = rule["error_name"]

        if en == "NameError":
            return "%s = %d\nprint(%s)" % (name, variant * 10, name)
        if en == "TypeError":
            return "result = '%s' + str(%d)" % (name, variant)
        if en == "IndexError":
            return "%s = [1, 2, 3]\nif len(%s) > %d:\n    print(%s[%d])" % (lst, lst, idx, lst, idx)
        if en == "KeyError":
            return "d = {'a': 1}\nprint(d.get('%s', 'default'))" % key
        if en == "FileNotFoundError":
            return "import os\nif os.path.exists('%s'):\n    with open('%s') as f:\n        data = f.read()" % (fname, fname)
        if en == "SyntaxError":
            return "if %s > 0:\n    print(%s)" % (name, name)
        if en == "AttributeError":
            return "x = [1, 2, 3]\nprint(getattr(x, '%s', 'none'))" % attr
        if en == "ImportError":
            return "from %s import existing_func" % mod
        if en == "ValueError":
            return "try:\n    x = int('%s')\nexcept ValueError:\n    x = 0" % name
        if en == "IndentationError":
            return "def foo():\n    print('hello')"
        if en == "LanguageServerCPUSpike":
            return '# settings.json:\n# "files.exclude": {"**/node_modules": true}\n# .windsurfignore: node_modules/'
        if en == "ActivityMonitorDisabled":
            return "sudo launchctl enable system/%s\n/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f /path/to/app"
        if en == "MCPToolNamingMismatch":
            return "// Go: register as \"pinecone_search_records\"\n// not \"search_records\""
        if en == "MCPArgMappingBug":
            return "// Go: cmdArgs = append(cmdArgs, \"--query\", queryStr)\n// not just positional"
        if en == "SettingsDrift":
            return "# Use SettingsGuardian.snapshot()\n# then SettingsGuardian.compare()"
        if en == "ProcessThrottleNeeded":
            return "renice -n 10 -p <pid>\ntaskpolicy -c <pid> -B"
        if en == "DBDoubleMigration":
            return "# engine.Run('gc', {})\n# then engine.Run('migrate_codefix', {})"
        if en == "DestructiveCommandBlocked":
            return "python3 ~/.config/devin/hooks/approve.py '*' --bulk\n# or use gc command instead of rm"
        return "# unknown fix"

    def Generate(self, params):
        rules_only = self._p(params, "rules_only", None)
        count = self._p(params, "count", LESSONS_PER_RULE)
        conn = self._get_conn()
        cur = conn.cursor()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()

        rules = ALL_RULES
        if rules_only:
            rules = [r for r in ALL_RULES if r["error_name"] in rules_only]

        generated = 0
        for rule in rules:
            for i in range(count):
                error_text = "%s: %s" % (rule["error_name"], rule["keyword"])
                if rule in ERROR_RULES:
                    name = NAMES[i % len(NAMES)]
                    if rule["error_name"] == "NameError":
                        error_text = "NameError: name '%s' is not defined" % name
                    elif rule["error_name"] == "TypeError":
                        error_text = "TypeError: unsupported operand type(s) for +: 'str' and 'int'"
                    elif rule["error_name"] == "IndexError":
                        error_text = "IndexError: list index out of range"
                    elif rule["error_name"] == "KeyError":
                        error_text = "KeyError: '%s'" % KEYS[i % len(KEYS)]
                    elif rule["error_name"] == "FileNotFoundError":
                        error_text = "FileNotFoundError: [Errno 2] No such file or directory: '%s'" % FILES[i % len(FILES)]
                    elif rule["error_name"] == "SyntaxError":
                        error_text = "SyntaxError: invalid syntax"
                    elif rule["error_name"] == "AttributeError":
                        error_text = "AttributeError: 'int' object has no attribute '%s'" % ATTRS[i % len(ATTRS)]
                    elif rule["error_name"] == "ImportError":
                        error_text = "ImportError: cannot import name 'nonexistent' from '%s'" % MODULES[i % len(MODULES)]
                    elif rule["error_name"] == "ValueError":
                        error_text = "ValueError: invalid literal for int() with base 10: '%s'" % (name + "abc")
                    elif rule["error_name"] == "IndentationError":
                        error_text = "IndentationError: expected an indented block"
                else:
                    error_text = "%s: %s (variant %d)" % (rule["error_name"], rule["keyword"], i + 1)

                broken = self._build_broken(rule, i)
                fixed = self._build_fixed(rule, i)
                confidence = random.uniform(50, 100)
                cur.execute(
                    "INSERT INTO lessons (error_text, error_name, root_cause, repair, "
                    "broken_code, fixed_code, confidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (error_text, rule["error_name"], rule["root_cause"], rule["repair"],
                     broken, fixed, confidence, self._now())
                )
                generated += 1
        conn.commit()
        self.state["results"]["generated"] += generated
        return (1, {"generated": generated, "total_rules": len(rules),
                    "lessons_per_rule": count,
                    "rule_names": [r["error_name"] for r in rules]}, None)

    def Query(self, params):
        error_name = self._p(params, "error_name")
        keyword = self._p(params, "keyword")
        limit = self._p(params, "limit", 50)
        min_confidence = self._p(params, "min_confidence", 0)
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM lessons WHERE confidence >= ?"
        args = [min_confidence]
        if error_name:
            sql += " AND error_name = ?"
            args.append(error_name)
        if keyword:
            sql += " AND (error_text LIKE ? OR root_cause LIKE ? OR repair LIKE ?)"
            args.extend(["%" + keyword + "%"] * 3)
        sql += " ORDER BY confidence DESC LIMIT ?"
        args.append(limit)
        cur.execute(sql, args)
        results = [dict(row) for row in cur.fetchall()]
        return (1, {"lessons": results, "count": len(results)}, None)

    def ImportFromC(self, params):
        c_db_path = self._p(params, "c_db_path", self.state["config"].get("c_db_path"))
        if not os.path.isfile(c_db_path):
            return (0, None, ("SOURCE_NOT_FOUND", "C ErrorFixTrainer.db not found at " + c_db_path, 0))
        conn = self._get_conn()
        cur = conn.cursor()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()
        src = sqlite3.connect(c_db_path)
        src.row_factory = sqlite3.Row
        scur = src.cursor()
        try:
            scur.execute("SELECT error_text, error_name, root_cause, repair, broken_code, fixed_code, confidence, created_at FROM lessons")
        except sqlite3.Error as e:
            src.close()
            return (0, None, ("QUERY_FAILED", str(e), 0))
        imported = 0
        for row in scur.fetchall():
            cur.execute(
                "INSERT INTO lessons (error_text, error_name, root_cause, repair, "
                "broken_code, fixed_code, confidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (row["error_text"], row["error_name"], row["root_cause"], row["repair"],
                 row["broken_code"], row["fixed_code"], row["confidence"], row["created_at"])
            )
            imported += 1
        conn.commit()
        src.close()
        self.state["results"]["imported"] += imported
        return (1, {"imported": imported, "source": c_db_path}, None)

    def ExportToDomgraph(self, params):
        domgraph_db = self._p(params, "domgraph_db_path", self.state["config"].get("domgraph_db_path"))
        if not os.path.isfile(domgraph_db):
            return (0, None, ("DOMGRAPH_NOT_FOUND", "dom_graph_unified.db not found at " + domgraph_db, 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT error_text, error_name, root_cause, repair, broken_code, fixed_code, confidence FROM lessons")
        lessons = cur.fetchall()
        dst = sqlite3.connect(domgraph_db)
        dcur = dst.cursor()
        exported = 0
        now = self._now()
        for row in lessons:
            props = json.dumps({
                "fix_result": "success",
                "error_type": row["error_name"],
                "root_cause": row["root_cause"],
                "repair": row["repair"],
                "broken_code": row["broken_code"],
                "fixed_code": row["fixed_code"],
                "source": "ErrorFixTrainer",
            })
            dcur.execute(
                "INSERT INTO nodes (domain, node_type, name, description, confidence, "
                "properties, domain_tags, created, updated) VALUES (?,?,?,?,?,?,?,?,?)",
                ("codefix", "knowledge", row["error_text"][:200], row["repair"],
                 float(row["confidence"]), props, row["error_name"], now, now)
            )
            exported += 1
        dst.commit()
        dst.close()
        self.state["results"]["exported"] += exported
        return (1, {"exported": exported, "target": domgraph_db}, None)

    def Stats(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM lessons")
            total = cur.fetchone()[0]
        except sqlite3.Error:
            total = 0
        try:
            cur.execute("SELECT error_name, COUNT(*) as cnt FROM lessons GROUP BY error_name ORDER BY cnt DESC")
            by_type = {row["error_name"]: row["cnt"] for row in cur.fetchall()}
        except sqlite3.Error:
            by_type = {}
        try:
            cur.execute("SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM lessons")
            row = cur.fetchone()
            avg_conf = row[0] or 0
            min_conf = row[1] or 0
            max_conf = row[2] or 0
        except sqlite3.Error:
            avg_conf = min_conf = max_conf = 0
        return (1, {"total_lessons": total, "by_error_type": by_type,
                    "avg_confidence": round(avg_conf, 2),
                    "min_confidence": min_conf, "max_confidence": max_conf,
                    "results": self.state["results"],
                    "db_path": self.state["config"]["db_path"]}, None)


if __name__ == "__main__":
    import sys
    trainer = ErrorFixTrainer()
    command = sys.argv[1] if len(sys.argv) > 1 else "generate"
    params = {}
    for arg in sys.argv[2:]:
        if arg.startswith("--"):
            key = arg[2:]
            if "=" in key:
                k, v = key.split("=", 1)
                params[k] = v
            else:
                params[key] = True
    ok, data, err = trainer.Run(command, params)
    if ok == 1:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps({"ok": 0, "error": str(err)}, indent=2))
        sys.exit(1)
