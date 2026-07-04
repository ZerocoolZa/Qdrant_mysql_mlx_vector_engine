#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_agent_brain.py
# Domain:   efl_brain
# Authority: Learning layer — turns the agent graph into a central nervous system
# DB:       None (pure computation, no LLM)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Builds on Efi_agent_graph.py to add:
#   Temporal Memory    — track graph changes over time
#   Reward Scores      — edges strengthen/weaken from outcomes
#   Prediction Links   — nodes predict, compare to reality, update confidence
#   Attention Weights  — focus exploration on important nodes
#   Execution History  — log of all runs and their outcomes
#   Self-Modifying Paths — edges that adapt based on success/failure
#   World Model        — internal representation built from observations
#   Goal System        — objectives that create hunger and drive behavior
#
# The graph becomes the central nervous system that all learning flows through.
# ============================================================================

"""
Agent Brain — learning layer on top of Agent Graph.

Survival Loop:
  Observe → Predict → Act → Measure → Store Experience → Update State → Repeat

Each node is a tiny living agent:
  Sensors:  taste, touch, vision, smell, pain, hunger
  Drives:   curiosity, fear, confidence, reward, success, failure
  Memory:   experiences, visits, predictions, attention
  Survival: health, age, generation, alive

Edges are self-modifying:
  weight    — strengthens on success, weakens on failure
  reward    — accumulated reward flowing through this edge
  trials    — how many times this edge was traversed
  success_rate — rolling success percentage

The brain adds:
  TemporalMemory  — snapshots of graph state over time
  GoalSystem      — goals that create hunger and drive exploration
  WorldModel      — internal map of what the system looks like
  ExecutionHistory— log of all simulations and their outcomes
  AttentionSystem — focuses exploration on high-value nodes
"""

import os
import sys
import json
import time
import random
import math
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Config_efl_brain as Config
from Efi_agent_graph import AgentNode, Edge, AgentGraph

ROOT = Config.BASE_DIR


# ============================================================================
# TEMPORAL MEMORY — track graph changes over time
# ============================================================================

class TemporalMemory:
    """Stores snapshots of graph state at different time points."""

    def __init__(self):
        self.state = {}
        self.state["snapshots"] = []
        self.state["max_snapshots"] = 100
        self.state["changes_detected"] = 0

    def Snapshot(self, graph):
        """Take a snapshot of the current graph state."""
        node_summary = {}
        for nid, node in graph.nodes.items():
            node_summary[nid] = {
                "type": node.type,
                "health": round(node.survival["health"], 4),
                "fear": round(node.drives["fear"], 4),
                "confidence": round(node.drives["confidence"], 4),
                "reward": round(node.drives["reward"], 4),
                "visits": node.memory["visits"],
                "alive": node.survival["alive"],
            }

        edge_summary = []
        for edge in graph.edges:
            edge_summary.append({
                "src": edge.src,
                "dst": edge.dst,
                "type": edge.type,
                "weight": round(edge.__dict__.get("weight", 1.0), 4),
            })

        snapshot = {
            "time": time.time(),
            "timestamp": len(self.state["snapshots"]),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "nodes": node_summary,
            "edges": edge_summary,
        }

        # Detect changes from last snapshot
        if self.state["snapshots"]:
            last = self.state["snapshots"][-1]
            changes = self._DiffSnapshots(last, snapshot)
            snapshot["changes"] = changes
            if changes["total_changes"] > 0:
                self.state["changes_detected"] += 1
        else:
            snapshot["changes"] = {"total_changes": 0}

        self.state["snapshots"].append(snapshot)
        if len(self.state["snapshots"]) > self.state["max_snapshots"]:
            self.state["snapshots"] = self.state["snapshots"][-self.state["max_snapshots"]:]

        return snapshot

    def _DiffSnapshots(self, old, new):
        """Compare two snapshots and report changes."""
        changes = {
            "nodes_added": [],
            "nodes_removed": [],
            "state_changes": [],
            "total_changes": 0,
        }

        old_nodes = set(old["nodes"].keys())
        new_nodes = set(new["nodes"].keys())

        changes["nodes_added"] = list(new_nodes - old_nodes)
        changes["nodes_removed"] = list(old_nodes - new_nodes)

        for nid in old_nodes & new_nodes:
            old_n = old["nodes"][nid]
            new_n = new["nodes"][nid]
            for key in ("health", "fear", "confidence", "reward", "visits", "alive"):
                if old_n.get(key) != new_n.get(key):
                    changes["state_changes"].append({
                        "node": nid,
                        "field": key,
                        "old": old_n.get(key),
                        "new": new_n.get(key),
                    })

        changes["total_changes"] = (
            len(changes["nodes_added"]) +
            len(changes["nodes_removed"]) +
            len(changes["state_changes"])
        )
        return changes

    def GetHistory(self, node_id=None, field=None):
        """Get temporal history for a specific node/field."""
        history = []
        for snap in self.state["snapshots"]:
            if node_id and node_id in snap["nodes"]:
                val = snap["nodes"][node_id]
                if field:
                    history.append({"time": snap["time"], "value": val.get(field)})
                else:
                    history.append({"time": snap["time"], "state": val})
        return history

    def ToDict(self):
        return {
            "snapshot_count": len(self.state["snapshots"]),
            "changes_detected": self.state["changes_detected"],
            "max_snapshots": self.state["max_snapshots"],
        }


