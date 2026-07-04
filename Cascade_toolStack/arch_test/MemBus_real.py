class MemBus:
    """Message routing bus."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.subscribers = {}

    #[@subscribe]{[@params<<params>][@return<Tuple3>][@purpose<subscribe to action pattern>]}
    def subscribe(self, params):
        try:
            pattern = params.get("pattern")
            callback = params.get("callback")
            if pattern not in self.subscribers:
                self.subscribers[pattern] = []
            self.subscribers[pattern].append(callback)
            return (1, {"pattern": pattern, "subscribers": len(self.subscribers[pattern])}, None)
        except Exception as e:
            return (0, None, ("SUBSCRIBE_ERROR", str(e), 0))

    #[@publish]{[@params<<params>][@return<Tuple3>][@purpose<publish action to bus>]}
    def publish(self, params):
        try:
            action = params.get("action")
            payload = params.get("payload", {})
            delivered = 0
            for pattern, callbacks in self.subscribers.items():
                if action.startswith(pattern) or pattern == "*":
                    for callback in callbacks:
                        callback(action, payload)
                        delivered += 1
            return (1, {"action": action, "delivered": delivered}, None)
        except Exception as e:
            return (0, None, ("PUBLISH_ERROR", str(e), 0))
