#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_serializer.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL Serializer: serializes IR nodes as BCL blocks"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_serializer.py" domain="BCL" authority="BCLSerializer"}
# [@SUMMARY]{summary="BCL Serializer: file/class/method/edge/inherit/violation/dep/deadcode/cycle/hotpath/metric nodes as BCL blocks."}
# [@CLASS]{class="BCLSerializer" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="serialize_file" type="command"}
# [@METHOD]{method="serialize_class" type="command"}
# [@METHOD]{method="serialize_method" type="command"}
# [@METHOD]{method="serialize_edge" type="command"}
# [@METHOD]{method="serialize_inherit" type="command"}
# [@METHOD]{method="serialize_violation" type="command"}
# [@METHOD]{method="serialize_metric" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib
import os
import datetime


class BCLSerializer:
    """Serialize IR nodes as BCL blocks."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "output": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "serialize_file":
            return self.SerializeFile(params)
        elif command == "serialize_class":
            return self.SerializeClass(params)
        elif command == "serialize_method":
            return self.SerializeMethod(params)
        elif command == "serialize_edge":
            return self.SerializeEdge(params)
        elif command == "serialize_inherit":
            return self.SerializeInherit(params)
        elif command == "serialize_violation":
            return self.SerializeViolation(params)
        elif command == "serialize_metric":
            return self.SerializeMetric(params)
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

    def StableId(self, filepath, prefix, *parts):
        raw = filepath + "|" + prefix + "|" + "|".join(str(p) for p in parts)
        return (1, hashlib.md5(raw.encode()).hexdigest()[:12], None)

    def BclField(self, key, value):
        return (1, "  #[@FIELD]   %s=%s" % (key, value), None)

    def BclNode(self, node_type, node_id, parent_id, fields):
        lines = []
        parent_str = " parent=%s" % parent_id if parent_id else ""
        lines.append("[@IRNODE]  type=%s id=%s%s" % (node_type, node_id, parent_str))
        for k, v in fields:
            field_result = self.BclField(k, v)
            lines.append(field_result[1])
        lines.append("[@ENDNODE]")
        return (1, "\n".join(lines), None)

    def SerializeFile(self, params):
        filepath = self._p(params, "filepath")
        source = self._p(params, "source")
        ff = self._p(params, "features")
        file_id = self._p(params, "file_id")
        if filepath is None or source is None or ff is None or file_id is None:
            return (0, None, ("MISSING_PARAM", "filepath source features file_id required", 0))
        file_hash = hashlib.md5(source.encode()).hexdigest()[:8]
        today = datetime.date.today().isoformat()
        filename = os.path.basename(filepath)
        fields = [
            ("file", filename), ("path", filepath), ("md5", file_hash),
            ("date", today), ("lines", ff.get("line_count", 0)),
            ("imports", ff.get("import_count", 0)),
            ("doc", (ff.get("module_docstring") or "NONE")[:80]),
            ("standalone_funcs", ff.get("standalone_function_count", 0)),
            ("async_funcs", ",".join(ff.get("standalone_async", [])) if ff.get("standalone_async") else "NONE"),
            ("trailing_ws", ff.get("has_trailing_ws", False)),
        ]
        return self.BclNode("file", file_id, None, fields)

    def SerializeClass(self, params):
        filepath = self._p(params, "filepath")
        source = self._p(params, "source")
        cf = self._p(params, "features")
        class_id = self._p(params, "class_id")
        file_id = self._p(params, "file_id")
        violations = self._p(params, "violations", [])
        if filepath is None or cf is None or class_id is None or file_id is None:
            return (0, None, ("MISSING_PARAM", "filepath features class_id file_id required", 0))
        file_hash = hashlib.md5((source or "").encode()).hexdigest()[:8]
        today = datetime.date.today().isoformat()
        docstring = cf.get("docstring") or ""
        summary = docstring.strip().split("\n")[0][:80] if docstring else "Class %s - %d methods" % (cf.get("class_name", "?"), cf.get("method_count", 0))
        cvstr = ";".join(v.get("rule", "") for v in violations) if violations else "NONE"
        fields = [
            ("name", cf.get("class_name", "")), ("doc", summary),
            ("methods", cf.get("method_count", 0)),
            ("method_names", ",".join(cf.get("method_names", [])[:15])),
            ("has_run", cf.get("has_run", False)),
            ("has_init", cf.get("has_init", False)),
            ("has_state", cf.get("has_state", False)),
            ("has_tabs", cf.get("has_tabs", False)),
            ("bases", ",".join(cf.get("bases", [])) if cf.get("bases") else "NONE"),
            ("constants", ",".join(cf.get("class_constants", [])) if cf.get("class_constants") else "NONE"),
            ("nested_classes", ",".join(cf.get("nested_classes", [])) if cf.get("nested_classes") else "NONE"),
            ("body_lines", "%d-%d" % (cf.get("lineno", 0), cf.get("end_lineno", 0))),
            ("complexity_total", cf.get("total_complexity", 0)),
            ("complexity_avg", "%.1f" % (cf.get("total_complexity", 0) / max(cf.get("method_count", 1), 1))),
            ("wmc", cf.get("wmc", 0)), ("rfc", cf.get("rfc", 0)),
            ("lcom", cf.get("lcom", 0)),
            ("patterns", cf.get("patterns", "NONE")),
            ("violations", cvstr),
            ("compliant", len(violations) == 0),
            ("hash", file_hash), ("date", today),
        ]
        return self.BclNode("class", class_id, file_id, fields)

    def SerializeMethod(self, params):
        filepath = self._p(params, "filepath")
        mf = self._p(params, "features")
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        violations = self._p(params, "violations", [])
        if filepath is None or mf is None or method_id is None or class_id is None:
            return (0, None, ("MISSING_PARAM", "filepath features method_id class_id required", 0))
        vstr = ";".join(v.get("rule", "") for v in violations) if violations else "NONE"
        params_str = ",".join(mf.get("params", [])) if mf.get("params") else "NONE"
        calls_str = ",".join(mf.get("calls", [])[:10]) if mf.get("calls") else "NONE"
        self_attrs_str = ",".join(sorted(set(mf.get("self_attrs", [])))) if mf.get("self_attrs") else "NONE"
        decorators_str = ",".join(mf.get("decorator_names", [])) if mf.get("decorator_names") else "NONE"
        strings_str = ",".join(mf.get("string_constants", [])[:5]) if mf.get("string_constants") else "NONE"
        nested_str = ",".join(mf.get("nested_funcs", [])) if mf.get("nested_funcs") else "NONE"
        async_tag = "async:" if mf.get("is_async") else ""
        fields = [
            ("name", "%s%s" % (async_tag, mf.get("name", ""))),
            ("params", params_str),
            ("returns", mf.get("return_count", 0)),
            ("tuple3", mf.get("returns_tuple3", False)),
            ("annotation", mf.get("return_annotation") or "NONE"),
            ("calls", mf.get("call_count", 0)),
            ("call_targets", calls_str),
            ("self_attrs", self_attrs_str),
            ("decorators", "%d:%s" % (mf.get("decorator_count", 0), decorators_str)),
            ("branches", mf.get("branch_count", 0)),
            ("loops", mf.get("loop_count", 0)),
            ("complexity", mf.get("complexity", 0)),
            ("max_nesting", mf.get("max_nesting", 0)),
            ("span", mf.get("line_span", 0)),
            ("hardcoded", mf.get("hardcoded_count", 0)),
            ("strings", strings_str),
            ("nested", nested_str),
            ("violations", vstr),
            ("compliant", len(violations) == 0),
            ("lineno", "%d-%d" % (mf.get("lineno", 0), mf.get("end_lineno", 0))),
        ]
        return self.BclNode("method", method_id, class_id, fields)

    def SerializeEdge(self, params):
        filepath = self._p(params, "filepath")
        caller_class = self._p(params, "caller_class")
        caller_method = self._p(params, "caller_method")
        callee = self._p(params, "callee")
        edge_type = self._p(params, "edge_type")
        caller_method_id = self._p(params, "caller_method_id")
        call_lineno = self._p(params, "call_lineno")
        if filepath is None or callee is None or caller_method_id is None:
            return (0, None, ("MISSING_PARAM", "filepath callee caller_method_id required", 0))
        id_result = self.StableId(filepath, "edge", "%s->%s" % (caller_method, callee), call_lineno)
        fields = [
            ("caller_class", caller_class or "NONE"),
            ("caller_method", caller_method or "NONE"),
            ("callee", callee),
            ("edge_type", edge_type or "CALL"),
            ("call_lineno", call_lineno or 0),
        ]
        return self.BclNode("edge", id_result[1], caller_method_id, fields)

    def SerializeInherit(self, params):
        filepath = self._p(params, "filepath")
        child = self._p(params, "child")
        parent_name = self._p(params, "parent_name")
        if filepath is None or child is None or parent_name is None:
            return (0, None, ("MISSING_PARAM", "filepath child parent_name required", 0))
        id_result = self.StableId(filepath, "inherit", "%s->%s" % (child, parent_name), child)
        fields = [("child", child), ("parent", parent_name)]
        return self.BclNode("inherit", id_result[1], None, fields)

    def SerializeViolation(self, params):
        rule_id = self._p(params, "rule_id")
        scope = self._p(params, "scope")
        parent_id = self._p(params, "parent_id")
        method_name = self._p(params, "method_name")
        severity = self._p(params, "severity")
        description = self._p(params, "description")
        if rule_id is None or parent_id is None:
            return (0, None, ("MISSING_PARAM", "rule_id parent_id required", 0))
        id_result = self.StableId(parent_id, "violate", rule_id, method_name or scope or "")
        fields = [
            ("rule", rule_id), ("scope", scope or "class"),
            ("severity", severity or "high"),
            ("target", method_name or "class"),
            ("description", description or ""),
        ]
        return self.BclNode("violate", id_result[1], parent_id, fields)

    def SerializeMetric(self, params):
        filepath = self._p(params, "filepath")
        key = self._p(params, "key")
        value = self._p(params, "value")
        file_id = self._p(params, "file_id")
        if filepath is None or key is None or file_id is None:
            return (0, None, ("MISSING_PARAM", "filepath key file_id required", 0))
        id_result = self.StableId(filepath, "metric", key, value if isinstance(value, int) else 0)
        fields = [("key", key), ("value", value)]
        return self.BclNode("metric", id_result[1], file_id, fields)
