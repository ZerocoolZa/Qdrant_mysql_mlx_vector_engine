import time
import uuid


class DomMessaging:
    """Messaging domain: in-memory queues, topics, broadcast, and retry handling using stdlib."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "queues": {}, "topics": {}, "deadletters": [], "acks": {}, "nacks": {}}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "ack": self.ack, "broadcast": self.broadcast, "channel": self.channel,
            "deadletter": self.deadletter, "delay": self.delay, "nack": self.nack,
            "priority": self.priority, "queue": self.queue, "receive": self.receive,
            "retry": self.retry, "send": self.send, "topic": self.topic, "unsubscribe": self.unsubscribe,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _new_id(self):
        return uuid.uuid4().hex

    def ack(self, params=None):
        params = params or {}
        try:
            msg_id = str(params.get("message_id", ""))
            self.state["acks"][msg_id] = {"status": "acked", "ts": time.time()}
            result = {"domain": "messaging", "method": "ack", "message_id": msg_id, "acked": True, "total_acks": len(self.state["acks"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ACK_ERROR", str(e), 0))

    def broadcast(self, params=None):
        params = params or {}
        try:
            payload = params.get("payload")
            subscribers = params.get("subscribers") or []
            delivered = 0
            for sub in subscribers:
                self.state["results"].append({"subscriber": sub, "payload": payload})
                delivered += 1
            result = {"domain": "messaging", "method": "broadcast", "payload": payload, "delivered": delivered, "subscribers": len(subscribers)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BROADCAST_ERROR", str(e), 0))

    def channel(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            mode = params.get("mode", "pubsub")
            self.state["queues"].setdefault(name, {"type": "channel", "mode": mode, "messages": []})
            result = {"domain": "messaging", "method": "channel", "name": name, "mode": mode, "total_channels": len(self.state["queues"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHANNEL_ERROR", str(e), 0))

    def deadletter(self, params=None):
        params = params or {}
        try:
            msg_id = str(params.get("message_id", ""))
            reason = str(params.get("reason", "max_retries"))
            entry = {"message_id": msg_id, "reason": reason, "ts": time.time()}
            self.state["deadletters"].append(entry)
            result = {"domain": "messaging", "method": "deadletter", "entry": entry, "total_deadletters": len(self.state["deadletters"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEADLETTER_ERROR", str(e), 0))

    def delay(self, params=None):
        params = params or {}
        try:
            msg_id = str(params.get("message_id", ""))
            delay_ms = int(params.get("delay_ms", 0))
            deliver_at = time.time() + (delay_ms / 1000.0)
            result = {"domain": "messaging", "method": "delay", "message_id": msg_id, "delay_ms": delay_ms, "deliver_at": deliver_at}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELAY_ERROR", str(e), 0))

    def nack(self, params=None):
        params = params or {}
        try:
            msg_id = str(params.get("message_id", ""))
            reason = str(params.get("reason", "rejected"))
            self.state["nacks"][msg_id] = {"status": "nacked", "reason": reason, "ts": time.time()}
            result = {"domain": "messaging", "method": "nack", "message_id": msg_id, "reason": reason, "total_nacks": len(self.state["nacks"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NACK_ERROR", str(e), 0))

    def priority(self, params=None):
        params = params or {}
        try:
            queue_name = str(params.get("queue", ""))
            msg_id = str(params.get("message_id", ""))
            level = int(params.get("level", 0))
            queue = self.state["queues"].get(queue_name)
            if queue is not None:
                for m in queue.get("messages", []):
                    if m.get("id") == msg_id:
                        m["priority"] = level
            result = {"domain": "messaging", "method": "priority", "queue": queue_name, "message_id": msg_id, "level": level, "set": queue is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PRIORITY_ERROR", str(e), 0))

    def queue(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            self.state["queues"].setdefault(name, {"type": "queue", "mode": "fifo", "messages": []})
            result = {"domain": "messaging", "method": "queue", "name": name, "total_queues": len(self.state["queues"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUEUE_ERROR", str(e), 0))

    def receive(self, params=None):
        params = params or {}
        try:
            queue_name = str(params.get("queue", ""))
            queue = self.state["queues"].get(queue_name)
            message = None
            if queue is not None and queue.get("messages"):
                messages = queue["messages"]
                messages.sort(key=lambda m: m.get("priority", 0), reverse=True)
                message = messages.pop(0)
            result = {"domain": "messaging", "method": "receive", "queue": queue_name, "message": message, "remaining": len(queue["messages"]) if queue else 0}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECEIVE_ERROR", str(e), 0))

    def retry(self, params=None):
        params = params or {}
        try:
            msg_id = str(params.get("message_id", ""))
            attempts = int(params.get("attempts", 0)) + 1
            max_retries = int(params.get("max_retries", 3))
            should_deadletter = attempts >= max_retries
            result = {"domain": "messaging", "method": "retry", "message_id": msg_id, "attempts": attempts, "max_retries": max_retries, "deadletter": should_deadletter}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RETRY_ERROR", str(e), 0))

    def send(self, params=None):
        params = params or {}
        try:
            queue_name = str(params.get("queue", ""))
            payload = params.get("payload")
            priority = int(params.get("priority", 0))
            queue = self.state["queues"].setdefault(queue_name, {"type": "queue", "mode": "fifo", "messages": []})
            message = {"id": self._new_id(), "payload": payload, "priority": priority, "ts": time.time()}
            queue["messages"].append(message)
            result = {"domain": "messaging", "method": "send", "queue": queue_name, "message_id": message["id"], "queue_size": len(queue["messages"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SEND_ERROR", str(e), 0))

    def topic(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            self.state["topics"].setdefault(name, {"subscribers": [], "messages": []})
            result = {"domain": "messaging", "method": "topic", "name": name, "total_topics": len(self.state["topics"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOPIC_ERROR", str(e), 0))

    def unsubscribe(self, params=None):
        params = params or {}
        try:
            topic_name = str(params.get("topic", ""))
            subscriber = str(params.get("subscriber", ""))
            topic = self.state["topics"].get(topic_name)
            removed = False
            if topic is not None and subscriber in topic["subscribers"]:
                topic["subscribers"].remove(subscriber)
                removed = True
            result = {"domain": "messaging", "method": "unsubscribe", "topic": topic_name, "subscriber": subscriber, "removed": removed, "remaining": len(topic["subscribers"]) if topic else 0}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNSUBSCRIBE_ERROR", str(e), 0))
