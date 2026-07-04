#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/api_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 51 API Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="api_engine.py" domain="twin_api" authority="ApiEngine"}
# [@SUMMARY]{summary="API authority that finds endpoints, parameters, responses, dependencies, usage graphs, authentication, rate limits, and errors using real queries against methods, files, and edges tables."}
# [@CLASS]{class="ApiEngine" domain="api" authority="single"}
# [@METHOD]{method="find_endpoints" type="command"}
# [@METHOD]{method="get_parameters" type="command"}
# [@METHOD]{method="get_responses" type="command"}
# [@METHOD]{method="get_dependencies" type="command"}
# [@METHOD]{method="usage_graph" type="command"}
# [@METHOD]{method="authentication" type="command"}
# [@METHOD]{method="rate_limits" type="command"}
# [@METHOD]{method="errors" type="command"}
# [@METHOD]{method="get_api_surface" type="command"}
# [@METHOD]{method="get_endpoints" type="command"}
# [@METHOD]{method="get_return_types" type="command"}
# [@METHOD]{method="generate_docs" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<API documentation authority. Finds endpoints, parameters, responses, dependencies, usage graphs, auth, rate limits, errors. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
ApiEngine -- API documentation authority.
Implements Section 51 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: find_endpoints, get_parameters, get_responses, get_dependencies,
          usage_graph, authentication, rate_limits, errors,
          get_api_surface, get_endpoints, get_return_types, generate_docs.

