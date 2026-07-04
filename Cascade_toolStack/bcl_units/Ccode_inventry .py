#!/usr/bin/env python3
"""
BCL Units C File Introspection Scanner — MAXIMUM EXTRACTION v2
Extracts every structural detail from .c files and writes markdown report.
"""
import os, re, hashlib
from datetime import datetime

ROOT = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bcl_units"
OUT  = os.path.join(ROOT, "bcl_units_full_analysis.md")

# ── PATTERNS ──

INCLUDE_RE = re.compile(r'^\s*#include\s+([<"].+?[>"])', re.MULTILINE)
IFDEF_RE   = re.compile(r'^\s*#(?:ifdef|ifndef|if)\s+(.+)$', re.MULTILINE)
ENDIF_RE   = re.compile(r'^\s*#endif', re.MULTILINE)
DEFINE_RE  = re.compile(r'^\s*#define\s+(\w+)(?:\s+(.+))?$', re.MULTILINE)
STRUCT_RE  = re.compile(r'\b(?:typedef\s+)?struct\s+(\w+)?\s*\{', re.MULTILINE)
ENUM_RE    = re.compile(r'\benum\s+(\w+)?\s*\{', re.MULTILINE)
TYPEDEF_RE = re.compile(r'^\s*typedef\s+(?:struct\s+\w+\s*\{[^}]*\}\s*)?(\w+)\s*;', re.MULTILINE | re.DOTALL)
CALL_RE    = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
CMD_RE     = re.compile(r'strcmp\s*\(\s*cmd\s*,\s*"([^"]+)"\)')
GHOST_RE   = re.compile(r'\[@GHOST\]\{([^}]*)\}')
SUMMARY_RE = re.compile(r'summary="([^"]*)"')
CLASS_RE   = re.compile(r'class="([^"]*)"')
METHOD_RE  = re.compile(r'method="([^"]*)"')
STRING_RE  = re.compile(r'"((?:[^"\\]|\\.)*)"')
STATIC_ARRAY_RE = re.compile(r'static\s+(?:const\s+)?(?:unsigned\s+char|char|int|long|struct\s+\w+)\s+(\w+)\s*\[', re.MULTILINE)
TODO_RE    = re.compile(r'(?:TODO|FIXME|HACK|XXX|BUG|NOTE)(?:\s*:\s*(.+?))?$', re.MULTILINE | re.IGNORECASE)
SQL_RE     = re.compile(r'"((?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|SHOW|DESCRIBE)\s[^"]{5,})"', re.IGNORECASE)
TABLE_RE   = re.compile(r'(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(\w+)', re.IGNORECASE)
BCL_PKT_RE = re.compile(r'"(\[@\w+\]\{[^"]*\})"')
BCL_PKT_BODY_RE = re.compile(r'\[@(\w+)\]\{([^}]+)\}')
GLOBAL_VAR_RE = re.compile(
    r'^(?:static\s+)?(?:const\s+)?(?:unsigned\s+|signed\s+)?'
    r'(?:int|char|double|float|size_t|long|short|FILE\s*\*|'
    r'sqlite3\s*\*|MYSQL\s*\*|struct\s+\w+|'
    r'\w+_\w+\s*\*?|const\s+char\s*\*|unsigned\s+char\s*\*|char\s*\*)\s+'
    r'(\w+)(?:\s*\[)?(?:\s*=)?',
    re.MULTILINE
)

# Function with full signature capture: return type + name + params
FUNC_SIG_RE = re.compile(
    r'^((?:static\s+)?(?:const\s+)?(?:inline\s+)?'
    r'(?:unsigned\s+|signed\s+)?'
    r'(?:int|void|char|double|float|size_t|long|short|FILE\s*\*|'
    r'sqlite3\s*\*|sqlite3_stmt\s*\*|sqlite3_int64|'
    r'MYSQL\s*\*|MYSQL_RES\s*\*|MYSQL_ROW|'
    r'BclParseResult\s*\*|EVP_CIPHER_CTX\s*\*|'
    r'\w+_\w+\s*\*?|const\s+char\s*\*|unsigned\s+char\s*\*|char\s*\*))\s+'
    r'(\*?\s*\w+)\s*\(([^;]*?)\)\s*\{',
    re.MULTILINE
)

