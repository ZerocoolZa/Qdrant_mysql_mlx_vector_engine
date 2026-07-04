#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_efl_brain.py>][@domain<efl_brain>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for efl_brain domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- Agent Graph Tuning Parameters -----------------------------
LEARNING_RATE_INITIAL = 0.3    # Initial learning rate for prediction links (fresh links learn fast)
LEARNING_RATE_FINAL = 0.01     # Minimum learning rate floor (confident links learn slow, refine)
CONSOLIDATION_INTERVAL = 30    # Run consolidation (sleep) every N simulation steps
HUB_THRESHOLD = 3              # Minimum outgoing edges for a node to be classified as a hub
MAX_DEPTH = 10                 # Maximum depth for path search and convergence iterations

# -- File Inventory --------------------------------------------
    # -- Config_efl_brain.py --
    # Purpose: EFL Brain — Gold Standard Config.
    # Lines: 1514 | Classes: 8 | Methods: 0
    #   Class: BracketProp -- methods: __init__, set, reset, to_dict
    #   Class: BracketContainer -- methods: __init__, add_prop, add_container, get_prop, get_container, get, set, prop_names, container_names, reset_all
    #   Class: BracketParser -- methods: parse, parse_token_entry, serialize, _val_to_str, _tokenize, _find_matching_paren, _split_tuple, _split_semicolons, _parse_value, _parse_items
    #   Class: ConfigEflBrain -- methods: __init__, Run, _get, _set, _mysql, _vbstyle, read_state, set_config
    #   Class: SchemaConfig -- methods: __init__, Run, _all, _tables, _views, _indexes, _seed, _full_schema, read_state, set_config
    #   Class: LintConfig -- methods: __init__, Run, _rules, _thresholds, _reserved, _enabled, read_state, set_config
    #   Class: TargetConfig -- methods: __init__, Run, _all, _classes, _scripts, read_state, set_config
    #   Class: BracketConfig -- methods: __init__, Run, _parse, _serialize, _load, _save, _resolve_path, _get, _set, _reset
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- Efi_agent_brain.py --
    # Purpose: Agent Brain — learning layer on top of Agent Graph.
    # Lines: 1019 | Classes: 6 | Methods: 0
    #   Class: TemporalMemory -- methods: __init__, Snapshot, _DiffSnapshots, GetHistory, ToDict
    #   Class: GoalSystem -- methods: __init__, AddGoal, GetActiveGoal, CompleteGoal, ApplyHunger, ToDict
    #   Class: WorldModel -- methods: __init__, Observe, Predict, ComparePrediction, GetAccuracy, ToDict
    #   Class: ExecutionHistory -- methods: __init__, LogRun, GetStats, ToDict
    #   Class: AttentionSystem -- methods: __init__, UpdateAttention, GetFocus, GetTopNodes, ToDict
    #   Class: AgentBrain -- methods: __init__, Build, Simulate, Evolve, WhatBreaksIfThisDies, WhatReachesThis, ShortestPath, RealBootSequence, Communities, Centrality
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- Efi_agent_graph.py --
    # Purpose: Agent Graph Engine — auto-discovers architecture from codebase.
    # Lines: 2827 | Classes: 11 | Methods: 0
    #   Class: AgentNode -- methods: __init__, Observe, Predict, Act, Measure, UpdateSurvival, BoostAttention, DecayAttention, ToDict
    #   Class: Edge -- methods: __init__, ToDict
    #   Class: PredictionLink -- methods: __init__, Update, NetValue, ToDict
    #   Class: WorldModel -- methods: __init__, Observe, Summary
    #   Class: Goal -- methods: __init__, CheckProgress, ToDict
    #   Class: GoalSystem -- methods: __init__, AddGoal, SelectActiveGoal, InjectDrive, UpdateGoals, Summary
    #   Class: EmotionalState -- methods: __init__, Update, Trend, ExplorationBias, ToDict
    #   Class: Consolidation -- methods: __init__, Consolidate, ToDict
    #   Class: AdversarialAgent -- methods: __init__, SetStrength, SetAggression, Attack, PoisonLinks, InjectFear, BlockNodes, FalseReward, UnblockAll, ToDict
    #   Class: MysqlKnowledgeConnector -- methods: __init__, Connect, Disconnect, LoadLearnedRules, SeedGraphFromRules, WriteOutcomeToMysql, ToDict
    #   Class: AgentGraph -- methods: __init__, AddNode, AddEdge, Build, ParsePythonFile, BuildImportEdges, BuildCallEdges, FindCallerClass, InitializeSensors, BuildTypedGraph
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- Efi_boot_graph.py --
    # Purpose: Execution Graph Validator + Self-Modifying Topology
    # Lines: 693 | Classes: 1 | Methods: 2
    #   Class: ExecutionGraph -- methods: __init__, AddNode, AddDependency, AddRuntimeRule, IsValidOrder, ExecutePath, BuildGraph, ScorePath, HealFailedPaths, Converge
    #   Functions: DemoConfigArchitecture, DemoFolderScan
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- Efi_brain_db.py --
    # Purpose: Brain Database — the dinner table for all brothers.
    # Lines: 342 | Classes: 1 | Methods: 0
    #   Class: BrainDb -- methods: __init__, Connect, Disconnect, _CreateTables, WritePredictionLinks, ReadPredictionLinks, WriteWorldModel, ReadWorldModel, WriteEmotionalState, ReadEmotionalState
    #   VBStyle: NO_Run | init | NO_state | PRINT | no_decorator

    # -- Efi_code_graph.py --
    # Purpose: Typed-State Code Graph — proper graph primitives.
    # Lines: 373 | Classes: 3 | Methods: 0
    #   Class: Node -- methods: __init__, ToDict
    #   Class: Edge -- methods: __init__, ToDict
    #   Class: TypedGraph -- methods: __init__, AddNode, AddEdge, Build, ParsePythonFile, BuildImportEdges, DetectCycles, FindPaths, GetRoots, GetLeaves
    #   VBStyle: NO_Run | init | state | PRINT | no_decorator

    # -- Efi_connector.py --
    # Purpose: Connector Brother — builds the agent graph from the database.
    # Lines: 363 | Classes: 1 | Methods: 0
    #   Class: Connector -- methods: __init__, BuildFromDb, WriteToDb, Summary, Run
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- Efi_core.py --
    # Purpose: EFL Brain — single entry point.
    # Lines: 1076 | Classes: 0 | Methods: 16
    #   Functions: get_conn, init_schema, pull_mysql, ingest_script, build_units, build_graph, cmd_build, cmd_status, cmd_exec, cmd_query
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- Efi_formal_spec.py --
    # Purpose: N/A
    # Lines: 349 | Classes: 0 | Methods: 0
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- Efi_graph_viewer.py --
    # Purpose: Efi Graph Viewer — loads Efi_code_graph.json (typed-state format) and renders
    # Lines: 475 | Classes: 1 | Methods: 0
    #   Class: GraphViewer -- methods: __init__, LoadGraph, LoadAgentGraphLive, BuildUI, ToggleFilter, LayoutNodes, DrawGraph, GetNodeAt, OnMotion, OnClick
    #   VBStyle: NO_Run | init | state | no_print | no_decorator

    # -- Efi_knowledge_archaeology.py --
    # Purpose: MySQL Architecture Archaeology — streaming, row-capped, progress-printing.
    # Lines: 341 | Classes: 0 | Methods: 0
    #   VBStyle: NO_Run | NO_init | state | PRINT | no_decorator

    # -- Efi_md_viewer.py --
    # Purpose: PyQt6 Markdown Viewer with Search + Match Navigation.
    # Lines: 257 | Classes: 1 | Methods: 1
    #   Class: MdViewer -- methods: __init__, _build_ui, load_file, clear_highlights, do_search, highlight_current, next_match, prev_match
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- Efi_orchestrator.py --
    # Purpose: Orchestrator Brother — the single entry point for the full efl_brain pipeline.
    # Lines: 542 | Classes: 1 | Methods: 0
    #   Class: Orchestrator -- methods: __init__, _StepBuild, _StepConnect, _StepSimulate, _StepDiff, _StepRepair, _StepScan, _StepReport, RunPipeline, RunStep
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- Efi_ram_ai.py --
    # Purpose: EFL RAM AI — Error → Fix Learning Loop
    # Lines: 1865 | Classes: 10 | Methods: 1
    #   Class: MemoryDB -- methods: __init__, _init, insert, record_fix_outcome, learn_rule, add_extracted_rule, fetch_extracted_rules, update_extracted_rule, fetch_all, fetch_learned_rules
    #   Class: BrokenCodeGenerator -- methods: __init__, generate, missing_colon, missing_colon_if, missing_colon_for, missing_colon_class, missing_paren, missing_comma, wrong_keyword, broken_bracket
    #   Class: ASTErrorInjector -- methods: generate, _inject
    #   Class: StaticAnalyzer -- methods: __init__, analyze, _layer1_ast, _get_literal, _layer2_patterns, _layer3_pyflakes, summary
    #   Class: Executor -- methods: run
    #   Class: RepairEngine -- methods: fix, fix_indentation, fix_missing_quote
    #   Class: RuleExtractor -- methods: _error_sig, _meta_class, extract, apply
    #   Class: MetaController -- methods: __init__, record, adapt, best_strategy, stats
    #   Class: EFLLoop -- methods: __init__, step_silent, run_parallel, _print_stats, step, run, self_analyze
    #   Class: _Reporter -- methods: unexpectedError, syntaxError, flake
    #   Functions: _parallel_worker
    #   VBStyle: NO_Run | init | NO_state | PRINT | DECOR

    # -- Efi_repair.py --
    # Purpose: Repair Brother — generates code fixes for gaps found by the diff engine.
    # Lines: 508 | Classes: 1 | Methods: 0
    #   Class: RepairEngine -- methods: __init__, ReadGaps, ReadLearnedFixes, ReadFragility, GenerateFix, _GenerateMethod, _GenerateEdge, _GenerateUnit, _ValidateCode, WriteFixes
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- Efi_solution_engine.py --
    # Purpose: Config Solution Engine — scans real folders, detects violations, generates fixes.
    # Lines: 795 | Classes: 1 | Methods: 1
    #   Class: ConfigSolutionEngine -- methods: __init__, ScanFile, FixGhostHeader, FixVBStyleHeader, FixClassHeader, FixMethodDocstring, FixFileIndex, ScanFolder, GenerateReport, AnalyzeBlastRadius
    #   Functions: PrintReport
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- Efi_test_config_rules.py --
    # Purpose: Config Architecture Test Suite — tests all dimensions of the config pattern.
    # Lines: 1062 | Classes: 7 | Methods: 22
    #   Class: TestConfig -- methods: GetVersion
    #   Class: MockMemUnit -- methods: __init__, Run
    #   Class: TestConfig -- methods: __init__
    #   Class: MockConfig -- methods: __init__
    #   Class: MockMemUnit -- methods: __init__, Run
    #   Class: MockApp -- methods: __init__, Execute
    #   Class: TestConfig -- methods: GetAbout, GetHelp, GetReadme
    #   Functions: Result, Skip, TestBootCold, TestValueLoading, TestEnvOverrides, TestSingleton, TestServiceContainer, TestTuple3, TestNoHardcoding, TestNoHiddenDeps
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- test_comparison.py --
    # Purpose: Comparison Test — Cross-Imports vs Database-Mediated Communication
    # Lines: 389 | Classes: 0 | Methods: 5
    #   Functions: test_coupling, test_communities, test_startup_time, test_resilience, test_data_flow
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "Config_efl_brain.py": {
        "purpose": "EFL Brain — Gold Standard Config.",
        "lines": 1514,
        "classes": ["BracketProp", "BracketContainer", "BracketParser", "ConfigEflBrain", "SchemaConfig", "LintConfig", "TargetConfig", "BracketConfig"],
        "methods": [],
    },
    "Efi_agent_brain.py": {
        "purpose": "Agent Brain — learning layer on top of Agent Graph.",
        "lines": 1019,
        "classes": ["TemporalMemory", "GoalSystem", "WorldModel", "ExecutionHistory", "AttentionSystem", "AgentBrain"],
        "methods": [],
    },
    "Efi_agent_graph.py": {
        "purpose": "Agent Graph Engine — auto-discovers architecture from codebase.",
        "lines": 2827,
        "classes": ["AgentNode", "Edge", "PredictionLink", "WorldModel", "Goal", "GoalSystem", "EmotionalState", "Consolidation", "AdversarialAgent", "MysqlKnowledgeConnector", "AgentGraph"],
        "methods": [],
    },
    "Efi_boot_graph.py": {
        "purpose": "Execution Graph Validator + Self-Modifying Topology",
        "lines": 693,
        "classes": ["ExecutionGraph"],
        "methods": ["DemoConfigArchitecture", "DemoFolderScan"],
    },
    "Efi_brain_db.py": {
        "purpose": "Brain Database — the dinner table for all brothers.",
        "lines": 342,
        "classes": ["BrainDb"],
        "methods": [],
    },
    "Efi_code_graph.py": {
        "purpose": "Typed-State Code Graph — proper graph primitives.",
        "lines": 373,
        "classes": ["Node", "Edge", "TypedGraph"],
        "methods": [],
    },
    "Efi_connector.py": {
        "purpose": "Connector Brother — builds the agent graph from the database.",
        "lines": 363,
        "classes": ["Connector"],
        "methods": [],
    },
    "Efi_core.py": {
        "purpose": "EFL Brain — single entry point.",
        "lines": 1076,
        "classes": [],
        "methods": ["get_conn", "init_schema", "pull_mysql", "ingest_script", "build_units", "build_graph", "cmd_build", "cmd_status", "cmd_exec", "cmd_query", "cmd_trace", "cmd_reuse", "cmd_diff", "_get_expectations", "cmd_feedback", "main"],
    },
    "Efi_formal_spec.py": {
        "purpose": "",
        "lines": 349,
        "classes": [],
        "methods": [],
    },
    "Efi_graph_viewer.py": {
        "purpose": "Efi Graph Viewer — loads Efi_code_graph.json (typed-state format) and renders",
        "lines": 475,
        "classes": ["GraphViewer"],
        "methods": [],
    },
    "Efi_knowledge_archaeology.py": {
        "purpose": "MySQL Architecture Archaeology — streaming, row-capped, progress-printing.",
        "lines": 341,
        "classes": [],
        "methods": [],
    },
    "Efi_md_viewer.py": {
        "purpose": "PyQt6 Markdown Viewer with Search + Match Navigation.",
        "lines": 257,
        "classes": ["MdViewer"],
        "methods": ["main"],
    },
    "Efi_orchestrator.py": {
        "purpose": "Orchestrator Brother — the single entry point for the full efl_brain pipeline.",
        "lines": 542,
        "classes": ["Orchestrator"],
        "methods": [],
    },
    "Efi_ram_ai.py": {
        "purpose": "EFL RAM AI — Error → Fix Learning Loop",
        "lines": 1865,
        "classes": ["MemoryDB", "BrokenCodeGenerator", "ASTErrorInjector", "StaticAnalyzer", "Executor", "RepairEngine", "RuleExtractor", "MetaController", "EFLLoop", "_Reporter"],
        "methods": ["_parallel_worker"],
    },
    "Efi_repair.py": {
        "purpose": "Repair Brother — generates code fixes for gaps found by the diff engine.",
        "lines": 508,
        "classes": ["RepairEngine"],
        "methods": [],
    },
    "Efi_solution_engine.py": {
        "purpose": "Config Solution Engine — scans real folders, detects violations, generates fixes.",
        "lines": 795,
        "classes": ["ConfigSolutionEngine"],
        "methods": ["PrintReport"],
    },
    "Efi_test_config_rules.py": {
        "purpose": "Config Architecture Test Suite — tests all dimensions of the config pattern.",
        "lines": 1062,
        "classes": ["TestConfig", "MockMemUnit", "TestConfig", "MockConfig", "MockMemUnit", "MockApp", "TestConfig"],
        "methods": ["Result", "Skip", "TestBootCold", "TestValueLoading", "TestEnvOverrides", "TestSingleton", "TestServiceContainer", "TestTuple3", "TestNoHardcoding", "TestNoHiddenDeps", "TestFileIndexMatch", "TestVBStyleCompliance", "TestCodeGraph", "TestDeadCode", "TestTodoScan", "TestCrossFolder", "TestFileHash", "TestSelfValidation", "TestImportGraph", "TestStartupOrder", "TestEmbeddedSchema", "TestDocConstants"],
    },
    "test_comparison.py": {
        "purpose": "Comparison Test — Cross-Imports vs Database-Mediated Communication",
        "lines": 389,
        "classes": [],
        "methods": ["test_coupling", "test_communities", "test_startup_time", "test_resilience", "test_data_flow"],
    },
}
# -- Classes Dict ----------------------------------------------
CLASSES = {
    "BracketProp": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "set", "reset", "to_dict"],
    },
    "BracketContainer": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "add_prop", "add_container", "get_prop", "get_container", "get", "set", "prop_names", "container_names", "reset_all", "from_dict", "to_dict"],
    },
    "BracketParser": {
        "file": "Config_efl_brain.py",
        "methods": ["parse", "parse_token_entry", "serialize", "_val_to_str", "_tokenize", "_find_matching_paren", "_split_tuple", "_split_semicolons", "_parse_value", "_parse_items"],
    },
    "ConfigEflBrain": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "Run", "_get", "_set", "_mysql", "_vbstyle", "read_state", "set_config"],
    },
    "SchemaConfig": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "Run", "_all", "_tables", "_views", "_indexes", "_seed", "_full_schema", "read_state", "set_config"],
    },
    "LintConfig": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "Run", "_rules", "_thresholds", "_reserved", "_enabled", "read_state", "set_config"],
    },
    "TargetConfig": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "Run", "_all", "_classes", "_scripts", "read_state", "set_config"],
    },
    "BracketConfig": {
        "file": "Config_efl_brain.py",
        "methods": ["__init__", "Run", "_parse", "_serialize", "_load", "_save", "_resolve_path", "_get", "_set", "_reset", "_list", "_validate", "_validate_recursive", "_export_json", "_import_json", "_diff", "_diff_dicts", "read_state", "set_config"],
    },
    "TemporalMemory": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "Snapshot", "_DiffSnapshots", "GetHistory", "ToDict"],
    },
    "GoalSystem": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "AddGoal", "GetActiveGoal", "CompleteGoal", "ApplyHunger", "ToDict"],
    },
    "WorldModel": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "Observe", "Predict", "ComparePrediction", "GetAccuracy", "ToDict"],
    },
    "ExecutionHistory": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "LogRun", "GetStats", "ToDict"],
    },
    "AttentionSystem": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "UpdateAttention", "GetFocus", "GetTopNodes", "ToDict"],
    },
    "AgentBrain": {
        "file": "Efi_agent_brain.py",
        "methods": ["__init__", "Build", "Simulate", "Evolve", "WhatBreaksIfThisDies", "WhatReachesThis", "ShortestPath", "RealBootSequence", "Communities", "Centrality", "Influence", "Cycles", "AttentionReport", "PredictionAccuracy", "GoalStatus", "TemporalChanges", "ExecutionStats", "Export", "Run", "RunSimulate", "RunEvolve", "RunBlast", "RunReaches", "RunPath", "RunBoot", "RunCommunities", "RunCentral", "RunInfluence", "RunCycles", "RunAttention", "RunAccuracy", "RunGoals", "RunExport"],
    },
    "AgentNode": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Observe", "Predict", "Act", "Measure", "UpdateSurvival", "BoostAttention", "DecayAttention", "ToDict"],
    },
    "Edge": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "ToDict"],
    },
    "PredictionLink": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Update", "NetValue", "ToDict"],
    },
    "WorldModel": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Observe", "Summary"],
    },
    "Goal": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "CheckProgress", "ToDict"],
    },
    "GoalSystem": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "AddGoal", "SelectActiveGoal", "InjectDrive", "UpdateGoals", "Summary"],
    },
    "EmotionalState": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Update", "Trend", "ExplorationBias", "ToDict"],
    },
    "Consolidation": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Consolidate", "ToDict"],
    },
    "AdversarialAgent": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "SetStrength", "SetAggression", "Attack", "PoisonLinks", "InjectFear", "BlockNodes", "FalseReward", "UnblockAll", "ToDict"],
    },
    "MysqlKnowledgeConnector": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "Connect", "Disconnect", "LoadLearnedRules", "SeedGraphFromRules", "WriteOutcomeToMysql", "ToDict"],
    },
    "AgentGraph": {
        "file": "Efi_agent_graph.py",
        "methods": ["__init__", "AddNode", "AddEdge", "Build", "ParsePythonFile", "BuildImportEdges", "BuildCallEdges", "FindCallerClass", "InitializeSensors", "BuildTypedGraph", "ValidateBootSequence", "StructuralAnalysis", "DetectCycles", "ShortestPath", "AllPaths", "WhatReachesThis", "BlastRadius", "Centrality", "BetweennessCentrality", "DetectCommunities", "BootSequence", "GetIslands", "GetOrCreatePredictionLink", "PredictNext", "FindNearestNodeOfType", "PathToTarget", "MultiStepPlan", "AdaptiveAlpha", "AttendTo", "SelfModify", "UpdateWorldModel", "SeedFromMysql", "WriteToDb", "ReadFromDb", "YinYangSimulate", "FullSimulate", "Simulate", "InfluenceRanking", "Export", "_TypeCounts", "Run", "RunBlastRadius", "RunReaches", "RunShortestPath", "RunAllPaths", "RunBootSequence", "RunCommunities", "RunCentrality", "RunInfluence", "RunIslands", "RunSimulate", "RunCycles", "RunExport", "RunPredict", "RunAttend", "RunSelfModify", "RunWorldModel", "RunGoals", "RunFullSimulate", "RunEmotion", "RunConsolidation", "RunPlan", "RunYinYang", "RunSeedMysql", "RunStructural", "RunValidateBoot", "RunWriteDb", "RunReadDb"],
    },
    "ExecutionGraph": {
        "file": "Efi_boot_graph.py",
        "methods": ["__init__", "AddNode", "AddDependency", "AddRuntimeRule", "IsValidOrder", "ExecutePath", "BuildGraph", "ScorePath", "HealFailedPaths", "Converge", "DetectCycles", "DetectDeadStates", "DetectUnreachable", "GetBestPaths", "GenerateReport", "ScanFolder", "HashFiles", "Run", "RunAnalyze", "RunConverge", "RunScan", "RunReport", "RunCycles", "RunDead", "RunUnreachable", "RunBest", "RunHashes"],
    },
    "BrainDb": {
        "file": "Efi_brain_db.py",
        "methods": ["__init__", "Connect", "Disconnect", "_CreateTables", "WritePredictionLinks", "ReadPredictionLinks", "WriteWorldModel", "ReadWorldModel", "WriteEmotionalState", "ReadEmotionalState", "WriteBlastRadius", "ReadBlastRadius", "WriteViolations", "ReadViolations", "UpdateViolationBlastRadius", "ReadAllForVisualization", "Stats"],
    },
    "Node": {
        "file": "Efi_code_graph.py",
        "methods": ["__init__", "ToDict"],
    },
    "Edge": {
        "file": "Efi_code_graph.py",
        "methods": ["__init__", "ToDict"],
    },
    "TypedGraph": {
        "file": "Efi_code_graph.py",
        "methods": ["__init__", "AddNode", "AddEdge", "Build", "ParsePythonFile", "BuildImportEdges", "DetectCycles", "FindPaths", "GetRoots", "GetLeaves", "GetHubs", "GetTypeCounts", "IsDAG", "GetComponents", "Export"],
    },
    "Connector": {
        "file": "Efi_connector.py",
        "methods": ["__init__", "BuildFromDb", "WriteToDb", "Summary", "Run"],
    },
    "GraphViewer": {
        "file": "Efi_graph_viewer.py",
        "methods": ["__init__", "LoadGraph", "LoadAgentGraphLive", "BuildUI", "ToggleFilter", "LayoutNodes", "DrawGraph", "GetNodeAt", "OnMotion", "OnClick", "OnResize", "ShowDetail", "Reload"],
    },
    "MdViewer": {
        "file": "Efi_md_viewer.py",
        "methods": ["__init__", "_build_ui", "load_file", "clear_highlights", "do_search", "highlight_current", "next_match", "prev_match"],
    },
    "Orchestrator": {
        "file": "Efi_orchestrator.py",
        "methods": ["__init__", "_StepBuild", "_StepConnect", "_StepSimulate", "_StepDiff", "_StepRepair", "_StepScan", "_StepReport", "RunPipeline", "RunStep", "Status", "Run"],
    },
    "MemoryDB": {
        "file": "Efi_ram_ai.py",
        "methods": ["__init__", "_init", "insert", "record_fix_outcome", "learn_rule", "add_extracted_rule", "fetch_extracted_rules", "update_extracted_rule", "fetch_all", "fetch_learned_rules", "stats"],
    },
    "BrokenCodeGenerator": {
        "file": "Efi_ram_ai.py",
        "methods": ["__init__", "generate", "missing_colon", "missing_colon_if", "missing_colon_for", "missing_colon_class", "missing_paren", "missing_comma", "wrong_keyword", "broken_bracket", "bad_indentation", "over_indentation", "tab_space_mix", "missing_quote", "missing_double_quote", "mixed_quotes", "undefined_var", "undefined_var_nested", "typo_variable", "missing_import", "wrong_import_name", "partial_import", "int_str_add", "list_plus_int", "dict_key_wrong_type", "wrong_attribute", "method_on_none", "missing_attribute", "list_index_overflow", "list_negative_overflow", "dict_missing_key", "too_few_args", "too_many_args", "wrong_kwarg", "local_before_global", "modifying_global_without_global", "nested_scope_leak", "unreachable_code", "empty_block", "duplicate_function", "missing_file", "division_by_zero", "key_error_runtime"],
    },
    "ASTErrorInjector": {
        "file": "Efi_ram_ai.py",
        "methods": ["generate", "_inject"],
    },
    "StaticAnalyzer": {
        "file": "Efi_ram_ai.py",
        "methods": ["__init__", "analyze", "_layer1_ast", "_get_literal", "_layer2_patterns", "_layer3_pyflakes", "summary"],
    },
    "Executor": {
        "file": "Efi_ram_ai.py",
        "methods": ["run"],
    },
    "RepairEngine": {
        "file": "Efi_ram_ai.py",
        "methods": ["fix", "fix_indentation", "fix_missing_quote"],
    },
    "RuleExtractor": {
        "file": "Efi_ram_ai.py",
        "methods": ["_error_sig", "_meta_class", "extract", "apply"],
    },
    "MetaController": {
        "file": "Efi_ram_ai.py",
        "methods": ["__init__", "record", "adapt", "best_strategy", "stats"],
    },
    "EFLLoop": {
        "file": "Efi_ram_ai.py",
        "methods": ["__init__", "step_silent", "run_parallel", "_print_stats", "step", "run", "self_analyze"],
    },
    "_Reporter": {
        "file": "Efi_ram_ai.py",
        "methods": ["unexpectedError", "syntaxError", "flake"],
    },
    "RepairEngine": {
        "file": "Efi_repair.py",
        "methods": ["__init__", "ReadGaps", "ReadLearnedFixes", "ReadFragility", "GenerateFix", "_GenerateMethod", "_GenerateEdge", "_GenerateUnit", "_ValidateCode", "WriteFixes", "RepairAll", "Report", "Run"],
    },
    "ConfigSolutionEngine": {
        "file": "Efi_solution_engine.py",
        "methods": ["__init__", "ScanFile", "FixGhostHeader", "FixVBStyleHeader", "FixClassHeader", "FixMethodDocstring", "FixFileIndex", "ScanFolder", "GenerateReport", "AnalyzeBlastRadius", "WriteToDb", "ReadFragilityFromDb", "Run", "RunScan", "RunReport", "RunFixes", "RunSummary"],
    },
    "TestConfig": {
        "file": "Efi_test_config_rules.py",
        "methods": ["GetVersion"],
    },
    "MockMemUnit": {
        "file": "Efi_test_config_rules.py",
        "methods": ["__init__", "Run"],
    },
    "TestConfig": {
        "file": "Efi_test_config_rules.py",
        "methods": ["__init__"],
    },
    "MockConfig": {
        "file": "Efi_test_config_rules.py",
        "methods": ["__init__"],
    },
    "MockMemUnit": {
        "file": "Efi_test_config_rules.py",
        "methods": ["__init__", "Run"],
    },
    "MockApp": {
        "file": "Efi_test_config_rules.py",
        "methods": ["__init__", "Execute"],
    },
    "TestConfig": {
        "file": "Efi_test_config_rules.py",
        "methods": ["GetAbout", "GetHelp", "GetReadme"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 18,
    "files_with_Run": 9,
    "files_with_state": 12,
    "files_with_print": 12,
    "files_with_decorator": 1,
    "pass_rate": 50.0,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "efl_brain"
FILE_COUNT = 18
CLASS_COUNT = 53
