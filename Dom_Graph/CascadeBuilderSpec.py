#!/usr/bin/env python3
#[@GHOST]{file_path="Dom_Graph/CascadeBuilderSpec.py" date="2026-07-03" author="devin" session_id="cascade-builder-spec" context="Spec graph data for Cascade Builder CLI — renders in Dom_Graph_Spec.py viewer"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="CascadeBuilderSpec.py" domain="dom_graph" authority="Spec"}
#[@SUMMARY]{summary="Graph spec data for Cascade Builder CLI. Nodes=planned classes, Edges=relationships. Compatible with Dom_Graph_Spec.py viewer."}
#[@CLASS]{class="CascadeBuilderSpec" domain="dom_graph" authority="single"}
#[@METHOD]{method="GetClasses" type="query"}
#[@METHOD]{method="GetEdges" type="query"}
#[@METHOD]{method="GetCategories" type="query"}

"""
Cascade Builder CLI — Spec Graph Data.

Plug these into Dom_Graph_Spec.py to visualize the planned architecture.
Nodes = planned C files in the cascade CLI.
Edges = call/dependency relationships.
"""

CASCADE_CATEGORIES = {
    "META":      "#f9e2af",
    "CRUD":      "#a6e3a1",
    "TRANSFORM": "#fab387",
    "INTEGRITY": "#f38ba8",
    "UTILITY":   "#89b4fa",
}

CASCADE_CATEGORY_ORDER = ["META", "CRUD", "TRANSFORM", "INTEGRITY", "UTILITY"]

CASCADE_EDGE_COLORS = {
    "calls":   "#cba6f7",
    "uses":    "#89b4fa",
    "feeds":   "#a6e3a1",
    "reads":   "#94e2d5",
    "updates": "#fab387",
    "checks":  "#f38ba8",
    "generates": "#f9e2af",
}

CASCADE_CLASSES = [
    # META — engine core
    ("CascadeEngine",      "META",      "engine",    "Main entry point, command dispatch, lifecycle"),
    ("StateDb",            "META",      "state",     "Open/manage per-project SQLite at .cascade/state.db"),
    ("ConfigStore",        "META",      "config",    "Project config: AI model, language prefs, naming convention, paths"),
    # CRUD — storage and retrieval
    ("TemplateStore",      "CRUD",      "template",  "Query file templates from embedded :memory: SQLite"),
    ("SnippetStore",       "CRUD",      "snippet",   "Query reusable snippets (GHOST header, SQLite open) for placeholder fill"),
    ("TypeContractStore",  "CRUD",      "contract",  "Pass 1.5: store shared types/return types so sections agree on interfaces"),
    ("MarkerScanner",      "CRUD",      "scan",      "Scan source files for BCL markers, extract section IDs + stage"),
    ("PlanScanner",        "CRUD",      "plan",      "Scan EXISTING file (not from template) and create tasks from markers"),
    ("TaskQueue",          "CRUD",      "task",      "Manage pending/done/blocked/failed tasks in project SQLite"),
    ("HistoryTracker",     "CRUD",      "history",   "Track regeneration history: attempts, failures, which sections failed N times"),
    # TRANSFORM — data shaping
    ("PlaceholderFiller",  "TRANSFORM", "fill",      "Replace {{Key}} placeholders in template text with values + snippets"),
    ("PromptBuilder",      "TRANSFORM", "prompt",    "Build AI prompts from template + task + type contracts + language rules"),
    ("PatchInserter",      "TRANSFORM", "patch",     "Replace marker body in source file with AI output, update BCL stage"),
    ("FileWriter",         "TRANSFORM", "write",     "Write skeleton file to disk, handle encoding and line endings"),
    # INTEGRITY — validation and verification
    ("Validator",          "INTEGRITY", "validate",  "Check syntax, unresolved markers, duplicate definitions"),
    ("ContractValidator",  "INTEGRITY", "contract",  "Check implementation matches return type and type contract from Pass 1.5"),
    ("Reconciler",         "INTEGRITY", "reconcile", "Code body is ground truth. Reconcile BCL marker vs DB vs actual body on every status"),
    ("HashChecker",        "INTEGRITY", "hash",      "Detect manual edits by comparing content_hash in marker vs database"),
    ("DependencyResolver", "INTEGRITY", "deps",      "Resolve depends_on graph: mark tasks ready vs blocked. Cycle detection"),
    # UTILITY — parsers and tools
    ("BclParser",          "UTILITY",   "bcl",       "Parse [@SECTION]{...} markers from source text (C port of bcl_parser.py)"),
    ("LanguageRules",      "UTILITY",   "lang",      "C/Python/Rust naming conventions, comment prefixes, marker formats"),
    ("BuildPipeline",      "UTILITY",   "build",     "Shell script + Python generator: .tpl files -> C header -> compile"),
]

