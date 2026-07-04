#!/usr/bin/env python3
#[@GHOST]{[@file<ui_energy_optimizer.py>][@state<active>][@date<2026-06-28>][@ver<12.1>][@auth<cascade>]}
#[@VBSTYLE]{[@auth<cascade>][@role<ppo_layout_brain>][@return<none>][@no<decorators|print|hardcoded_paths|tabs>]}
#[@SUMMARY]{Layout Intelligence Engine v12.1 — Full PPO layout brain with autonomous training loop and synthetic UI graph generator. Actor-critic, adjacency matrix, VSCode structure reward, live training with reward graph, MPS GPU. Stage 2 hybrid AI with active learning.}
#[@CLASS]{Node Constraint Graph PhysicsEngine EnergyScorer WeightLearner AnnealingShaker DockRules LayoutMemory SyntheticUIGenerator GraphEncoder ActorCritic RLEnvironment PPOTrainer TrainingLoop BrainLoop Canvas ControlPanel InfoPanel}
#[@METHOD]{__init__ accumulate integrate clamp evaluate learn shake apply_rules step tick paintEvent encode forward get_state get_reward compute_advantages ppo_update train_step generate start_episode step_episode end_episode main}

"""
Layout Intelligence Engine v12.1 — "The PPO Layout Brain"
======================================================
Stage 2: Hybrid AI — physics + PPO actor-critic + autonomous training.

Evolution:
  Stage 1 (v9): deterministic physics + heuristics + energy minimization
  Stage 2 (v12.1): hybrid — physics + PPO + synthetic data + auto-training  <-- THIS
  Stage 3 (future): full AI — NN replaces physics entirely

RL Components:
  - SyntheticUIGenerator: generates random VSCode-style UI graphs (6-14 nodes)
  - GraphEncoder: graph state -> tensor (positions, velocities, types, adjacency)
  - ActorCritic: shared encoder -> policy head (dx,dy) + value head (V(s))
  - RLEnvironment: wraps physics engine as RL env (state/action/reward)
  - PPOTrainer: PPO with advantage estimation, clipped objectives, value loss
  - TrainingLoop: autonomous episode runner (generate -> play -> learn -> repeat)
  - MPS acceleration on Apple Silicon

Reward = -overlap_penalty - misalignment_penalty - dock_distance
         + vscode_structure_bonus + stability_bonus

Training Loop:
  1. Generate synthetic UI graph (random nodes, roles, constraints)
  2. Run episode: policy predicts moves, physics applies, reward computed
  3. Record transitions (state, action, reward, value, log_prob)
  4. PPO update: clipped objective + value loss + entropy bonus
  5. Track best reward, average reward, loss history
  6. Repeat with new graph -> generalises to unseen layouts

The GUI is just the output surface.
The engine is a layout intelligence system that LEARNS.

Loop:
  read graph -> apply constraints -> physics -> energy -> learn -> anneal -> NN -> render -> repeat
  [AUTO]: generate graph -> episode -> train -> repeat

Run: python3 ui_energy_optimizer.py
"""

import sys
import math
import json
import random
import time
from collections import deque

import torch
import torch.nn as nn
import torch.optim as optim
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QGroupBox, QCheckBox, QTextEdit,
)
from PyQt6.QtCore import QTimer, Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QPainterPath, QLinearGradient,
)

TORCH_DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

random.seed(42)

CANVAS_W = 1100
CANVAS_H = 700


# ═══════════════════════════════════════════════════════════════
# STEP 1: NODE + CONSTRAINT + GRAPH (Data structures)
# ═══════════════════════════════════════════════════════════════

class Node:
    """Step 1+2: A UI panel node with physics state."""

    def __init__(self, node_id, node_type, role, name, x, y, w, h, target_x, target_y):
        self.id = node_id
        self.type = node_type
        self.role = role
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self.vx = 0.0
        self.vy = 0.0
        self.fx = 0.0
        self.fy = 0.0
        self.mass = max(0.5, (w * h) / 4000.0)
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.converged = False
        self.pulse = 0.0
        self.trail = deque(maxlen=20)
        self.bump_flash = 0.0
        self.heat = 0.0
        self.dragging = False

    def rect(self):
        return QRectF(self.x, self.y, self.w, self.h)

    def center(self):
        return (self.x + self.w / 2, self.y + self.h / 2)

    def distance_to_target(self):
        cx, cy = self.center()
        return math.sqrt((cx - self.target_x - self.w / 2) ** 2 + (cy - self.target_y - self.h / 2) ** 2)

    def completeness(self):
        return max(0.0, min(1.0, 1.0 - self.distance_to_target() / 300.0))

    def to_dict(self):
        return {"id": self.id, "type": self.type, "role": self.role, "name": self.name,
                "x": round(self.x, 1), "y": round(self.y, 1), "w": self.w, "h": self.h,
                "target_x": self.target_x, "target_y": self.target_y}


class Constraint:
    """Step 1+2: A docking constraint between nodes or node and region."""

    def __init__(self, a, b, relation, strength=1.0):
        self.a = a
        self.b = b
        self.relation = relation
        self.strength = strength


class Graph:
    """Step 2: Graph memory core — node registry, edge registry, position state."""

    def __init__(self):
        self.nodes = []
        self.constraints = []
        self.node_map = {}

    def add_node(self, node):
        self.nodes.append(node)
        self.node_map[node.id] = node

    def add_constraint(self, constraint):
        self.constraints.append(constraint)

    def get_node(self, node_id):
        return self.node_map.get(node_id)

    def to_json(self):
        return json.dumps({
            "nodes": [n.to_dict() for n in self.nodes],
            "constraints": [{"a": c.a, "b": c.b, "relation": c.relation} for c in self.constraints],
        }, indent=2)


# ═══════════════════════════════════════════════════════════════
# STEP 3: PHYSICS ENGINE (Pure math, no GUI)
# ═══════════════════════════════════════════════════════════════

class PhysicsEngine:
    """Step 3: Force accumulation, velocity update, damping, boundary clamp."""

    def __init__(self):
        self.repulsion_radius = 70
        self.boundary_w = CANVAS_W
        self.boundary_h = CANVAS_H

    def accumulate(self, graph, weights, poles):
        """Accumulate all forces on each node."""
        for n in graph.nodes:
            n.fx = 0.0
            n.fy = 0.0

        for n in graph.nodes:
            cx, cy = n.center()
            tx = n.target_x + n.w / 2
            ty = n.target_y + n.h / 2
            dx = tx - cx
            dy = ty - cy
            n.fx += dx * weights["dock"] / n.mass
            n.fy += dy * weights["dock"] / n.mass

            for pole in poles:
                px, py, charge, radius = pole
                dx = px - cx
                dy = py - cy
                dist = math.sqrt(dx * dx + dy * dy) + 1e-6
                if dist < radius:
                    falloff = 1.0 - (dist / radius)
                    strength = charge * falloff * falloff * weights["attraction"] / n.mass
                    n.fx += (dx / dist) * strength
                    n.fy += (dy / dist) * strength

            for other in graph.nodes:
                if other is n:
                    continue
                ox, oy = other.center()
                dx = cx - ox
                dy = cy - oy
                dist = math.sqrt(dx * dx + dy * dy) + 1e-6
                if dist < self.repulsion_radius:
                    force = weights["repulsion"] / (dist * dist) / n.mass
                    n.fx += (dx / dist) * force
                    n.fy += (dy / dist) * force

            grid = 20
            nx = round(cx / grid) * grid
            ny = round(cy / grid) * grid
            n.fx += (nx - cx) * weights["alignment"] / n.mass
            n.fy += (ny - cy) * weights["alignment"] / n.mass

    def integrate(self, graph, weights):
        """Velocity update + position update."""
        for n in graph.nodes:
            if n.dragging:
                continue
            n.vx += n.fx
            n.vy += n.fy
            n.vx *= weights["damping"]
            n.vy *= weights["damping"]
            n.x += n.vx
            n.y += n.vy

    def clamp(self, graph):
        """Boundary constraints."""
        for n in graph.nodes:
            n.x = max(0, min(self.boundary_w - n.w, n.x))
            n.y = max(0, min(self.boundary_h - n.h, n.y))

    def resolve_collisions(self, graph):
        """Collision resolution — the bumping."""
        count = 0
        for i in range(len(graph.nodes)):
            for j in range(i + 1, len(graph.nodes)):
                a = graph.nodes[i]
                b = graph.nodes[j]
                if a.rect().intersects(b.rect()):
                    ra = a.rect()
                    rb = b.rect()
                    ox = min(ra.right(), rb.right()) - max(ra.left(), rb.left())
                    oy = min(ra.bottom(), rb.bottom()) - max(ra.top(), rb.top())
                    if ox < oy:
                        sign = -1 if a.center()[0] < b.center()[0] else 1
                        a.x += sign * ox / 2
                        b.x -= sign * ox / 2
                        a.vx -= sign * 0.8
                        b.vx += sign * 0.8
                    else:
                        sign = -1 if a.center()[1] < b.center()[1] else 1
                        a.y += sign * oy / 2
                        b.y -= sign * oy / 2
                        a.vy -= sign * 0.8
                        b.vy += sign * 0.8
                    a.bump_flash = 1.0
                    b.bump_flash = 1.0
                    a.heat = min(1.0, a.heat + 0.3)
                    b.heat = min(1.0, b.heat + 0.3)
                    count += 1
        return count


# ═══════════════════════════════════════════════════════════════
# STEP 4: ENERGY SCORER (The brain signal)
# ═══════════════════════════════════════════════════════════════

class EnergyScorer:
    """Step 4: E = overlap + misalignment + dock_distance + motion_instability."""

    def __init__(self):
        self.energy = 0.0
        self.components = {}

    def evaluate(self, graph):
        n = max(1, len(graph.nodes))

        overlap = 0.0
        for i in range(len(graph.nodes)):
            for j in range(i + 1, len(graph.nodes)):
                if graph.nodes[i].rect().intersects(graph.nodes[j].rect()):
                    ra = graph.nodes[i].rect()
                    rb = graph.nodes[j].rect()
                    ox = min(ra.right(), rb.right()) - max(ra.left(), rb.left())
                    oy = min(ra.bottom(), rb.bottom()) - max(ra.top(), rb.top())
                    overlap += (ox * oy) / 1000.0

        misalignment = 0.0
        for node in graph.nodes:
            cx, cy = node.center()
            grid = 20
            misalignment += abs(cx - round(cx / grid) * grid) / 100.0
            misalignment += abs(cy - round(cy / grid) * grid) / 100.0

        dock_distance = sum(node.distance_to_target() for node in graph.nodes) / n / 500.0

        motion = 0.0
        for node in graph.nodes:
            speed = math.sqrt(node.vx ** 2 + node.vy ** 2)
            motion += speed / 50.0
        motion /= n

        usability = sum(node.completeness() for node in graph.nodes) / n

        energy = overlap * 3.0 + misalignment * 0.5 + dock_distance + motion * 0.3 - usability * 2.0
        score = max(0.0, min(1.0, usability - overlap * 0.1))

        self.components = {
            "overlap": overlap * 3.0,
            "misalignment": misalignment * 0.5,
            "dock_distance": dock_distance,
            "motion": motion * 0.3,
            "usability": usability * 2.0,
            "total": energy,
            "score": score,
        }
        self.energy = energy
        return energy


