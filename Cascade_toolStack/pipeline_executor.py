#!/usr/bin/env python3

#[@GHOST]{[@file<pipeline_executor.py>][@domain<Cascade_toolStack>][@role<execution>][@auth<cascade>][@date<2026-06-29>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<execution>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}

"""
Pipeline Execution Engine — Chunk 2.

Executes file manipulation pipelines from the pipeline_graph database.
Implements: real file ops, template routing, loop blocks, constraint validation,
learning loop (success/fail tracking + pruning), and intent-to-pipeline mapping.
"""

import os
import re
import sqlite3
import subprocess
import tempfile
import json
import hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pipeline_graph.db")


class PipelineExecutor:
    """Executes file manipulation pipelines with learning."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "db_path": self.param.get("db_path", DB_PATH),
            "conn": None,
            "dry_run": self.param.get("dry_run", False),
            "verbose": self.param.get("verbose", False),
        }
        self.extracted_buffer = {}

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def open(self, params=None):
        path = self._p(params, "db_path", self.state["db_path"])
        self.state["conn"] = sqlite3.connect(path)
        self.state["conn"].row_factory = sqlite3.Row
        return (1, {"connected": True, "path": path}, None)

    def close(self, params=None):
        if self.state["conn"]:
            self.state["conn"].close()
            self.state["conn"] = None
        return (1, {"closed": True}, None)

    def Run(self, command, params=None):
        if command == "execute":
            return self.execute_pipeline(params)
        if command == "lookup":
            return self.lookup_pipeline(params)
        if command == "learn":
            return self.record_result(params)
        if command == "prune":
            return self.prune_failures(params)
        if command == "stats":
            return self.get_stats(params)
        if command == "classify":
            return self.auto_classify(params)
        if command == "list":
            return self.list_pipelines(params)
        return (0, None, (1, "unknown command", 0))

    def lookup_pipeline(self, params):
        category = self._p(params, "category")
        depth = self._p(params, "depth")
        useful_only = self._p(params, "useful_only", True)
        if not self.state["conn"]:
            self.open()
        cur = self.state["conn"].cursor()
        sql = "SELECT * FROM pipelines WHERE 1=1"
        args = []
        if useful_only:
            sql += " AND useful=1"
        if category:
            sql += " AND category=?"
            args.append(category)
        if depth:
            sql += " AND depth=?"
            args.append(depth)
        sql += " ORDER BY success_count DESC, fail_count ASC LIMIT 10"
        cur.execute(sql, args)
        rows = cur.fetchall()
        results = [dict(r) for r in rows]
        return (1, results, None)

    def execute_pipeline(self, params):
        chain = self._p(params, "chain")
        files = self._p(params, "files", {})
        if not chain:
            return (0, None, (1, "no chain specified", 0))
        if not self.state["conn"]:
            self.open()
        steps = chain.split("->")
        work_dir = self._p(params, "work_dir", tempfile.mkdtemp(prefix="pipeline_"))
        os.makedirs(work_dir, exist_ok=True)
        file_map = {}
        for name, content in files.items():
            fpath = os.path.join(work_dir, name)
            os.makedirs(os.path.dirname(fpath), exist_ok=True) if os.path.dirname(name) else None
            with open(fpath, "w") as f:
                f.write(content)
            file_map[name] = fpath
        results = []
        for i, step in enumerate(steps):
            step_params = self._p(params, f"step{i+1}_params", {})
            step_params.setdefault("work_dir", work_dir)
            step_params.setdefault("file_map", file_map)
            rc, data, err = self.execute_primitive(step, step_params)
            results.append({
                "step": i + 1,
                "primitive": step,
                "rc": rc,
                "data": data,
                "error": err,
            })
            if rc == 0:
                self.record_result({
                    "chain": chain,
                    "success": False,
                    "failed_step": i + 1,
                })
                return (0, results, (2, f"pipeline failed at step {i+1}: {step}", 0))
        verify = self._p(params, "verify", True)
        if verify:
            rc, data, err = self.verify_files(file_map)
            if rc == 0:
                self.record_result({"chain": chain, "success": False, "failed_step": len(steps)})
                return (0, results, (3, "verification failed", 0))
        self.record_result({"chain": chain, "success": True})
        return (1, {"results": results, "work_dir": work_dir, "file_map": file_map}, None)

    def execute_primitive(self, name, params):
        work_dir = self._p(params, "work_dir", ".")
        file_map = self._p(params, "file_map", {})
        if name == "move_lines":
            return self._move_lines(params)
        if name == "copy_lines":
            return self._copy_lines(params)
        if name == "append":
            return self._append(params)
        if name == "insert_at_line":
            return self._insert_at_line(params)
        if name == "insert_after_pat":
            return self._insert_after_pat(params)
        if name == "insert_before_pat":
            return self._insert_before_pat(params)
        if name == "replace_range":
            return self._replace_range(params)
        if name == "delete_lines":
            return self._delete_lines(params)
        if name == "delete_pattern":
            return self._delete_pattern(params)
        if name == "extract_regex":
            return self._extract_regex(params)
        if name == "duplicate_within":
            return self._duplicate_within(params)
        if name == "swap_blocks":
            return self._swap_blocks(params)
        if name == "split_file":
            return self._split_file(params)
        if name == "merge_files":
            return self._merge_files(params)
        if name == "grep_pattern":
            return self._grep_pattern(params)
        return (0, None, (1, f"unknown primitive: {name}", 0))

    def _read_file(self, fpath):
        with open(fpath, "r") as f:
            return f.read()

    def _write_file(self, fpath, content):
        os.makedirs(os.path.dirname(fpath), exist_ok=True) if os.path.dirname(fpath) else None
        with open(fpath, "w") as f:
            f.write(content)

    def _resolve_file(self, name, params):
        file_map = self._p(params, "file_map", {})
        if name in file_map:
            return file_map[name]
        return name

    def _move_lines(self, params):
        src = self._resolve_file(self._p(params, "file"), params)
        tgt = self._resolve_file(self._p(params, "target"), params)
        start = self._p(params, "start", 1)
        end = self._p(params, "end", 1)
        lines = self._read_file(src).splitlines(True)
        extracted = "".join(lines[start-1:end])
        remaining = "".join(lines[:start-1] + lines[end:])
        self._write_file(src, remaining)
        existing = ""
        if os.path.exists(tgt):
            existing = self._read_file(tgt)
            if not existing.endswith("\n"):
                existing += "\n"
        self._write_file(tgt, existing + extracted)
        return (1, {"moved": end - start + 1, "src": src, "tgt": tgt}, None)

    def _copy_lines(self, params):
        src = self._resolve_file(self._p(params, "file"), params)
        tgt = self._resolve_file(self._p(params, "target"), params)
        start = self._p(params, "start", 1)
        end = self._p(params, "end", 1)
        lines = self._read_file(src).splitlines(True)
        extracted = "".join(lines[start-1:end])
        existing = ""
        if os.path.exists(tgt):
            existing = self._read_file(tgt)
            if not existing.endswith("\n"):
                existing += "\n"
        self._write_file(tgt, existing + extracted)
        return (1, {"copied": end - start + 1}, None)

    def _append(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        content = self._p(params, "content", "")
        if content.startswith("__extracted__:"):
            key = content.split(":", 1)[1]
            content = self.extracted_buffer.get(key, "")
        existing = ""
        if os.path.exists(fpath):
            existing = self._read_file(fpath)
            if not existing.endswith("\n"):
                existing += "\n"
        self._write_file(fpath, existing + content)
        return (1, {"appended": len(content)}, None)

    def _insert_at_line(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        line = self._p(params, "line", 1)
        content = self._p(params, "content", "")
        if content.startswith("__extracted__:"):
            key = content.split(":", 1)[1]
            content = self.extracted_buffer.get(key, "")
        lines = self._read_file(fpath).splitlines(True)
        idx = max(0, min(line - 1, len(lines)))
        lines.insert(idx, content + "\n" if not content.endswith("\n") else content)
        self._write_file(fpath, "".join(lines))
        return (1, {"inserted_at": line}, None)

    def _insert_after_pat(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        pattern = self._p(params, "pattern", "")
        content = self._p(params, "content", self._p(params, "insert", ""))
        if content.startswith("__extracted__:"):
            key = content.split(":", 1)[1]
            content = self.extracted_buffer.get(key, "")
        text = self._read_file(fpath)
        idx = text.find(pattern)
        if idx == -1:
            return (0, None, (1, "pattern not found", 0))
        insert_pos = idx + len(pattern)
        result = text[:insert_pos] + content + "\n" + text[insert_pos:]
        self._write_file(fpath, result)
        return (1, {"inserted_after": pattern[:40]}, None)

    def _insert_before_pat(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        pattern = self._p(params, "pattern", "")
        content = self._p(params, "content", "")
        if content.startswith("__extracted__:"):
            key = content.split(":", 1)[1]
            content = self.extracted_buffer.get(key, "")
        text = self._read_file(fpath)
        idx = text.find(pattern)
        if idx == -1:
            return (0, None, (1, "pattern not found", 0))
        result = text[:idx] + content + "\n" + text[idx:]
        self._write_file(fpath, result)
        return (1, {"inserted_before": pattern[:40]}, None)

    def _replace_range(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        start = self._p(params, "start", 1)
        end = self._p(params, "end", 1)
        content = self._p(params, "content", "")
        if content.startswith("__extracted__:"):
            key = content.split(":", 1)[1]
            content = self.extracted_buffer.get(key, "")
        lines = self._read_file(fpath).splitlines(True)
        new_lines = lines[:start-1] + [content + "\n"] + lines[end:]
        self._write_file(fpath, "".join(new_lines))
        return (1, {"replaced": end - start + 1}, None)

    def _delete_lines(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        start = self._p(params, "start", 1)
        end = self._p(params, "end", 1)
        lines = self._read_file(fpath).splitlines(True)
        new_lines = lines[:start-1] + lines[end:]
        self._write_file(fpath, "".join(new_lines))
        return (1, {"deleted": end - start + 1}, None)

    def _delete_pattern(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        pattern = self._p(params, "pattern", "")
        text = self._read_file(fpath)
        count = text.count(pattern)
        text = text.replace(pattern, "")
        self._write_file(fpath, text)
        return (1, {"deleted_occurrences": count}, None)

    def _extract_regex(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        pat1 = self._p(params, "pat1", self._p(params, "pattern", ""))
        pat2 = self._p(params, "pat2", "")
        text = self._read_file(fpath)
        if pat2:
            regex = re.compile(re.escape(pat1) + r".*?" + re.escape(pat2), re.DOTALL)
            matches = regex.findall(text)
            extracted = "\n".join(matches)
            text = regex.sub("", text)
        else:
            matches = re.findall(pat1, text)
            extracted = "\n".join(matches) if matches else pat1
            text = text.replace(pat1, "")
        self._write_file(fpath, text)
        key = hashlib.md5(fpath.encode()).hexdigest()[:8]
        self.extracted_buffer[key] = extracted
        return (1, {"extracted_len": len(extracted), "buffer_key": key}, None)

    def _duplicate_within(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        start = self._p(params, "start", 1)
        end = self._p(params, "end", 1)
        target_line = self._p(params, "target_line", 1)
        lines = self._read_file(fpath).splitlines(True)
        block = lines[start-1:end]
        idx = max(0, min(target_line - 1, len(lines)))
        new_lines = lines[:idx] + block + lines[idx:]
        self._write_file(fpath, "".join(new_lines))
        return (1, {"duplicated": end - start + 1}, None)

    def _swap_blocks(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        s1 = self._p(params, "s1", 1)
        e1 = self._p(params, "e1", 1)
        s2 = self._p(params, "s2", 1)
        e2 = self._p(params, "e2", 1)
        lines = self._read_file(fpath).splitlines(True)
        block1 = lines[s1-1:e1]
        block2 = lines[s2-1:e2]
        if s1 < s2:
            lines = lines[:s1-1] + block2 + lines[e1:s2-1] + block1 + lines[e2:]
        else:
            lines = lines[:s2-1] + block1 + lines[e2:s1-1] + block2 + lines[e1:]
        self._write_file(fpath, "".join(lines))
        return (1, {"swapped": True}, None)

    def _split_file(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        split_line = self._p(params, "split_line", 1)
        lines = self._read_file(fpath).splitlines(True)
        part1 = "".join(lines[:split_line])
        part2 = "".join(lines[split_line:])
        base, ext = os.path.splitext(fpath)
        f1 = base + "_part1" + ext
        f2 = base + "_part2" + ext
        self._write_file(f1, part1)
        self._write_file(f2, part2)
        return (1, {"file1": f1, "file2": f2}, None)

    def _merge_files(self, params):
        f1 = self._resolve_file(self._p(params, "file1"), params)
        f2 = self._resolve_file(self._p(params, "file2"), params)
        content1 = self._read_file(f1) if os.path.exists(f1) else ""
        content2 = self._read_file(f2) if os.path.exists(f2) else ""
        if content1 and not content1.endswith("\n"):
            content1 += "\n"
        merged = content1 + content2
        base, ext = os.path.splitext(f1)
        out = base + "_merged" + ext
        self._write_file(out, merged)
        return (1, {"merged_file": out, "total_lines": merged.count("\n") + 1}, None)

    def _grep_pattern(self, params):
        fpath = self._resolve_file(self._p(params, "file"), params)
        pattern = self._p(params, "pattern", "")
        text = self._read_file(fpath)
        matches = []
        for i, line in enumerate(text.splitlines(), 1):
            if pattern in line:
                matches.append({"line": i, "text": line.strip()})
        return (1, {"matches": matches, "count": len(matches)}, None)

    def verify_files(self, file_map):
        for name, fpath in file_map.items():
            if not os.path.exists(fpath):
                return (0, {"missing": fpath}, (1, "file missing", 0))
            if fpath.endswith(".py"):
                try:
                    result = subprocess.run(
                        ["python3", "-m", "py_compile", fpath],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode != 0:
                        return (0, {"file": fpath, "error": result.stderr}, (2, "compile failed", 0))
                except subprocess.TimeoutExpired:
                    return (0, {"file": fpath}, (3, "compile timeout", 0))
        return (1, {"verified": len(file_map)}, None)

    def record_result(self, params):
        chain = self._p(params, "chain")
        success = self._p(params, "success", True)
        if not chain or not self.state["conn"]:
            return (0, None, (1, "no chain or no db", 0))
        cur = self.state["conn"].cursor()
        if success:
            cur.execute(
                "UPDATE pipelines SET tested=1, success_count=success_count+1 WHERE chain=?",
                (chain,)
            )
        else:
            cur.execute(
                "UPDATE pipelines SET tested=1, fail_count=fail_count+1 WHERE chain=?",
                (chain,)
            )
        self.state["conn"].commit()
        return (1, {"recorded": True, "chain": chain, "success": success}, None)

    def prune_failures(self, params):
        threshold = self._p(params, "threshold", 3)
        if not self.state["conn"]:
            return (0, None, (1, "no db", 0))
        cur = self.state["conn"].cursor()
        cur.execute(
            "UPDATE pipelines SET useful=0 WHERE fail_count >= ? AND useful IS NOT 0",
            (threshold,)
        )
        pruned = cur.rowcount
        self.state["conn"].commit()
        return (1, {"pruned": pruned, "threshold": threshold}, None)

    def get_stats(self, params):
        if not self.state["conn"]:
            self.open()
        cur = self.state["conn"].cursor()
        cur.execute("SELECT depth, COUNT(*) as cnt FROM pipelines GROUP BY depth ORDER BY depth")
        by_depth = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT useful, COUNT(*) as cnt FROM pipelines GROUP BY useful")
        by_useful = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT category, COUNT(*) as cnt FROM pipelines WHERE useful=1 GROUP BY category ORDER BY cnt DESC")
        by_category = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as cnt FROM pipelines WHERE tested=1")
        tested = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM pipelines WHERE success_count > 0")
        proven = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM pipelines WHERE fail_count > 0")
        failed = cur.fetchone()["cnt"]
        return (1, {
            "by_depth": by_depth,
            "by_useful": by_useful,
            "by_category": by_category,
            "tested": tested,
            "proven": proven,
            "failed": failed,
        }, None)

    def auto_classify(self, params):
        if not self.state["conn"]:
            self.open()
        cur = self.state["conn"].cursor()
        rules = [
            ("config_extraction", "extract_regex->append->delete_pattern%"),
            ("config_extraction", "extract_regex->insert_after_pat->delete_pattern%"),
            ("config_extraction", "extract_regex->insert_at_line->delete_pattern%"),
            ("config_extraction", "extract_regex->replace_range->delete_pattern%"),
            ("monolith_split", "split_file->append%"),
            ("monolith_split", "split_file->insert%"),
            ("dedup_merge", "merge_files->delete%"),
            ("dedup_merge", "merge_files->replace_range%"),
            ("reorder", "swap_blocks->insert%"),
            ("reorder", "move_lines->insert%"),
            ("reorder", "move_lines->delete%"),
            ("cleanup", "delete_pattern->delete%"),
            ("cleanup", "delete_lines->delete%"),
            ("duplicate", "duplicate_within->insert%"),
            ("duplicate", "duplicate_within->append%"),
            ("refactor", "extract_regex->append->delete_pattern->insert%"),
            ("refactor", "copy_lines->insert%->delete_pattern%"),
        ]
        tagged = 0
        for category, pattern in rules:
            cur.execute(
                "UPDATE pipelines SET useful=1, category=? WHERE chain LIKE ? AND useful IS NULL",
                (category, pattern)
            )
            tagged += cur.rowcount
        cur.execute("""
            UPDATE pipelines SET useful=0 
            WHERE useful IS NULL 
            AND (chain LIKE '%->split_file->split_file%'
              OR chain LIKE '%->merge_files->merge_files%'
              OR chain LIKE '%->swap_blocks->swap_blocks%'
              OR chain LIKE '%->duplicate_within->duplicate_within%')
        """)
        rejected = cur.rowcount
        self.state["conn"].commit()
        return (1, {"tagged_useful": tagged, "rejected": rejected}, None)

    def list_pipelines(self, params):
        category = self._p(params, "category")
        useful = self._p(params, "useful")
        limit = self._p(params, "limit", 20)
        if not self.state["conn"]:
            self.open()
        cur = self.state["conn"].cursor()
        sql = "SELECT chain, depth, useful, category, success_count, fail_count FROM pipelines WHERE 1=1"
        args = []
        if category:
            sql += " AND category=?"
            args.append(category)
        if useful is not None:
            sql += " AND useful=?"
            args.append(useful)
        sql += " ORDER BY success_count DESC, depth ASC LIMIT ?"
        args.append(limit)
        cur.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        return (1, rows, None)


INTENT_MAP = {
    "move schema": {"category": "config_extraction", "useful_only": True},
    "extract config": {"category": "config_extraction", "useful_only": True},
    "split file": {"category": "monolith_split", "useful_only": True},
    "merge files": {"category": "dedup_merge", "useful_only": True},
    "reorder code": {"category": "reorder", "useful_only": True},
    "cleanup": {"category": "cleanup", "useful_only": True},
    "duplicate block": {"category": "duplicate", "useful_only": True},
    "refactor": {"category": "refactor", "useful_only": True},
}


def route_intent(intent_text):
    intent_lower = intent_text.lower()
    for key, params in INTENT_MAP.items():
        if key in intent_lower:
            return params
    return {"useful_only": True}


if __name__ == "__main__":
    import sys
    exe = PipelineExecutor()
    exe.open()

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: pipeline_executor.py <command> [args]\n")
        sys.stderr.write("Commands: stats, classify, list, lookup, execute, prune\n")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        rc, data, err = exe.get_stats({})
        sys.stdout.write(json.dumps(data, indent=2) + "\n")

    elif cmd == "classify":
        rc, data, err = exe.auto_classify({})
        sys.stdout.write(json.dumps(data, indent=2) + "\n")

    elif cmd == "list":
        category = sys.argv[2] if len(sys.argv) > 2 else None
        rc, data, err = exe.list_pipelines({"category": category, "useful": 1})
        for row in data:
            sys.stdout.write(f"  [{row['depth']}] {row['chain']}  (ok={row['success_count']}, fail={row['fail_count']})\n")

    elif cmd == "lookup":
        intent = " ".join(sys.argv[2:])
        params = route_intent(intent)
        rc, data, err = exe.lookup_pipeline(params)
        for row in data:
            sys.stdout.write(f"  [{row['depth']}] {row['chain']}  cat={row['category']}  ok={row['success_count']}\n")

    elif cmd == "prune":
        rc, data, err = exe.prune_failures({"threshold": 3})
        sys.stdout.write(json.dumps(data, indent=2) + "\n")

    elif cmd == "execute":
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: pipeline_executor.py execute <chain> [--params JSON] <file1=path1> ...\n")
            sys.stderr.write("  --params '{\"step1_params\":{\"file\":\"source.py\",\"pat1\":\"SCHEMA_SQL\",\"pat2\":\"\"}, ...}'\n")
            sys.exit(1)
        chain = sys.argv[2]
        step_params_all = {}
        file_args = []
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--params" and i + 1 < len(sys.argv):
                step_params_all = json.loads(sys.argv[i + 1])
                i += 2
            else:
                file_args.append(sys.argv[i])
                i += 1
        files = {}
        for arg in file_args:
            if "=" in arg:
                name, path = arg.split("=", 1)
                with open(path) as f:
                    files[name] = f.read()
        exec_params = {
            "chain": chain,
            "files": files,
            "verify": True,
        }
        exec_params.update(step_params_all)
        rc, data, err = exe.execute_pipeline(exec_params)
        if rc == 1:
            sys.stdout.write("Pipeline succeeded\n")
            results = data.get("results", []) if isinstance(data, dict) else data
            for step in results:
                sys.stdout.write(f"  Step {step['step']}: {step['primitive']} -> OK\n")
        else:
            sys.stderr.write(f"Pipeline failed: {err}\n")
            results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for step in results:
                status = "OK" if step["rc"] == 1 else "FAIL"
                sys.stderr.write(f"  Step {step['step']}: {step['primitive']} -> {status}\n")
        sys.exit(0 if rc == 1 else 1)

    else:
        sys.stderr.write(f"Unknown command: {cmd}\n")
        exe.close()
        sys.exit(1)

    exe.close()
