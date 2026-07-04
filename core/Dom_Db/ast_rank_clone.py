#!/usr/bin/env python3
#[@GHOST]{[@file<ast_rank_clone.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ast_rank_clone>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import ast
import os
import re
import time
import hashlib
import sqlite3
import difflib
from collections import defaultdict, deque


class AstRankClone:
    """AST-based code clone detection using structural fingerprinting.

    Domain: clone detection across Type 1 (exact), Type 2 (renamed),
    and Type 3 (near) clones via normalized AST structural hashing.
    Authority: owns AST normalization, clone grouping, and persistence.
    """

    DEFAULT_SCAN_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
    DEFAULT_DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/db/go_mcp_store.db"
    SKIP_DIRS = (
        ".git", "__pycache__", ".devin", ".windsurf", ".codeium",
        "node_modules", ".tasks", "snapshots", "logs",
    )
    MIN_LINES = 6
    DEFAULT_SIMILARITY = 0.8
    CLONE_TYPE_EXACT = "Type 1"
    CLONE_TYPE_RENAMED = "Type 2"
    CLONE_TYPE_NEAR = "Type 3"
    PYTHON_EXTENSION = ".py"
    MAX_FILES = 10000
    NGRAM_SIZE = 5
    NGRAM_PREFILTER = 0.65
    NORM_CAP = 1500

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "scan_path": self.DEFAULT_SCAN_PATH,
                "db_path": self.DEFAULT_DB_PATH,
                "skip_dirs": list(self.SKIP_DIRS),
                "min_lines": self.MIN_LINES,
                "similarity": self.DEFAULT_SIMILARITY,
                "max_files": self.MAX_FILES,
            },
            "functions": [],
            "clone_groups": [],
            "files_scanned": 0,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "functions_count": len(self.state["functions"]),
            "clone_groups_count": len(self.state["clone_groups"]),
            "files_scanned": self.state["files_scanned"],
        }

    def set_config(self, config):
        if config is None:
            return (0, None, ("CFG_NULL", "config is None", 0))
        for key, value in config.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Run(self, command, params=None):
        dispatch = {
            "scan": self.Scan,
            "detect": self.Detect,
            "compare": self.Compare,
            "report": self.Report,
            "store_sqlite": self.StoreSqlite,
            "read_state": lambda p: (1, self.read_state(), None),
            "set_config": lambda p: self.set_config(p),
            "close": lambda p: self.Close(),
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))
        return handler(params)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def NormalizeType1(self, node):
        """Type 1 normalization: dump AST with all whitespace removed."""
        dumped = ast.dump(node)
        return "".join(dumped.split())

    def NormalizeType2(self, node):
        """Type 2 normalization: replace identifiers with placeholders."""
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                n.id = "VAR"
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n.name = "FUNC"
            elif isinstance(n, ast.arg):
                n.arg = "ARG"
            elif isinstance(n, ast.Attribute):
                n.attr = "ATTR"
        dumped = ast.dump(node)
        return "".join(dumped.split())

    def StructuralHash(self, normalized_string):
        """MD5 hash of a normalized AST string."""
        return hashlib.md5(normalized_string.encode("utf-8")).hexdigest()

    def ExtractFunctions(self, tree, fpath, min_lines):
        """Walk AST and extract all FunctionDef and AsyncFunctionDef nodes."""
        functions = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            line_start = node.lineno
            line_end = self.NodeEndLine(node)
            func_lines = (line_end - line_start) + 1
            if func_lines < min_lines:
                continue
            body_node = self.BuildBodyNode(node)
            type1_norm = self.NormalizeType1(body_node)
            type2_norm = self.NormalizeType2(self.BuildBodyNode(node))
            type1_hash = self.StructuralHash(type1_norm)
            type2_hash = self.StructuralHash(type2_norm)
            functions.append({
                "file": fpath,
                "name": node.name,
                "line_start": line_start,
                "line_end": line_end,
                "lines": func_lines,
                "type1_hash": type1_hash,
                "type2_hash": type2_hash,
                "type1_norm": type1_norm,
                "type2_norm": type2_norm,
            })
        return functions

    def NodeEndLine(self, node):
        end_line = getattr(node, "end_lineno", None)
        if end_line is not None:
            return end_line
        last_line = getattr(node, "lineno", 0)
        for child in ast.walk(node):
            child_line = getattr(child, "lineno", None)
            if child_line is not None and child_line > last_line:
                last_line = child_line
        return last_line

    def BuildBodyNode(self, func_node):
        """Build a synthetic Module node containing only the function body."""
        body = list(func_node.body)
        module = ast.Module(body=body, type_ignores=[])
        return module

    def WalkPyFiles(self, path, skip_dirs, max_files):
        files = []
        count = 0
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in sorted(filenames):
                if not fname.endswith(self.PYTHON_EXTENSION):
                    continue
                files.append(os.path.join(root, fname))
                count += 1
                if count >= max_files:
                    return files
        return files

    def ParseFile(self, fpath):
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))
        try:
            tree = ast.parse(source, filename=fpath)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAIL", "syntax error: " + str(exc), 0))
        except Exception as exc:
            return (0, None, ("PARSE_FAIL", "parse error: " + str(exc), 0))
        return (1, tree, None)

    def GroupClones(self, functions, similarity):
        """Group functions by structural hash and detect clone types."""
        exact_buckets = defaultdict(list)
        renamed_buckets = defaultdict(list)
        for func in functions:
            exact_buckets[func["type1_hash"]].append(func)
            renamed_buckets[func["type2_hash"]].append(func)

        clone_groups = []
        seen_pairs = set()

        for hash_key, group in exact_buckets.items():
            if len(group) < 2:
                continue
            members = []
            for func in group:
                pair_key = (func["file"], func["name"], func["line_start"])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                members.append(func)
            if len(members) < 2:
                continue
            clone_groups.append({
                "clone_type": self.CLONE_TYPE_EXACT,
                "hash": hash_key,
                "members": members,
                "similarity": 1.0,
            })

        for hash_key, group in renamed_buckets.items():
            if len(group) < 2:
                continue
            members = []
            for func in group:
                pair_key = (func["file"], func["name"], func["line_start"])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                members.append(func)
            if len(members) < 2:
                continue
            is_exact = all(m["type1_hash"] == group[0]["type1_hash"] for m in members)
            if is_exact:
                continue
            clone_groups.append({
                "clone_type": self.CLONE_TYPE_RENAMED,
                "hash": hash_key,
                "members": members,
                "similarity": 1.0,
            })

        near_groups = self.DetectNearClones(functions, similarity, seen_pairs)
        clone_groups.extend(near_groups)
        return clone_groups

    def NgramSet(self, text, n=None):
        """Compute character n-gram set for fast similarity pre-filtering."""
        if n is None:
            n = self.NGRAM_SIZE
        if len(text) < n:
            return {text}
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    def NgramJaccard(self, set_a, set_b):
        """Jaccard similarity between two n-gram sets."""
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return inter / union

    def DetectNearClones(self, functions, similarity, seen_pairs):
        """Detect Type 3 near clones via length-sorted blocking + n-gram pre-filter."""
        near_groups = []
        used = set()
        norm_data = []
        for idx, func in enumerate(functions):
            capped = func["type2_norm"][:self.NORM_CAP]
            ngrams = self.NgramSet(capped)
            norm_data.append((idx, capped, len(capped), ngrams))
        total = len(norm_data)
        if total < 2:
            return near_groups
        prefilter = min(self.NGRAM_PREFILTER, similarity)
        order = sorted(range(total), key=lambda i: norm_data[i][2])
        for pos_i in range(total):
            i = order[pos_i]
            if i in used:
                continue
            idx_i, norm_i, len_i, ngrams_i = norm_data[i]
            if len_i == 0:
                continue
            max_len = len_i / similarity
            cluster = [functions[idx_i]]
            for pos_j in range(pos_i + 1, total):
                j = order[pos_j]
                len_j = norm_data[j][2]
                if len_j > max_len:
                    break
                if j in used:
                    continue
                idx_j, norm_j, _, ngrams_j = norm_data[j]
                if len_j == 0:
                    continue
                jacc = self.NgramJaccard(ngrams_i, ngrams_j)
                if jacc < prefilter:
                    continue
                matcher = difflib.SequenceMatcher(None, norm_i, norm_j, autojunk=False)
                quick = matcher.quick_ratio()
                if quick < similarity:
                    continue
                ratio = matcher.ratio()
                if ratio >= similarity:
                    cluster.append(functions[idx_j])
                    used.add(j)
            if len(cluster) >= 2:
                used.add(i)
                best_ratio = 0.0
                for a in range(len(cluster)):
                    for b in range(a + 1, len(cluster)):
                        ma = difflib.SequenceMatcher(
                            None, cluster[a]["type2_norm"][:self.NORM_CAP],
                            cluster[b]["type2_norm"][:self.NORM_CAP], autojunk=False,
                        )
                        r = ma.ratio()
                        if r > best_ratio:
                            best_ratio = r
                near_groups.append({
                    "clone_type": self.CLONE_TYPE_NEAR,
                    "hash": self.StructuralHash(norm_i),
                    "members": cluster,
                    "similarity": best_ratio,
                })
        return near_groups

    def Scan(self, params=None):
        path = self._p(params, "path", self.state["config"].get("scan_path", self.DEFAULT_SCAN_PATH))
        min_lines = self._p(params, "min_lines", self.state["config"].get("min_lines", self.MIN_LINES))
        similarity = self._p(params, "similarity", self.state["config"].get("similarity", self.DEFAULT_SIMILARITY))
        skip_dirs = set(self.state["config"].get("skip_dirs", list(self.SKIP_DIRS)))
        max_files = self._p(params, "max_files", self.state["config"].get("max_files", self.MAX_FILES))

        if not path:
            return (0, None, ("NO_PATH", "path param required", 0))
        if not os.path.isdir(path):
            return (0, None, ("PATH_MISSING", "path not found: " + str(path), 0))

        files = self.WalkPyFiles(path, skip_dirs, max_files)
        all_functions = []
        files_scanned = 0
        for fpath in files:
            ok, tree, err = self.ParseFile(fpath)
            if ok != 1:
                continue
            funcs = self.ExtractFunctions(tree, fpath, min_lines)
            all_functions.extend(funcs)
            files_scanned += 1

        clone_groups = self.GroupClones(all_functions, similarity)
        total_clones = sum(len(g["members"]) for g in clone_groups)

        self.state["functions"] = all_functions
        self.state["clone_groups"] = clone_groups
        self.state["files_scanned"] = files_scanned

        return (1, {
            "functions_scanned": len(all_functions),
            "clone_groups": clone_groups,
            "total_clones": total_clones,
            "files_scanned": files_scanned,
        }, None)

    def Detect(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        min_lines = self._p(params, "min_lines", self.state["config"].get("min_lines", self.MIN_LINES))
        similarity = self._p(params, "similarity", self.state["config"].get("similarity", self.DEFAULT_SIMILARITY))

        ok, tree, err = self.ParseFile(fpath)
        if ok != 1:
            return (0, None, err)
        functions = self.ExtractFunctions(tree, fpath, min_lines)
        clone_groups = self.GroupClones(functions, similarity)
        total_clones = sum(len(g["members"]) for g in clone_groups)

        return (1, {
            "clones": clone_groups,
            "count": total_clones,
            "functions_scanned": len(functions),
        }, None)

    def Compare(self, params=None):
        file1 = self._p(params, "file1")
        file2 = self._p(params, "file2")
        if not file1:
            return (0, None, ("NO_FILE1", "file1 param required", 0))
        if not file2:
            return (0, None, ("NO_FILE2", "file2 param required", 0))
        if not os.path.isfile(file1):
            return (0, None, ("FILE1_MISSING", "file1 not found: " + str(file1), 0))
        if not os.path.isfile(file2):
            return (0, None, ("FILE2_MISSING", "file2 not found: " + str(file2), 0))

        min_lines = self._p(params, "min_lines", self.state["config"].get("min_lines", self.MIN_LINES))
        similarity = self._p(params, "similarity", self.state["config"].get("similarity", self.DEFAULT_SIMILARITY))

        ok1, tree1, err1 = self.ParseFile(file1)
        if ok1 != 1:
            return (0, None, err1)
        ok2, tree2, err2 = self.ParseFile(file2)
        if ok2 != 1:
            return (0, None, err2)

        funcs1 = self.ExtractFunctions(tree1, file1, min_lines)
        funcs2 = self.ExtractFunctions(tree2, file2, min_lines)

        matches = []
        for f1 in funcs1:
            best_match = None
            best_ratio = 0.0
            best_type = self.CLONE_TYPE_NEAR
            for f2 in funcs2:
                if f1["type1_hash"] == f2["type1_hash"]:
                    ratio = 1.0
                    ctype = self.CLONE_TYPE_EXACT
                elif f1["type2_hash"] == f2["type2_hash"]:
                    ratio = 1.0
                    ctype = self.CLONE_TYPE_RENAMED
                else:
                    ratio = difflib.SequenceMatcher(
                        None, f1["type2_norm"], f2["type2_norm"]
                    ).ratio()
                    ctype = self.CLONE_TYPE_NEAR
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = f2
                    best_type = ctype
            if best_match is not None and best_ratio >= similarity:
                matches.append({
                    "clone_type": best_type,
                    "similarity": best_ratio,
                    "file1_func": {
                        "name": f1["name"],
                        "file": f1["file"],
                        "line_start": f1["line_start"],
                        "line_end": f1["line_end"],
                    },
                    "file2_func": {
                        "name": best_match["name"],
                        "file": best_match["file"],
                        "line_start": best_match["line_start"],
                        "line_end": best_match["line_end"],
                    },
                })

        return (1, {"matches": matches, "count": len(matches)}, None)

    def Report(self, params=None):
        clone_groups = self._p(params, "clone_groups")
        if clone_groups is None:
            clone_groups = self.state.get("clone_groups", [])
        if not clone_groups:
            return (1, "Code Clone Detection Report\n===========================\nNo clones detected.\n", None)

        files_scanned = self.state.get("files_scanned", 0)
        functions_scanned = len(self.state.get("functions", []))
        total_instances = sum(len(g["members"]) for g in clone_groups)

        lines = []
        lines.append("Code Clone Detection Report")
        lines.append("===========================")
        lines.append("Files scanned: " + str(files_scanned))
        lines.append("Functions scanned: " + str(functions_scanned))
        lines.append("Clone groups found: " + str(len(clone_groups)))
        lines.append("Total clone instances: " + str(total_instances))
        lines.append("")

        for idx, group in enumerate(clone_groups, start=1):
            ctype = group.get("clone_type", self.CLONE_TYPE_NEAR)
            sim = group.get("similarity", 0.0)
            sim_pct = int(round(sim * 100))
            members = group.get("members", [])
            max_lines = max((m.get("lines", 0) for m in members), default=0)
            saved = max(0, max_lines * (len(members) - 1))
            lines.append("Clone Group " + str(idx) + " (" + ctype + "):")
            for m in members:
                loc = m.get("file", "?") + ":" + str(m.get("line_start", 0)) + "-" + str(m.get("line_end", 0))
                lines.append("  " + m.get("name", "?") + " in " + loc)
            lines.append("  Similarity: " + str(sim_pct) + "%")
            lines.append("  Lines saved if deduplicated: ~" + str(saved))
            lines.append("")

        return (1, "\n".join(lines), None)

    def StoreSqlite(self, params=None):
        db_path = self._p(params, "db_path", self.state["config"].get("db_path", self.DEFAULT_DB_PATH))
        clone_groups = self.state.get("clone_groups", [])
        if not clone_groups:
            return (0, None, ("NO_CLONES", "no clone groups to store; run scan first", 0))

        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.isdir(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as exc:
                return (0, None, ("MKDIR_FAIL", "failed to create db dir: " + str(exc), 0))

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS code_clones ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "hash TEXT, "
                "clone_type TEXT, "
                "file_path TEXT, "
                "func_name TEXT, "
                "line_start INTEGER, "
                "line_end INTEGER, "
                "similarity REAL, "
                "scanned_at TEXT)"
            )
            conn.commit()
        except Exception as exc:
            return (0, None, ("DB_FAIL", "failed to init db: " + str(exc), 0))

        scanned_at = time.strftime("%Y-%m-%d %H:%M:%S")
        stored = 0
        try:
            for group in clone_groups:
                gh = group.get("hash", "")
                ctype = group.get("clone_type", self.CLONE_TYPE_NEAR)
                sim = group.get("similarity", 0.0)
                for m in group.get("members", []):
                    cursor.execute(
                        "INSERT INTO code_clones ("
                        "hash, clone_type, file_path, func_name, "
                        "line_start, line_end, similarity, scanned_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            gh,
                            ctype,
                            m.get("file", ""),
                            m.get("name", ""),
                            m.get("line_start", 0),
                            m.get("line_end", 0),
                            sim,
                            scanned_at,
                        ),
                    )
                    stored += 1
            conn.commit()
            conn.close()
        except Exception as exc:
            try:
                conn.close()
            except Exception:
                pass
            return (0, None, ("INSERT_FAIL", "failed to store clones: " + str(exc), 0))

        return (1, {"stored": stored, "db_path": db_path}, None)
