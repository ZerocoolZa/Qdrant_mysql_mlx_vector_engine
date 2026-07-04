"""VBStyle domain implementation: serialization.

Object<->format: JSON, protobuf, CBOR, Avro, schema validation.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import json
import base64
import re


class DomSerialization:
    """Object<->format: JSON, protobuf, CBOR, Avro, schema validation."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._serializers = {}
        self._types = {}
        self._formats = {
            "json": {"mime": "application/json", "binary": False, "schema": True},
            "jsonb": {"mime": "application/json", "binary": False, "schema": True},
            "base64": {"mime": "application/octet-stream", "binary": True, "schema": False},
            "csv": {"mime": "text/csv", "binary": False, "schema": False},
            "tsv": {"mime": "text/tab-separated-values", "binary": False, "schema": False},
        }

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "serialize": self.serialize,
            "deserialize": self.deserialize,
            "validate_schema": self.validate_schema,
            "register_serializer": self.register_serializer,
            "get_format_info": self.get_format_info,
            "convert_format": self.convert_format,
            "register_type": self.register_type,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def serialize(self, params=None):
        params = params or {}
        try:
            data = params.get("data")
            fmt = params.get("format", "json")
            if fmt == "json":
                output = json.dumps(data, sort_keys=True)
            elif fmt == "base64":
                raw = json.dumps(data).encode("utf-8")
                output = base64.b64encode(raw).decode("ascii")
            elif fmt == "csv":
                if not isinstance(data, list) or not data:
                    output = ""
                else:
                    if isinstance(data[0], dict):
                        keys = list(data[0].keys())
                        lines = [",".join(keys)]
                        for row in data:
                            lines.append(",".join(str(row.get(k, "")) for k in keys))
                        output = "\n".join(lines)
                    else:
                        output = "\n".join(",".join(str(c) for c in row) for row in data)
            elif fmt == "tsv":
                if not isinstance(data, list) or not data:
                    output = ""
                else:
                    if isinstance(data[0], dict):
                        keys = list(data[0].keys())
                        lines = ["\t".join(keys)]
                        for row in data:
                            lines.append("\t".join(str(row.get(k, "")) for k in keys))
                        output = "\n".join(lines)
                    else:
                        output = "\n".join("\t".join(str(c) for c in row) for row in data)
            elif fmt in self._serializers:
                output = self._serializers[fmt](data)
            else:
                return (0, None, ("SERIALIZE_ERROR", f"unsupported format: {fmt}", 0))
            result = {"domain": "serialization", "method": "serialize", "data": {"format": fmt, "output": output, "size": len(str(output))}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SERIALIZE_ERROR", str(e), 0))

    def deserialize(self, params=None):
        params = params or {}
        try:
            payload = params.get("payload")
            fmt = params.get("format", "json")
            if payload is None:
                return (0, None, ("DESERIALIZE_ERROR", "missing payload", 0))
            if fmt == "json":
                data = json.loads(payload)
            elif fmt == "base64":
                raw = base64.b64decode(payload)
                data = json.loads(raw.decode("utf-8"))
            elif fmt == "csv":
                lines = payload.strip().split("\n")
                if not lines:
                    data = []
                else:
                    header = lines[0].split(",")
                    data = [dict(zip(header, line.split(","))) for line in lines[1:] if line]
            elif fmt == "tsv":
                lines = payload.strip().split("\n")
                if not lines:
                    data = []
                else:
                    header = lines[0].split("\t")
                    data = [dict(zip(header, line.split("\t"))) for line in lines[1:] if line]
            else:
                return (0, None, ("DESERIALIZE_ERROR", f"unsupported format: {fmt}", 0))
            result = {"domain": "serialization", "method": "deserialize", "data": {"format": fmt, "data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESERIALIZE_ERROR", str(e), 0))

    def validate_schema(self, params=None):
        params = params or {}
        try:
            data = params.get("data")
            schema = params.get("schema")
            if schema is None:
                return (0, None, ("VALIDATE_SCHEMA_ERROR", "missing schema", 0))
            errors = []
            schema_type = schema.get("type")
            if schema_type == "object":
                if not isinstance(data, dict):
                    errors.append("expected object")
                else:
                    required = schema.get("required", [])
                    for req in required:
                        if req not in data:
                            errors.append(f"missing required: {req}")
                    properties = schema.get("properties", {})
                    for k, v in data.items():
                        if k in properties:
                            expected_type = properties[k].get("type")
                            type_map = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "array": list, "object": dict}
                            py_type = type_map.get(expected_type)
                            if py_type and not isinstance(v, py_type):
                                errors.append(f"{k}: expected {expected_type}")
            elif schema_type == "array":
                if not isinstance(data, list):
                    errors.append("expected array")
            elif schema_type:
                type_map = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "array": list, "object": dict}
                py_type = type_map.get(schema_type)
                if py_type and not isinstance(data, py_type):
                    errors.append(f"expected {schema_type}")
            valid = len(errors) == 0
            result = {"domain": "serialization", "method": "validate_schema", "data": {"valid": valid, "errors": errors}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VALIDATE_SCHEMA_ERROR", str(e), 0))

    def register_serializer(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("REGISTER_SERIALIZER_ERROR", "missing name", 0))
            mime = params.get("mime", "application/octet-stream")
            binary = bool(params.get("binary", False))
            self._formats[name] = {"mime": mime, "binary": binary, "schema": False}
            result = {"domain": "serialization", "method": "register_serializer", "data": {"name": name, "mime": mime, "binary": binary}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REGISTER_SERIALIZER_ERROR", str(e), 0))

    def get_format_info(self, params=None):
        params = params or {}
        try:
            fmt = params.get("format")
            if fmt is None:
                result = {"domain": "serialization", "method": "get_format_info", "data": {"formats": dict(self._formats)}}
            elif fmt in self._formats:
                result = {"domain": "serialization", "method": "get_format_info", "data": {"format": fmt, "info": self._formats[fmt]}}
            else:
                return (0, None, ("GET_FORMAT_INFO_ERROR", f"unknown format: {fmt}", 0))
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_FORMAT_INFO_ERROR", str(e), 0))

    def convert_format(self, params=None):
        params = params or {}
        try:
            payload = params.get("payload")
            from_fmt = params.get("from_format", "json")
            to_fmt = params.get("to_format", "json")
            if payload is None:
                return (0, None, ("CONVERT_FORMAT_ERROR", "missing payload", 0))
            deser = self.deserialize({"payload": payload, "format": from_fmt})
            if deser[0] != 1:
                return deser
            data = deser[1]["data"]["data"]
            ser = self.serialize({"data": data, "format": to_fmt})
            if ser[0] != 1:
                return ser
            output = ser[1]["data"]["output"]
            result = {"domain": "serialization", "method": "convert_format", "data": {"from": from_fmt, "to": to_fmt, "output": output}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONVERT_FORMAT_ERROR", str(e), 0))

    def register_type(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("REGISTER_TYPE_ERROR", "missing name", 0))
            type_info = params.get("type_info") or {}
            self._types[name] = type_info
            result = {"domain": "serialization", "method": "register_type", "data": {"name": name, "type_info": type_info, "registered": len(self._types)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REGISTER_TYPE_ERROR", str(e), 0))
