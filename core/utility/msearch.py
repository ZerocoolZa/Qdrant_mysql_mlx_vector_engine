# [@GHOST]{[@file<msearch.py>][@domain<utility>][@role<search>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<search_wrapper>][@return<tuple3>][@orch<Orchestrator>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{MSearch wrapper — calls msearch binary for MySQL + Qdrant vector search, parses JSON output}
# [@WCL]{[@self_contained<true>][@wraps<msearch_binary>][@modes<keyword|semantic|hybrid|where|count|qstats>][@output<parsed_json>]}

import os
import json
import subprocess

from . import Config


class MSearch:
    """MSearch wrapper — calls the msearch binary and parses results.

    Wraps the msearch v4 binary for:
    - MySQL keyword search across vb_shared, CODEBASE, all databases
    - Qdrant vector semantic search (BGE auto-embedding)
    - Hybrid search (MySQL + Qdrant combined)
    - Table discovery (--where, --count, --qstats)

    Usage:
        from core.utility.msearch import MSearch
        ms = MSearch()
        code, results, err = ms.Run("search", {"keyword": "ErrorHandler"})
        code, results, err = ms.Run("semantic", {"keyword": "MemUnit lifecycle", "top": 5})
        code, results, err = ms.Run("hybrid", {"keyword": "domain closure", "top": 5})
        code, results, err = ms.Run("where", {"keyword": "new VBStyle rule"})
        code, results, err = ms.Run("count", {"keyword": "Tuple3"})
        code, results, err = ms.Run("qstats")
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_search": "",
            "last_count": 0,
            "history": [],
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["binary"] = os.path.join(
            Config.PROJECT_ROOT, "Cascade_toolStack", "Built_tools", "msearch"
        )

    def Run(self, command, params=None):
        params = params or {}
        if command == "search":
            return self.search(params)
        elif command == "semantic":
            return self.semantic(params)
        elif command == "hybrid":
            return self.hybrid(params)
        elif command == "where":
            return self.where(params)
        elif command == "count":
            return self.count(params)
        elif command == "qstats":
            return self.qstats(params)
        elif command == "all_db":
            return self.all_db(params)
        elif command == "all_mysql":
            return self.all_mysql(params)
        elif command == "vbstyle":
            return self.vbstyle(params)
        elif command == "raw":
            return self.raw(params)
        elif command == "full":
            return self.full(params)
        elif command == "magnetic":
            return self.magnetic(params)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def build_cmd(self, keyword, params):
        cmd = [self.state["binary"]]
        if keyword:
            cmd.append(keyword)
        if params.get("json", True):
            cmd.append("--json")
        if params.get("table"):
            cmd.extend(["--table", params["table"]])
        if params.get("db"):
            cmd.extend(["--db", params["db"]])
        if params.get("limit"):
            cmd.extend(["--limit", str(params["limit"])])
        if params.get("type"):
            cmd.extend(["--type", params["type"]])
        if params.get("context"):
            cmd.extend(["--context", params["context"]])
        if params.get("status"):
            cmd.extend(["--status", params["status"]])
        if params.get("dump"):
            cmd.append("--dump")
        if params.get("deep"):
            cmd.append("--deep")
        if params.get("and"):
            cmd.append("--and")
        if params.get("no_fulltext"):
            cmd.append("--no-fulltext")
        if params.get("mode"):
            cmd.extend(["--mode", params["mode"]])
        if params.get("host"):
            cmd.extend(["--host", params["host"]])
        if params.get("user"):
            cmd.extend(["--user", params["user"]])
        if params.get("pass"):
            cmd.extend(["--pass", params["pass"]])
        if params.get("port"):
            cmd.extend(["--port", str(params["port"])])
        return cmd

    def parse_concatenated_json(self, output):
        tables = []
        decoder = json.JSONDecoder()
        idx = 0
        length = len(output)
        while idx < length:
            while idx < length and output[idx] in " \t\n\r":
                idx += 1
            if idx >= length:
                break
            try:
                obj, end_idx = decoder.raw_decode(output, idx)
                if isinstance(obj, dict):
                    tables.append(obj)
                elif isinstance(obj, list):
                    tables.extend(obj)
                idx = end_idx
            except json.JSONDecodeError:
                idx += 1
        return {"tables": tables, "count": sum(len(t.get("rows", [])) for t in tables)}

    def execute(self, cmd):
        try:
            if not os.path.exists(self.state["binary"]):
                return (0, None, ("binary_not_found", self.state["binary"], 0))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                return (0, None, ("msearch_error", result.stderr.strip()[:200], 0))
            output = result.stdout.strip()
            if not output:
                return (1, {"tables": [], "count": 0}, None)
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                data = self.parse_concatenated_json(output)
            total = 0
            if isinstance(data, list):
                for table in data:
                    if isinstance(table, dict):
                        rows = table.get("rows", [])
                        total += len(rows)
            elif isinstance(data, dict):
                if "tables" not in data:
                    data = {"tables": [data] if data else []}
                for table in data.get("tables", []):
                    if isinstance(table, dict):
                        total += len(table.get("rows", []))
            self.state["last_count"] = total
            self.state["history"].append({
                "cmd": " ".join(cmd[1:]),
                "count": total,
            })
            return (1, data, None)
        except subprocess.TimeoutExpired:
            return (0, None, ("timeout", "msearch took >30s", 0))
        except Exception as e:
            return (0, None, ("exec_error", str(e), 0))

    def search(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        self.state["last_search"] = keyword
        cmd = self.build_cmd(keyword, params)
        return self.execute(cmd)

    def semantic(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = self.build_cmd(keyword, params)
        cmd.append("--semantic")
        if params.get("dimension"):
            cmd.extend(["--dimension", params["dimension"]])
        if params.get("top"):
            cmd.extend(["--top", str(params["top"])])
        if params.get("multi"):
            cmd.append("--multi")
        self.state["last_search"] = keyword + " (semantic)"
        return self.execute(cmd)

    def hybrid(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = self.build_cmd(keyword, params)
        cmd.append("--hybrid")
        if params.get("top"):
            cmd.extend(["--top", str(params["top"])])
        self.state["last_search"] = keyword + " (hybrid)"
        return self.execute(cmd)

    def where(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = [self.state["binary"], "--where", keyword, "--json"]
        self.state["last_search"] = keyword + " (where)"
        return self.execute(cmd)

    def count(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = self.build_cmd(keyword, params)
        cmd.append("--count")
        self.state["last_search"] = keyword + " (count)"
        return self.execute(cmd)

    def qstats(self, params=None):
        cmd = [self.state["binary"], "--qstats", "--json"]
        self.state["last_search"] = "qstats"
        return self.execute(cmd)

    def all_db(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = self.build_cmd(keyword, params)
        cmd.append("--all-db")
        self.state["last_search"] = keyword + " (all-db)"
        return self.execute(cmd)

    def all_mysql(self, params):
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = self.build_cmd(keyword, params)
        cmd.append("--all-mysql")
        self.state["last_search"] = keyword + " (all-mysql)"
        return self.execute(cmd)

    def vbstyle(self, params):
        path = self._p(params, "path", "")
        if not path or not os.path.exists(path):
            return (0, None, ("file_not_found", path or "missing", 0))
        cmd = [self.state["binary"], "--vbstyle", path]
        self.state["last_search"] = "vbstyle:" + os.path.basename(path)
        return self.execute(cmd)

    def full(self, params):
        """Full semantic object search — returns all 12 sections in one query."""
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        cmd = [self.state["binary"], keyword, "--full"]
        if params.get("limit"):
            cmd.extend(["--limit", str(params["limit"])])
        if params.get("mode"):
            cmd.extend(["--mode", params["mode"]])
        self.state["last_search"] = keyword + " (full)"
        return self.execute(cmd)

    def magnetic(self, params):
        """Magnetic radius search — context reconstruction with ±N message radius."""
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword required", 0))
        radius = self._p(params, "radius", 200)
        cmd = [self.state["binary"], keyword, "--magnetic", "--radius", str(radius)]
        if params.get("limit"):
            cmd.extend(["--limit", str(params["limit"])])
        if params.get("mode"):
            cmd.extend(["--mode", params["mode"]])
        if params.get("chat_only"):
            cmd.append("--chat")
        if params.get("graph_only"):
            cmd.append("--graph-radius")
        self.state["last_search"] = keyword + f" (magnetic ±{radius})"
        return self.execute(cmd)

    def raw(self, params):
        args = self._p(params, "args", [])
        if not args or not isinstance(args, list):
            return (0, None, ("missing_param", "args list required", 0))
        cmd = [self.state["binary"]] + args
        self.state["last_search"] = "raw:" + " ".join(args)
        return self.execute(cmd)
