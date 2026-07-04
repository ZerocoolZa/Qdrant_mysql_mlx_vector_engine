import copy


class DomFactory:
    """Object factory registry: create, clone, configure, dispose, prototype, unregister, report."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._registry = {}
        self._prototypes = {}
        self._instances = {}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "clone": self.clone,
            "configure": self.configure,
            "create": self.create,
            "dispose": self.dispose,
            "prototype": self.prototype,
            "report": self.report,
            "unregister": self.unregister,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def create(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            spec = params.get("spec", {})
            if name is None:
                return (0, None, ("CREATE_ERROR", "missing name", 0))
            if name in self._prototypes:
                obj = copy.deepcopy(self._prototypes[name])
                if isinstance(spec, dict):
                    if isinstance(obj, dict):
                        obj.update(spec)
            else:
                obj = dict(spec) if isinstance(spec, dict) else spec
            instance_id = f"{name}_{len(self._instances)}"
            self._instances[instance_id] = {"name": name, "spec": spec, "instance": obj}
            result = {"domain": "factory", "method": "create", "data": {"instance_id": instance_id, "name": name, "created": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def clone(self, params=None):
        params = params or {}
        try:
            instance_id = params.get("instance_id")
            if instance_id not in self._instances:
                return (0, None, ("CLONE_ERROR", "instance not found", 0))
            original = self._instances[instance_id]
            cloned = copy.deepcopy(original["instance"])
            new_id = f"{original['name']}_clone_{len(self._instances)}"
            self._instances[new_id] = {"name": original["name"], "spec": original["spec"], "instance": cloned}
            result = {"domain": "factory", "method": "clone", "data": {"instance_id": new_id, "source": instance_id, "cloned": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLONE_ERROR", str(e), 0))

    def configure(self, params=None):
        params = params or {}
        try:
            instance_id = params.get("instance_id")
            config = params.get("config", {})
            if instance_id not in self._instances:
                return (0, None, ("CONFIGURE_ERROR", "instance not found", 0))
            inst = self._instances[instance_id]["instance"]
            if isinstance(inst, dict):
                inst.update(config)
            result = {"domain": "factory", "method": "configure", "data": {"instance_id": instance_id, "configured": True, "config": config}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONFIGURE_ERROR", str(e), 0))

    def dispose(self, params=None):
        params = params or {}
        try:
            instance_id = params.get("instance_id")
            if instance_id in self._instances:
                del self._instances[instance_id]
                result = {"domain": "factory", "method": "dispose", "data": {"instance_id": instance_id, "disposed": True}}
                return (1, result, None)
            return (0, None, ("DISPOSE_ERROR", "instance not found", 0))
        except Exception as e:
            return (0, None, ("DISPOSE_ERROR", str(e), 0))

    def prototype(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            template = params.get("template", {})
            if name is None:
                return (0, None, ("PROTOTYPE_ERROR", "missing name", 0))
            self._prototypes[name] = copy.deepcopy(template)
            self._registry[name] = {"type": "prototype", "created_count": 0}
            result = {"domain": "factory", "method": "prototype", "data": {"name": name, "registered": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROTOTYPE_ERROR", str(e), 0))

    def unregister(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            removed_proto = name in self._prototypes
            removed_reg = name in self._registry
            self._prototypes.pop(name, None)
            self._registry.pop(name, None)
            result = {"domain": "factory", "method": "unregister", "data": {"name": name, "removed_prototype": removed_proto, "removed_registry": removed_reg}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNREGISTER_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            result = {"domain": "factory", "method": "report", "data": {
                "prototypes": list(self._prototypes.keys()),
                "registry": dict(self._registry),
                "instances": list(self._instances.keys()),
                "instance_count": len(self._instances),
                "prototype_count": len(self._prototypes),
            }}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
