#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLModelDB.py
#[@SUMMARY] SQLite model database: stores expert weights, versions, routes, cache state as BLOB rows
#[@CLASS] CoreMLModelDB
#[@METHOD] init, store, load, route, ensemble, list, prune, stats, hot_load, hot_evict, hot_stats
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import sqlite3
import time
import json
import struct
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"
TOTAL_PARAMS = 23050
WEIGHT_SIZE_BYTES = TOTAL_PARAMS * 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT DEFAULT '',
    weights BLOB NOT NULL,
    normalization TEXT DEFAULT '',
    metadata TEXT DEFAULT '',
    created_at REAL DEFAULT 0,
    active INTEGER DEFAULT 0,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS routes (
    domain TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    priority INTEGER DEFAULT 0,
    updated_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cache_state (
    slot INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    loaded_at REAL DEFAULT 0,
    last_access REAL DEFAULT 0,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    model_name TEXT,
    timestamp REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_models_name ON models(name);
CREATE INDEX IF NOT EXISTS idx_models_domain ON models(domain);
CREATE INDEX IF NOT EXISTS idx_models_active ON models(active);
"""


class CoreMLModelDB:
    """SQLite model database — the model bank as a queryable store.

    Tables:
      models      — expert weights as BLOB, with domain, version, metadata
      routes      — domain → expert mapping
      cache_state — hot cache slots (which models are in RAM)
      access_log  — every load/hit/evict event
      stats       — counters (hits, misses, evictions, reloads)

    All weight data stored as BLOB (raw float32 bytes).
    No files on disk. One .sqlite file = entire model bank.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": DB_PATH,
                "max_hot": 2,
            },
            "conn": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.initDB()

    def Run(self, command, params=None):
        params = params or {}
        if command == "init":
            return self.cmdInit(params)
        if command == "store":
            return self.cmdStore(params)
        if command == "load":
            return self.cmdLoad(params)
        if command == "route":
            return self.cmdRoute(params)
        if command == "ensemble":
            return self.cmdEnsemble(params)
        if command == "list":
            return self.cmdList(params)
        if command == "prune":
            return self.cmdPrune(params)
        if command == "stats":
            return self.cmdStats(params)
        if command == "hot_load":
            return self.cmdHotLoad(params)
        if command == "hot_evict":
            return self.cmdHotEvict(params)
        if command == "hot_stats":
            return self.cmdHotStats(params)
        if command == "hot_clear":
            return self.cmdHotClear(params)
        if command == "set_cache_size":
            return self.cmdSetCacheSize(params)
        if command == "import_files":
            return self.cmdImportFiles(params)
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
            path = self.state["config"]["db_path"]
            self.state["conn"] = sqlite3.connect(path)
            self.state["conn"].execute("PRAGMA journal_mode=WAL")
        return self.state["conn"]

    def initDB(self):
        conn = self.getConn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        for key in ["hits", "misses", "evictions", "reloads"]:
            conn.execute(
                "INSERT OR IGNORE INTO stats (key, value) VALUES (?, 0)",
                (key,),
            )
        conn.commit()

    def cmdInit(self, params):
        try:
            self.initDB()
            conn = self.getConn()
            count = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
            return (1, {"db_path": self.state["config"]["db_path"], "models": count}, None)
        except Exception as e:
            return (0, None, ("INIT_ERROR", str(e), 0))

    def cmdStore(self, params):
        """Store a model's weights as BLOB in the database."""
        try:
            name = self.p(params, "name")
            domain = self.p(params, "domain", "general")
            version = int(self.p(params, "version", 0))
            description = self.p(params, "description", "")
            weightsPath = self.p(params, "weights_path")
            normalization = self.p(params, "normalization", "")
            metadata = self.p(params, "metadata", "")
            if not name or not weightsPath:
                return (0, None, ("PARAMS_ERROR", "name and weights_path required", 0))
            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", weightsPath, 0))
            with open(weightsPath, "rb") as f:
                weightsBlob = f.read()
            if len(weightsBlob) != WEIGHT_SIZE_BYTES:
                return (0, None, ("WEIGHTS_SIZE", "Expected " + str(WEIGHT_SIZE_BYTES) + " got " + str(len(weightsBlob)), 0))
            conn = self.getConn()
            if version == 0:
                row = conn.execute(
                    "SELECT MAX(version) FROM models WHERE name=?", (name,)
                ).fetchone()
                version = (row[0] or 0) + 1
            conn.execute("UPDATE models SET active=0 WHERE name=?", (name,))
            conn.execute(
                "INSERT OR REPLACE INTO models (name, domain, version, description, weights, normalization, metadata, created_at, active) VALUES (?,?,?,?,?,?,?,?,1)",
                (name, domain, version, description, weightsBlob, normalization, metadata, time.time()),
            )
            conn.commit()
            return (1, {
                "stored": name,
                "version": version,
                "domain": domain,
                "blob_size": len(weightsBlob),
            }, None)
        except Exception as e:
            return (0, None, ("STORE_ERROR", str(e), 0))

    def cmdLoad(self, params):
        """Load a model's weights from DB to a file (for C inference)."""
        try:
            name = self.p(params, "name")
            version = self.p(params, "version", "latest")
            outputPath = self.p(params, "output_path")
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            conn = self.getConn()
            if version == "latest":
                row = conn.execute(
                    "SELECT version, weights, domain FROM models WHERE name=? AND active=1", (name,)
                ).fetchone()
                if not row:
                    row = conn.execute(
                        "SELECT version, weights, domain FROM models WHERE name=? ORDER BY version DESC LIMIT 1", (name,)
                    ).fetchone()
            else:
                row = conn.execute(
                    "SELECT version, weights, domain FROM models WHERE name=? AND version=?", (name, int(version))
                ).fetchone()
            if not row:
                return (0, None, ("MODEL_NOT_FOUND", name + " v" + str(version), 0))
            ver, weightsBlob, domain = row
            if outputPath:
                with open(outputPath, "wb") as f:
                    f.write(weightsBlob)
            return (1, {
                "name": name,
                "version": ver,
                "domain": domain,
                "blob_size": len(weightsBlob),
                "output_path": outputPath,
            }, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def cmdRoute(self, params):
        """Route a domain to the best expert in the DB."""
        try:
            domain = self.p(params, "domain")
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            conn = self.getConn()
            row = conn.execute(
                "SELECT name, version FROM models WHERE domain=? AND active=1 ORDER BY version DESC LIMIT 1",
                (domain,),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT name, version FROM models WHERE domain=? ORDER BY version DESC LIMIT 1",
                    (domain,),
                ).fetchone()
            if not row:
                return (0, None, ("NO_EXPERT", "No expert for domain: " + domain, 0))
            mName, mVer = row
            conn.execute(
                "INSERT OR REPLACE INTO routes (domain, model_name, model_version, priority, updated_at) VALUES (?,?,?,?,?)",
                (domain, mName, mVer, 0, time.time()),
            )
            conn.commit()
            return (1, {
                "domain": domain,
                "expert": mName,
                "version": mVer,
                "ram": "1 model (" + str(WEIGHT_SIZE_BYTES // 1024) + " KB)",
            }, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def cmdEnsemble(self, params):
        """Create an ensemble config from multiple DB experts."""
        try:
            experts = self.p(params, "experts", [])
            if not experts or not isinstance(experts, list):
                return (0, None, ("PARAMS_ERROR", "experts list required", 0))
            conn = self.getConn()
            config = []
            weight = 1.0 / len(experts)
            for name in experts:
                row = conn.execute(
                    "SELECT version, domain FROM models WHERE name=? AND active=1", (name,)
                ).fetchone()
                if not row:
                    row = conn.execute(
                        "SELECT version, domain FROM models WHERE name=? ORDER BY version DESC LIMIT 1", (name,)
                    ).fetchone()
                if not row:
                    return (0, None, ("MODEL_NOT_FOUND", name, 0))
                config.append({
                    "name": name,
                    "version": row[0],
                    "domain": row[1],
                    "weight": round(weight, 4),
                })
            return (1, {
                "ensemble": config,
                "ram": str(len(experts)) + " models (" + str(len(experts) * WEIGHT_SIZE_BYTES // 1024) + " KB)",
            }, None)
        except Exception as e:
            return (0, None, ("ENSEMBLE_ERROR", str(e), 0))

    def cmdList(self, params):
        """List all models in the database."""
        try:
            conn = self.getConn()
            rows = conn.execute(
                "SELECT name, domain, version, active, description, created_at FROM models ORDER BY name, version"
            ).fetchall()
            models = []
            for row in rows:
                models.append({
                    "name": row[0],
                    "domain": row[1],
                    "version": row[2],
                    "active": bool(row[3]),
                    "description": row[4],
                    "created": row[5],
                })
            return (1, {
                "total_models": len(models),
                "total_versions": len(models),
                "db_size_bytes": os.path.getsize(self.state["config"]["db_path"]) if os.path.exists(self.state["config"]["db_path"]) else 0,
                "models": models,
            }, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def cmdPrune(self, params):
        """Remove old inactive versions, keep latest N per model."""
        try:
            keepN = int(self.p(params, "keep", 2))
            conn = self.getConn()
            names = conn.execute("SELECT DISTINCT name FROM models").fetchall()
            removed = 0
            for (name,) in names:
                versions = conn.execute(
                    "SELECT version FROM models WHERE name=? ORDER BY version DESC", (name,)
                ).fetchall()
                for i, (ver,) in enumerate(versions):
                    if i >= keepN:
                        conn.execute("DELETE FROM models WHERE name=? AND version=?", (name, ver))
                        removed += 1
            conn.commit()
            return (1, {"pruned": removed, "kept_per_model": keepN}, None)
        except Exception as e:
            return (0, None, ("PRUNE_ERROR", str(e), 0))

    def cmdStats(self, params):
        """Get database stats."""
        try:
            conn = self.getConn()
            totalModels = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
            totalRoutes = conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
            cacheSlots = conn.execute("SELECT COUNT(*) FROM cache_state").fetchone()[0]
            dbSize = os.path.getsize(self.state["config"]["db_path"]) if os.path.exists(self.state["config"]["db_path"]) else 0
            statRows = conn.execute("SELECT key, value FROM stats").fetchall()
            statDict = {row[0]: row[1] for row in statRows}
            return (1, {
                "total_models": totalModels,
                "total_routes": totalRoutes,
                "hot_cache_slots": cacheSlots,
                "max_hot": self.state["config"]["max_hot"],
                "db_size_bytes": dbSize,
                "db_size_kb": round(dbSize / 1024, 1),
                "counters": statDict,
            }, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def cmdHotLoad(self, params):
        """Load a model into hot cache (RAM slot in DB)."""
        try:
            name = self.p(params, "name")
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            conn = self.getConn()
            maxHot = self.state["config"]["max_hot"]
            existing = conn.execute(
                "SELECT slot, model_name, last_access FROM cache_state WHERE model_name=?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE cache_state SET last_access=?, access_count=access_count+1 WHERE model_name=?",
                    (time.time(), name),
                )
                conn.execute("UPDATE stats SET value=value+1 WHERE key='hits'")
                conn.execute("INSERT INTO access_log (action, model_name, timestamp) VALUES ('hit', ?, ?)", (name, time.time()))
                conn.commit()
                return (1, {"status": "HIT", "name": name, "slot": existing[0]}, None)
            cacheCount = conn.execute("SELECT COUNT(*) FROM cache_state").fetchone()[0]
            if cacheCount >= maxHot:
                lru = conn.execute(
                    "SELECT slot, model_name FROM cache_state ORDER BY last_access ASC LIMIT 1"
                ).fetchone()
                if lru:
                    conn.execute("DELETE FROM cache_state WHERE slot=?", (lru[0],))
                    conn.execute("UPDATE stats SET value=value+1 WHERE key='evictions'")
                    conn.execute("INSERT INTO access_log (action, model_name, timestamp) VALUES ('evict', ?, ?)", (lru[1], time.time()))
                    slot = lru[0]
                else:
                    slot = cacheCount
            else:
                slot = cacheCount
            conn.execute(
                "INSERT INTO cache_state (slot, model_name, model_version, loaded_at, last_access, access_count) VALUES (?,?,?,?,?,1)",
                (slot, name, 0, time.time(), time.time()),
            )
            conn.execute("UPDATE stats SET value=value+1 WHERE key='misses'")
            conn.execute("UPDATE stats SET value=value+1 WHERE key='reloads'")
            conn.execute("INSERT INTO access_log (action, model_name, timestamp) VALUES ('load', ?, ?)", (name, time.time()))
            conn.commit()
            return (1, {"status": "MISS", "name": name, "slot": slot, "cache_size": slot + 1}, None)
        except Exception as e:
            return (0, None, ("HOT_LOAD_ERROR", str(e), 0))

    def cmdHotEvict(self, params):
        """Evict LRU model from hot cache."""
        try:
            conn = self.getConn()
            lru = conn.execute(
                "SELECT slot, model_name FROM cache_state ORDER BY last_access ASC LIMIT 1"
            ).fetchone()
            if not lru:
                return (0, None, ("CACHE_EMPTY", "no models in cache", 0))
            conn.execute("DELETE FROM cache_state WHERE slot=?", (lru[0],))
            conn.execute("UPDATE stats SET value=value+1 WHERE key='evictions'")
            conn.execute("INSERT INTO access_log (action, model_name, timestamp) VALUES ('evict', ?, ?)", (lru[1], time.time()))
            conn.commit()
            return (1, {"evicted": lru[1], "slot": lru[0], "freed_bytes": WEIGHT_SIZE_BYTES}, None)
        except Exception as e:
            return (0, None, ("HOT_EVICT_ERROR", str(e), 0))

    def cmdHotStats(self, params):
        """Get hot cache stats from DB."""
        try:
            conn = self.getConn()
            slots = conn.execute(
                "SELECT slot, model_name, loaded_at, last_access, access_count FROM cache_state ORDER BY slot"
            ).fetchall()
            statRows = conn.execute("SELECT key, value FROM stats").fetchall()
            statDict = {row[0]: row[1] for row in statRows}
            hotModels = []
            for row in slots:
                hotModels.append({
                    "slot": row[0],
                    "name": row[1],
                    "loaded_at": row[2],
                    "last_access": row[3],
                    "access_count": row[4],
                })
            total = statDict.get("hits", 0) + statDict.get("misses", 0)
            hitRate = statDict.get("hits", 0) / total if total > 0 else 0.0
            return (1, {
                "hot_models": hotModels,
                "hot_count": len(hotModels),
                "max_hot": self.state["config"]["max_hot"],
                "ram_kb": round(len(hotModels) * WEIGHT_SIZE_BYTES / 1024, 1),
                "counters": statDict,
                "hit_rate": round(hitRate, 4),
            }, None)
        except Exception as e:
            return (0, None, ("HOT_STATS_ERROR", str(e), 0))

    def cmdHotClear(self, params):
        """Clear all hot cache slots."""
        try:
            conn = self.getConn()
            count = conn.execute("SELECT COUNT(*) FROM cache_state").fetchone()[0]
            conn.execute("DELETE FROM cache_state")
            conn.commit()
            return (1, {"cleared": count, "freed_bytes": count * WEIGHT_SIZE_BYTES}, None)
        except Exception as e:
            return (0, None, ("HOT_CLEAR_ERROR", str(e), 0))

    def cmdSetCacheSize(self, params):
        """Set max hot cache size."""
        try:
            newSize = int(self.p(params, "size", 2))
            self.state["config"]["max_hot"] = newSize
            conn = self.getConn()
            current = conn.execute("SELECT COUNT(*) FROM cache_state").fetchone()[0]
            while current > newSize:
                lru = conn.execute(
                    "SELECT slot, model_name FROM cache_state ORDER BY last_access ASC LIMIT 1"
                ).fetchone()
                if not lru:
                    break
                conn.execute("DELETE FROM cache_state WHERE slot=?", (lru[0],))
                conn.execute("UPDATE stats SET value=value+1 WHERE key='evictions'")
                current -= 1
            conn.commit()
            return (1, {"max_hot": newSize, "current": current}, None)
        except Exception as e:
            return (0, None, ("SET_SIZE_ERROR", str(e), 0))

    def cmdImportFiles(self, params):
        """Import all .weights.bin files from experts/ and model_bank/ into the DB."""
        try:
            baseDir = os.path.dirname(self.state["config"]["db_path"])
            expertsDir = os.path.join(baseDir, "experts")
            bankDir = os.path.join(baseDir, "model_bank")
            imported = 0
            skipped = 0
            for searchDir in [expertsDir, bankDir]:
                if not os.path.exists(searchDir):
                    continue
                for fname in os.listdir(searchDir):
                    if not fname.endswith(".weights.bin"):
                        continue
                    wpath = os.path.join(searchDir, fname)
                    baseName = fname.replace(".weights.bin", "")
                    if "_v" in baseName:
                        name = baseName.rsplit("_v", 1)[0]
                        version = int(baseName.rsplit("_v", 1)[1])
                    else:
                        name = baseName
                        version = 0
                    ok, data, err = self.cmdStore({
                        "name": name,
                        "domain": name,
                        "version": version,
                        "weights_path": wpath,
                        "description": "Imported from " + searchDir,
                    })
                    if ok:
                        imported += 1
                    else:
                        skipped += 1
            return (1, {"imported": imported, "skipped": skipped}, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

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
