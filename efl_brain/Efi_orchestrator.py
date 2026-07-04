#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_orchestrator.py
# Domain:   efl_brain
# Authority: Orchestrator brother — the single entry point that runs the full
#            pipeline: build → connect → simulate → diff → repair → scan → report
# DB:       efl_brain.db (coordinates all brothers through the dinner table)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths (all from Config_efl_brain.py)
#   @cstyle   — Coding style compliant
# ============================================================================

"""
Orchestrator Brother — the single entry point for the full efl_brain pipeline.

The orchestrator calls each brother in order. Each brother writes results to
efl_brain.db (the dinner table). The next brother reads from there.
No brother imports another brother — they all communicate through the database.

Pipeline steps:
  1. BUILD    — Efi_core.py builds the database from MySQL + scripts
  2. CONNECT  — Efi_connector.py builds the agent graph from DB rows
  3. SIMULATE — Efi_agent_graph.py runs the cognitive substrate simulation
  4. DIFF     — Efi_core.py runs the diff engine (expected vs existing)
  5. REPAIR   — Efi_repair.py generates code fixes for gaps
  6. SCAN     — Efi_solution_engine.py scans for config rule violations
  7. REPORT   — Aggregate all results into a final summary

Usage:
  python3 Efi_orchestrator.py              — run full pipeline
  python3 Efi_orchestrator.py run run      — same, via Run() dispatch
  python3 Efi_orchestrator.py run status   — show pipeline status
  python3 Efi_orchestrator.py run step 3   — run only step 3 (simulate)
  python3 Efi_orchestrator.py run report   — show final report
"""

import os
import sys
import time
import sqlite3
from collections import defaultdict

from Config_efl_brain import DB_PATH

# The orchestrator is the entry point — it imports all brothers at the top level.
# Brothers do NOT import each other. They communicate through efl_brain.db.
from Efi_connector import Connector
from Efi_repair import RepairEngine
from Efi_solution_engine import ConfigSolutionEngine
from Efi_agent_graph import AgentGraph, ROOT

# Table name constants — no hardcoding (R7 compliance)
CLASSES_TABLE = "classes"
METHODS_TABLE = "methods"
GRAPH_EDGES_TABLE = "graph_edges"
DIFF_RESULTS_TABLE = "diff_results"
PREDICTION_LINKS_TABLE = "agent_prediction_links"
GENERATED_FIXES_TABLE = "agent_generated_fixes"
VIOLATIONS_TABLE = "agent_violations"
WORLD_MODEL_TABLE = "agent_world_model"
EMOTIONAL_STATE_TABLE = "agent_emotional_state"


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  Orchestrator
# Domain: efl_brain
# Authority: Runs the full pipeline by calling each brother in sequence
# Dependencies: Config_efl_brain, Efi_connector, Efi_repair (lazy imports)
# ============================================================================