# Global/static variable declarations (not inside functions)
GLOBAL_VAR_RE = re.compile(
    r'^(?:static\s+)?(?:const\s+)?(?:unsigned\s+|signed\s+)?'
    r'(?:int|char|double|float|size_t|long|short|FILE\s*\*|'
    r'sqlite3\s*\*|MYSQL\s*\*|struct\s+\w+|'
    r'\w+_\w+\s*\*?|const\s+char\s*\*|unsigned\s+char\s*\*|char\s*\*)\s+'
    r'(\w+)(?:\s*\[)?(?:\s*=)?',
    re.MULTILINE
)

C_KEYWORDS = {
    'if','for','while','switch','case','else','return','sizeof','break','continue',
    'goto','do','default','typedef','struct','enum','union','void','int','char',
    'short','long','float','double','unsigned','signed','const','static','inline',
    'extern','register','volatile','auto',
}

C_STDLIB = {
    'strcmp','strncmp','strcasecmp','strncasecmp','strstr','strcasestr','strrchr',
    'strchr','strlen','strncpy','strncat','strcat','strcpy','strdup',
    'snprintf','printf','fprintf','sprintf','sscanf','scanf',
    'memcpy','memset','memmove','memcmp','memchr',
    'malloc','calloc','realloc','free',
    'fopen','fclose','fgets','fread','fwrite','fseek','ftell','feof','ferror',
    'opendir','readdir','closedir','rewinddir',
    'stat','lstat','fstat','mkdir','rmdir','remove','rename',
    'time','clock','difftime','localtime','gmtime',
    'atoi','atof','atol','strtol','strtod',
    'exit','abort','atexit','qsort','bsearch','rand','srand',
}

MYSQL_FUNCS = {
    'mysql_query','mysql_store_result','mysql_fetch_row','mysql_free_result',
    'mysql_real_escape_string','mysql_init','mysql_real_connect','mysql_close',
    'mysql_num_rows','mysql_fetch_fields','mysql_field_count','mysql_error',
    'mysql_num_fields','mysql_next_result','mysql_use_result','mysql_data_seek',
    'mysql_fetch_field','mysql_fetch_field_direct','mysql_affected_rows',
    'mysql_insert_id','mysql_escape_string','mysql_options',
}

SQLITE_FUNCS = {
    'sqlite3_open','sqlite3_close','sqlite3_exec','sqlite3_prepare_v2',
    'sqlite3_step','sqlite3_finalize','sqlite3_bind_text','sqlite3_bind_int',
    'sqlite3_bind_int64','sqlite3_bind_double','sqlite3_bind_blob',
    'sqlite3_bind_null','sqlite3_column_text','sqlite3_column_int',
    'sqlite3_column_int64','sqlite3_column_double','sqlite3_column_blob',
    'sqlite3_column_count','sqlite3_column_name','sqlite3_last_insert_rowid',
    'sqlite3_changes','sqlite3_errmsg','sqlite3_reset',
}

OPENSSL_FUNCS = {
    'EVP_CIPHER_CTX_new','EVP_CIPHER_CTX_free','EVP_CIPHER_CTX_ctrl',
    'EVP_DecryptInit_ex','EVP_DecryptUpdate','EVP_DecryptFinal_ex',
    'EVP_EncryptInit_ex','EVP_EncryptUpdate','EVP_EncryptFinal_ex',
    'EVP_aes_256_gcm','EVP_aes_128_cbc','EVP_sha256',
}

BCL_FUNCS = {
    'BclParser_Init','BclParser_Parse','BclParser_Extract','BclParser_Free',
    'BclResult_Ok','BclResult_Err',
}

ALL_STDLIB = C_STDLIB | MYSQL_FUNCS | SQLITE_FUNCS | OPENSSL_FUNCS | BCL_FUNCS

# ── HELPERS ──

def read_file(path):
    with open(path, "r", errors="ignore") as f:
        return f.read()

def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//.*', '', text)
    return text

def sha256_short(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]

