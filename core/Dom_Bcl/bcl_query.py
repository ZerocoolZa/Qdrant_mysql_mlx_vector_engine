#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_query.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR Query — query BCL IR blocks by field values"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_query.py" domain="BCL" authority="IRQuery"}
# [@SUMMARY]{summary="BCL IR Query: filters IR blocks by field values. E.g. type=method class=MemUnit"}
# [@CLASS]{class="IRQuery" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="query_ir" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}


class IRQuery:
    """Query BCL IR blocks by field values."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "query_ir":
            return self.QueryIr(params)
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

    def QueryIr(self, params):
        results = self._p(params, "results")
        query_str = self._p(params, "query_str")
        if results is None or query_str is None:
            return (0, None, ("MISSING_PARAM", "results and query_str required", 0))
        filters = {}
        for part in query_str.split():
            if "=" in part:
                k, v = part.split("=", 1)
                filters[k] = v
        matches = []
        for r in results:
            if "error" in r:
                continue
            for block in r.get("bcl", "").split("\n\n"):
                first_line = block.split("\n")[0]
                if "[@IRNODE]" not in first_line:
                    continue
                matched = True
                for k, v in filters.items():
                    pattern = "%s=%s" % (k, v)
                    if pattern not in block:
                        matched = False
                        break
                if matched:
                    matches.append(block)
        self.state["results"] = matches
        return (1, {"matches": matches, "count": len(matches)}, None)
