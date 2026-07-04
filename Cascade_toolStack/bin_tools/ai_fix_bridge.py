#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] ai_fix_bridge.py
#[@SUMMARY] Bridge between cascade_cli error detection and CoreML AST trainer. Receives error text, suggests fix.
#[@CLASS] AiFixBridge
#[@METHOD] Run, lookup_fix, load_rules, suggest
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] cli_ai_fix

import sys
import os
import json
import re
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(SCRIPT_DIR, ".cascade_fix_rules")


def loadTrainer():
    trainerPath = os.path.join(SCRIPT_DIR, "ErrorFixTrainer.py")
    if not os.path.exists(trainerPath):
        return None
    try:
        spec = importlib.util.spec_from_file_location("ErrorFixTrainer", trainerPath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.ErrorFixTrainer()
    except Exception:
        return None

DEFAULT_RULES = [
    {
        "error_name": "ModuleNotFoundError",
        "error_keyword": "modulenotfounderror",
        "fix_description": "Module not installed or wrong name. Try: pip install <module> or check import spelling.",
        "fix_action": "check_import",
        "examples": [
            {"bad": "import nonexistent_xyz", "good": "import os  # use a real module"},
            {"bad": "import nump", "good": "import numpy as np  # typo: nump -> numpy"},
        ],
    },
    {
        "error_name": "ImportError",
        "error_keyword": "cannot import name",
        "fix_description": "Name does not exist in the module. Check the module's exports or API docs.",
        "fix_action": "check_import_name",
        "examples": [
            {"bad": "from os import notarealthing", "good": "from os import path  # check available names"},
        ],
    },
    {
        "error_name": "FileNotFoundError",
        "error_keyword": "no such file or directory",
        "fix_description": "File or directory does not exist. Check path spelling, use absolute paths, or create the file first.",
        "fix_action": "check_path",
        "examples": [
            {"bad": "open('/nonexistent/file.txt')", "good": "open(os.path.expanduser('~/file.txt'))  # use real path"},
            {"bad": "chdir('/nonexistent')", "good": "chdir(os.path.dirname(__file__))  # use known dir"},
        ],
    },
    {
        "error_name": "AttributeError",
        "error_keyword": "has no attribute",
        "fix_description": "Object does not have that attribute. Check the class API or use getattr() with a default.",
        "fix_action": "check_attribute",
        "examples": [
            {"bad": "obj.nonexistent_method()", "good": "getattr(obj, 'method', default_fn)()  # safe access"},
        ],
    },
    {
        "error_name": "KeyError",
        "error_keyword": "keyerror",
        "fix_description": "Key not in dictionary. Use dict.get(key) with a default or check key existence first.",
        "fix_action": "use_get_or_check",
        "examples": [
            {"bad": "value = my_dict['missing_key']", "good": "value = my_dict.get('missing_key', default_value)"},
        ],
    },
    {
        "error_name": "IndexError",
        "error_keyword": "list index out of range",
        "fix_description": "List index too large. Check len() before indexing or use try/except.",
        "fix_action": "check_length",
        "examples": [
            {"bad": "x = my_list[5]", "good": "x = my_list[5] if len(my_list) > 5 else None"},
            {"bad": "print(x[5])  # x=[1,2]", "good": "print(x[min(5, len(x)-1)])  # safe index"},
        ],
    },
    {
        "error_name": "IndentationError",
        "error_keyword": "expected an indented block",
        "fix_description": "Missing indentation after a colon. Add 4 spaces after if/for/while/def/class lines.",
        "fix_action": "fix_indentation",
        "examples": [
            {"bad": "if True:\npass", "good": "if True:\n    pass  # indent 4 spaces"},
        ],
    },
    {
        "error_name": "NameError",
        "error_keyword": "is not defined",
        "fix_description": "Variable or function name not defined. Check spelling, imports, or define before use.",
        "fix_action": "check_name",
        "examples": [
            {"bad": "print(undefined_var)", "good": "undefined_var = None  # define before use\nprint(undefined_var)"},
        ],
    },
    {
        "error_name": "ValueError",
        "error_keyword": "invalid literal for",
        "fix_description": "Cannot convert value to the requested type. Validate input before conversion.",
        "fix_action": "validate_input",
        "examples": [
            {"bad": "int('abc')", "good": "int('abc') if 'abc'.isdigit() else 0  # validate first"},
        ],
    },
    {
        "error_name": "TypeError",
        "error_keyword": "unsupported operand type",
        "fix_description": "Wrong type for operation. Check types with isinstance() or convert before use.",
        "fix_action": "check_type",
        "examples": [
            {"bad": "result = 'hello' + 5", "good": "result = 'hello' + str(5)  # convert type"},
        ],
    },
    {
        "error_name": "SyntaxError",
        "error_keyword": "invalid syntax",
        "fix_description": "Python syntax error. Check for missing colons, parens, quotes, or wrong operators.",
        "fix_action": "fix_syntax",
        "examples": [
            {"bad": "if True\n    pass", "good": "if True:\n    pass  # missing colon"},
            {"bad": "print('hello)", "good": "print('hello')  # missing closing quote"},
        ],
    },
    {
        "error_name": "PermissionError",
        "error_keyword": "permission denied",
        "fix_description": "No permission for the operation. Check file permissions or use sudo (with caution).",
        "fix_action": "check_permissions",
        "examples": [
            {"bad": "open('/etc/passwd', 'w')", "good": "open('/tmp/myfile', 'w')  # use writable location"},
        ],
    },
    {
        "error_name": "ConnectionError",
        "error_keyword": "connection refused",
        "fix_description": "Cannot connect to service. Check if the service is running and the port is correct.",
        "fix_action": "check_connection",
        "examples": [
            {"bad": "connect('localhost:9999')", "good": "connect('localhost:8080')  # check port"},
        ],
    },
    {
        "error_name": "RecursionError",
        "error_keyword": "maximum recursion depth",
        "fix_description": "Infinite recursion. Add a base case or increase recursion limit with care.",
        "fix_action": "add_base_case",
        "examples": [
            {"bad": "def fib(n): return fib(n-1)+fib(n-2)", "good": "def fib(n):\n    if n < 2: return n\n    return fib(n-1)+fib(n-2)  # base case"},
        ],
    },
    {
        "error_name": "UnicodeDecodeError",
        "error_keyword": "codec can't decode",
        "fix_description": "Encoding mismatch. Specify encoding explicitly when opening files.",
        "fix_action": "specify_encoding",
        "examples": [
            {"bad": "open('file.txt').read()", "good": "open('file.txt', encoding='utf-8').read()"},
        ],
    },
]


class AiFixBridge:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "rules": [],
            "rules_file": RULES_FILE,
        }
        self.loadRules()

    def Run(self, command, params=None):
        params = params or {}
        if command == "suggest":
            return self.cmdSuggest(params)
        if command == "list_rules":
            return self.cmdListRules(params)
        if command == "add_rule":
            return self.cmdAddRule(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def loadRules(self):
        if os.path.exists(self.state["rules_file"]):
            try:
                with open(self.state["rules_file"], "r") as f:
                    self.state["rules"] = json.load(f)
                return
            except Exception:
                pass
        self.state["rules"] = DEFAULT_RULES
        self.saveRules()

    def saveRules(self):
        try:
            with open(self.state["rules_file"], "w") as f:
                json.dump(self.state["rules"], f, indent=2)
        except Exception:
            pass

    def lookupFix(self, error_text):
        error_lower = error_text.lower()
        best_match = None
        best_score = 0
        for rule in self.state["rules"]:
            keyword = rule.get("error_keyword", "").lower()
            if keyword and keyword in error_lower:
                score = len(keyword)
                if score > best_score:
                    best_score = score
                    best_match = rule
        return best_match

    def lookupFixByAction(self, action):
        for rule in self.state["rules"]:
            if rule.get("fix_action") == action:
                return rule
        return None

    def cmdSuggest(self, params):
        error_text = self.p(params, "error_text", "")
        if not error_text:
            return (0, None, ("NO_ERROR_TEXT", "error_text parameter required", 0))

        trainer = loadTrainer()
        if trainer is not None:
            ok, data, err = trainer.Run("infer", {"error_text": error_text})
            if ok and data and data.get("found"):
                action = data.get("fix_action", "")
                confidence = data.get("confidence", 0.0)
                rule = self.lookupFixByAction(action)
                if rule is not None:
                    result = {
                        "found": True,
                        "error_name": rule.get("error_name", ""),
                        "fix_description": rule.get("fix_description", ""),
                        "fix_action": action,
                        "confidence": confidence,
                        "source": "model",
                        "examples": rule.get("examples", []),
                    }
                    return (1, result, None)

        rule = self.lookupFix(error_text)
        if rule is None:
            return (1, {"found": False, "message": "No fix rule matches this error."}, None)
        result = {
            "found": True,
            "error_name": rule.get("error_name", ""),
            "fix_description": rule.get("fix_description", ""),
            "fix_action": rule.get("fix_action", ""),
            "source": "keyword",
            "examples": rule.get("examples", []),
        }
        return (1, result, None)

    def cmdListRules(self, params):
        rules = []
        for rule in self.state["rules"]:
            rules.append({
                "error_name": rule.get("error_name", ""),
                "fix_action": rule.get("fix_action", ""),
                "fix_description": rule.get("fix_description", ""),
            })
        return (1, rules, None)

    def cmdAddRule(self, params):
        error_name = self.p(params, "error_name", "")
        error_keyword = self.p(params, "error_keyword", "")
        fix_description = self.p(params, "fix_description", "")
        fix_action = self.p(params, "fix_action", "")
        if not error_name or not error_keyword:
            return (0, None, ("MISSING_PARAMS", "error_name and error_keyword required", 0))
        rule = {
            "error_name": error_name,
            "error_keyword": error_keyword,
            "fix_description": fix_description,
            "fix_action": fix_action,
            "examples": [],
        }
        self.state["rules"].append(rule)
        self.saveRules()
        return (1, {"added": error_name}, None)

    def readState(self, params=None):
        return (1, dict(self.state), None)

    def setConfig(self, params=None):
        if not isinstance(params, dict):
            return (0, None, ("NO_PARAMS", "config dict required", 0))
        for key, value in params.items():
            self.state[key] = value
        return (1, {"updated": list(params.keys())}, None)


if __name__ == "__main__":
    bridge = AiFixBridge()
    if len(sys.argv) < 2:
        print("Usage: ai_fix_bridge.py <error_text>")
        print("       ai_fix_bridge.py --file <path>")
        print("       ai_fix_bridge.py --list-rules")
        print("       ai_fix_bridge.py --add-rule <error_name> <error_keyword> <fix_description>")
        sys.exit(1)
    if sys.argv[1] == "--list-rules":
        ok, data, err = bridge.Run("list_rules")
        if ok:
            for r in data:
                print("  %s -> %s" % (r["error_name"], r["fix_action"]))
                print("    %s" % r["fix_description"])
        sys.exit(0)
    if sys.argv[1] == "--add-rule":
        if len(sys.argv) < 5:
            print("Usage: ai_fix_bridge.py --add-rule <error_name> <error_keyword> <fix_description>")
            sys.exit(1)
        ok, data, err = bridge.Run("add_rule", {
            "error_name": sys.argv[2],
            "error_keyword": sys.argv[3],
            "fix_description": sys.argv[4],
            "fix_action": "custom",
        })
        if ok:
            print("[OK] Fix rule added: %s" % data.get("added", ""))
            sys.exit(0)
        else:
            print("[FAIL] Could not add rule")
            sys.exit(1)
    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Usage: ai_fix_bridge.py --file <path>")
            sys.exit(1)
        try:
            with open(sys.argv[2], "r") as f:
                error_text = f.read()
        except Exception as e:
            print("NO_SUGGESTION: cannot read file: %s" % str(e))
            sys.exit(1)
    else:
        error_text = " ".join(sys.argv[1:])
    ok, data, err = bridge.Run("suggest", {"error_text": error_text})
    if ok and data and data.get("found"):
        source = data.get("source", "keyword")
        confidence = data.get("confidence", 0.0)
        print("SUGGESTION:")
        print("  Error: %s" % data.get("error_name", ""))
        print("  Fix:   %s" % data.get("fix_description", ""))
        print("  Action: %s" % data.get("fix_action", ""))
        if source == "model":
            print("  Confidence: %.1f%% (neural model)" % (confidence * 100))
        else:
            print("  Source: keyword lookup")
        examples = data.get("examples", [])
        if examples:
            print("  Examples:")
            for ex in examples:
                print("    BAD:  %s" % ex.get("bad", ""))
                print("    GOOD: %s" % ex.get("good", ""))
        sys.exit(0)
    else:
        print("NO_SUGGESTION: %s" % (data.get("message") if data else "unknown"))
        sys.exit(1)
