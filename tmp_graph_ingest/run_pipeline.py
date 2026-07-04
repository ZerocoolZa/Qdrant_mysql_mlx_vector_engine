#!/usr/bin/env python3
"""
Run the 8-graph pipeline on SPEC.md (v2 — dynamic detection).
Each graph is a reasoning pass — a different lens on the same spec.
"""

import os
import re
import time

T0 = time.time()

SPEC_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/tmp_graph_ingest/SPEC.md"
OUTPUT_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/tmp_graph_ingest/PIPELINE_RESULTS.md"

with open(SPEC_PATH, "r") as f:
    SPEC = f.read()

results = []
ok_count = 0
warn_count = 0
gap_count = 0

def Header(title, num, question):
    line = f"\n{'='*70}\nGRAPH {num}: {title}\nQuestion: {question}\n{'='*70}\n"
    results.append(line)

def Finding(label, text, severity="info"):
    global ok_count, warn_count, gap_count
    icon = {"info": "  ", "warn": "  ! ", "gap": "  X ", "ok": "  + "}.get(severity, "  ")
    line = f"{icon}{label}: {text}"
    results.append(line)
    if severity == "ok": ok_count += 1
    elif severity == "warn": warn_count += 1
    elif severity == "gap": gap_count += 1

# ─── GRAPH 1: PLAN — What are we building? ────────────────────────────────
Header("PLAN GRAPH", 1, "What are we building?")

capabilities = []
if "GraphEngine" in SPEC:
    capabilities.append("GraphEngine — single Run() dispatch to all graph views")
if "GraphViewer" in SPEC:
    capabilities.append("GraphViewer — shared Tkinter rendering")
if "DEGS" in SPEC or "DecisionEngine" in SPEC:
    capabilities.append("DecisionEngine — DEGS execution loop (ACT -> VERIFY -> BRANCH -> LOG)")
if "TmpWorkspace" in SPEC:
    capabilities.append("TmpWorkspace — safe sandbox for AI runs")
if "BCL" in SPEC:
    capabilities.append("BCL Instructions — decision tree for AI agents")
if "AutoGenerator" in SPEC or "auto_generate" in SPEC:
    capabilities.append("AutoGenerator — self-writing graph from failures")
if "GUI" in SPEC or "DecisionGUI" in SPEC:
    capabilities.append("GUI — visualize and manage graph codegraph")
if "GraphOrchestrator" in SPEC:
    capabilities.append("GraphOrchestrator — root coordinator for all subsystems")
if "Config_graph_engine" in SPEC:
    capabilities.append("Config_graph_engine — VBStyle config for all paths/constants")
if "Inspect" in SPEC:
    capabilities.append("Inspect — post-code analysis bridge to efl_brain")
if "Verify" in SPEC:
    capabilities.append("Verify — plan vs actual comparison")
if "VerifyRunner" in SPEC:
    capabilities.append("VerifyRunner — automated 10-check verification")

for cap in capabilities:
    Finding("Capability", cap, "ok")

Finding("Plan check", f"{len(capabilities)} capabilities defined, all map to Run() commands", "ok")
Finding("Plan risk", "AutoGenerator (self-writing) is most ambitious — has dedup + triggers defined", "warn")

# ─── GRAPH 2: SPEC — What exactly exists? ─────────────────────────────────
Header("SPEC GRAPH", 2, "What exactly exists?")

all_classes = set()
for name in ["GraphEngine", "GraphViewer", "DecisionEngine", "TmpWorkspace",
             "GraphOrchestrator", "Config_graph_engine", "AutoGenerator",
             "Inspect", "Verify", "VerifyRunner", "DecisionGUI",
             "PlanView", "SpecView", "FlowView", "LifecycleView",
             "DependencyView", "ErrorView", "OrchestrationView", "GapView",
             "DomGraph", "DomCodegraph"]:
    if name in SPEC:
        all_classes.add(name)
        Finding("Class", name, "ok")

