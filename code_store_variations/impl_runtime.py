import time


class DomRuntime:
    """Runtime domain: module loading, hooks, dispatch, profiling, and sandboxing using stdlib."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "modules": {}, "hooks": {}, "intercepts": {}, "profile": {}, "sandbox": {}}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "compile": self.compile, "decompile": self.decompile, "dispatch": self.dispatch,
            "eval": self.eval, "hook": self.hook, "intercept": self.intercept,
            "load": self.load, "monitor": self.monitor, "profile": self.profile,
            "sandbox": self.sandbox, "unload": self.unload, "unregister": self.unregister,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def compile(self, params=None):
        params = params or {}
        try:
            source = str(params.get("source", ""))
            name = str(params.get("name", "<runtime>"))
            code = compile(source, name, "exec")
            result = {"domain": "runtime", "method": "compile", "name": name, "compiled": True, "size": len(source)}
            self.state["modules"][name] = {"code": code, "source": source, "loaded": False}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPILE_ERROR", str(e), 0))

    def decompile(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            module = self.state["modules"].get(name)
            source = module["source"] if module else ""
            result = {"domain": "runtime", "method": "decompile", "name": name, "source": source, "found": module is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPILE_ERROR", str(e), 0))

    def dispatch(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            args = params.get("args") or []
            module = self.state["modules"].get(target)
            executed = False
            output = None
            if module is not None and module.get("loaded"):
                ns = module.get("ns", {})
                fn = ns.get("main")
                if callable(fn):
                    output = fn(*args)
                    executed = True
            result = {"domain": "runtime", "method": "dispatch", "target": target, "executed": executed, "output": output}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISPATCH_ERROR", str(e), 0))

    def eval(self, params=None):
        params = params or {}
        try:
            expr = str(params.get("expr", ""))
            ns = params.get("namespace") or {}
            value = eval(expr, {}, dict(ns))
            result = {"domain": "runtime", "method": "eval", "expr": expr, "value": value}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVAL_ERROR", str(e), 0))

    def hook(self, params=None):
        params = params or {}
        try:
            event = str(params.get("event", ""))
            handler = params.get("handler")
            self.state["hooks"].setdefault(event, []).append(handler)
            result = {"domain": "runtime", "method": "hook", "event": event, "handler_count": len(self.state["hooks"][event])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HOOK_ERROR", str(e), 0))

    def intercept(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            interceptor = params.get("interceptor")
            self.state["intercepts"][target] = interceptor
            result = {"domain": "runtime", "method": "intercept", "target": target, "set": True, "total_intercepts": len(self.state["intercepts"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INTERCEPT_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            module = self.state["modules"].get(name)
            loaded = False
            if module is not None and not module.get("loaded"):
                ns = {}
                exec(module["code"], ns)
                module["ns"] = ns
                module["loaded"] = True
                loaded = True
            result = {"domain": "runtime", "method": "load", "name": name, "loaded": loaded, "total_modules": len(self.state["modules"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def monitor(self, params=None):
        params = params or {}
        try:
            loaded = sum(1 for m in self.state["modules"].values() if m.get("loaded"))
            hooks = sum(len(v) for v in self.state["hooks"].values())
            intercepts = len(self.state["intercepts"])
            result = {"domain": "runtime", "method": "monitor", "modules": len(self.state["modules"]), "loaded": loaded, "hooks": hooks, "intercepts": intercepts}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MONITOR_ERROR", str(e), 0))

    def profile(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            start = time.time()
            module = self.state["modules"].get(target)
            elapsed = 0.0
            if module is not None and module.get("loaded"):
                ns = module.get("ns", {})
                fn = ns.get("main")
                if callable(fn):
                    fn()
                    elapsed = time.time() - start
            self.state["profile"][target] = elapsed
            result = {"domain": "runtime", "method": "profile", "target": target, "elapsed": elapsed}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROFILE_ERROR", str(e), 0))

    def sandbox(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            allowed = params.get("allowed") or []
            self.state["sandbox"][name] = {"allowed": allowed, "active": True}
            result = {"domain": "runtime", "method": "sandbox", "name": name, "allowed": allowed, "total_sandboxes": len(self.state["sandbox"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SANDBOX_ERROR", str(e), 0))

    def unload(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            module = self.state["modules"].get(name)
            unloaded = False
            if module is not None:
                module["loaded"] = False
                module.pop("ns", None)
                unloaded = True
            result = {"domain": "runtime", "method": "unload", "name": name, "unloaded": unloaded}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNLOAD_ERROR", str(e), 0))

    def unregister(self, params=None):
        params = params or {}
        try:
            kind = str(params.get("kind", ""))
            key = str(params.get("key", ""))
            removed = False
            if kind == "hook":
                if key in self.state["hooks"]:
                    del self.state["hooks"][key]
                    removed = True
            elif kind == "intercept":
                if key in self.state["intercepts"]:
                    del self.state["intercepts"][key]
                    removed = True
            result = {"domain": "runtime", "method": "unregister", "kind": kind, "key": key, "removed": removed}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNREGISTER_ERROR", str(e), 0))