def find_matching_brace(text, start_pos):
    """Find the closing brace that matches the opening brace at start_pos."""
    depth = 0
    i = start_pos
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

def count_max_nesting(body):
    """Count maximum brace nesting depth in a function body."""
    depth = 0
    max_depth = 0
    for ch in body:
        if ch == '{':
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == '}':
            depth -= 1
    return max_depth

def extract_global_vars(code):
    """Extract global/static variable declarations outside function bodies."""
    globals_list = []
    for m in GLOBAL_VAR_RE.finditer(code):
        decl = m.group(0).strip()
        if decl and not any(kw in decl for kw in ['return', 'if', 'for', 'while', 'switch']):
            globals_list.append(decl)
    return globals_list

def build_intra_file_call_graph(code, func_names):
    """Build function-to-function call graph within a single file.
    Returns: {caller: set(callees)}"""
    from collections import defaultdict
    graph = defaultdict(set)
    for m in FUNC_SIG_RE.finditer(code):
        name = m.group(2).replace('*','').strip()
        if name not in func_names:
            continue
        brace_pos = code.find('{', m.end() - 1)
        if brace_pos == -1:
            brace_pos = m.end()
        end_brace = find_matching_brace(code, brace_pos)
        body = code[brace_pos:end_brace+1] if end_brace > 0 else ""
        calls = set(CALL_RE.findall(body))
        for c in calls:
            if c in func_names and c != name:
                graph[name].add(c)
    return graph

def detect_intra_file_cycles(graph):
    """DFS-based circular dependency detection within a file.
    Returns list of cycles (each cycle is a list of function names)."""
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

def extract_struct_fields(raw, struct_name):
    """Extract field names from a named struct."""
    if not struct_name:
        return []
    pat = re.compile(r'struct\s+' + re.escape(struct_name) + r'\s*\{([^}]*)\}', re.DOTALL)
    m = pat.search(raw)
    if not m:
        return []
    body = m.group(1)
    fields = []
    for line in body.split(';'):
        line = line.strip()
        if not line or line.startswith('/*') or line.startswith('//'):
            continue
        m2 = re.match(r'(?:\w+\s+)*\*?\s*(\w+)\s*(?:\[\d*\])?\s*$', line)
        if m2:
            fields.append(m2.group(1))
    return fields

def extract_enum_constants(raw, enum_name):
    """Extract constant names from a named enum."""
    if not enum_name:
        return []
    pat = re.compile(r'enum\s+' + re.escape(enum_name) + r'\s*\{([^}]*)\}', re.DOTALL)
    m = pat.search(raw)
    if not m:
        return []
    body = m.group(1)
    constants = []
    for item in body.split(','):
        item = item.strip()
        if not item:
            continue
        m2 = re.match(r'(\w+)(?:\s*=\s*.+)?$', item)
        if m2:
            constants.append(m2.group(1))
    return constants

def extract_ifdef_blocks(raw):
    """Extract #ifdef/#ifndef/#if blocks with their condition."""
    blocks = []
    lines = raw.splitlines()
    stack = []
    for i, line in enumerate(lines):
        m = IFDEF_RE.match(line)
        if m:
            stack.append((m.group(1).strip(), i+1))
        elif ENDIF_RE.match(line) and stack:
            cond, start = stack.pop()
            blocks.append({'condition': cond, 'start_line': start, 'end_line': i+1})
    return blocks

# ── ANALYSIS ──

