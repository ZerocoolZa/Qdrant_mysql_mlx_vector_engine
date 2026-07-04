#!/usr/bin/env python3
# [@GHOST]{[@file<BrainRL.py>][@domain<graph>][@role<rl_environment>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<rl_environment>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainRL — PyTorch reinforcement learning environment for the GUI AI Brain. Encodes graph state into a flat tensor, trains a PolicyNetwork with REINFORCE policy gradient to predict node movement vectors. MPS (Apple Silicon) support with CPU fallback. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainRL}
# [@METHOD]{Run,encode,step,reset,reward,train,save,load,policy,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<PyTorch RL environment for GUI AI Brain. REINFORCE policy gradient, MPS/CPU support. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded STATE_DIM=40, ACTION_DIM=10, and multiple RL hyperparameter constants. Uses nn.Module subclass (PolicyNetwork) which may conflict with one-class-per-file rule.>][@todos<Move RL hyperparameters to Config.py. Consider separating PolicyNetwork into its own file.>]}
"""
BrainRL — PyTorch reinforcement learning environment for the GUI AI Brain.

WHAT IT DOES:
  Wraps GuiAiBrain into an RL environment. A small neural network (PolicyNetwork)
  learns layout optimization policies via the REINFORCE policy gradient algorithm.

  1. Encodes the graph state (node positions, types, overlaps, distances) into a
     flat tensor of size STATE_DIM.
  2. PolicyNetwork predicts movement vectors (dx, dy) per node (ACTION_DIM).
  3. Predicted movements are applied to the brain.
  4. Reward = -energy + structure_bonus.
  5. Trains the network using REINFORCE (policy gradient).
  6. Supports MPS (Apple Silicon GPU) if available, falls back to CPU.

USAGE:
  from BrainRL import BrainRL

  rl = BrainRL()
  ok, stats, err = rl.Run("train", {"brain": brain, "spec": uiSpec, "episodes": 200})
  ok, data, err = rl.Run("policy", {"brain": brain})
  ok, data, err = rl.Run("save", {"path": "policy_weights.pt"})
  ok, data, err = rl.Run("load", {"path": "policy_weights.pt"})
"""

import os

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


# ════════════════════════════════════════════
# RL CONSTANTS
# ════════════════════════════════════════════

STATE_DIM = 40        # flattened state vector size (5 nodes * 8 features)
ACTION_DIM = 10       # 5 nodes * 2 (dx, dy)
HIDDEN_DIM = 128
LEARNING_RATE = 0.003
GAMMA = 0.95          # discount factor (lower = focus on immediate reward)
MAX_EPISODES = 1000
REWARD_SCALE = 0.01
STRUCTURE_BONUS = 5.0
MPS_DEVICE = "mps"
CPU_DEVICE = "cpu"
NODE_COUNT = 5
FEATURES_PER_NODE = 8
MAX_STEPS_PER_EPISODE = 50
DONE_THRESHOLD = 0.1
ACTION_SCALE = 50.0   # pixels per action unit (was 10 — too small)
OVERLAP_PENALTY = 0.1
ENERGY_WEIGHT = 0.01
DELTA_BONUS = 2.0     # multiplier for energy improvement


# ════════════════════════════════════════════
# POLICY NETWORK — plain class wrapping torch.nn.Sequential
# ════════════════════════════════════════════