CASCADE_EDGES = [
    # CascadeEngine calls everything
    ("CascadeEngine",      "StateDb",           "calls"),
    ("CascadeEngine",      "ConfigStore",       "calls"),
    ("CascadeEngine",      "TemplateStore",     "calls"),
    ("CascadeEngine",      "SnippetStore",      "calls"),
    ("CascadeEngine",      "TypeContractStore", "calls"),
    ("CascadeEngine",      "MarkerScanner",     "calls"),
    ("CascadeEngine",      "PlanScanner",       "calls"),
    ("CascadeEngine",      "TaskQueue",         "calls"),
    ("CascadeEngine",      "PromptBuilder",     "calls"),
    ("CascadeEngine",      "PatchInserter",     "calls"),
    ("CascadeEngine",      "Validator",         "calls"),
    ("CascadeEngine",      "Reconciler",        "calls"),
    ("CascadeEngine",      "FileWriter",        "calls"),
    # Template rendering chain
    ("TemplateStore",      "PlaceholderFiller", "uses"),
    ("PlaceholderFiller",  "SnippetStore",      "reads"),
    ("PlaceholderFiller",  "FileWriter",        "feeds"),
    # Type contract chain (Pass 1.5)
    ("TypeContractStore",  "PromptBuilder",     "feeds"),
    ("ContractValidator",  "TypeContractStore", "reads"),
    # Marker scanning chain
    ("MarkerScanner",      "BclParser",         "uses"),
    ("PlanScanner",        "BclParser",         "uses"),
    ("PlanScanner",        "MarkerScanner",     "uses"),
    # Task queue chain
    ("TaskQueue",          "MarkerScanner",     "feeds"),
    ("TaskQueue",          "DependencyResolver","uses"),
    ("TaskQueue",          "HistoryTracker",    "reads"),
    ("DependencyResolver", "TaskQueue",         "updates"),
    # Prompt building chain
    ("PromptBuilder",      "TaskQueue",         "reads"),
    ("PromptBuilder",      "TemplateStore",     "reads"),
    ("PromptBuilder",      "TypeContractStore", "reads"),
    ("PromptBuilder",      "LanguageRules",     "reads"),
    # Patch insertion chain
    ("PatchInserter",      "BclParser",         "uses"),
    ("PatchInserter",      "TaskQueue",         "updates"),
    ("PatchInserter",      "HashChecker",       "uses"),
    # Validation chain
    ("Validator",          "MarkerScanner",     "checks"),
    ("ContractValidator",  "Validator",         "extends"),
    ("Reconciler",         "HashChecker",       "uses"),
    ("Reconciler",         "MarkerScanner",     "checks"),
    ("Reconciler",         "TaskQueue",         "updates"),
    # Build pipeline
    ("BuildPipeline",      "TemplateStore",     "generates"),
    ("BuildPipeline",      "SnippetStore",      "generates"),
    # State
    ("StateDb",            "TaskQueue",         "owns"),
    ("StateDb",            "HistoryTracker",    "owns"),
    ("StateDb",            "ConfigStore",       "owns"),
]

CASCADE_LIFECYCLE_PHASES = [
    ("Phase 1: Bootstrap",  ["CascadeEngine", "TemplateStore", "BuildPipeline"]),
    ("Phase 2: Generate",   ["PlaceholderFiller", "MarkerScanner", "BclParser"]),
    ("Phase 3: Queue",      ["TaskQueue"]),
    ("Phase 4: AI Loop",    ["PromptBuilder", "PatchInserter"]),
    ("Phase 5: Verify",     ["Validator"]),
]

CASCADE_FLOWS = {
    "CascadeEngine": [
        ("start", "CascadeEngine receives command"),
        ("dispatch", "Route to new/next/apply/status/validate"),
        ("new", "TemplateStore renders skeleton"),
        ("scan", "MarkerScanner finds BCL markers"),
        ("queue", "TaskQueue creates tasks"),
        ("next", "PromptBuilder builds AI prompt"),
        ("apply", "PatchInserter replaces marker body"),
        ("validate", "Validator checks result"),
        ("done", "TaskQueue marks complete"),
    ],
}


class CascadeBuilderSpec:
    """Spec data for Cascade Builder CLI graph."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "categories": CASCADE_CATEGORIES,
            "category_order": CASCADE_CATEGORY_ORDER,
            "edge_colors": CASCADE_EDGE_COLORS,
            "classes": CASCADE_CLASSES,
            "edges": CASCADE_EDGES,
            "lifecycle_phases": CASCADE_LIFECYCLE_PHASES,
            "flows": CASCADE_FLOWS,
        }

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "get_classes": self.GetClasses,
            "get_edges": self.GetEdges,
            "get_categories": self.GetCategories,
            "get_flows": self.GetFlows,
            "read_state": self.read_state,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return (1, default, None)
        return (1, params.get(key, default), None)

    def GetClasses(self, params=None):
        return (1, list(self.state["classes"]), None)

    def GetEdges(self, params=None):
        return (1, list(self.state["edges"]), None)

    def GetCategories(self, params=None):
        return (1, dict(self.state["categories"]), None)

    def GetFlows(self, params=None):
        return (1, dict(self.state["flows"]), None)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in (params or {}).items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)


if __name__ == "__main__":
    spec = CascadeBuilderSpec()
    ok, classes, err = spec.Run("get_classes")
    print(f"Classes: {len(classes)}")
    for name, cat, disp, desc in classes:
        print(f"  {name:22s} [{cat:10s}] dispatch={disp:10s} — {desc}")
    ok, edges, err = spec.Run("get_edges")
    print(f"\nEdges: {len(edges)}")
    for src, dst, etype in edges:
        print(f"  {src:22s} -> {dst:22s} [{etype}]")
