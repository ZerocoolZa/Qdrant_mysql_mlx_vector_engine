#!/usr/bin/env python3

#[@GHOST]{[@file<SuperConfig.py>][@domain<Dom_Db>][@role<config>][@auth<cascade>][@date<2026-07-01>][@ver<2.0.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded_paths>]}

"""
SuperConfig — central configuration authority for all Dom_Db modules.

Every DB path, runtime constant, file inventory entry, and cross-module
reference lives here. Individual modules import from SuperConfig instead
of hardcoding paths in __init__ or class-body constants.

USAGE:
    from SuperConfig import DB, RUNTIME, FILES, MODULES
    db_path = DB.METHOD_ORCHESTRATOR
    max_repair = RUNTIME.MAX_REPAIR_ATTEMPTS

PIPELINE ORDER:
    methods.sqlite
        -> method_orchestrator.sqlite
            -> computation_units.sqlite
                -> unit_discovery.sqlite
                -> survivor_ranking.sqlite
                -> execution_planner.sqlite
                    -> execution_sessions.sqlite
                        -> ai_repair_supervisor.sqlite
"""

# ===========================================================================
# SECTION 1 — DATABASE PATHS
# All SQLite DB paths used by Dom_Db modules. Single source of truth.
# ===========================================================================

class DB:
    """All SQLite database paths for the Dom_Db pipeline."""

    # Source: methods extracted from AST scanning
    METHODS_DB              = "/tmp/methods.sqlite"

    # Orchestrator: method-centric composition, class assembly, call graph
    METHOD_ORCHESTRATOR_DB  = "/tmp/method_orchestrator.sqlite"

    # Computation Units: immutable executable objects with contracts + deps
    COMPUTATION_UNITS_DB    = "/tmp/computation_units.sqlite"

    # Unit Discovery: SCC analysis, call closure, cluster formation
    UNIT_DISCOVERY_DB       = "/tmp/unit_discovery.sqlite"

    # Survivor Ranking: evolutionary selection, version tracking, pruning
    SURVIVOR_RANKING_DB     = "/tmp/survivor_ranking.sqlite"

    # Execution Planner: deterministic plan builder, topological sort
    EXECUTION_PLANNER_DB    = "/tmp/execution_planner.sqlite"

    # Execution Session: self-repairing runtime, MemUnit capture, cache
    EXECUTION_SESSIONS_DB   = "/tmp/execution_sessions.sqlite"

    # AI Repair Supervisor: structured repair reasoning, pattern learning
    AI_REPAIR_SUPERVISOR_DB = "/tmp/ai_repair_supervisor.sqlite"

    # AST Definition Store: one row per function/method definition
    AST_DEFINITIONS_DB      = "/tmp/ast_definitions.sqlite"

    # AST Definition Store v2: normalized classes + methods tables
    AST_DEFINITIONS_V2_DB   = "/tmp/ast_definitions_v2.sqlite"

    # Code Intelligence DB: complexity scores, god functions, regressions
    CODE_INTEL_DB           = "/tmp/code_intel.sqlite"

    # Execution Planner Maintenance: cleanup, integrity, migration
    EXEC_PLANNER_MAINT_DB   = "/tmp/execution_planner.sqlite"

    # Clone Detection DB (ast_rank_clone)
    CLONE_DB                = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/db/go_mcp_store.db"


# ===========================================================================
# SECTION 2 — RUNTIME CONSTANTS
# Tunable parameters used across modules. Import instead of hardcoding.
# ===========================================================================