# ═══════════════════════════════════════════════════════════════
# STEP 5: WEIGHT LEARNER (Adaptive forces)
# ═══════════════════════════════════════════════════════════════

class WeightLearner:
    """Step 5: if energy up -> increase penalty, if down -> stabilize."""

    def __init__(self):
        self.weights = {"attraction": 0.08, "repulsion": 1500.0, "alignment": 0.02,
                        "dock": 0.12, "damping": 0.90}
        self.base = dict(self.weights)
        self.effectiveness = {k: 0.5 for k in self.weights}
        self.history = {k: deque(maxlen=15) for k in self.weights}
        self.adjustments = {k: 0 for k in self.weights}
        self.last_energy = 0.0
        self.adaptation_count = 0
        self.think_log = deque(maxlen=12)
        self.active = True

    def learn(self, energy, observations, step):
        """The learning rule."""
        if not self.active:
            return

        delta = self.last_energy - energy
        for k in self.weights:
            self.history[k].append(delta)
            if len(self.history[k]) >= 5:
                avg = sum(self.history[k]) / len(self.history[k])
                if avg > 0:
                    self.effectiveness[k] = min(1.0, self.effectiveness[k] + 0.02)
                else:
                    self.effectiveness[k] = max(0.1, self.effectiveness[k] - 0.03)
        self.last_energy = energy

        changed = []
        for k in self.weights:
            old = self.weights[k]
            if self.effectiveness[k] > 0.6:
                self.weights[k] = min(self.base[k] * 3.0, self.weights[k] * 1.05)
            elif self.effectiveness[k] < 0.3:
                self.weights[k] = max(self.base[k] * 0.1, self.weights[k] * 0.95)
            if abs(old - self.weights[k]) > 0.001:
                self.adjustments[k] += 1
                changed.append(k)

        if changed:
            self.adaptation_count += 1
            parts = ["%s %s" % (k, "up" if self.weights[k] > self.base[k] else "down") for k in changed]
            self.think_log.append("Step %d: adapted %s" % (step, ", ".join(parts)))

        if observations.get("overlap", 0) > 3 and step > 20:
            self.weights["repulsion"] = min(self.base["repulsion"] * 3.0, self.weights["repulsion"] * 1.1)
            self.think_log.append("Step %d: %d overlaps -> boost repulsion to %.0f" % (
                step, observations["overlap"], self.weights["repulsion"]))

        if observations.get("motion", 0) > 20 and step > 30:
            self.weights["attraction"] = max(self.base["attraction"] * 0.1, self.weights["attraction"] * 0.95)
            self.think_log.append("Step %d: motion %.1f -> relax attraction to %.3f" % (
                step, observations["motion"], self.weights["attraction"]))

        score = observations.get("score", 0)
        if score > 0.8 and observations.get("motion", 0) < 2.0 and step > 20:
            self.weights["attraction"] = max(self.base["attraction"] * 0.1, self.weights["attraction"] * 0.98)
            if step % 50 == 0:
                self.think_log.append("Step %d: layout good (score=%.3f) -> stabilize" % (step, score))


# ═══════════════════════════════════════════════════════════════
# STEP 6: ANNEALING SHAKER
# ═══════════════════════════════════════════════════════════════

class AnnealingShaker:
    """Step 6: temperature *= 0.97, noise = random * temperature."""

    def __init__(self):
        self.temperature = 0.0
        self.max_temperature = 25.0
        self.cooling_rate = 0.997
        self.auto_cool = True
        self.shake_frames = 0

    def shake(self, intensity=1.0):
        self.temperature = self.max_temperature * intensity
        self.shake_frames = 60

    def inject_noise(self, nodes):
        if self.temperature < 0.1:
            return
        for n in nodes:
            n.vx += random.uniform(-self.temperature, self.temperature) * 0.3
            n.vy += random.uniform(-self.temperature, self.temperature) * 0.3
            n.heat = min(1.0, n.heat + self.temperature * 0.01)

    def cool(self):
        if self.auto_cool:
            self.temperature *= self.cooling_rate
            if self.temperature < 0.01:
                self.temperature = 0.0
        if self.shake_frames > 0:
            self.shake_frames -= 1

    def phase(self):
        if self.temperature > 10:
            return "HOT"
        elif self.temperature > 1:
            return "COOLING"
        elif self.temperature > 0.01:
            return "COLD"
        return "FROZEN"


# ═══════════════════════════════════════════════════════════════
# STEP 7: VSCode DOCK RULES (Hard constraints — structural truth)
# ═══════════════════════════════════════════════════════════════

class DockRules:
    """Step 7: Fixed structural rules that override physics."""

    def __init__(self):
        self.regions = {
            "top": QRectF(0, 0, CANVAS_W, 50),
            "left": QRectF(0, 50, 150, 500),
            "center": QRectF(150, 50, 600, 500),
            "right": QRectF(750, 50, 200, 500),
            "bottom": QRectF(0, 550, CANVAS_W, 100),
        }
        self.role_to_region = {
            "top": "top", "left": "left", "center": "center",
            "right": "right", "bottom": "bottom",
        }

    def apply(self, graph):
        """Apply hard constraints — force nodes toward their structural region."""
        for node in graph.nodes:
            region_name = self.role_to_region.get(node.role, "center")
            region = self.regions[region_name]
            cx, cy = node.center()
            rx = region.center().x()
            ry = region.center().y()
            dx = rx - cx
            dy = ry - cy
            dist = math.sqrt(dx * dx + dy * dy) + 1e-6
            if dist > 200:
                pull = (dist - 200) * 0.05
                node.vx += (dx / dist) * pull
                node.vy += (dy / dist) * pull


# ═══════════════════════════════════════════════════════════════
# STEP 10: LAYOUT MEMORY (JSON persistence)
# ═══════════════════════════════════════════════════════════════

class LayoutMemory:
    """Step 10: Save/load layout state as JSON."""

    def __init__(self):
        self.saved = {}

    def save(self, graph, weights, energy, name="default"):
        data = {
            "name": name,
            "node_positions": [{"id": n.id, "x": round(n.x, 1), "y": round(n.y, 1)} for n in graph.nodes],
            "weights": dict(weights.weights),
            "final_energy": round(energy, 4),
        }
        self.saved[name] = data
        return json.dumps(data, indent=2)

    def load(self, name="default"):
        return self.saved.get(name)


# ═══════════════════════════════════════════════════════════════
# RL LAYER 0: SYNTHETIC UI GRAPH GENERATOR (training data source)
# ═══════════════════════════════════════════════════════════════

class SyntheticUIGenerator:
    """Generates random VSCode-style UI graphs for RL training episodes.

    Produces varied layouts with different node counts, roles, sizes,
    and constraint patterns so the policy network generalises.
    """

    ROLE_POOL = ["top", "left", "center", "right", "bottom"]
    TYPE_POOL = ["panel", "button", "editor", "toolbar", "terminal", "statusbar", "menubar", "search"]
    NAME_POOL = ["Menu", "Tool", "Search", "Sidebar", "Editor", "Settings", "Tooltips",
                 "Shortcuts", "Theme", "Terminal", "Status", "Help", "About", "Fonts",
                 "Output", "Debug", "Problems", "Explorer", "Git", "Extensions"]

    ROLE_TARGETS = {
        "top": lambda: (random.uniform(10, 800), 5),
        "left": lambda: (5, random.uniform(40, 400)),
        "center": lambda: (random.uniform(150, 400), random.uniform(40, 300)),
        "right": lambda: (random.uniform(750, 850), random.uniform(40, 400)),
        "bottom": lambda: (random.uniform(10, 600), random.uniform(560, 670)),
    }

    ROLE_SIZES = {
        "top": lambda: (random.randint(100, 300), random.randint(25, 40)),
        "left": lambda: (random.randint(100, 180), random.randint(200, 400)),
        "center": lambda: (random.randint(300, 500), random.randint(250, 400)),
        "right": lambda: (random.randint(120, 180), random.randint(40, 120)),
        "bottom": lambda: (random.randint(200, 500), random.randint(60, 100)),
    }

    def __init__(self, min_nodes=6, max_nodes=14):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.episode_count = 0
        self.difficulty = 0
        self.max_difficulty = 3

    def set_difficulty(self, level):
        self.difficulty = max(0, min(self.max_difficulty, level))

    def generate(self):
        """Generate a random UI graph with nodes + constraints.

        Difficulty scales:
          0 = easy (6-8 nodes, 15% constraints, large sizes)
          1 = medium (8-11 nodes, 25% constraints, normal sizes)
          2 = hard (10-14 nodes, 35% constraints, varied sizes)
          3 = expert (12-14 nodes, 45% constraints, small sizes)
        """
        if self.difficulty == 0:
            n_min, n_max, constraint_prob = 6, 8, 0.15
        elif self.difficulty == 1:
            n_min, n_max, constraint_prob = 8, 11, 0.25
        elif self.difficulty == 2:
            n_min, n_max, constraint_prob = 10, 14, 0.35
        else:
            n_min, n_max, constraint_prob = 12, 14, 0.45
        graph = Graph()
        num_nodes = random.randint(n_min, n_max)
        nodes = []

        for i in range(num_nodes):
            role = random.choice(self.ROLE_POOL)
            ntype = random.choice(self.TYPE_POOL)
            name = random.choice(self.NAME_POOL) + str(i)
            w, h = self.ROLE_SIZES[role]()
            tx, ty = self.ROLE_TARGETS[role]()
            x = random.uniform(50, 900)
            y = random.uniform(50, 500)
            node = Node("n%d" % i, ntype, role, name, x, y, w, h, tx, ty)
            nodes.append(node)
            graph.add_node(node)

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if random.random() < constraint_prob:
                    ni = nodes[i]
                    nj = nodes[j]
                    if ni.role == nj.role:
                        rel = "dock_right"
                    elif (ni.role == "left" and nj.role == "center") or (ni.role == "center" and nj.role == "right"):
                        rel = "dock_right"
                    elif (ni.role == "center" and nj.role == "bottom") or (ni.role == "left" and nj.role == "bottom"):
                        rel = "dock_bottom"
                    else:
                        rel = "dock_region"
                    graph.add_constraint(Constraint(ni.id, nj.id, rel))

        self.episode_count += 1
        return graph


