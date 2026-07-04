#!/usr/bin/env python3
"""
AST Code Ranking System v2 — terminal-based code intelligence scanner.

Pipeline: SCAN FOLDER -> STRIP BCL -> PARSE AST -> EXTRACT METRICS
          -> DETECT DEAD CODE -> BUILD DEPENDENCY GRAPH -> DETECT CYCLES
          -> SCORE FILES + FUNCTIONS -> GENERATE REFACTOR SUGGESTIONS
          -> TRACK TRENDS -> RANK FILES -> PRINT TERMINAL REPORT

Enhancements over v1:
  1. BCL awareness — strips BCL comment blocks before parse, scores BCL tags
  2. Local import resolution — maps imports to actual file modules
  3. Function-level scoring — per-function complexity, god function detection
  4. Refactor suggestions — actionable advice per issue
  5. Trend tracking — saves history, compares to last run
  6. Dead code detection — unused imports, empty functions, unreachable code

Usage:
    python3 ast_ranker.py <folder> [--json] [--verbose] [--min-score N]
                           [--history] [--functions] [--suggest] [--learn]
    python3 ast_ranker.py --query <sql-like-query>
    python3 ast_ranker.py --query "god_functions"
    python3 ast_ranker.py --query "regressed"
    python3 ast_ranker.py --query "missing_bcl"
    python3 ast_ranker.py --query "search:Config"
    python3 ast_ranker.py --query "deps:core.Dom_Db.Config"
"""

import ast
import os
import sys
import json
import re
import time
import argparse
from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

try:
    from code_intel_db import CodeIntelDB
    CODE_INTEL_AVAILABLE = True
except ImportError:
    CODE_INTEL_AVAILABLE = False

try:
    from code_intel_mysql import CodeIntelMySQL
    MYSQL_INTEL_AVAILABLE = True
except ImportError:
    MYSQL_INTEL_AVAILABLE = False

try:
    from ast_def_store import AstDefStore
    DEF_STORE_AVAILABLE = True
except ImportError:
    DEF_STORE_AVAILABLE = False


# ---------------------------------------------------------------------------
# RESULT MODELS
# ---------------------------------------------------------------------------

@dataclass
class FunctionMetrics:
    name: str
    line: int
    end_line: int = 0
    lines: int = 0
    args: int = 0
    branches: int = 0
    loops: int = 0
    max_depth: int = 0
    complexity: int = 0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class FileMetrics:
    file: str
    lines: int = 0
    functions: int = 0
    classes: int = 0
    loops: int = 0
    ifs: int = 0
    max_depth: int = 0
    imports: List[str] = field(default_factory=list)
    local_imports: List[str] = field(default_factory=list)
    resolved_imports: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    parse_error: Optional[str] = None
    bcl_tags: List[str] = field(default_factory=list)
    bcl_format: str = ""
    bcl_score: int = 0
    unused_imports: List[str] = field(default_factory=list)
    empty_functions: List[str] = field(default_factory=list)
    function_metrics: List[FunctionMetrics] = field(default_factory=list)


@dataclass
class FileScore:
    file: str
    score: int = 0
    complexity: int = 0
    structure: int = 0
    hygiene: int = 0
    bcl: int = 0
    metrics: FileMetrics = field(default_factory=lambda: FileMetrics(""))
    rank: int = 0
    grade: str = "F"
    prev_score: Optional[int] = None
    delta: Optional[int] = None
    suggestions: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BCL PRE-PARSER
# ---------------------------------------------------------------------------

BCL_TAG_RE = re.compile(r'\[@(\w+)\]')
BCL_HEADER_RE = re.compile(r'^#\[@(\w+)\]\{', re.MULTILINE)
BCL_ANGLE_RE = re.compile(r'\[@(\w+)<([^>]*)>\]')
BCL_KEYVALUE_RE = re.compile(r'(\w+)="([^"]*)"')
BCL_SEMICOLON_RE = re.compile(r'"([^"]*)"\s*;\s*"([^"]*)"')
REQUIRED_BCL_TAGS = {"GHOST", "VBSTYLE", "FILEID", "SUMMARY", "CLASS", "METHOD"}


