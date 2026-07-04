#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Agent Graph Engine auto-discovers architecture from codebase. Nodes are living agents with sensors, drives, memory, survival. No #[@...] headers (uses old-style comment blocks). No Run dispatch. No Tuple3 returns. Uses Config_efl_brain import. File references Efi_agent_graph.py in header but filename is Dom_Graph_Agent.py. Has hardcoded paths.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Fix filename reference in header. Remove hardcoded paths.>]}
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_agent_graph.py
# Domain:   efl_brain
# Authority: Agent Graph engine — nodes are living agents with sensors + drives
# DB:       None (pure computation, no LLM)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Graph = (V, E) where V = AgentNodes, E = typed edges
# Each node carries: state, sensors, drives, memory, survival
# Cycle = detected. Community = detected. Centrality = computed.
# Boot sequence = discovered from actual imports, not documentation.
# ============================================================================
"""
Agent Graph Engine — auto-discovers architecture from codebase.
Each node is a living agent with:
  Sensors:  taste, touch, vision, smell, pain, hunger
  Drives:   curiosity, fear, confidence, reward, success, failure
  Memory:   experience log, visit count, last seen
  Survival: health, age, generation
The graph answers:
  - What depends on this? (blast radius)
  - What breaks if this dies? (reachability loss)
  - What is the shortest path A → B?
  - What is the most central node?
  - What is the real boot sequence?
  - What are the communities (subsystems)?
  - What is the actual runtime architecture?
No LLM. Feelings = numeric state variables that drive movement.
"""
import os
import ast
import json
import time
import hashlib
import random
import math
from collections import defaultdict, deque
# No cross-imports — brothers communicate through efl_brain.db (the dinner table)
# TypedGraph and ExecutionGraph are imported lazily inside the functions that need them
import Config_efl_brain as Config
ROOT = Config.BASE_DIR
# ============================================================================
# PRIMITIVE: AGENT NODE
# ============================================================================
# Node + State + Sensors + Drives + Memory + Survival
# ============================================================================
class AgentNode:
    """A graph vertex that is also a tiny living agent."""
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Observe(self, node, total_nodes):
        """Update the world model from observing a node."""
        self.state["node_types_seen"][node.type] += 1
        self.state["total_reward"] += node.drives["reward"]
        self.state["total_pain"] += node.sensors["pain"]
        self.state["steps_observed"] += 1
        self.state["last_node"] = node.id
        if node.drives["reward"] > 0.7 and node.id not in self.state["high_value_nodes"]:
            self.state["high_value_nodes"].append(node.id)
        if node.sensors["pain"] > 0.7 and node.id not in self.state["dangerous_nodes"]:
            self.state["dangerous_nodes"].append(node.id)
        # Track explored fraction
        total_seen = sum(self.state["node_types_seen"].values())
        self.state["explored_fraction"] = min(1.0, total_seen / max(1, total_nodes))
        # Rolling average confidence
        if self.state["steps_observed"] > 0:
            self.state["avg_confidence"] = (
                self.state["avg_confidence"] * 0.9 + node.drives["confidence"] * 0.1
            )
        return (1, None, None)
    def Predict(self):
        """Predict outcome based on current state."""
        confidence = self.drives["confidence"]
        curiosity = self.drives["curiosity"]
        fear = self.drives["fear"]
        prediction = confidence * (1 - fear) + curiosity * 0.3
        return (1, max(0.0, min(1.0, prediction)), None)
    def Act(self, available_targets):
        """Decide which target to move to based on drives + sensors."""
        if not available_targets:
            return (1, None, None)
        scored = []
        for target_id, target_node in available_targets:
            score = 0.0
            score += target_node.drives["curiosity"] * 0.3
            score += target_node.sensors["taste"] * 0.2
            score += target_node.sensors["smell"] * 0.2
            score -= target_node.drives["fear"] * 0.3
            score -= target_node.sensors["pain"] * 0.4
            score += self.drives["curiosity"] * 0.1
            scored.append((score, target_id))
        scored.sort(reverse=True, key=lambda x: x[0])
        # Sometimes explore randomly (curiosity-driven)
        if random.random() < self.drives["curiosity"] * 0.2 and len(scored) > 1:
            return (1, scored[random.randint(0, min(2, len(scored) - 1))][1], None)
        return (1, scored[0][1] if scored else None, None)
    def Measure(self, success, reward_value=0.0, pain_value=0.0):
        """Measure outcome and update drives."""
        self.memory["visits"] += 1
        self.memory["last_seen"] = time.time()
        if success:
            self.drives["success"] += 1
            self.drives["reward"] = min(1.0, self.drives["reward"] + 0.1)
            self.drives["confidence"] = min(1.0, self.drives["confidence"] + 0.05)
            self.drives["fear"] = max(0.0, self.drives["fear"] - 0.05)
            self.sensors["taste"] = min(1.0, self.sensors["taste"] + 0.1)
            self.sensors["pain"] = max(0.0, self.sensors["pain"] - 0.1)
        else:
            self.drives["failure"] += 1
            self.drives["fear"] = min(1.0, self.drives["fear"] + 0.1)
            self.drives["confidence"] = max(0.0, self.drives["confidence"] - 0.1)
            self.sensors["pain"] = min(1.0, self.sensors["pain"] + 0.15)
            self.sensors["taste"] = max(0.0, self.sensors["taste"] - 0.05)
        self.memory["last_reward"] = self.drives["reward"]
        self.memory["last_pain"] = self.sensors["pain"]
        # Record experience
        self.memory["experiences"].append({
            "success": success,
            "reward": reward_value,
            "pain": pain_value,
            "fear": self.drives["fear"],
            "confidence": self.drives["confidence"],
        })
        # Keep memory bounded
        if len(self.memory["experiences"]) > 100:
            self.memory["experiences"] = self.memory["experiences"][-50:]
        return (1, None, None)
    def UpdateSurvival(self):
        """Update health based on experiences."""
        total = self.drives["success"] + self.drives["failure"]
        if total > 0:
            success_rate = self.drives["success"] / total
            self.survival["health"] = max(0.0, min(1.0, success_rate * 0.7 + 0.3))
        self.survival["age"] += 1
        # Health affects alive status
        if self.survival["health"] < 0.1:
            self.survival["alive"] = False
            self.drives["fear"] = 1.0
        else:
            self.survival["alive"] = True
        return (1, None, None)
    def BoostAttention(self, amount):
        """Increase attention toward this node."""
        self.attention = min(1.0, self.attention + amount)
        if self.attention > self.attention_peak:
            self.attention_peak = self.attention
        return (1, None, None)
    def DecayAttention(self, decay_rate=0.05):
        """Decay attention each step — focus fades unless re-stimulated."""
        self.attention = max(0.0, self.attention - decay_rate)
        # Novelty decays with each visit — faster decay promotes exploration
        self.novelty = max(0.0, self.novelty - 0.05)
        return (1, None, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Update(self, confidence, fear, reward, pain, success_streak, fail_streak):
        """Update mood from current drives and sensors."""
        # Mood = weighted blend of confidence and reward, minus fear and pain
        raw_mood = (confidence * 0.35 + reward * 0.30) - (fear * 0.20 + pain * 0.15)
        self.mood = max(0.0, min(1.0, 0.7 * self.mood + 0.3 * (raw_mood + 0.5)))
        # Arousal = how stimulated the agent is (recent activity)
        self.arousal = max(0.0, min(1.0, 0.8 * self.arousal + 0.2 * (success_streak + fail_streak) / 10.0))
        # Frustration grows with failures and pain, decays with success and reward
        frustration_delta = (pain * 0.1 + fail_streak * 0.05) - (reward * 0.05 + success_streak * 0.03)
        self.frustration = max(0.0, min(1.0, self.frustration + frustration_delta))
        self.history.append(self.mood)
        if len(self.history) > 50:
            self.history = self.history[-30:]
        return (1, None, None)
    def NetValue(self):
        """Net expected value: reward minus pain, weighted by confidence."""
        return (1, (self.expected_reward - self.expected_pain) * self.confidence, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Observe(self, node, total_nodes):
        """Update the world model from observing a node."""
        self.state["node_types_seen"][node.type] += 1
        self.state["total_reward"] += node.drives["reward"]
        self.state["total_pain"] += node.sensors["pain"]
        self.state["steps_observed"] += 1
        self.state["last_node"] = node.id
        if node.drives["reward"] > 0.7 and node.id not in self.state["high_value_nodes"]:
            self.state["high_value_nodes"].append(node.id)
        if node.sensors["pain"] > 0.7 and node.id not in self.state["dangerous_nodes"]:
            self.state["dangerous_nodes"].append(node.id)
        # Track explored fraction
        total_seen = sum(self.state["node_types_seen"].values())
        self.state["explored_fraction"] = min(1.0, total_seen / max(1, total_nodes))
        # Rolling average confidence
        if self.state["steps_observed"] > 0:
            self.state["avg_confidence"] = (
                self.state["avg_confidence"] * 0.9 + node.drives["confidence"] * 0.1
            )
        return (1, None, None)
    def Summary(self):
        return (1, {
            "total_goals": len(self.state["goals"]),
            "completed": self.state["goals_completed"],
            "failed": self.state["goals_failed"],
            "active_goal": self.state["active_goal"],
            "goals": [g.ToDict() for g in self.state["goals"]],
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def CheckProgress(self, current_node):
        """Check if the current node satisfies this goal."""
        self.steps_taken += 1
        if self.target_id and current_node.id == self.target_id:
            self.progress = 1.0
            self.completed = True
            return (1, True, None)
        if self.target_type and current_node.type == self.target_type:
            self.progress = max(self.progress, 0.5)
            # Type match is partial progress; full completion requires staying there
            if self.steps_taken > 0:
                self.progress = 1.0
                self.completed = True
                return (1, True, None)
        if self.steps_taken >= self.max_steps and not self.completed:
            self.failed = True
        return (1, False, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def AddGoal(self, goal):
        self.state["goals"].append(goal)
        return (1, None, None)
    def SelectActiveGoal(self):
        """Pick the highest-priority incomplete goal."""
        candidates = [g for g in self.state["goals"] if not g.completed and not g.failed]
        if not candidates:
            self.state["active_goal"] = None
            return (1, None, None)
        candidates.sort(key=lambda g: g.priority, reverse=True)
        self.state["active_goal"] = candidates[0].id
        return (1, candidates[0], None)
    def InjectDrive(self, node, goal):
        """Inject hunger/curiosity into a node based on the active goal."""
        if goal is None:
            return (1, None, None)
        # Boost hunger — the agent wants to reach the goal target
        node.sensors["hunger"] = min(1.0, node.sensors["hunger"] + goal.priority * 0.3)
        # Boost curiosity toward the goal's target type
        node.drives["curiosity"] = min(1.0, node.drives["curiosity"] + goal.priority * 0.2)
    def UpdateGoals(self, current_node):
        """Check all goals against the current node. Returns (reward, pain)."""
        reward = 0.0
        pain = 0.0
        for goal in self.state["goals"]:
            if goal.completed or goal.failed:
                continue
            was_completed = goal.completed
            goal.CheckProgress(current_node)
            if goal.completed and not was_completed:
                reward += goal.reward_on_complete
                self.state["goals_completed"] += 1
            if goal.failed and not was_completed:
                pain += goal.pain_on_fail
                self.state["goals_failed"] += 1
        return (1, reward, pain, None)
    def Summary(self):
        return (1, {
            "total_goals": len(self.state["goals"]),
            "completed": self.state["goals_completed"],
            "failed": self.state["goals_failed"],
            "active_goal": self.state["active_goal"],
            "goals": [g.ToDict() for g in self.state["goals"]],
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Update(self, confidence, fear, reward, pain, success_streak, fail_streak):
        """Update mood from current drives and sensors."""
        # Mood = weighted blend of confidence and reward, minus fear and pain
        raw_mood = (confidence * 0.35 + reward * 0.30) - (fear * 0.20 + pain * 0.15)
        self.mood = max(0.0, min(1.0, 0.7 * self.mood + 0.3 * (raw_mood + 0.5)))
        # Arousal = how stimulated the agent is (recent activity)
        self.arousal = max(0.0, min(1.0, 0.8 * self.arousal + 0.2 * (success_streak + fail_streak) / 10.0))
        # Frustration grows with failures and pain, decays with success and reward
        frustration_delta = (pain * 0.1 + fail_streak * 0.05) - (reward * 0.05 + success_streak * 0.03)
        self.frustration = max(0.0, min(1.0, self.frustration + frustration_delta))
        self.history.append(self.mood)
        if len(self.history) > 50:
            self.history = self.history[-30:]
        return (1, None, None)
    def Trend(self):
        """Return mood trend: 'rising', 'falling', or 'stable'."""
        if len(self.history) < 5:
            return (1, "stable", None)
        recent = sum(self.history[-5:]) / 5
        older = sum(self.history[-10:-5]) / 5 if len(self.history) >= 10 else sum(self.history) / len(self.history)
        diff = recent - older
        if diff > 0.05:
            return (1, "rising", None)
        if diff < -0.05:
            return (1, "falling", None)
        return (1, "stable", None)
    def ExplorationBias(self):
        """How much the agent should favor exploration over exploitation.
        High frustration or high mood → more exploration.
        Low mood (fear) → less exploration (retreat to known)."""
        return (1, max(0.0, min(1.0, self.frustration * 0.5 + self.mood * 0.3 + 0.2)), None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Consolidate(self, graph):
        """Run one consolidation cycle on the graph."""
        self.consolidation_count += 1
        # 1. Prune weak prediction links (confidence < 0.15 AND update_count < 3)
        weak_keys = []
        for key, link in graph.prediction_links.items():
            if link.confidence < 0.15 and link.update_count < 3:
                weak_keys.append(key)
        for key in weak_keys:
            del graph.prediction_links[key]
            graph.edges_pruned += 1
            self.links_pruned_total += 1
        # 2. Compress experience memory — keep only first, last, and significant events
        for node in graph.nodes.values():
            exps = node.memory.get("experiences", [])
            if len(exps) > 20:
                # Keep first 3, last 5, and any with extreme reward or pain
                significant = [e for e in exps if e.get("reward", 0) > 0.7 or e.get("pain", 0) > 0.7]
                kept = exps[:3] + exps[-5:] + significant
                # Deduplicate preserving order
                seen = set()
                deduped = []
                for e in kept:
                    key = (e.get("success"), round(e.get("reward", 0), 2), round(e.get("pain", 0), 2))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(e)
                node.memory["experiences"] = deduped[:15]
                self.memories_compressed_total += len(exps) - len(deduped)
        # 3. Refresh novelty for nodes not visited recently
        now = time.time()
        for node in graph.nodes.values():
            if node.memory["visits"] == 0:
                node.novelty = min(1.0, node.novelty + 0.3)
                self.novelty_refreshed_total += 1
            elif node.memory["last_seen"] > 0 and (now - node.memory["last_seen"]) > 5:
                # Nodes not seen in a while get partial novelty refresh
                node.novelty = min(1.0, node.novelty + 0.1)
        # 4. Global fear decay — sleep reduces anxiety
        total_fear_decay = 0.0
        for node in graph.nodes.values():
            old_fear = node.drives["fear"]
            node.drives["fear"] = max(0.0, node.drives["fear"] * 0.7)
            total_fear_decay += old_fear - node.drives["fear"]
        self.fear_decayed_total += total_fear_decay
        return (1, None, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def SetStrength(self, strength):
        """Set the adversary's power level (0.0 - 1.0)."""
        self.strength = max(0.0, min(1.0, strength))
        return (1, None, None)
    def SetAggression(self, aggression):
        """Set how often the adversary attacks (0.0 - 1.0)."""
        self.aggression = max(0.0, min(1.0, aggression))
        return (1, None, None)
    def Attack(self, graph, yang_current_id, step):
        """Execute one attack turn. Returns the attack type used, or None."""
        if random.random() > self.aggression:
            return (1, None, None)
        self.attack_count += 1
        # Choose attack type — intelligent adversary targets the yang's strengths
        attack_types = ["poison_links", "inject_fear", "block_nodes", "false_reward"]
        # Intelligent targeting: if yang has high confidence, attack links
        # If yang has high reward, create false rewards
        # If yang is exploring well, block nodes
        yang_node = graph.nodes.get(yang_current_id)
        if yang_node and self.intelligence > 0.5:
            if yang_node.drives["confidence"] > 0.7:
                attack_types = ["poison_links", "poison_links", "inject_fear"]
            elif yang_node.drives["reward"] > 0.5:
                attack_types = ["false_reward", "false_reward", "block_nodes"]
            else:
                attack_types = ["block_nodes", "inject_fear", "poison_links"]
        attack = random.choice(attack_types)
        if attack == "poison_links":
            self.PoisonLinks(graph, yang_current_id)
        elif attack == "inject_fear":
            self.InjectFear(graph, yang_current_id)
        elif attack == "block_nodes":
            self.BlockNodes(graph, yang_current_id)
        elif attack == "false_reward":
            self.FalseReward(graph, yang_current_id)
        self.attacks[attack] += 1
        return (1, attack, None)
    def PoisonLinks(self, graph, yang_current_id):
        """Invert prediction links around the yang agent — swap reward and pain."""
        neighbors = list(set(
            graph.adj.get(yang_current_id, []) +
            graph.radj.get(yang_current_id, [])
        ))
        for nid in neighbors[:5]:  # Attack at most 5 links
            key = (yang_current_id, nid)
            if key in graph.prediction_links:
                link = graph.prediction_links[key]
                # Swap reward and pain with probability based on strength
                if random.random() < self.strength:
                    link.expected_reward, link.expected_pain = (
                        link.expected_pain, link.expected_reward
                    )
                    # Reduce confidence — the yang must re-learn
                    link.confidence *= (1.0 - self.strength * 0.3)
        return (1, None, None)
    def InjectFear(self, graph, yang_current_id):
        """Inject fear into high-confidence nodes near the yang agent."""
        neighbors = list(set(
            graph.adj.get(yang_current_id, []) +
            graph.radj.get(yang_current_id, [])
        ))
        for nid in neighbors:
            if nid in graph.nodes:
                node = graph.nodes[nid]
                if node.drives["confidence"] > 0.5:
                    node.drives["fear"] = min(1.0, node.drives["fear"] + self.strength * 0.3)
                    node.Observe("pain", self.strength * 0.2)
        return (1, None, None)
    def BlockNodes(self, graph, yang_current_id):
        """Temporarily block high-value nodes — remove them from adjacency."""
        candidates = []
        for nid, node in graph.nodes.items():
            if node.drives["reward"] > 0.5 and nid != yang_current_id:
                candidates.append(nid)
        if candidates:
            num_block = min(len(candidates), max(1, int(self.strength * 3)))
            blocked = random.sample(candidates, num_block)
            for nid in blocked:
                self.blocked_nodes.add(nid)
        return (1, None, None)
    def FalseReward(self, graph, yang_current_id):
        """Create false reward signals on low-value nodes — trick the yang."""
        neighbors = list(set(
            graph.adj.get(yang_current_id, []) +
            graph.radj.get(yang_current_id, [])
        ))
        for nid in neighbors:
            if nid in graph.nodes:
                node = graph.nodes[nid]
                if node.drives["reward"] < 0.3:
                    # Inflate reward to trick the yang into visiting
                    node.drives["reward"] = min(1.0, node.drives["reward"] + self.strength * 0.4)
                    node.sensors["taste"] = min(1.0, node.sensors["taste"] + self.strength * 0.3)
        return (1, None, None)
    def UnblockAll(self):
        """Remove all blocked nodes — used between attack waves."""
        self.blocked_nodes.clear()
        return (1, None, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def Connect(self):
        """Try to connect to MySQL. Returns True on success."""
        try:
            import mysql.connector
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db,
                connection_timeout=3,
            )
            self.connected = self.conn.is_connected()
            return (1, self.connected, None)
        except Exception:
            self.connected = False
            return (1, False, None)
    def Disconnect(self):
        if self.conn and self.connected:
            try:
                self.conn.close()
            except Exception:
                pass
        self.connected = False
        return (1, None, None)
    def LoadLearnedRules(self, keywords=None, limit=500):
        """Load learned_rules from MySQL. Returns list of dicts.
        If keywords given, filters by pattern/trigger_condition/fix_action.
        Each rule: {pattern, trigger_condition, fix_action, confidence, success_count, failure_count}"""
        if not self.connected:
            return (1, [], None)
        try:
            cursor = self.conn.cursor(dictionary=True)
            if keywords:
                like_clause = " OR ".join(
                    [f"pattern LIKE '%{kw}%' OR trigger_condition LIKE '%{kw}%' OR fix_action LIKE '%{kw}%'"
                     for kw in keywords]
                )
                sql = f"""
                    SELECT pattern, trigger_condition, fix_action, confidence,
                           success_count, failure_count
                    FROM learned_rules
                    WHERE {like_clause}
                    ORDER BY confidence DESC, success_count DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
            else:
                sql = """
                    SELECT pattern, trigger_condition, fix_action, confidence,
                           success_count, failure_count
                    FROM learned_rules
                    ORDER BY confidence DESC, success_count DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            self.rules_loaded = len(rows)
            return (1, rows, None)
        except Exception:
            return (1, [], None)
    def SeedGraphFromRules(self, graph, keywords=None, limit=500):
        """Pre-populate prediction links with confidence from learned_rules.
        Maps rule keywords to node names/paths in the graph."""
        rules = self.LoadLearnedRules(keywords=keywords, limit=limit)
        if not rules:
            return (1, 0, None)
        # Build a lookup: keyword -> list of node_ids
        # Index by node name, class name, method names, and path components
        keyword_to_ids = defaultdict(list)
        for nid, node in graph.nodes.items():
            name = node.state.get("name", os.path.basename(node.path) if node.path else nid)
            for word in name.lower().replace("_", " ").split():
                if len(word) > 2:
                    keyword_to_ids[word].append(nid)
            if node.state.get("class_name"):
                for word in node.state["class_name"].lower().replace("_", " ").split():
                    if len(word) > 2:
                        keyword_to_ids[word].append(nid)
            for method in node.state.get("methods", []):
                for word in method.lower().replace("_", " ").split():
                    if len(word) > 2:
                        keyword_to_ids[word].append(nid)
            # Also index by path components
            if node.path:
                for part in os.path.basename(node.path).lower().replace("_", " ").split():
                    if len(part) > 2:
                        keyword_to_ids[part].append(nid)
        seeded = 0
        for rule in rules:
            pattern = (rule.get("pattern") or "").lower()
            trigger = (rule.get("trigger_condition") or "").lower()
            fix_action = (rule.get("fix_action") or "").lower()
            confidence = float(rule.get("confidence") or 0.5)
            success_count = int(rule.get("success_count") or 0)
            failure_count = int(rule.get("failure_count") or 0)
            # Extract keywords from all text fields and match to nodes
            all_text = f"{pattern} {trigger} {fix_action}"
            matched_ids = set()
            for word in all_text.replace("_", " ").split():
                word = word.strip(".,;:!?\"'()[]{}")
                if len(word) > 3 and word in keyword_to_ids:
                    matched_ids.update(keyword_to_ids[word])
            # Seed prediction links for matched nodes
            for target_id in matched_ids:
                for src_id in graph.radj.get(target_id, []):
                    link = graph.GetOrCreatePredictionLink(src_id, target_id)
                    mysql_weight = min(1.0, success_count / 10.0)
                    link.confidence = max(link.confidence, confidence * mysql_weight)
                    total = success_count + failure_count
                    if total > 0:
                        link.expected_reward = max(0.0, min(1.0, success_count / total))
                        link.expected_pain = max(0.0, min(1.0, failure_count / total))
                    link.update_count = max(link.update_count, total)
                    seeded += 1
        return (1, seeded, None)
    def WriteOutcomeToMysql(self, pattern, trigger_condition, fix_action, success, confidence):
        """Write a new learned_rule back to MySQL from a graph outcome."""
        if not self.connected:
            return (1, False, None)
        try:
            cursor = self.conn.cursor()
            success_count = 1 if success else 0
            failure_count = 0 if success else 1
            sql = """
                INSERT INTO learned_rules (pattern, trigger_condition, fix_action, confidence, success_count, failure_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (pattern, trigger_condition, fix_action, confidence, success_count, failure_count))
            self.conn.commit()
            cursor.close()
            self.rules_written += 1
            return (1, True, None)
        except Exception:
            return (1, False, None)
    def ToDict(self):
        return (1, {
            "connected": self.connected,
            "host": self.host,
            "db": self.db,
            "rules_loaded": self.rules_loaded,
            "rules_written": self.rules_written,
        }, None)
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
        self.edge_set = set()
        # --- Cognitive substrate ---
        self.prediction_links = {}        # (src_id, dst_id) -> PredictionLink
        self.world_model = WorldModel()
        self.goal_system = GoalSystem()
        self.emotion = EmotionalState()
        self.consolidation = Consolidation()
        self.co_activation = defaultdict(int)   # (a, b) -> co-activation count (for growing edges)
        self.self_modify_count = 0
        self.edges_grown = 0
        self.edges_pruned = 0
        self.success_streak = 0
        self.fail_streak = 0
        self.consolidation_interval = Config.CONSOLIDATION_INTERVAL  # consolidate every N steps
        self.adversary = None             # AdversarialAgent (yin), set by YinYangSimulate
        self.mysql = None                 # MysqlConnector, set by SeedFromMysql
    def AddNode(self, node):
        self.nodes[node.id] = node
        return (1, None, None)
    def AddEdge(self, edge):
        key = (edge.src, edge.dst, edge.type)
        if key not in self.edge_set:
            self.edges.append(edge)
            self.adj[edge.src].append(edge.dst)
            self.radj[edge.dst].append(edge.src)
            self.edge_set.add(key)
        return (1, None, None)
    def Build(self, root):
        folder_id = root
        self.AddNode(AgentNode(folder_id, "FOLDER", root))
        for entry in sorted(os.listdir(root)):
            full_path = os.path.join(root, entry)
            if os.path.isdir(full_path):
                self.AddNode(AgentNode(full_path, "FOLDER", full_path))
                self.AddEdge(Edge(folder_id, full_path, "CONTAINS"))
                continue
            if entry.startswith("."):
                continue
            ext = os.path.splitext(entry)[1]
            file_id = full_path
            if entry.startswith("Config_") and ext == ".py":
                self.AddNode(AgentNode(file_id, "CONFIG", full_path))
            elif ext == ".py":
                self.AddNode(AgentNode(file_id, "FILE_PY", full_path))
            elif ext == ".json":
                self.AddNode(AgentNode(file_id, "FILE_JSON", full_path))
            elif ext == ".md":
                self.AddNode(AgentNode(file_id, "FILE_MD", full_path))
            elif ext == ".db":
                self.AddNode(AgentNode(file_id, "FILE_DB", full_path))
            else:
                continue
            self.AddEdge(Edge(folder_id, file_id, "CONTAINS"))
        py_nodes = [n for n in self.nodes.values() if n.type in ("FILE_PY", "CONFIG")]
        for py_node in py_nodes:
            self.ParsePythonFile(py_node)
        self.BuildImportEdges(py_nodes)
        self.BuildCallEdges(py_nodes)
        self.InitializeSensors()
        return (1, None, None)
    def ParsePythonFile(self, py_node):
        if not os.path.exists(py_node.path):
            return (1, None, None)
        with open(py_node.path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=py_node.path)
            except SyntaxError:
                return (1, None, None)
        for item in ast.iter_child_nodes(tree):
            if isinstance(item, ast.ClassDef):
                class_id = f"{py_node.id}::{item.name}"
                has_run = False
                has_state = False
                methods = []
                for child in item.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(child.name)
                        if child.name == "Run":
                            has_run = True
                        for node in ast.walk(child):
                            if isinstance(node, ast.Attribute):
                                if isinstance(node.value, ast.Name) and node.value.id == "self":
                                    if node.attr == "state":
                                        has_state = True
                node_type = "MEMUNIT" if has_run and has_state else "CLASS"
                class_node = AgentNode(class_id, node_type, py_node.path)
                class_node.state["class_name"] = item.name
                class_node.state["methods"] = methods
                class_node.state["method_count"] = len(methods)
                class_node.state["has_run"] = has_run
                class_node.state["has_state"] = has_state
                class_node.state["bases"] = [b.id for b in item.bases if isinstance(b, ast.Name)]
                self.AddNode(class_node)
                self.AddEdge(Edge(py_node.id, class_id, "DEFINES"))
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{py_node.id}::{item.name}"
                func_node = AgentNode(func_id, "FUNCTION", py_node.path)
                func_node.state["params"] = [a.arg for a in item.args.args]
                func_node.state["param_count"] = len(item.args.args)
                self.AddNode(func_node)
                self.AddEdge(Edge(py_node.id, func_id, "DEFINES"))
    def BuildImportEdges(self, py_nodes):
        path_to_id = {}
        for n in py_nodes:
            base = os.path.splitext(os.path.basename(n.path))[0]
            path_to_id[base] = n.id
        for py_node in py_nodes:
            if not os.path.exists(py_node.path):
                continue
            with open(py_node.path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=py_node.path)
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module in path_to_id:
                        target_id = path_to_id[node.module]
                        if target_id != py_node.id:
                            self.AddEdge(Edge(py_node.id, target_id, "IMPORTS"))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in path_to_id:
                            target_id = path_to_id[alias.name]
                            if target_id != py_node.id:
                                self.AddEdge(Edge(py_node.id, target_id, "IMPORTS"))
        return (1, None, None)
    def BuildCallEdges(self, py_nodes):
        """Detect method calls between classes — CALLS edges."""
        class_names = {}
        for n in self.nodes.values():
            if n.type in ("CLASS", "MEMUNIT") and n.state.get("class_name"):
                class_names[n.state["class_name"]] = n.id
        for py_node in py_nodes:
            if not os.path.exists(py_node.path):
                continue
            with open(py_node.path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=py_node.path)
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            var_name = node.func.value.id
                            if var_name in class_names:
                                caller_id = self.FindCallerClass(py_node.id, node.lineno)
                                if caller_id and caller_id != class_names[var_name]:
                                    self.AddEdge(Edge(caller_id, class_names[var_name], "CALLS"))
        return (1, None, None)
    def FindCallerClass(self, file_id, lineno):
        """Find which class method contains a given line number."""
        for n in self.nodes.values():
            if n.id.startswith(file_id + "::") and n.type in ("CLASS", "MEMUNIT", "FUNCTION"):
                return (1, n.id, None)
        return (1, file_id, None)
    def InitializeSensors(self):
        """Set initial sensor values based on node properties."""
        for node in self.nodes.values():
            if node.type == "CONFIG":
                node.sensors["smell"] = 1.0
                node.drives["confidence"] = 0.9
                node.sensors["hunger"] = 0.2
            elif node.type == "MEMUNIT":
                node.sensors["smell"] = 0.8
                node.drives["curiosity"] = 0.7
                node.drives["confidence"] = 0.7
            elif node.type == "CLASS":
                node.sensors["smell"] = 0.5
                node.drives["curiosity"] = 0.5
            elif node.type == "FUNCTION":
                node.sensors["touch"] = 0.3
                node.drives["curiosity"] = 0.4
            elif node.type == "FILE_PY":
                node.sensors["vision"] = 0.6
            elif node.type == "FILE_DB":
                node.sensors["smell"] = 0.4
                node.drives["hunger"] = 0.3
            elif node.type == "FILE_MD":
                node.sensors["vision"] = 0.3
        return (1, None, None)
    def BuildTypedGraph(self):
        """Build a TypedGraph (from Efi_code_graph.py) from the same root.
        The TypedGraph provides structural analysis (roots, leaves, hubs, DAG check)
        that complements the agent graph's cognitive layer.
        Lazy import — no module-level coupling."""
        from Efi_code_graph import TypedGraph
        tg = TypedGraph()
        tg.Build(ROOT)
        return (1, tg, None)
    def ValidateBootSequence(self):
        """Use ExecutionGraph (from Efi_boot_graph.py) to validate the boot order.
        Returns the execution graph's report on whether the boot sequence is valid.
        Lazy import — no module-level coupling."""
        from Efi_boot_graph import ExecutionGraph
        eg = ExecutionGraph()
        eg.BuildGraph()
        return (1, eg.GenerateReport(), None)
    def StructuralAnalysis(self):
        """Run TypedGraph structural analysis and merge results into the agent graph.
        Returns roots, leaves, hubs, and DAG status from the typed graph."""
        tg = self.BuildTypedGraph()
        return (1, {
            "roots": tg.GetRoots(),
            "leaves": tg.GetLeaves(),
            "hubs": tg.GetHubs(),
            "is_dag": tg.IsDAG(),
            "type_counts": tg.GetTypeCounts(),
            "components": len(tg.GetComponents()),
        }, None)
    def DetectCycles(self):
        visited = set()
        stack = []
        cycles = []
        def DFS(node_id):
            if node_id in stack:
                idx = stack.index(node_id)
                cycles.append(stack[idx:] + [node_id])
                return (1, None, None)
            if node_id in visited:
                return (1, None, None)
            visited.add(node_id)
            stack.append(node_id)
            for neighbor in self.adj.get(node_id, []):
                DFS(neighbor)
            stack.pop()
        for node_id in self.nodes:
            if node_id not in visited:
                DFS(node_id)
        return (1, cycles, None)
    def ShortestPath(self, src_id, dst_id):
        if src_id not in self.nodes or dst_id not in self.nodes:
            return (1, [], None)
        if src_id == dst_id:
            return (1, [src_id], None)
        visited = {src_id}
        queue = deque([(src_id, [src_id])])
        while queue:
            current, path = queue.popleft()
            for neighbor in self.adj.get(current, []):
                if neighbor == dst_id:
                    return (1, path + [neighbor], None)
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return (1, [], None)
    def AllPaths(self, src_id, dst_id, max_depth=10):
        paths = []
        def Walk(node_id, path, depth):
            if depth > max_depth:
                return (1, None, None)
            path.append(node_id)
            if node_id == dst_id:
                paths.append(list(path))
            else:
                for nxt in self.adj.get(node_id, []):
                    if nxt not in path:
                        Walk(nxt, path, depth + 1)
            path.pop()
        Walk(src_id, [], 0)
        return (1, paths, None)
    def WhatReachesThis(self, node_id):
        """All nodes that can reach node_id (reverse BFS)."""
        if node_id not in self.nodes:
            return (1, [], None)
        visited = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for parent in self.radj.get(current, []):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return (1, list(visited), None)
    def BlastRadius(self, node_id):
        """Everything that depends on node_id — if it dies, these break."""
        if node_id not in self.nodes:
            return (1, [], None)
        visited = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for child in self.adj.get(current, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return (1, list(visited), None)
    def Centrality(self):
        """Degree centrality for all nodes."""
        scores = {}
        for node_id in self.nodes:
            in_deg = len(self.radj.get(node_id, []))
            out_deg = len(self.adj.get(node_id, []))
            scores[node_id] = in_deg + out_deg
        return (1, sorted(scores.items(), key=lambda x: x[1], reverse=True), None)
    def BetweennessCentrality(self):
        """Approximate betweenness — how many shortest paths pass through this node."""
        node_ids = list(self.nodes.keys())
        betweenness = {nid: 0 for nid in node_ids}
        # Sample pairs (full computation is O(n^3))
        sample_size = min(len(node_ids), 30)
        sampled = random.sample(node_ids, sample_size) if len(node_ids) > sample_size else node_ids
        for src in sampled:
            for dst in sampled:
                if src == dst:
                    continue
                path = self.ShortestPath(src, dst)
                for mid in path[1:-1]:
                    betweenness[mid] += 1
        return (1, sorted(betweenness.items(), key=lambda x: x[1], reverse=True), None)
    def DetectCommunities(self, max_iterations=20):
        """Label propagation algorithm — finds subsystem clusters.
        Communities reflect real code-level coupling (imports, defines, contains).
        Brothers that communicate through the database (efl_brain.db) don't need
        to be in the same community — the database is the dinner table, not the
        import graph. This shows the TRUE coupling structure of the codebase.
        """
        labels = {nid: i for i, nid in enumerate(self.nodes)}
        for _ in range(max_iterations):
            changed = False
            for node_id in self.nodes:
                neighbor_labels = []
                for neighbor in self.adj.get(node_id, []):
                    neighbor_labels.append(labels.get(neighbor, labels[node_id]))
                for neighbor in self.radj.get(node_id, []):
                    neighbor_labels.append(labels.get(neighbor, labels[node_id]))
                if neighbor_labels:
                    # Pick most common label
                    counts = defaultdict(int)
                    for lbl in neighbor_labels:
                        counts[lbl] += 1
                    new_label = max(counts.items(), key=lambda x: x[1])[0]
                    if new_label != labels[node_id]:
                        labels[node_id] = new_label
                        changed = True
            if not changed:
                break
        # Group by label
        communities = defaultdict(list)
        for node_id, label in labels.items():
            communities[label].append(node_id)
        return (1, list(communities.values()), None)
    def BootSequence(self):
        """Discover the real boot order from import dependencies."""
        # Only consider IMPORTS edges
        import_adj = defaultdict(list)
        import_indeg = defaultdict(int)
        for edge in self.edges:
            if edge.type == "IMPORTS":
                import_adj[edge.src].append(edge.dst)
                import_indeg[edge.dst] += 1
        # Kahn's algorithm
        queue = deque()
        for node_id in self.nodes:
            if import_indeg.get(node_id, 0) == 0:
                queue.append(node_id)
        order = []
        visited = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            order.append(current)
            for neighbor in import_adj.get(current, []):
                import_indeg[neighbor] -= 1
                if import_indeg[neighbor] <= 0:
                    queue.append(neighbor)
        return (1, order, None)
    def GetIslands(self):
        """Find disconnected components."""
        visited = set()
        islands = []
        for node_id in self.nodes:
            if node_id in visited:
                continue
            component = []
            queue = deque([node_id])
            while queue:
                nid = queue.popleft()
                if nid in visited:
                    continue
                visited.add(nid)
                component.append(nid)
                for n in self.adj.get(nid, []):
                    queue.append(n)
                for n in self.radj.get(nid, []):
                    queue.append(n)
            islands.append(component)
        return (1, islands, None)
    def GetOrCreatePredictionLink(self, src_id, dst_id):
        """Get an existing prediction link or create a new one."""
        key = (src_id, dst_id)
        if key not in self.prediction_links:
            self.prediction_links[key] = PredictionLink(src_id, dst_id)
        return (1, self.prediction_links[key], None)
    def PredictNext(self, current_id):
        """Use prediction links to choose the best next node from current_id.
        Returns (best_next_id, predicted_value) or (None, 0.0) if no links."""
        neighbors = self.adj.get(current_id, [])
        if not neighbors:
            return (1, None, 0.0, None)
        best_next = None
        best_value = -1e9
        for nid in neighbors:
            if nid not in self.nodes:
                continue
            link = self.GetOrCreatePredictionLink(current_id, nid)
            value = link.NetValue()
            # Add novelty bonus — unexplored nodes get a curiosity boost
            value += self.nodes[nid].novelty * 0.1
            if value > best_value:
                best_value = value
                best_next = nid
        return (1, best_next, best_value, None)
    def FindNearestNodeOfType(self, start_id, target_type, max_depth=8):
        """BFS from start_id to find the nearest node of target_type.
        Returns the node_id or None if not found within max_depth."""
        if start_id not in self.nodes:
            return (1, None, None)
        visited = {start_id}
        queue = deque([(start_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth > max_depth:
                continue
            if depth > 0 and self.nodes[current].type == target_type:
                return (1, current, None)
            for neighbor in list(set(
                self.adj.get(current, []) + self.radj.get(current, [])
            )):
                if neighbor not in visited and neighbor in self.nodes:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return (1, None, None)
    def PathToTarget(self, start_id, target_id, max_depth=8):
        """BFS shortest path from start_id to target_id.
        Returns the path as a list of node_ids, or [] if no path."""
        if start_id not in self.nodes or target_id not in self.nodes:
            return (1, [], None)
        if start_id == target_id:
            return (1, [start_id], None)
        visited = {start_id}
        queue = deque([(start_id, [start_id])])
        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue
            for neighbor in list(set(
                self.adj.get(current, []) + self.radj.get(current, [])
            )):
                if neighbor == target_id:
                    return (1, path + [neighbor], None)
                if neighbor not in visited and neighbor in self.nodes:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return (1, [], None)
    def MultiStepPlan(self, current_id, active_goal, visited_count, depth=2):
        """Look ahead `depth` hops from current_id and score each path.
        Returns (best_next_id, best_path_score).
        Considers: goal proximity, novelty, prediction links, emotional bias."""
        neighbors = list(set(
            self.adj.get(current_id, []) +
            self.radj.get(current_id, [])
        ))
        if not neighbors:
            return (1, None, 0.0, None)
        best_next = None
        best_score = -1e9
        exploration_bias = self.emotion.ExplorationBias()
        for nid in neighbors:
            if nid not in self.nodes:
                continue
            nnode = self.nodes[nid]
            # Base score from prediction link + novelty + attention
            link = self.GetOrCreatePredictionLink(current_id, nid)
            score = link.NetValue() * 0.2
            score += nnode.novelty * 0.3 * (0.5 + exploration_bias)
            score += nnode.attention * 0.1
            score += nnode.drives["curiosity"] * 0.1
            score -= nnode.drives["fear"] * 0.15
            score -= nnode.sensors["pain"] * 0.2
            # Strong anti-loop penalty — visited nodes get heavily penalized
            visit_penalty = visited_count.get(nid, 0)
            score -= visit_penalty * 0.5
            # Goal steering
            if active_goal:
                if active_goal.target_type and nnode.type == active_goal.target_type:
                    score += active_goal.priority * 0.8
                if active_goal.target_id and nid == active_goal.target_id:
                    score += active_goal.priority * 1.0
                # Goal-directed pathfinding: if goal targets a type,
                # check if this neighbor is on the path to the nearest target node
                if active_goal.target_type and nnode.type != active_goal.target_type:
                    # Is this neighbor closer to the target type?
                    target_node = self.FindNearestNodeOfType(nid, active_goal.target_type, max_depth=4)
                    if target_node:
                        path_to_target = self.PathToTarget(nid, target_node, max_depth=4)
                        if path_to_target and len(path_to_target) <= 3:
                            score += active_goal.priority * 0.4 / len(path_to_target)
            # Look ahead one more hop (depth=2)
            if depth >= 2:
                sub_neighbors = list(set(
                    self.adj.get(nid, []) + self.radj.get(nid, [])
                ))
                best_sub_score = 0.0
                for sub_nid in sub_neighbors:
                    if sub_nid not in self.nodes or sub_nid == current_id:
                        continue
                    sub_node = self.nodes[sub_nid]
                    sub_link = self.GetOrCreatePredictionLink(nid, sub_nid)
                    sub_score = sub_link.NetValue() * 0.1
                    sub_score += sub_node.novelty * 0.15
                    sub_score -= visited_count.get(sub_nid, 0) * 0.3
                    if active_goal and active_goal.target_type and sub_node.type == active_goal.target_type:
                        sub_score += active_goal.priority * 0.4
                    if sub_score > best_sub_score:
                        best_sub_score = sub_score
                score += best_sub_score * 0.3
            if score > best_score:
                best_score = score
                best_next = nid
        return (1, best_next, best_score, None)
    def AdaptiveAlpha(self, link):
        """Learning rate that decays as confidence grows.
        Fresh links learn fast; confident links learn slow (refine)."""
        return (1, max(Config.LEARNING_RATE_FINAL, Config.LEARNING_RATE_INITIAL * (1.0 - link.confidence)), None)
    def AttendTo(self, node_id, goal=None):
        """Boost attention on a node based on reward, novelty, and goal relevance."""
        if node_id not in self.nodes:
            return (1, None, None)
        node = self.nodes[node_id]
        boost = 0.0
        # Reward boosts attention
        boost += node.drives["reward"] * 0.3
        # Novelty boosts attention
        boost += node.novelty * 0.2
        # Goal relevance boosts attention
        if goal:
            if goal.target_type and node.type == goal.target_type:
                boost += goal.priority * 0.4
            if goal.target_id and node.id == goal.target_id:
                boost += goal.priority * 0.5
        node.BoostAttention(boost)
    def SelfModify(self, src_id, dst_id, actual_reward, actual_pain):
        """Update prediction links from outcome, prune weak links, grow new edges.
        This is the self-modifying paths mechanism:
        1. Update the prediction link for src->dst with the actual outcome (adaptive alpha)
        2. Track co-activation — if two nodes are visited close together, grow an edge
        3. Prune prediction links with very low confidence and negative value
        4. Boost confidence on the source node if prediction was accurate
        """
        self.self_modify_count += 1
        # 1. Update prediction link with adaptive learning rate
        link = self.GetOrCreatePredictionLink(src_id, dst_id)
        alpha = self.AdaptiveAlpha(link)
        link.Update(actual_reward, actual_pain, alpha=alpha)
        # 4. Confidence boost when prediction was accurate
        predicted_reward = link.expected_reward
        prediction_error = abs(predicted_reward - actual_reward)
        if prediction_error < 0.2 and src_id in self.nodes:
            # Accurate prediction → grow confidence
            self.nodes[src_id].drives["confidence"] = min(
                1.0, self.nodes[src_id].drives["confidence"] + 0.08
            )
        # 2. Track co-activation for potential edge growth
        self.co_activation[(src_id, dst_id)] += 1
        # If two nodes co-activate enough times and there's no structural edge, grow one
        co_count = self.co_activation[(src_id, dst_id)]
        if co_count >= 5 and (src_id, dst_id, "ASSOCIATES") not in self.edge_set:
            if src_id in self.nodes and dst_id in self.nodes:
                self.AddEdge(Edge(src_id, dst_id, "ASSOCIATES"))
                self.edges_grown += 1
        # 3. Prune prediction links with very low confidence and strongly negative value
        # Only prune after enough updates to have a real signal
        if link.update_count >= 10 and link.confidence > 0.3 and link.NetValue() < -0.3:
            # Mark as pruned — remove from prediction links
            del self.prediction_links[(src_id, dst_id)]
            self.edges_pruned += 1
        return (1, None, None)
    def UpdateWorldModel(self, node):
        """Feed an observed node into the world model."""
        self.world_model.Observe(node, len(self.nodes))
        return (1, None, None)
    def SeedFromMysql(self, keywords=None, limit=500):
        """Connect to MySQL vb_shared and seed prediction links from learned_rules.
        Returns the number of prediction links seeded."""
        self.mysql = MysqlConnector()
        if not self.mysql.Connect():
            return (1, 0, None)
        seeded = self.mysql.SeedGraphFromRules(self, keywords=keywords, limit=limit)
        return (1, seeded, None)
    def WriteToDb(self, db_path=None):
        """Write all agent graph state to efl_brain.db (the dinner table).
        Other brothers (solution_engine, graph_viewer) can read this without
        importing this file. No cross-imports needed."""
        from Efi_brain_db import BrainDb
        db = BrainDb(db_path)
        db.Connect()
        # Write prediction links
        links = []
        for (src, dst), link in self.prediction_links.items():
            links.append({
                "source_node": src,
                "target_node": dst,
                "expected_reward": round(link.expected_reward, 4),
                "expected_pain": round(link.expected_pain, 4),
                "confidence": round(link.confidence, 4),
                "update_count": link.update_count,
            })
        written_links = db.WritePredictionLinks(links)
        # Write world model
        wm = self.world_model.Summary()
        db.WriteWorldModel(wm)
        # Write emotional state
        db.WriteEmotionalState(self.emotion.ToDict())
        # Write blast radius for high-value nodes
        blast_written = 0
        for nid, node in self.nodes.items():
            if node.drives["reward"] > 0.5 or node.type in ("CONFIG", "MEMUNIT"):
                blast = self.BlastRadius(nid)
                blast_written += db.WriteBlastRadius(nid, blast)
        db.Disconnect()
        return (1, {
            "prediction_links_written": written_links,
            "blast_radius_written": blast_written,
            "world_model_written": True,
            "emotional_state_written": True,
        }, None)
    def ReadFromDb(self, db_path=None):
        """Read prediction links and world model from efl_brain.db.
        This lets the agent graph pick up where the last run left off,
        or read data written by other brothers."""
        from Efi_brain_db import BrainDb
        db = BrainDb(db_path)
        db.Connect()
        links = db.ReadPredictionLinks()
        restored = 0
        for link in links:
            src = link["source_node"]
            dst = link["target_node"]
            if src in self.nodes and dst in self.nodes:
                pred_link = self.GetOrCreatePredictionLink(src, dst)
                pred_link.confidence = max(pred_link.confidence, link["confidence"])
                pred_link.expected_reward = link["expected_reward"]
                pred_link.expected_pain = link["expected_pain"]
                pred_link.update_count = link["update_count"]
                restored += 1
        wm = db.ReadWorldModel()
        em = db.ReadEmotionalState()
        db.Disconnect()
        return (1, {
            "prediction_links_restored": restored,
            "world_model": wm,
            "emotional_state": em,
        }, None)
    def YinYangSimulate(self, start_id, steps=200, yin_strength=0.5, yin_aggression=0.3):
        """Adversarial simulation: yang agent runs FullSimulate while yin attacks.
        The yin agent attacks at intervals, trying to break the yang's predictions.
        The yang must maintain goals, confidence, and exploration despite attacks.
        Consolidation (sleep) is the yang's primary defense — it prunes poisoned links
        and restores confidence.
        Returns the FullSimulate result plus yin attack statistics.
        """
        if start_id not in self.nodes:
            return (1, {"error": "Start node not found"}, None)
        # Create the adversary
        self.adversary = AdversarialAgent(name="Yin")
        self.adversary.SetStrength(yin_strength)
        self.adversary.SetAggression(yin_aggression)
        # We need to hook the adversary into the simulation loop.
        # Instead of modifying FullSimulate, we run a custom loop here that
        # calls the same steps but inserts yin attacks between steps.
        # Seed default goals if none exist
        if not self.goal_system.state["goals"]:
            self.goal_system.AddGoal(Goal("G1", "Find a CONFIG node", target_type="CONFIG", priority=0.8))
            self.goal_system.AddGoal(Goal("G2", "Find a MEMUNIT node", target_type="MEMUNIT", priority=0.7))
            self.goal_system.AddGoal(Goal("G3", "Explore 80% of the graph", priority=0.5))
            self.goal_system.AddGoal(Goal("G4", "Find a FUNCTION node", target_type="FUNCTION", priority=0.4))
        path = []
        path_history = []
        current_id = start_id
        visited_count = defaultdict(int)
        unique_nodes_visited = set()
        consolidation_steps = []
        yin_attacks_log = []
        yang_resisted = 0  # count of attacks the yang recovered from
        for step in range(steps):
            node = self.nodes[current_id]
            unique_nodes_visited.add(current_id)
            # 1. Observe
            node.Observe("touch", 1.0)
            node.sensors["hunger"] = max(0.0, node.sensors["hunger"] - 0.1)
            # 2. Predict
            predicted_next, predicted_value = self.PredictNext(current_id)
            # 3. Attend
            active_goal = self.goal_system.SelectActiveGoal()
            self.AttendTo(current_id, active_goal)
            if step % 3 == 0:
                for n in self.nodes.values():
                    n.DecayAttention()
            # 4. Plan
            planned_next, plan_score = self.MultiStepPlan(
                current_id, active_goal, visited_count, depth=2
            )
            # 5. Act — but filter out blocked nodes
            next_id = planned_next
            if next_id and next_id in self.adversary.blocked_nodes:
                # Blocked! Yang must find an alternative
                neighbors = list(set(
                    self.adj.get(current_id, []) + self.radj.get(current_id, [])
                ))
                unblocked = [
                    nid for nid in neighbors
                    if nid in self.nodes and nid not in self.adversary.blocked_nodes
                    and nid != next_id
                ]
                if unblocked:
                    next_id = random.choice(unblocked)
                yang_resisted += 1
            if next_id is None:
                candidates = [
                    nid for nid in self.nodes
                    if visited_count.get(nid, 0) == 0
                    and nid not in self.adversary.blocked_nodes
                    and (self.adj.get(nid) or self.radj.get(nid))
                ]
                if candidates:
                    next_id = random.choice(candidates)
                else:
                    node.Measure(False, pain_value=0.1)
                    break
            # Emotional exploration
            exploration_bias = self.emotion.ExplorationBias()
            if random.random() < exploration_bias * 0.2:
                neighbors = list(set(
                    self.adj.get(current_id, []) + self.radj.get(current_id, [])
                ))
                fresh_neighbors = [
                    nid for nid in neighbors
                    if nid in self.nodes and visited_count.get(nid, 0) == 0
                    and nid not in self.adversary.blocked_nodes
                ]
                if fresh_neighbors:
                    next_id = random.choice(fresh_neighbors)
            if next_id is None or next_id not in self.nodes:
                node.Measure(False)
                break
            # 6. Measure
            target = self.nodes[next_id]
            is_new_node = visited_count.get(next_id, 0) == 0
            is_valuable_type = target.type in ("CONFIG", "MEMUNIT", "FUNCTION")
            success = is_new_node or is_valuable_type or target.drives["curiosity"] > 0.5
            reward_value = 0.0
            if is_new_node:
                reward_value += 0.15
            if is_valuable_type:
                reward_value += 0.1
            pain_value = 0.0
            if not success:
                pain_value = 0.05
            node.Measure(success, reward_value=reward_value, pain_value=pain_value)
            if success:
                self.success_streak += 1
                self.fail_streak = 0
            else:
                self.fail_streak += 1
                self.success_streak = 0
            target.Observe("touch", 0.5)
            if not success:
                target.Observe("pain", 0.05)
            # 7. Self-modify
            actual_reward = target.drives["reward"] + reward_value
            actual_pain = target.sensors["pain"]
            self.SelfModify(current_id, next_id, actual_reward, actual_pain)
            # 8. Update world model
            self.UpdateWorldModel(node)
            # 9. Update emotional state
            self.emotion.Update(
                confidence=node.drives["confidence"],
                fear=node.drives["fear"],
                reward=node.drives["reward"],
                pain=node.sensors["pain"],
                success_streak=self.success_streak,
                fail_streak=self.fail_streak,
            )
            # 10. Check goals
            goal_reward, goal_pain = self.goal_system.UpdateGoals(target)
            if goal_reward > 0:
                node.drives["reward"] = min(1.0, node.drives["reward"] + goal_reward)
                self.emotion.mood = min(1.0, self.emotion.mood + goal_reward * 0.3)
            if goal_pain > 0:
                node.sensors["pain"] = min(1.0, node.sensors["pain"] + goal_pain)
            for g in self.goal_system.state["goals"]:
                if "Explore" in g.description:
                    g.progress = self.world_model.state["explored_fraction"]
                    threshold = 0.5 if "50%" in g.description else 0.8 if "80%" in g.description else 0.5
                    if g.progress >= threshold and not g.completed:
                        g.completed = True
                        self.goal_system.state["goals_completed"] += 1
            node.UpdateSurvival()
            visited_count[current_id] += 1
            path_history.append(current_id)
            # 11. YIN ATTACK — the adversary strikes
            attack_type = self.adversary.Attack(self, next_id, step)
            if attack_type:
                yin_attacks_log.append({
                    "step": step,
                    "attack": attack_type,
                    "yang_confidence_before": round(node.drives["confidence"], 3),
                })
            # 12. Periodic consolidation (sleep) — yang's defense against yin
            if step > 0 and step % self.consolidation_interval == 0:
                self.consolidation.Consolidate(self)
                consolidation_steps.append(step)
                # Unblock nodes after consolidation — yin's blocks are temporary
                self.adversary.UnblockAll()
            path.append({
                "step": step,
                "node": current_id,
                "type": node.type,
                "prediction": round(predicted_value, 3),
                "plan_score": round(plan_score, 3),
                "attention": round(node.attention, 3),
                "fear": round(node.drives["fear"], 3),
                "confidence": round(node.drives["confidence"], 3),
                "reward": round(node.drives["reward"], 3),
                "novelty": round(node.novelty, 3),
                "mood": round(self.emotion.mood, 3),
                "frustration": round(self.emotion.frustration, 3),
                "success": success,
                "is_new": is_new_node,
                "under_attack": attack_type is not None,
                "attack_type": attack_type,
            })
            current_id = next_id
        return (1, {
            "path": path,
            "steps": len(path),
            "unique_nodes_visited": len(unique_nodes_visited),
            "total_nodes": len(self.nodes),
            "coverage": round(len(unique_nodes_visited) / max(1, len(self.nodes)), 4),
            "world_model": self.world_model.Summary(),
            "goals": self.goal_system.Summary(),
            "emotion": self.emotion.ToDict(),
            "consolidation": self.consolidation.ToDict(),
            "consolidation_steps": consolidation_steps,
            "prediction_links": len(self.prediction_links),
            "self_modify_count": self.self_modify_count,
            "edges_grown": self.edges_grown,
            "edges_pruned": self.edges_pruned,
            "yin": self.adversary.ToDict(),
            "yin_attack_count": self.adversary.attack_count,
            "yin_attacks": yin_attacks_log,
            "yang_resisted": yang_resisted,
            "mysql": self.mysql.ToDict() if self.mysql else None,
        }, None)
    def FullSimulate(self, start_id, steps=100):
        """Full cognitive substrate simulation with planning, emotions, and consolidation.
        The agent loop becomes:
          1. Observe current node (sensors)
          2. Predict next move (prediction links)
          3. Attend to relevant nodes (attention weights)
          4. Plan — multi-step lookahead with goal-directed pathfinding
          5. Act — choose where to go (plan + emotion + exploration bias)
          6. Measure outcome (reward/pain) — success = learned something new
          7. Self-modify (adaptive alpha prediction links, grow/prune edges)
          8. Update world model
          9. Update emotional state (mood, arousal, frustration)
         10. Check goals
         11. Periodically: consolidate (sleep — prune, compress, refresh)
        """
        if start_id not in self.nodes:
            return (1, {"error": "Start node not found"}, None)
        # Seed default goals if none exist
        if not self.goal_system.state["goals"]:
            self.goal_system.AddGoal(Goal(
                "G1", "Find a CONFIG node", target_type="CONFIG", priority=0.8
            ))
            self.goal_system.AddGoal(Goal(
                "G2", "Find a MEMUNIT node", target_type="MEMUNIT", priority=0.7
            ))
            self.goal_system.AddGoal(Goal(
                "G3", "Explore 80% of the graph", priority=0.5
            ))
            self.goal_system.AddGoal(Goal(
                "G4", "Find a FUNCTION node", target_type="FUNCTION", priority=0.4
            ))
        path = []
        path_history = []
        current_id = start_id
        visited_count = defaultdict(int)
        unique_nodes_visited = set()
        consolidation_steps = []
        for step in range(steps):
            node = self.nodes[current_id]
            unique_nodes_visited.add(current_id)
            # 1. Observe
            node.Observe("touch", 1.0)
            node.sensors["hunger"] = max(0.0, node.sensors["hunger"] - 0.1)
            # 2. Predict
            predicted_next, predicted_value = self.PredictNext(current_id)
            # 3. Attend — select active goal and boost attention
            active_goal = self.goal_system.SelectActiveGoal()
            self.AttendTo(current_id, active_goal)
            # Decay attention on all nodes (but only every 3 steps to save time)
            if step % 3 == 0:
                for n in self.nodes.values():
                    n.DecayAttention()
            # 4. Plan — multi-step lookahead with goal-directed pathfinding
            planned_next, plan_score = self.MultiStepPlan(
                current_id, active_goal, visited_count, depth=2
            )
            # 5. Act — use the plan, with emotional exploration bias
            next_id = planned_next
            if next_id is None:
                # No neighbors — try jumping to an unvisited node
                candidates = [
                    nid for nid in self.nodes
                    if visited_count.get(nid, 0) == 0
                    and (self.adj.get(nid) or self.radj.get(nid))
                ]
                if candidates:
                    next_id = random.choice(candidates)
                else:
                    node.Measure(False, pain_value=0.1)
                    break
            # Emotional exploration — sometimes override with a random fresh node
            exploration_bias = self.emotion.ExplorationBias()
            if random.random() < exploration_bias * 0.2:
                neighbors = list(set(
                    self.adj.get(current_id, []) + self.radj.get(current_id, [])
                ))
                fresh_neighbors = [
                    nid for nid in neighbors
                    if nid in self.nodes and visited_count.get(nid, 0) == 0
                ]
                if fresh_neighbors:
                    next_id = random.choice(fresh_neighbors)
            if next_id is None or next_id not in self.nodes:
                node.Measure(False)
                break
            # 6. Measure outcome — success = visited a NEW node or found something valuable
            target = self.nodes[next_id]
            is_new_node = visited_count.get(next_id, 0) == 0
            is_valuable_type = target.type in ("CONFIG", "MEMUNIT", "FUNCTION")
            success = is_new_node or is_valuable_type or target.drives["curiosity"] > 0.5
            # Reward scales with novelty and value
            reward_value = 0.0
            if is_new_node:
                reward_value += 0.15
            if is_valuable_type:
                reward_value += 0.1
            pain_value = 0.0
            if not success:
                pain_value = 0.05
            node.Measure(success, reward_value=reward_value, pain_value=pain_value)
            # Track streaks for emotional state
            if success:
                self.success_streak += 1
                self.fail_streak = 0
            else:
                self.fail_streak += 1
                self.success_streak = 0
            # Target feels the touch
            target.Observe("touch", 0.5)
            if not success:
                target.Observe("pain", 0.05)
            # 7. Self-modify — update prediction links from actual outcome
            actual_reward = target.drives["reward"] + reward_value
            actual_pain = target.sensors["pain"]
            self.SelfModify(current_id, next_id, actual_reward, actual_pain)
            # 8. Update world model
            self.UpdateWorldModel(node)
            # 9. Update emotional state
            self.emotion.Update(
                confidence=node.drives["confidence"],
                fear=node.drives["fear"],
                reward=node.drives["reward"],
                pain=node.sensors["pain"],
                success_streak=self.success_streak,
                fail_streak=self.fail_streak,
            )
            # 10. Check goals
            goal_reward, goal_pain = self.goal_system.UpdateGoals(target)
            if goal_reward > 0:
                node.drives["reward"] = min(1.0, node.drives["reward"] + goal_reward)
                self.emotion.mood = min(1.0, self.emotion.mood + goal_reward * 0.3)
            if goal_pain > 0:
                node.sensors["pain"] = min(1.0, node.sensors["pain"] + goal_pain)
            # Check exploration goal
            for g in self.goal_system.state["goals"]:
                if "Explore" in g.description:
                    g.progress = self.world_model.state["explored_fraction"]
                    threshold = 0.5 if "50%" in g.description else 0.8 if "80%" in g.description else 0.5
                    if g.progress >= threshold and not g.completed:
                        g.completed = True
                        self.goal_system.state["goals_completed"] += 1
            node.UpdateSurvival()
            visited_count[current_id] += 1
            path_history.append(current_id)
            # 11. Periodic consolidation (sleep)
            if step > 0 and step % self.consolidation_interval == 0:
                self.consolidation.Consolidate(self)
                consolidation_steps.append(step)
            path.append({
                "step": step,
                "node": current_id,
                "type": node.type,
                "prediction": round(predicted_value, 3),
                "plan_score": round(plan_score, 3),
                "attention": round(node.attention, 3),
                "fear": round(node.drives["fear"], 3),
                "confidence": round(node.drives["confidence"], 3),
                "reward": round(node.drives["reward"], 3),
                "novelty": round(node.novelty, 3),
                "mood": round(self.emotion.mood, 3),
                "frustration": round(self.emotion.frustration, 3),
                "success": success,
                "is_new": is_new_node,
            })
            current_id = next_id
        return (1, {
            "path": path,
            "steps": len(path),
            "unique_nodes_visited": len(unique_nodes_visited),
            "total_nodes": len(self.nodes),
            "coverage": round(len(unique_nodes_visited) / max(1, len(self.nodes)), 4),
            "world_model": self.world_model.Summary(),
            "goals": self.goal_system.Summary(),
            "emotion": self.emotion.ToDict(),
            "consolidation": self.consolidation.ToDict(),
            "consolidation_steps": consolidation_steps,
            "prediction_links": len(self.prediction_links),
            "self_modify_count": self.self_modify_count,
            "edges_grown": self.edges_grown,
            "edges_pruned": self.edges_pruned,
        }, None)
    def Simulate(self, start_id, steps=50):
        """Walk the graph as an agent — observe, predict, act, measure."""
        if start_id not in self.nodes:
            return (1, [], None)
        path = []
        current_id = start_id
        visited_count = defaultdict(int)
        for step in range(steps):
            node = self.nodes[current_id]
            node.Observe("touch", 1.0)
            node.sensors["hunger"] = max(0.0, node.sensors["hunger"] - 0.1)
            prediction = node.Predict()
            path.append({
                "step": step,
                "node": current_id,
                "type": node.type,
                "prediction": round(prediction, 3),
                "fear": round(node.drives["fear"], 3),
                "confidence": round(node.drives["confidence"], 3),
                "curiosity": round(node.drives["curiosity"], 3),
                "reward": round(node.drives["reward"], 3),
            })
            # Get available targets
            neighbors = self.adj.get(current_id, [])
            available = [(nid, self.nodes[nid]) for nid in neighbors if nid in self.nodes]
            if not available:
                node.Measure(False, pain_value=0.1)
                break
            # Agent decides where to go
            next_id = node.Act(available)
            if next_id is None:
                node.Measure(False)
                break
            # Propagate smell to neighbors
            for nid, nnode in available:
                if nid == next_id:
                    nnode.Observe("smell", node.drives["curiosity"] * 0.5)
            # Measure success (did we find something interesting?)
            target = self.nodes[next_id]
            success = target.type in ("CONFIG", "MEMUNIT") or target.drives["curiosity"] > 0.5
            node.Measure(success, reward_value=0.1 if success else 0.0)
            # Target feels the touch
            target.Observe("touch", 0.5)
            if not success:
                target.Observe("pain", 0.1)
            node.UpdateSurvival()
            visited_count[current_id] += 1
            # Avoid loops — if we've been here too many times, increase fear
            if visited_count[current_id] > 3:
                node.drives["fear"] = min(1.0, node.drives["fear"] + 0.3)
                node.Observe("pain", 0.2)
            current_id = next_id
        return (1, path, None)
    def InfluenceRanking(self):
        """Rank nodes by how many others they affect (forward reach)."""
        ranking = []
        for node_id in self.nodes:
            affected = set()
            queue = deque([node_id])
            while queue:
                current = queue.popleft()
                for child in self.adj.get(current, []):
                    if child not in affected:
                        affected.add(child)
                        queue.append(child)
            ranking.append((node_id, len(affected)))
        return (1, sorted(ranking, key=lambda x: x[1], reverse=True), None)
    def Export(self):
        cycles = self.DetectCycles()
        communities = self.DetectCommunities()
        boot = self.BootSequence()
        centrality = self.Centrality()[:10]
        influence = self.InfluenceRanking()[:10]
        islands = self.GetIslands()
        return (1, {
            "primitives": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
            "node_types": self.TypeCounts(),
            "nodes": [n.ToDict() for n in self.nodes.values()],
            "edges": [e.ToDict() for e in self.edges],
            "derived": {
                "cycles": cycles,
                "cycle_count": len(cycles),
                "is_dag": len(cycles) == 0,
                "boot_sequence": boot,
                "communities": communities,
                "community_count": len(communities),
                "centrality_top10": [(nid, score) for nid, score in centrality],
                "influence_top10": [(nid, score) for nid, score in influence],
                "islands": islands,
                "island_count": len(islands),
            },
            "cognitive_substrate": {
                "prediction_links": [pl.ToDict() for pl in self.prediction_links.values()],
                "prediction_link_count": len(self.prediction_links),
                "self_modify_count": self.self_modify_count,
                "edges_grown": self.edges_grown,
                "edges_pruned": self.edges_pruned,
                "world_model": self.world_model.Summary(),
                "goal_system": self.goal_system.Summary(),
                "emotion": self.emotion.ToDict(),
                "consolidation": self.consolidation.ToDict(),
            },
        }, None)
    def _TypeCounts(self):
        counts = defaultdict(int)
        for node in self.nodes.values():
            counts[node.type] += 1
        return (1, dict(counts), None)
    def Run(self, command, params):
        """Dispatch entry — returns Tuple3."""
        DISPATCH = {
            "blast": self.RunBlastRadius,
            "reaches": self.RunReaches,
            "path": self.RunShortestPath,
            "all_paths": self.RunAllPaths,
            "boot": self.RunBootSequence,
            "communities": self.RunCommunities,
            "central": self.RunCentrality,
            "influence": self.RunInfluence,
            "islands": self.RunIslands,
            "simulate": self.RunSimulate,
            "cycles": self.RunCycles,
            "export": self.RunExport,
            "predict": self.RunPredict,
            "attend": self.RunAttend,
            "self_modify": self.RunSelfModify,
            "world_model": self.RunWorldModel,
            "goals": self.RunGoals,
            "full_simulate": self.RunFullSimulate,
            "emotion": self.RunEmotion,
            "consolidation": self.RunConsolidation,
            "plan": self.RunPlan,
            "yin_yang": self.RunYinYang,
            "seed_mysql": self.RunSeedMysql,
            "structural": self.RunStructural,
            "validate_boot": self.RunValidateBoot,
            "write_db": self.RunWriteDb,
            "read_db": self.RunReadDb,
        }
        handler = DISPATCH.get(command)
        if handler is None:
            return (False, None, f"Unknown command: {command}")
        return handler(params)
    def RunBlastRadius(self, params):
        node_id = params.get("node_id", "")
        if node_id not in self.nodes:
            return (False, None, "Node not found")
        blast = self.BlastRadius(node_id)
        return (True, {"node": node_id, "blast_radius": len(blast), "affected": blast}, "")
    def RunReaches(self, params):
        node_id = params.get("node_id", "")
        if node_id not in self.nodes:
            return (False, None, "Node not found")
        reaches = self.WhatReachesThis(node_id)
        return (True, {"node": node_id, "reached_by_count": len(reaches), "reached_by": reaches}, "")
    def RunShortestPath(self, params):
        src = params.get("src", "")
        dst = params.get("dst", "")
        path = self.ShortestPath(src, dst)
        if not path:
            return (False, None, "No path found")
        return (True, {"path": path, "length": len(path)}, "")
    def RunAllPaths(self, params):
        src = params.get("src", "")
        dst = params.get("dst", "")
        paths = self.AllPaths(src, dst)
        return (True, {"paths": paths, "count": len(paths)}, "")
    def RunBootSequence(self, params):
        boot = self.BootSequence()
        return (True, {"boot_order": boot, "steps": len(boot)}, "")
    def RunCommunities(self, params):
        communities = self.DetectCommunities()
        return (True, {"communities": communities, "count": len(communities)}, "")
    def RunCentrality(self, params):
        centrality = self.Centrality()[:20]
        return (True, {"centrality": centrality}, "")
    def RunInfluence(self, params):
        influence = self.InfluenceRanking()[:20]
        return (True, {"influence": influence}, "")
    def RunIslands(self, params):
        islands = self.GetIslands()
        return (True, {"islands": islands, "count": len(islands)}, "")
    def RunSimulate(self, params):
        start = params.get("start", "")
        steps = params.get("steps", 50)
        if start not in self.nodes:
            return (False, None, "Start node not found")
        path = self.Simulate(start, steps)
        return (True, {"simulation": path, "steps": len(path)}, "")
    def RunCycles(self, params):
        cycles = self.DetectCycles()
        return (True, {"cycles": cycles, "count": len(cycles)}, "")
    def RunExport(self, params):
        return (True, self.Export(), "")
    def RunPredict(self, params):
        """Predict the best next node from a given node using prediction links."""
        node_id = params.get("node_id", "")
        if node_id not in self.nodes:
            return (False, None, "Node not found")
        next_id, value = self.PredictNext(node_id)
        return (True, {
            "from": node_id,
            "predicted_next": next_id,
            "predicted_value": round(value, 4),
            "prediction_link_count": len(self.prediction_links),
        }, "")
    def RunAttend(self, params):
        """Boost attention on a node. Optionally pass a goal_id for goal-relevant boost."""
        node_id = params.get("node_id", "")
        if node_id not in self.nodes:
            return (False, None, "Node not found")
        goal_id = params.get("goal_id")
        goal = None
        if goal_id:
            for g in self.goal_system.state["goals"]:
                if g.id == goal_id:
                    goal = g
                    break
        self.AttendTo(node_id, goal)
        node = self.nodes[node_id]
        return (True, {
            "node": node_id,
            "attention": round(node.attention, 4),
            "attention_peak": round(node.attention_peak, 4),
            "novelty": round(node.novelty, 4),
        }, "")
    def RunSelfModify(self, params):
        """Manually trigger a self-modify step: update a prediction link from an outcome."""
        src = params.get("src", "")
        dst = params.get("dst", "")
        reward = params.get("reward", 0.5)
        pain = params.get("pain", 0.0)
        if src not in self.nodes or dst not in self.nodes:
            return (False, None, "Source or destination node not found")
        self.SelfModify(src, dst, reward, pain)
        return (True, {
            "src": src,
            "dst": dst,
            "self_modify_count": self.self_modify_count,
            "edges_grown": self.edges_grown,
            "edges_pruned": self.edges_pruned,
            "prediction_links": len(self.prediction_links),
        }, "")
    def RunWorldModel(self, params):
        """Return the current world model summary."""
        return (True, self.world_model.Summary(), "")
    def RunGoals(self, params):
        """Return the goal system summary, or add a goal if action='add'."""
        action = params.get("action", "summary")
        if action == "add":
            goal = Goal(
                goal_id=params.get("goal_id", f"G{len(self.goal_system.state['goals'])+1}"),
                description=params.get("description", ""),
                target_type=params.get("target_type"),
                target_id=params.get("target_id"),
                priority=params.get("priority", 0.5),
            )
            self.goal_system.AddGoal(goal)
            return (True, {"added": goal.ToDict()}, "")
        return (True, self.goal_system.Summary(), "")
    def RunFullSimulate(self, params):
        """Run the full cognitive substrate simulation."""
        start = params.get("start", "")
        steps = params.get("steps", 100)
        if start not in self.nodes:
            return (False, None, "Start node not found")
        result = self.FullSimulate(start, steps)
        return (True, result, "")
    def RunEmotion(self, params):
        """Return the current emotional state."""
        return (True, self.emotion.ToDict(), "")
    def RunConsolidation(self, params):
        """Trigger a consolidation cycle manually."""
        self.consolidation.Consolidate(self)
        return (True, self.consolidation.ToDict(), "")
    def RunPlan(self, params):
        """Run multi-step planning from a node. Optionally pass a goal_id."""
        node_id = params.get("node_id", "")
        if node_id not in self.nodes:
            return (False, None, "Node not found")
        goal_id = params.get("goal_id")
        goal = None
        if goal_id:
            for g in self.goal_system.state["goals"]:
                if g.id == goal_id:
                    goal = g
                    break
        visited = defaultdict(int)
        next_id, score = self.MultiStepPlan(node_id, goal, visited, depth=2)
        return (True, {
            "from": node_id,
            "planned_next": next_id,
            "plan_score": round(score, 4),
        }, "")
    def RunYinYang(self, params):
        """Run adversarial yin/yang simulation."""
        start = params.get("start", "")
        steps = params.get("steps", 200)
        yin_strength = params.get("yin_strength", 0.5)
        yin_aggression = params.get("yin_aggression", 0.3)
        if start not in self.nodes:
            return (False, None, "Start node not found")
        result = self.YinYangSimulate(start, steps, yin_strength, yin_aggression)
        return (True, result, "")
    def RunSeedMysql(self, params):
        """Seed prediction links from MySQL learned_rules."""
        keywords = params.get("keywords")
        limit = params.get("limit", 500)
        seeded = self.SeedFromMysql(keywords=keywords, limit=limit)
        return (True, {
            "seeded": seeded,
            "mysql": self.mysql.ToDict() if self.mysql else None,
        }, "")
    def RunStructural(self, params):
        """Run TypedGraph structural analysis (roots, leaves, hubs, DAG)."""
        return (True, self.StructuralAnalysis(), "")
    def RunValidateBoot(self, params):
        """Validate boot sequence using ExecutionGraph."""
        return (True, {"report": self.ValidateBootSequence()}, "")
    def RunWriteDb(self, params):
        """Write agent graph state to efl_brain.db."""
        result = self.WriteToDb()
        return (True, result, "")
    def RunReadDb(self, params):
        """Read agent graph state from efl_brain.db."""
        result = self.ReadFromDb()
        return (True, result, "")