class RUNTIME:
    """Tunable runtime parameters shared across Dom_Db modules."""

    # ExecutionSession — repair loop
    MAX_REPAIR_ATTEMPTS     = 3

    # SurvivorRanking — evolutionary pruning
    PRUNE_THRESHOLD         = 0.3
    DEFAULT_KEEP_TOP_N     = 5

    # ExecPlannerMaintenance — log retention
    MAX_AGE_DAYS            = 30
    SCHEMA_VERSION          = 2

    # AstRankClone — clone detection
    MIN_LINES               = 6
    DEFAULT_SIMILARITY      = 0.8
    MAX_FILES               = 10000
    NGRAM_SIZE              = 5
    NGRAM_PREFILTER         = 0.65
    NORM_CAP                = 1500

    # SQLite pragmas applied to all connections
    FOREIGN_KEYS_ON         = True
    CHECK_SAME_THREAD       = False

    # Compile cache: shared across orchestrator, planner, session
    COMPILE_CACHE_ENABLED   = True


# ===========================================================================
# SECTION 3 — FILE INVENTORY
# Every .py file in Dom_Db, grouped by pipeline role.
# ===========================================================================

class FILES:
    """Complete file inventory for Dom_Db domain."""

    # --- Core pipeline (method -> unit -> execution -> repair) ---
    METHOD_ORCHESTRATOR     = "method_orchestrator.py"
    COMPUTATION_UNIT        = "computation_unit.py"
    UNIT_DISCOVERY          = "unit_discovery.py"
    SURVIVOR_RANKING        = "survivor_ranking.py"
    EXECUTION_PLANNER       = "execution_planner.py"
    EXECUTION_SESSION       = "execution_session.py"
    AI_REPAIR_SUPERVISOR    = "ai_repair_supervisor.py"

    # --- Method storage + graph ---
    METHODS_STORE           = "methods_store.py"
    METHODS_GRAPH           = "methods_graph.py"
    METHOD_PROXY            = "method_proxy.py"

    # --- AST analysis ---
    AST_DEF_STORE           = "ast_def_store.py"
    AST_DEF_STORE_V2        = "ast_def_store_v2.py"
    AST_RANKER              = "ast_ranker.py"
    AST_RANK_ENGINE         = "ast_rank_engine.py"
    AST_RANK_OUTPUT         = "ast_rank_output.py"
    AST_RANK_CLONE          = "ast_rank_clone.py"

    # --- Code intelligence ---
    CODE_INTEL_DB           = "code_intel_db.py"
    CODE_INTEL_MYSQL        = "code_intel_mysql.py"
    CLASS_DISCOVERY         = "class_discovery.py"

    # --- Convergence / mix-match ---
    MIX_MATCH_CONVERGE      = "mix_match_converge.py"
    RAM_MIX_MATCH           = "ram_mix_match.py"

    # --- BCL patterns ---
    BCL_PATTERN_COLLECTOR   = "bcl_pattern_collector.py"
    BCL_PATTERN_CTX         = "bcl_pattern_ctx.py"
    BCL_PATTERN_DB          = "bcl_pattern_db.py"
    BCL_PATTERN_GUI         = "bcl_pattern_gui.py"
    BCL_PATTERN_MSEARCH     = "bcl_pattern_msearch.py"
    BCL_VALIDATOR           = "bcl_validator.py"

    # --- Maintenance + sandbox ---
    EXEC_PLANNER_MAINT      = "exec_planner_maintenance.py"
    EXEC_SANDBOX            = "exec_sandbox.py"
    EXEC_PLANNER_INTEGRATIONS = "execution_planner_integrations.py"

    # --- Loader ---
    DB_MODULE_LOADER        = "DbModuleLoader.py"
    DB_MODULE_LOADER_V3     = "DbModuleLoader_v3_2_fixes.py"

    # --- Config + init ---
    CONFIG                  = "Config.py"
    SUPER_CONFIG            = "SuperConfig.py"
    INIT                    = "__init__.py"

    # --- Test ---
    TEST_DB_LOADER          = "test_db_loader.py"

    # --- Non-Python ---
    AST_INTEL_PLAN          = "AST_INTEL_PLAN.md"
    VB_CLASSES_DB           = "vb_classes.db"

    @classmethod
    def ALL_PY(cls):
        """Return all .py files in Dom_Db."""
        return [
            cls.METHOD_ORCHESTRATOR, cls.COMPUTATION_UNIT, cls.UNIT_DISCOVERY,
            cls.SURVIVOR_RANKING, cls.EXECUTION_PLANNER, cls.EXECUTION_SESSION,
            cls.AI_REPAIR_SUPERVISOR, cls.METHODS_STORE, cls.METHODS_GRAPH,
            cls.METHOD_PROXY, cls.AST_DEF_STORE, cls.AST_DEF_STORE_V2,
            cls.AST_RANKER, cls.AST_RANK_ENGINE, cls.AST_RANK_OUTPUT,
            cls.AST_RANK_CLONE, cls.CODE_INTEL_DB, cls.CODE_INTEL_MYSQL,
            cls.CLASS_DISCOVERY, cls.MIX_MATCH_CONVERGE, cls.RAM_MIX_MATCH,
            cls.BCL_PATTERN_COLLECTOR, cls.BCL_PATTERN_CTX, cls.BCL_PATTERN_DB,
            cls.BCL_PATTERN_GUI, cls.BCL_PATTERN_MSEARCH, cls.BCL_VALIDATOR,
            cls.EXEC_PLANNER_MAINT, cls.EXEC_SANDBOX,
            cls.EXEC_PLANNER_INTEGRATIONS, cls.DB_MODULE_LOADER,
            cls.DB_MODULE_LOADER_V3, cls.CONFIG, cls.SUPER_CONFIG,
            cls.INIT, cls.TEST_DB_LOADER,
        ]


