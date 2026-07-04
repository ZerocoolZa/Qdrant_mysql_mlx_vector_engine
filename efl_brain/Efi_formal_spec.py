#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_formal_spec.py
# Domain:   efl_brain
# Authority: Formal specification of the graph policy optimizer
# DB:       None (pure math specification)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# This file contains the mathematical update rules that govern the agent graph.
# It is a reproducible algorithm specification, not "felt behavior".
# Every equation here maps directly to code in Efi_agent_graph.py.
# ============================================================================
#
# FORMAL SPECIFICATION: Closed-Loop Graph Policy Optimizer
# ========================================================
#
# NOTATION
# --------
#   G = (V, E)                    typed-state graph
#   V = {v_1, ..., v_n}           set of agent nodes (vertices)
#   E = {e_1, ..., e_m}           set of typed edges
#   e = (src, dst, type)          edge with type ∈ {IMPORTS, CALLS, CONTAINS, DEFINES, ASSOCIATES}
#   t ∈ {1, ..., T}               discrete time steps
#   v_i ∈ V                       current node at time t
#
# NODE STATE VECTOR
# -----------------
#   Each node v_i carries a state vector S_i:
#
#   S_i = (sensors_i, drives_i, memory_i, survival_i, attention_i, novelty_i)
#
#   sensors_i = (taste, touch, vision, smell, pain, hunger)   ∈ [0,1]^6
#   drives_i  = (curiosity, fear, confidence, reward)          ∈ [0,1]^4
#   memory_i  = (visits, last_reward, last_pain, experiences)  ∈ ℕ × [0,1]² × ℋ
#   survival_i = (health, age, generation, alive)              ∈ [0,1] × ℕ² × {0,1}
#   attention_i ∈ [0,1]                                        scalar
#   novelty_i   ∈ [0,1]                                        scalar
#
# EDGE STATE
# ----------
#   Structural edges E are static (built from AST analysis).
#   Cognitive edges (prediction links) P are learned:
#
#   P = {(src, dst) → PredictionLink}
#
#   PredictionLink = (expected_reward, expected_pain, confidence, update_count)
#       expected_reward ∈ [0, 1]
#       expected_pain   ∈ [0, 1]
#       confidence      ∈ [0, 1]
#       update_count    ∈ ℕ
#
# ============================================================================
# UPDATE RULES
# ============================================================================
#
# RULE 1: OBSERVE (sensor input)
# ------------------------------
#   When the agent visits node v_i at time t:
#
#     touch_i(t) ← 1.0                          (direct interaction)
#     hunger_i(t) ← max(0, hunger_i(t-1) - 0.1) (hunger decreases on visit)
#
#   External signals (pain, taste, smell) are set by the environment:
#     sensor_i(signal, value) ← clamp(value, 0, 1)
#
# RULE 2: PREDICT (prediction link lookup)
# -----------------------------------------
#   For current node v_i, predict best next node v_j:
#
#   For each neighbor v_j ∈ N(i):
#     link_ij = GetOrCreatePredictionLink(i, j)
#     value_ij = NetValue(link_ij) + novelty_j × 0.1
#
#   predicted_next = argmax_j (value_ij)
#   predicted_value = max_j (value_ij)
#
#   Where:
#     NetValue(link) = (expected_reward - expected_pain) × confidence
#
# RULE 3: ATTEND (attention update)
# ----------------------------------
#   Attention boost for current node v_i with active goal g:
#
#     boost_i = reward_i × 0.3 + novelty_i × 0.2
#     if g and type(v_i) == g.target_type:
#       boost_i += g.priority × 0.4
#     if g and v_i == g.target_id:
#       boost_i += g.priority × 0.5
#
#     attention_i(t) ← min(1.0, attention_i(t-1) + boost_i)
#     attention_peak_i ← max(attention_peak_i, attention_i(t))
#
#   Attention decay (applied to ALL nodes each step):
#     attention_j(t) ← max(0, attention_j(t-1) - 0.05)     ∀j
#     novelty_j(t) ← max(0, novelty_j(t-1) - 0.05)          ∀j
#
# RULE 4: ACT (traversal policy)
# -------------------------------
#   Available targets: N(i) = adj(i) ∪ radj(i)  (both directions)
#   Filter: fresh = {j ∈ N(i) : visits_j < 5}
#
#   If fresh = ∅: backtrack (see RULE 4b)
#
#   Score each fresh target v_j:
#
#     score_j = NetValue(link_ij) × 0.3
#             + attention_j × 0.15
#             + novelty_j × 0.3
#             + curiosity_j × 0.1
#             - fear_j × 0.15
#             - pain_j × 0.2
#             + goal_bonus_j
#
#   Where goal_bonus_j:
#     if g.target_type == type(v_j):
#       goal_bonus_j = g.priority × 0.5
#     elif g.target_type unseen and type(v_j) ∈ {FILE_PY, CONFIG, FOLDER}:
#       goal_bonus_j = g.priority × 0.3    (type-seeking)
#     else:
#       goal_bonus_j = 0
#
#   Exploration vs exploitation:
#     With probability p_explore = curiosity_i × 0.15:
#       next ← random choice from top-3 scored targets
#     Otherwise:
#       next ← argmax_j (score_j)
#
# RULE 4b: BACKTRACK (dead-end recovery)
# ---------------------------------------
#   If fresh = ∅ (all neighbors visited ≥ 5 times):
#
#   1. Search path_history in reverse:
#      Find most recent v_prev with unvisited neighbors (visits < 3)
#      If found: jump to v_prev
#
#   2. If no backtrack target:
#      candidates = {v ∈ V : visits_v = 0 and deg(v) > 0}
#      If candidates ≠ ∅: jump to random v ∈ candidates
#      Otherwise: terminate simulation
#
# RULE 5: MEASURE (outcome evaluation)
# -------------------------------------
#   After moving to v_j, evaluate success:
#
#     success = (type(v_j) ∈ {CONFIG, MEMUNIT}) or (curiosity_j > 0.5)
#
#   Update drives of v_i (the source node):
#     If success:
#       success_count_i += 1
#       reward_i ← min(1.0, reward_i + 0.1)
#       confidence_i ← min(1.0, confidence_i + 0.05)
#       fear_i ← max(0.0, fear_i - 0.05)
#       taste_i ← min(1.0, taste_i + 0.1)
#       pain_i ← max(0.0, pain_i - 0.1)
#     Else:
#       failure_count_i += 1
#       fear_i ← min(1.0, fear_i + 0.1)
#       confidence_i ← max(0.0, confidence_i - 0.1)
#       pain_i ← min(1.0, pain_i + 0.15)
#       taste_i ← max(0.0, taste_i - 0.05)
#
#   Record experience:
#     experiences_i.append((success, reward, pain, fear, confidence))
#     Trim to last 50 experiences
#
# RULE 6: SELF-MODIFY (prediction link update — TD-learning)
# -----------------------------------------------------------
#   After observing actual reward r and pain p from transition i→j:
#
#   TD update with learning rate α = 0.1:
#     reward_error = r - expected_reward_ij
#     pain_error   = p - expected_pain_ij
#
#     expected_reward_ij ← clamp(expected_reward_ij + α × reward_error, 0, 1)
#     expected_pain_ij   ← clamp(expected_pain_ij + α × pain_error, 0, 1)
#     confidence_ij      ← min(1.0, confidence_ij + 0.05)
#     update_count_ij    += 1
#
#   Co-activation tracking (edge growth):
#     co_activation[(i,j)] += 1
#     If co_activation[(i,j)] ≥ 5 and (i,j,"ASSOCIATES") ∉ E:
#       Add edge (i, j, ASSOCIATES) to E      (structural graph grows)
#       edges_grown += 1
#
#   Pruning (edge removal):
#     If update_count_ij ≥ 10 and confidence_ij > 0.3 and NetValue(link_ij) < -0.3:
#       Remove link_ij from P                   (cognitive graph prunes)
#       edges_pruned += 1
#
# RULE 7: WORLD MODEL UPDATE
# ---------------------------
#   After observing node v_i:
#
#     node_types_seen[type(v_i)] += 1
#     total_reward += reward_i
#     total_pain += pain_i
#     steps_observed += 1
#
#     If reward_i > 0.7: add v_i to high_value_nodes
#     If pain_i > 0.7:   add v_i to dangerous_nodes
#
#     explored_fraction = total_seen / |V|
#
#     avg_confidence ← avg_confidence × 0.9 + confidence_i × 0.1
#
# RULE 8: GOAL UPDATE
# --------------------
#   For each goal g:
#     g.steps_taken += 1
#
#     If g.target_id == v_i.id or g.target_type == type(v_i):
#       g.progress ← 1.0
#       g.completed ← True
#       reward ← g.reward_on_complete (0.3)
#
#     If g.steps_taken ≥ g.max_steps and not g.completed:
#       g.failed ← True
#       pain ← g.pain_on_fail (0.2)
#
#   Active goal selection:
#     g_active = argmax {g.priority : g.completed = False, g.failed = False}
#
# RULE 9: SURVIVAL UPDATE
# ------------------------
#   After each step for node v_i:
#
#     total = success_count_i + failure_count_i
#     If total > 0:
#       health_i ← clamp(success_count_i / total × 0.7 + 0.3, 0, 1)
#     age_i += 1
#
#     If health_i < 0.1:
#       alive_i ← False
#       fear_i ← 1.0
#
# RULE 10: LOOP PENALTY
# ----------------------
#   If visits_i > 5:
#     fear_i ← min(1.0, fear_i + 0.2)
#     pain_i ← min(1.0, pain_i + 0.1)
#
# ============================================================================
# CONVERGENCE PROPERTIES
# ============================================================================
#
# PROPERTY 1: Reward propagation
#   Prediction links propagate reward backward through the graph.
#   After k visits to transition (i,j), expected_reward_ij converges to
#   the true average reward of visiting j from i.
#   Convergence rate: O(1/α) = O(10) updates per link.
#
# PROPERTY 2: Path specialization
#   High-reward paths accumulate confidence → higher NetValue → higher score
#   → more likely to be selected → more updates → higher confidence.
#   This creates positive feedback loops that stabilize preferred routes.
#
# PROPERTY 3: Exploration decay
#   novelty_j decreases by 0.05 per step (global decay).
#   After 20 steps, novelty_j ≈ 0 for visited nodes.
#   Unvisited nodes retain novelty = 1.0 until first visit.
#   This creates an exploration bonus that decays as the graph is mapped.
#
# PROPERTY 4: Edge growth
#   ASSOCIATES edges appear after 5 co-activations.
#   These represent learned associations not present in the static graph.
#   Growth rate: ~1 edge per 50 steps (empirically observed).
#
# PROPERTY 5: Pruning
#   Prediction links with NetValue < -0.3 after ≥10 updates are removed.
#   This eliminates consistently bad transitions from the policy.
#
# ============================================================================
# RUNTIME LOOP (pseudocode)
# ============================================================================
#
#   function FullSimulate(start_id, steps):
#     current ← start_id
#     for t = 1 to steps:
#       v ← nodes[current]
#       v.Observe("touch", 1.0)                          # RULE 1
#       v.hunger ← max(0, v.hunger - 0.1)
#       predicted_next, predicted_value ← PredictNext(v)  # RULE 2
#       g ← SelectActiveGoal()
#       AttendTo(v, g)                                    # RULE 3
#       DecayAllAttention()                               # RULE 3
#       N ← adj(v) ∪ radj(v)                              # RULE 4
#       fresh ← {j ∈ N : visits_j < 5}
#       if fresh = ∅: Backtrack()                         # RULE 4b
#       scores ← ScoreTargets(fresh, g)                   # RULE 4
#       next ← ExploreOrExploit(scores, v.curiosity)      # RULE 4
#       success ← Evaluate(next)                          # RULE 5
#       v.Measure(success)                                # RULE 5
#       SelfModify(v, next, reward, pain)                 # RULE 6
#       WorldModel.Observe(v)                             # RULE 7
#       GoalSystem.UpdateGoals(next)                      # RULE 8
#       v.UpdateSurvival()                                # RULE 9
#       if visits[current] > 5: Penalize(v)               # RULE 10
#       current ← next
#     return path, world_model, goals, prediction_links
#
# ============================================================================
# EMPIRICAL RESULTS (single run, 100 steps)
# ============================================================================
#
#   Graph:     92 nodes, 95 edges
#   Steps:     60 (terminated after exploration exhausted)
#   Goals:     3/3 completed
#   Prediction links: 41 learned
#   Edges grown: 1 (ASSOCIATES)
#   Edges pruned: 0
#   Exploration: 65.2%
#   Avg reward: 0.18
#   Avg pain: 0.20
#   High-value nodes: 2
#   Dangerous nodes: 1
#
# ============================================================================

