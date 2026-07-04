class DomCu:
    """Compute-unit domain: lifecycle management of registered compute units."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            for k, v in param.items():
                self.state["config"][k] = v

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "benchmark": self.benchmark,
            "create": self.create,
            "destroy": self.destroy,
            "history": self.history,
            "inspect": self.inspect,
            "report": self.report,
            "status": self.status,
            "unregister": self.unregister,
        }
        h = handlers.get(command)
        if h:
            return h(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _find(self, name):
        return next((c for c in self.state["catalog"] if c.get("name") == name), None)

    def benchmark(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            iterations = params.get("iterations", 1)
            if not name:
                return (0, None, ("BENCHMARK_ERROR", "name required", 0))
            unit = self._find(name)
            if unit is None:
                return (0, None, ("BENCHMARK_ERROR", f"unit {name} not found", 0))
            metrics = {"name": name, "iterations": iterations, "avg_ms": 0.0, "max_ms": 0.0}
            self.state["results"].append(metrics)
            result = {"domain": "cu", "method": "benchmark", "metrics": metrics}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BENCHMARK_ERROR", str(e), 0))

    def create(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            kind = params.get("type", "generic")
            config = params.get("config", {})
            if not name:
                return (0, None, ("CREATE_ERROR", "name required", 0))
            if self._find(name) is not None:
                return (0, None, ("CREATE_ERROR", f"unit {name} already exists", 0))
            unit = {"name": name, "type": kind, "config": config, "status": "created"}
            self.state["catalog"].append(unit)
            result = {"domain": "cu", "method": "create", "unit": unit, "created": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def destroy(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("DESTROY_ERROR", "name required", 0))
            before = len(self.state["catalog"])
            self.state["catalog"] = [c for c in self.state["catalog"] if c.get("name") != name]
            destroyed = before != len(self.state["catalog"])
            result = {"domain": "cu", "method": "destroy", "name": name, "destroyed": destroyed}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESTROY_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if name:
                events = [r for r in self.state["results"] if r.get("name") == name]
            else:
                events = list(self.state["results"])
            result = {"domain": "cu", "method": "history", "events": events, "count": len(events)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def inspect(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("INSPECT_ERROR", "name required", 0))
            unit = self._find(name)
            if unit is None:
                return (0, None, ("INSPECT_ERROR", f"unit {name} not found", 0))
            result = {"domain": "cu", "method": "inspect", "unit": unit}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INSPECT_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            summary = {
                "total_units": len(self.state["catalog"]),
                "units": [c.get("name") for c in self.state["catalog"]],
                "events": len(self.state["results"]),
            }
            result = {"domain": "cu", "method": "report", "summary": summary}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def status(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("STATUS_ERROR", "name required", 0))
            unit = self._find(name)
            if unit is None:
                return (0, None, ("STATUS_ERROR", f"unit {name} not found", 0))
            result = {"domain": "cu", "method": "status", "name": name, "status": unit.get("status", "unknown")}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def unregister(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("UNREGISTER_ERROR", "name required", 0))
            unit = self._find(name)
            if unit is None:
                return (0, None, ("UNREGISTER_ERROR", f"unit {name} not found", 0))
            unit["status"] = "unregistered"
            result = {"domain": "cu", "method": "unregister", "name": name, "unregistered": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNREGISTER_ERROR", str(e), 0))
