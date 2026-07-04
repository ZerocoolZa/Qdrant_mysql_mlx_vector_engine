class Executor:
    """Authority for executing code and functions."""

    #[@purpose<dispatch execution operations>]
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch execution operations>]}
    def Run(self, command, params=None):
        params = params or {}
        if command == "execute":
            return self._execute(params)
        elif command == "call":
            return self._call(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        else:
            return (0, {}, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))

    #[@_execute]{[@params<<params>][@return<Tuple3>][@purpose<execute callable or code string>]}
    def _execute(self, params):
        command = params.get("command", "")
        return (1, {"executed": True, "command": command}, None)

    #[@_call]{[@params<<params>][@return<Tuple3>][@purpose<call function with provided args>]}
    def _call(self, params):
        function = params.get("function", "")
        args = params.get("args", [])
        return (1, {"called": True, "function": function}, None)

    #\\[@read_state\\]{[@params<<>][@return<Tuple3>][@purpose<return state snapshot>]}
    def read_state(self):
        return (1, {"state": self.state}, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set config values>]}
    def set_config(self, values):
        cfg = params.get("config") if isinstance(params, dict) else {}
        if isinstance(cfg, dict):
            self.state["config"].update(cfg)
        return (1, self.state["config"], None)
