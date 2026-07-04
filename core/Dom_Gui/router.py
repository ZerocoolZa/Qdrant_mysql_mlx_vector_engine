# [@GHOST]{[@file<EventRouter.py>][@domain<Dom_Gui>][@role<router>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<signal_router>][@return<dict>][@orch<GUIBuilder>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Connects PyQt6 signals to handler methods on the host application object}


class EventRouter:
    """Route BCL [@SIGNAL] declarations to real PyQt6 signal/slot connections.

    Signal map translates BCL signal names to PyQt6 signal attributes.
    If handler method not found on host, logs warning and skips.
    """

    SIGNAL_MAP = {
        "clicked": "clicked",
        "triggered": "triggered",
        "textChanged": "textChanged",
        "currentIndexChanged": "currentIndexChanged",
        "currentTextChanged": "currentTextChanged",
        "stateChanged": "stateChanged",
        "activated": "activated",
        "valueChanged": "valueChanged",
        "toggled": "toggled",
        "returnPressed": "returnPressed",
        "customContextMenuRequested": "customContextMenuRequested",
    }

    def __init__(self):
        self.connections = []
        self.warnings = []

    def route(self, signals, host, widgets):
        """Connect all signals to handler methods on host.

        Args:
            signals: list of dicts from GUIParser.get_signals()
            host: the application object (has handler methods)
            widgets: dict of {name: QWidget} from GUIBuilder

        Returns:
            dict of {widget_name: [(signal, handler), ...]} connected
        """
        self.connections = []
        self.warnings = []

        for sig in signals:
            widget_name = sig.get("widget")
            signal_name = sig.get("signal")
            handler_name = sig.get("handler")
            accepts = sig.get("accepts")

            widget = widgets.get(widget_name)
            if widget is None:
                self.warnings.append(f"Widget not found: {widget_name}")
                continue

            pyqt_signal = self.SIGNAL_MAP.get(signal_name)
            if pyqt_signal is None:
                self.warnings.append(f"Unknown signal: {signal_name} on {widget_name}")
                continue

            handler = getattr(host, handler_name, None)
            if handler is None:
                self.warnings.append(f"Handler not found: {handler_name} on host")
                continue

            signal_obj = getattr(widget, pyqt_signal, None)
            if signal_obj is None:
                self.warnings.append(f"Signal attr not found: {pyqt_signal} on {widget_name}")
                continue

            try:
                signal_obj.connect(handler)
                self.connections.append({
                    "widget": widget_name,
                    "signal": signal_name,
                    "handler": handler_name,
                })
            except Exception as e:
                self.warnings.append(f"Connect failed: {widget_name}.{signal_name} -> {handler_name}: {e}")

        return self.connections

    def disconnect(self, widget_name, signal_name=None):
        """Disconnect signals for a widget."""
        to_remove = []
        for conn in self.connections:
            if conn["widget"] == widget_name:
                if signal_name is None or conn["signal"] == signal_name:
                    to_remove.append(conn)
        for conn in to_remove:
            self.connections.remove(conn)

    def get_warnings(self):
        return self.warnings