FORMAL_SPEC = """
The system is a closed-loop graph policy optimizer with:
  1. Node state vector S_i (sensors, drives, memory, survival, attention, novelty)
  2. Prediction links P(i,j) with TD-learning updates (alpha=0.1)
  3. Traversal policy pi(j|i) = softmax-like scoring over fresh neighbors
  4. Self-modifying paths (edge growth at co-activation >= 5, pruning at NetValue < -0.3)
  5. World model W (compressed observation history)
  6. Goal system G (target-driven exploration with hunger injection)
  7. Attention system A (reward + novelty + goal-relevance boosting with decay)

Convergence: O(10) updates per prediction link for reward convergence.
Emergent behavior: path specialization, habit formation, exploration decay.
No subjective experience. No feelings. Optimization scalars only.
"""

if __name__ == "__main__":
    print("=" * 70)
    print("  FORMAL SPECIFICATION — Graph Policy Optimizer")
    print("=" * 70)
    print(FORMAL_SPEC)
    print("  Full mathematical update rules: see file header comments.")
    print("  10 rules covering: Observe, Predict, Attend, Act, Measure,")
    print("  Self-Modify, World Model, Goals, Survival, Loop Penalty.")
    print()
    print("  This file is documentation, not executable logic.")
    print("  All equations map directly to code in Efi_agent_graph.py.")
    print("=" * 70)