def analyze_file(path):
    raw = read_file(path)
    code = strip_comments(raw)
    fname = os.path.basename(path)

    includes = [m.strip() for m in INCLUDE_RE.findall(raw)]
    defines = DEFINE_RE.findall(raw)
    structs = [s for s in STRUCT_RE.findall(raw) if s]
    enums = [e for e in ENUM_RE.findall(raw) if e]
    typedefs = TYPEDEF_RE.findall(raw)
    static_arrays = STATIC_ARRAY_RE.findall(code)
    ifdef_blocks = extract_ifdef_blocks(raw)
    todos = TODO_RE.findall(raw)
    sql_queries = SQL_RE.findall(code)
    table_refs = list(dict.fromkeys(TABLE_RE.findall(' '.join(sql_queries))))
    bcl_packets = BCL_PKT_RE.findall(code)
    bcl_packet_bodies = BCL_PKT_BODY_RE.findall(code)
    global_vars = extract_global_vars(code)

    # Struct fields
    struct_details = {}
    for s in structs:
        struct_details[s] = extract_struct_fields(raw, s)

    # Enum constants
    enum_details = {}
    for e in enums:
        enum_details[e] = extract_enum_constants(raw, e)

    # Functions with full signatures + body info
    functions = []
    for m in FUNC_SIG_RE.finditer(code):
        ret_type = m.group(1).strip()
        name = m.group(2).replace('*','').strip()
        params = m.group(3).strip()
        if not name or name in C_KEYWORDS:
            continue

        is_static = m.group(1).startswith('static')
        brace_pos = code.find('{', m.end() - 1)
        if brace_pos == -1:
            brace_pos = m.end()
        end_brace = find_matching_brace(code, brace_pos)
        body = code[brace_pos:end_brace+1] if end_brace > 0 else ""
        body_lines = body.count('\n')
        max_nesting = count_max_nesting(body)

        # Count params
        if params.strip() in ('void', ''):
            param_count = 0
        else:
            param_count = len([p for p in params.split(',') if p.strip() and p.strip() != 'void'])

        # Find line number
        line_no = code[:m.start()].count('\n') + 1

        # Intra-file calls within this function body
        body_calls = set(CALL_RE.findall(body))
        body_calls = body_calls - C_KEYWORDS - ALL_STDLIB

        functions.append({
            'name': name,
            'return_type': ret_type,
            'params': params,
            'param_count': param_count,
            'is_static': is_static,
            'line': line_no,
            'body_lines': body_lines,
            'max_nesting': max_nesting,
            'calls_in_body': sorted(body_calls),
        })

    func_names = [f['name'] for f in functions]

    # Intra-file call graph + cycle detection
    intra_graph = build_intra_file_call_graph(code, func_names)
    intra_cycles = detect_intra_file_cycles(intra_graph)

    # All calls in file (for dead code detection)
    all_calls_in_file = set()
    for m in CALL_RE.finditer(code):
        name = m.group(1)
        if name not in C_KEYWORDS and name not in ALL_STDLIB:
            all_calls_in_file.add(name)

    # Dead functions: defined but never called anywhere in this file
    dead_funcs = [f for f in func_names if f not in all_calls_in_file]

    # External calls (calls to functions not defined in this file)
    external_calls = sorted(all_calls_in_file - set(func_names))

    bcl_cmds = CMD_RE.findall(code)
    strings = STRING_RE.findall(code)

    # Headers
    headers = {}
    g = GHOST_RE.search(raw)
    headers['ghost'] = g.group(1)[:300] if g else ''
    s = SUMMARY_RE.search(raw)
    headers['summary'] = s.group(1) if s else ''
    c = CLASS_RE.search(raw)
    headers['class'] = c.group(1) if c else ''
    headers['methods'] = METHOD_RE.findall(raw)

    # Complexity
    complexity = 0
    for kw in ['if','for','while','switch','case','else']:
        complexity += len(re.findall(r'\b' + kw + r'\b', code))

    lines = len(raw.splitlines())
    code_lines = len([l for l in code.splitlines() if l.strip()])
    comment_lines = lines - code_lines

    status = "IMPLEMENTED" if lines > 100 and len(func_names) > 3 else "SHELL" if lines <= 50 else "PARTIAL"

    # Domain detection
    domains = []
    inc_str = ' '.join(includes).lower()
    if 'mysql' in inc_str: domains.append('mysql')
    if 'sqlite' in inc_str: domains.append('sqlite')
    if 'openssl' in inc_str: domains.append('crypto')
    if 'dirent' in inc_str or 'sys/stat' in inc_str: domains.append('filesystem')
    if 'sys/socket' in inc_str or 'curl' in inc_str: domains.append('network')
    if any('search' in c for c in bcl_cmds): domains.append('search')
    if any('ingest' in c for c in bcl_cmds): domains.append('ingestion')
    if any('clean' in c for c in bcl_cmds): domains.append('cleanup')
    if any('lint' in c or 'check' in c for c in bcl_cmds): domains.append('validation')
    if any('merge' in c for c in bcl_cmds): domains.append('build')
    if any('discover' in c for c in bcl_cmds): domains.append('discovery')
    if not domains: domains.append('unknown')

    risk = "HIGH" if complexity > 80 else "MEDIUM" if complexity > 30 else "LOW"

    return {
        'file': fname,
        'path': path,
        'lines': lines,
        'code_lines': code_lines,
        'comment_lines': comment_lines,
        'functions': functions,
        'function_count': len(functions),
        'func_names': func_names,
        'dead_funcs': dead_funcs,
        'external_calls': external_calls,
        'call_count': len(external_calls),
        'includes': includes,
        'defines': defines,
        'structs': structs,
        'struct_details': struct_details,
        'enums': enums,
        'enum_details': enum_details,
        'typedefs': typedefs,
        'static_arrays': static_arrays,
        'ifdef_blocks': ifdef_blocks,
        'todos': todos,
        'sql_queries': sql_queries,
        'table_refs': table_refs,
        'bcl_commands': bcl_cmds,
        'bcl_packets': bcl_packets,
        'bcl_packet_bodies': bcl_packet_bodies,
        'global_vars': global_vars,
        'intra_call_graph': dict(intra_graph),
        'intra_cycles': intra_cycles,
        'strings': strings[:50],
        'headers': headers,
        'complexity': complexity,
        'risk': risk,
        'status': status,
        'domain': ', '.join(domains),
        'sha': sha256_short(raw),
    }