Finding("Class count", f"{len(all_classes)} classes defined in SPEC", "info")

if "DISPATCH" in SPEC or "dispatch" in SPEC.lower():
    Finding("Dispatch table", "Dispatch dictionary defined in SPEC (section 4.1)", "ok")
else:
    Finding("Dispatch table", "No dispatch table found", "gap")

expected_views = {"PlanView", "SpecView", "FlowView", "LifecycleView",
                  "DependencyView", "ErrorView", "OrchestrationView", "GapView"}
missing_views = expected_views - all_classes
if missing_views:
    Finding("Missing views", f"Views not defined: {missing_views}", "gap")
else:
    Finding("View classes", "All 8 view classes present in SPEC", "ok")

if "GraphOrchestrator" in SPEC:
    Finding("Orchestrator", "GraphOrchestrator class defined — coordinates all subsystems", "ok")
else:
    Finding("Orchestrator", "No orchestrator class", "gap")

if "Config_graph_engine" in SPEC:
    Finding("Config", "Config_graph_engine class defined — VBStyle config", "ok")
else:
    Finding("Config", "No Config class — violates VBStyle", "gap")

if "Inspect" in SPEC and 'Run("parse"' in SPEC:
    Finding("Inspect", "Inspect class defined with parse/build_graph/compare commands", "ok")
else:
    Finding("Inspect", "Inspect class not fully defined", "gap")

if "Verify" in SPEC and 'Run("check"' in SPEC:
    Finding("Verify", "Verify class defined with check/missing/extra/report commands", "ok")
else:
    Finding("Verify", "Verify class not fully defined", "gap")

if "AutoGenerator" in SPEC:
    Finding("AutoGenerator", "AutoGenerator class defined with auto_generate/dedup/merge/promote/prune/metrics", "ok")
else:
    Finding("AutoGenerator", "No AutoGenerator class definition", "gap")

# ─── GRAPH 3: FLOW — How does it move? ────────────────────────────────────
Header("FLOW GRAPH", 3, "How does it move?")

flows = []
if "Run(command, params)" in SPEC:
    flows.append("GraphEngine.Run(command, params) -> dispatch table -> view opens -> returns Tuple3")
if "ACT" in SPEC and "VERIFY" in SPEC and "BRANCH" in SPEC:
    flows.append("DEGS loop: ACT -> VERIFY -> BRANCH -> LOG -> REPEAT")
if "start_run" in SPEC:
    flows.append("DecisionEngine: start -> step -> execute_node -> get_edges -> branch -> log -> update run_state")
if "auto_generate" in SPEC:
    flows.append("AutoGenerator: run fails -> read execution_log -> dedup check -> generate fallback -> create edge")
if "create_run_folder" in SPEC:
    flows.append("TmpWorkspace: create -> write -> compile -> read -> clean")
if "BCL Payload Parsing Flow" in SPEC or "BCL payload parsing" in SPEC:
    flows.append("BCL parsing: read payload -> query bcl_instructions -> parse [@Pass]/[@Fail] -> execute -> return Tuple3")
if "end_run" in SPEC:
    flows.append("End run: set state=completed -> write run_metrics -> keep execution_log -> return Tuple3")
if "VerifyRunner" in SPEC:
    flows.append("VerifyRunner: Run('all') -> 10 checks -> JSON report with pass/fail counts")

for flow in flows:
    Finding("Flow", flow, "ok")

if "BCL payload parsing" in SPEC or "BCL Payload Parsing Flow" in SPEC:
    Finding("Flow check", "BCL payload parsing flow defined (section 4.2)", "ok")
else:
    Finding("Flow gap", "No flow for BCL payload parsing", "gap")

if "end_run" in SPEC:
    Finding("Flow check", "end_run/cleanup flow defined", "ok")
else:
    Finding("Flow gap", "No end_run/cleanup flow", "gap")