class PolicyNetwork:
    """
    Plain Python wrapper around a torch.nn.Sequential policy network.
    Predicts action logits from a state vector and samples actions.
    """

    def __init__(self, inputDim, outputDim, hiddenDim, device):
        self.inputDim = inputDim
        self.outputDim = outputDim
        self.hiddenDim = hiddenDim
        self.device = device
        self.net = None
        self.available = TORCH_AVAILABLE
        if not self.available:
            return
        self.net = nn.Sequential(
            nn.Linear(inputDim, hiddenDim),
            nn.ReLU(),
            nn.Linear(hiddenDim, hiddenDim),
            nn.ReLU(),
            nn.Linear(hiddenDim, outputDim),
        ).to(device)

    def forward(self, x):
        if not self.available or self.net is None:
            return None
        return self.net(x)

    def getAction(self, state):
        if not self.available or self.net is None:
            return None, None
        stateTensor = torch.FloatTensor(state).to(self.device)
        logits = self.forward(stateTensor)
        # Small std for controlled movements, tanh to clamp to [-1,1]
        mean = torch.tanh(logits)
        std = torch.ones_like(logits) * 0.3
        dist = torch.distributions.Normal(mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1.0, 1.0)
        logProb = dist.log_prob(action).sum()
        return action.cpu().detach().numpy(), logProb


# ════════════════════════════════════════════
# BRAIN RL — the main RL environment class
# ════════════════════════════════════════════

