#!/usr/bin/env python3
#[@GHOST]{[@file<layout_brain_transformer.py>][@state<experimental>][@date<2026-06-28>][@ver<1.0>][@auth<cascade>]}
#[@VBSTYLE]{[@auth<cascade>][@role<transformer_rl_brain>][@return<Tuple3>][@no<decorators|print|hardcoded_paths|tabs>]}
#[@SUMMARY]{Experimental transformer-based layout brain. Variable-size graph actor-critic, multi-head self-attention, curriculum training, dense reward shaping. Headless trainer that exports a policy for the GUI.}
#[@CLASS]{GraphNode VariableGraph TransformerActorCritic LayoutEnv CurriculumGenerator TransformerTrainer}
#[@METHOD]{Run encode forward step reset reward train evaluate save load main}

"""
Layout Brain Transformer — experimental variable-size RL agent.

Push goals:
  - Variable-size graphs via transformer attention.
  - Curriculum learning: easy -> hard layouts.
  - Dense reward shaping: every step gives a meaningful signal.
  - PPO-style clipped objective for stable training.
  - MPS GPU support.

Run: python3 layout_brain_transformer.py
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

TORCH_DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

CANVAS_W = 1000
CANVAS_H = 700


# ═══════════════════════════════════════════════════════════════
# GRAPH NODE
# ═══════════════════════════════════════════════════════════════

class GraphNode:
    """A node in a variable-size layout graph."""

    def __init__(self, node_id, node_type, role, x, y, w, h, target_x, target_y):
        self.id = node_id
        self.type = node_type
        self.role = role
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.vx = 0.0
        self.vy = 0.0

    def center(self):
        return self.x + self.w / 2.0, self.y + self.h / 2.0

    def rect(self):
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


# ═══════════════════════════════════════════════════════════════
# VARIABLE GRAPH
# ═══════════════════════════════════════════════════════════════

class VariableGraph:
    """Container for a variable number of nodes."""

    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)


# ═══════════════════════════════════════════════════════════════
# TRANSFORMER ACTOR-CRITIC
# ═══════════════════════════════════════════════════════════════

class TransformerActorCritic(nn.Module):
    """Transformer policy for variable-size graphs. Outputs per-node actions and a value."""

    def __init__(self, node_feature_dim, hidden_dim, num_heads, num_layers):
        super().__init__()
        self.node_feature_dim = node_feature_dim
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.input_proj = nn.Linear(node_feature_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.actor_mean = nn.Linear(hidden_dim, 2)
        self.actor_logstd = nn.Parameter(torch.zeros(1, 1, 2))
        self.critic = nn.Linear(hidden_dim, 1)
        self.action_scale = 15.0

    def forward(self, node_features):
        """node_features: [batch, num_nodes, feature_dim]."""
        x = self.input_proj(node_features)
        x = self.transformer(x)
        mean = torch.tanh(self.actor_mean(x)) * self.action_scale
        logstd = self.actor_logstd.expand(x.size(0), x.size(1), 2)
        std = torch.exp(logstd)
        value = self.critic(x).mean(dim=1)
        return mean, std, value


# ═══════════════════════════════════════════════════════════════
# LAYOUT ENVIRONMENT
# ═══════════════════════════════════════════════════════════════

class LayoutEnv:
    """Variable-size layout RL environment with simple physics."""

    ROLE_TARGETS = {
        "top": lambda: (random.uniform(10, CANVAS_W - 300), 5),
        "left": lambda: (5, random.uniform(40, CANVAS_H - 250)),
        "center": lambda: (random.uniform(150, CANVAS_W - 400), random.uniform(40, CANVAS_H - 300)),
        "right": lambda: (random.uniform(CANVAS_W - 220, CANVAS_W - 180), random.uniform(40, CANVAS_H - 250)),
        "bottom": lambda: (random.uniform(10, CANVAS_W - 300), random.uniform(CANVAS_H - 120, CANVAS_H - 60)),
    }

    ROLE_SIZES = {
        "top": lambda: (random.randint(200, 600), random.randint(30, 50)),
        "left": lambda: (random.randint(150, 250), random.randint(250, 500)),
        "center": lambda: (random.randint(300, 600), random.randint(300, 500)),
        "right": lambda: (random.randint(150, 220), random.randint(200, 400)),
        "bottom": lambda: (random.randint(300, 700), random.randint(60, 120)),
    }

    NODE_FEATURE_DIM = 17
    ROLE_ENCODING = {
        "top": [1, 0, 0, 0, 0],
        "left": [0, 1, 0, 0, 0],
        "center": [0, 0, 1, 0, 0],
        "right": [0, 0, 0, 1, 0],
        "bottom": [0, 0, 0, 0, 1],
    }

    def __init__(self):
        self.graph = None
        self.prev_energy = 0.0
        self.step_count = 0
        self.max_steps = 100

    def make_node_features(self):
        """Create [num_nodes, feature_dim] tensor."""
        feats = []
        for n in self.graph.nodes:
            cx, cy = n.center()
            dx = n.target_x - n.x
            dy = n.target_y - n.y
            dist = math.sqrt(dx * dx + dy * dy)
            speed = math.sqrt(n.vx * n.vx + n.vy * n.vy)
            role_emb = self.ROLE_ENCODING.get(n.role, [0, 0, 0, 0, 0])
            node_feats = [
                n.x / CANVAS_W, n.y / CANVAS_H,
                n.vx / 50.0, n.vy / 50.0,
                n.target_x / CANVAS_W, n.target_y / CANVAS_H,
                dx / 300.0, dy / 300.0, dist / 300.0, speed / 50.0,
                n.w / CANVAS_W, n.h / CANVAS_H,
            ]
            node_feats.extend(role_emb)
            feats.append(node_feats)
        return torch.tensor(feats, dtype=torch.float32, device=TORCH_DEVICE)

    def reset(self, graph):
        """Reset environment to a new graph."""
        self.graph = graph
        for n in self.graph.nodes:
            n.x = random.uniform(50, CANVAS_W - n.w - 50)
            n.y = random.uniform(50, CANVAS_H - n.h - 50)
            n.vx = 0.0
            n.vy = 0.0
        self.prev_energy = self.compute_energy()
        self.step_count = 0
        return self.make_node_features()

    def compute_energy(self):
        """Lower energy = better layout."""
        nodes = self.graph.nodes
        overlap_cost = 0.0
        misalign_cost = 0.0
        bound_cost = 0.0
        for i in range(len(nodes)):
            n = nodes[i]
            dx = n.target_x - n.x
            dy = n.target_y - n.y
            misalign_cost += math.sqrt(dx * dx + dy * dy) * 0.01
            if n.x < 0:
                bound_cost += abs(n.x) * 0.1
            if n.y < 0:
                bound_cost += abs(n.y) * 0.1
            if n.x + n.w > CANVAS_W:
                bound_cost += (n.x + n.w - CANVAS_W) * 0.1
            if n.y + n.h > CANVAS_H:
                bound_cost += (n.y + n.h - CANVAS_H) * 0.1
            for j in range(i + 1, len(nodes)):
                m = nodes[j]
                ox = max(0.0, min(n.x + n.w, m.x + m.w) - max(n.x, m.x))
                oy = max(0.0, min(n.y + n.h, m.y + m.h) - max(n.y, m.y))
                overlap_cost += ox * oy * 0.001
        return overlap_cost + misalign_cost + bound_cost

    def apply_physics(self):
        """One tick of simple deterministic physics."""
        for n in self.graph.nodes:
            dx = n.target_x - n.x
            dy = n.target_y - n.y
            n.vx += dx * 0.005
            n.vy += dy * 0.005
            n.vx *= 0.9
            n.vy *= 0.9
            n.x += n.vx
            n.y += n.vy
            n.x = max(0, min(n.x, CANVAS_W - n.w))
            n.y = max(0, min(n.y, CANVAS_H - n.h))

    def step(self, action):
        """Apply action as velocity impulses, run physics, compute reward."""
        for i, n in enumerate(self.graph.nodes):
            n.vx += float(action[i, 0]) * 0.5
            n.vy += float(action[i, 1]) * 0.5
        self.apply_physics()
        energy = self.compute_energy()
        reward = self.prev_energy - energy
        self.prev_energy = energy
        self.step_count += 1
        done = self.step_count >= self.max_steps or energy < 0.5
        return self.make_node_features(), reward, done, {"energy": energy}


# ═══════════════════════════════════════════════════════════════
# CURRICULUM GENERATOR
# ═══════════════════════════════════════════════════════════════

class CurriculumGenerator:
    """Generates layouts from easy to hard."""

    ROLES = ["top", "left", "center", "right", "bottom"]
    TYPES = ["panel", "toolbar", "editor", "sidebar", "terminal", "inspector", "statusbar", "menubar"]

    def __init__(self):
        self.stage = 0
        self.episodes = 0

    def generate(self, level=None):
        """level 0 = easy (3-5 nodes), higher = more nodes and more overlap."""
        if level is None:
            level = min(4, self.stage)
        graph = VariableGraph()
        min_nodes = 3 + level
        max_nodes = 5 + level * 2
        num_nodes = random.randint(min_nodes, max_nodes)
        for i in range(num_nodes):
            role = random.choice(self.ROLES)
            ntype = random.choice(self.TYPES)
            w, h = LayoutEnv.ROLE_SIZES[role]()
            tx, ty = LayoutEnv.ROLE_TARGETS[role]()
            node = GraphNode("n%d" % i, ntype, role, 0, 0, w, h, tx, ty)
            graph.add_node(node)
        self.episodes += 1
        if self.episodes % 200 == 0:
            self.stage = min(4, self.stage + 1)
        return graph


# ═══════════════════════════════════════════════════════════════
# TRANSFORMER TRAINER
# ═══════════════════════════════════════════════════════════════

class TransformerTrainer:
    """PPO-style trainer for the transformer layout brain."""

    def __init__(self):
        self.policy = TransformerActorCritic(
            node_feature_dim=LayoutEnv.NODE_FEATURE_DIM,
            hidden_dim=128,
            num_heads=4,
            num_layers=2,
        ).to(TORCH_DEVICE)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=3e-4)
        self.env = LayoutEnv()
        self.generator = CurriculumGenerator()
        self.gamma = 0.99
        self.lam = 0.95
        self.clip_eps = 0.2
        self.entropy_coef = 0.01
        self.value_coef = 0.5
        self.ppo_epochs = 4
        self.batch_size = 32
        self.episode_count = 0
        self.reward_history = deque(maxlen=100)
        self.loss_history = deque(maxlen=100)
        self.best_reward = -1e9

    def collect_episode(self):
        """Run one episode and return transitions."""
        graph = self.generator.generate()
        state = self.env.reset(graph)
        transitions = []
        done = False
        while not done:
            with torch.no_grad():
                mean, std, value = self.policy(state.unsqueeze(0))
            dist = torch.distributions.Normal(mean, std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1).sum(dim=-1)
            next_state, reward, done, info = self.env.step(action.squeeze(0))
            transitions.append({
                "state": state,
                "action": action.squeeze(0),
                "reward": reward,
                "log_prob": log_prob,
                "value": value.squeeze(0),
                "done": done,
            })
            state = next_state
            if len(transitions) >= self.env.max_steps:
                break
        return transitions

    def compute_gae(self, transitions):
        """Compute generalized advantage estimates."""
        rewards = [t["reward"] for t in transitions]
        values = [float(t["value"]) for t in transitions]
        with torch.no_grad():
            _, _, last_value = self.policy(transitions[-1]["state"].unsqueeze(0))
        last_value = float(last_value.squeeze(0))
        advantages = []
        gae = 0.0
        for i in reversed(range(len(rewards))):
            next_value = values[i + 1] if i + 1 < len(values) else last_value
            delta = rewards[i] + self.gamma * next_value - values[i]
            gae = delta + self.gamma * self.lam * gae
            advantages.insert(0, gae)
        returns = [a + v for a, v in zip(advantages, values)]
        return advantages, returns

    def train(self, episodes):
        """Main training loop."""
        for ep in range(episodes):
            transitions = self.collect_episode()
            if len(transitions) < 3:
                continue
            advantages, returns = self.compute_gae(transitions)
            adv_tensor = torch.tensor(advantages, dtype=torch.float32, device=TORCH_DEVICE)
            ret_tensor = torch.tensor(returns, dtype=torch.float32, device=TORCH_DEVICE)
            if adv_tensor.std() > 1e-6:
                adv_tensor = (adv_tensor - adv_tensor.mean()) / (adv_tensor.std() + 1e-8)
            states = torch.stack([t["state"] for t in transitions])
            actions = torch.stack([t["action"] for t in transitions])
            old_log_probs = torch.stack([t["log_prob"] for t in transitions]).detach()
            total_loss = 0.0
            for _ in range(self.ppo_epochs):
                mean, std, values = self.policy(states)
                values = values.mean(dim=1)
                dist = torch.distributions.Normal(mean, std)
                new_log_probs = dist.log_prob(actions).sum(dim=-1).sum(dim=-1)
                ratio = torch.exp(new_log_probs - old_log_probs)
                surr1 = ratio * adv_tensor
                surr2 = torch.clamp(ratio, 1 - self.clip_eps, 1 + self.clip_eps) * adv_tensor
                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = ((values - ret_tensor) ** 2).mean()
                entropy_loss = -dist.entropy().mean()
                loss = policy_loss + self.value_coef * value_loss + self.entropy_coef * entropy_loss
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
                self.optimizer.step()
                total_loss += float(loss.item())
            ep_reward = sum(t["reward"] for t in transitions)
            self.reward_history.append(ep_reward)
            self.loss_history.append(total_loss / self.ppo_epochs)
            self.episode_count += 1
            if ep_reward > self.best_reward:
                self.best_reward = ep_reward
            if (ep + 1) % 50 == 0:
                avg_reward = sum(self.reward_history) / len(self.reward_history)
                avg_loss = sum(self.loss_history) / len(self.loss_history)
                line = "Ep %d | avg_reward=%.2f | best=%.2f | loss=%.3f | stage=%d\n" % (
                    ep + 1, avg_reward, self.best_reward, avg_loss, self.generator.stage)
                sys.stdout.write(line)
        return self.get_report()

    def get_report(self):
        avg_reward = sum(self.reward_history) / max(1, len(self.reward_history))
        avg_loss = sum(self.loss_history) / max(1, len(self.loss_history))
        return {
            "episodes": self.episode_count,
            "avg_reward": avg_reward,
            "best_reward": self.best_reward,
            "avg_loss": avg_loss,
            "device": str(TORCH_DEVICE),
        }

    def save(self, path):
        torch.save(self.policy.state_dict(), path)
        return {"saved": True, "path": path}

    def load(self, path):
        self.policy.load_state_dict(torch.load(path, map_location=TORCH_DEVICE))
        return {"loaded": True, "path": path}


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    trainer = TransformerTrainer()
    t0 = time.time()
    report = trainer.train(episodes=500)
    t1 = time.time()
    report["elapsed_sec"] = round(t1 - t0, 2)
    trainer.save("layout_transformer_policy.pt")
    sys.stdout.write(json.dumps(report, indent=2))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