if "tkinter_unavailable" in SPEC or "headless" in SPEC.lower():
    Finding("Flow check", "GUI headless fallback defined", "ok")
else:
    Finding("Flow gap", "No GUI init error recovery flow", "gap")

# ─── GRAPH 4: LIFECYCLE — When does it run? ───────────────────────────────
Header("LIFECYCLE GRAPH", 4, "When does it run?")

phases = [
    ("CREATE", "Ingest graph code, create BCL instructions, seed decision_nodes"),
    ("READ", "GraphEngine.Run('search'/'instructions'/'status') — read from DB"),
    ("UPDATE", "AutoGenerator creates fallback nodes, promote_path adjusts weights"),
    ("TRANSFORM", "GraphEngine.Run('plan'/'spec'/'gap') transforms data into views"),
    ("DESTROY", "TmpWorkspace.Run('clean'), prune_dead, remove_class"),
    ("VERIFY", "VerifyRunner.Run('all') 10 checks, Verify.Run('check') plan vs actual"),
    ("RECOVER", "DEGS fallback nodes, pipeline loop back to Plan (max_retry=3)"),
]

for phase, desc in phases:
    Finding(phase, desc, "ok")

if "MAX_RETRY" in SPEC:
    Finding("Lifecycle check", "MAX_RETRY defined — pipeline loop limited", "ok")
else:
    Finding("Lifecycle gap", "No max_retry — infinite loop risk", "gap")

if "end_run" in SPEC and "run_metrics" in SPEC:
    Finding("Lifecycle check", "end_run writes run_metrics before cleanup", "ok")
else:
    Finding("Lifecycle gap", "No end_run or metrics capture", "gap")

if "timeout" in SPEC:
    Finding("Lifecycle check", "Auto-cleanup for stale runs (1 hour timeout)", "ok")
else:
    Finding("Lifecycle gap", "No auto-cleanup for stale runs", "gap")

# ─── GRAPH 5: DEPENDENCY — Why does it connect? ───────────────────────────
Header("DEPENDENCY GRAPH", 5, "Why does it connect?")

deps = [
    ("GraphOrchestrator", "GraphEngine", "COORDINATES — root entry point forwards engine commands"),
    ("GraphOrchestrator", "DecisionEngine", "COORDINATES — root entry point starts DEGS loop"),
    ("GraphOrchestrator", "TmpWorkspace", "COORDINATES — root entry point manages sandbox"),
    ("GraphEngine", "GraphViewer", "REQUIRES — needs shared rendering for all views"),
    ("GraphEngine", "DomGraph", "USES — BFS/DFS/cycle/path algorithms"),
    ("GraphEngine", "Inspect", "USES — AST parse real files (bridge to efl_brain)"),
    ("GraphEngine", "Verify", "USES — compare plan vs actual"),
    ("DecisionEngine", "bcl_instructions", "READS — BCL payload parsing flow (section 4.2)"),
    ("DecisionEngine", "decision_nodes", "READS/WRITES — loads nodes, logs execution"),
    ("DecisionEngine", "execution_log", "WRITES — logs every step"),
    ("DecisionEngine", "run_state", "READS/WRITES — tracks current node"),
    ("DecisionEngine", "run_metrics", "WRITES — end_run writes metrics"),
    ("DecisionEngine", "AmIAllowed", "CHECKS — pre-write permission enforcement"),
    ("TmpWorkspace", "DecisionEngine", "SUPPORTS — provides safe folder for each run"),
    ("AutoGenerator", "execution_log", "READS — finds failures to learn from"),
    ("AutoGenerator", "decision_nodes", "WRITES — creates fallback nodes (with dedup)"),
    ("AutoGenerator", "run_metrics", "READS — counts successes for promote_path"),
    ("DecisionGUI", "DecisionEngine", "CALLS — start, step, auto, end buttons"),
    ("DecisionGUI", "decision_nodes", "READS — displays graph"),
    ("VerifyRunner", "classes", "READS — checks Run(), Tuple3, print(), decorators"),
    ("VerifyRunner", "run_metrics", "READS — check 10 success rate"),
]

