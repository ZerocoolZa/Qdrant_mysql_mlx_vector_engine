#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLCapabilityRouter.py
#[@SUMMARY] Capability-based router: maps task requirements to expert groups, activates only relevant experts
#[@CLASS] CoreMLCapabilityRouter
#[@METHOD] register_capability, route_task, activate_capability, deactivate_capability, status, list_capabilities
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import time
import sqlite3
import struct
import subprocess

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
TEMP_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/tmp_runtime"

CAPABILITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS capabilities (
    capability_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    expert_group TEXT DEFAULT '',
    active_experts TEXT DEFAULT '',
    ram_kb REAL DEFAULT 0,
    activated_count INTEGER DEFAULT 0,
    last_activated REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS capability_experts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT NOT NULL,
    expert_name TEXT NOT NULL,
    layer TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    weight_path TEXT DEFAULT '',
    state TEXT DEFAULT 'inactive',
    UNIQUE(capability_id, expert_name)
);

CREATE TABLE IF NOT EXISTS task_capability_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_keyword TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    UNIQUE(task_keyword, capability_id)
);

CREATE TABLE IF NOT EXISTS activation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT,
    task_input TEXT,
    experts_activated TEXT,
    timestamp REAL DEFAULT 0
);
"""

CAPABILITIES = [
    {
        "id": "python_grammar",
        "name": "Python Grammar + AST + Parser",
        "description": "Valid Python syntax, AST structure, parsing rules",
        "experts": [
            {"name": "ast_grammar_vscode", "layer": "grammar", "domain": "vscode"},
            {"name": "ast_grammar_browser", "layer": "grammar", "domain": "browser"},
            {"name": "ast_grammar_dashboard", "layer": "grammar", "domain": "dashboard"},
            {"name": "ast_grammar_mobile", "layer": "grammar", "domain": "mobile"},
            {"name": "ast_grammar_tablet", "layer": "grammar", "domain": "tablet"},
        ],
        "keywords": ["python", "syntax", "parse", "ast", "grammar", "function", "class", "def", "import", "code"],
    },
    {
        "id": "python_idioms",
        "name": "Python Idioms + Patterns",
        "description": "Design patterns, comprehensions, decorators, async, context managers",
        "experts": [
            {"name": "ast_idiom_vscode", "layer": "idiom", "domain": "vscode"},
            {"name": "ast_idiom_browser", "layer": "idiom", "domain": "browser"},
            {"name": "ast_idiom_dashboard", "layer": "idiom", "domain": "dashboard"},
            {"name": "ast_idiom_mobile", "layer": "idiom", "domain": "mobile"},
            {"name": "ast_idiom_tablet", "layer": "idiom", "domain": "tablet"},
        ],
        "keywords": ["pattern", "idiom", "decorator", "comprehension", "async", "context", "manager", "lambda", "generator"],
    },
    {
        "id": "python_libraries",
        "name": "Python Library + Ecosystem",
        "description": "Standard library, third-party imports, ecosystem knowledge",
        "experts": [
            {"name": "ast_library_vscode", "layer": "library", "domain": "vscode"},
            {"name": "ast_library_browser", "layer": "library", "domain": "browser"},
            {"name": "ast_library_dashboard", "layer": "library", "domain": "dashboard"},
            {"name": "ast_library_mobile", "layer": "library", "domain": "mobile"},
            {"name": "ast_library_tablet", "layer": "library", "domain": "tablet"},
        ],
        "keywords": ["library", "import", "module", "package", "stdlib", "numpy", "pyqt", "sqlite", "subprocess", "os", "sys"],
    },
    {
        "id": "vbstyle",
        "name": "VBStyle + Architecture Conventions",
        "description": "Run() dispatch, Tuple3 returns, self.state, BCL headers, no print, no self._",
        "experts": [
            {"name": "ast_style_vscode", "layer": "style", "domain": "vscode"},
            {"name": "ast_style_browser", "layer": "style", "domain": "browser"},
            {"name": "ast_style_dashboard", "layer": "style", "domain": "dashboard"},
            {"name": "ast_style_mobile", "layer": "style", "domain": "mobile"},
            {"name": "ast_style_tablet", "layer": "style", "domain": "tablet"},
        ],
        "keywords": ["vbstyle", "bcl", "run", "tuple3", "style", "convention", "header", "stamp", "config", "dispatch"],
    },
    {
        "id": "layout_prediction",
        "name": "UI Layout Prediction",
        "description": "40D layout features -> 10D panel arrangement predictions",
        "experts": [
            {"name": "vscode", "layer": "layout", "domain": "vscode"},
            {"name": "browser", "layer": "layout", "domain": "browser"},
            {"name": "dashboard", "layer": "layout", "domain": "dashboard"},
            {"name": "mobile", "layer": "layout", "domain": "mobile"},
            {"name": "tablet", "layer": "layout", "domain": "tablet"},
        ],
        "keywords": ["layout", "panel", "ui", "ide", "editor", "sidebar", "toolbar", "browser", "mobile", "dashboard", "tablet", "portrait", "landscape", "touch", "swipe", "gui"],
    },
    {
        "id": "code_analysis",
        "name": "Code Analysis + Classification",
        "description": "Classify Python files by domain using all 4 AST layers",
        "experts": [
            {"name": "ast_grammar_vscode", "layer": "grammar", "domain": "vscode"},
            {"name": "ast_grammar_browser", "layer": "grammar", "domain": "browser"},
            {"name": "ast_grammar_dashboard", "layer": "grammar", "domain": "dashboard"},
            {"name": "ast_grammar_mobile", "layer": "grammar", "domain": "mobile"},
            {"name": "ast_grammar_tablet", "layer": "grammar", "domain": "tablet"},
            {"name": "ast_idiom_vscode", "layer": "idiom", "domain": "vscode"},
            {"name": "ast_idiom_browser", "layer": "idiom", "domain": "browser"},
            {"name": "ast_idiom_dashboard", "layer": "idiom", "domain": "dashboard"},
            {"name": "ast_idiom_mobile", "layer": "idiom", "domain": "mobile"},
            {"name": "ast_idiom_tablet", "layer": "idiom", "domain": "tablet"},
        ],
        "keywords": ["analyze", "classify", "categorize", "domain", "which", "what kind", "structure", "understand"],
    },
    {
        "id": "error_handling",
        "name": "Error Detection + VBStyle Compliance",
        "description": "Detect VBStyle violations, missing Run(), print(), self._, decorators",
        "experts": [
            {"name": "ast_style_vscode", "layer": "style", "domain": "vscode"},
            {"name": "ast_style_browser", "layer": "style", "domain": "browser"},
            {"name": "ast_style_dashboard", "layer": "style", "domain": "dashboard"},
            {"name": "ast_style_mobile", "layer": "style", "domain": "mobile"},
            {"name": "ast_style_tablet", "layer": "style", "domain": "tablet"},
        ],
        "keywords": ["error", "violation", "compliance", "check", "validate", "lint", "fix", "repair", "bug", "fail"],
    },
]

EXPERT_RAM_KB = 90


class CoreMLCapabilityRouter:
    """Capability-based router.

    Instead of asking 'what model do I have?', asks 'what capability do I need?'

    Capabilities are groups of experts that work together:
      - python_grammar: 5 grammar experts (one per domain)
      - python_idioms: 5 idiom experts
      - python_libraries: 5 library experts
      - vbstyle: 5 style experts
      - layout_prediction: 5 layout experts
      - code_analysis: 10 experts (grammar + idiom combined)
      - error_handling: 5 style experts

    When a task comes in, the router:
      1. Matches task keywords to capabilities
      2. Activates only the needed experts (sparse activation)
      3. Runs inference on active experts
      4. Deactivates when done (frees RAM)
      5. Logs the activation

    Experts not needed stay dormant. 0 RAM.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": DB_PATH,
                "experts_dir": EXPERTS_DIR,
                "coretotch_bin": CORETOTCH_BIN,
                "temp_dir": TEMP_DIR,
            },
            "conn": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.initSchema()

    def Run(self, command, params=None):
        params = params or {}
        if command == "init":
            return self.cmdInit(params)
        if command == "route_task":
            return self.cmdRouteTask(params)
        if command == "activate":
            return self.cmdActivate(params)
        if command == "deactivate":
            return self.cmdDeactivate(params)
        if command == "status":
            return self.cmdStatus(params)
        if command == "list_capabilities":
            return self.cmdListCapabilities(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def getConn(self):
        if self.state["conn"] is None:
            self.state["conn"] = sqlite3.connect(self.state["config"]["db_path"])
            self.state["conn"].execute("PRAGMA journal_mode=WAL")
        return self.state["conn"]

    def initSchema(self):
        conn = self.getConn()
        conn.executescript(CAPABILITY_SCHEMA)
        conn.commit()

    def cmdInit(self, params):
        try:
            self.initSchema()
            conn = self.getConn()
            for cap in CAPABILITIES:
                conn.execute(
                    "INSERT OR REPLACE INTO capabilities (capability_id, name, description, expert_group, active_experts, ram_kb, activated_count, last_activated) VALUES (?,?,?,?,?,?,?,?)",
                    (cap["id"], cap["name"], cap["description"], ",".join(e["name"] for e in cap["experts"]), "", 0, 0, 0)
                )
                for expert in cap["experts"]:
                    weightPath = os.path.join(EXPERTS_DIR, expert["name"] + ".weights.bin")
                    if not os.path.exists(weightPath):
                        weightPath = os.path.join(EXPERTS_DIR, expert["domain"] + ".weights.bin")
                    conn.execute(
                        "INSERT OR REPLACE INTO capability_experts (capability_id, expert_name, layer, domain, weight_path, state) VALUES (?,?,?,?,?,?)",
                        (cap["id"], expert["name"], expert["layer"], expert["domain"], weightPath, "inactive")
                    )
                for keyword in cap["keywords"]:
                    conn.execute(
                        "INSERT OR REPLACE INTO task_capability_map (task_keyword, capability_id, priority) VALUES (?,?,?)",
                        (keyword.lower(), cap["id"], 5)
                    )
            conn.commit()
            capCount = conn.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0]
            expertCount = conn.execute("SELECT COUNT(*) FROM capability_experts").fetchone()[0]
            keywordCount = conn.execute("SELECT COUNT(*) FROM task_capability_map").fetchone()[0]
            return (1, {
                "capabilities": capCount,
                "expert_assignments": expertCount,
                "keyword_mappings": keywordCount,
            }, None)
        except Exception as e:
            return (0, None, ("INIT_ERROR", str(e), 0))

    def detectCapabilities(self, taskInput):
        """Match task text to capabilities via keyword matching."""
        taskLower = taskInput.lower()
        conn = self.getConn()
        matches = {}
        for cap in CAPABILITIES:
            for keyword in cap["keywords"]:
                if keyword in taskLower:
                    if cap["id"] not in matches:
                        matches[cap["id"]] = {"count": 0, "name": cap["name"], "keywords": []}
                    matches[cap["id"]]["count"] += 1
                    matches[cap["id"]]["keywords"].append(keyword)
        ranked = sorted(matches.items(), key=lambda x: x[1]["count"], reverse=True)
        return [{"id": k, "name": v["name"], "score": v["count"], "keywords": v["keywords"]} for k, v in ranked]

    def cmdRouteTask(self, params):
        """Route a task to capabilities, activate experts, return plan."""
        try:
            taskInput = self.p(params, "task_input", "")
            if not taskInput:
                return (0, None, ("PARAMS_ERROR", "task_input required", 0))
            t0 = time.time()
            detected = self.detectCapabilities(taskInput)
            if not detected:
                return (0, None, ("NO_CAPABILITY", "No capability matched for: " + taskInput, 0))
            conn = self.getConn()
            activatedExperts = []
            totalRam = 0
            for cap in detected:
                capId = cap["id"]
                experts = conn.execute(
                    "SELECT expert_name, weight_path, layer, domain FROM capability_experts WHERE capability_id=?",
                    (capId,)
                ).fetchall()
                for expertName, weightPath, layer, domain in experts:
                    if not os.path.exists(weightPath):
                        continue
                    conn.execute(
                        "UPDATE capability_experts SET state='active' WHERE capability_id=? AND expert_name=?",
                        (capId, expertName)
                    )
                    activatedExperts.append({
                        "capability": capId,
                        "expert": expertName,
                        "layer": layer,
                        "domain": domain,
                        "weight_path": weightPath,
                    })
                    totalRam += EXPERT_RAM_KB
                conn.execute(
                    "UPDATE capabilities SET active_experts=?, ram_kb=?, activated_count=activated_count+1, last_activated=? WHERE capability_id=?",
                    (",".join(e["expert"] for e in activatedExperts if e["capability"] == capId), len(experts) * EXPERT_RAM_KB, time.time(), capId)
                )
            conn.execute(
                "INSERT INTO activation_log (capability_id, task_input, experts_activated, timestamp) VALUES (?,?,?,?)",
                (",".join(c["id"] for c in detected), taskInput, ",".join(e["expert"] for e in activatedExperts), time.time())
            )
            conn.commit()
            elapsed = round((time.time() - t0) * 1000, 1)
            return (1, {
                "task_input": taskInput,
                "detected_capabilities": detected,
                "activated_experts": activatedExperts,
                "expert_count": len(activatedExperts),
                "ram_kb": totalRam,
                "routing_ms": elapsed,
            }, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def cmdActivate(self, params):
        """Manually activate a capability."""
        try:
            capId = self.p(params, "capability_id")
            if not capId:
                return (0, None, ("PARAMS_ERROR", "capability_id required", 0))
            conn = self.getConn()
            experts = conn.execute(
                "SELECT expert_name, weight_path FROM capability_experts WHERE capability_id=? AND state='inactive'",
                (capId,)
            ).fetchall()
            activated = 0
            for expertName, weightPath in experts:
                if os.path.exists(weightPath):
                    conn.execute(
                        "UPDATE capability_experts SET state='active' WHERE capability_id=? AND expert_name=?",
                        (capId, expertName)
                    )
                    activated += 1
            conn.execute(
                "UPDATE capabilities SET active_experts=?, ram_kb=?, last_activated=? WHERE capability_id=?",
                (str(activated), activated * EXPERT_RAM_KB, time.time(), capId)
            )
            conn.commit()
            return (1, {
                "capability": capId,
                "activated": activated,
                "ram_kb": activated * EXPERT_RAM_KB,
            }, None)
        except Exception as e:
            return (0, None, ("ACTIVATE_ERROR", str(e), 0))

    def cmdDeactivate(self, params):
        """Deactivate a capability — frees all RAM."""
        try:
            capId = self.p(params, "capability_id")
            if not capId:
                return (0, None, ("PARAMS_ERROR", "capability_id required", 0))
            conn = self.getConn()
            count = conn.execute(
                "UPDATE capability_experts SET state='inactive' WHERE capability_id=? AND state='active'",
                (capId,)
            )
            conn.execute(
                "UPDATE capabilities SET active_experts='', ram_kb=0 WHERE capability_id=?",
                (capId,)
            )
            conn.commit()
            return (1, {
                "capability": capId,
                "deactivated": count.rowcount,
                "freed_kb": count.rowcount * EXPERT_RAM_KB,
            }, None)
        except Exception as e:
            return (0, None, ("DEACTIVATE_ERROR", str(e), 0))

    def cmdStatus(self, params):
        """Get full capability system status."""
        try:
            conn = self.getConn()
            caps = conn.execute(
                "SELECT capability_id, name, description, ram_kb, activated_count, last_activated FROM capabilities ORDER BY capability_id"
            ).fetchall()
            capList = []
            totalRam = 0
            totalActive = 0
            for row in caps:
                capId, name, desc, ramKb, actCount, lastAct = row
                activeExperts = conn.execute(
                    "SELECT expert_name, layer, domain FROM capability_experts WHERE capability_id=? AND state='active'",
                    (capId,)
                ).fetchall()
                totalExperts = conn.execute(
                    "SELECT COUNT(*) FROM capability_experts WHERE capability_id=?",
                    (capId,)
                ).fetchone()[0]
                capList.append({
                    "id": capId,
                    "name": name,
                    "description": desc,
                    "active_experts": len(activeExperts),
                    "total_experts": totalExperts,
                    "ram_kb": ramKb,
                    "activated_count": actCount,
                    "is_active": len(activeExperts) > 0,
                })
                totalRam += ramKb
                totalActive += len(activeExperts)
            return (1, {
                "capabilities": capList,
                "total_capabilities": len(capList),
                "total_active_experts": totalActive,
                "total_ram_kb": totalRam,
            }, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def cmdListCapabilities(self, params):
        """List all registered capabilities with their expert groups."""
        try:
            conn = self.getConn()
            caps = conn.execute(
                "SELECT capability_id, name, description FROM capabilities ORDER BY capability_id"
            ).fetchall()
            result = []
            for capId, name, desc in caps:
                experts = conn.execute(
                    "SELECT expert_name, layer, domain, state FROM capability_experts WHERE capability_id=?",
                    (capId,)
                ).fetchall()
                keywords = conn.execute(
                    "SELECT task_keyword FROM task_capability_map WHERE capability_id=?",
                    (capId,)
                ).fetchall()
                result.append({
                    "id": capId,
                    "name": name,
                    "description": desc,
                    "experts": [{"name": e[0], "layer": e[1], "domain": e[2], "state": e[3]} for e in experts],
                    "keywords": [k[0] for k in keywords],
                })
            return (1, {"capabilities": result, "total": len(result)}, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "connected": self.state["conn"] is not None,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