def build_call_graph(all_data):
    """Build cross-file and intra-file call graphs."""
    func_to_file = {}
    for d in all_data:
        for f in d['func_names']:
            func_to_file[f] = d['file']

    cross = {}
    for d in all_data:
        targets = []
        for call in d['external_calls']:
            if call in func_to_file and func_to_file[call] != d['file']:
                targets.append((call, func_to_file[call]))
        cross[d['file']] = targets

    # Circular dependency detection: file A calls file B, file B calls file A
    file_deps = {}
    for d in all_data:
        deps = set()
        for fn, tgt in cross[d['file']]:
            deps.add(tgt)
        file_deps[d['file']] = deps

    circulars = []
    for f1 in file_deps:
        for f2 in file_deps[f1]:
            if f1 in file_deps.get(f2, set()):
                pair = tuple(sorted([f1, f2]))
                if pair not in circulars:
                    circulars.append(pair)

    return func_to_file, cross, circulars

def write_report(data):
    func_map, cross_calls, circulars = build_call_graph(data)

    with open(OUT, "w") as f:
        f.write("# BCL Units Full Structural Analysis v2\n\n")
        f.write(f"Generated: {datetime.now()}\n\n")

        # Overview
        total_lines = sum(d['lines'] for d in data)
        total_code = sum(d['code_lines'] for d in data)
        total_funcs = sum(d['function_count'] for d in data)
        total_cx = sum(d['complexity'] for d in data)
        total_dead = sum(len(d['dead_funcs']) for d in data)
        total_todos = sum(len(d['todos']) for d in data)
        total_sql = sum(len(d['sql_queries']) for d in data)
        impl = sum(1 for d in data if d['status']=='IMPLEMENTED')
        shell = sum(1 for d in data if d['status']=='SHELL')
        partial = sum(1 for d in data if d['status']=='PARTIAL')

        f.write("## Overview\n\n")
        f.write("| Metric | Value |\n|---|---|\n")
        f.write(f"| Files | {len(data)} |\n")
        f.write(f"| Total lines | {total_lines} |\n")
        f.write(f"| Code lines | {total_code} |\n")
        f.write(f"| Comment lines | {total_lines - total_code} |\n")
        f.write(f"| Functions | {total_funcs} |\n")
        f.write(f"| Dead functions | {total_dead} |\n")
        f.write(f"| Complexity | {total_cx} |\n")
        f.write(f"| TODOs/FIXMEs | {total_todos} |\n")
        f.write(f"| SQL queries | {total_sql} |\n")
        total_intra_cycles = sum(len(d['intra_cycles']) for d in data)
        total_globals = sum(len(d['global_vars']) for d in data)
        total_bcl_pkts = sum(len(d['bcl_packet_bodies']) for d in data)
        f.write(f"| Circular deps (cross-file) | {len(circulars)} |\n")
        f.write(f"| Circular deps (intra-file) | {total_intra_cycles} |\n")
        f.write(f"| Global vars | {total_globals} |\n")
        f.write(f"| BCL packet patterns | {total_bcl_pkts} |\n")
        f.write(f"| IMPLEMENTED | {impl} |\n")
        f.write(f"| PARTIAL | {partial} |\n")
        f.write(f"| SHELL | {shell} |\n\n")

        # Summary table
        f.write("## Summary Table\n\n")
        f.write("| File | Lines | Code | Funcs | Dead | CX | Nest | Risk | Status | Domain | SQL | TODO | GV | Pkt | Cyc | Cmds |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for d in sorted(data, key=lambda x: -x['lines']):
            max_nest = max((fn['max_nesting'] for fn in d['functions']), default=0)
            cmds = ', '.join(d['bcl_commands'][:4])
            if len(d['bcl_commands'])>4: cmds += f" (+{len(d['bcl_commands'])-4})"
            f.write(f"| {d['file']} | {d['lines']} | {d['code_lines']} | "
                    f"{d['function_count']} | {len(d['dead_funcs'])} | "
                    f"{d['complexity']} | {max_nest} | {d['risk']} | "
                    f"{d['status']} | {d['domain']} | "
                    f"{len(d['sql_queries'])} | {len(d['todos'])} | "
                    f"{len(d['global_vars'])} | {len(d['bcl_packet_bodies'])} | "
                    f"{len(d['intra_cycles'])} | {cmds} |\n")

        # Circular dependencies
        if circulars:
            f.write("\n## Circular Dependencies\n\n")
            for a, b in circulars:
                f.write(f"- `{a}` <-> `{b}`\n")
            f.write("\n")

        # Cross-file call graph
        f.write("## Cross-File Call Graph\n\n")
        f.write("| Caller | -> | Target File | Function |\n|---|---|---|---|\n")
        for src in sorted(cross_calls):
            for fn, tgt in sorted(cross_calls[src], key=lambda x:(x[1],x[0])):
                f.write(f"| {src} | -> | {tgt} | {fn} |\n")

        # Per-file detail
        for d in sorted(data, key=lambda x: -x['lines']):
            f.write(f"\n---\n\n## {d['file']}\n\n")

            f.write(f"| Property | Value |\n|---|---|\n")
            f.write(f"| Lines | {d['lines']} (code: {d['code_lines']}, comments: {d['comment_lines']}) |\n")
            f.write(f"| Functions | {d['function_count']} |\n")
            f.write(f"| Dead functions | {len(d['dead_funcs'])} |\n")
            f.write(f"| External calls | {d['call_count']} |\n")
            f.write(f"| Complexity | {d['complexity']} |\n")
            f.write(f"| Risk | {d['risk']} |\n")
            f.write(f"| Status | **{d['status']}** |\n")
            f.write(f"| Domain | {d['domain']} |\n")
            f.write(f"| SHA | {d['sha']} |\n")
            f.write(f"| Includes | {len(d['includes'])} |\n")
            f.write(f"| Defines | {len(d['defines'])} |\n")
            f.write(f"| Structs | {len(d['structs'])} |\n")
            f.write(f"| Enums | {len(d['enums'])} |\n")
            f.write(f"| Typedefs | {len(d['typedefs'])} |\n")
            f.write(f"| Static arrays | {len(d['static_arrays'])} |\n")
            f.write(f"| #ifdef blocks | {len(d['ifdef_blocks'])} |\n")
            f.write(f"| SQL queries | {len(d['sql_queries'])} |\n")
            f.write(f"| Table refs | {', '.join(d['table_refs']) or '(none)'} |\n")
            f.write(f"| BCL commands | {len(d['bcl_commands'])} |\n")
            f.write(f"| BCL packets | {len(d['bcl_packets'])} |\n")
            f.write(f"| Global vars | {len(d['global_vars'])} |\n")
            f.write(f"| Intra-file cycles | {len(d['intra_cycles'])} |\n")
            f.write(f"| TODOs/FIXMEs | {len(d['todos'])} |\n\n")

            # Headers
            h = d['headers']
            if h['summary']:
                f.write(f"**Summary:** {h['summary']}\n\n")
            if h['class']:
                f.write(f"**Class:** {h['class']}\n\n")
            if h['methods']:
                f.write(f"**Declared methods:** {', '.join(h['methods'])}\n\n")

            # BCL commands
            if d['bcl_commands']:
                f.write("### BCL Commands\n")
                for c in d['bcl_commands']:
                    f.write(f"- `{c}`\n")
                f.write("\n")

            # Functions with full detail
            if d['functions']:
                f.write(f"### Functions ({d['function_count']})\n\n")
                f.write("| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |\n")
                f.write("|---|---|---|---|---|---|---|---|---|\n")
                for fn in d['functions']:
                    vis = "static" if fn['is_static'] else "exported"
                    callers = [src for src, calls in cross_calls.items()
                               if any(c[0]==fn['name'] for c in calls)]
                    call_str = ', '.join(fn['calls_in_body'][:5])
                    if len(fn['calls_in_body'])>5: call_str += f" (+{len(fn['calls_in_body'])-5})"
                    f.write(f"| `{fn['name']}` | {fn['return_type']} | "
                            f"`{fn['params'][:40]}` | {fn['param_count']} | "
                            f"{vis} | {fn['line']} | {fn['body_lines']} | "
                            f"{fn['max_nesting']} | {call_str} |\n")
                f.write("\n")

                # Dead functions
                if d['dead_funcs']:
                    f.write(f"### Dead Functions ({len(d['dead_funcs'])})\n")
                    f.write("Defined but never called in this file:\n\n")
                    for df in d['dead_funcs']:
                        f.write(f"- `{df}`\n")
                    f.write("\n")

            # External calls
            if d['external_calls']:
                f.write(f"### External Calls ({d['call_count']})\n")
                for c in d['external_calls'][:40]:
                    tgt = f"  -> {func_map[c]}" if c in func_map and func_map[c]!=d['file'] else ""
                    f.write(f"- `{c}`{tgt}\n")
                if len(d['external_calls'])>40:
                    f.write(f"- ... ({len(d['external_calls'])-40} more)\n")
                f.write("\n")

            # Includes
            if d['includes']:
                f.write("### Includes\n")
                for i in d['includes']:
                    f.write(f"- `{i}`\n")
                f.write("\n")

            # Defines
            if d['defines']:
                f.write(f"### Defines ({len(d['defines'])})\n")
                for name, val in d['defines'][:25]:
                    if val:
                        f.write(f"- `{name}` = `{val.strip()}`\n")
                    else:
                        f.write(f"- `{name}`\n")
                if len(d['defines'])>25:
                    f.write(f"- ... ({len(d['defines'])-25} more)\n")
                f.write("\n")

            # Structs with fields
            if d['structs']:
                f.write("### Structs\n")
                for s in d['structs']:
                    fields = d['struct_details'].get(s, [])
                    f.write(f"- `struct {s}` ({len(fields)} fields)\n")
                    for fld in fields[:10]:
                        f.write(f"  - `{fld}`\n")
                    if len(fields)>10:
                        f.write(f"  - ... ({len(fields)-10} more)\n")
                f.write("\n")

            # Enums with constants
            if d['enums']:
                f.write("### Enums\n")
                for e in d['enums']:
                    consts = d['enum_details'].get(e, [])
                    f.write(f"- `enum {e}` ({len(consts)} constants)\n")
                    for c in consts[:10]:
                        f.write(f"  - `{c}`\n")
                    if len(consts)>10:
                        f.write(f"  - ... ({len(consts)-10} more)\n")
                f.write("\n")

            # Typedefs
            if d['typedefs']:
                f.write("### Typedefs\n")
                for t in d['typedefs']:
                    f.write(f"- `{t}`\n")
                f.write("\n")

            # Static arrays
            if d['static_arrays']:
                f.write("### Static Arrays\n")
                for a in d['static_arrays']:
                    f.write(f"- `{a}`\n")
                f.write("\n")

            # #ifdef blocks
            if d['ifdef_blocks']:
                f.write("### Conditional Compilation (#ifdef)\n")
                for blk in d['ifdef_blocks']:
                    f.write(f"- `{blk['condition']}` (lines {blk['start_line']}-{blk['end_line']})\n")
                f.write("\n")

            # SQL queries
            if d['sql_queries']:
                f.write(f"### SQL Queries ({len(d['sql_queries'])})\n")
                for q in d['sql_queries'][:15]:
                    short = q[:80] + "..." if len(q)>80 else q
                    f.write(f"- `{short}`\n")
                if len(d['sql_queries'])>15:
                    f.write(f"- ... ({len(d['sql_queries'])-15} more)\n")
                f.write("\n")

            # BCL packet patterns with body extraction
            if d['bcl_packet_bodies']:
                f.write(f"### BCL Packet Patterns ({len(d['bcl_packet_bodies'])})\n")
                for pkt_name, pkt_body in d['bcl_packet_bodies'][:15]:
                    f.write(f"- `[@{pkt_name}]` — `{pkt_body[:60]}`\n")
                if len(d['bcl_packet_bodies'])>15:
                    f.write(f"- ... ({len(d['bcl_packet_bodies'])-15} more)\n")
                f.write("\n")

            # Global variables
            if d['global_vars']:
                f.write(f"### Global Variables ({len(d['global_vars'])})\n")
                for g in d['global_vars'][:20]:
                    f.write(f"- `{g}`\n")
                if len(d['global_vars'])>20:
                    f.write(f"- ... ({len(d['global_vars'])-20} more)\n")
                f.write("\n")

            # Intra-file call graph
            if d['intra_call_graph']:
                f.write(f"### Intra-File Call Graph\n\n")
                f.write("| Caller | Calls |\n|---|---|\n")
                for caller, callees in sorted(d['intra_call_graph'].items()):
                    f.write(f"| `{caller}` | {', '.join(sorted(callees))} |\n")
                f.write("\n")

            # Intra-file cycles
            if d['intra_cycles']:
                f.write(f"### Intra-File Cycles ({len(d['intra_cycles'])})\n")
                for cyc in d['intra_cycles']:
                    f.write(f"- `{' -> '.join(cyc)}`\n")
                f.write("\n")

            # TODOs
            if d['todos']:
                f.write(f"### TODOs / FIXMEs ({len(d['todos'])})\n")
                for t in d['todos']:
                    f.write(f"- {t.strip()}\n")
                f.write("\n")

            # String literals
            if d['strings']:
                f.write("### String Literals (first 30)\n")
                for s in d['strings'][:30]:
                    if len(s) > 80:
                        s = s[:77] + "..."
                    f.write(f"- `{s}`\n")
                f.write("\n")

            # Shell warning
            if d['status'] == 'SHELL':
                f.write("> **SHELL STUB** — only `read_state` and `set_config` implemented.\n\n")

def run():
    results = []
    for root, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if fn.endswith('.c'):
                try:
                    results.append(analyze_file(os.path.join(root, fn)))
                except Exception as e:
                    print(f"ERROR: {fn}: {e}")
    write_report(results)
    print(f"DONE -> {OUT}")
    print(f"Files: {len(results)} | Lines: {sum(d['lines'] for d in results)} | Funcs: {sum(d['function_count'] for d in results)}")
    print(f"Dead: {sum(len(d['dead_funcs']) for d in results)} | TODOs: {sum(len(d['todos']) for d in results)} | SQL: {sum(len(d['sql_queries']) for d in results)}")
    print(f"Globals: {sum(len(d['global_vars']) for d in results)} | BCL pkts: {sum(len(d['bcl_packet_bodies']) for d in results)} | Intra-cycles: {sum(len(d['intra_cycles']) for d in results)}")
    print(f"IMPLEMENTED: {sum(1 for d in results if d['status']=='IMPLEMENTED')} | SHELL: {sum(1 for d in results if d['status']=='SHELL')}")

if __name__ == "__main__":
    run()