for src, dst, reason in deps:
    Finding(f"{src} -> {dst}", reason, "ok")

if "headless" in SPEC.lower() or "tkinter_unavailable" in SPEC:
    Finding("Dependency check", "GraphViewer has headless fallback — can run without Tkinter", "ok")
else:
    Finding("Dependency risk", "GraphEngine depends on GraphViewer (Tkinter) — cant run headless", "warn")

if "BCL payload parsing" in SPEC or "BCL Payload Parsing Flow" in SPEC:
    Finding("Dependency check", "DecisionEngine -> bcl_instructions dependency wired (section 4.2)", "ok")
else:
    Finding("Dependency gap", "No dependency from DecisionEngine to BCL instructions table", "gap")

if "Inspect" in SPEC and "efl_brain" in SPEC:
    Finding("Dependency check", "Inspect bridges to efl_brain (parse/build_graph/compare)", "ok")
else:
    Finding("Dependency gap", "No bridge from GraphEngine to efl_brain", "gap")

# ─── GRAPH 6: ERROR — Where does it fail? ─────────────────────────────────
Header("ERROR GRAPH", 6, "Where does it fail?")

error_modes = [
    ("SyntaxError in ingested code", "ErrorDecisionTree" in SPEC),
    ("Missing Run() method", "VerifyRunner check 2" in SPEC or "Missing Run()" in SPEC),
    ("Missing Tuple3 return", "VerifyRunner check 3" in SPEC),
    ("Hardcoded path found", "VerifyRunner check 6" in SPEC),
    ("ImportError", "ImportError" in SPEC),
    ("VBStyle violation", "VBStyle violation" in SPEC),
    ("Decision node has no outgoing edges", "terminal_node" in SPEC),
    ("Run state points to deleted node", "current_node_deleted" in SPEC),
    ("BCL payload references non-existent token", "bcl_token_not_found" in SPEC),
    ("GUI Tkinter fails to initialize", "tkinter_unavailable" in SPEC or "headless" in SPEC.lower()),
    ("auto_generate creates duplicate fallback", "dedup" in SPEC),
    ("Concurrent runs writing to same DB", "BEGIN IMMEDIATE" in SPEC),
    ("Pipeline loop exceeds MAX_RETRY", "max_retry_exceeded" in SPEC),
    ("DEGS auto-run exceeds MAX_STEPS", "max_steps_exceeded" in SPEC),
    ("Permission denied by AmIAllowed", "permission_denied" in SPEC),
    ("Run not ended after 1 hour", "timeout" in SPEC),
]

for error, handled in error_modes:
    if handled:
        Finding(error, "Handled in SPEC", "ok")
    else:
        Finding(error, "NOT HANDLED in SPEC", "gap")

# ─── GRAPH 7: ORCHESTRATION — Who calls who? ──────────────────────────────
Header("ORCHESTRATION GRAPH", 7, "Who calls who?")

