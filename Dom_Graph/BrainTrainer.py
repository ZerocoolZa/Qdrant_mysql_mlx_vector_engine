#!/usr/bin/env python3
# [@GHOST]{[@file<BrainTrainer.py>][@domain<graph>][@role<trainer>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<trainer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainTrainer — Full RL training loop that wires BrainSynthetic (data generation), BrainRL (PyTorch environment), and GuiAiBrain (physics engine). Trains the policy network with REINFORCE to learn layout optimization. Tracks reward/loss history, best model, save/load weights, generalization eval. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainTrainer}
# [@METHOD]{Run,train,evaluate,save,load,report,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Full RL training loop wiring BrainSynthetic, BrainRL, and GuiAiBrain. REINFORCE policy gradient with reward/loss tracking. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded TRAIN_EPISODES=500, STEPS_PER_EPISODE=20, GAMMA, LR constants.>][@todos<Move training hyperparameters to Config.py>]}
"""
BrainTrainer — Full reinforcement learning training loop for the GUI AI Brain.

WHAT IT DOES:
  Wires together three modules into one training pipeline:
    1. BrainSynthetic  — generates random UI specs (data generation)
    2. GuiAiBrain      — physics engine that lays out the graph
    3. BrainRL         — PyTorch RL environment + REINFORCE policy network

  The training loop, per episode:
    - Generate a fresh random UI spec via BrainSynthetic
    - Create a fresh GuiAiBrain and perceive the spec
    - Create a fresh BrainRL env bound to that brain
    - Run STEPS_PER_EPISODE steps: encode state, sample policy action,
      collect reward and log-probability
    - Compute discounted returns (GAMMA) and REINFORCE policy gradient loss
    - Update the policy network via the optimizer
    - Track avg reward, loss, best reward, best episode

  After training, the model can be saved/loaded and evaluated on unseen
  specs to measure generalization.

USAGE:
  from BrainTrainer import BrainTrainer

  trainer = BrainTrainer()
  ok, metrics, err = trainer.Run("train", {"episodes": 500, "steps": 20})
  ok, data, err = trainer.Run("save", {"path": "brain_model.pt"})
  ok, data, err = trainer.Run("evaluate", {"episodes": 50})
  ok, report, err = trainer.Run("report", {})
"""

from GuiAiBrain import GuiAiBrain
from BrainRL import BrainRL
from BrainSynthetic import BrainSynthetic


# ════════════════════════════════════════════
# TRAINER CONSTANTS
# ════════════════════════════════════════════

TRAIN_EPISODES = 500
STEPS_PER_EPISODE = 20
EVAL_EPISODES = 50
SAVE_INTERVAL = 100
PRINT_INTERVAL = 10
GAMMA = 0.95
LEARNING_RATE = 0.003
MODEL_PATH = "brain_model.pt"
REWARD_SCALE = 0.01
PHYSICS_TICKS_BETWEEN_STEPS = 3  # run physics between RL steps


# ════════════════════════════════════════════
# BRAIN TRAINER — the full RL training loop
# ════════════════════════════════════════════

