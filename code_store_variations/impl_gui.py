class DomGui:
    """GUI domain: widget tree management, layout, drawing, and event handling using stdlib."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "widgets": {}, "windows": {}, "events": [], "theme": "default", "style": {}}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "add_widget": self.add_widget, "button": self.button, "checkbox": self.checkbox,
            "close_window": self.close_window, "combo": self.combo, "create_window": self.create_window,
            "dialog": self.dialog, "draw_line": self.draw_line, "draw_rect": self.draw_rect,
            "draw_text": self.draw_text, "event_click": self.event_click, "event_close": self.event_close,
            "event_key": self.event_key, "event_mouse": self.event_mouse, "event_resize": self.event_resize,
            "hide": self.hide, "label": self.label, "layout": self.layout, "menu": self.menu,
            "paint": self.paint, "panel": self.panel, "progress": self.progress, "refresh": self.refresh,
            "remove_widget": self.remove_widget, "render": self.render, "resize": self.resize,
            "set_style": self.set_style, "set_theme": self.set_theme, "set_title": self.set_title,
            "slider": self.slider, "splitter": self.splitter, "tab": self.tab, "table": self.table,
            "text": self.text, "toolbar": self.toolbar, "tree": self.tree, "update": self.update,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _next_id(self):
        return str(len(self.state["widgets"]) + 1)

    def _add_widget(self, widget):
        wid = widget["id"]
        self.state["widgets"][wid] = widget
        return widget

    def add_widget(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": params.get("type", "widget"), "parent": params.get("parent"), "props": params.get("props", {})}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "add_widget", "id": str(wid), "total": len(self.state["widgets"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_WIDGET_ERROR", str(e), 0))

    def button(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "button", "parent": params.get("parent"), "props": {"label": params.get("label", "Button"), "enabled": params.get("enabled", True)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "button", "id": str(wid), "label": widget["props"]["label"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUTTON_ERROR", str(e), 0))

    def checkbox(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "checkbox", "parent": params.get("parent"), "props": {"label": params.get("label", "Check"), "checked": params.get("checked", False)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "checkbox", "id": str(wid), "checked": widget["props"]["checked"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECKBOX_ERROR", str(e), 0))

    def close_window(self, params=None):
        params = params or {}
        try:
            win_id = str(params.get("window_id", ""))
            existed = win_id in self.state["windows"]
            if existed:
                del self.state["windows"][win_id]
            result = {"domain": "gui", "method": "close_window", "window_id": win_id, "closed": existed, "remaining_windows": len(self.state["windows"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLOSE_WINDOW_ERROR", str(e), 0))

    def combo(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "combo", "parent": params.get("parent"), "props": {"items": params.get("items", []), "selected": params.get("selected")}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "combo", "id": str(wid), "items": widget["props"]["items"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMBO_ERROR", str(e), 0))

    def create_window(self, params=None):
        params = params or {}
        try:
            win_id = str(params.get("id", str(len(self.state["windows"]) + 1)))
            window = {"id": win_id, "title": params.get("title", "Window"), "width": params.get("width", 800), "height": params.get("height", 600), "visible": True}
            self.state["windows"][win_id] = window
            result = {"domain": "gui", "method": "create_window", "id": win_id, "title": window["title"], "total_windows": len(self.state["windows"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_WINDOW_ERROR", str(e), 0))

    def dialog(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "dialog", "parent": params.get("parent"), "props": {"title": params.get("title", "Dialog"), "modal": params.get("modal", True), "buttons": params.get("buttons", ["ok", "cancel"])}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "dialog", "id": str(wid), "modal": widget["props"]["modal"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIALOG_ERROR", str(e), 0))

    def draw_line(self, params=None):
        params = params or {}
        try:
            shape = {"type": "line", "x1": params.get("x1", 0), "y1": params.get("y1", 0), "x2": params.get("x2", 0), "y2": params.get("y2", 0), "color": params.get("color", "#000000")}
            self.state["results"].append(shape)
            result = {"domain": "gui", "method": "draw_line", "shape": shape}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DRAW_LINE_ERROR", str(e), 0))

    def draw_rect(self, params=None):
        params = params or {}
        try:
            shape = {"type": "rect", "x": params.get("x", 0), "y": params.get("y", 0), "w": params.get("w", 0), "h": params.get("h", 0), "color": params.get("color", "#000000"), "fill": params.get("fill", False)}
            self.state["results"].append(shape)
            result = {"domain": "gui", "method": "draw_rect", "shape": shape}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DRAW_RECT_ERROR", str(e), 0))

    def draw_text(self, params=None):
        params = params or {}
        try:
            shape = {"type": "text", "x": params.get("x", 0), "y": params.get("y", 0), "text": params.get("text", ""), "font": params.get("font", "sans"), "size": params.get("size", 12)}
            self.state["results"].append(shape)
            result = {"domain": "gui", "method": "draw_text", "shape": shape}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DRAW_TEXT_ERROR", str(e), 0))

    def event_click(self, params=None):
        params = params or {}
        try:
            event = {"type": "click", "widget_id": str(params.get("widget_id", "")), "x": params.get("x", 0), "y": params.get("y", 0)}
            self.state["events"].append(event)
            result = {"domain": "gui", "method": "event_click", "event": event, "total_events": len(self.state["events"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_CLICK_ERROR", str(e), 0))

    def event_close(self, params=None):
        params = params or {}
        try:
            event = {"type": "close", "window_id": str(params.get("window_id", ""))}
            self.state["events"].append(event)
            result = {"domain": "gui", "method": "event_close", "event": event}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_CLOSE_ERROR", str(e), 0))

    def event_key(self, params=None):
        params = params or {}
        try:
            event = {"type": "key", "key": params.get("key", ""), "modifiers": params.get("modifiers", [])}
            self.state["events"].append(event)
            result = {"domain": "gui", "method": "event_key", "event": event}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_KEY_ERROR", str(e), 0))

    def event_mouse(self, params=None):
        params = params or {}
        try:
            event = {"type": "mouse", "action": params.get("action", "move"), "x": params.get("x", 0), "y": params.get("y", 0), "button": params.get("button", 0)}
            self.state["events"].append(event)
            result = {"domain": "gui", "method": "event_mouse", "event": event}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_MOUSE_ERROR", str(e), 0))

    def event_resize(self, params=None):
        params = params or {}
        try:
            event = {"type": "resize", "window_id": str(params.get("window_id", "")), "width": params.get("width", 0), "height": params.get("height", 0)}
            self.state["events"].append(event)
            result = {"domain": "gui", "method": "event_resize", "event": event}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EVENT_RESIZE_ERROR", str(e), 0))

    def hide(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("id", ""))
            target = self.state["widgets"].get(wid) or self.state["windows"].get(wid)
            if target is not None:
                target["visible"] = False
            result = {"domain": "gui", "method": "hide", "id": wid, "hidden": target is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HIDE_ERROR", str(e), 0))

    def label(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "label", "parent": params.get("parent"), "props": {"text": params.get("text", "")}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "label", "id": str(wid), "text": widget["props"]["text"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LABEL_ERROR", str(e), 0))

    def layout(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "layout", "parent": params.get("parent"), "props": {"direction": params.get("direction", "vertical"), "spacing": params.get("spacing", 8), "margin": params.get("margin", 8)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "layout", "id": str(wid), "direction": widget["props"]["direction"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LAYOUT_ERROR", str(e), 0))

    def menu(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "menu", "parent": params.get("parent"), "props": {"items": params.get("items", [])}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "menu", "id": str(wid), "items": widget["props"]["items"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MENU_ERROR", str(e), 0))

    def paint(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("widget_id", ""))
            widget = self.state["widgets"].get(wid)
            painted = widget is not None
            if painted:
                widget["props"]["painted"] = True
            result = {"domain": "gui", "method": "paint", "widget_id": wid, "painted": painted}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PAINT_ERROR", str(e), 0))

    def panel(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "panel", "parent": params.get("parent"), "props": {"title": params.get("title", ""), "border": params.get("border", True)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "panel", "id": str(wid), "title": widget["props"]["title"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PANEL_ERROR", str(e), 0))

    def progress(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "progress", "parent": params.get("parent"), "props": {"value": params.get("value", 0), "max": params.get("max", 100)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "progress", "id": str(wid), "value": widget["props"]["value"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROGRESS_ERROR", str(e), 0))

    def refresh(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("widget_id", ""))
            refreshed = wid in self.state["widgets"]
            result = {"domain": "gui", "method": "refresh", "widget_id": wid, "refreshed": refreshed}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REFRESH_ERROR", str(e), 0))

    def remove_widget(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("id", ""))
            existed = wid in self.state["widgets"]
            if existed:
                del self.state["widgets"][wid]
            result = {"domain": "gui", "method": "remove_widget", "id": wid, "removed": existed, "remaining": len(self.state["widgets"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REMOVE_WIDGET_ERROR", str(e), 0))

    def render(self, params=None):
        params = params or {}
        try:
            widgets = list(self.state["widgets"].values())
            windows = list(self.state["windows"].values())
            result = {"domain": "gui", "method": "render", "widget_count": len(widgets), "window_count": len(windows), "widgets": widgets, "windows": windows}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RENDER_ERROR", str(e), 0))

    def resize(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("id", ""))
            width = params.get("width")
            height = params.get("height")
            target = self.state["windows"].get(wid) or self.state["widgets"].get(wid)
            if target is not None and width is not None:
                target["width"] = width
            if target is not None and height is not None:
                target["height"] = height
            result = {"domain": "gui", "method": "resize", "id": wid, "resized": target is not None, "width": width, "height": height}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESIZE_ERROR", str(e), 0))

    def set_style(self, params=None):
        params = params or {}
        try:
            style = params.get("style") or {}
            self.state["style"].update(style)
            result = {"domain": "gui", "method": "set_style", "style": self.state["style"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_STYLE_ERROR", str(e), 0))

    def set_theme(self, params=None):
        params = params or {}
        try:
            theme = str(params.get("theme", "default"))
            self.state["theme"] = theme
            result = {"domain": "gui", "method": "set_theme", "theme": theme}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_THEME_ERROR", str(e), 0))

    def set_title(self, params=None):
        params = params or {}
        try:
            win_id = str(params.get("window_id", ""))
            title = str(params.get("title", ""))
            window = self.state["windows"].get(win_id)
            if window is not None:
                window["title"] = title
            result = {"domain": "gui", "method": "set_title", "window_id": win_id, "title": title, "set": window is not None}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_TITLE_ERROR", str(e), 0))

    def slider(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "slider", "parent": params.get("parent"), "props": {"min": params.get("min", 0), "max": params.get("max", 100), "value": params.get("value", 0)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "slider", "id": str(wid), "value": widget["props"]["value"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SLIDER_ERROR", str(e), 0))

    def splitter(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "splitter", "parent": params.get("parent"), "props": {"orientation": params.get("orientation", "horizontal"), "ratio": params.get("ratio", 0.5)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "splitter", "id": str(wid), "orientation": widget["props"]["orientation"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLITTER_ERROR", str(e), 0))

    def tab(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "tab", "parent": params.get("parent"), "props": {"tabs": params.get("tabs", []), "active": params.get("active", 0)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "tab", "id": str(wid), "tabs": widget["props"]["tabs"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TAB_ERROR", str(e), 0))

    def table(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "table", "parent": params.get("parent"), "props": {"columns": params.get("columns", []), "rows": params.get("rows", [])}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "table", "id": str(wid), "columns": widget["props"]["columns"], "row_count": len(widget["props"]["rows"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TABLE_ERROR", str(e), 0))

    def text(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "text", "parent": params.get("parent"), "props": {"text": params.get("text", ""), "readonly": params.get("readonly", False)}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "text", "id": str(wid), "text": widget["props"]["text"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEXT_ERROR", str(e), 0))

    def toolbar(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "toolbar", "parent": params.get("parent"), "props": {"actions": params.get("actions", [])}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "toolbar", "id": str(wid), "actions": widget["props"]["actions"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOOLBAR_ERROR", str(e), 0))

    def tree(self, params=None):
        params = params or {}
        try:
            wid = params.get("id") or self._next_id()
            widget = {"id": str(wid), "type": "tree", "parent": params.get("parent"), "props": {"nodes": params.get("nodes", [])}}
            self._add_widget(widget)
            result = {"domain": "gui", "method": "tree", "id": str(wid), "nodes": widget["props"]["nodes"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TREE_ERROR", str(e), 0))

    def update(self, params=None):
        params = params or {}
        try:
            wid = str(params.get("id", ""))
            props = params.get("props") or {}
            widget = self.state["widgets"].get(wid)
            updated = False
            if widget is not None:
                widget["props"].update(props)
                updated = True
            result = {"domain": "gui", "method": "update", "id": wid, "updated": updated, "props": props}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))
