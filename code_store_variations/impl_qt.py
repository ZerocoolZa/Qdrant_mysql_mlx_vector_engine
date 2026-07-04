class DomQt:
    """Qt domain: widget lifecycle, signals/slots, layout and event handling."""

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
            "create_widget": self.create_widget,
            "disable": self.disable,
            "disconnect": self.disconnect,
            "enable": self.enable,
            "event": self.event,
            "hide": self.hide,
            "layout": self.layout,
            "menu": self.menu,
            "paint": self.paint,
            "signal": self.signal,
            "slot": self.slot,
            "style": self.style,
            "tooltip": self.tooltip,
        }
        h = handlers.get(command)
        if h:
            return h(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def create_widget(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            wtype = params.get("type", "QWidget")
            if not name:
                return (0, None, ("CREATE_WIDGET_ERROR", "name required", 0))
            widget = {"name": name, "type": wtype, "visible": False, "enabled": True}
            self.state["catalog"].append(widget)
            result = {"domain": "qt", "method": "create_widget", "widget": widget, "created": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_WIDGET_ERROR", str(e), 0))

    def disable(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("DISABLE_ERROR", "name required", 0))
            for w in self.state["catalog"]:
                if w.get("name") == name:
                    w["enabled"] = False
            result = {"domain": "qt", "method": "disable", "name": name, "disabled": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISABLE_ERROR", str(e), 0))

    def disconnect(self, params=None):
        params = params or {}
        try:
            signal = params.get("signal")
            slot = params.get("slot")
            if not signal or not slot:
                return (0, None, ("DISCONNECT_ERROR", "signal and slot required", 0))
            result = {"domain": "qt", "method": "disconnect", "signal": signal, "slot": slot, "disconnected": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISCONNECT_ERROR", str(e), 0))

    def enable(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("ENABLE_ERROR", "name required", 0))
            for w in self.state["catalog"]:
                if w.get("name") == name:
                    w["enabled"] = True
            result = {"domain": "qt", "method": "enable", "name": name, "enabled": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENABLE_ERROR", str(e), 0))

    def event(self, params=None):
        params = params or {}
        try:
            etype = params.get("type")
            target = params.get("target")
            if not etype:
                return (0, None, ("EVENT_ERROR", "type required", 0))
            evt = {"type": etype, "target": target}
            self.state["results"].append(evt)
            result = {"domain": "qt", "method": "event", "event": evt, "dispatched": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_ERROR", str(e), 0))

    def hide(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("HIDE_ERROR", "name required", 0))
            for w in self.state["catalog"]:
                if w.get("name") == name:
                    w["visible"] = False
            result = {"domain": "qt", "method": "hide", "name": name, "hidden": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HIDE_ERROR", str(e), 0))

    def layout(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            ltype = params.get("type", "QVBoxLayout")
            widgets = params.get("widgets", [])
            if not name:
                return (0, None, ("LAYOUT_ERROR", "name required", 0))
            lay = {"name": name, "type": ltype, "widgets": widgets}
            self.state["config"]["layout"] = lay
            result = {"domain": "qt", "method": "layout", "layout": lay}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LAYOUT_ERROR", str(e), 0))

    def menu(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            items = params.get("items", [])
            if not name:
                return (0, None, ("MENU_ERROR", "name required", 0))
            menu = {"name": name, "items": items}
            self.state["catalog"].append(menu)
            result = {"domain": "qt", "method": "menu", "menu": menu, "created": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MENU_ERROR", str(e), 0))

    def paint(self, params=None):
        params = params or {}
        try:
            target = params.get("target")
            paint_ops = params.get("operations", [])
            if not target:
                return (0, None, ("PAINT_ERROR", "target required", 0))
            result = {"domain": "qt", "method": "paint", "target": target, "operations": paint_ops, "painted": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PAINT_ERROR", str(e), 0))

    def signal(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            source = params.get("source")
            if not name:
                return (0, None, ("SIGNAL_ERROR", "name required", 0))
            sig = {"name": name, "source": source}
            self.state["results"].append(sig)
            result = {"domain": "qt", "method": "signal", "signal": sig, "emitted": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGNAL_ERROR", str(e), 0))

    def slot(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            handler = params.get("handler")
            if not name or not handler:
                return (0, None, ("SLOT_ERROR", "name and handler required", 0))
            slot = {"name": name, "handler": handler}
            self.state["catalog"].append(slot)
            result = {"domain": "qt", "method": "slot", "slot": slot, "registered": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SLOT_ERROR", str(e), 0))

    def style(self, params=None):
        params = params or {}
        try:
            target = params.get("target")
            sheet = params.get("stylesheet", "")
            if not target:
                return (0, None, ("STYLE_ERROR", "target required", 0))
            result = {"domain": "qt", "method": "style", "target": target, "stylesheet": sheet, "applied": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STYLE_ERROR", str(e), 0))

    def tooltip(self, params=None):
        params = params or {}
        try:
            target = params.get("target")
            text = params.get("text", "")
            if not target:
                return (0, None, ("TOOLTIP_ERROR", "target required", 0))
            result = {"domain": "qt", "method": "tooltip", "target": target, "text": text, "set": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOOLTIP_ERROR", str(e), 0))