# ============================================================================
# GOAL SYSTEM — objectives that create hunger and drive behavior
# ============================================================================

class GoalSystem:
    """Manages goals that create hunger and drive agent exploration."""

    def __init__(self):
        self.state = {}
        self.state["goals"] = []
        self.state["active_goal"] = None
        self.state["completed_goals"] = []
        self.state["failed_goals"] = []

    def AddGoal(self, goal_id, description, target_type=None, target_node=None,
                reward=1.0, priority=1.0):
        """Add a new goal."""
        goal = {
            "id": goal_id,
            "description": description,
            "target_type": target_type,
            "target_node": target_node,
            "reward": reward,
            "priority": priority,
            "status": "pending",
            "created": time.time(),
            "attempts": 0,
            "completed": False,
        }
        self.state["goals"].append(goal)
        self.state["goals"].sort(key=lambda g: g["priority"], reverse=True)

    def GetActiveGoal(self):
        """Get the highest-priority pending goal."""
        for goal in self.state["goals"]:
            if goal["status"] == "pending":
                self.state["active_goal"] = goal["id"]
                return goal
        return None

    def CompleteGoal(self, goal_id, success=True):
        """Mark a goal as complete or failed."""
        for goal in self.state["goals"]:
            if goal["id"] == goal_id:
                goal["status"] = "completed" if success else "failed"
                goal["completed"] = success
                goal["attempts"] += 1
                if success:
                    self.state["completed_goals"].append(goal)
                else:
                    self.state["failed_goals"].append(goal)
                self.state["active_goal"] = None
                return True
        return False

    def ApplyHunger(self, graph):
        """Apply hunger to nodes based on active goals."""
        goal = self.GetActiveGoal()
        if not goal:
            return

        for node in graph.nodes.values():
            if goal["target_type"] and node.type == goal["target_type"]:
                node.sensors["hunger"] = min(1.0, node.sensors["hunger"] + 0.3)
                node.drives["curiosity"] = min(1.0, node.drives["curiosity"] + 0.2)
            if goal["target_node"] and node.id == goal["target_node"]:
                node.sensors["hunger"] = 1.0
                node.drives["curiosity"] = 1.0
                node.sensors["smell"] = 1.0

    def ToDict(self):
        return {
            "goal_count": len(self.state["goals"]),
            "active_goal": self.state["active_goal"],
            "completed": len(self.state["completed_goals"]),
            "failed": len(self.state["failed_goals"]),
            "goals": [{"id": g["id"], "status": g["status"], "priority": g["priority"],
                        "description": g["description"]} for g in self.state["goals"]],
        }


# ============================================================================
# WORLD MODEL — internal representation of the system
# ============================================================================