# ═══════════════════════════════════════════════════════════════
# RL LAYER 1: GRAPH ENCODER (graph state -> tensor)
# ═══════════════════════════════════════════════════════════════

MAX_NODES = 14

class GraphEncoder:
    """Encodes graph layout state into fixed-size tensor (padded to MAX_NODES).

    Always outputs the same tensor size regardless of actual node count,
    so the model never needs resizing. Unused slots are zero-padded.
    """

    ROLE_EMBED = {"top": [1, 0, 0, 0, 0], "left": [0, 1, 0, 0, 0],
                  "center": [0, 0, 1, 0, 0], "right": [0, 0, 0, 1, 0],
                  "bottom": [0, 0, 0, 0, 1]}

    FEATURES_PER_NODE = 12
    ROLE_DIM = 5

    def __init__(self, num_nodes):
        self.num_nodes = num_nodes
        self.padded_nodes = MAX_NODES
        self.features_per_node = self.FEATURES_PER_NODE
        self.adj_size = MAX_NODES * MAX_NODES

    def encode(self, graph):
        """Convert graph to fixed-size tensor: [node_features padded + adjacency padded]."""
        actual_n = len(graph.nodes)
        node_feat_dim = self.FEATURES_PER_NODE + self.ROLE_DIM
        feats = [0.0] * (MAX_NODES * node_feat_dim)
        for idx, n in enumerate(graph.nodes):
            cx, cy = n.center()
            tx = n.target_x + n.w / 2
            ty = n.target_y + n.h / 2
            dx = tx - cx
            dy = ty - cy
            dist = math.sqrt(dx * dx + dy * dy)
            speed = math.sqrt(n.vx ** 2 + n.vy ** 2)
            overlap_n = 0
            for other in graph.nodes:
                if other.id == n.id:
                    continue
                if n.rect().intersects(other.rect()):
                    overlap_n += 1
            is_docked = 1.0 if n.converged else 0.0
            role_emb = self.ROLE_EMBED.get(n.role, [0, 0, 0, 0, 0])
            node_feats = [
                cx / CANVAS_W, cy / CANVAS_H,
                n.vx / 50.0, n.vy / 50.0,
                dx / 300.0, dy / 300.0,
                dist / 300.0, speed / 50.0,
                n.w / 400.0, n.h / 200.0,
                overlap_n / max(1, actual_n),
                is_docked,
            ]
            base = idx * node_feat_dim
            for k, v in enumerate(node_feats + role_emb):
                feats[base + k] = v
        adj = [0.0] * (MAX_NODES * MAX_NODES)
        for i in range(actual_n):
            for j in range(actual_n):
                if i == j:
                    continue
                ni = graph.nodes[i]
                nj = graph.nodes[j]
                d = math.sqrt((ni.x - nj.x) ** 2 + (ni.y - nj.y) ** 2)
                adj[i * MAX_NODES + j] = min(1.0, 200.0 / (d + 1.0))
        feats.extend(adj)
        return torch.tensor(feats, dtype=torch.float32, device=TORCH_DEVICE)

    def tensor_size(self):
        return MAX_NODES * (self.FEATURES_PER_NODE + self.ROLE_DIM) + self.adj_size


# ═══════════════════════════════════════════════════════════════
# RL LAYER 2: ACTOR-CRITIC NETWORK (policy + value)
# ═══════════════════════════════════════════════════════════════

class ActorCritic(nn.Module):
    """Fixed-size actor-critic: always outputs MAX_NODES actions.

    Caller masks unused action slots. Weights persist across episodes
    with different node counts — no model resizing needed.
    """

    def __init__(self, input_size, num_nodes=MAX_NODES):
        super().__init__()
        self.num_nodes = num_nodes
        hidden = 256
        self.shared = nn.Sequential(
            nn.Linear(input_size, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.actor = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, MAX_NODES * 2),
        )
        self.critic = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )
        self.action_scale = 5.0
        self.log_std = nn.Parameter(torch.zeros(MAX_NODES, 2))

    def forward(self, x):
        shared_out = self.shared(x)
        mean = self.actor(shared_out).view(MAX_NODES, 2) * self.action_scale
        value = self.critic(shared_out).squeeze(-1)
        std = torch.exp(self.log_std)
        return mean, std, value


# ═══════════════════════════════════════════════════════════════
# RL LAYER 3: RL ENVIRONMENT (wraps physics as RL env)
# ═══════════════════════════════════════════════════════════════

class RLEnvironment:
    """Wraps the physics engine as an RL environment: state/action/reward."""

    def __init__(self, graph, poles, physics, scorer, weights, shaker, dock_rules):
        self.graph = graph
        self.poles = poles
        self.physics = physics
        self.scorer = scorer
        self.weights = weights
        self.shaker = shaker
        self.dock_rules = dock_rules
        self.encoder = GraphEncoder(len(graph.nodes))
        self.prev_energy = 0.0
        self.prev_overlap = 0
        self.episode_steps = 0
        self.max_steps = 200
        self.last_reward = 0.0
        self.last_components = {}

    def reset_env(self):
        """Reset to a random layout, return initial state."""
        for n in self.graph.nodes:
            n.x = random.uniform(50, 900)
            n.y = random.uniform(50, 500)
            n.vx = 0
            n.vy = 0
            n.converged = False
            n.trail.clear()
        self.shaker.temperature = self.shaker.max_temperature
        self.episode_steps = 0
        self.scorer.evaluate(self.graph)
        self.prev_energy = self.scorer.energy
        self.prev_overlap = self._count_overlap()
        return self.encoder.encode(self.graph)

    def get_state(self):
        return self.encoder.encode(self.graph)

    def _count_overlap(self):
        overlap = 0
        for i in range(len(self.graph.nodes)):
            for j in range(i + 1, len(self.graph.nodes)):
                if self.graph.nodes[i].rect().intersects(self.graph.nodes[j].rect()):
                    overlap += 1
        return overlap

    def _compute_reward(self):
        """Full reward: -overlap - misalignment - dock_dist + structure + stability."""
        energy = self.scorer.energy
        comp = self.scorer.components
        overlap = self._count_overlap()
        overlap_penalty = -10.0 * overlap
        misalign_penalty = -2.0 * comp.get("misalignment", 0.0)
        dock_penalty = -1.0 * comp.get("dock_distance", 0.0)
        converged = sum(1 for n in self.graph.nodes if n.converged)
        structure_bonus = 20.0 * converged / max(1, len(self.graph.nodes))
        max_vel = max((math.sqrt(nd.vx ** 2 + nd.vy ** 2) for nd in self.graph.nodes), default=0)
        stability_bonus = 5.0 * max(0, 1.0 - max_vel / 20.0)
        energy_delta = -(energy - self.prev_energy)
        overlap_delta = -2.0 * (overlap - self.prev_overlap)
        reward = (overlap_penalty + misalign_penalty + dock_penalty
                  + structure_bonus + stability_bonus + energy_delta + overlap_delta)
        self.prev_energy = energy
        self.prev_overlap = overlap
        self.last_reward = reward
        self.last_components = {
            "overlap_pen": overlap_penalty,
            "misalign_pen": misalign_penalty,
            "dock_pen": dock_penalty,
            "struct_bonus": structure_bonus,
            "stability_bonus": stability_bonus,
            "energy_delta": energy_delta,
            "total": reward,
        }
        return reward

    def apply_action(self, action_tensor):
        """Apply NN-predicted force adjustments to nodes."""
        for i, n in enumerate(self.graph.nodes):
            if n.dragging:
                continue
            dx = action_tensor[i, 0].item()
            dy = action_tensor[i, 1].item()
            n.vx += dx
            n.vy += dy

    def step_env(self, action_tensor):
        """One RL step: apply action, run physics, compute reward."""
        self.apply_action(action_tensor)
        self.physics.accumulate(self.graph, self.weights.weights, self.poles)
        self.shaker.inject_noise(self.graph.nodes)
        self.physics.resolve_collisions(self.graph)
        self.physics.integrate(self.graph, self.weights.weights)
        self.physics.clamp(self.graph)
        self.dock_rules.apply(self.graph)
        self.shaker.cool()

        energy = self.scorer.evaluate(self.graph)
        score = self.scorer.components.get("score", 0.0)
        reward = self._compute_reward()

        overlap = self._count_overlap()
        converged = sum(1 for n in self.graph.nodes if n.converged)
        self.episode_steps += 1

        done = self.episode_steps >= self.max_steps or converged == len(self.graph.nodes)
        return self.get_state(), reward, done, {"energy": energy, "score": score, "overlap": overlap, "converged": converged}

    def current_reward(self):
        """Reward for the current state (used in hybrid mode)."""
        return self._compute_reward()


# ═══════════════════════════════════════════════════════════════
# RL LAYER 4: PPO TRAINER (Proximal Policy Optimization)
# ═══════════════════════════════════════════════════════════════