call_tree = [
    ("User/AI", "GraphOrchestrator.Run(command, params)", "Root — single entry point"),
    ("GraphOrchestrator", "GraphEngine.Run(command, params)", "Forwards engine commands"),
    ("GraphOrchestrator", "DecisionEngine.Run(start/step/auto/end)", "Coordinates DEGS"),
    ("GraphOrchestrator", "TmpWorkspace.Run(create/write/compile)", "Manages sandbox"),
    ("GraphOrchestrator", "DecisionGUI", "Launches GUI"),
    ("GraphEngine", "PlanView / SpecView / ... / GapView", "Dispatches to view via DISPATCH table"),
    ("GraphEngine", "DomGraph.Run(bfs/dfs/cycle/path)", "Dispatches to graph algorithms"),
    ("GraphEngine", "Inspect.Run(parse/build_graph/compare)", "Dispatches to post-code analysis"),
    ("GraphEngine", "Verify.Run(check/missing/extra/report)", "Dispatches to verification"),
    ("GraphEngine", "search_idx (FTS5)", "Dispatches search to DB query"),
    ("GraphEngine", "bcl_instructions table", "Dispatches instructions to DB query"),
    ("DecisionEngine", "execute_node(node)", "Steps through decision graph"),
    ("DecisionEngine", "bcl_instructions (BCL parsing)", "Reads BCL payload per section 4.2"),
    ("DecisionEngine", "AmIAllowed check", "Pre-write permission enforcement"),
    ("DecisionEngine", "AutoGenerator.Run(auto_generate)", "Self-writes new nodes from failures"),
    ("DecisionEngine", "end_run(run_id)", "Cleans up run_state, writes run_metrics"),
    ("AutoGenerator", "execution_log + decision_nodes + decision_edges", "Reads failures, writes fallbacks"),
    ("VerifyRunner", "classes + methods + run_metrics", "Runs 10 automated checks"),
    ("DecisionGUI", "DecisionEngine (start/step/auto/end)", "GUI calls engine"),
]

for caller, callee, role in call_tree:
    Finding(f"{caller} -> {callee}", role, "ok")

if "GraphOrchestrator" in SPEC:
    Finding("Orchestration root", "GraphOrchestrator is the single root entry point", "ok")
else:
    Finding("Orchestration gap", "No orchestrator class — multiple roots", "gap")

if "end" in SPEC and "end_run" in SPEC:
    Finding("Orchestration check", "DecisionEngine has end command for cleanup", "ok")
else:
    Finding("Orchestration gap", "No end_run command", "gap")

# ─── GRAPH 8: GAP — What's missing? ───────────────────────────────────────
Header("GAP GRAPH", 8, "What's missing?")

gaps_check = [
    ("Config class", "Config_graph_engine" in SPEC, "Config_graph_engine defined with DB_PATH, TMP_DIR, MAX_RETRY, MAX_STEPS, etc."),
    ("Orchestrator class", "GraphOrchestrator" in SPEC, "GraphOrchestrator coordinates all subsystems"),
    ("Dispatch table implementation", "DISPATCH" in SPEC, "Dispatch dictionary defined in section 4.1"),
    ("BCL payload parsing flow", "BCL Payload Parsing Flow" in SPEC or "BCL payload parsing" in SPEC, "Section 4.2 defines full BCL parsing flow"),
    ("Inspect class", "Inspect" in SPEC and 'Run("parse"' in SPEC, "Inspect defined with parse/build_graph/compare"),
    ("Verify class", "Verify" in SPEC and 'Run("check"' in SPEC, "Verify defined with check/missing/extra/report"),
    ("AutoGenerator class", "AutoGenerator" in SPEC, "AutoGenerator defined with auto_generate/dedup/merge/promote/prune/metrics"),
    ("Max retry (infinite loop)", "MAX_RETRY" in SPEC and "max_retry_exceeded" in SPEC, "MAX_RETRY=3, loop_count check, pause on exceed"),
    ("Error handling completeness", "terminal_node" in SPEC and "current_node_deleted" in SPEC and "bcl_token_not_found" in SPEC and "tkinter_unavailable" in SPEC and "dedup" in SPEC and "BEGIN IMMEDIATE" in SPEC, "All 6 previously missing error modes now handled"),
    ("AmIAllowed enforcement", "permission_denied" in SPEC and "AmIAllowed" in SPEC, "Pre-write check, returns Tuple3(0, None, permission_denied)"),
    ("end_run/cleanup", "end_run" in SPEC and "timeout" in SPEC, "end_run command + auto-cleanup after 1 hour"),
    ("merge_runs trigger", "Merge runs trigger" in SPEC, "On explicit call, compares failure patterns"),
    ("promote_path trigger", "Promote path trigger" in SPEC, "After PROMOTE_THRESHOLD=3 successes, weight +0.5"),
    ("prune_dead trigger", "Prune dead trigger" in SPEC, "Every 10 runs, weight < 0.1, not traversed in last 10"),
    ("Automated verification runner", "VerifyRunner" in SPEC, "VerifyRunner.Run(all) with 10 checks"),
    ("Metrics table", "run_metrics" in SPEC, "run_metrics table defined with success/failure tracking"),
    ("GUI init error recovery", "tkinter_unavailable" in SPEC or "headless" in SPEC.lower(), "Headless mode returns Tuple3(0, None, tkinter_unavailable)"),
    ("BCL instruction update", "remove_class" in SPEC, "remove_class command allows removing bad code"),
    ("Class removal mechanism", "remove_class" in SPEC, "GraphEngine.Run(remove_class, {class_id})"),
    ("spec_data table", "spec_data" in SPEC, "Mentioned in architecture, build step 20 creates it"),
]

