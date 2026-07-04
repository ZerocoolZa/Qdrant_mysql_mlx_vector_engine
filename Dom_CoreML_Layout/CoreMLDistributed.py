#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLDistributed.py
#[@SUMMARY] Distributed GPU router: tracks GPU nodes, assigns experts, sparse activation across VRAM
#[@CLASS] CoreMLDistributed
#[@METHOD] register_gpu, assign_expert, route_distributed, activate, deactivate, status, rebalance
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import time
import sqlite3
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"
EXPERT_RAM_KB = 90
DEFAULT_VRAM_KB = 8 * 1024 * 1024

DISTRIBUTED_SCHEMA = """
CREATE TABLE IF NOT EXISTS gpu_nodes (
    node_id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    vram_total_kb REAL DEFAULT 8388608,
    vram_used_kb REAL DEFAULT 0,
    status TEXT DEFAULT 'idle',
    last_heartbeat REAL DEFAULT 0,
    metadata TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expert_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_name TEXT NOT NULL,
    expert_version INTEGER DEFAULT 1,
    node_id TEXT NOT NULL,
    state TEXT DEFAULT 'inactive',
    loaded_at REAL DEFAULT 0,
    last_active REAL DEFAULT 0,
    inference_count INTEGER DEFAULT 0,
    UNIQUE(expert_name, node_id)
);

CREATE TABLE IF NOT EXISTS activation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_name TEXT,
    node_id TEXT,
    action TEXT,
    timestamp REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_assign_node ON expert_assignments(node_id);
CREATE INDEX IF NOT EXISTS idx_assign_state ON expert_assignments(state);
"""