# ===========================================================================
# SECTION 4 — MODULE REGISTRY
# Maps each file to: class name, DB path it owns, DBs it reads, pipeline stage.
# ===========================================================================

class MODULES:
    """Cross-reference: file -> class -> owns_db -> reads_db -> pipeline_stage."""

    METHOD_ORCHESTRATOR = {
        "file": "method_orchestrator.py",
        "class": "MethodOrchestrator",
        "owns_db": DB.METHOD_ORCHESTRATOR_DB,
        "reads_db": [DB.METHODS_DB],
        "stage": "1_compose",
        "commands": [
            "build", "compose", "materialize", "stats",
            "close", "export_class", "import_class", "class_health",
            "method_signature", "call_tree", "global_health",
        ],
    }

    COMPUTATION_UNIT = {
        "file": "computation_unit.py",
        "class": "ComputationUnit",
        "owns_db": DB.COMPUTATION_UNITS_DB,
        "reads_db": [DB.METHOD_ORCHESTRATOR_DB],
        "stage": "2_ingest",
        "commands": [
            "ingest_method", "verify", "query", "info",
            "fork", "lineage", "contracts", "set_contract",
            "execute", "dedup_report", "stats",
            "close", "batch_ingest", "export_cu", "import_cu",
            "compare_cus", "dependency_graph", "health",
            "purge_duplicates", "stats_detail",
        ],
    }

    UNIT_DISCOVERY = {
        "file": "unit_discovery.py",
        "class": "UnitDiscovery",
        "owns_db": DB.UNIT_DISCOVERY_DB,
        "reads_db": [DB.METHOD_ORCHESTRATOR_DB, DB.COMPUTATION_UNITS_DB],
        "stage": "3_discover",
        "commands": [
            "discover", "units", "unit_detail", "sccs",
            "call_graph", "stats",
        ],
    }

    SURVIVOR_RANKING = {
        "file": "survivor_ranking.py",
        "class": "SurvivorRanking",
        "owns_db": DB.SURVIVOR_RANKING_DB,
        "reads_db": [DB.COMPUTATION_UNITS_DB],
        "stage": "4_rank",
        "commands": [
            "register", "rank", "best", "prune", "record_run",
            "evolution", "stats", "promote",
        ],
    }

    EXECUTION_PLANNER = {
        "file": "execution_planner.py",
        "class": "ExecutionPlanner",
        "owns_db": DB.EXECUTION_PLANNER_DB,
        "reads_db": [DB.METHOD_ORCHESTRATOR_DB, DB.COMPUTATION_UNITS_DB],
        "stage": "5_plan",
        "commands": [
            "create_plan", "execute_plan", "status",
            "query_plan", "stats",
        ],
    }

    EXECUTION_SESSION = {
        "file": "execution_session.py",
        "class": "ExecutionSession",
        "owns_db": DB.EXECUTION_SESSIONS_DB,
        "reads_db": [DB.COMPUTATION_UNITS_DB, DB.METHOD_ORCHESTRATOR_DB],
        "stage": "6_execute",
        "commands": [
            "create", "execute", "status", "repair_log", "memunit_log",
            "register_survivor", "survivor_lookup", "build_survivor_catalog",
            "clear_cache", "stats", "close",
            "parallel_execute", "dry_run", "replay",
            "export_session", "import_session", "session_diff",
            "validate", "cleanup", "profile", "invalidate_cache",
        ],
    }

    AI_REPAIR_SUPERVISOR = {
        "file": "ai_repair_supervisor.py",
        "class": "AIRepairSupervisor",
        "owns_db": DB.AI_REPAIR_SUPERVISOR_DB,
        "reads_db": [
            DB.COMPUTATION_UNITS_DB,
            DB.SURVIVOR_RANKING_DB,
            DB.EXECUTION_SESSIONS_DB,
        ],
        "stage": "7_repair",
        "commands": [
            "analyze", "decide", "apply", "learn", "history", "stats", "close",
        ],
    }

    METHODS_STORE = {
        "file": "methods_store.py",
        "class": "MethodsStore",
        "owns_db": DB.METHODS_DB,
        "reads_db": [DB.AST_DEFINITIONS_V2_DB],
        "stage": "0_source",
        "commands": ["ingest_from_v2", "all_methods", "close"],
    }

    METHODS_GRAPH = {
        "file": "methods_graph.py",
        "class": "MethodsGraph",
        "owns_db": DB.METHODS_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["load", "build_graph", "query"],
    }

    METHOD_PROXY = {
        "file": "method_proxy.py",
        "class": "MethodProxy",
        "owns_db": DB.METHODS_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["call", "cache", "stats"],
    }

    AST_DEF_STORE = {
        "file": "ast_def_store.py",
        "class": "AstDefStore",
        "owns_db": DB.AST_DEFINITIONS_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["ingest_scores", "query_all", "query_stats"],
    }

    CODE_INTEL_DB = {
        "file": "code_intel_db.py",
        "class": "CodeIntelDB",
        "owns_db": DB.CODE_INTEL_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["ingest_scores", "query_god_functions", "query_regressed_files"],
    }

    CLASS_DISCOVERY = {
        "file": "class_discovery.py",
        "class": "ClassDiscovery",
        "owns_db": DB.METHODS_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["discover", "stats"],
    }

    MIX_MATCH_CONVERGE = {
        "file": "mix_match_converge.py",
        "class": "MixMatchConverge",
        "owns_db": DB.METHODS_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["load", "converge", "stats"],
    }

    RAM_MIX_MATCH = {
        "file": "ram_mix_match.py",
        "class": "RamMixMatch",
        "owns_db": ":memory:",
        "reads_db": [DB.METHODS_DB],
        "stage": "0_source",
        "commands": ["load", "query", "stats"],
    }

    AST_RANK_CLONE = {
        "file": "ast_rank_clone.py",
        "class": "AstRankClone",
        "owns_db": DB.CLONE_DB,
        "reads_db": [],
        "stage": "0_source",
        "commands": ["scan", "compare_files", "store_sqlite", "report"],
    }

    EXEC_PLANNER_MAINT = {
        "file": "exec_planner_maintenance.py",
        "class": "ExecPlannerMaintenance",
        "owns_db": DB.EXEC_PLANNER_MAINT_DB,
        "reads_db": [],
        "stage": "8_maintain",
        "commands": [
            "cleanup_old_logs", "integrity_check", "table_stats",
            "migrate_schema", "export_db", "import_db",
            "health_check", "optimize",
        ],
    }

    @classmethod
    def ALL(cls):
        """Return all module registry entries."""
        return [
            cls.METHOD_ORCHESTRATOR, cls.COMPUTATION_UNIT, cls.UNIT_DISCOVERY,
            cls.SURVIVOR_RANKING, cls.EXECUTION_PLANNER, cls.EXECUTION_SESSION,
            cls.AI_REPAIR_SUPERVISOR, cls.METHODS_STORE, cls.METHODS_GRAPH,
            cls.METHOD_PROXY, cls.AST_DEF_STORE, cls.CODE_INTEL_DB,
            cls.CLASS_DISCOVERY, cls.MIX_MATCH_CONVERGE, cls.RAM_MIX_MATCH,
            cls.AST_RANK_CLONE, cls.EXEC_PLANNER_MAINT,
        ]

    @classmethod
    def BY_STAGE(cls):
        """Return modules grouped by pipeline stage."""
        result = {}
        for mod in cls.ALL():
            stage = mod["stage"]
            if stage not in result:
                result[stage] = []
            result[stage].append(mod)
        return result

    @classmethod
    def BY_CLASS(cls):
        """Return {class_name: module_entry} for quick lookup."""
        return {mod["class"]: mod for mod in cls.ALL()}