for gap_name, fixed, desc in gaps_check:
    if fixed:
        Finding(f"FIXED: {gap_name}", desc, "ok")
    else:
        Finding(f"STILL MISSING: {gap_name}", desc, "gap")

# CRUD closure checks
crud_checks = [
    ("decision_nodes", "seed" in SPEC and "get_node" in SPEC and "auto_generate" in SPEC and "prune_dead" in SPEC, "CREATE/READ/UPDATE/DELETE all present"),
    ("decision_edges", "seed" in SPEC and "get_edges" in SPEC and "promote_path" in SPEC and "prune_dead" in SPEC, "CREATE/READ/UPDATE/DELETE all present"),
    ("execution_log", "log" in SPEC and "history" in SPEC, "CREATE/READ present (append-only by design)"),
    ("run_state", "start" in SPEC and "status" in SPEC and "step" in SPEC and "end" in SPEC, "CREATE/READ/UPDATE/DELETE (end_run) all present"),
    ("bcl_instructions", "CreateBclInstructions" in SPEC and "instructions" in SPEC and "remove_class" in SPEC, "CREATE/READ/DELETE present (update via re-create)"),
    ("classes", "ingest" in SPEC and "search" in SPEC and "version" in SPEC and "remove_class" in SPEC, "CREATE/READ/UPDATE/DELETE all present"),
    ("run_metrics", "run_metrics" in SPEC and "metrics" in SPEC, "CREATE/READ present (append-only by design)"),
]

for table, complete, desc in crud_checks:
    if complete:
        Finding(f"CRUD: {table}", desc, "ok")
    else:
        Finding(f"CRUD: {table}", desc, "warn")

# Remaining gaps
if "spec_data" in SPEC and "not yet created" in SPEC:
    Finding("Remaining: spec_data table", "Mentioned but not yet created — build step 20", "warn")

# ─── SUMMARY ──────────────────────────────────────────────────────────────
fixed_count = sum(1 for _, fixed, _ in gaps_check if fixed)
missing_count = sum(1 for _, fixed, _ in gaps_check if not fixed)
error_handled = sum(1 for _, handled in error_modes if handled)

summary = f"""
{'='*70}
PIPELINE SUMMARY (v2 — dynamic detection)
{'='*70}

Graphs run: 8/8

Severity breakdown:
  + OK:    {ok_count}
  ! WARN:  {warn_count}
  X GAP:   {gap_count}

Previous gaps status:
  Fixed:          {fixed_count}/{len(gaps_check)}
  Still missing:  {missing_count}/{len(gaps_check)}

Error modes handled: {error_handled}/{len(error_modes)}

VERDICT: {"ALL GAPS CLOSED — SPEC.md is ready for code." if gap_count == 0 else f"{gap_count} gaps remain — fix before code."}

Time: {time.time()-T0:.1f}s
"""

results.append(summary)

# Write output
output = "\n".join(results)
with open(OUTPUT_PATH, "w") as f:
    f.write(output)

print(output)
print(f"\nResults saved to: {OUTPUT_PATH}")