class CoreMLDistributed:
    """Distributed GPU router for sparse expert activation.

    Manages expert models across multiple GPU nodes:
      - register_gpu: add a GPU node with VRAM capacity
      - assign_expert: assign an expert to a GPU node
      - route_distributed: find which GPU has the needed expert
      - activate: mark expert as active (VRAM allocated)
      - deactivate: mark expert as inactive (VRAM freed)
      - rebalance: redistribute experts for load balancing

    Key principle: only active experts consume VRAM.
    Inactive experts stay assigned but dormant (0 VRAM).
    This is sparse activation across distributed GPUs.
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
        self.initSchema()

    def Run(self, command, params=None):
        params = params or {}
        if command == "init":
            return self.cmdInit(params)
        if command == "register_gpu":
            return self.cmdRegisterGpu(params)
        if command == "assign_expert":
            return self.cmdAssignExpert(params)
        if command == "route_distributed":
            return self.cmdRouteDistributed(params)
        if command == "activate":
            return self.cmdActivate(params)
        if command == "deactivate":
            return self.cmdDeactivate(params)
        if command == "status":
            return self.cmdStatus(params)
        if command == "rebalance":
            return self.cmdRebalance(params)
        if command == "auto_assign":
            return self.cmdAutoAssign(params)
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
        conn.executescript(DISTRIBUTED_SCHEMA)
        conn.commit()

    def cmdInit(self, params):
        try:
            self.initSchema()
            conn = self.getConn()
            gpus = conn.execute("SELECT COUNT(*) FROM gpu_nodes").fetchone()[0]
            assignments = conn.execute("SELECT COUNT(*) FROM expert_assignments").fetchone()[0]
            return (1, {"gpu_nodes": gpus, "expert_assignments": assignments}, None)
        except Exception as e:
            return (0, None, ("INIT_ERROR", str(e), 0))

    def cmdRegisterGpu(self, params):
        try:
            nodeId = self.p(params, "node_id")
            name = self.p(params, "name", nodeId)
            vramKb = float(self.p(params, "vram_kb", DEFAULT_VRAM_KB))
            metadata = self.p(params, "metadata", "")
            if not nodeId:
                return (0, None, ("PARAMS_ERROR", "node_id required", 0))
            conn = self.getConn()
            conn.execute(
                "INSERT OR REPLACE INTO gpu_nodes (node_id, name, vram_total_kb, vram_used_kb, status, last_heartbeat, metadata) VALUES (?,?,?,?,?,?,?)",
                (nodeId, name, vramKb, 0, "idle", time.time(), metadata),
            )
            conn.commit()
            return (1, {
                "registered": nodeId,
                "name": name,
                "vram_total_kb": vramKb,
                "vram_total_gb": round(vramKb / (1024 * 1024), 1),
                "vram_used_kb": 0,
                "experts assignable": int(vramKb / EXPERT_RAM_KB),
            }, None)
        except Exception as e:
            return (0, None, ("REGISTER_GPU_ERROR", str(e), 0))

    def cmdAssignExpert(self, params):
        try:
            expertName = self.p(params, "expert_name")
            nodeId = self.p(params, "node_id")
            version = int(self.p(params, "version", 1))
            if not expertName or not nodeId:
                return (0, None, ("PARAMS_ERROR", "expert_name and node_id required", 0))
            conn = self.getConn()
            gpu = conn.execute("SELECT vram_total_kb, vram_used_kb FROM gpu_nodes WHERE node_id=?", (nodeId,)).fetchone()
            if not gpu:
                return (0, None, ("GPU_NOT_FOUND", nodeId, 0))
            vramTotal, vramUsed = gpu
            conn.execute(
                "INSERT OR REPLACE INTO expert_assignments (expert_name, expert_version, node_id, state, loaded_at) VALUES (?,?,?,?,?)",
                (expertName, version, nodeId, "inactive", time.time()),
            )
            conn.commit()
            return (1, {
                "assigned": expertName,
                "version": version,
                "node": nodeId,
                "state": "inactive",
                "vram_total_kb": vramTotal,
                "vram_used_kb": vramUsed,
                "vram_free_kb": vramTotal - vramUsed,
            }, None)
        except Exception as e:
            return (0, None, ("ASSIGN_ERROR", str(e), 0))

    def cmdAutoAssign(self, params):
        """Auto-assign all models in DB to GPU nodes, balancing load."""
        try:
            conn = self.getConn()
            models = conn.execute("SELECT name, version FROM models WHERE active=1").fetchall()
            gpus = conn.execute("SELECT node_id, vram_total_kb, vram_used_kb FROM gpu_nodes").fetchall()
            if not gpus:
                return (0, None, ("NO_GPUS", "Register GPU nodes first", 0))
            assigned = 0
            for i, (name, version) in enumerate(models):
                gpu = gpus[i % len(gpus)]
                nodeId = gpu[0]
                conn.execute(
                    "INSERT OR REPLACE INTO expert_assignments (expert_name, expert_version, node_id, state, loaded_at) VALUES (?,?,?,?,?)",
                    (name, version, nodeId, "inactive", time.time()),
                )
                assigned += 1
            conn.commit()
            return (1, {"auto_assigned": assigned, "gpu_nodes": len(gpus)}, None)
        except Exception as e:
            return (0, None, ("AUTO_ASSIGN_ERROR", str(e), 0))

    def cmdActivate(self, params):
        """Activate an expert on a GPU — allocates VRAM."""
        try:
            expertName = self.p(params, "expert_name")
            nodeId = self.p(params, "node_id")
            if not expertName or not nodeId:
                return (0, None, ("PARAMS_ERROR", "expert_name and node_id required", 0))
            conn = self.getConn()
            assignment = conn.execute(
                "SELECT state FROM expert_assignments WHERE expert_name=? AND node_id=?", (expertName, nodeId)
            ).fetchone()
            if not assignment:
                return (0, None, ("NOT_ASSIGNED", expertName + " not assigned to " + nodeId, 0))
            if assignment[0] == "active":
                conn.execute(
                    "UPDATE expert_assignments SET last_active=?, inference_count=inference_count+1 WHERE expert_name=? AND node_id=?",
                    (time.time(), expertName, nodeId),
                )
                conn.commit()
                return (1, {"expert": expertName, "node": nodeId, "state": "already_active"}, None)
            gpu = conn.execute("SELECT vram_total_kb, vram_used_kb FROM gpu_nodes WHERE node_id=?", (nodeId,)).fetchone()
            if not gpu:
                return (0, None, ("GPU_NOT_FOUND", nodeId, 0))
            vramTotal, vramUsed = gpu
            if vramUsed + EXPERT_RAM_KB > vramTotal:
                activeOnNode = conn.execute(
                    "SELECT expert_name FROM expert_assignments WHERE node_id=? AND state='active' ORDER BY last_active ASC LIMIT 1",
                    (nodeId,),
                ).fetchone()
                if activeOnNode:
                    conn.execute(
                        "UPDATE expert_assignments SET state='inactive' WHERE expert_name=? AND node_id=?",
                        (activeOnNode[0], nodeId),
                    )
                    conn.execute(
                        "UPDATE gpu_nodes SET vram_used_kb=vram_used_kb-? WHERE node_id=?",
                        (EXPERT_RAM_KB, nodeId),
                    )
                    conn.execute(
                        "INSERT INTO activation_log (expert_name, node_id, action, timestamp) VALUES (?,?,?,?)",
                        (activeOnNode[0], nodeId, "auto_deactivate", time.time()),
                    )
                else:
                    return (0, None, ("VRAM_FULL", "No space on " + nodeId, 0))
            conn.execute(
                "UPDATE expert_assignments SET state='active', loaded_at=?, last_active=?, inference_count=inference_count+1 WHERE expert_name=? AND node_id=?",
                (time.time(), time.time(), expertName, nodeId),
            )
            conn.execute(
                "UPDATE gpu_nodes SET vram_used_kb=vram_used_kb+?, status='active' WHERE node_id=?",
                (EXPERT_RAM_KB, nodeId),
            )
            conn.execute(
                "INSERT INTO activation_log (expert_name, node_id, action, timestamp) VALUES (?,?,?,?)",
                (expertName, nodeId, "activate", time.time()),
            )
            conn.commit()
            return (1, {
                "expert": expertName,
                "node": nodeId,
                "state": "active",
                "ram_kb": EXPERT_RAM_KB,
            }, None)
        except Exception as e:
            return (0, None, ("ACTIVATE_ERROR", str(e), 0))

    def cmdDeactivate(self, params):
        """Deactivate an expert — frees VRAM."""
        try:
            expertName = self.p(params, "expert_name")
            nodeId = self.p(params, "node_id")
            if not expertName or not nodeId:
                return (0, None, ("PARAMS_ERROR", "expert_name and node_id required", 0))
            conn = self.getConn()
            assignment = conn.execute(
                "SELECT state FROM expert_assignments WHERE expert_name=? AND node_id=?", (expertName, nodeId)
            ).fetchone()
            if not assignment:
                return (0, None, ("NOT_ASSIGNED", expertName, 0))
            if assignment[0] != "active":
                return (1, {"expert": expertName, "node": nodeId, "state": "already_inactive"}, None)
            conn.execute(
                "UPDATE expert_assignments SET state='inactive' WHERE expert_name=? AND node_id=?",
                (expertName, nodeId),
            )
            conn.execute(
                "UPDATE gpu_nodes SET vram_used_kb=MAX(0, vram_used_kb-?) WHERE node_id=?",
                (EXPERT_RAM_KB, nodeId),
            )
            conn.execute(
                "INSERT INTO activation_log (expert_name, node_id, action, timestamp) VALUES (?,?,?,?)",
                (expertName, nodeId, "deactivate", time.time()),
            )
            conn.commit()
            return (1, {
                "expert": expertName,
                "node": nodeId,
                "state": "inactive",
                "freed_kb": EXPERT_RAM_KB,
            }, None)
        except Exception as e:
            return (0, None, ("DEACTIVATE_ERROR", str(e), 0))

    def cmdRouteDistributed(self, params):
        """Find which GPU node has the needed expert, activate it, return route."""
        try:
            expertName = self.p(params, "expert_name")
            if not expertName:
                return (0, None, ("PARAMS_ERROR", "expert_name required", 0))
            conn = self.getConn()
            assignments = conn.execute(
                "SELECT node_id, state FROM expert_assignments WHERE expert_name=?",
                (expertName,),
            ).fetchall()
            if not assignments:
                return (0, None, ("EXPERT_UNASSIGNED", expertName + " not assigned to any GPU", 0))
            activeNode = None
            inactiveNode = None
            for nodeId, state in assignments:
                if state == "active":
                    activeNode = nodeId
                    break
                if inactiveNode is None:
                    inactiveNode = nodeId
            if activeNode:
                conn.execute(
                    "UPDATE expert_assignments SET last_active=?, inference_count=inference_count+1 WHERE expert_name=? AND node_id=?",
                    (time.time(), expertName, activeNode),
                )
                conn.commit()
                return (1, {
                    "expert": expertName,
                    "node": activeNode,
                    "state": "HIT",
                    "action": "already_active",
                    "latency": "minimal",
                }, None)
            if inactiveNode:
                ok, actData, actErr = self.cmdActivate({"expert_name": expertName, "node_id": inactiveNode})
                if not ok:
                    return (0, None, actErr)
                return (1, {
                    "expert": expertName,
                    "node": inactiveNode,
                    "state": "MISS",
                    "action": "activated",
                    "ram_kb": EXPERT_RAM_KB,
                    "latency": "load+infer",
                }, None)
            return (0, None, ("NO_AVAILABLE_NODE", "All nodes full", 0))
        except Exception as e:
            return (0, None, ("ROUTE_DIST_ERROR", str(e), 0))

    def cmdStatus(self, params):
        """Get distributed system status — all GPUs, assignments, VRAM."""
        try:
            conn = self.getConn()
            gpus = conn.execute(
                "SELECT node_id, name, vram_total_kb, vram_used_kb, status FROM gpu_nodes ORDER BY node_id"
            ).fetchall()
            gpuList = []
            totalVram = 0
            totalUsed = 0
            totalActive = 0
            totalAssigned = 0
            for row in gpus:
                nodeId, name, vramTotal, vramUsed, status = row
                active = conn.execute(
                    "SELECT COUNT(*) FROM expert_assignments WHERE node_id=? AND state='active'", (nodeId,)
                ).fetchone()[0]
                assigned = conn.execute(
                    "SELECT COUNT(*) FROM expert_assignments WHERE node_id=?", (nodeId,)
                ).fetchone()[0]
                gpuList.append({
                    "node_id": nodeId,
                    "name": name,
                    "vram_total_gb": round(vramTotal / (1024 * 1024), 1),
                    "vram_used_kb": vramUsed,
                    "vram_free_kb": vramTotal - vramUsed,
                    "utilization_pct": round(vramUsed / vramTotal * 100, 1) if vramTotal > 0 else 0,
                    "status": status,
                    "active_experts": active,
                    "assigned_experts": assigned,
                })
                totalVram += vramTotal
                totalUsed += vramUsed
                totalActive += active
                totalAssigned += assigned
            return (1, {
                "gpu_nodes": gpuList,
                "total_gpus": len(gpuList),
                "total_vram_gb": round(totalVram / (1024 * 1024), 1),
                "total_used_kb": totalUsed,
                "total_active_experts": totalActive,
                "total_assigned_experts": totalAssigned,
                "sparse_ratio": str(totalActive) + "/" + str(totalAssigned) + " active",
            }, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def cmdRebalance(self, params):
        """Rebalance experts across GPUs — deactivate all, redistribute."""
        try:
            conn = self.getConn()
            conn.execute("UPDATE expert_assignments SET state='inactive'")
            conn.execute("UPDATE gpu_nodes SET vram_used_kb=0, status='idle'")
            conn.commit()
            models = conn.execute("SELECT name FROM models WHERE active=1").fetchall()
            gpus = conn.execute("SELECT node_id FROM gpu_nodes").fetchall()
            if not gpus:
                return (0, None, ("NO_GPUS", "No GPU nodes registered", 0))
            redistributed = 0
            for i, (name,) in enumerate(models):
                nodeId = gpus[i % len(gpus)][0]
                conn.execute(
                    "INSERT OR REPLACE INTO expert_assignments (expert_name, node_id, state, loaded_at) VALUES (?,?,?,?)",
                    (name[0] if isinstance(name, tuple) else name, nodeId, "inactive", time.time()),
                )
                redistributed += 1
            conn.commit()
            return (1, {
                "redistributed": redistributed,
                "gpu_nodes": len(gpus),
                "all_deactivated": True,
            }, None)
        except Exception as e:
            return (0, None, ("REBALANCE_ERROR", str(e), 0))

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