# ===========================================================================
# SECTION 5 — PIPELINE FLOW
# Data flows through these stages in order.
# ===========================================================================

PIPELINE = [
    {"stage": "0_source",       "module": "MethodsStore",        "input": "AST scan",          "output": DB.METHODS_DB},
    {"stage": "1_compose",      "module": "MethodOrchestrator",  "input": DB.METHODS_DB,       "output": DB.METHOD_ORCHESTRATOR_DB},
    {"stage": "2_ingest",       "module": "ComputationUnit",     "input": DB.METHOD_ORCHESTRATOR_DB, "output": DB.COMPUTATION_UNITS_DB},
    {"stage": "3_discover",     "module": "UnitDiscovery",       "input": DB.METHOD_ORCHESTRATOR_DB, "output": DB.UNIT_DISCOVERY_DB},
    {"stage": "4_rank",         "module": "SurvivorRanking",     "input": DB.COMPUTATION_UNITS_DB, "output": DB.SURVIVOR_RANKING_DB},
    {"stage": "5_plan",         "module": "ExecutionPlanner",    "input": DB.COMPUTATION_UNITS_DB, "output": DB.EXECUTION_PLANNER_DB},
    {"stage": "6_execute",      "module": "ExecutionSession",    "input": DB.COMPUTATION_UNITS_DB, "output": DB.EXECUTION_SESSIONS_DB},
    {"stage": "7_repair",       "module": "AIRepairSupervisor",  "input": DB.EXECUTION_SESSIONS_DB, "output": DB.AI_REPAIR_SUPERVISOR_DB},
    {"stage": "8_maintain",     "module": "ExecPlannerMaintenance", "input": DB.EXECUTION_PLANNER_DB, "output": DB.EXECUTION_PLANNER_DB},
]