class BrainTrainer:
    """
    Full RL training loop wiring BrainSynthetic + BrainRL + GuiAiBrain.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "train_episodes": TRAIN_EPISODES,
                "steps_per_episode": STEPS_PER_EPISODE,
                "eval_episodes": EVAL_EPISODES,
                "save_interval": SAVE_INTERVAL,
                "print_interval": PRINT_INTERVAL,
                "gamma": GAMMA,
                "learning_rate": LEARNING_RATE,
                "model_path": MODEL_PATH,
                "reward_scale": REWARD_SCALE,
            },
            "reward_history": [],
            "loss_history": [],
            "best_reward": 0.0,
            "best_episode": -1,
            "best_rl": None,
            "episodes_run": 0,
            "model_path": "",
            "torch_available": False,
        }
        self.detectTorch()

    def Run(self, command, params=None):
        dispatch = {
            "train": self.cmd_train,
            "evaluate": self.cmd_evaluate,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "report": self.cmd_report,
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
    # INTERNAL — torch availability (imported inside method)
    # ════════════════════════════════════════════

    def detectTorch(self):
        try:
            import torch
            self.state["torch_available"] = True
            return True
        except ImportError as excTorch:
            self.state["torch_available"] = False
            return False

    def importTorch(self):
        try:
            import torch
            return torch, True
        except ImportError as excTorch:
            return None, False

    def scalarLoss(self, loss):
        if hasattr(loss, "item"):
            try:
                return float(loss.item())
            except Exception as excItem:
                return 0.0
        try:
            return float(loss)
        except Exception as excCast:
            return 0.0

    # ════════════════════════════════════════════
    # TRAIN — full REINFORCE policy gradient loop
    # ════════════════════════════════════════════

    def cmd_train(self, params):
        episodes = int(self.p(params, "episodes", TRAIN_EPISODES))
        steps = int(self.p(params, "steps", STEPS_PER_EPISODE))
        gamma = self.state["config"]["gamma"]
        saveInterval = self.state["config"]["save_interval"]
        torch, torchAvailable = self.importTorch()
        rewardHistory = []
        lossHistory = []
        bestReward = -1e18
        bestEpisode = -1
        bestRl = None
        # Create ONE RL environment with ONE policy network — reuse across all episodes
        # This is critical: the network must persist so weights carry over between episodes
        firstBrain = GuiAiBrain()
        firstSynth = BrainSynthetic()
        ok, firstSpec, _ = firstSynth.Run("random_spec")
        if not ok:
            return (0, None, ("ERR_SYNTH", "failed to generate first spec", 0))
        firstBrain.Run("perceive", {"spec": firstSpec})
        masterRl = BrainRL(param={"brain": firstBrain})
        # Get the optimizer from the master RL env — it will update the SAME network
        optimizer = masterRl.state.get("optimizer")
        for episode in range(episodes):
            synth = BrainSynthetic()
            ok, specData, errSynth = synth.Run("random_spec")
            if not ok:
                continue
            brain = GuiAiBrain()
            okPerc, percData, errPerc = brain.Run(
                "perceive", {"spec": specData}
            )
            if not okPerc:
                continue
            # Reuse the MASTER RL env (same policy network) but with the new brain
            masterRl.state["brain"] = brain
            rewards = []
            logProbs = []
            for step in range(steps):
                # Run physics between RL steps — let the physics engine help
                if step > 0:
                    brain.Run("cycle", {"ticks": PHYSICS_TICKS_BETWEEN_STEPS})
                okPol, polData, errPol = masterRl.Run("policy", {"brain": brain})
                if not okPol:
                    break
                rewards.append(float(polData.get("reward", 0.0)))
                logProbs.append(polData.get("log_prob_tensor", polData.get("log_prob", 0)))
            if len(rewards) == 0:
                continue
            returns = []
            G = 0.0
            for r in reversed(rewards):
                G = r + gamma * G
                returns.insert(0, G)
            # Normalize returns (baseline) — CRITICAL for REINFORCE
            if torchAvailable:
                returnsTensor = torch.tensor(returns, dtype=torch.float32,
                                             device=masterRl.state["device"])
                meanR = returnsTensor.mean()
                stdR = returnsTensor.std()
                if stdR > 1e-8:
                    returnsNorm = (returnsTensor - meanR) / (stdR + 1e-8)
                else:
                    returnsNorm = returnsTensor - meanR
                returns = returnsNorm.tolist()
            # Build loss — accumulate tensor log probs * normalized returns
            loss = None
            for lp, Gv in zip(logProbs, returns):
                term = -lp * Gv
                if loss is None:
                    loss = term
                else:
                    loss = loss + term
            lossVal = 0.0
            if torchAvailable and loss is not None and hasattr(loss, "backward"):
                if optimizer is not None:
                    try:
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                    except Exception as excStep:
                        lossVal = self.scalarLoss(loss)
                lossVal = self.scalarLoss(loss)
            elif loss is not None:
                lossVal = self.scalarLoss(loss)
            epReward = sum(rewards) / len(rewards)
            rewardHistory.append(epReward)
            lossHistory.append(lossVal)
            if epReward > bestReward:
                bestReward = epReward
                bestEpisode = episode
                bestRl = masterRl
            if (episode + 1) % saveInterval == 0 and bestRl is not None:
                bestRl.Run("save", {"path": MODEL_PATH})
        self.state["reward_history"] = rewardHistory
        self.state["loss_history"] = lossHistory
        self.state["best_reward"] = bestReward if bestReward > -1e17 else 0.0
        self.state["best_episode"] = bestEpisode
        self.state["best_rl"] = bestRl
        self.state["episodes_run"] = episodes
        avgReward = (
            sum(rewardHistory) / len(rewardHistory)
            if rewardHistory else 0.0
        )
        return (1, {
            "episodes": episodes,
            "avg_reward": avgReward,
            "best_reward": self.state["best_reward"],
            "best_episode": bestEpisode,
            "history": rewardHistory,
            "loss_history": lossHistory,
        }, None)

    # ════════════════════════════════════════════
    # EVALUATE — test trained model on unseen specs
    # ════════════════════════════════════════════

    def cmd_evaluate(self, params):
        episodes = int(self.p(params, "episodes", EVAL_EPISODES))
        steps = int(self.p(params, "steps", STEPS_PER_EPISODE))
        bestRl = self.state.get("best_rl")
        rewardsAll = []
        for episode in range(episodes):
            synth = BrainSynthetic()
            ok, specData, errSynth = synth.Run("random_spec")
            if not ok:
                continue
            brain = GuiAiBrain()
            okPerc, percData, errPerc = brain.Run(
                "perceive", {"spec": specData}
            )
            if not okPerc:
                continue
            rl = BrainRL(param={"brain": brain})
            loadOk = True
            if bestRl is not None:
                okLoad, loadData, errLoad = self.transferWeights(bestRl, rl)
                loadOk = okLoad
            epRewards = []
            for step in range(steps):
                okEnc, encData, errEnc = rl.Run("encode", {"brain": brain})
                if not okEnc:
                    break
                okPol, polData, errPol = rl.Run("policy", {"brain": brain})
                if not okPol:
                    break
                epRewards.append(float(polData.get("reward", 0.0)))
            if len(epRewards) > 0:
                rewardsAll.append(sum(epRewards) / len(epRewards))
        avgReward = (
            sum(rewardsAll) / len(rewardsAll)
            if rewardsAll else 0.0
        )
        return (1, {
            "episodes": episodes,
            "avg_reward": avgReward,
            "rewards": rewardsAll,
            "best_reward": max(rewardsAll) if rewardsAll else 0.0,
            "worst_reward": min(rewardsAll) if rewardsAll else 0.0,
        }, None)

    def transferWeights(self, srcRl, dstRl):
        torch, torchAvailable = self.importTorch()
        if not torchAvailable:
            return (1, {"transferred": False}, None)
        srcPolicy = srcRl.state.get("policy")
        dstPolicy = dstRl.state.get("policy")
        if srcPolicy is None or dstPolicy is None:
            return (0, None, ("ERR_POLICY", "policy missing", 0))
        if srcPolicy.net is None or dstPolicy.net is None:
            return (0, None, ("ERR_POLICY", "network missing", 0))
        try:
            dstPolicy.net.load_state_dict(srcPolicy.net.state_dict())
        except Exception as excCopy:
            return (0, None, ("ERR_COPY", "weight copy failed", 0))
        return (1, {"transferred": True}, None)

    # ════════════════════════════════════════════
    # SAVE / LOAD — persist trained model weights
    # ════════════════════════════════════════════

    def cmd_save(self, params):
        path = self.p(params, "path", MODEL_PATH)
        bestRl = self.state.get("best_rl")
        if bestRl is None:
            return (0, None, ("ERR_NO_MODEL", "no trained model to save", 0))
        ok, data, err = bestRl.Run("save", {"path": path})
        if not ok:
            return (0, None, ("ERR_SAVE", "save failed", 0))
        self.state["model_path"] = path
        return (1, {"path": path, "saved": True}, None)

    def cmd_load(self, params):
        path = self.p(params, "path", MODEL_PATH)
        bestRl = self.state.get("best_rl")
        if bestRl is None:
            bestRl = BrainRL()
            self.state["best_rl"] = bestRl
        ok, data, err = bestRl.Run("load", {"path": path})
        if not ok:
            return (0, None, ("ERR_LOAD", "load failed", 0))
        self.state["model_path"] = path
        return (1, {"path": path, "loaded": True}, None)

    # ════════════════════════════════════════════
    # REPORT — training metrics summary
    # ════════════════════════════════════════════

    def cmd_report(self, params):
        rewardHistory = self.state.get("reward_history", [])
        lossHistory = self.state.get("loss_history", [])
        avgReward = (
            sum(rewardHistory) / len(rewardHistory)
            if rewardHistory else 0.0
        )
        avgLoss = (
            sum(lossHistory) / len(lossHistory)
            if lossHistory else 0.0
        )
        report = {
            "episodes_run": self.state.get("episodes_run", 0),
            "best_reward": self.state.get("best_reward", 0.0),
            "best_episode": self.state.get("best_episode", -1),
            "avg_reward": avgReward,
            "avg_loss": avgLoss,
            "reward_history": list(rewardHistory),
            "loss_history": list(lossHistory),
            "model_path": self.state.get("model_path", ""),
            "torch_available": self.state.get("torch_available", False),
            "has_model": self.state.get("best_rl") is not None,
        }
        return (1, report, None)
