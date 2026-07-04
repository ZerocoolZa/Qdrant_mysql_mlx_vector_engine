#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLRouter.py
#[@SUMMARY] DB-driven routing engine: scores, ranks, and auto-selects best backpack per task
#[@CLASS] CoreMLRouter
#[@METHOD] register_task, detect_domain, route, score, rank, update_score, auto_route
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import time
import sqlite3
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"

ROUTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_domains (
    domain TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    keywords TEXT DEFAULT '',
    priority INTEGER DEFAULT 0,
    created_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS model_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    accuracy REAL DEFAULT 0.0,
    latency_ms REAL DEFAULT 0.0,
    ram_kb REAL DEFAULT 90.0,
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_used REAL DEFAULT 0,
    score REAL DEFAULT 0.0,
    UNIQUE(model_name, version)
);

CREATE TABLE IF NOT EXISTS routing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_input TEXT,
    detected_domain TEXT,
    selected_model TEXT,
    selected_version INTEGER,
    score REAL,
    timestamp REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_scores_domain ON model_scores(domain);
CREATE INDEX IF NOT EXISTS idx_scores_score ON model_scores(score DESC);
"""

DOMAIN_KEYWORDS = {
    "vscode": "ide,editor,code,panel,sidebar,explorer,tab,terminal",
    "browser": "browser,web,url,tab,bookmark,toolbar,address",
    "dashboard": "dashboard,analytics,chart,graph,widget,metric,kpi",
    "mobile": "mobile,phone,portrait,touch,swipe,app,screen",
    "tablet": "tablet,landscape,split, multitouch,dual",
}

SCORING_WEIGHTS = {
    "accuracy": 0.5,
    "latency": 0.2,
    "success_rate": 0.2,
    "usage_recency": 0.1,
}


class CoreMLRouter:
    """DB-driven routing engine.

    The database decides which backpack to load.
    No manual switching in C. The router:
      1. Detects domain from task input
      2. Queries model_scores for that domain
      3. Ranks by composite score (accuracy + latency + success + recency)
      4. Returns best backpack
      5. Updates scores after inference (feedback loop)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": DB_PATH},
            "conn": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.initRouter()

    def Run(self, command, params=None):
        params = params or {}
        if command == "init":
            return self.cmdInit(params)
        if command == "register_domain":
            return self.cmdRegisterDomain(params)
        if command == "detect_domain":
            return self.cmdDetectDomain(params)
        if command == "route":
            return self.cmdRoute(params)
        if command == "rank":
            return self.cmdRank(params)
        if command == "update_score":
            return self.cmdUpdateScore(params)
        if command == "auto_route":
            return self.cmdAutoRoute(params)
        if command == "history":
            return self.cmdHistory(params)
        if command == "seed_scores":
            return self.cmdSeedScores(params)
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

    def initRouter(self):
        conn = self.getConn()
        conn.executescript(ROUTER_SCHEMA)
        conn.commit()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            conn.execute(
                "INSERT OR IGNORE INTO task_domains (domain, keywords, priority, created_at) VALUES (?,?,?,?)",
                (domain, keywords, 0, time.time()),
            )
        conn.commit()

    def cmdInit(self, params):
        try:
            self.initRouter()
            conn = self.getConn()
            domains = conn.execute("SELECT COUNT(*) FROM task_domains").fetchone()[0]
            scores = conn.execute("SELECT COUNT(*) FROM model_scores").fetchone()[0]
            return (1, {"domains": domains, "scored_models": scores}, None)
        except Exception as e:
            return (0, None, ("INIT_ERROR", str(e), 0))

    def cmdRegisterDomain(self, params):
        try:
            domain = self.p(params, "domain")
            keywords = self.p(params, "keywords", "")
            description = self.p(params, "description", "")
            priority = int(self.p(params, "priority", 0))
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            conn = self.getConn()
            conn.execute(
                "INSERT OR REPLACE INTO task_domains (domain, keywords, priority, description, created_at) VALUES (?,?,?,?,?)",
                (domain, keywords, priority, description, time.time()),
            )
            conn.commit()
            return (1, {"registered": domain, "keywords": keywords}, None)
        except Exception as e:
            return (0, None, ("REGISTER_DOMAIN_ERROR", str(e), 0))

    def cmdDetectDomain(self, params):
        """Detect domain from task input text using keyword matching."""
        try:
            taskInput = self.p(params, "task_input", "")
            if not taskInput:
                return (0, None, ("PARAMS_ERROR", "task_input required", 0))
            conn = self.getConn()
            rows = conn.execute("SELECT domain, keywords, priority FROM task_domains").fetchall()
            bestDomain = None
            bestScore = 0
            taskLower = taskInput.lower()
            for domain, keywords, priority in rows:
                kwList = [k.strip().lower() for k in (keywords or "").split(",") if k.strip()]
                score = 0
                for kw in kwList:
                    if kw in taskLower:
                        score += 1
                score += priority * 0.1
                if score > bestScore:
                    bestScore = score
                    bestDomain = domain
            if not bestDomain:
                return (0, None, ("NO_MATCH", "No domain matched: " + taskInput, 0))
            return (1, {
                "detected_domain": bestDomain,
                "confidence": round(bestScore, 2),
                "task_input": taskInput,
            }, None)
        except Exception as e:
            return (0, None, ("DETECT_ERROR", str(e), 0))

    def cmdRoute(self, params):
        """Route to best model for a given domain, using DB scoring."""
        try:
            domain = self.p(params, "domain")
            if not domain:
                taskInput = self.p(params, "task_input", "")
                if taskInput:
                    ok, detectData, detectErr = self.cmdDetectDomain({"task_input": taskInput})
                    if ok:
                        domain = detectData["detected_domain"]
                    else:
                        return (0, None, detectErr)
                else:
                    return (0, None, ("PARAMS_ERROR", "domain or task_input required", 0))
            conn = self.getConn()
            rows = conn.execute(
                "SELECT model_name, version, accuracy, latency_ms, ram_kb, usage_count, success_count, fail_count, score FROM model_scores WHERE domain=? ORDER BY score DESC",
                (domain,),
            ).fetchall()
            if not rows:
                rows2 = conn.execute(
                    "SELECT name, version FROM models WHERE domain=? AND active=1 ORDER BY version DESC LIMIT 1",
                    (domain,),
                ).fetchone()
                if not rows2:
                    return (0, None, ("NO_MODEL", "No scored model for domain: " + domain, 0))
                return (1, {
                    "domain": domain,
                    "model": rows2[0],
                    "version": rows2[1],
                    "score": 0.0,
                    "note": "no scores yet, using latest active model",
                }, None)
            best = rows[0]
            modelName, version, accuracy, latency, ram, usage, success, fail, score = best
            conn.execute(
                "INSERT INTO routing_history (task_input, detected_domain, selected_model, selected_version, score, timestamp) VALUES (?,?,?,?,?,?)",
                (self.p(params, "task_input", ""), domain, modelName, version, score, time.time()),
            )
            conn.execute(
                "UPDATE model_scores SET usage_count=usage_count+1, last_used=? WHERE model_name=? AND version=?",
                (time.time(), modelName, version),
            )
            conn.commit()
            return (1, {
                "domain": domain,
                "model": modelName,
                "version": version,
                "score": round(score, 4),
                "accuracy": accuracy,
                "latency_ms": latency,
                "ram_kb": ram,
                "usage_count": usage + 1,
            }, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def cmdRank(self, params):
        """Rank all models for a domain by composite score."""
        try:
            domain = self.p(params, "domain")
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            conn = self.getConn()
            rows = conn.execute(
                "SELECT model_name, version, accuracy, latency_ms, usage_count, success_count, fail_count, score FROM model_scores WHERE domain=? ORDER BY score DESC",
                (domain,),
            ).fetchall()
            rankings = []
            for i, row in enumerate(rows):
                rankings.append({
                    "rank": i + 1,
                    "model": row[0],
                    "version": row[1],
                    "accuracy": row[2],
                    "latency_ms": row[3],
                    "usage_count": row[4],
                    "success_count": row[5],
                    "fail_count": row[6],
                    "score": round(row[7], 4),
                })
            return (1, {"domain": domain, "rankings": rankings, "total": len(rankings)}, None)
        except Exception as e:
            return (0, None, ("RANK_ERROR", str(e), 0))

    def cmdUpdateScore(self, params):
        """Update model score after inference (feedback loop)."""
        try:
            modelName = self.p(params, "model_name")
            version = int(self.p(params, "version", 1))
            success = self.p(params, "success", True)
            accuracy = self.p(params, "accuracy", None)
            latencyMs = self.p(params, "latency_ms", None)
            if not modelName:
                return (0, None, ("PARAMS_ERROR", "model_name required", 0))
            conn = self.getConn()
            row = conn.execute(
                "SELECT accuracy, latency_ms, usage_count, success_count, fail_count FROM model_scores WHERE model_name=? AND version=?",
                (modelName, version),
            ).fetchone()
            if not row:
                return (0, None, ("MODEL_NOT_SCORED", modelName + " v" + str(version), 0))
            curAcc, curLat, curUsage, curSuccess, curFail = row
            newUsage = curUsage + 1
            newSuccess = curSuccess + (1 if success else 0)
            newFail = curFail + (0 if success else 1)
            newAcc = accuracy if accuracy is not None else curAcc
            newLat = latencyMs if latencyMs is not None else curLat
            successRate = newSuccess / newUsage if newUsage > 0 else 0.0
            compositeScore = (
                SCORING_WEIGHTS["accuracy"] * newAcc
                + SCORING_WEIGHTS["latency"] * max(0, 1.0 - newLat / 100.0)
                + SCORING_WEIGHTS["success_rate"] * successRate
                + SCORING_WEIGHTS["usage_recency"] * min(1.0, newUsage / 10.0)
            )
            conn.execute(
                "UPDATE model_scores SET accuracy=?, latency_ms=?, usage_count=?, success_count=?, fail_count=?, score=? WHERE model_name=? AND version=?",
                (newAcc, newLat, newUsage, newSuccess, newFail, compositeScore, modelName, version),
            )
            conn.commit()
            return (1, {
                "model": modelName,
                "version": version,
                "new_score": round(compositeScore, 4),
                "usage": newUsage,
                "success_rate": round(successRate, 4),
            }, None)
        except Exception as e:
            return (0, None, ("UPDATE_SCORE_ERROR", str(e), 0))

    def cmdAutoRoute(self, params):
        """Full auto-routing: detect domain → route → return backpack path."""
        try:
            taskInput = self.p(params, "task_input", "")
            if not taskInput:
                return (0, None, ("PARAMS_ERROR", "task_input required", 0))
            ok, detectData, detectErr = self.cmdDetectDomain({"task_input": taskInput})
            if not ok:
                return (0, None, detectErr)
            domain = detectData["detected_domain"]
            ok, routeData, routeErr = self.cmdRoute({"domain": domain, "task_input": taskInput})
            if not ok:
                return (0, None, routeErr)
            return (1, {
                "task_input": taskInput,
                "detected_domain": domain,
                "detection_confidence": detectData["confidence"],
                "selected_model": routeData["model"],
                "selected_version": routeData["version"],
                "score": routeData["score"],
                "ram_kb": routeData.get("ram_kb", 90.0),
            }, None)
        except Exception as e:
            return (0, None, ("AUTO_ROUTE_ERROR", str(e), 0))

    def cmdHistory(self, params):
        """Get routing history."""
        try:
            limit = int(self.p(params, "limit", 10))
            conn = self.getConn()
            rows = conn.execute(
                "SELECT task_input, detected_domain, selected_model, selected_version, score, timestamp FROM routing_history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            history = []
            for row in rows:
                history.append({
                    "task_input": row[0],
                    "domain": row[1],
                    "model": row[2],
                    "version": row[3],
                    "score": round(row[4], 4) if row[4] else 0.0,
                    "timestamp": row[5],
                })
            return (1, {"history": history, "total": len(history)}, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def cmdSeedScores(self, params):
        """Seed initial scores for all models in the DB."""
        try:
            conn = self.getConn()
            models = conn.execute("SELECT name, domain, version FROM models WHERE active=1").fetchall()
            seeded = 0
            for name, domain, version in models:
                conn.execute(
                    "INSERT OR IGNORE INTO model_scores (model_name, domain, version, accuracy, latency_ms, ram_kb, usage_count, success_count, fail_count, score) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (name, domain, version, 0.5, 10.0, 90.0, 0, 0, 0, 0.5),
                )
                seeded += 1
            conn.commit()
            return (1, {"seeded": seeded}, None)
        except Exception as e:
            return (0, None, ("SEED_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "connected": self.state["conn"] is not None,
            "scoring_weights": SCORING_WEIGHTS,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