# ===========================================================================
# SECTION 6 — DB DEPENDENCY GRAPH
# Which DBs are read by which modules (for connection management).
# ===========================================================================

DB_READERS = {
    DB.METHODS_DB:              ["MethodsStore", "MethodsGraph", "MethodProxy", "MethodOrchestrator", "ClassDiscovery", "MixMatchConverge", "RamMixMatch"],
    DB.METHOD_ORCHESTRATOR_DB:  ["MethodOrchestrator", "ComputationUnit", "UnitDiscovery", "ExecutionPlanner", "ExecutionSession"],
    DB.COMPUTATION_UNITS_DB:    ["ComputationUnit", "UnitDiscovery", "SurvivorRanking", "ExecutionPlanner", "ExecutionSession", "AIRepairSupervisor"],
    DB.UNIT_DISCOVERY_DB:       ["UnitDiscovery"],
    DB.SURVIVOR_RANKING_DB:     ["SurvivorRanking", "AIRepairSupervisor"],
    DB.EXECUTION_PLANNER_DB:    ["ExecutionPlanner", "ExecPlannerMaintenance"],
    DB.EXECUTION_SESSIONS_DB:   ["ExecutionSession", "AIRepairSupervisor"],
    DB.AI_REPAIR_SUPERVISOR_DB: ["AIRepairSupervisor"],
    DB.AST_DEFINITIONS_DB:      ["AstDefStore"],
    DB.AST_DEFINITIONS_V2_DB:   ["MethodsStore"],
    DB.CODE_INTEL_DB:           ["CodeIntelDB"],
}