def strip_bcl_comments(source: str) -> Tuple[str, List[str], str]:
    """Strip BCL comment blocks from source before AST parsing.

    Returns (clean_source, bcl_tags_found, bcl_format).
    """
    lines = source.split("\n")
    clean_lines = []
    bcl_tags = []
    bcl_format = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#[@") or stripped.startswith("# [@"):
            tags = BCL_TAG_RE.findall(stripped)
            bcl_tags.extend(tags)
            if not bcl_format:
                if BCL_ANGLE_RE.search(stripped):
                    bcl_format = "header_angle"
                elif BCL_KEYVALUE_RE.search(stripped):
                    bcl_format = "header_keyvalue"
                elif BCL_SEMICOLON_RE.search(stripped):
                    bcl_format = "header_semicolon"
                elif ";" in stripped and '"' in stripped:
                    bcl_format = "header_semicolon"
                else:
                    bcl_format = "header_other"
            continue
        clean_lines.append(line)

    return "\n".join(clean_lines), bcl_tags, bcl_format


def score_bcl(tags: List[str], fmt: str) -> Tuple[int, List[str]]:
    """Score BCL header presence and format. Returns (score, issues)."""
    score = 0
    issues = []
    tag_set = set(tags)

    for required in REQUIRED_BCL_TAGS:
        if required in tag_set:
            score += 3
        else:
            score -= 2
            issues.append("MISSING_BCL_" + required)

    if fmt == "header_angle":
        score += 2
    elif fmt == "header_semicolon":
        score += 2
    elif fmt == "header_keyvalue":
        score += 1
    elif fmt == "header_other":
        score -= 1
        issues.append("BCL_UNKNOWN_FORMAT")

    if not tags:
        score = 0

    return score, issues


# ---------------------------------------------------------------------------
# AST ANALYZER
# ---------------------------------------------------------------------------

