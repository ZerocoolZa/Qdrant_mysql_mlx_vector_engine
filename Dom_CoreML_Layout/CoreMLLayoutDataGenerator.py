#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLLayoutDataGenerator.py
#[@SUMMARY] Generates synthetic layout episodes for CoreML on-device training
#[@CLASS] CoreMLLayoutDataGenerator
#[@METHOD] generate, save, load
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import json
import random
import math
from Config_CoreMLLayout import (
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    INPUT_DIM,
    OUTPUT_DIM,
    NUM_ROLES,
    ROLE_NAMES,
    ROLE_SIZES,
    MAX_NODES,
    TRAINING_DATA_PATH,
    MAX_EPISODES,
)


class CoreMLLayoutDataGenerator:
    """Generates synthetic (state, action, reward) layout episodes."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "episodes": [],
            "episode_count": 0,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "generate":
            return self.cmdGenerate(params)
        if command == "save":
            return self.cmdSave(params)
        if command == "load":
            return self.cmdLoad(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def makeNode(self, idx, role):
        w, h = ROLE_SIZES[role]
        x = random.uniform(0, max(1, CANVAS_WIDTH - w))
        y = random.uniform(0, max(1, CANVAS_HEIGHT - h))
        tx = self.targetX(role, w)
        ty = self.targetY(role, h)
        return {
            "id": idx,
            "role": role,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "tx": tx,
            "ty": ty,
        }

    def targetX(self, role, w):
        if role == "top" or role == "bottom" or role == "center":
            return (CANVAS_WIDTH - w) / 2.0
        if role == "left":
            return 10.0
        return CANVAS_WIDTH - w - 10.0

    def targetY(self, role, h):
        if role == "top":
            return 10.0
        if role == "bottom":
            return CANVAS_HEIGHT - h - 10.0
        return (CANVAS_HEIGHT - h) / 2.0

    def encodeState(self, nodes):
        features = []
        for n in nodes:
            features.append(n["x"] / CANVAS_WIDTH)
            features.append(n["y"] / CANVAS_HEIGHT)
            features.append(n["w"] / CANVAS_WIDTH)
            features.append(n["h"] / CANVAS_HEIGHT)
            features.append(n["tx"] / CANVAS_WIDTH)
            features.append(n["ty"] / CANVAS_HEIGHT)
            roleIdx = ROLE_NAMES.index(n["role"])
            features.append(float(roleIdx) / NUM_ROLES)
            features.append(0.0)
        while len(features) < INPUT_DIM:
            features.append(0.0)
        return features[:INPUT_DIM]

    def computeEnergy(self, nodes):
        energy = 0.0
        for n in nodes:
            dx = n["x"] - n["tx"]
            dy = n["y"] - n["ty"]
            energy += dx * dx + dy * dy
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ni = nodes[i]
                nj = nodes[j]
                ox = min(ni["x"] + ni["w"], nj["x"] + nj["w"]) - max(ni["x"], nj["x"])
                oy = min(ni["y"] + ni["h"], nj["y"] + nj["h"]) - max(ni["y"], nj["y"])
                if ox > 0 and oy > 0:
                    energy += ox * oy * 0.5
        return energy

    def bestAction(self, nodes):
        action = [0.0] * OUTPUT_DIM
        energyCurrent = self.computeEnergy(nodes)
        bestEnergy = energyCurrent
        for a in range(OUTPUT_DIM):
            testNodes = [dict(n) for n in nodes]
            self.applyAction(testNodes, a, 0.5)
            energyNew = self.computeEnergy(testNodes)
            if energyNew < bestEnergy:
                bestEnergy = energyNew
                bestA = a
        action[bestA] = 1.0
        return action

    def applyAction(self, nodes, actionIdx, magnitude):
        if actionIdx == 0:
            for n in nodes:
                n["x"] += magnitude * 10
        elif actionIdx == 1:
            for n in nodes:
                n["x"] -= magnitude * 10
        elif actionIdx == 2:
            for n in nodes:
                n["y"] += magnitude * 10
        elif actionIdx == 3:
            for n in nodes:
                n["y"] -= magnitude * 10
        elif actionIdx == 4:
            for n in nodes:
                n["x"] += (n["tx"] - n["x"]) * magnitude * 0.1
        elif actionIdx == 5:
            for n in nodes:
                n["y"] += (n["ty"] - n["y"]) * magnitude * 0.1
        elif actionIdx == 6:
            for n in nodes:
                n["x"] += (n["tx"] - n["x"]) * magnitude * 0.05
                n["y"] += (n["ty"] - n["y"]) * magnitude * 0.05
        elif actionIdx == 7:
            for n in nodes:
                n["x"] -= (n["tx"] - n["x"]) * magnitude * 0.05
        elif actionIdx == 8:
            for n in nodes:
                n["y"] -= (n["ty"] - n["y"]) * magnitude * 0.05
        elif actionIdx == 9:
            pass

    def cmdGenerate(self, params):
        try:
            numEpisodes = int(self.p(params, "episodes", MAX_EPISODES))
            stepsPerEpisode = int(self.p(params, "steps", 20))
            episodes = []
            for ep in range(numEpisodes):
                numNodes = random.randint(3, MAX_NODES)
                roles = random.sample(ROLE_NAMES, min(numNodes, NUM_ROLES))
                while len(roles) < numNodes:
                    roles.append(random.choice(ROLE_NAMES))
                nodes = [self.makeNode(i, roles[i]) for i in range(numNodes)]
                steps = []
                for step in range(stepsPerEpisode):
                    state = self.encodeState(nodes)
                    action = self.bestAction(nodes)
                    energyBefore = self.computeEnergy(nodes)
                    actionIdx = action.index(max(action))
                    self.applyAction(nodes, actionIdx, 0.5)
                    energyAfter = self.computeEnergy(nodes)
                    reward = energyBefore - energyAfter
                    steps.append({
                        "state": state,
                        "action": action,
                        "reward": reward,
                    })
                    if energyAfter < 1.0:
                        break
                episodes.append({
                    "episode": ep,
                    "num_nodes": numNodes,
                    "steps": steps,
                    "final_energy": self.computeEnergy(nodes),
                })
            self.state["episodes"] = episodes
            self.state["episode_count"] = len(episodes)
            return (1, {
                "episodes": len(episodes),
                "total_steps": sum(len(e["steps"]) for e in episodes),
            }, None)
        except Exception as e:
            return (0, None, ("GENERATE_ERROR", str(e), 0))

    def cmdSave(self, params):
        try:
            path = self.p(params, "path", TRAINING_DATA_PATH)
            data = {
                "episodes": self.state["episodes"],
                "config": {
                    "input_dim": INPUT_DIM,
                    "output_dim": OUTPUT_DIM,
                    "canvas": [CANVAS_WIDTH, CANVAS_HEIGHT],
                },
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return (1, {"path": path, "episodes": len(self.state["episodes"])}, None)
        except Exception as e:
            return (0, None, ("SAVE_ERROR", str(e), 0))

    def cmdLoad(self, params):
        try:
            path = self.p(params, "path", TRAINING_DATA_PATH)
            with open(path, "r") as f:
                data = json.load(f)
            self.state["episodes"] = data.get("episodes", [])
            self.state["episode_count"] = len(self.state["episodes"])
            return (1, {"path": path, "episodes": self.state["episode_count"]}, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "episode_count": self.state["episode_count"],
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