DB_OWNERS = {
    DB.METHODS_DB:              "MethodsStore",
    DB.METHOD_ORCHESTRATOR_DB:  "MethodOrchestrator",
    DB.COMPUTATION_UNITS_DB:    "ComputationUnit",
    DB.UNIT_DISCOVERY_DB:       "UnitDiscovery",
    DB.SURVIVOR_RANKING_DB:     "SurvivorRanking",
    DB.EXECUTION_PLANNER_DB:    "ExecutionPlanner",
    DB.EXECUTION_SESSIONS_DB:   "ExecutionSession",
    DB.AI_REPAIR_SUPERVISOR_DB: "AIRepairSupervisor",
    DB.AST_DEFINITIONS_DB:      "AstDefStore",
    DB.CODE_INTEL_DB:           "CodeIntelDB",
}


# ===========================================================================
# SECTION 7 — SKIP DIRS (for AST scanning)
# ===========================================================================

SKIP_DIRS = (
    ".git", "__pycache__", ".devin", ".windsurf", ".codeium",
    "node_modules", ".tasks", "snapshots", "logs",
)


# ===========================================================================
# SECTION 8 — DEMO
# ===========================================================================

if __name__ == "__main__":
    print("=== SuperConfig — Dom_Db Central Config ===")
    print()

    print("--- DB Paths ---")
    for name in dir(DB):
        if not name.startswith("_"):
            print(f"  {name:30s} = {getattr(DB, name)}")
    print()

    print("--- Runtime Constants ---")
    for name in dir(RUNTIME):
        if not name.startswith("_"):
            print(f"  {name:30s} = {getattr(RUNTIME, name)}")
    print()

    print("--- File Inventory ---")
    for f in FILES.ALL_PY():
        print(f"  {f}")
    print(f"  Total .py files: {len(FILES.ALL_PY())}")
    print()

    print("--- Module Registry ---")
    for mod in MODULES.ALL():
        print(f"  [{mod['stage']}] {mod['class']:30s}  owns={mod['owns_db']}")
        if mod["reads_db"]:
            for r in mod["reads_db"]:
                print(f"       reads: {r}")
    print()

    print("--- Pipeline Flow ---")
    for step in PIPELINE:
        print(f"  {step['stage']:12s}  {step['module']:30s}  {step['input']} -> {step['output']}")
    print()

    print("--- DB Readers (who reads what) ---")
    for db_path, readers in DB_READERS.items():
        print(f"  {db_path}")
        for r in readers:
            print(f"    <- {r}")
    print()

    print("--- DB Owners ---")
    for db_path, owner in DB_OWNERS.items():
        print(f"  {db_path}  owner={owner}")
    print()

    print("--- Modules by Stage ---")
    for stage, mods in sorted(MODULES.BY_STAGE().items()):
        print(f"  {stage}:")
        for m in mods:
            print(f"    {m['class']}  ({m['file']})")
    print()

    print("=== SuperConfig DEMO COMPLETE ===")