class Analyzer(ast.NodeVisitor):

    def __init__(self):
        self.functions = 0
        self.classes = 0
        self.loops = 0
        self.ifs = 0
        self.depth = 0
        self.max_depth = 0
        self.imports = []
        self.local_imports = []
        self.function_metrics: List[FunctionMetrics] = []
        self.all_names: Set[str] = set()
        self.import_names: Dict[str, str] = {}

    def generic_visit(self, node):
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        super().generic_visit(node)
        self.depth -= 1

    def visit_Name(self, node):
        self.all_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.all_names.add(node.value.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions += 1
        fm = self._analyze_function(node)
        self.function_metrics.append(fm)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.functions += 1
        fm = self._analyze_function(node)
        self.function_metrics.append(fm)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_If(self, node):
        self.ifs += 1
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
            display = alias.asname or alias.name.split(".")[0]
            self.import_names[display] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
            if node.level > 0:
                self.local_imports.append(node.module)
            for alias in node.names:
                display = alias.asname or alias.name
                self.import_names[display] = node.module + "." + alias.name
        self.generic_visit(node)

    def _analyze_function(self, node) -> FunctionMetrics:
        """Analyze a single function for complexity and issues."""
        end_line = getattr(node, "end_lineno", node.lineno)
        func_lines = end_line - node.lineno + 1

        class FuncCounter(ast.NodeVisitor):
            def __init__(self):
                self.d = 0
                self.max_d = 0
                self.branches = 0
                self.loops = 0

            def generic_visit(self, n):
                self.d += 1
                self.max_d = max(self.max_d, self.d)
                super().generic_visit(n)
                self.d -= 1

            def visit_If(self, n):
                self.branches += 1
                self.generic_visit(n)

            def visit_For(self, n):
                self.loops += 1
                self.generic_visit(n)

            def visit_While(self, n):
                self.loops += 1
                self.generic_visit(n)

        counter = FuncCounter()
        for child in ast.iter_child_nodes(node):
            counter.visit(child)

        branches = counter.branches
        loops = counter.loops
        max_d = counter.max_d
        complexity = branches + loops + 1

        issues = []
        suggestions = []

        if max_d > 6:
            issues.append("DEEP_NESTING")
            suggestions.append(
                "L%d: %s() nested %d levels — extract helper function"
                % (node.lineno, node.name, max_d)
            )
        if func_lines > 80:
            issues.append("LONG_FUNCTION")
            suggestions.append(
                "L%d: %s() is %d lines — split into smaller functions"
                % (node.lineno, node.name, func_lines)
            )
        if complexity > 15:
            issues.append("HIGH_COMPLEXITY")
            suggestions.append(
                "L%d: %s() complexity=%d (branches=%d, loops=%d) — refactor dispatch"
                % (node.lineno, node.name, complexity, branches, loops)
            )
        if len(node.args.args) > 6:
            issues.append("MANY_ARGS")
            suggestions.append(
                "L%d: %s() has %d args — use params dict"
                % (node.lineno, node.name, len(node.args.args))
            )

        body_has_pass = all(
            isinstance(stmt, ast.Pass) for stmt in node.body
        )
        if body_has_pass:
            issues.append("EMPTY_FUNCTION")

        return FunctionMetrics(
            name=node.name,
            line=node.lineno,
            end_line=end_line,
            lines=func_lines,
            args=len(node.args.args),
            branches=branches,
            loops=loops,
            max_depth=max_d,
            complexity=complexity,
            issues=issues,
            suggestions=suggestions,
        )


# ---------------------------------------------------------------------------
# DEAD CODE DETECTOR
# ---------------------------------------------------------------------------

def detect_unused_imports(import_names: Dict[str, str],
                          all_names: Set[str]) -> List[str]:
    """Find imports that are never referenced in the code."""
    unused = []
    for display, full in import_names.items():
        if display not in all_names:
            unused.append(full)
    return unused


def detect_empty_functions(func_metrics: List[FunctionMetrics]) -> List[str]:
    """Find functions with empty (pass-only) bodies."""
    return [fm.name for fm in func_metrics if "EMPTY_FUNCTION" in fm.issues]


# ---------------------------------------------------------------------------
# DEPENDENCY GRAPH
# ---------------------------------------------------------------------------

class DependencyGraph:

    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.reverse: Dict[str, Set[str]] = defaultdict(set)
        self.cycles: List[List[str]] = []
        self.layers: Dict[str, int] = {}

    def add_node(self, name: str):
        self.nodes.add(name)

    def add_edge(self, source: str, target: str):
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges[source].add(target)
        self.reverse[target].add(source)

    def detect_cycles(self) -> List[List[str]]:
        """Tarjan SCC for cycle detection."""
        index_counter = [0]
        stack = []
        lowlink = {}
        index = {}
        on_stack = {}
        result = []

        def strongconnect(node):
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack[node] = True

            for successor in self.edges.get(node, []):
                if successor not in index:
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif on_stack.get(successor, False):
                    lowlink[node] = min(lowlink[node], index[successor])

            if lowlink[node] == index[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == node:
                        break
                if len(scc) > 1:
                    result.append(scc)

        for node in sorted(self.nodes):
            if node not in index:
                strongconnect(node)

        self.cycles = result
        return result

    def compute_layers(self) -> Dict[str, int]:
        """Topological sort -> layer assignment (Kahn algorithm)."""
        in_degree = {n: 0 for n in self.nodes}
        for source in self.edges:
            for target in self.edges[source]:
                in_degree[target] = in_degree.get(target, 0) + 1

        queue = deque()
        for node in self.nodes:
            if in_degree.get(node, 0) == 0:
                queue.append(node)
                self.layers[node] = 0

        while queue:
            node = queue.popleft()
            for successor in self.edges.get(node, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    self.layers[successor] = self.layers.get(node, 0) + 1
                    queue.append(successor)

        return self.layers

    def get_fan_in(self, node: str) -> int:
        return len(self.reverse.get(node, set()))

    def get_fan_out(self, node: str) -> int:
        return len(self.edges.get(node, set()))


# ---------------------------------------------------------------------------
# IMPORT RESOLVER
# ---------------------------------------------------------------------------

def resolve_imports(imports: List[str], local_imports: List[str],
                    module_map: Dict[str, str]) -> List[str]:
    """Map import strings to actual module names in the codebase."""
    resolved = []
    for imp in imports:
        parts = imp.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in module_map:
                resolved.append(candidate)
                break
    return resolved


# ---------------------------------------------------------------------------
# SCORING ENGINE
# ---------------------------------------------------------------------------

WEIGHTS = {
    "function": 5,
    "class": 8,
    "loop": -2,
    "if": -1,
    "depth": -3,
    "parse_error": -999,
    "high_nesting": -15,
    "no_functions": -10,
    "loop_heavy": -10,
    "no_classes": -5,
    "too_many_imports": -8,
    "circular_dep": -25,
    "high_fan_out": -5,
    "high_fan_in": -3,
    "unused_import": -3,
    "empty_function": -4,
    "long_function": -8,
    "high_complexity": -10,
    "many_args": -5,
    "deep_nesting_func": -6,
    "missing_bcl": -2,
    "bcl_unknown_format": -1,
}

FAN_OUT_THRESHOLD = 10
FAN_IN_THRESHOLD = 8
IMPORT_THRESHOLD = 20


def compute_score(metrics: FileMetrics, graph: Optional[DependencyGraph] = None,
                  module_name: Optional[str] = None) -> FileScore:
    structure = metrics.functions * WEIGHTS["function"] + metrics.classes * WEIGHTS["class"]
    complexity = -(metrics.loops * abs(WEIGHTS["loop"]) + metrics.ifs * abs(WEIGHTS["if"]) + metrics.max_depth * abs(WEIGHTS["depth"]))

    hygiene = 0
    issues = []
    suggestions = []

    if metrics.parse_error:
        metrics.issues = ["PARSE_ERROR"]
        return FileScore(
            file=metrics.file,
            score=WEIGHTS["parse_error"],
            structure=structure,
            complexity=complexity,
            hygiene=hygiene,
            metrics=metrics,
        )

    if metrics.max_depth > 8:
        hygiene += WEIGHTS["high_nesting"]
        issues.append("HIGH_NESTING")
        suggestions.append("File has max nesting depth %d — extract deep blocks" % metrics.max_depth)

    if metrics.functions == 0:
        hygiene += WEIGHTS["no_functions"]
        issues.append("NO_FUNCTIONS")

    if metrics.classes == 0 and metrics.functions > 3:
        hygiene += WEIGHTS["no_classes"]
        issues.append("NO_CLASSES")

    if metrics.loops > 20:
        hygiene += WEIGHTS["loop_heavy"]
        issues.append("LOOP_HEAVY")

    if len(metrics.imports) > IMPORT_THRESHOLD:
        hygiene += WEIGHTS["too_many_imports"]
        issues.append("TOO_MANY_IMPORTS")

    for unused in metrics.unused_imports:
        hygiene += WEIGHTS["unused_import"]
        issues.append("UNUSED_IMPORT: %s" % unused)
        suggestions.append("Remove unused import: %s" % unused)

    for empty_fn in metrics.empty_functions:
        hygiene += WEIGHTS["empty_function"]
        issues.append("EMPTY_FUNCTION: %s" % empty_fn)
        suggestions.append("Implement or remove empty function: %s()" % empty_fn)

    for fm in metrics.function_metrics:
        for issue in fm.issues:
            if issue == "LONG_FUNCTION":
                hygiene += WEIGHTS["long_function"]
            elif issue == "HIGH_COMPLEXITY":
                hygiene += WEIGHTS["high_complexity"]
            elif issue == "MANY_ARGS":
                hygiene += WEIGHTS["many_args"]
            elif issue == "DEEP_NESTING":
                hygiene += WEIGHTS["deep_nesting_func"]
        suggestions.extend(fm.suggestions)

    if graph and module_name:
        fan_out = graph.get_fan_out(module_name)
        fan_in = graph.get_fan_in(module_name)
        if fan_out > FAN_OUT_THRESHOLD:
            hygiene += WEIGHTS["high_fan_out"]
            issues.append("HIGH_FAN_OUT(%d)" % fan_out)
            suggestions.append("High fan-out (%d) — consider facade pattern" % fan_out)
        if fan_in > FAN_IN_THRESHOLD:
            hygiene += WEIGHTS["high_fan_in"]
            issues.append("HIGH_FAN_IN(%d)" % fan_in)

        for cycle in graph.cycles:
            if module_name in cycle:
                hygiene += WEIGHTS["circular_dep"]
                issues.append("CIRCULAR_DEP(%s)" % "->".join(cycle[:4]))
                suggestions.append("Circular dependency: %s" % " -> ".join(cycle[:4]))
                break

    bcl_score, bcl_issues = score_bcl(metrics.bcl_tags, metrics.bcl_format)
    for bi in bcl_issues:
        issues.append(bi)
        if bi.startswith("MISSING_BCL"):
            hygiene += WEIGHTS["missing_bcl"]
        elif bi == "BCL_UNKNOWN_FORMAT":
            hygiene += WEIGHTS["bcl_unknown_format"]

    total = structure + complexity + hygiene + bcl_score
    metrics.issues = issues

    return FileScore(
        file=metrics.file,
        score=total,
        structure=structure,
        complexity=complexity,
        hygiene=hygiene,
        bcl=bcl_score,
        metrics=metrics,
        suggestions=suggestions,
    )


def grade_for_score(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    if score >= 0:
        return "E"
    return "F"


# ---------------------------------------------------------------------------
# FILE SCANNER
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", "__pycache__", ".devin", ".windsurf", ".codeium",
    ".cursor", "node_modules", ".tasks", "treasure_trove_backup",
    "snapshots", "logs", ".bookmarkai", ".codebuddy",
    "vscode-book-runtime.empty", "venv", ".venv",
}


def file_to_module(rel_path: str, root: str) -> str:
    rel = os.path.relpath(rel_path, root)
    if rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace(os.sep, ".")


def score_file(path: str, root: str) -> Tuple[FileMetrics, Optional[ast.AST]]:
    """Parse and analyze a single Python file. Returns (metrics, ast_tree_or_None)."""
    metrics = FileMetrics(file=os.path.relpath(path, root))

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        metrics.parse_error = str(exc)
        return metrics, None

    clean_source, bcl_tags, bcl_format = strip_bcl_comments(source)
    metrics.bcl_tags = bcl_tags
    metrics.bcl_format = bcl_format

    try:
        tree = ast.parse(clean_source)
    except Exception as exc:
        metrics.parse_error = str(exc)
        metrics.lines = source.count("\n") + 1
        return metrics, None

    metrics.lines = source.count("\n") + 1

    analyzer = Analyzer()
    analyzer.visit(tree)

    metrics.functions = analyzer.functions
    metrics.classes = analyzer.classes
    metrics.loops = analyzer.loops
    metrics.ifs = analyzer.ifs
    metrics.max_depth = analyzer.max_depth
    metrics.imports = analyzer.imports
    metrics.local_imports = analyzer.local_imports
    metrics.function_metrics = analyzer.function_metrics

    metrics.unused_imports = detect_unused_imports(
        analyzer.import_names, analyzer.all_names
    )
    metrics.empty_functions = detect_empty_functions(metrics.function_metrics)

    return metrics, tree


def scan_folder(folder: str) -> Tuple[List[FileMetrics], DependencyGraph]:
    """Scan a folder for Python files, analyze each, build dependency graph."""
    results = []
    graph = DependencyGraph()
    module_map = {}

    for root_dir, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root_dir, fname)
            metrics, tree = score_file(fpath, folder)
            results.append(metrics)

            if tree is not None:
                mod_name = file_to_module(fpath, folder)
                module_map[mod_name] = fpath
                graph.add_node(mod_name)

    for metrics in results:
        if metrics.parse_error:
            continue
        fpath = os.path.join(folder, metrics.file)
        mod_name = file_to_module(fpath, folder)
        metrics.resolved_imports = resolve_imports(
            metrics.imports, metrics.local_imports, module_map
        )
        for resolved in metrics.resolved_imports:
            if resolved != mod_name:
                graph.add_edge(mod_name, resolved)

    graph.detect_cycles()
    graph.compute_layers()

    return results, graph


# ---------------------------------------------------------------------------
# RANKING
# ---------------------------------------------------------------------------

def rank_files(metrics_list: List[FileMetrics], graph: DependencyGraph,
               root: str) -> List[FileScore]:
    scores = []
    for metrics in metrics_list:
        mod_name = file_to_module(
            os.path.join(root, metrics.file), root
        ) if not metrics.parse_error else None
        fs = compute_score(metrics, graph, mod_name)
        fs.grade = grade_for_score(fs.score)
        scores.append(fs)

    scores.sort(key=lambda x: x.score, reverse=True)
    for i, s in enumerate(scores, 1):
        s.rank = i

    return scores


# ---------------------------------------------------------------------------
# TREND TRACKER
# ---------------------------------------------------------------------------

HISTORY_FILE = "/tmp/ast_ranker_history.json"


def load_history() -> Dict[str, int]:
    if not os.path.isfile(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
        return data.get("scores", {})
    except Exception:
        return {}


def save_history(scores: List[FileScore]):
    data = {
        "timestamp": time.time(),
        "scores": {s.metrics.file: s.score for s in scores},
    }
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def apply_trends(scores: List[FileScore], history: Dict[str, int]):
    for s in scores:
        prev = history.get(s.metrics.file)
        if prev is not None:
            s.prev_score = prev
            s.delta = s.score - prev


# ---------------------------------------------------------------------------
# TERMINAL REPORT
# ---------------------------------------------------------------------------

GRADE_COLORS = {
    "A": "\033[92m",
    "B": "\033[94m",
    "C": "\033[93m",
    "D": "\033[33m",
    "E": "\033[91m",
    "F": "\033[31m",
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"


def color_grade(grade: str) -> str:
    return GRADE_COLORS.get(grade, "") + grade + RESET


def format_delta(delta: Optional[int]) -> str:
    if delta is None:
        return ""
    if delta > 0:
        return GREEN + " (+%d)" % delta + RESET
    if delta < 0:
        return RED + " (%d)" % delta + RESET
    return DIM + " (0)" + RESET


def print_report(scores: List[FileScore], graph: DependencyGraph,
                 verbose: bool = False, show_functions: bool = False,
                 show_suggestions: bool = False):
    total = len(scores)
    passed = sum(1 for s in scores if s.metrics.parse_error is None)
    failed = total - passed
    avg_score = sum(s.score for s in scores) / total if total else 0
    a_count = sum(1 for s in scores if s.grade == "A")
    cycle_count = len(graph.cycles)
    improved = sum(1 for s in scores if s.delta is not None and s.delta > 0)
    regressed = sum(1 for s in scores if s.delta is not None and s.delta < 0)

    print()
    print(BOLD + "=== AST CODE RANKING v2 ===" + RESET)
    print()
    print(f"  Files scanned:  {total}")
    print(f"  Parsed OK:      {passed}")
    print(f"  Parse errors:   {failed}")
    print(f"  Avg score:      {avg_score:.1f}")
    print(f"  Grade A files:  {a_count}")
    print(f"  Cycles found:   {cycle_count}")
    if improved or regressed:
        print(f"  Improved:       {GREEN}{improved}{RESET}")
        print(f"  Regressed:      {RED}{regressed}{RESET}")
    print()

    print(BOLD + "--- LEADERBOARD ---" + RESET)
    print()
    for s in scores:
        grade_str = color_grade(s.grade)
        delta_str = format_delta(s.delta)
        status = " | ".join(s.metrics.issues) if s.metrics.issues else "OK"
        bcl_str = ""
        if s.metrics.bcl_tags:
            bcl_str = "  BCL: %s [%d tags]" % (s.metrics.bcl_format, len(s.metrics.bcl_tags))

        print(
            f"  {s.rank:02d}. [{grade_str}] {s.metrics.file}{delta_str}\n"
            f"      Score: {s.score:>5}  (struct: {s.structure}, "
            f"complex: {s.complexity}, hygiene: {s.hygiene}, bcl: {s.bcl})\n"
            f"      Func: {s.metrics.functions:>3}  Class: {s.metrics.classes:>3}  "
            f"Loops: {s.metrics.loops:>3}  Ifs: {s.metrics.ifs:>3}  "
            f"Depth: {s.metrics.max_depth:>2}  Lines: {s.metrics.lines:>4}{bcl_str}"
        )
        if s.metrics.unused_imports:
            print(f"      Unused imports: {', '.join(s.metrics.unused_imports[:5])}")
        if s.metrics.empty_functions:
            print(f"      Empty functions: {', '.join(s.metrics.empty_functions[:5])}")
        print(f"      Status: {status}")
        print()

        if show_functions and s.metrics.function_metrics:
            god_funcs = [fm for fm in s.metrics.function_metrics if fm.issues]
            if god_funcs:
                print(f"      {DIM}--- Function Issues ---{RESET}")
                for fm in god_funcs[:10]:
                    print(
                        f"      L{fm.line:>4} {fm.name}() "
                        f"lines={fm.lines} cx={fm.complexity} depth={fm.max_depth} "
                        f"-> {', '.join(fm.issues)}"
                    )
                print()

        if show_suggestions and s.suggestions:
            print(f"      {YELLOW}--- Refactor Suggestions ---{RESET}")
            for sug in s.suggestions[:10]:
                print(f"      {YELLOW}*{RESET} {sug}")
            if len(s.suggestions) > 10:
                print(f"      ... and {len(s.suggestions) - 10} more")
            print()

    if graph.cycles:
        print(BOLD + "--- CIRCULAR DEPENDENCIES ---" + RESET)
        print()
        for i, cycle in enumerate(graph.cycles, 1):
            chain = " -> ".join(cycle[:6])
            if len(cycle) > 6:
                chain += " -> ..."
            print(f"  Cycle {i}: {chain}")
        print()

    if graph.layers and verbose:
        print(BOLD + "--- DEPENDENCY LAYERS ---" + RESET)
        print()
        by_layer = defaultdict(list)
        for mod, layer in graph.layers.items():
            by_layer[layer].append(mod)
        for layer in sorted(by_layer.keys()):
            mods = by_layer[layer]
            print(f"  Layer {layer}: {len(mods)} modules")
            for m in mods[:5]:
                print(f"    - {m}")
            if len(mods) > 5:
                print(f"    ... and {len(mods) - 5} more")
        print()

    print(BOLD + "--- GRADE DISTRIBUTION ---" + RESET)
    print()
    grade_counts = {g: 0 for g in "ABCDEF"}
    for s in scores:
        grade_counts[s.grade] = grade_counts.get(s.grade, 0) + 1
    for g in "ABCDEF":
        count = grade_counts.get(g, 0)
        bar = "#" * count
        print(f"  {color_grade(g)}: {count:>3} {bar}")
    print()

    if verbose:
        print(BOLD + "--- DEAD CODE SUMMARY ---" + RESET)
        print()
        total_unused = sum(len(s.metrics.unused_imports) for s in scores)
        total_empty = sum(len(s.metrics.empty_functions) for s in scores)
        total_god = sum(
            1 for s in scores
            for fm in s.metrics.function_metrics
            if "HIGH_COMPLEXITY" in fm.issues
        )
        print(f"  Unused imports:  {total_unused}")
        print(f"  Empty functions: {total_empty}")
        print(f"  God functions:   {total_god}")
        print()


# ---------------------------------------------------------------------------
# JSON EXPORT
# ---------------------------------------------------------------------------

def export_json(scores: List[FileScore], graph: DependencyGraph) -> str:
    data = {
        "summary": {
            "total_files": len(scores),
            "avg_score": sum(s.score for s in scores) / len(scores) if scores else 0,
            "cycles": len(graph.cycles),
            "improved": sum(1 for s in scores if s.delta is not None and s.delta > 0),
            "regressed": sum(1 for s in scores if s.delta is not None and s.delta < 0),
        },
        "rankings": [
            {
                "rank": s.rank,
                "file": s.metrics.file,
                "score": s.score,
                "grade": s.grade,
                "prev_score": s.prev_score,
                "delta": s.delta,
                "structure": s.structure,
                "complexity": s.complexity,
                "hygiene": s.hygiene,
                "bcl": s.bcl,
                "bcl_format": s.metrics.bcl_format,
                "bcl_tags": s.metrics.bcl_tags,
                "metrics": {
                    "lines": s.metrics.lines,
                    "functions": s.metrics.functions,
                    "classes": s.metrics.classes,
                    "loops": s.metrics.loops,
                    "ifs": s.metrics.ifs,
                    "max_depth": s.metrics.max_depth,
                    "imports": len(s.metrics.imports),
                    "unused_imports": s.metrics.unused_imports,
                    "empty_functions": s.metrics.empty_functions,
                },
                "function_issues": [
                    {
                        "name": fm.name,
                        "line": fm.line,
                        "lines": fm.lines,
                        "complexity": fm.complexity,
                        "issues": fm.issues,
                    }
                    for fm in s.metrics.function_metrics if fm.issues
                ],
                "issues": s.metrics.issues,
                "suggestions": s.suggestions,
            }
            for s in scores
        ],
        "cycles": graph.cycles,
        "layers": {k: v for k, v in sorted(graph.layers.items(), key=lambda x: x[1])},
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def print_query_result(rows: list, query: str):
    """Print query results in a readable terminal format."""
    print()
    print(BOLD + "=== CODE INTEL QUERY: %s ===" % query + RESET)
    print()
    if not rows:
        print("  No results.")
        print()
        return
    if isinstance(rows, dict):
        rows = [rows]
    cols = list(rows[0].keys()) if rows else []
    for row in rows[:50]:
        parts = []
        for col in cols:
            val = row.get(col, "")
            if val is None:
                val = ""
            parts.append("%s=%s" % (col, val))
        print("  " + " | ".join(parts))
    if len(rows) > 50:
        print("  ... and %d more" % (len(rows) - 50))
    print()


def run_query(db, query: str):
    """Dispatch a query string to the appropriate CodeIntelDB method."""
    q = query.strip().lower()

    if q in ("god_functions", "god"):
        return db.query_god_functions()
    if q == "regressed":
        return db.query_regressed_files()
    if q == "improved":
        return db.query_improved_files()
    if q in ("new", "added"):
        return db.query_new_files()
    if q == "deleted":
        return db.query_deleted_files()
    if q == "missing_bcl":
        return db.query_missing_bcl()
    if q == "unused_imports":
        return db.query_unused_imports_summary()
    if q == "history":
        return db.query_scan_history()
    if q == "stats":
        s = db.query_stats()
        return [s] if s else []
    if q == "top":
        return db.query_top_files()
    if q == "bottom":
        return db.query_bottom_files()
    if q.startswith("search:"):
        return db.query_search(query.split(":", 1)[1])
    if q.startswith("deps:"):
        mod = query.split(":", 1)[1]
        return [{"module": mod, "depends_on": d} for d in db.query_dependencies(mod)]
    if q.startswith("dependents:"):
        mod = query.split(":", 1)[1]
        return [{"module": mod, "imported_by": d} for d in db.query_dependents(mod)]
    if q.startswith("file:"):
        r = db.query_file_detail(query.split(":", 1)[1])
        return [r] if r else []
    if q.startswith("funcs:"):
        return db.query_functions_in_file(query.split(":", 1)[1])
    if q.startswith("grade:"):
        return db.query_files_by_grade(query.split(":", 1)[1].upper())
    if q.startswith("func:"):
        return db.query_function_by_name(query.split(":", 1)[1])

    print("Unknown query: %s" % query)
    print("Available: god_functions, regressed, improved, new, deleted, missing_bcl,")
    print("           unused_imports, history, stats, top, bottom,")
    print("           search:<text>, deps:<module>, dependents:<module>,")
    print("           file:<path>, funcs:<path>, grade:<A-F>, func:<name>")
    return []


def main():
    parser = argparse.ArgumentParser(
        description="AST Code Ranking System v2 — structural analysis + dependency graph + BCL + dead code + code intelligence"
    )
    parser.add_argument("folder", nargs="?", help="Folder to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of terminal report")
    parser.add_argument("--verbose", action="store_true", help="Show imports, dependency layers, dead code summary")
    parser.add_argument("--min-score", type=int, default=None, help="Only show files with score >= N")
    parser.add_argument("--functions", action="store_true", help="Show per-function issues")
    parser.add_argument("--suggest", action="store_true", help="Show refactor suggestions")
    parser.add_argument("--history", action="store_true", help="Track score trends across runs")
    parser.add_argument("--learn", action="store_true", help="Ingest results into SQLite code intelligence DB")
    parser.add_argument("--sync-mysql", action="store_true", help="Sync results into MySQL code_intel database (the powerhouse)")
    parser.add_argument("--defs", action="store_true", help="Extract every function/method def into SQLite ast_definitions (1 row = 1 def)")
    parser.add_argument("--query", metavar="Q", default=None, help="Query the code intelligence DB (SQLite or MySQL)")
    parser.add_argument("--mysql", action="store_true", help="Use MySQL for queries instead of SQLite")
    parser.add_argument("--db", metavar="PATH", default="/tmp/code_intel.sqlite", help="Path to code intelligence SQLite DB")
    args = parser.parse_args()

    if args.query:
        if args.mysql:
            if not MYSQL_INTEL_AVAILABLE:
                print("Error: code_intel_mysql.py not found or mysql.connector not installed")
                sys.exit(1)
            db = CodeIntelMySQL()
        else:
            if not CODE_INTEL_AVAILABLE:
                print("Error: code_intel_db.py not found")
                sys.exit(1)
            db = CodeIntelDB(args.db)
        rows = run_query(db, args.query)
        print_query_result(rows, args.query)
        db.close()
        return

    if not args.folder:
        parser.print_help()
        sys.exit(1)

    if not os.path.isdir(args.folder):
        print("Error: folder does not exist: %s" % args.folder)
        sys.exit(1)

    metrics_list, graph = scan_folder(args.folder)
    scores = rank_files(metrics_list, graph, args.folder)

    if args.history:
        history = load_history()
        apply_trends(scores, history)
        save_history(scores)

    if args.learn:
        if not CODE_INTEL_AVAILABLE:
            print("Error: code_intel_db.py not found")
            sys.exit(1)
        db = CodeIntelDB(args.db)
        run_id = db.ingest_scores(scores, graph, args.folder)
        print(BOLD + "\n  [LEARN] Ingested %d files into SQLite (run_id=%d)" % (len(scores), run_id) + RESET)
        db.close()

    if args.sync_mysql:
        if not MYSQL_INTEL_AVAILABLE:
            print("Error: code_intel_mysql.py not found or mysql.connector not installed")
            sys.exit(1)
        mdb = CodeIntelMySQL()
        run_id = mdb.ingest_scores(scores, graph, args.folder)
        fcount = mdb.query_function_count()
        ccount = mdb.query_class_count()
        print(BOLD + "\n  [MYSQL] Synced %d files, %d functions, %d classes into code_intel (run_id=%d)" % (
            len(scores), fcount, ccount, run_id) + RESET)
        mdb.close()

    if args.defs:
        if not DEF_STORE_AVAILABLE:
            print("Error: ast_def_store.py not found")
            sys.exit(1)
        store = AstDefStore("/tmp/ast_definitions.sqlite")
        run_id = store.ingest_scores(scores, args.folder)
        stats = store.query_stats()
        print(BOLD + "\n  [DEFS] Extracted %s definitions (%s methods, %s functions) into ast_definitions (run_id=%d)" % (
            stats.get("total", 0), stats.get("methods", 0), stats.get("functions", 0), run_id) + RESET)
        store.close()

    if args.min_score is not None:
        scores = [s for s in scores if s.score >= args.min_score]

    if args.json:
        print(export_json(scores, graph))
    else:
        print_report(
            scores, graph,
            verbose=args.verbose,
            show_functions=args.functions,
            show_suggestions=args.suggest,
        )


if __name__ == "__main__":
    main()