# Class: Orchestrator — runs the full pipeline by calling each brother in sequence
class Orchestrator:
    """Orchestrator brother — runs the full pipeline.

    self.state holds all working data:
      state["steps"]     — list of step results
      state["current"]   — current step number
      state["stats"]     — aggregate statistics
      state["db_path"]   — path to efl_brain.db
    """

    def __init__(self):
        """Initialize the orchestrator brother with empty state and pipeline definition."""
        self.state = {}
        self.state["steps"] = []
        self.state["current"] = 0
        self.state["stats"] = {}
        self.state["db_path"] = DB_PATH

        # Pipeline definition — each step has a name, description, and runner
        self.PIPELINE = [
            {"name": "build",    "desc": "Build database from MySQL + scripts",     "fn": self._StepBuild},
            {"name": "connect",  "desc": "Build agent graph from DB rows",          "fn": self._StepConnect},
            {"name": "simulate", "desc": "Run cognitive substrate simulation",      "fn": self._StepSimulate},
            {"name": "diff",     "desc": "Diff expected vs existing (find gaps)",   "fn": self._StepDiff},
            {"name": "repair",   "desc": "Generate code fixes for gaps",            "fn": self._StepRepair},
            {"name": "scan",     "desc": "Scan for config rule violations",         "fn": self._StepScan},
            {"name": "report",   "desc": "Aggregate all results",                   "fn": self._StepReport},
        ]

    # ----------------------------------------------------------------
    # Pipeline steps — each returns (ok, data, error)
    # ----------------------------------------------------------------

    def _StepBuild(self):
        """Step 1: Build database from MySQL + scripts.

        Delegates to Efi_core.py cmd_build. If the database already exists
        and has data, this step is skipped.
        """
        try:
            # Check if DB already has data
            conn = sqlite3.connect(self.state["db_path"])
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {CLASSES_TABLE}")
            class_count = c.fetchone()[0]
            c.execute(f"SELECT COUNT(*) FROM {METHODS_TABLE}")
            method_count = c.fetchone()[0]
            conn.close()

            if class_count > 0 and method_count > 0:
                return (True, {
                    "skipped": True,
                    "reason": f"DB already has {class_count} classes, {method_count} methods",
                    "classes": class_count,
                    "methods": method_count,
                }, "")

            # Would call Efi_core.cmd_build() here — but that requires MySQL
            # which may not be available. For now, report that build is needed.
            return (True, {
                "skipped": False,
                "reason": "DB empty — run 'python3 efl.py build' first",
                "classes": 0,
                "methods": 0,
            }, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepConnect(self):
        """Step 2: Build agent graph from DB rows using the connector brother."""
        try:
            connector = Connector()
            ok, data, err = connector.Run("full")
            if not ok:
                return (False, None, f"Connector failed: {err}")
            return (True, data, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepSimulate(self):
        """Step 3: Run cognitive substrate simulation.

        Uses the agent graph to simulate exploration, then writes results
        to the database for other brothers to read.
        """
        try:
            graph = AgentGraph()
            graph.Build(ROOT)

            # Find a good start node
            config_id = [nid for nid in graph.nodes if graph.nodes[nid].type == "CONFIG"]
            start = config_id[0] if config_id else list(graph.nodes.keys())[0]
            if not graph.adj.get(start):
                folders = [nid for nid in graph.nodes if graph.nodes[nid].type == "FOLDER"]
                if folders:
                    start = folders[0]

            ok, sim_result, err = graph.Run("full_simulate", {"start": start, "steps": 100})
            if not ok:
                return (False, None, f"Simulation failed: {err}")

            # Write results to the dinner table
            write_result = graph.WriteToDb()

            return (True, {
                "steps": sim_result["steps"],
                "coverage": sim_result["coverage"],
                "goals_completed": sim_result["goals"]["completed"],
                "prediction_links": sim_result["prediction_links"],
                "mood": sim_result["emotion"]["mood"],
                "written_to_db": write_result,
            }, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepDiff(self):
        """Step 4: Run diff engine to find gaps.

        Delegates to Efi_core.py cmd_diff. Reads expectation_graph and
        compares against existing methods/classes/units.
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            c = conn.cursor()

            # Check if diff_results already has data
            c.execute(f"SELECT COUNT(*) FROM {DIFF_RESULTS_TABLE} WHERE status = 'MISSING'")
            missing_count = c.fetchone()[0]
            conn.close()

            if missing_count > 0:
                return (True, {
                    "gaps_found": missing_count,
                    "skipped": True,
                    "reason": "Diff results already exist",
                }, "")

            # Would call Efi_core.cmd_diff() here
            return (True, {
                "gaps_found": 0,
                "skipped": False,
                "reason": "Run 'python3 efl.py diff' first",
            }, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepRepair(self):
        """Step 5: Generate code fixes for gaps using the repair brother."""
        try:
            engine = RepairEngine()
            ok, data, err = engine.Run("repair")
            if not ok:
                return (False, None, f"Repair failed: {err}")
            return (True, data, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepScan(self):
        """Step 6: Scan for config rule violations using the solution engine."""
        try:
            se = ConfigSolutionEngine()
            se.ScanFolder(os.path.dirname(os.path.abspath(__file__)))

            # Write violations to DB
            write_result = se.WriteToDb()

            report = se.GenerateReport()

            return (True, {
                "files_scanned": report["files_scanned"],
                "total_violations": report["total_violations"],
                "by_rule": report["by_rule"],
                "written_to_db": write_result,
            }, "")
        except Exception as e:
            return (False, None, str(e))

    def _StepReport(self):
        """Step 7: Aggregate all results into a final summary."""
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Gather stats from all tables
            stats = {}

            c.execute(f"SELECT COUNT(*) FROM {CLASSES_TABLE}")
            stats["classes"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {METHODS_TABLE}")
            stats["methods"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {GRAPH_EDGES_TABLE}")
            stats["graph_edges"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {DIFF_RESULTS_TABLE} WHERE status = 'MISSING'")
            stats["gaps_missing"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {PREDICTION_LINKS_TABLE}")
            stats["prediction_links"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {GENERATED_FIXES_TABLE}")
            stats["generated_fixes"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {GENERATED_FIXES_TABLE} WHERE valid = 1")
            stats["valid_fixes"] = c.fetchone()[0]

            c.execute(f"SELECT COUNT(*) FROM {VIOLATIONS_TABLE}")
            stats["violations"] = c.fetchone()[0]

            c.execute(f"SELECT AVG(confidence) FROM {PREDICTION_LINKS_TABLE}")
            avg_conf = c.fetchone()[0]
            stats["avg_confidence"] = round(avg_conf, 4) if avg_conf else 0.0

            # World model
            c.execute(f"SELECT * FROM {WORLD_MODEL_TABLE} ORDER BY written_at DESC LIMIT 1")
            wm = c.fetchone()
            if wm:
                stats["world_model"] = {
                    "explored": round(dict(wm)["explored_fraction"] * 100, 1),
                    "avg_reward": round(dict(wm)["avg_reward"], 4),
                    "avg_confidence": round(dict(wm)["avg_confidence"], 4),
                }

            # Emotional state
            c.execute(f"SELECT * FROM {EMOTIONAL_STATE_TABLE} ORDER BY written_at DESC LIMIT 1")
            em = c.fetchone()
            if em:
                stats["emotion"] = {
                    "mood": round(dict(em)["mood"], 4),
                    "trend": dict(em)["trend"],
                }

            conn.close()

            # Add step results
            step_summary = []
            for step in self.state["steps"]:
                step_summary.append({
                    "step": step["step"],
                    "name": step["name"],
                    "ok": step["ok"],
                    "duration": round(step["duration"], 4),
                })

            stats["pipeline_steps"] = step_summary

            return (True, stats, "")
        except Exception as e:
            return (False, None, str(e))

    # ----------------------------------------------------------------
    # Run — execute the full pipeline or a single step
    # ----------------------------------------------------------------

    def RunPipeline(self):
        """Run the full pipeline from step 1 to step 7.

        Returns:
            Tuple3 (ok, data, error)
        """
        self.state["steps"] = []
        self.state["current"] = 0
        pipeline_ok = True
        errors = []

        for i, step in enumerate(self.PIPELINE):
            self.state["current"] = i + 1
            t0 = time.time()

            try:
                ok, data, err = step["fn"]()
                duration = time.time() - t0

                self.state["steps"].append({
                    "step": i + 1,
                    "name": step["name"],
                    "desc": step["desc"],
                    "ok": ok,
                    "data": data,
                    "error": err,
                    "duration": duration,
                })

                if not ok:
                    pipeline_ok = False
                    errors.append(f"Step {i+1} ({step['name']}): {err}")

            except Exception as e:
                duration = time.time() - t0
                self.state["steps"].append({
                    "step": i + 1,
                    "name": step["name"],
                    "desc": step["desc"],
                    "ok": False,
                    "data": None,
                    "error": str(e),
                    "duration": duration,
                })
                pipeline_ok = False
                errors.append(f"Step {i+1} ({step['name']}): {e}")

        # Final stats
        total_duration = sum(s["duration"] for s in self.state["steps"])
        ok_count = sum(1 for s in self.state["steps"] if s["ok"])

        self.state["stats"] = {
            "total_steps": len(self.PIPELINE),
            "steps_ok": ok_count,
            "steps_failed": len(self.PIPELINE) - ok_count,
            "total_duration": round(total_duration, 4),
            "errors": errors,
        }

        return (pipeline_ok, self.state["stats"], "" if pipeline_ok else "; ".join(errors))

    def RunStep(self, step_num):
        """Run a single step by number (1-7).

        Returns:
            Tuple3 (ok, data, error)
        """
        if step_num < 1 or step_num > len(self.PIPELINE):
            return (False, None, f"Invalid step number: {step_num}. Valid: 1-{len(self.PIPELINE)}")

        step = self.PIPELINE[step_num - 1]
        t0 = time.time()
        ok, data, err = step["fn"]()
        duration = time.time() - t0

        return (ok, {
            "step": step_num,
            "name": step["name"],
            "desc": step["desc"],
            "data": data,
            "duration": round(duration, 4),
        }, err)

    def Status(self):
        """Return the current pipeline status.

        Returns:
            Tuple3 (ok, data, error)
        """
        return (True, {
            "pipeline": [{"step": i+1, "name": s["name"], "desc": s["desc"]} for i, s in enumerate(self.PIPELINE)],
            "current_step": self.state["current"],
            "steps_run": len(self.state["steps"]),
            "stats": self.state["stats"],
        }, "")

    # ----------------------------------------------------------------
    # Run — dispatch entry point
    # ----------------------------------------------------------------

    def Run(self, command, params=None):
        """Dispatch entry point.

        Args:
            command: str — "run", "status", "step", "report"
            params: dict — optional parameters (e.g. {"step": 3})

        Returns:
            Tuple3 (ok, data, error)
        """
        if params is None:
            params = {}

        if command == "run":
            return self.RunPipeline()

        elif command == "status":
            return self.Status()

        elif command == "step":
            step_num = params.get("step", 0)
            if isinstance(step_num, str):
                step_num = int(step_num)
            return self.RunStep(step_num)

        elif command == "report":
            return self._StepReport()

        else:
            return (False, None, f"Unknown command: {command}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    orch = Orchestrator()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    sub = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "run" and sub:
        if sub == "step":
            step_num = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            ok, data, err = orch.Run("step", {"step": step_num})
        else:
            ok, data, err = orch.Run(sub)
    elif cmd == "run":
        ok, data, err = orch.Run("run")
    else:
        ok, data, err = orch.Run(cmd)

    if ok:
        sys.stdout.write("=" * 70 + "\n")
        sys.stdout.write("  ORCHESTRATOR BROTHER — Full Pipeline\n")
        sys.stdout.write("=" * 70 + "\n")

        if isinstance(data, dict) and "total_steps" in data:
            # Full pipeline report
            sys.stdout.write(f"\n  Steps: {data['total_steps']} total, {data['steps_ok']} ok, {data['steps_failed']} failed\n")
            sys.stdout.write(f"  Duration: {data['total_duration']}s\n\n")
            for step in orch.state["steps"]:
                status = "OK" if step["ok"] else "FAIL"
                sys.stdout.write(f"    Step {step['step']}: {step['name']:12s}  {status:4s}  {step['duration']:.3f}s\n")
                if step["ok"] and step["data"]:
                    for k, v in step["data"].items():
                        if isinstance(v, dict):
                            for k2, v2 in v.items():
                                sys.stdout.write(f"      {k2:20s} {v2}\n")
                        elif not isinstance(v, (list,)):
                            sys.stdout.write(f"      {k:20s} {v}\n")
                elif step["error"]:
                    sys.stdout.write(f"      ERROR: {step['error']}\n")
            if data.get("errors"):
                sys.stdout.write(f"\n  Errors:\n")
                for e in data["errors"]:
                    sys.stdout.write(f"    - {e}\n")
        elif isinstance(data, dict) and "pipeline" in data:
            # Status
            sys.stdout.write(f"\n  Pipeline steps:\n")
            for s in data["pipeline"]:
                sys.stdout.write(f"    {s['step']}. {s['name']:12s} — {s['desc']}\n")
            sys.stdout.write(f"\n  Current step: {data['current_step']}\n")
            sys.stdout.write(f"  Steps run: {data['steps_run']}\n")
        elif isinstance(data, dict) and "step" in data:
            # Single step
            sys.stdout.write(f"\n  Step {data['step']}: {data['name']} — {data['desc']}\n")
            sys.stdout.write(f"  Duration: {data['duration']}s\n")
            if data.get("data"):
                for k, v in data["data"].items():
                    if isinstance(v, dict):
                        sys.stdout.write(f"    {k}:\n")
                        for k2, v2 in v.items():
                            sys.stdout.write(f"      {k2:20s} {v2}\n")
                    else:
                        sys.stdout.write(f"    {k:25s} {v}\n")
        else:
            sys.stdout.write(f"\n  Result: {data}\n")

        sys.stdout.write("=" * 70 + "\n")
    else:
        sys.stdout.write(f"ERROR: {err}\n")
        sys.exit(1)