class WorldModel:
    """Builds an internal model of the system from observations."""

    def __init__(self):
        self.state = {}
        self.state["model"] = {}
        self.state["confidence"] = {}
        self.state["predictions_made"] = 0
        self.state["predictions_correct"] = 0
        self.state["predictions_wrong"] = 0

    def Observe(self, graph):
        """Update the world model from current graph state."""
        model = {}
        for nid, node in graph.nodes.items():
            model[nid] = {
                "type": node.type,
                "health": round(node.survival["health"], 4),
                "fear": round(node.drives["fear"], 4),
                "confidence": round(node.drives["confidence"], 4),
                "reward": round(node.drives["reward"], 4),
                "success_rate": round(
                    node.drives["success"] / max(1, node.drives["success"] + node.drives["failure"]), 4
                ),
                "visits": node.memory["visits"],
                "alive": node.survival["alive"],
            }
        self.state["model"] = model

    def Predict(self, node_id, field, steps_ahead=1):
        """Predict a node's future state based on trends."""
        if node_id not in self.state["model"]:
            return None

        current = self.state["model"][node_id]
        self.state["predictions_made"] += 1

        # Simple trend prediction
        if field == "health":
            success_rate = current.get("success_rate", 0.5)
            prediction = min(1.0, max(0.0, success_rate * 0.7 + 0.3))
        elif field == "fear":
            prediction = max(0.0, min(1.0, current.get("fear", 0) * 0.9))
        elif field == "confidence":
            prediction = max(0.0, min(1.0, current.get("confidence", 0.5) * 1.02))
        elif field == "reward":
            prediction = max(0.0, min(1.0, current.get("reward", 0) + 0.05))
        else:
            prediction = current.get(field)

        return prediction

    def ComparePrediction(self, node_id, field, predicted, actual):
        """Compare a prediction to reality and update confidence."""
        self.state["predictions_made"] += 1
        if predicted is not None and actual is not None:
            diff = abs(predicted - actual)
            if diff < 0.15:
                self.state["predictions_correct"] += 1
                return True
            else:
                self.state["predictions_wrong"] += 1
                return False
        return None

    def GetAccuracy(self):
        total = self.state["predictions_correct"] + self.state["predictions_wrong"]
        if total == 0:
            return 0.0
        return self.state["predictions_correct"] / total

    def ToDict(self):
        return {
            "model_size": len(self.state["model"]),
            "predictions_made": self.state["predictions_made"],
            "predictions_correct": self.state["predictions_correct"],
            "predictions_wrong": self.state["predictions_wrong"],
            "accuracy": round(self.GetAccuracy(), 4),
        }


# ============================================================================
# EXECUTION HISTORY — log of all simulations and outcomes
# ============================================================================

class ExecutionHistory:
    """Logs every simulation run and its outcome."""

    def __init__(self):
        self.state = {}
        self.state["runs"] = []
        self.state["max_runs"] = 200

    def LogRun(self, run_id, start_node, steps, path, outcomes):
        """Log a simulation run."""
        entry = {
            "run_id": run_id,
            "start": start_node,
            "steps": steps,
            "path_length": len(path),
            "successes": sum(1 for o in outcomes if o.get("success")),
            "failures": sum(1 for o in outcomes if not o.get("success")),
            "reward_total": sum(o.get("reward", 0) for o in outcomes),
            "pain_total": sum(o.get("pain", 0) for o in outcomes),
            "timestamp": time.time(),
        }
        self.state["runs"].append(entry)
        if len(self.state["runs"]) > self.state["max_runs"]:
            self.state["runs"] = self.state["runs"][-self.state["max_runs"]:]

    def GetStats(self):
        """Get aggregate statistics across all runs."""
        if not self.state["runs"]:
            return {"total_runs": 0}
        total = len(self.state["runs"])
        total_success = sum(r["successes"] for r in self.state["runs"])
        total_failure = sum(r["failures"] for r in self.state["runs"])
        total_reward = sum(r["reward_total"] for r in self.state["runs"])
        total_pain = sum(r["pain_total"] for r in self.state["runs"])
        avg_steps = sum(r["steps"] for r in self.state["runs"]) / total
        return {
            "total_runs": total,
            "total_successes": total_success,
            "total_failures": total_failure,
            "success_rate": round(total_success / max(1, total_success + total_failure), 4),
            "total_reward": round(total_reward, 4),
            "total_pain": round(total_pain, 4),
            "avg_steps": round(avg_steps, 2),
        }

    def ToDict(self):
        stats = self.GetStats()
        stats["run_count"] = len(self.state["runs"])
        return stats


# ============================================================================
# ATTENTION SYSTEM — focus exploration on high-value nodes
# ============================================================================