class PPOTrainer:
    """PPO trainer with advantage estimation, clipped objective, value loss."""

    def __init__(self, env):
        self.env = env
        self.model = ActorCritic(env.encoder.tensor_size(), len(env.graph.nodes)).to(TORCH_DEVICE)
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-4)
        self.gamma = 0.95
        self.gae_lambda = 0.95
        self.clip_epsilon = 0.2
        self.value_coef = 0.5
        self.entropy_coef = 0.01
        self.total_episodes = 0
        self.training = False
        self.loss_history = deque(maxlen=100)
        self.reward_history = deque(maxlen=100)
        self.value_history = deque(maxlen=100)
        self.policy_loss_history = deque(maxlen=100)
        self.current_loss = 0.0
        self.current_episode_reward = 0.0
        self.accumulated_states = []
        self.accumulated_actions = []
        self.accumulated_rewards = []
        self.accumulated_values = []
        self.accumulated_log_probs = []
        self.nn_predictions = None
        self.last_action = None
        self.batch_size = 16

    def predict(self, state_tensor):
        """Get force adjustments from the policy network (with exploration noise)."""
        with torch.no_grad():
            mean, std, value = self.model(state_tensor)
        noise = torch.randn_like(mean) * std
        action = mean + noise
        return action, mean

    def predict_eval(self, state_tensor):
        """Get force adjustments without noise (evaluation mode)."""
        with torch.no_grad():
            mean, std, value = self.model(state_tensor)
        return mean

    def record_transition(self, state, action, reward):
        """Store transition for PPO update."""
        with torch.no_grad():
            mean, std, value = self.model(state)
            dist = torch.distributions.Normal(mean, std)
            log_prob = dist.log_prob(action).sum()
        self.accumulated_states.append(state.detach())
        self.accumulated_actions.append(action.detach())
        self.accumulated_rewards.append(reward)
        self.accumulated_values.append(value.item())
        self.accumulated_log_probs.append(log_prob.item())
        self.current_episode_reward += reward

    def compute_advantages(self):
        """Compute GAE advantages and discounted returns."""
        rewards = self.accumulated_rewards
        values = self.accumulated_values + [0.0]
        advantages = []
        gae = 0.0
        for t in reversed(range(len(rewards))):
            delta = rewards[t] + self.gamma * values[t + 1] - values[t]
            gae = delta + self.gamma * self.gae_lambda * gae
            advantages.insert(0, gae)
        advantages = torch.tensor(advantages, dtype=torch.float32, device=TORCH_DEVICE)
        returns = advantages + torch.tensor(values[:-1], dtype=torch.float32, device=TORCH_DEVICE)
        if advantages.std() > 1e-6:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        return advantages, returns

    def train_step(self):
        """One PPO update with clipped objective + value loss + entropy bonus."""
        if len(self.accumulated_states) < self.batch_size:
            return 0.0
        advantages, returns = self.compute_advantages()
        old_log_probs = torch.tensor(self.accumulated_log_probs, dtype=torch.float32, device=TORCH_DEVICE)
        total_loss = torch.tensor(0.0, device=TORCH_DEVICE)
        n_updates = 0
        for epoch in range(4):
            for start in range(0, len(self.accumulated_states), self.batch_size):
                end = start + self.batch_size
                if end > len(self.accumulated_states):
                    break
                batch_states = torch.stack(self.accumulated_states[start:end])
                batch_actions = torch.stack(self.accumulated_actions[start:end])
                batch_adv = advantages[start:end]
                batch_ret = returns[start:end]
                batch_old_lp = old_log_probs[start:end]
                mean, std, values = self.model(batch_states)
                dist = torch.distributions.Normal(mean, std)
                new_log_probs = dist.log_prob(batch_actions).sum(dim=-1)
                ratio = torch.exp(new_log_probs - batch_old_lp)
                surr1 = ratio * batch_adv
                surr2 = torch.clamp(ratio, 1.0 - self.clip_epsilon, 1.0 + self.clip_epsilon) * batch_adv
                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = self.value_coef * ((values.squeeze(-1) - batch_ret) ** 2).mean()
                entropy = self.entropy_coef * dist.entropy().sum(dim=-1).mean()
                loss = policy_loss + value_loss - entropy
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
                self.optimizer.step()
                total_loss = total_loss + loss.detach()
                n_updates += 1
        avg_loss = (total_loss / max(1, n_updates)).item()
        self.loss_history.append(avg_loss)
        self.reward_history.append(self.current_episode_reward)
        self.value_history.append(returns.mean().item())
        self.policy_loss_history.append(policy_loss.item())
        self.accumulated_states = []
        self.accumulated_actions = []
        self.accumulated_rewards = []
        self.accumulated_values = []
        self.accumulated_log_probs = []
        self.current_episode_reward = 0.0
        self.total_episodes += 1
        self.current_loss = avg_loss
        return avg_loss

    def should_train(self):
        return self.training and len(self.accumulated_states) >= self.batch_size

    def get_metrics(self):
        avg_loss = sum(self.loss_history) / max(1, len(self.loss_history))
        avg_reward = sum(self.reward_history) / max(1, len(self.reward_history))
        avg_value = sum(self.value_history) / max(1, len(self.value_history))
        avg_policy_loss = sum(self.policy_loss_history) / max(1, len(self.policy_loss_history))
        return {
            "episodes": self.total_episodes,
            "loss": self.current_loss,
            "avg_loss": avg_loss,
            "avg_reward": avg_reward,
            "avg_value": avg_value,
            "avg_policy_loss": avg_policy_loss,
            "training": self.training,
            "device": str(TORCH_DEVICE),
            "buffer_size": len(self.accumulated_states),
            "reward_components": self.env.last_components,
        }

    def save_model(self, path="glab_model.pt"):
        torch.save({
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "episodes": self.total_episodes,
            "loss_history": list(self.loss_history),
            "reward_history": list(self.reward_history),
            "value_history": list(self.value_history),
        }, path)
        return path

    def load_model(self, path="glab_model.pt"):
        try:
            checkpoint = torch.load(path, map_location=TORCH_DEVICE)
            self.model.load_state_dict(checkpoint["model_state"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state"])
            self.total_episodes = checkpoint.get("episodes", 0)
            self.loss_history = deque(checkpoint.get("loss_history", []), maxlen=100)
            self.reward_history = deque(checkpoint.get("reward_history", []), maxlen=100)
            self.value_history = deque(checkpoint.get("value_history", []), maxlen=100)
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# RL LAYER 5: TRAINING LOOP (autonomous episode runner)
# ═══════════════════════════════════════════════════════════════

class TrainingLoop:
    """Runs full RL training episodes autonomously.

    Each episode:
      1. Generate synthetic UI graph (or reset current)
      2. Run N steps with PPO policy
      3. Record transitions
      4. Update policy via PPO

    Runs in the GUI timer — one episode step per tick.
    """

    def __init__(self, trainer, generator, brain):
        self.trainer = trainer
        self.generator = generator
        self.brain = brain
        self.auto_train = False
        self.episode_active = False
        self.episode_step = 0
        self.episode_max = 150
        self.episode_reward = 0.0
        self.episode_count = 0
        self.best_reward = -999.0
        self.episode_rewards = deque(maxlen=50)
        self.episode_losses = deque(maxlen=50)
        self.current_episode_graph = None
        self.train_on_episode_end = True
        self.deploy_mode = False
        self.auto_save_interval = 10
        self.model_path = "glab_model.pt"
        self.reward_trend = deque(maxlen=20)

    def start_episode(self):
        """Begin a new training episode with a fresh synthetic graph."""
        self.current_episode_graph = self.generator.generate()
        self.brain.graph = self.current_episode_graph
        self.brain.rl_env.graph = self.current_episode_graph
        self.brain.rl_env.encoder = GraphEncoder(len(self.current_episode_graph.nodes))
        self.trainer.accumulated_states = []
        self.trainer.accumulated_actions = []
        self.trainer.accumulated_rewards = []
        self.trainer.accumulated_values = []
        self.trainer.accumulated_log_probs = []
        self.trainer.env = self.brain.rl_env
        self.brain.rl_env.reset_env()
        self.episode_active = True
        self.episode_step = 0
        self.episode_reward = 0.0
        self.trainer.current_episode_reward = 0.0

    def step_episode(self):
        """Run one step of the current episode."""
        if not self.episode_active:
            return
        state = self.brain.rl_env.get_state()
        action, mean = self.trainer.predict(state)
        self.trainer.last_action = action.cpu().numpy()
        self.trainer.nn_predictions = mean.cpu().numpy()
        next_state, reward, done, info = self.brain.rl_env.step_env(action)
        self.trainer.record_transition(state, action, reward)
        self.episode_reward += reward
        self.episode_step += 1
        if self.trainer.should_train():
            self.trainer.train_step()
        if done or self.episode_step >= self.episode_max:
            self.end_episode()

    def end_episode(self):
        """Finish episode, do final PPO update, log results."""
        if self.trainer.should_train() or len(self.trainer.accumulated_states) >= 5:
            self.trainer.train_step()
        self.episode_rewards.append(self.episode_reward)
        self.reward_trend.append(self.episode_reward)
        self.episode_count += 1
        if self.episode_reward > self.best_reward:
            self.best_reward = self.episode_reward
            self.trainer.save_model(self.model_path)
        self.episode_losses.append(self.trainer.current_loss)
        if self.episode_count % self.auto_save_interval == 0:
            self.trainer.save_model(self.model_path)
        if self.episode_count % 20 == 0 and self.is_learning():
            new_diff = min(self.generator.max_difficulty, self.generator.difficulty + 1)
            self.generator.set_difficulty(new_diff)
        self.episode_active = False

    def deploy(self):
        """Load best model and apply to default VSCode graph."""
        loaded = self.trainer.load_model(self.model_path)
        if not loaded:
            return False
        self.deploy_mode = True
        self.auto_train = False
        self.brain.rl_active = True
        self.brain.rl_trainer.training = False
        return True

    def is_learning(self):
        """Check if reward is trending up over recent episodes."""
        if len(self.reward_trend) < 10:
            return False
        first_half = list(self.reward_trend)[:len(self.reward_trend) // 2]
        second_half = list(self.reward_trend)[len(self.reward_trend) // 2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        return avg_second > avg_first

    def tick(self):
        """Called every GUI frame. Runs one episode step if auto_train is on."""
        if self.auto_train:
            if not self.episode_active:
                self.start_episode()
            self.step_episode()

    def get_metrics(self):
        avg_r = sum(self.episode_rewards) / max(1, len(self.episode_rewards))
        avg_l = sum(self.episode_losses) / max(1, len(self.episode_losses))
        import os
        model_exists = os.path.exists(self.model_path)
        return {
            "auto_train": self.auto_train,
            "episode_active": self.episode_active,
            "episode_step": self.episode_step,
            "episode_max": self.episode_max,
            "episode_count": self.episode_count,
            "episode_reward": self.episode_reward,
            "avg_episode_reward": avg_r,
            "best_reward": self.best_reward,
            "avg_loss": avg_l,
            "graphs_generated": self.generator.episode_count,
            "deploy_mode": self.deploy_mode,
            "is_learning": self.is_learning(),
            "model_saved": model_exists,
            "difficulty": self.generator.difficulty,
            "difficulty_name": ["Easy", "Medium", "Hard", "Expert"][self.generator.difficulty],
        }


# ═══════════════════════════════════════════════════════════════
# STEP 9: BRAIN LOOP (Full cognitive loop)
# ═══════════════════════════════════════════════════════════════

class BrainLoop:
    """Step 9: read graph -> constraints -> physics -> energy -> learn -> anneal -> render."""

    def __init__(self, graph, poles):
        self.graph = graph
        self.poles = poles
        self.physics = PhysicsEngine()
        self.scorer = EnergyScorer()
        self.learner = WeightLearner()
        self.shaker = AnnealingShaker()
        self.dock_rules = DockRules()
        self.memory = LayoutMemory()
        self.rl_env = RLEnvironment(graph, poles, self.physics, self.scorer, self.learner, self.shaker, self.dock_rules)
        self.rl_trainer = PPOTrainer(self.rl_env)
        self.ui_generator = SyntheticUIGenerator(min_nodes=6, max_nodes=14)
        self.training_loop = TrainingLoop(self.rl_trainer, self.ui_generator, self)
        self.rl_active = False
        self.rl_apply_interval = 3
        self.step_count = 0
        self.cognitive_interval = 10
        self.collision_count = 0
        self.current_score = 0.0
        self.all_converged = False
        self.fps = 0.0
        self.fps_frames = 0
        self.fps_last_time = time.time()
        self.wave_time = 0.0
        self.observations = {}

    def step(self):
        self.step_count += 1
        self.collision_count = 0
        self.wave_time += 0.05

        if self.training_loop.auto_train:
            self.training_loop.tick()
            self.scorer.evaluate(self.graph)
            self.current_score = self.scorer.components.get("score", 0.0)
            for n in self.graph.nodes:
                n.pulse = max(0, n.pulse - 0.04)
                n.bump_flash = max(0, n.bump_flash - 0.08)
                n.heat = max(0, n.heat - 0.02)
                if self.step_count % 4 == 0:
                    n.trail.append((n.x + n.w / 2, n.y + n.h / 2))
            self.fps_frames += 1
            now = time.time()
            if now - self.fps_last_time >= 1.0:
                self.fps = self.fps_frames / (now - self.fps_last_time)
                self.fps_frames = 0
                self.fps_last_time = now
            return

        w = self.learner.weights

        self.physics.accumulate(self.graph, w, self.poles)
        self.shaker.inject_noise(self.graph.nodes)
        self.collision_count = self.physics.resolve_collisions(self.graph)
        self.physics.integrate(self.graph, w)
        self.physics.clamp(self.graph)
        self.dock_rules.apply(self.graph)
        self.shaker.cool()

        if self.rl_active and self.step_count % self.rl_apply_interval == 0:
            state = self.rl_env.get_state()
            action, mean = self.rl_trainer.predict(state)
            self.rl_trainer.last_action = action.cpu().numpy()
            self.rl_trainer.nn_predictions = mean.cpu().numpy()
            self.rl_env.apply_action(action)
            reward = self.rl_env.current_reward()
            if self.rl_trainer.training:
                self.rl_trainer.record_transition(state, action, reward)

        if self.rl_trainer.should_train():
            self.rl_trainer.train_step()

        energy = self.scorer.evaluate(self.graph)
        self.current_score = self.scorer.components.get("score", 0.0)

        for n in self.graph.nodes:
            n.pulse = max(0, n.pulse - 0.04)
            n.bump_flash = max(0, n.bump_flash - 0.08)
            n.heat = max(0, n.heat - 0.02)
            if self.step_count % 4 == 0:
                n.trail.append((n.x + n.w / 2, n.y + n.h / 2))
            d = n.distance_to_target()
            speed = math.sqrt(n.vx ** 2 + n.vy ** 2)
            if d < 8 and speed < 1.0 and self.shaker.temperature < 2.0:
                if not n.converged:
                    n.pulse = 1.0
                n.converged = True
            else:
                n.converged = False

        if self.step_count % self.cognitive_interval == 0:
            n_count = max(1, len(self.graph.nodes))
            overlap = 0
            for i in range(len(self.graph.nodes)):
                for j in range(i + 1, len(self.graph.nodes)):
                    if self.graph.nodes[i].rect().intersects(self.graph.nodes[j].rect()):
                        overlap += 1
            max_vel = max((math.sqrt(nd.vx ** 2 + nd.vy ** 2) for nd in self.graph.nodes), default=0)
            self.observations = {
                "overlap": overlap,
                "motion": max_vel,
                "score": self.current_score,
            }
            self.learner.learn(energy, self.observations, self.step_count)

        self.all_converged = all(n.converged for n in self.graph.nodes) and self.step_count > 50

        self.fps_frames += 1
        now = time.time()
        if now - self.fps_last_time >= 1.0:
            self.fps = self.fps_frames / (now - self.fps_last_time)
            self.fps_frames = 0
            self.fps_last_time = now

    def shake(self, intensity=1.0):
        self.shaker.shake(intensity)
        for n in self.graph.nodes:
            n.vx += random.uniform(-self.shaker.temperature, self.shaker.temperature)
            n.vy += random.uniform(-self.shaker.temperature, self.shaker.temperature)
            n.heat = 1.0

    def reset(self):
        for n in self.graph.nodes:
            n.x = random.uniform(50, 900)
            n.y = random.uniform(50, 500)
            n.vx = random.uniform(-10, 10)
            n.vy = random.uniform(-10, 10)
            n.converged = False
            n.pulse = 1.0
            n.trail.clear()
            n.bump_flash = 0.0
            n.heat = 1.0
        self.step_count = 0
        self.shaker.temperature = self.shaker.max_temperature
        self.all_converged = False
        self.shaker.shake_frames = 0
        self.learner.think_log.clear()
        self.learner.adaptation_count = 0
        self.learner.weights = dict(self.learner.base)
        self.learner.effectiveness = {k: 0.5 for k in self.learner.weights}
        self.learner.adjustments = {k: 0 for k in self.learner.weights}
        for k in self.learner.history:
            self.learner.history[k].clear()

    def settle(self):
        for n in self.graph.nodes:
            n.x = n.target_x + random.uniform(-30, 30)
            n.y = n.target_y + random.uniform(-30, 30)
            n.vx = 0
            n.vy = 0
        self.shaker.temperature = 5.0

    def save_layout(self, name="session_1"):
        return self.memory.save(self.graph, self.learner, self.scorer.energy, name)


# ═══════════════════════════════════════════════════════════════
# STEP 8: PYQT RENDERER (Canvas)
# ═══════════════════════════════════════════════════════════════

class Canvas(QWidget):
    """Step 8: PyQt renderer — draws the layout intelligence state."""

    def __init__(self, brain, info_panel):
        super().__init__()
        self.brain = brain
        self.info_panel = info_panel
        self.setMinimumSize(900, 700)
        self.setWindowTitle("Layout Intelligence Engine v12.1 — The PPO Layout Brain")
        self.setMouseTracking(True)
        self.show_trails = True
        self.show_targets = True
        self.show_poles = True
        self.show_containers = True
        self.show_forces = False
        self.show_edges = True
        self.show_nn = True
        self.font_label = QFont("Arial", 8, QFont.Weight.Bold)
        self.font_title = QFont("Arial", 15, QFont.Weight.Bold)
        self.font_small = QFont("Arial", 7)
        self.font_tiny = QFont("Arial", 6)
        self.font_phase = QFont("Arial", 10, QFont.Weight.Bold)
        self.drag_node = None
        self.drag_offset = (0, 0)
        self.mouse_pos = (0, 0)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def tick(self):
        self.brain.step()
        self.update()
        self.info_panel.update()

    def node_color(self, n):
        if n.bump_flash > 0.1:
            f = n.bump_flash
            return QColor(int(255 * f + 80 * (1 - f)), int(180 * f + 200 * (1 - f)), int(50 * f + 100 * (1 - f)))
        if n.converged:
            return QColor(80, 255, 100)
        score = n.completeness()
        r = int(255 * (1 - score))
        g = int(180 * score + 50)
        b = int(80 + 100 * score)
        return QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for n in self.brain.graph.nodes:
                if n.rect().contains(pos):
                    self.drag_node = n
                    n.dragging = True
                    self.drag_offset = (pos.x() - n.x, pos.y() - n.y)
                    return

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.mouse_pos = (pos.x(), pos.y())
        if self.drag_node:
            self.drag_node.x = pos.x() - self.drag_offset[0]
            self.drag_node.y = pos.y() - self.drag_offset[1]
            self.drag_node.vx = 0
            self.drag_node.vy = 0

    def mouseReleaseEvent(self, event):
        if self.drag_node:
            self.drag_node.dragging = False
            self.drag_node = None

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.brain.shake(1.0)
        elif key == Qt.Key.Key_R:
            self.brain.reset()
        elif key == Qt.Key.Key_S:
            self.brain.settle()
        elif key == Qt.Key.Key_F:
            self.show_forces = not self.show_forces
        elif key == Qt.Key.Key_E:
            self.show_edges = not self.show_edges
        elif key == Qt.Key.Key_T:
            self.show_trails = not self.show_trails
        elif key == Qt.Key.Key_G:
            self.show_targets = not self.show_targets
        elif key == Qt.Key.Key_P:
            self.show_poles = not self.show_poles
        elif key == Qt.Key.Key_C:
            self.show_containers = not self.show_containers
        elif key == Qt.Key.Key_N:
            self.show_nn = not self.show_nn
        elif key == Qt.Key.Key_L:
            self.brain.rl_trainer.training = not self.brain.rl_trainer.training
        elif key == Qt.Key.Key_A:
            self.brain.training_loop.auto_train = not self.brain.training_loop.auto_train
            if self.brain.training_loop.auto_train:
                self.brain.rl_active = True
        elif key == Qt.Key.Key_D:
            self.brain.training_loop.deploy()
        elif key == Qt.Key.Key_Escape:
            QApplication.quit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(22, 22, 32))
        gradient.setColorAt(1, QColor(12, 12, 18))
        p.fillRect(self.rect(), QBrush(gradient))

        p.setPen(QPen(QColor(30, 30, 40, 60), 1))
        for x in range(0, self.width(), 20):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 20):
            p.drawLine(0, y, self.width(), y)

        if self.show_containers:
            for name, rect in self.brain.dock_rules.regions.items():
                p.setPen(QPen(QColor(100, 100, 120, 80), 1, Qt.PenStyle.DashLine))
                p.setBrush(QBrush(QColor(40, 50, 70, 20)))
                p.drawRoundedRect(rect, 4, 4)
                p.setFont(self.font_tiny)
                p.setPen(QPen(QColor(100, 120, 140, 120)))
                p.drawText(QPointF(rect.x() + 4, rect.y() + 12), name)

        if self.show_poles:
            for pole in self.brain.poles:
                px, py, charge, radius = pole
                for r_frac in [0.3, 0.6, 0.9]:
                    r = radius * r_frac
                    alpha = int(20 * (1 - r_frac) + 6)
                    c = QColor(80, 180, 255, alpha) if charge > 0 else QColor(255, 80, 80, alpha)
                    p.setPen(QPen(c, 1, Qt.PenStyle.DashLine))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(px, py), r, r)

        if self.show_edges:
            for c in self.brain.graph.constraints:
                a = self.brain.graph.get_node(c.a)
                b_node = self.brain.graph.get_node(c.b)
                if a and b_node:
                    p.setPen(QPen(QColor(100, 150, 200, 60), 1))
                    p.drawLine(QPointF(*a.center()), QPointF(*b_node.center()))
                elif a:
                    region = self.brain.dock_rules.regions.get(c.b)
                    if region:
                        p.setPen(QPen(QColor(100, 150, 200, 40), 1, Qt.PenStyle.DashLine))
                        p.drawLine(QPointF(*a.center()), QPointF(region.center().x(), region.center().y()))

        p.setFont(self.font_title)
        p.setPen(QPen(QColor(220, 220, 240)))
        p.drawText(20, 28, "Layout Intelligence Engine v12.1 — The PPO Layout Brain")

        p.setFont(self.font_small)
        p.setPen(QPen(QColor(140, 140, 160)))
        p.drawText(20, 44, "Stage 2: Hybrid AI — PPO actor-critic on %s" % str(TORCH_DEVICE))

        phase = self.brain.shaker.phase()
        phase_colors = {"HOT": QColor(255, 100, 50), "COOLING": QColor(255, 180, 80),
                        "COLD": QColor(150, 200, 255), "FROZEN": QColor(100, 255, 100)}
        brain_status = "ACTIVE" if self.brain.learner.active else "DORMANT"
        rl_status = "ON" if self.brain.rl_active else "OFF"
        train_status = "TRAINING" if self.brain.rl_trainer.training else "IDLE"
        auto_status = "AUTO" if self.brain.training_loop.auto_train else "MANUAL"
        p.setFont(self.font_phase)
        p.setPen(QPen(phase_colors.get(phase, QColor(200, 200, 200))))
        converged = sum(1 for n in self.brain.graph.nodes if n.converged)
        tl = self.brain.training_loop
        p.drawText(20, 64, "Step: %d  |  %s  |  T=%.1f  |  Score: %.3f  |  Brain: %s  |  RL: %s  |  %s  |  Eps: %d  |  Loss: %.1f  |  %d/%d  |  FPS: %.0f" % (
            self.brain.step_count, phase, self.brain.shaker.temperature,
            self.brain.current_score, brain_status,
            rl_status, auto_status, tl.episode_count, self.brain.rl_trainer.current_loss,
            converged, len(self.brain.graph.nodes), self.brain.fps))

        p.setFont(self.font_tiny)
        p.setPen(QPen(QColor(100, 120, 140)))
        p.drawText(20, 78, "[Space]shake [R]reset [S]settle [F]forces [E]edges [T]trails [G]targets [P]poles [C]containers [N]nn [L]learn [A]auto-train [D]deploy [Esc]quit")

        if self.brain.shaker.shake_frames > 0:
            shake_alpha = int(min(255, self.brain.shaker.shake_frames * 4))
            p.setFont(self.font_title)
            p.setPen(QPen(QColor(255, 100, 50, shake_alpha)))
            p.drawText(self.width() // 2 - 80, 95, "SHAKING!")

        if self.show_poles:
            for pole in self.brain.poles:
                px, py, charge, radius = pole
                color = QColor(80, 180, 255) if charge > 0 else QColor(255, 80, 80)
                symbol = "+" if charge > 0 else "-"
                glow = QRadialGradient(px, py, 22)
                glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 60))
                glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(px, py), 22, 22)
                p.setBrush(QBrush(color))
                p.setPen(QPen(QColor(255, 255, 255), 2))
                p.drawEllipse(QPointF(px, py), 9, 9)
                p.setFont(self.font_label)
                p.setPen(QPen(QColor(255, 255, 255)))
                p.drawText(QPointF(px - 3, py + 3), symbol)

        if self.show_targets:
            for n in self.brain.graph.nodes:
                p.setPen(QPen(QColor(80, 200, 255, 40), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(QRectF(n.target_x, n.target_y, n.w, n.h), 6, 6)

        for n in self.brain.graph.nodes:
            if self.show_trails and len(n.trail) > 1:
                for i in range(1, len(n.trail)):
                    alpha = int(70 * (i / len(n.trail)))
                    p.setPen(QPen(QColor(255, 255, 255, alpha), 1))
                    p.drawLine(QPointF(n.trail[i - 1][0], n.trail[i - 1][1]),
                               QPointF(n.trail[i][0], n.trail[i][1]))

        for n in self.brain.graph.nodes:
            color = self.node_color(n)
            rect = n.rect()

            if n.pulse > 0:
                pr = max(rect.width(), rect.height()) / 2 + n.pulse * 15
                cx, cy = n.center()
                p.setPen(QPen(QColor(255, 255, 255, int(n.pulse * 80)), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), pr, pr)

            if n.heat > 0.1:
                glow = QRadialGradient(rect.center().x(), rect.center().y(), rect.width())
                h_alpha = int(n.heat * 45)
                glow.setColorAt(0, QColor(255, 100, 50, h_alpha))
                glow.setColorAt(1, QColor(255, 100, 50, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(rect.center(), rect.width() * 0.9, rect.height() * 0.9)

            glow2 = QRadialGradient(rect.center().x(), rect.center().y(), rect.width())
            glow2.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 30))
            glow2.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            p.setBrush(QBrush(glow2))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(rect.center(), rect.width() * 0.8, rect.height() * 0.8)

            p.setBrush(QBrush(color))
            border = QColor(255, 255, 255) if n.converged else (QColor(255, 200, 50) if n.dragging else QColor(200, 200, 200))
            p.setPen(QPen(border, 2 if n.converged else 1))
            p.drawRoundedRect(rect, 6, 6)

            p.setFont(self.font_label)
            p.setPen(QPen(QColor(255, 255, 255)))
            text_rect = p.fontMetrics().boundingRect(n.name)
            p.drawText(QPointF(rect.center().x() - text_rect.width() / 2, rect.center().y() + 4), n.name)

            p.setFont(self.font_tiny)
            role_colors = {"top": QColor(150, 200, 255), "left": QColor(255, 200, 150),
                           "center": QColor(200, 255, 200), "right": QColor(255, 180, 220),
                           "bottom": QColor(255, 150, 100)}
            rc = role_colors.get(n.role, QColor(160, 160, 180))
            p.setPen(QPen(rc))
            p.drawText(QPointF(rect.left() + 2, rect.top() + 8), n.role)

            if n.converged:
                p.setPen(QPen(QColor(100, 255, 100)))
                p.drawText(QPointF(rect.left(), rect.bottom() + 9), "LOCKED")
            elif n.completeness() > 0.7:
                p.setPen(QPen(QColor(255, 200, 80)))
                p.drawText(QPointF(rect.left(), rect.bottom() + 9), "NEAR")
            else:
                p.setPen(QPen(QColor(255, 100, 100)))
                p.drawText(QPointF(rect.left(), rect.bottom() + 9), "DRIFTING")

            if n.bump_flash > 0.3:
                p.setPen(QPen(QColor(255, 200, 50, int(n.bump_flash * 255))))
                p.drawText(QPointF(rect.right() + 3, rect.center().y()), "BUMP!")

            if self.show_forces:
                cx, cy = n.center()
                fx, fy = n.fx, n.fy
                fmag = math.sqrt(fx * fx + fy * fy)
                if fmag > 0.1:
                    scale = min(50, fmag * 5) / fmag
                    p.setPen(QPen(QColor(255, 100, 255, 200), 2))
                    p.drawLine(QPointF(cx, cy), QPointF(cx + fx * scale, cy + fy * scale))
                    ax = cx + fx * scale
                    ay = cy + fy * scale
                    p.setBrush(QBrush(QColor(255, 100, 255, 200)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(ax, ay), 3, 3)

        if self.show_nn and self.brain.rl_trainer.nn_predictions is not None:
            preds = self.brain.rl_trainer.nn_predictions
            for i, n in enumerate(self.brain.graph.nodes):
                if i >= len(preds):
                    break
                cx, cy = n.center()
                dx, dy = preds[i]
                fmag = math.sqrt(dx * dx + dy * dy)
                if fmag > 0.1:
                    scale = min(40, fmag * 3) / fmag
                    p.setPen(QPen(QColor(0, 255, 255, 180), 2))
                    p.drawLine(QPointF(cx, cy), QPointF(cx + dx * scale, cy + dy * scale))
                    ax = cx + dx * scale
                    ay = cy + dy * scale
                    p.setBrush(QBrush(QColor(0, 255, 255, 180)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(ax, ay), 3, 3)

        lx = 10
        ly = self.height() - 70
        p.setFont(self.font_small)
        p.setPen(QPen(QColor(160, 160, 180)))
        p.drawText(lx, ly, "LEGEND:")
        items = [
            (QColor(80, 180, 255), "+ pole (attract)"),
            (QColor(255, 80, 80), "- pole (repel)"),
            (QColor(80, 255, 100), "locked (settled)"),
            (QColor(255, 200, 50), "BUMP! / dragging"),
            (QColor(255, 100, 255), "force vector [F]"),
            (QColor(0, 255, 255), "NN prediction [N]"),
        ]
        for i, (c, label) in enumerate(items):
            p.setBrush(QBrush(c))
            p.setPen(QPen(Qt.GlobalColor.white, 1))
            p.drawEllipse(QPointF(lx + 10, ly + 8 + i * 12), 5, 5)
            p.setPen(QPen(QColor(160, 160, 180)))
            p.drawText(lx + 22, ly + 12 + i * 12, label)

        if self.brain.all_converged:
            wave = math.sin(self.brain.wave_time) * 0.5 + 0.5
            alpha = int(150 + 105 * wave)
            p.setFont(self.font_title)
            p.setPen(QPen(QColor(100, 255, 100, alpha)))
            p.drawText(self.width() // 2 - 160, self.height() - 20, "BRAIN CONVERGED — LAYOUT LOCKED")


# ═══════════════════════════════════════════════════════════════
# INFO PANEL (Right side — brain state)
# ═══════════════════════════════════════════════════════════════

class InfoPanel(QWidget):
    """Shows weights, energy, brain log, score chart, JSON preview."""

    def __init__(self, brain):
        super().__init__()
        self.brain = brain
        self.setMinimumWidth(250)
        self.setMaximumWidth(280)
        self.font_small = QFont("Arial", 7)
        self.font_label = QFont("Arial", 9, QFont.Weight.Bold)
        self.font_tiny = QFont("Arial", 6)
        self.score_history = deque(maxlen=200)
        self.energy_history = deque(maxlen=200)
        self.temp_history = deque(maxlen=200)
        self.reward_history = deque(maxlen=200)
        self.value_history = deque(maxlen=200)
        self.show_json = False

    def update_data(self):
        self.score_history.append(self.brain.current_score)
        self.energy_history.append(self.brain.scorer.energy)
        self.temp_history.append(self.brain.shaker.temperature)
        self.reward_history.append(self.brain.rl_env.last_reward)
        if self.brain.rl_trainer.value_history:
            self.value_history.append(self.brain.rl_trainer.value_history[-1])

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(18, 18, 28))
        w = self.width()
        y = 0

        p.setFont(self.font_label)
        p.setPen(QPen(QColor(180, 180, 200)))
        p.drawText(8, y + 16, "Adaptive Weights (Step 5)")
        y += 22

        p.setFont(self.font_small)
        weights = self.brain.learner.weights
        base = self.brain.learner.base
        eff = self.brain.learner.effectiveness
        adj = self.brain.learner.adjustments
        for key in weights:
            p.setPen(QPen(QColor(160, 160, 180)))
            p.drawText(8, y, "%s:" % key)
            bar_x = 60
            bar_w = 100
            ratio = weights[key] / (base[key] * 3.0) if base[key] > 0 else 0
            ratio = max(0.0, min(1.0, ratio))
            fill_w = int(bar_w * ratio)
            c = QColor(80, 255, 100) if eff[key] > 0.6 else (QColor(255, 200, 80) if eff[key] > 0.3 else QColor(255, 100, 100))
            p.setPen(QPen(QColor(60, 60, 60), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(bar_x, y - 8, bar_w, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(c))
            p.drawRect(bar_x, y - 8, fill_w, 7)
            p.setPen(QPen(QColor(160, 160, 180)))
            val_str = "%.3f" % weights[key] if weights[key] < 1 else "%.0f" % weights[key]
            p.drawText(bar_x + bar_w + 4, y, "%s eff=%.0f%% adj=%d" % (val_str, eff[key] * 100, adj[key]))
            y += 12
        y += 6

        p.setFont(self.font_label)
        p.setPen(QPen(QColor(180, 180, 200)))
        p.drawText(8, y, "Energy Breakdown (Step 4)")
        y += 16

        p.setFont(self.font_small)
        comp = self.brain.scorer.components
        items = [
            ("overlap", comp.get("overlap", 0), QColor(255, 80, 80)),
            ("misalign", comp.get("misalignment", 0), QColor(255, 180, 80)),
            ("dock_dist", comp.get("dock_distance", 0), QColor(255, 120, 120)),
            ("motion", comp.get("motion", 0), QColor(200, 150, 255)),
            ("usability", comp.get("usability", 0), QColor(80, 255, 100)),
        ]
        max_val = max(abs(v) for _, v, _ in items) + 1e-6
        for label, val, color in items:
            p.setPen(QPen(QColor(160, 160, 180)))
            p.drawText(8, y, "%s:" % label)
            bar_x = 60
            bar_w = 100
            ratio = min(1.0, abs(val) / max_val)
            fill_w = int(bar_w * ratio)
            p.setPen(QPen(QColor(60, 60, 60), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(bar_x, y - 8, bar_w, 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRect(bar_x, y - 8, fill_w, 6)
            p.setPen(QPen(QColor(160, 160, 180)))
            p.drawText(bar_x + bar_w + 4, y, "%.2f" % val)
            y += 10
        p.setPen(QPen(QColor(100, 200, 255)))
        p.drawText(8, y, "TOTAL: %.2f  SCORE: %.3f" % (comp.get("total", 0), comp.get("score", 0)))
        y += 14

        p.setFont(self.font_label)
        p.setPen(QPen(QColor(180, 180, 200)))
        p.drawText(8, y, "Brain Thought Log (Step 9)")
        y += 14

        p.setFont(self.font_tiny)
        log = list(self.brain.learner.think_log)
        for i, thought in enumerate(log[-6:]):
            alpha = int(100 + 155 * (i / max(1, len(log[-6:]))))
            p.setPen(QPen(QColor(100, 220, 255, alpha)))
            p.drawText(8, y, thought[:45])
            y += 10
        y += 4

        rl_metrics = self.brain.rl_trainer.get_metrics()
        p.setFont(self.font_label)
        p.setPen(QPen(QColor(0, 255, 255)))
        p.drawText(8, y, "PPO Actor-Critic (%s)" % rl_metrics["device"])
        y += 14

        p.setFont(self.font_small)
        p.setPen(QPen(QColor(160, 160, 180)))
        p.drawText(8, y, "Eps: %d  Buf: %d  Loss: %.2f" % (
            rl_metrics["episodes"], rl_metrics["buffer_size"], rl_metrics["avg_loss"]))
        y += 10
        p.drawText(8, y, "Reward: %.3f  Value: %.3f  PLoss: %.3f" % (
            rl_metrics["avg_reward"], rl_metrics["avg_value"], rl_metrics["avg_policy_loss"]))
        y += 10
        train_color = QColor(0, 255, 100) if rl_metrics["training"] else QColor(160, 160, 180)
        p.setPen(QPen(train_color))
        p.drawText(8, y, "Training: %s  RL Active: %s" % (
            "ON" if rl_metrics["training"] else "OFF",
            "ON" if self.brain.rl_active else "OFF"))
        y += 12

        rc = rl_metrics.get("reward_components", {})
        if rc:
            p.setFont(self.font_tiny)
            p.setPen(QPen(QColor(255, 100, 100)))
            p.drawText(8, y, "overlap: %.1f" % rc.get("overlap_pen", 0))
            y += 8
            p.setPen(QPen(QColor(255, 180, 80)))
            p.drawText(8, y, "misalign: %.1f  dock: %.1f" % (
                rc.get("misalign_pen", 0), rc.get("dock_pen", 0)))
            y += 8
            p.setPen(QPen(QColor(80, 255, 100)))
            p.drawText(8, y, "struct: +%.1f  stab: +%.1f" % (
                rc.get("struct_bonus", 0), rc.get("stability_bonus", 0)))
            y += 8
            p.setPen(QPen(QColor(0, 255, 255)))
            p.drawText(8, y, "R_total: %.3f" % rc.get("total", 0))
            y += 10

        tl_metrics = self.brain.training_loop.get_metrics()
        p.setFont(self.font_label)
        tl_label = "Training Loop %s" % ("[AUTO]" if tl_metrics["auto_train"] else ("[DEPLOY]" if tl_metrics["deploy_mode"] else "[OFF]"))
        tl_color = QColor(255, 200, 0) if tl_metrics["auto_train"] else (QColor(100, 255, 200) if tl_metrics["deploy_mode"] else QColor(160, 160, 180))
        p.setPen(QPen(tl_color))
        p.drawText(8, y, tl_label)
        y += 14
        p.setFont(self.font_small)
        p.setPen(QPen(QColor(160, 160, 180)))
        p.drawText(8, y, "Ep: %d  Step: %d/%d  Graphs: %d" % (
            tl_metrics["episode_count"], tl_metrics["episode_step"],
            tl_metrics["episode_max"], tl_metrics["graphs_generated"]))
        y += 10
        p.drawText(8, y, "R_ep: %.2f  R_avg: %.2f  R_best: %.2f" % (
            tl_metrics["episode_reward"], tl_metrics["avg_episode_reward"],
            tl_metrics["best_reward"]))
        y += 10
        learn_color = QColor(0, 255, 100) if tl_metrics["is_learning"] else QColor(255, 160, 80)
        p.setPen(QPen(learn_color))
        learn_str = "LEARNING" if tl_metrics["is_learning"] else "exploring..."
        model_str = "Model saved" if tl_metrics["model_saved"] else "no model yet"
        p.drawText(8, y, "%s  |  %s" % (learn_str, model_str))
        y += 10
        diff_colors = [QColor(100, 255, 100), QColor(255, 200, 80), QColor(255, 120, 80), QColor(255, 80, 80)]
        p.setPen(QPen(diff_colors[tl_metrics["difficulty"]]))
        p.drawText(8, y, "Difficulty: %s" % tl_metrics["difficulty_name"])
        y += 12

        ep_rewards = list(self.brain.training_loop.episode_rewards)
        if len(ep_rewards) >= 2:
            p.setFont(self.font_label)
            p.setPen(QPen(QColor(180, 180, 200)))
            p.drawText(8, y, "Episode Reward History")
            y += 14
            chart_h = 40
            chart_w = w - 16
            min_r = min(ep_rewards)
            max_r = max(ep_rewards)
            range_r = max_r - min_r + 1e-6
            p.setPen(QPen(QColor(0, 255, 200, 180), 2))
            for i in range(1, len(ep_rewards)):
                x1 = 8 + (i - 1) * chart_w / max(1, len(ep_rewards) - 1)
                x2 = 8 + i * chart_w / max(1, len(ep_rewards) - 1)
                y1 = y + chart_h - (ep_rewards[i - 1] - min_r) / range_r * chart_h
                y2 = y + chart_h - (ep_rewards[i] - min_r) / range_r * chart_h
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            p.setPen(QPen(QColor(100, 100, 120)))
            p.drawLine(QPointF(8, y + chart_h), QPointF(8 + chart_w, y + chart_h))
            best_y = y + chart_h - (self.brain.training_loop.best_reward - min_r) / range_r * chart_h
            p.setPen(QPen(QColor(255, 255, 100, 120), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(8, best_y), QPointF(8 + chart_w, best_y))
            y += chart_h + 6

        p.setFont(self.font_label)
        p.setPen(QPen(QColor(180, 180, 200)))
        p.drawText(8, y, "Score / Energy / Temp / Reward")
        y += 14

        if len(self.score_history) >= 2:
            chart_h = 50
            chart_w = w - 16
            max_e = max(abs(v) for v in self.energy_history) + 1e-8
            max_t = max(self.temp_history) + 1e-8
            max_r = max(abs(v) for v in self.reward_history) + 1e-8 if self.reward_history else 1.0
            n = len(self.score_history)
            for history, max_val, color in [
                (self.energy_history, max_e, QColor(100, 200, 255)),
                (self.temp_history, max_t, QColor(255, 180, 80)),
                (self.score_history, 1.0, QColor(80, 255, 100)),
                (self.reward_history, max_r, QColor(0, 255, 255)),
            ]:
                path = QPainterPath()
                for i in range(n):
                    px = 8 + (i / max(1, n - 1)) * chart_w
                    py = y + chart_h - (history[i] / max_val) * chart_h
                    if i == 0:
                        path.moveTo(px, py)
                    else:
                        path.lineTo(px, py)
                p.setPen(QPen(color, 2))
                p.drawPath(path)
            y += chart_h + 6

        p.setFont(self.font_label)
        p.setPen(QPen(QColor(180, 180, 200)))
        p.drawText(8, y, "JSON Output (Step 10 — persistence)")
        y += 14

        p.setFont(self.font_tiny)
        p.setPen(QPen(QColor(120, 200, 120)))
        json_str = self.brain.graph.to_json()[:600]
        lines = json_str.split("\n")
        for line in lines[-8:]:
            p.drawText(8, y, line[:38])
            y += 9


# ═══════════════════════════════════════════════════════════════
# CONTROL PANEL
# ═══════════════════════════════════════════════════════════════

class ControlPanel(QGroupBox):
    """Controls for all steps + RL layer."""

    def __init__(self, callbacks):
        super().__init__("Controls — Physics + RL")
        self.setFont(QFont("Arial", 9))
        layout = QVBoxLayout()

        shake_btn = QPushButton("SHAKE [Space]")
        shake_btn.setMinimumHeight(35)
        shake_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 12px; background-color: #ff6600; color: white; border-radius: 6px; }")
        shake_btn.clicked.connect(callbacks["shake"])
        layout.addWidget(shake_btn)

        self.brain_check = QCheckBox("Brain Active (heuristic)")
        self.brain_check.setChecked(True)
        self.brain_check.toggled.connect(callbacks["brain"])
        layout.addWidget(self.brain_check)

        self.rl_check = QCheckBox("RL Policy Active [N]")
        self.rl_check.toggled.connect(callbacks["rl"])
        layout.addWidget(self.rl_check)

        self.train_check = QCheckBox("RL Training [L]")
        self.train_check.toggled.connect(callbacks["train"])
        layout.addWidget(self.train_check)

        self.auto_train_check = QCheckBox("Auto-Train Episodes [A]")
        self.auto_train_check.toggled.connect(callbacks["autotrain"])
        layout.addWidget(self.auto_train_check)

        self.auto_cool = QCheckBox("Auto-Cool (Step 6)")
        self.auto_cool.setChecked(True)
        self.auto_cool.toggled.connect(callbacks["autocool"])
        layout.addWidget(self.auto_cool)

        self.show_forces = QCheckBox("Force Vectors [F]")
        self.show_forces.toggled.connect(callbacks["forces"])
        layout.addWidget(self.show_forces)

        self.show_nn = QCheckBox("NN Predictions [N]")
        self.show_nn.setChecked(True)
        self.show_nn.toggled.connect(callbacks["nn"])
        layout.addWidget(self.show_nn)

        self.show_edges = QCheckBox("Dock Edges [E]")
        self.show_edges.setChecked(True)
        self.show_edges.toggled.connect(callbacks["edges"])
        layout.addWidget(self.show_edges)

        self.show_containers = QCheckBox("Dock Regions [C]")
        self.show_containers.setChecked(True)
        self.show_containers.toggled.connect(callbacks["containers"])
        layout.addWidget(self.show_containers)

        self.show_poles = QCheckBox("Magnetic Poles [P]")
        self.show_poles.setChecked(True)
        self.show_poles.toggled.connect(callbacks["poles"])
        layout.addWidget(self.show_poles)

        self.show_trails = QCheckBox("Trails [T]")
        self.show_trails.setChecked(True)
        self.show_trails.toggled.connect(callbacks["trails"])
        layout.addWidget(self.show_trails)

        self.show_targets = QCheckBox("Targets [G]")
        self.show_targets.setChecked(True)
        self.show_targets.toggled.connect(callbacks["targets"])
        layout.addWidget(self.show_targets)

        cog_row = QHBoxLayout()
        cog_row.addWidget(QLabel("Think every:"))
        self.cog_slider = QSlider(Qt.Orientation.Horizontal)
        self.cog_slider.setRange(1, 50)
        self.cog_slider.setValue(10)
        self.cog_slider.valueChanged.connect(callbacks["cog"])
        self.cog_label = QLabel("10")
        self.cog_label.setMinimumWidth(30)
        cog_row.addWidget(self.cog_slider)
        cog_row.addWidget(self.cog_label)
        layout.addLayout(cog_row)

        cool_row = QHBoxLayout()
        cool_row.addWidget(QLabel("Cooling:"))
        self.cool_slider = QSlider(Qt.Orientation.Horizontal)
        self.cool_slider.setRange(900, 999)
        self.cool_slider.setValue(997)
        self.cool_slider.valueChanged.connect(callbacks["cool"])
        self.cool_label = QLabel("0.997")
        self.cool_label.setMinimumWidth(40)
        cool_row.addWidget(self.cool_slider)
        cool_row.addWidget(self.cool_label)
        layout.addLayout(cool_row)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save JSON")
        save_btn.clicked.connect(callbacks["save"])
        btn_row.addWidget(save_btn)
        reset_btn = QPushButton("Reset [R]")
        reset_btn.clicked.connect(callbacks["reset"])
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        settle_btn = QPushButton("Drop to Target [S]")
        settle_btn.clicked.connect(callbacks["settle"])
        layout.addWidget(settle_btn)

        self.setLayout(layout)
        self.setMaximumWidth(250)


# ═══════════════════════════════════════════════════════════════
# GRAPH BUILDER (Step 1 — JSON input format)
# ═══════════════════════════════════════════════════════════════

def load_graph_from_json(json_str):
    """Step 1: Load UI graph from JSON description."""
    data = json.loads(json_str)
    graph = Graph()
    for nd in data.get("nodes", []):
        node = Node(
            nd["id"], nd.get("type", "panel"), nd.get("role", "center"),
            nd.get("name", nd["id"]),
            nd.get("x", 100), nd.get("y", 100),
            nd.get("w", 150), nd.get("h", 50),
            nd.get("target_x", nd.get("x", 100)), nd.get("target_y", nd.get("y", 100)),
        )
        graph.add_node(node)
    for c in data.get("constraints", []):
        graph.add_constraint(Constraint(c["a"], c["b"], c.get("relation", "dock")))
    return graph


def build_default_graph():
    """Build the default VSCode-style layout graph."""
    graph = Graph()

    nodes_data = [
        ("menubar", "menubar", "top", "MenuBar", 50, 50, 200, 30, 10, 5),
        ("toolbar", "toolbar", "top", "Toolbar", 300, 50, 250, 35, 220, 5),
        ("search", "search", "top", "Search", 600, 50, 180, 30, 800, 5),
        ("sidebar", "sidebar", "left", "Sidebar", 50, 200, 120, 300, 5, 50),
        ("editor", "editor", "center", "Editor", 200, 200, 400, 300, 150, 50),
        ("settings", "panel", "right", "Settings", 700, 200, 150, 60, 760, 50),
        ("tooltips", "panel", "right", "Tooltips", 700, 300, 150, 50, 760, 120),
        ("shortcuts", "panel", "right", "Shortcuts", 700, 400, 150, 50, 760, 190),
        ("theme", "panel", "right", "Theme", 700, 500, 150, 50, 760, 260),
        ("terminal", "terminal", "bottom", "Terminal", 50, 550, 400, 80, 150, 560),
        ("statusbar", "statusbar", "bottom", "StatusBar", 500, 550, 300, 25, 10, 660),
        ("help", "statusbar", "bottom", "Help", 300, 550, 120, 40, 560, 660),
        ("about", "statusbar", "bottom", "About", 450, 550, 100, 40, 700, 660),
        ("fonts", "statusbar", "bottom", "Fonts", 600, 550, 80, 40, 820, 660),
    ]

    for nid, ntype, role, name, x, y, w, h, tx, ty in nodes_data:
        graph.add_node(Node(nid, ntype, role, name, x, y, w, h, tx, ty))

    constraints = [
        ("menubar", "toolbar", "dock_right"),
        ("toolbar", "search", "dock_right"),
        ("sidebar", "editor", "dock_right"),
        ("editor", "settings", "dock_right"),
        ("terminal", "statusbar", "dock_right"),
        ("sidebar", "terminal", "dock_bottom"),
        ("editor", "terminal", "dock_bottom"),
        ("menubar", "top", "dock_region"),
        ("toolbar", "top", "dock_region"),
        ("search", "top", "dock_region"),
        ("sidebar", "left", "dock_region"),
        ("editor", "center", "dock_region"),
        ("settings", "right", "dock_region"),
        ("tooltips", "right", "dock_region"),
        ("shortcuts", "right", "dock_region"),
        ("theme", "right", "dock_region"),
        ("terminal", "bottom", "dock_region"),
        ("statusbar", "bottom", "dock_region"),
    ]
    for a, b, rel in constraints:
        graph.add_constraint(Constraint(a, b, rel))

    return graph


def build_poles():
    return [
        (500, -50, 5.0, 300),
        (500, 750, 5.0, 300),
        (-50, 350, 4.0, 300),
        (400, 350, 3.0, 250),
        (800, 200, 2.0, 200),
        (500, 400, -1.5, 150),
    ]


# ═══════════════════════════════════════════════════════════════
# MAIN (Step 8+9 — connect everything)
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)

    graph = build_default_graph()
    poles = build_poles()
    brain = BrainLoop(graph, poles)

    for n in graph.nodes:
        n.x = random.uniform(50, 900)
        n.y = random.uniform(50, 500)
        n.vx = random.uniform(-10, 10)
        n.vy = random.uniform(-10, 10)
    brain.shaker.temperature = brain.shaker.max_temperature

    info_panel = InfoPanel(brain)
    canvas = Canvas(brain, info_panel)

    def on_shake():
        brain.shake(1.0)

    def on_brain(checked):
        brain.learner.active = checked

    def on_autocool(checked):
        brain.shaker.auto_cool = checked

    def on_cool(val):
        brain.shaker.cooling_rate = val / 1000.0
        panel.cool_label.setText("%.3f" % brain.shaker.cooling_rate)

    def on_cog(val):
        brain.cognitive_interval = val
        panel.cog_label.setText(str(val))

    def on_forces(checked):
        canvas.show_forces = checked
        panel.show_forces.setChecked(checked)

    def on_nn(checked):
        canvas.show_nn = checked
        panel.show_nn.setChecked(checked)

    def on_rl(checked):
        brain.rl_active = checked

    def on_train(checked):
        brain.rl_trainer.training = checked

    def on_autotrain(checked):
        brain.training_loop.auto_train = checked
        if checked:
            brain.rl_active = True
            brain.rl_trainer.training = True
            panel.train_check.setChecked(True)
            panel.rl_check.setChecked(True)

    def on_edges(checked):
        canvas.show_edges = checked

    def on_poles(checked):
        canvas.show_poles = checked

    def on_trails(checked):
        canvas.show_trails = checked

    def on_targets(checked):
        canvas.show_targets = checked

    def on_containers(checked):
        canvas.show_containers = checked

    def on_reset():
        brain.reset()
        info_panel.score_history.clear()
        info_panel.energy_history.clear()
        info_panel.temp_history.clear()

    def on_settle():
        brain.settle()

    def on_save():
        brain.save_layout("session_1")

    panel = ControlPanel({
        "shake": on_shake, "brain": on_brain, "autocool": on_autocool,
        "cool": on_cool, "cog": on_cog, "forces": on_forces,
        "nn": on_nn, "rl": on_rl, "train": on_train,
        "autotrain": on_autotrain,
        "edges": on_edges, "poles": on_poles, "trails": on_trails,
        "targets": on_targets, "containers": on_containers,
        "reset": on_reset, "settle": on_settle, "save": on_save,
    })

    update_timer = QTimer()
    update_timer.timeout.connect(info_panel.update_data)
    update_timer.start(100)

    window = QWidget()
    window.setWindowTitle("Layout Intelligence Engine v12.1 — The PPO Layout Brain")
    window.setMinimumSize(1300, 850)

    layout = QHBoxLayout()
    layout.addWidget(canvas, 1)

    right = QVBoxLayout()
    right.setSpacing(3)
    right.addWidget(panel)
    right.addWidget(info_panel, 1)
    layout.addLayout(right)

    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