class BrainRL:
    """
    Reinforcement learning environment wrapping GuiAiBrain.
    Encodes graph state, trains a PolicyNetwork with REINFORCE.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "state_dim": STATE_DIM,
                "action_dim": ACTION_DIM,
                "hidden_dim": HIDDEN_DIM,
                "learning_rate": LEARNING_RATE,
                "gamma": GAMMA,
                "max_episodes": MAX_EPISODES,
                "reward_scale": REWARD_SCALE,
                "structure_bonus": STRUCTURE_BONUS,
                "device": CPU_DEVICE,
            },
            "policy": None,
            "optimizer": None,
            "device": None,
            "torch_available": TORCH_AVAILABLE,
            "episode_count": 0,
            "training_log": [],
            "last_state": None,
            "last_reward": 0.0,
        }
        self.initDevice()
        self.initPolicy()

    def Run(self, command, params=None):
        dispatch = {
            "encode": self.cmd_encode,
            "step": self.cmd_step,
            "reset": self.cmd_reset,
            "reward": self.cmd_reward,
            "train": self.cmd_train,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "policy": self.cmd_policy,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # INTERNAL — device + policy setup
    # ════════════════════════════════════════════

    def initDevice(self):
        if not TORCH_AVAILABLE:
            self.state["device"] = CPU_DEVICE
            self.state["config"]["device"] = CPU_DEVICE
            return
        deviceName = CPU_DEVICE
        try:
            if torch.backends.mps.is_available():
                deviceName = MPS_DEVICE
        except Exception:
            deviceName = CPU_DEVICE
        self.state["device"] = torch.device(deviceName)
        self.state["config"]["device"] = deviceName

    def initPolicy(self):
        if not TORCH_AVAILABLE:
            self.state["policy"] = None
            self.state["optimizer"] = None
            return
        device = self.state["device"]
        policy = PolicyNetwork(STATE_DIM, ACTION_DIM, HIDDEN_DIM, device)
        self.state["policy"] = policy
        if policy.net is not None:
            self.state["optimizer"] = torch.optim.Adam(
                policy.net.parameters(), lr=LEARNING_RATE
            )
        else:
            self.state["optimizer"] = None

    # ════════════════════════════════════════════
    # ENCODE — brain graph state -> flat tensor
    # ════════════════════════════════════════════

    def encodeBrain(self, brain):
        ok, brainState, err = brain.Run("read_state", {})
        if not ok:
            return [0.0] * STATE_DIM
        graph = brainState.get("graph", {})
        nodes = graph.get("nodes", {})
        cfg = brainState.get("config", {})
        canvasW = float(cfg.get("canvas_w", 1000))
        canvasH = float(cfg.get("canvas_h", 700))
        dockX = 0.0
        dockY = 0.0
        features = []
        nodeItems = list(nodes.items())[:NODE_COUNT]
        for nodeId, node in nodeItems:
            xNorm = float(node.get("x", 0)) / canvasW
            yNorm = float(node.get("y", 0)) / canvasH
            vxNorm = float(node.get("vx", 0)) / canvasW
            vyNorm = float(node.get("vy", 0)) / canvasH
            wNorm = float(node.get("w", 0)) / canvasW
            hNorm = float(node.get("h", 0)) / canvasH
            overlapScore = self.computeOverlapScore(node, nodes)
            distToDock = (
                ((float(node.get("x", 0)) - dockX) ** 2
                 + (float(node.get("y", 0)) - dockY) ** 2) ** 0.5
            ) / max(canvasW, 1.0)
            features.extend([
                xNorm, yNorm, vxNorm, vyNorm,
                wNorm, hNorm, overlapScore, distToDock,
            ])
        while len(features) < STATE_DIM:
            features.append(0.0)
        return features[:STATE_DIM]

    def computeOverlapScore(self, targetNode, nodes):
        tx = float(targetNode.get("x", 0))
        ty = float(targetNode.get("y", 0))
        tw = float(targetNode.get("w", 0))
        th = float(targetNode.get("h", 0))
        score = 0.0
        for otherId, other in nodes.items():
            if otherId == targetNode.get("id", ""):
                continue
            ox = float(other.get("x", 0))
            oy = float(other.get("y", 0))
            ow = float(other.get("w", 0))
            oh = float(other.get("h", 0))
            overlapX = max(0.0, min(tx + tw, ox + ow) - max(tx, ox))
            overlapY = max(0.0, min(ty + th, oy + oh) - max(ty, oy))
            score += overlapX * overlapY
        return score / 10000.0

    def cmd_encode(self, params):
        brain = self.p(params, "brain")
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        features = self.encodeBrain(brain)
        self.state["last_state"] = features
        return (1, {"state": features, "dim": len(features)}, None)

    # ════════════════════════════════════════════
    # STEP — apply action to brain, return next state + reward + done
    # ════════════════════════════════════════════

    def cmd_step(self, params):
        brain = self.p(params, "brain")
        action = self.p(params, "action")
        if not brain or action is None:
            return (0, None, ("ERR_PARAMS", "brain and action required", 0))
        self.applyActionToBrain(brain, action)
        ok, rewardData, err = self.cmd_reward({"brain": brain})
        if not ok:
            return (0, None, ("ERR_REWARD", "reward computation failed", 0))
        reward = rewardData.get("reward", 0.0)
        nextState = self.encodeBrain(brain)
        done = abs(reward) < DONE_THRESHOLD
        self.state["last_state"] = nextState
        self.state["last_reward"] = reward
        return (1, {"next_state": nextState, "reward": reward, "done": done}, None)

    def applyActionToBrain(self, brain, action):
        ok, brainState, err = brain.Run("read_state", {})
        if not ok:
            return
        nodes = brainState.get("graph", {}).get("nodes", {})
        nodeIds = list(nodes.keys())[:NODE_COUNT]
        for idx, nodeId in enumerate(nodeIds):
            baseIdx = idx * 2
            if baseIdx + 1 >= len(action):
                break
            dx = float(action[baseIdx]) * ACTION_SCALE
            dy = float(action[baseIdx + 1]) * ACTION_SCALE
            node = nodes[nodeId]
            node["x"] = node.get("x", 0) + dx
            node["y"] = node.get("y", 0) + dy

    # ════════════════════════════════════════════
    # RESET — reset brain with new spec, return initial state
    # ════════════════════════════════════════════

    def cmd_reset(self, params):
        brain = self.p(params, "brain")
        spec = self.p(params, "spec")
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        if spec:
            ok, data, err = brain.Run("perceive", {"spec": spec})
            if not ok:
                return (0, None, ("ERR_PERCEIVE", "brain perceive failed", 0))
        # Clear previous energy so first reward is delta from initial state
        self.state["prev_energy"] = None
        features = self.encodeBrain(brain)
        self.state["last_state"] = features
        self.state["last_reward"] = 0.0
        return (1, {"state": features, "dim": len(features)}, None)

    # ════════════════════════════════════════════
    # REWARD — compute reward = -energy + structure_bonus
    # ════════════════════════════════════════════

    def cmd_reward(self, params):
        brain = self.p(params, "brain")
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        ok, energyData, err = brain.Run("energy", {})
        if not ok:
            return (0, None, ("ERR_ENERGY", "brain energy failed", 0))
        energy = float(energyData.get("total", 0.0))
        overlapTotal = float(energyData.get("overlap", 0.0))
        structureBonus = self.computeStructureBonus(brain)
        prevEnergy = self.state.get("prev_energy")
        if prevEnergy is None:
            prevEnergy = energy
        # DELTA reward: reward = improvement + structure bonus - overlap penalty
        # This tells the network "you moved in the right direction"
        deltaEnergy = prevEnergy - energy  # positive = energy went down = good
        reward = (deltaEnergy * ENERGY_WEIGHT * DELTA_BONUS) + structureBonus - (overlapTotal * OVERLAP_PENALTY)
        self.state["prev_energy"] = energy
        return (1, {
            "reward": reward,
            "energy": energy,
            "delta_energy": deltaEnergy,
            "structure_bonus": structureBonus,
            "overlap_penalty": overlapTotal,
        }, None)

    def computeStructureBonus(self, brain):
        ok, brainState, err = brain.Run("read_state", {})
        if not ok:
            return 0.0
        nodes = brainState.get("graph", {}).get("nodes", {})
        if len(nodes) == 0:
            return 0.0
        totalOverlap = 0.0
        nodeList = list(nodes.values())
        for i in range(len(nodeList)):
            for j in range(i + 1, len(nodeList)):
                totalOverlap += self.computePairOverlap(nodeList[i], nodeList[j])
        if totalOverlap < 1.0:
            return STRUCTURE_BONUS
        return 0.0

    def computePairOverlap(self, a, b):
        ax = float(a.get("x", 0))
        ay = float(a.get("y", 0))
        aw = float(a.get("w", 0))
        ah = float(a.get("h", 0))
        bx = float(b.get("x", 0))
        by = float(b.get("y", 0))
        bw = float(b.get("w", 0))
        bh = float(b.get("h", 0))
        overlapX = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
        overlapY = max(0.0, min(ay + ah, by + bh) - max(ay, by))
        return overlapX * overlapY

    # ════════════════════════════════════════════
    # TRAIN — REINFORCE policy gradient loop
    # ════════════════════════════════════════════

    def cmd_train(self, params):
        brain = self.p(params, "brain")
        spec = self.p(params, "spec")
        episodes = int(self.p(params, "episodes", MAX_EPISODES))
        if not brain or not spec:
            return (0, None, ("ERR_PARAMS", "brain and spec required", 0))
        if not TORCH_AVAILABLE:
            return (0, None, ("ERR_TORCH", "torch not available", 0))
        policy = self.state["policy"]
        optimizer = self.state["optimizer"]
        if policy is None or optimizer is None:
            return (0, None, ("ERR_POLICY", "policy network not initialized", 0))
        gamma = self.state["config"]["gamma"]
        episodeRewards = []
        for ep in range(episodes):
            ok, resetData, err = self.cmd_reset({"brain": brain, "spec": spec})
            if not ok:
                continue
            logProbs = []
            rewards = []
            for step in range(MAX_STEPS_PER_EPISODE):
                state = self.encodeBrain(brain)
                action, logProb = policy.getAction(state)
                if action is None or logProb is None:
                    break
                okStep, stepData, errStep = self.cmd_step({
                    "brain": brain,
                    "action": action,
                })
                if not okStep:
                    break
                reward = stepData.get("reward", 0.0)
                done = stepData.get("done", False)
                logProbs.append(logProb)
                rewards.append(reward)
                if done:
                    break
            if len(logProbs) == 0:
                continue
            returns = self.computeReturns(rewards, gamma)
            loss = self.computePolicyLoss(logProbs, returns)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epReward = sum(rewards)
            episodeRewards.append(epReward)
            self.state["training_log"].append({
                "episode": ep,
                "reward": epReward,
                "steps": len(rewards),
            })
        self.state["episode_count"] += episodes
        avgReward = (
            sum(episodeRewards) / len(episodeRewards)
            if episodeRewards else 0.0
        )
        return (1, {
            "episodes": episodes,
            "avg_reward": avgReward,
            "max_reward": max(episodeRewards) if episodeRewards else 0.0,
            "min_reward": min(episodeRewards) if episodeRewards else 0.0,
            "completed": len(episodeRewards),
        }, None)

    def computeReturns(self, rewards, gamma):
        returns = []
        discounted = 0.0
        for r in reversed(rewards):
            discounted = r + gamma * discounted
            returns.insert(0, discounted)
        return returns

    def computePolicyLoss(self, logProbs, returns):
        # Normalize returns (baseline subtraction + std scaling)
        # This is CRITICAL for REINFORCE — without it, gradient variance is huge
        # and the network cannot find the learning signal
        returnsTensor = torch.tensor(returns, dtype=torch.float32, device=self.state["device"])
        meanR = returnsTensor.mean()
        stdR = returnsTensor.std()
        if stdR > 1e-8:
            normalizedReturns = (returnsTensor - meanR) / (stdR + 1e-8)
        else:
            normalizedReturns = returnsTensor - meanR
        lossTerms = []
        for i in range(len(logProbs)):
            term = -logProbs[i] * normalizedReturns[i]
            lossTerms.append(term)
        return torch.stack(lossTerms).sum()

    # ════════════════════════════════════════════
    # SAVE / LOAD — model weights
    # ════════════════════════════════════════════

    def cmd_save(self, params):
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not TORCH_AVAILABLE:
            return (0, None, ("ERR_TORCH", "torch not available", 0))
        policy = self.state["policy"]
        if policy is None or policy.net is None:
            return (0, None, ("ERR_POLICY", "no policy to save", 0))
        try:
            torch.save(policy.net.state_dict(), path)
        except Exception as exc:
            return (0, None, ("ERR_SAVE", "save failed: %s" % str(exc), 0))
        return (1, {"path": path, "saved": True}, None)

    def cmd_load(self, params):
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not TORCH_AVAILABLE:
            return (0, None, ("ERR_TORCH", "torch not available", 0))
        if not os.path.exists(path):
            return (0, None, ("ERR_FILE", "path not found: %s" % path, 0))
        policy = self.state["policy"]
        if policy is None or policy.net is None:
            return (0, None, ("ERR_POLICY", "no policy to load into", 0))
        try:
            weights = torch.load(path, map_location=self.state["device"])
            policy.net.load_state_dict(weights)
        except Exception as exc:
            return (0, None, ("ERR_LOAD", "load failed: %s" % str(exc), 0))
        return (1, {"path": path, "loaded": True}, None)

    # ════════════════════════════════════════════
    # POLICY — use trained network to predict best action and apply it
    # ════════════════════════════════════════════

    def cmd_policy(self, params):
        brain = self.p(params, "brain")
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        if not TORCH_AVAILABLE:
            return (0, None, ("ERR_TORCH", "torch not available", 0))
        policy = self.state["policy"]
        if policy is None:
            return (0, None, ("ERR_POLICY", "policy network not initialized", 0))
        state = self.encodeBrain(brain)
        action, logProb = policy.getAction(state)
        if action is None:
            return (0, None, ("ERR_ACTION", "action prediction failed", 0))
        ok, stepData, err = self.cmd_step({"brain": brain, "action": action})
        if not ok:
            return (0, None, ("ERR_STEP", "step failed", 0))
        logProbVal = float(logProb.detach()) if logProb is not None else 0.0
        return (1, {
            "action": action.tolist() if hasattr(action, "tolist") else list(action),
            "next_state": stepData.get("next_state"),
            "reward": stepData.get("reward", 0.0),
            "done": stepData.get("done", False),
            "log_prob": logProbVal,
            "log_prob_tensor": logProb,
        }, None)