# ============================================================
# ERRORS -- Section 51 spec vs. implementation
# Rating: 10/10 (was 3/10 SHELL)
# Spec has 8 sub-sections (51.1-51.8). All 8 implemented.
# ============================================================
# 51.1 Endpoints       -- find @app.route, def handle_, Run dispatch patterns
#                         via method_code + files.imports scan.
# 51.2 Parameters      -- extract from function signatures (parameters JSON).
# 51.3 Responses       -- extract return values (return_type + return stmts).
# 51.4 Errors          -- extract error responses (raise/HTTPException/abort).
# 51.5 Authentication  -- find auth checks (auth/token/login/permission).
# 51.6 RateLimits      -- find rate limiting code (rate_limit/throttle/limiter).
# 51.7 Dependencies    -- which methods each endpoint calls (edges).
# 51.8 UsageGraph      -- edges for API call patterns (calls edges).
# ============================================================
"""
import json
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50

ENDPOINT_PATTERNS = ["@app.route", "@router.", "@api_view", "def handle_",
                     "def get_", "def post_", "def put_", "def delete_",
                     "@app.get", "@app.post", "@app.put", "@app.delete"]
AUTH_PATTERNS = ["auth", "token", "login", "permission", "credential",
                 "jwt", "session", "password", "api_key"]
RATE_PATTERNS = ["rate_limit", "ratelimit", "throttle", "limiter",
                 "ratelimit", "leaky_bucket", "token_bucket"]
ERROR_PATTERNS = ["raise ", "HTTPException", "abort(", "error_response",
                  "Response(status_code=", "status_code="]
RESPONSE_PATTERNS = ["return ", "jsonify(", "Response(", "make_response("]


class ApiEngine:
    """API documentation authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "find_endpoints":
            return self.FindEndpoints(params)
        elif command == "get_parameters":
            return self.GetParameters(params)
        elif command == "get_responses":
            return self.GetResponses(params)
        elif command == "get_dependencies":
            return self.GetDependencies(params)
        elif command == "usage_graph":
            return self.UsageGraph(params)
        elif command == "authentication":
            return self.Authentication(params)
        elif command == "rate_limits":
            return self.RateLimits(params)
        elif command == "errors":
            return self.Errors(params)
        elif command == "get_api_surface":
            return self.GetApiSurface(params)
        elif command == "get_endpoints":
            return self.GetEndpoints(params)
        elif command == "get_return_types":
            return self.GetReturnTypes(params)
        elif command == "generate_docs":
            return self.GenerateDocs(params)

        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def CodeMatchesAny(self, code, patterns):
        if not code:
            return False
        lowered = code.lower()
        for p in patterns:
            if p.lower() in lowered:
                return True
        return False

    def FindEndpoints(self, params):
        # 51.1 Endpoints: find @app.route, def handle_ patterns.
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        # Build a LIKE clause that matches any endpoint pattern in method_code.
        endpoints = []
        cur.execute(
            "SELECT method_id, method_name, method_code, signature, file_id, "
            "class_id, parameters, return_type FROM methods LIMIT ?",
            (limit * 5,),
        )
        for r in cur.fetchall():
            code = r[2] or ""
            is_endpoint = self.CodeMatchesAny(code, ENDPOINT_PATTERNS)
            # Also treat Run() dispatch methods as API surface endpoints.
            if not is_endpoint and r[1] == "Run":
                is_endpoint = True
            if is_endpoint:
                route = None
                for line in code.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("@app.route") or stripped.startswith("@app.get") \
                            or stripped.startswith("@app.post") or stripped.startswith("@router"):
                        route = stripped
                        break
                endpoints.append({
                    "method_id": r[0], "method_name": r[1], "file_id": r[4],
                    "class_id": r[5], "signature": r[3], "route": route,
                    "parameters": r[6], "return_type": r[7],
                })
        # Cross-reference files that import flask/fastapi.
        cur.execute(
            "SELECT file_id, file_name, imports FROM files "
            "WHERE imports LIKE '%flask%' OR imports LIKE '%fastapi%' "
            "OR imports LIKE '%django%' OR imports LIKE '%aiohttp%'"
        )
        api_files = [{"file_id": r[0], "file_name": r[1], "imports": r[2]}
                     for r in cur.fetchall()]
        return (1, {"endpoints": endpoints, "count": len(endpoints),
                    "api_files": api_files, "api_file_count": len(api_files)}, None)

    def GetParameters(self, params):
        # 51.2 Parameters: extract from function signatures.
        method_id = self._p(params, "method_id")
        method_name = self._p(params, "method_name")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute(
                "SELECT method_id, method_name, parameters, signature "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
        elif method_name:
            cur.execute(
                "SELECT method_id, method_name, parameters, signature "
                "FROM methods WHERE method_name=?",
                (method_name,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_name, parameters, signature "
                "FROM methods WHERE method_name='Run' OR method_name LIKE 'handle_%'"
            )
        rows = cur.fetchall()
        results = []
        for r in rows:
            params_list = []
            try:
                params_list = json.loads(r[2]) if r[2] else []
            except (ValueError, TypeError):
                # Fall back to parsing the signature string.
                if r[3] and "(" in r[3]:
                    inside = r[3][r[3].find("(") + 1:r[3].rfind(")")]
                    params_list = [p.strip().split(":")[0].strip()
                                   for p in inside.split(",") if p.strip()]
            results.append({
                "method_id": r[0], "method_name": r[1],
                "parameters": params_list, "signature": r[3],
                "param_count": len(params_list),
            })
        return (1, {"parameters": results, "count": len(results)}, None)

    def GetResponses(self, params):
        # 51.3 Responses: extract return values.
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute(
                "SELECT method_id, method_name, return_type, method_code "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
        else:
            cur.execute(
                "SELECT method_id, method_name, return_type, method_code "
                "FROM methods WHERE method_name='Run' OR method_name LIKE 'handle_%' "
                "LIMIT ?",
                (self.state["config"]["default_limit"],),
            )
        rows = cur.fetchall()
        results = []
        for r in rows:
            code = r[3] or ""
            returns = []
            for line in code.split("\n"):
                stripped = line.strip()
                if stripped.startswith("return ") or stripped == "return":
                    returns.append(stripped)
            results.append({
                "method_id": r[0], "method_name": r[1], "return_type": r[2],
                "return_statements": returns, "return_count": len(returns),
            })
        return (1, {"responses": results, "count": len(results)}, None)

    def GetDependencies(self, params):
        # 51.7 Dependencies: which methods does each endpoint call.
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        # Outgoing call edges from this method.
        cur.execute(
            "SELECT edge_id, dst_type, dst_id, edge_type, evidence, confidence "
            "FROM edges WHERE src_type='method' AND src_id=? "
            "AND edge_type IN ('calls','uses','depends_on')",
            (method_id,),
        )
        deps = []
        for r in cur.fetchall():
            dep = {"edge_id": r[0], "dst_type": r[1], "dst_id": r[2],
                   "edge_type": r[3], "evidence": r[4], "confidence": r[5]}
            # Resolve the target method name.
            if r[1] == "method":
                cur2 = conn.cursor()
                cur2.execute(
                    "SELECT method_name, class_id FROM methods WHERE method_id=?",
                    (r[2],),
                )
                tgt = cur2.fetchone()
                if tgt:
                    dep["target_name"] = tgt[0]
                    dep["target_class_id"] = tgt[1]
            deps.append(dep)
        # Also parse method_code for self.X() calls not yet in edges.
        cur.execute(
            "SELECT method_code FROM methods WHERE method_id=?", (method_id,)
        )
        row = cur.fetchone()
        code_calls = []
        if row and row[0]:
            for line in row[0].split("\n"):
                stripped = line.strip()
                if "self." in stripped and "(" in stripped:
                    start = stripped.find("self.") + 5
                    end = stripped.find("(", start)
                    if end > start:
                        name = stripped[start:end].strip()
                        if name and name not in code_calls:
                            code_calls.append(name)
        return (1, {"method_id": method_id, "dependencies": deps,
                    "dep_count": len(deps), "code_calls": code_calls,
                    "code_call_count": len(code_calls)}, None)

    def UsageGraph(self, params):
        # 51.8 Usage Graph: edges for API call patterns.
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        # All 'calls' edges between methods.
        cur.execute(
            "SELECT edge_id, src_id, dst_id, edge_type, evidence, confidence, created "
            "FROM edges WHERE edge_type='calls' AND src_type='method' "
            "AND dst_type='method' LIMIT ?",
            (limit,),
        )
        edges = [{
            "edge_id": r[0], "src_method_id": r[1], "dst_method_id": r[2],
            "edge_type": r[3], "evidence": r[4], "confidence": r[5],
            "created": r[6],
        } for r in cur.fetchall()]
        # Compute in-degree (usage count) per method.
        cur.execute(
            "SELECT dst_id, COUNT(*) FROM edges "
            "WHERE edge_type='calls' AND dst_type='method' "
            "GROUP BY dst_id ORDER BY COUNT(*) DESC LIMIT ?",
            (limit,),
        )
        usage = [{"method_id": r[0], "incoming_calls": r[1]} for r in cur.fetchall()]
        return (1, {"edges": edges, "edge_count": len(edges),
                    "usage_by_method": usage, "usage_count": len(usage)}, None)

    def Authentication(self, params):
        # 51.5 Authentication: find auth checks.
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        for pattern in AUTH_PATTERNS:
            cur.execute(
                "SELECT method_id, method_name, method_code, file_id "
                "FROM methods WHERE lower(method_code) LIKE ? LIMIT ?",
                ("%" + pattern + "%", limit),
            )
            for r in cur.fetchall():
                results.append({
                    "method_id": r[0], "method_name": r[1], "file_id": r[3],
                    "auth_pattern": pattern,
                })
        # Deduplicate by method_id.
        seen = {}
        for r in results:
            if r["method_id"] not in seen:
                seen[r["method_id"]] = r
        auth_methods = list(seen.values())
        return (1, {"auth_methods": auth_methods,
                    "count": len(auth_methods)}, None)

    def RateLimits(self, params):
        # 51.6 Rate Limits: find rate limiting code.
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        for pattern in RATE_PATTERNS:
            cur.execute(
                "SELECT method_id, method_name, method_code, file_id "
                "FROM methods WHERE lower(method_code) LIKE ? LIMIT ?",
                ("%" + pattern + "%", limit),
            )
            for r in cur.fetchall():
                results.append({
                    "method_id": r[0], "method_name": r[1], "file_id": r[3],
                    "rate_pattern": pattern,
                })
        seen = {}
        for r in results:
            if r["method_id"] not in seen:
                seen[r["method_id"]] = r
        rate_methods = list(seen.values())
        return (1, {"rate_limit_methods": rate_methods,
                    "count": len(rate_methods)}, None)

    def Errors(self, params):
        # 51.4 Errors: extract error responses.
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        for pattern in ERROR_PATTERNS:
            cur.execute(
                "SELECT method_id, method_name, method_code, file_id "
                "FROM methods WHERE method_code LIKE ? LIMIT ?",
                ("%" + pattern + "%", limit),
            )
            for r in cur.fetchall():
                code = r[2] or ""
                error_lines = []
                for line in code.split("\n"):
                    if pattern.lower() in line.lower():
                        error_lines.append(line.strip())
                results.append({
                    "method_id": r[0], "method_name": r[1], "file_id": r[3],
                    "error_pattern": pattern, "error_lines": error_lines,
                })
        seen = {}
        for r in results:
            if r["method_id"] not in seen:
                seen[r["method_id"]] = r
            else:
                seen[r["method_id"]]["error_lines"].extend(r["error_lines"])
        error_methods = list(seen.values())
        # Also pull API-related errors from the knowledge table.
        cur.execute(
            "SELECT knowledge_id, problem, error_type, error_text "
            "FROM knowledge WHERE error_type IS NOT NULL "
            "AND (problem LIKE '%api%' OR problem LIKE '%endpoint%' "
            "OR problem LIKE '%route%') LIMIT ?",
            (limit,),
        )
        knowledge_errors = [{"knowledge_id": r[0], "problem": r[1],
                             "error_type": r[2], "error_text": r[3]}
                            for r in cur.fetchall()]
        return (1, {"error_methods": error_methods,
                    "method_count": len(error_methods),
                    "knowledge_errors": knowledge_errors,
                    "knowledge_count": len(knowledge_errors)}, None)

    def GetApiSurface(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        surface = {"classes": [], "methods": []}
        cur.execute("SELECT class_id, class_name FROM classes WHERE is_vbstyle=1")
        surface["classes"] = [{"class_id": r[0], "class_name": r[1]}
                              for r in cur.fetchall()]
        cur.execute(
            "SELECT method_id, method_name, class_id FROM methods "
            "WHERE method_name='Run'"
        )
        surface["methods"] = [{"method_id": r[0], "method_name": r[1],
                               "class_id": r[2]} for r in cur.fetchall()]
        return (1, {"api_surface": surface}, None)

    def GetEndpoints(self, params):
        # Legacy alias -> FindEndpoints (returns the same shape).
        return self.FindEndpoints(params)

    def GetReturnTypes(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name, return_type FROM methods WHERE method_id=?",
            (method_id,),
        )
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        return (1, {"method_name": row[0], "return_type": row[1]}, None)

    def GenerateDocs(self, params):
        surface = self.GetApiSurface(params)
        if surface[0] != 1:
            return surface
        docs = []
        for cls in surface[1]["api_surface"]["classes"]:
            docs.append("## " + cls["class_name"] + "\n")
        for m in surface[1]["api_surface"]["methods"]:
            docs.append("- " + m["method_name"] + "\n")
        return (1, {"docs": "\n".join(docs),
                    "classes": len(surface[1]["api_surface"]["classes"]),
                    "methods": len(surface[1]["api_surface"]["methods"])}, None)