class AttentionSystem:
    """Manages attention weights across nodes."""

    def __init__(self):
        self.state = {}
        self.state["attention"] = {}
        self.state["focus_node"] = None
        self.state["attention_decay"] = 0.95

    def UpdateAttention(self, graph):
        """Update attention weights based on node states."""
        for nid, node in graph.nodes.items():
            current = self.state["attention"].get(nid, 0.5)

            # Attention factors
            curiosity = node.drives["curiosity"]
            reward = node.drives["reward"]
            pain = node.sensors["pain"]
            health = node.survival["health"]
            visits = node.memory["visits"]

            # Novelty bonus — unvisited nodes get attention boost
            novelty = 1.0 / (1.0 + visits * 0.1)

            # Attention = curiosity + reward + novelty - pain - visited_penalty
            new_attention = (
                curiosity * 0.3 +
                reward * 0.2 +
                novelty * 0.2 +
                health * 0.1 -
                pain * 0.2
            )
            new_attention = max(0.0, min(1.0, new_attention))

            # Apply decay + new value
            self.state["attention"][nid] = (
                current * self.state["attention_decay"] +
                new_attention * (1 - self.state["attention_decay"])
            )

    def GetFocus(self):
        """Get the node with highest attention."""
        if not self.state["attention"]:
            return None
        focus = max(self.state["attention"].items(), key=lambda x: x[1])
        self.state["focus_node"] = focus[0]
        return focus

    def GetTopNodes(self, n=10):
        """Get top N nodes by attention."""
        sorted_nodes = sorted(self.state["attention"].items(),
                              key=lambda x: x[1], reverse=True)
        return sorted_nodes[:n]

    def ToDict(self):
        return {
            "tracked_nodes": len(self.state["attention"]),
            "focus_node": self.state["focus_node"],
            "top_5": self.GetTopNodes(5),
        }


# ============================================================================
# AGENT BRAIN — full learning system
# ============================================================================

