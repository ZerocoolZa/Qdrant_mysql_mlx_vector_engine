"""
C Analysis Core — Stage 2 Implementation Layer
Pure extraction functions. No CLI, no orchestration, no cross-file logic.
Each function is self-contained and independently testable.
"""
import re
from collections import defaultdict

# =========================
# PATTERNS
# =========================

FUNC_DEF = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*\{')
FUNC_CALL = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

STRUCT_DEF = re.compile(r'\bstruct\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{')
ENUM_DEF   = re.compile(r'\benum\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{')

SQL_PATTERN = re.compile(r'(".*?SELECT.*?"|".*?INSERT.*?"|".*?UPDATE.*?"|".*?DELETE.*?")', re.I)
MYSQL_TABLE = re.compile(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)|\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.I)

TODO_PATTERN = re.compile(r'(TODO|FIXME|HACK)\s*[:\-]?\s*(.*)')

IFDEF_PATTERN = re.compile(r'#(ifdef|ifndef|if|elif|else|endif)\b')

GLOBAL_VAR = re.compile(r'^(static\s+)?[a-zA-Z_][a-zA-Z0-9_\*\s]+[a-zA-Z_][a-zA-Z0-9_]*\s*(=|;)', re.M)

INCLUDE_PATTERN = re.compile(r'#include\s+[<"]([^">]+)[">]')
BCL_PACKET_PATTERN = re.compile(r'\[@([A-Z0-9]+)\]\{([^}]+)\}')


# =========================
# FUNCTIONS
# =========================

def extract_functions(code):
    return [(m.group(1), m.group(2), m.start()) for m in FUNC_DEF.finditer(code)]


def function_body_ranges(code):
    funcs = []
    for m in FUNC_DEF.finditer(code):
        name = m.group(1)
        start = m.end() - 1

        depth = 0
        for i in range(start, len(code)):
            if code[i] == '{':
                depth += 1
            elif code[i] == '}':
                depth -= 1
                if depth == 0:
                    funcs.append((name, start, i))
                    break
    return funcs


def function_body_sizes(code):
    return {name: (end - start) for name, start, end in function_body_ranges(code)}


def function_arity(code):
    result = {}
    for m in FUNC_DEF.finditer(code):
        params = m.group(2).strip()
        if not params:
            result[m.group(1)] = 0
        else:
            result[m.group(1)] = len([p for p in params.split(",") if p.strip()])
    return result


def static_vs_exported(code):
    result = {}
    for m in FUNC_DEF.finditer(code):
        line_start = code.rfind('\n', 0, m.start()) + 1
        line = code[line_start:m.start()]
        result[m.group(1)] = "static" if "static" in line else "exported"
    return result


# =========================
# STRUCT / ENUM
# =========================

def extract_struct_fields(code):
    structs = {}

    for m in STRUCT_DEF.finditer(code):
        name = m.group(1)
        start = m.end()

        depth = 1
        end = start

        for i in range(start, len(code)):
            if code[i] == '{':
                depth += 1
            elif code[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        block = code[start:end]
        fields = []

        for line in block.splitlines():
            line = line.strip().strip(';')
            if line and not line.startswith('//'):
                fields.append(line)

        structs[name] = fields

    return structs


def extract_enums(code):
    enums = {}

    for m in ENUM_DEF.finditer(code):
        name = m.group(1)
        block = code[m.end():]

        enum_body = block.split('}')[0]
        enums[name] = [x.strip() for x in enum_body.split(',') if x.strip()]

    return enums


# =========================
# GLOBAL VARS
# =========================

def extract_global_vars(code):
    return [m.group(0).strip() for m in GLOBAL_VAR.finditer(code)]


# =========================
# CALL GRAPH
# =========================

def build_call_graph(code):
    funcs = extract_functions(code)
    graph = defaultdict(set)

    for name, _, start in funcs:
        body = code[start:start + 5000]
        calls = FUNC_CALL.findall(body)

        for c in calls:
            if c != name:
                graph[name].add(c)

    return graph


def dead_functions(code):
    funcs = set(f[0] for f in extract_functions(code))
    graph = build_call_graph(code)

    called = set()
    for targets in graph.values():
        called.update(targets)

    return list(funcs - called)


def circular_dependencies(graph):
    visited = set()
    stack = set()
    cycles = []

    def dfs(node, path):
        if node in stack:
            cycles.append(path + [node])
            return
        if node in visited:
            return

        visited.add(node)
        stack.add(node)

        for nxt in graph.get(node, []):
            dfs(nxt, path + [node])

        stack.remove(node)

    for n in graph:
        dfs(n, [])

    return cycles


# =========================
# TODO / COMMENTS
# =========================

def extract_todos(code):
    return [(m.group(1), m.group(2).strip()) for m in TODO_PATTERN.finditer(code)]


# =========================
# SQL / MYSQL
# =========================

def extract_sql_queries(code):
    return SQL_PATTERN.findall(code)


def extract_mysql_tables(code):
    tables = []
    for m in MYSQL_TABLE.finditer(code):
        tables.append(m.group(1) or m.group(2))
    return [t for t in tables if t]


# =========================
# IFDEF
# =========================

def extract_ifdef_blocks(code):
    blocks = []
    stack = []

    for m in IFDEF_PATTERN.finditer(code):
        tag = m.group(0)

        if tag.startswith("#if") and not tag.startswith("#endif"):
            stack.append((tag, m.start()))

        elif tag.startswith("#endif") and stack:
            start_tag, start_idx = stack.pop()
            blocks.append((start_tag, start_idx, m.end()))

    return blocks


# =========================
# NESTING DEPTH
# =========================

def max_nesting_depth(code):
    depth = 0
    max_depth = 0

    for c in code:
        if c == '{':
            depth += 1
            max_depth = max(max_depth, depth)
        elif c == '}':
            depth -= 1

    return max_depth


# =========================
# HEADER DEPENDENCIES
# =========================

def header_dependency_tree(code):
    return INCLUDE_PATTERN.findall(code)


# =========================
# BCL PACKETS
# =========================

def extract_bcl_packets(code):
    return [(m.group(1), m.group(2)) for m in BCL_PACKET_PATTERN.finditer(code)]
