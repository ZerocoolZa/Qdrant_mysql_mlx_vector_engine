import difflib
import re
import base64
import json


class DomText:
    """Text domain: string manipulation, comparison, encoding, and transformation operations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))
            elif isinstance(param, str):
                self.state["config"]["text"] = param

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "clean": self.clean,
            "compare": self.compare,
            "count": self.count,
            "diff": self.diff,
            "encode": self.encode,
            "format": self.format,
            "join": self.join,
            "read": self.read,
            "replace": self.replace,
            "split": self.split,
            "write": self.write,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def clean(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            actions = params.get("actions", ["strip", "collapse_ws"])
            if not isinstance(actions, (list, tuple)):
                actions = [actions]
            out = text
            for action in actions:
                if action == "strip":
                    out = out.strip()
                elif action == "collapse_ws":
                    out = re.sub(r"\s+", " ", out)
                elif action == "lower":
                    out = out.lower()
                elif action == "upper":
                    out = out.upper()
                elif action == "remove_punct":
                    out = re.sub(r"[^\w\s]", "", out)
                elif action == "remove_digits":
                    out = re.sub(r"\d", "", out)
                elif action == "remove_html":
                    out = re.sub(r"<[^>]+>", "", out)
            result = {"domain": "text", "method": "clean", "data": {"text": out, "length": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAN_ERROR", str(e), 0))

    def compare(self, params=None):
        params = params or {}
        try:
            a = str(params.get("a", ""))
            b = str(params.get("b", ""))
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            equal = (a == b)
            result = {"domain": "text", "method": "compare", "data": {"ratio": ratio, "equal": equal, "len_a": len(a), "len_b": len(b)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_ERROR", str(e), 0))

    def count(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            mode = params.get("mode", "chars")
            if mode == "chars":
                n = len(text)
            elif mode == "words":
                n = len(text.split())
            elif mode == "lines":
                n = text.count("\n") + (1 if text else 0)
            elif mode == "substring":
                n = text.count(str(params.get("substring", "")))
            else:
                n = len(text)
            result = {"domain": "text", "method": "count", "data": {"count": n, "mode": mode}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUNT_ERROR", str(e), 0))

    def diff(self, params=None):
        params = params or {}
        try:
            a = str(params.get("a", ""))
            b = str(params.get("b", ""))
            a_lines = a.splitlines()
            b_lines = b.splitlines()
            differ = difflib.unified_diff(a_lines, b_lines, lineterm="")
            diff_text = "\n".join(differ)
            result = {"domain": "text", "method": "diff", "data": {"diff": diff_text, "has_diff": bool(diff_text)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIFF_ERROR", str(e), 0))

    def encode(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            encoding = params.get("encoding", "base64")
            if encoding == "base64":
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            elif encoding == "hex":
                encoded = text.encode("utf-8").hex()
            elif encoding == "url":
                from urllib.parse import quote
                encoded = quote(text, safe="")
            elif encoding == "rot13":
                encoded = text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm"))
            else:
                encoded = text
            result = {"domain": "text", "method": "encode", "data": {"encoded": encoded, "encoding": encoding}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCODE_ERROR", str(e), 0))

    def format(self, params=None):
        params = params or {}
        try:
            template = str(params.get("template", ""))
            values = params.get("values", {})
            if not isinstance(values, dict):
                values = {}
            out = template
            for key, val in values.items():
                out = out.replace("{" + str(key) + "}", str(val))
            result = {"domain": "text", "method": "format", "data": {"text": out}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORMAT_ERROR", str(e), 0))

    def join(self, params=None):
        params = params or {}
        try:
            parts = params.get("parts", [])
            sep = params.get("separator", " ")
            out = sep.join(str(p) for p in parts)
            result = {"domain": "text", "method": "join", "data": {"text": out, "count": len(parts)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("JOIN_ERROR", str(e), 0))

    def read(self, params=None):
        params = params or {}
        try:
            path = str(params.get("path", ""))
            if not path:
                result = {"domain": "text", "method": "read", "data": {"text": "", "path": path}}
                return (1, result, None)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            result = {"domain": "text", "method": "read", "data": {"text": text, "path": path, "length": len(text)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 0))

    def replace(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            old = str(params.get("old", ""))
            new = str(params.get("new", ""))
            count = params.get("count", -1)
            if count is None or count < 0:
                out = text.replace(old, new)
            else:
                out = text.replace(old, new, int(count))
            result = {"domain": "text", "method": "replace", "data": {"text": out, "replacements": text.count(old) if count < 0 else min(text.count(old), int(count))}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPLACE_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            sep = params.get("separator", " ")
            if sep == "":
                parts = list(text)
            elif isinstance(sep, str):
                parts = text.split(sep)
            else:
                parts = re.split(sep, text)
            result = {"domain": "text", "method": "split", "data": {"parts": parts, "count": len(parts)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))

    def write(self, params=None):
        params = params or {}
        try:
            path = str(params.get("path", ""))
            text = str(params.get("text", ""))
            mode = params.get("mode", "w")
            if not path:
                result = {"domain": "text", "method": "write", "data": {"written": False, "path": path}}
                return (1, result, None)
            with open(path, mode, encoding="utf-8") as f:
                f.write(text)
            result = {"domain": "text", "method": "write", "data": {"written": True, "path": path, "length": len(text)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 0))
