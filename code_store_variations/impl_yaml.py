import re
import json


class DomYaml:
    """YAML domain: load, dump, merge, compare, and inject YAML-like structured data using stdlib only."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "compare": self.compare,
            "dump": self.dump,
            "inject": self.inject,
            "load": self.load,
            "merge": self.merge,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def load(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            data = self._parse_yaml(text)
            result = {"domain": "yaml", "method": "load", "data": {"data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def dump(self, params=None):
        params = params or {}
        try:
            data = params.get("data", {})
            text = self._dump_yaml(data, 0)
            result = {"domain": "yaml", "method": "dump", "data": {"text": text}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DUMP_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            docs = params.get("docs", [])
            if not isinstance(docs, (list, tuple)):
                docs = [docs]
            merged = {}
            for doc in docs:
                if isinstance(doc, str):
                    doc = self._parse_yaml(doc)
                if isinstance(doc, dict):
                    merged = self._deep_merge(merged, doc)
            result = {"domain": "yaml", "method": "merge", "data": {"data": merged}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def compare(self, params=None):
        params = params or {}
        try:
            a = params.get("a", "")
            b = params.get("b", "")
            if isinstance(a, str):
                a = self._parse_yaml(a)
            if isinstance(b, str):
                b = self._parse_yaml(b)
            equal = (a == b)
            diffs = self._diff_keys(a, b, "")
            result = {"domain": "yaml", "method": "compare", "data": {"equal": equal, "diffs": diffs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_ERROR", str(e), 0))

    def inject(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            key = str(params.get("key", ""))
            value = params.get("value", "")
            data = self._parse_yaml(text)
            if key:
                parts = key.split(".")
                cur = data
                for p in parts[:-1]:
                    if not isinstance(cur.get(p), dict):
                        cur[p] = {}
                    cur = cur[p]
                cur[parts[-1]] = value
            out_text = self._dump_yaml(data, 0)
            result = {"domain": "yaml", "method": "inject", "data": {"text": out_text, "key": key}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INJECT_ERROR", str(e), 0))

    def _deep_merge(self, base, overlay):
        out = dict(base) if isinstance(base, dict) else {}
        for k, v in overlay.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = self._deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    def _diff_keys(self, a, b, prefix):
        diffs = []
        if isinstance(a, dict) and isinstance(b, dict):
            keys = set(a.keys()) | set(b.keys())
            for k in keys:
                path = f"{prefix}.{k}" if prefix else k
                if k not in a:
                    diffs.append({"path": path, "status": "added"})
                elif k not in b:
                    diffs.append({"path": path, "status": "removed"})
                elif a[k] != b[k]:
                    if isinstance(a[k], dict) and isinstance(b[k], dict):
                        diffs.extend(self._diff_keys(a[k], b[k], path))
                    else:
                        diffs.append({"path": path, "status": "changed", "old": a[k], "new": b[k]})
        elif a != b:
            diffs.append({"path": prefix, "status": "changed", "old": a, "new": b})
        return diffs

    def _parse_scalar(self, val):
        val = val.strip()
        if val == "":
            return None
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return val[1:-1]
        if val.lower() in ("true", "yes", "on"):
            return True
        if val.lower() in ("false", "no", "off"):
            return False
        if val.lower() in ("null", "~", "none"):
            return None
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                return []
            items = [self._parse_scalar(x.strip()) for x in inner.split(",")]
            return items
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def _parse_yaml(self, text):
        lines = text.split("\n")
        root = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0 and ":" in stripped:
                key, _, rest = stripped.partition(":")
                key = key.strip()
                rest = rest.strip()
                if rest == "":
                    nested, i = self._parse_block(lines, i + 1, 1)
                    root[key] = nested
                else:
                    root[key] = self._parse_scalar(rest)
                    i += 1
            elif indent == 0 and stripped.startswith("- "):
                items, i = self._parse_list(lines, i, 0)
                root = items
            else:
                i += 1
        return root

    def _parse_block(self, lines, start, min_indent):
        result = {}
        i = start
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent < min_indent:
                break
            if ":" in stripped:
                key, _, rest = stripped.partition(":")
                key = key.strip()
                rest = rest.strip()
                if rest == "":
                    nested, i = self._parse_block(lines, i + 1, indent + 1)
                    result[key] = nested
                else:
                    result[key] = self._parse_scalar(rest)
                    i += 1
            else:
                i += 1
        return result, i

    def _parse_list(self, lines, start, min_indent):
        items = []
        i = start
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent < min_indent:
                break
            if stripped.startswith("- "):
                rest = stripped[2:].strip()
                if ":" in rest and rest.split(":")[1].strip() == "":
                    key, _, _ = rest.partition(":")
                    obj = {}
                    nested, i = self._parse_block(lines, i + 1, indent + 1)
                    obj[key.strip()] = nested
                    items.append(obj)
                else:
                    items.append(self._parse_scalar(rest))
                    i += 1
            else:
                i += 1
        return items, i

    def _dump_yaml(self, data, indent):
        pad = "  " * indent
        lines = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    lines.append(f"{pad}{k}:")
                    lines.append(self._dump_yaml(v, indent + 1))
                elif isinstance(v, list):
                    lines.append(f"{pad}{k}:")
                    for item in v:
                        if isinstance(item, (dict, list)):
                            lines.append(f"{pad}-")
                            lines.append(self._dump_yaml(item, indent + 2))
                        else:
                            lines.append(f"{pad}- {self._format_scalar(item)}")
                else:
                    lines.append(f"{pad}{k}: {self._format_scalar(v)}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(f"{pad}-")
                    lines.append(self._dump_yaml(item, indent + 1))
                else:
                    lines.append(f"{pad}- {self._format_scalar(item)}")
        return "\n".join(lines)

    def _format_scalar(self, val):
        if val is None:
            return "null"
        if val is True:
            return "true"
        if val is False:
            return "false"
        if isinstance(val, str):
            if any(c in val for c in ":#{}[]&*!|>'\"%@`"):
                return f'"{val}"'
            return val
        return str(val)