class AgentBrain:
    """Central nervous system — all learning flows through the graph."""

    def __init__(self, root):
        self.state = {}
        self.state["root"] = root
        self.state["generation"] = 1
        self.state["total_simulations"] = 0

        # Core graph
        self.graph = AgentGraph()

        # Learning systems
        self.temporal = TemporalMemory()
        self.goals = GoalSystem()
        self.world = WorldModel()
        self.history = ExecutionHistory()
        self.attention = AttentionSystem()

        # Edge weights for self-modifying paths
        self.edge_weights = {}
        self.edge_trials = defaultdict(int)
        self.edge_successes = defaultdict(int)

    # ------------------------------------------------------------------------
    # Build the brain
    # ------------------------------------------------------------------------

    def Build(self):
        """Build the graph and initialize all systems."""
        self.graph.Build(self.state["root"])

        # Initialize edge weights
        for edge in self.graph.edges:
            key = (edge.src, edge.dst, edge.type)
            self.edge_weights[key] = 1.0
            self.edge_trials[key] = 0
            self.edge_successes[key] = 0

        # Take initial snapshot
        self.temporal.Snapshot(self.graph)
        self.world.Observe(self.graph)
        self.attention.UpdateAttention(self.graph)

        # Set default goals
        self.goals.AddGoal("find_config", "Find the CONFIG node",
                           target_type="CONFIG", reward=1.0, priority=1.0)
        self.goals.AddGoal("find_memunits", "Find all MEMUNIT nodes",
                           target_type="MEMUNIT", reward=0.8, priority=0.8)
        self.goals.AddGoal("find_hubs", "Find the most connected nodes",
                           reward=0.5, priority=0.5)
        self.goals.AddGoal("map_communities", "Discover subsystem clusters",
                           reward=0.6, priority=0.6)

        # Apply hunger from goals
        self.goals.ApplyHunger(self.graph)

    # ------------------------------------------------------------------------
    # Full survival loop simulation
    # ------------------------------------------------------------------------

    def Simulate(self, start_id=None, steps=100):
        """Run a full survival loop: Observe → Predict → Act → Measure → Store."""
        if start_id is None:
            # Start from FOLDER node — it has CONTAINS edges to everything
            folder_nodes = [nid for nid in self.graph.nodes if self.graph.nodes[nid].type == "FOLDER"]
            if folder_nodes:
                start_id = folder_nodes[0]
            else:
                config_nodes = [nid for nid in self.graph.nodes if self.graph.nodes[nid].type == "CONFIG"]
                start_id = config_nodes[0] if config_nodes else list(self.graph.nodes.keys())[0]

        if start_id not in self.graph.nodes:
            return {"error": "Start node not found"}

        run_id = f"run_{self.state['total_simulations']}"
        self.state["total_simulations"] += 1

        path = []
        outcomes = []
        current_id = start_id
        visited_count = defaultdict(int)
        predictions_log = []

        for step in range(steps):
            node = self.graph.nodes[current_id]

            # --- OBSERVE ---
            node.Observe("touch", 1.0)
            node.sensors["hunger"] = max(0.0, node.sensors["hunger"] - 0.05)
            self.attention.UpdateAttention(self.graph)

            # --- PREDICT ---
            prediction = node.Predict()
            predicted_health = self.world.Predict(current_id, "health")
            predicted_fear = self.world.Predict(current_id, "fear")
            predictions_log.append({
                "node": current_id,
                "prediction": round(prediction, 4),
                "predicted_health": round(predicted_health, 4) if predicted_health else None,
                "predicted_fear": round(predicted_fear, 4) if predicted_fear else None,
            })

            # --- ACT ---
            neighbors = self.graph.adj.get(current_id, [])
            reverse_neighbors = self.graph.radj.get(current_id, [])
            all_neighbors = list(set(neighbors + reverse_neighbors))

            if not all_neighbors:
                node.Measure(False, pain_value=0.1)
                outcomes.append({"success": False, "reward": 0, "pain": 0.1, "reason": "dead_end"})
                break

            # If stuck in a loop (visited > 3 times), backtrack to folder
            if visited_count[current_id] > 2:
                folder_nodes = [nid for nid in self.graph.nodes if self.graph.nodes[nid].type == "FOLDER"]
                if folder_nodes and folder_nodes[0] != current_id:
                    node.drives["fear"] = min(1.0, node.drives["fear"] + 0.1)
                    current_id = folder_nodes[0]
                    continue

            # Score neighbors using attention + edge weights
            scored = []
            for nid in all_neighbors:
                if nid not in self.graph.nodes:
                    continue
                nnode = self.graph.nodes[nid]
                attention_score = self.attention.state["attention"].get(nid, 0.5)

                # Find best edge weight across all edge types
                best_weight = 1.0
                for etype in ("IMPORTS", "CALLS", "CONTAINS", "DEFINES"):
                    ekey = (current_id, nid, etype)
                    rev_ekey = (nid, current_id, etype)
                    if ekey in self.edge_weights:
                        best_weight = max(best_weight, self.edge_weights[ekey])
                    if rev_ekey in self.edge_weights:
                        best_weight = max(best_weight, self.edge_weights[rev_ekey])

                score = (
                    attention_score * 0.4 +
                    nnode.drives["curiosity"] * 0.2 +
                    best_weight * 0.2 +
                    nnode.sensors["smell"] * 0.1 -
                    nnode.drives["fear"] * 0.1
                )
                scored.append((score, nid))

            scored.sort(reverse=True, key=lambda x: x[0])

            # Exploration vs exploitation
            if random.random() < node.drives["curiosity"] * 0.15 and len(scored) > 1:
                next_id = scored[random.randint(0, min(2, len(scored) - 1))][1]
            else:
                next_id = scored[0][1] if scored else None

            if next_id is None:
                node.Measure(False)
                outcomes.append({"success": False, "reward": 0, "pain": 0.05, "reason": "no_target"})
                break

            # --- MEASURE ---
            target = self.graph.nodes[next_id]
            success = target.type in ("CONFIG", "MEMUNIT") or target.drives["curiosity"] > 0.6
            reward_val = 0.1 if success else 0.0
            pain_val = 0.05 if not success else 0.0

            node.Measure(success, reward_value=reward_val, pain_value=pain_val)
            target.Observe("touch", 0.5)
            if success:
                target.Observe("taste", 0.3)
                target.sensors["smell"] = min(1.0, target.sensors["smell"] + 0.1)
            else:
                target.Observe("pain", 0.05)

            # --- SELF-MODIFYING PATHS ---
            # Strengthen/weaken edges based on outcome
            for etype in ("IMPORTS", "CALLS", "CONTAINS", "DEFINES"):
                ekey = (current_id, next_id, etype)
                rev_ekey = (next_id, current_id, etype)
                for key in (ekey, rev_ekey):
                    if key in self.edge_weights:
                        self.edge_trials[key] += 1
                        if success:
                            self.edge_successes[key] += 1
                            self.edge_weights[key] = min(2.0, self.edge_weights[key] + 0.05)
                        else:
                            self.edge_weights[key] = max(0.1, self.edge_weights[key] - 0.03)

            # --- STORE EXPERIENCE ---
            path.append({
                "step": step,
                "node": current_id,
                "name": current_id.split("::")[-1] if "::" in current_id else os.path.basename(current_id),
                "type": node.type,
                "prediction": round(prediction, 4),
                "fear": round(node.drives["fear"], 4),
                "confidence": round(node.drives["confidence"], 4),
                "curiosity": round(node.drives["curiosity"], 4),
                "reward": round(node.drives["reward"], 4),
                "health": round(node.survival["health"], 4),
                "next": next_id.split("::")[-1] if "::" in next_id else os.path.basename(next_id),
                "success": success,
            })

            outcomes.append({"success": success, "reward": reward_val, "pain": pain_val})

            # --- UPDATE STATE ---
            node.UpdateSurvival()
            target.UpdateSurvival()
            visited_count[current_id] += 1

            # Fear from revisiting
            if visited_count[current_id] > 3:
                node.drives["fear"] = min(1.0, node.drives["fear"] + 0.2)

            # Check goals
            active_goal = self.goals.GetActiveGoal()
            if active_goal:
                if active_goal.get("target_type") == target.type:
                    self.goals.CompleteGoal(active_goal["id"], success=True)
                elif active_goal.get("target_node") == next_id:
                    self.goals.CompleteGoal(active_goal["id"], success=True)

            current_id = next_id

        # --- POST-SIMULATION ---
        # Update world model
        self.world.Observe(self.graph)

        # Compare predictions to reality
        for plog in predictions_log[:20]:
            nid = plog["node"]
            if nid in self.graph.nodes:
                actual_health = self.graph.nodes[nid].survival["health"]
                actual_fear = self.graph.nodes[nid].drives["fear"]
                if plog["predicted_health"] is not None:
                    self.world.ComparePrediction(nid, "health", plog["predicted_health"], actual_health)
                if plog["predicted_fear"] is not None:
                    self.world.ComparePrediction(nid, "fear", plog["predicted_fear"], actual_fear)

        # Log to execution history
        self.history.LogRun(run_id, start_id, len(path), path, outcomes)

        # Take temporal snapshot
        self.temporal.Snapshot(self.graph)

        # Apply goal hunger for next run
        self.goals.ApplyHunger(self.graph)

        return {
            "run_id": run_id,
            "start": start_id,
            "steps": len(path),
            "path": path,
            "outcomes": outcomes,
            "predictions": predictions_log,
        }

    # ------------------------------------------------------------------------
    # Run multiple simulations (generations)
    # ------------------------------------------------------------------------

    def Evolve(self, generations=10, steps_per_gen=50):
        """Run multiple generations of simulation."""
        results = []
        for gen in range(generations):
            self.state["generation"] = gen + 1
            result = self.Simulate(steps=steps_per_gen)
            results.append({
                "generation": gen + 1,
                "steps": result["steps"],
                "successes": sum(1 for o in result["outcomes"] if o.get("success")),
                "failures": sum(1 for o in result["outcomes"] if not o.get("success")),
            })
        return results

    # ------------------------------------------------------------------------
    # Query the brain
    # ------------------------------------------------------------------------

    def WhatBreaksIfThisDies(self, node_id):
        """Blast radius — what depends on this node?"""
        return self.graph.BlastRadius(node_id)

    def WhatReachesThis(self, node_id):
        """What can reach this node?"""
        return self.graph.WhatReachesThis(node_id)

    def ShortestPath(self, src, dst):
        """Shortest path A → B."""
        return self.graph.ShortestPath(src, dst)

    def RealBootSequence(self):
        """Discover the real boot order from imports."""
        return self.graph.BootSequence()

    def Communities(self):
        """Find subsystem clusters."""
        return self.graph.DetectCommunities()

    def Centrality(self):
        """Most connected nodes."""
        return self.graph.Centrality()

    def Influence(self):
        """Which node affects the most others?"""
        return self.graph.InfluenceRanking()

    def Cycles(self):
        """Detect circular dependencies."""
        return self.graph.DetectCycles()

    def AttentionReport(self):
        """What the brain is focusing on."""
        return self.attention.GetTopNodes(10)

    def PredictionAccuracy(self):
        """How good are the brain's predictions?"""
        return self.world.GetAccuracy()

    def GoalStatus(self):
        """What goals are active, completed, failed?"""
        return self.goals.ToDict()

    def TemporalChanges(self):
        """What changed over time?"""
        return self.temporal.state["changes_detected"]

    def ExecutionStats(self):
        """Aggregate execution history."""
        return self.history.GetStats()

    # ------------------------------------------------------------------------
    # Full export
    # ------------------------------------------------------------------------

    def Export(self):
        return {
            "brain": {
                "generation": self.state["generation"],
                "total_simulations": self.state["total_simulations"],
                "root": self.state["root"],
            },
            "graph": {
                "nodes": len(self.graph.nodes),
                "edges": len(self.graph.edges),
                "node_types": self.graph._TypeCounts(),
            },
            "temporal": self.temporal.ToDict(),
            "goals": self.goals.ToDict(),
            "world_model": self.world.ToDict(),
            "execution_history": self.history.ToDict(),
            "attention": self.attention.ToDict(),
            "edge_weights": {
                f"{k[0]}::{k[1]}::{k[2]}": {
                    "weight": round(w, 4),
                    "trials": self.edge_trials.get(k, 0),
                    "successes": self.edge_successes.get(k, 0),
                    "success_rate": round(
                        self.edge_successes.get(k, 0) / max(1, self.edge_trials.get(k, 0)), 4
                    ),
                }
                for k, w in self.edge_weights.items()
                if self.edge_trials.get(k, 0) > 0
            },
            "derived": {
                "cycles": self.graph.DetectCycles(),
                "boot_sequence": self.graph.BootSequence(),
                "communities": self.graph.DetectCommunities(),
                "centrality_top10": self.graph.Centrality()[:10],
                "influence_top10": self.graph.InfluenceRanking()[:10],
            },
        }

    # ------------------------------------------------------------------------
    # Run — dispatch entry
    # ------------------------------------------------------------------------

    def Run(self, command, params):
        """Dispatch entry — returns Tuple3."""
        DISPATCH = {
            "simulate": self.RunSimulate,
            "evolve": self.RunEvolve,
            "blast": self.RunBlast,
            "reaches": self.RunReaches,
            "path": self.RunPath,
            "boot": self.RunBoot,
            "communities": self.RunCommunities,
            "central": self.RunCentral,
            "influence": self.RunInfluence,
            "cycles": self.RunCycles,
            "attention": self.RunAttention,
            "accuracy": self.RunAccuracy,
            "goals": self.RunGoals,
            "export": self.RunExport,
        }
        handler = DISPATCH.get(command)
        if handler is None:
            return (False, None, f"Unknown command: {command}")
        return handler(params)

    def RunSimulate(self, params):
        steps = params.get("steps", 50) if params else 50
        start = params.get("start") if params else None
        result = self.Simulate(start, steps)
        return (True, result, "")

    def RunEvolve(self, params):
        gens = params.get("generations", 10) if params else 10
        steps = params.get("steps", 50) if params else 50
        results = self.Evolve(gens, steps)
        return (True, {"generations": results}, "")

    def RunBlast(self, params):
        nid = params.get("node_id", "") if params else ""
        blast = self.WhatBreaksIfThisDies(nid)
        return (True, {"blast_radius": len(blast), "affected": blast}, "")

    def RunReaches(self, params):
        nid = params.get("node_id", "") if params else ""
        reaches = self.WhatReachesThis(nid)
        return (True, {"reached_by": reaches, "count": len(reaches)}, "")

    def RunPath(self, params):
        src = params.get("src", "") if params else ""
        dst = params.get("dst", "") if params else ""
        path = self.ShortestPath(src, dst)
        return (True, {"path": path, "length": len(path)}, "")

    def RunBoot(self, params):
        boot = self.RealBootSequence()
        return (True, {"boot_order": boot}, "")

    def RunCommunities(self, params):
        communities = self.Communities()
        return (True, {"communities": communities, "count": len(communities)}, "")

    def RunCentral(self, params):
        central = self.Centrality()[:20]
        return (True, {"centrality": central}, "")

    def RunInfluence(self, params):
        influence = self.Influence()[:20]
        return (True, {"influence": influence}, "")

    def RunCycles(self, params):
        cycles = self.Cycles()
        return (True, {"cycles": cycles, "count": len(cycles)}, "")

    def RunAttention(self, params):
        top = self.AttentionReport()
        return (True, {"top_attention": top}, "")

    def RunAccuracy(self, params):
        acc = self.PredictionAccuracy()
        return (True, {"prediction_accuracy": round(acc, 4)}, "")

    def RunGoals(self, params):
        return (True, self.GoalStatus(), "")

    def RunExport(self, params):
        return (True, self.Export(), "")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  AGENT BRAIN — Central Nervous System")
    print("=" * 70)

    brain = AgentBrain(ROOT)
    brain.Build()

    print(f"\n  Graph:     {len(brain.graph.nodes)} nodes, {len(brain.graph.edges)} edges")
    print(f"  Goals:     {len(brain.goals.state['goals'])} active")
    print(f"  Attention: {len(brain.attention.state['attention'])} nodes tracked")
    print(f"  World model: {len(brain.world.state['model'])} nodes modeled")

    # Run 5 generations of simulation
    print(f"\n{'─' * 70}")
    print(f"  EVOLVING — 5 generations, 50 steps each")
    print(f"{'─' * 70}")

    results = brain.Evolve(generations=5, steps_per_gen=50)

    for r in results:
        total = r["successes"] + r["failures"]
        rate = r["successes"] / max(1, total) * 100
        print(f"  Gen {r['generation']}: {r['steps']:3d} steps | "
              f"✓{r['successes']:3d} ✗{r['failures']:3d} | "
              f"success rate: {rate:.0f}%")

    # Report
    print(f"\n{'─' * 70}")
    print(f"  BRAIN STATE REPORT")
    print(f"{'─' * 70}")

    stats = brain.ExecutionStats()
    print(f"\n  EXECUTION HISTORY:")
    print(f"    Total runs:       {stats.get('total_runs', 0)}")
    print(f"    Total successes:  {stats.get('total_successes', 0)}")
    print(f"    Total failures:   {stats.get('total_failures', 0)}")
    print(f"    Success rate:     {stats.get('success_rate', 0)*100:.1f}%")
    print(f"    Total reward:     {stats.get('total_reward', 0):.2f}")
    print(f"    Total pain:       {stats.get('total_pain', 0):.2f}")
    print(f"    Avg steps:        {stats.get('avg_steps', 0):.1f}")

    print(f"\n  PREDICTION ACCURACY:")
    print(f"    {brain.PredictionAccuracy()*100:.1f}% correct")

    print(f"\n  GOAL STATUS:")
    goals = brain.GoalStatus()
    print(f"    Active: {goals['active_goal']}")
    print(f"    Completed: {goals['completed']}")
    print(f"    Failed: {goals['failed']}")
    for g in goals["goals"]:
        status_icon = "✓" if g["status"] == "completed" else "✗" if g["status"] == "failed" else "→"
        print(f"    {status_icon} {g['id']:20s} (priority {g['priority']:.1f}) — {g['description']}")

    print(f"\n  ATTENTION (top 5):")
    for nid, score in brain.AttentionReport()[:5]:
        name = nid.split("::")[-1] if "::" in nid else os.path.basename(nid)
        print(f"    {score:.3f} — {name}")

    print(f"\n  TEMPORAL CHANGES:")
    print(f"    {brain.TemporalChanges()} change events detected across snapshots")

    # Show edge weights that changed
    export = brain.Export()
    changed_edges = {k: v for k, v in export["edge_weights"].items() if v["trials"] > 0}
    if changed_edges:
        print(f"\n  SELF-MODIFYING PATHS ({len(changed_edges)} edges adapted):")
        for ekey, info in sorted(changed_edges.items(), key=lambda x: x[1]["trials"], reverse=True)[:5]:
            parts = ekey.split("::")
            src_name = parts[0].split("/")[-1] if "/" in parts[0] else parts[0]
            dst_name = parts[1].split("/")[-1] if "/" in parts[1] else parts[1]
            print(f"    {src_name} → {dst_name} [{parts[2]}] "
                  f"weight={info['weight']:.2f} trials={info['trials']} "
                  f"success_rate={info['success_rate']*100:.0f}%")

    # Export
    print(f"\n  Brain state ready (use WriteToDb to persist)")
    print(f"{'=' * 70}")
