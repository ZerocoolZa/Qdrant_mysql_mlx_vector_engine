#[@GHOST]{[@file<TerminalRenderer.py>][@domain<terminal_render>][@role<ansi_compile>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<renderer_terminal>][@return<Tuple3>][@state<canvas,theme>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/TerminalRenderer.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Terminal renderer: compiles solved Layout Graph -> ANSI string canvas. Block/Table/Tree/Pipeline are visitors over the solved tree.}
#[@CLASS]{TerminalRenderer — owns canvas grid, theme, text layout; renders any solved node tree to ANSI}
#[@METHOD]{Run dispatch: render, render_node, canvas_str, read_state, set_config}

import Config
from LayoutNode import LayoutNode
from AnsiTheme import AnsiTheme
from TextLayout import TextLayout, _visible_width, _strip_ansi, _wrap_text, _truncate


class Canvas:
    """Cell grid canvas. (x, y) -> char. Renders to a single ANSI string."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        # grid[y] = list of chars (width long)
        self.grid = [[" "] * width for _ in range(height)]
        # color[y] = list of ansi prefix strings (or "")
        self.color = [[""] * width for _ in range(height)]

    def put(self, x, y, text, code=""):
        if y < 0 or y >= self.height:
            return
        i = 0
        n = len(text)
        while i < n:
            if x >= self.width:
                break
            ch = text[i]
            if ch == "\x1b":
                # capture ansi code into `code` for subsequent chars
                j = i + 1
                while j < n and text[j] not in ("m",):
                    j += 1
                code = text[i:j + 1]
                i = j + 1
                continue
            if ch == "\n":
                break
            cw = 2 if ord(ch) in _WIDE_SET else 1
            if ch == "\t":
                ch = " "
                cw = 1
            if x + cw <= self.width:
                self.grid[y][x] = ch
                self.color[y][x] = code
                if cw == 2:
                    if x + 1 < self.width:
                        self.grid[y][x + 1] = ""
                        self.color[y][x + 1] = code
                x += cw
            else:
                break
            i += 1

    def hline(self, x, y, length, ch="\u2500", code=""):
        if y < 0 or y >= self.height:
            return
        for i in range(length):
            if x + i < self.width:
                self.grid[y][x + i] = ch
                self.color[y][x + i] = code

    def vline(self, x, y, length, ch="\u2502", code=""):
        for i in range(length):
            if y + i >= self.height:
                break
            if x < self.width:
                self.grid[y + i][x] = ch
                self.color[y + i][x] = code

    def box(self, x, y, w, h, code=""):
        if w < 2 or h < 2:
            return
        self.put(x, y, "\u250c", code)
        self.hline(x + 1, y, w - 2, "\u2500", code)
        self.put(x + w - 1, y, "\u2510", code)
        self.vline(x, y + 1, h - 2, "\u2502", code)
        self.vline(x + w - 1, y + 1, h - 2, "\u2502", code)
        self.put(x, y + h - 1, "\u2514", code)
        self.hline(x + 1, y + h - 1, w - 2, "\u2500", code)
        self.put(x + w - 1, y + h - 1, "\u2518", code)

    def to_string(self):
        lines = []
        for y in range(self.height):
            row = []
            prev_code = None
            for x in range(self.width):
                ch = self.grid[y][x]
                code = self.color[y][x]
                if ch == "":
                    continue
                if code != prev_code:
                    if code == "":
                        row.append(Config.ANSI_RESET)
                    else:
                        row.append(code)
                    prev_code = code
                row.append(ch)
            if prev_code:
                row.append(Config.ANSI_RESET)
            lines.append("".join(row).rstrip())
        return "\n".join(lines)


# Reuse the wide set from TextLayout
_WIDE_SET = set()
for _lo, _hi in Config.CJK_WIDE_RANGES:
    for _cp in range(_lo, _hi + 1):
        _WIDE_SET.add(_cp)
        if len(_WIDE_SET) > 200000:
            break


class TerminalRenderer:
    """Compiles a solved Layout Graph into an ANSI string.

    Visits each node, dispatches on kind:
      block    -> boxed cell with title + content
      text     -> wrapped text in rect
      row/col  -> recurse children (rects already solved)
      table    -> header + rows grid
      tree     -> indented tree lines
      pipeline -> staged horizontal flow
      spacer   -> blank
      divider  -> horizontal rule
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "width": p.get("width", Config.DEFAULT_TERM_WIDTH),
                "height": p.get("height", Config.DEFAULT_TERM_HEIGHT),
                "theme": p.get("theme", Config.THEME_DEFAULT),
            },
            "theme": AnsiTheme(param={"preset": p.get("theme", Config.THEME_DEFAULT)}),
            "text": TextLayout(),
            "canvas": None,
            "stats": {"nodes": 0, "leaves": 0},
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "render": self.render,
            "render_node": self.render_node,
            "canvas_str": self.canvas_str,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # render(root) -> ANSI string
    # ------------------------------------------------------------------
    def render(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("missing_root", "render requires {'root': LayoutNode}", 0))
        rect = root.state["rect"]
        if rect is None:
            return (0, None, ("not_solved", "tree has no rects; run solver first", 0))
        w = rect.w
        h = rect.h
        if w <= 0 or h <= 0:
            return (1, "", None)
        canvas = Canvas(w, h)
        self.state["canvas"] = canvas
        self._render_node(root, canvas)
        return (1, canvas.to_string(), None)

    def render_node(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("missing_node", "render_node requires {'node': LayoutNode}", 0))
        rect = node.state["rect"]
        if rect is None:
            return (0, None, ("not_solved", "node has no rect", 0))
        canvas = Canvas(rect.w, rect.h)
        self._render_node(node, canvas)
        return (1, canvas.to_string(), None)

    def canvas_str(self, params):
        c = self.state["canvas"]
        if c is None:
            return (0, None, ("no_canvas", "no canvas; render first", 0))
        return (1, c.to_string(), None)

    # ------------------------------------------------------------------
    # Core: dispatch on node kind
    # ------------------------------------------------------------------
    def _render_node(self, node, canvas):
        self.state["stats"]["nodes"] += 1
        kind = node.state["kind"]
        rect = node.state["rect"]
        if rect is None:
            return
        theme = self.state["theme"]
        border_code = theme.state["palette"].get("border", "")
        title_code = theme.state["palette"].get("title", "")
        fg_code = theme.state["palette"].get("fg", "")

        if kind == Config.KIND_BLOCK:
            self._render_block(node, canvas, border_code, title_code, fg_code)
        elif kind == Config.KIND_TEXT:
            self._render_text(node, canvas, fg_code)
        elif kind == Config.KIND_TABLE:
            self._render_table(node, canvas, border_code, title_code, fg_code)
        elif kind == Config.KIND_TREE:
            self._render_tree(node, canvas, fg_code)
        elif kind == Config.KIND_PIPELINE:
            self._render_pipeline(node, canvas, border_code, title_code, fg_code)
        elif kind == Config.KIND_DIVIDER:
            self._render_divider(node, canvas, border_code)
        elif kind == Config.KIND_SPACER:
            pass
        elif kind in (Config.KIND_ROW, Config.KIND_COLUMN, Config.KIND_CONTAINER):
            for ch in node.state["children"]:
                self._render_node(ch, canvas)
        else:
            # widget / unknown -> recurse children
            self.state["stats"]["leaves"] += 1
            for ch in node.state["children"]:
                self._render_node(ch, canvas)

    # ------------------------------------------------------------------
    # Block: boxed cell with optional title + content
    # ------------------------------------------------------------------
    def _render_block(self, node, canvas, border_code, title_code, fg_code):
        rect = node.state["rect"]
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        if w < 2 or h < 2:
            # too small for a box; just put content if any
            content = node.state["content"]
            if content and h == 1:
                canvas.put(x, y, str(content)[:w], fg_code)
            return
        canvas.box(x, y, w, h, border_code)
        title = node.state["meta"].get("title")
        if title:
            t = " " + str(title) + " "
            tx = x + 2
            if tx + len(t) <= x + w:
                canvas.put(tx, y, t, title_code)
        content = node.state["content"]
        if content:
            inner_w = w - 2
            inner_h = h - 2
            lines = _wrap_text(str(content), inner_w, Config.WRAP_WORD)
            for i, ln in enumerate(lines[:inner_h]):
                canvas.put(x + 1, y + 1 + i, ln, fg_code)

    # ------------------------------------------------------------------
    # Text: wrapped text in rect
    # ------------------------------------------------------------------
    def _render_text(self, node, canvas, fg_code):
        rect = node.state["rect"]
        content = node.state["content"]
        if not content:
            return
        lines = _wrap_text(str(content), rect.w, Config.WRAP_WORD)
        for i, ln in enumerate(lines[:rect.h]):
            canvas.put(rect.x, rect.y + i, ln, fg_code)

    # ------------------------------------------------------------------
    # Divider: horizontal rule
    # ------------------------------------------------------------------
    def _render_divider(self, node, canvas, border_code):
        rect = node.state["rect"]
        canvas.hline(rect.x, rect.y, rect.w, "\u2500", border_code)

    # ------------------------------------------------------------------
    # Table: header + rows grid
    # ------------------------------------------------------------------
    def _render_table(self, node, canvas, border_code, title_code, fg_code):
        rect = node.state["rect"]
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        meta = node.state["meta"]
        headers = meta.get("headers", [])
        rows = node.state["content"]
        if not isinstance(rows, list):
            rows = []
        if not headers:
            # fallback: just render content as text lines
            self._render_text(node, canvas, fg_code)
            return
        ncol = len(headers)
        if ncol == 0:
            return
        col_w = max(1, w // ncol)
        # top border
        canvas.hline(x, y, w, "\u2500", border_code)
        # header row
        for i, hd in enumerate(headers):
            cx = x + i * col_w
            label = _truncate(str(hd), col_w - 1, "")
            canvas.put(cx, y + 1, label, title_code)
        canvas.hline(x, y + 2, w, "\u2500", border_code)
        # rows
        ry = y + 3
        for row in rows[:max(0, h - 3)]:
            if not isinstance(row, (list, tuple)):
                row = [row]
            for i in range(ncol):
                cx = x + i * col_w
                val = row[i] if i < len(row) else ""
                label = _truncate(str(val), col_w - 1, "")
                canvas.put(cx, ry, label, fg_code)
            ry += 1
            if ry >= y + h:
                break

    # ------------------------------------------------------------------
    # Tree: indented tree lines
    # ------------------------------------------------------------------
    def _render_tree(self, node, canvas, fg_code):
        rect = node.state["rect"]
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        meta = node.state["meta"]
        root_label = meta.get("root_label", node.state["content"] or "")
        children = node.state["children"]
        line = 0
        if y + line < y + h:
            canvas.put(x, y + line, str(root_label)[:w], fg_code)
            line += 1
        for ch in children:
            if line >= h:
                break
            label = ch.state["meta"].get("label", ch.state["content"] or "")
            prefix = "\u251c\u2500 "
            canvas.put(x, y + line, prefix + str(label)[:w - 3], fg_code)
            line += 1
            for gc in ch.state["children"]:
                if line >= h:
                    break
                glabel = gc.state["meta"].get("label", gc.state["content"] or "")
                gp = "    \u2514\u2500 "
                canvas.put(x, y + line, gp + str(glabel)[:w - 5], fg_code)
                line += 1

    # ------------------------------------------------------------------
    # Pipeline: staged horizontal flow
    # ------------------------------------------------------------------
    def _render_pipeline(self, node, canvas, border_code, title_code, fg_code):
        rect = node.state["rect"]
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        children = node.state["children"]
        n = len(children)
        if n == 0:
            return
        stage_w = max(1, w // n)
        for i, ch in enumerate(children):
            sx = x + i * stage_w
            label = ch.state["meta"].get("label", ch.state["content"] or "")
            canvas.box(sx, y, min(stage_w, w - (sx - x)), h, border_code)
            canvas.put(sx + 1, y, " " + str(label)[:stage_w - 2] + " ", title_code)
            sub = ch.state["meta"].get("sub", "")
            if sub and h > 2:
                canvas.put(sx + 1, y + 1, str(sub)[:stage_w - 2], fg_code)
            # arrow between stages
            if i < n - 1 and sx + stage_w < x + w:
                ax = sx + stage_w - 1
                if ax < canvas.width:
                    canvas.put(ax, y + h // 2, ">", fg_code)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
            "has_canvas": self.state["canvas"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("width", "height", "theme"):
            if k in params:
                self.state["config"][k] = params[k]
        if "theme" in params:
            self.state["theme"].Run("preset", {"name": params["theme"]})
        return (1, True, None)
