class MemUnit:
    """MemUnit orchestrator — the backbone.
    Connects all Core and Lib through central routing."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": []
        }
        self.memdb = MemDB(mem, db, param)
        self.membus = MemBus(mem, db, param)
        self.executor = Executor(mem, db, param)

    #[@connect_core]{[@params<<params>][@return<Tuple3>][@purpose<connect Core instance to MemUnit>]}
    def connect_core(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            r = self.executor.register_core({"name": name, "instance": instance})
            if r[0]:
                self.membus.subscribe({"pattern": name, "callback": lambda a, p: None})
            return r
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    #[@connect_lib]{[@params<<params>][@return<Tuple3>][@purpose<connect Lib instance to MemUnit>]}
    def connect_lib(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            r = self.executor.register_lib({"name": name, "instance": instance})
            if r[0]:
                self.membus.subscribe({"pattern": name, "callback": lambda a, p: None})
            return r
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    #[@execute]{[@params<<params>][@return<Tuple3>][@purpose<execute action through MemUnit routing>]}
    def execute(self, params):
        try:
            target = params.get("target")
            action = params.get("action")
            action_params = params.get("params", {})

            self.memdb.queue_command({
                "action": action,
                "source": "MemUnit",
                "target": target,
                "params": action_params
            })

            result = self.executor.execute({
                "target": target,
                "action": action,
                "params": action_params
            })

            return result
        except Exception as e:
            return (0, None, ("EXECUTE_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read MemUnit state>]}
    def read_state(self, params=None):
        try:
            if params is None:
                params = {}
            return (1, self.state.copy(), None)
        except Exception as e:
            return (0, None, ("STATE_READ_ERROR", str(e), 0))

    #[@Run]{[@params<<params>][@return<Tuple3>][@purpose<central command dispatch>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        if command == "connect_core":
            return self.connect_core(params)
        elif command == "connect_lib":
            return self.connect_lib(params)
        elif command == "execute":
            return self.execute(params)
        elif command == "read_state":
            return self.read_state(params)
        else:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
