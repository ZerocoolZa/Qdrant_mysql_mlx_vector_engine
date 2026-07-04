#[@GHOST]{[@file<TextLayout.py>][@domain<text_layout>][@role<text_measure_wrap>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<text>][@return<Tuple3>][@state<measure,wrap>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/TextLayout.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{CJK-aware text measurement + wrapping: ANSI-stripped visible width, East-Asian wide detection, word/char/hard wrap to a cell box}
#[@CLASS]{TextLayout — visible_width, wrap, truncate, pad, strip_ansi}
#[@METHOD]{Run dispatch: visible_width, wrap, truncate, pad, strip_ansi, read_state, set_config}

import Config

# Precompute a wide-char set for fast lookup
_WIDE_SET = set()
for _lo, _hi in Config.CJK_WIDE_RANGES:
    for _cp in range(_lo, _hi + 1):
        _WIDE_SET.add(_cp)
        if len(_WIDE_SET) > 200000:
            break


class TextLayout:
    """CJK-aware text measurement and wrapping.

    All operations ignore ANSI escape sequences when measuring visible width.
    Wrapping respects East-Asian wide characters (width 2) and zero-width
    controls. Three wrap modes: word, char, hard.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "tab_width": p.get("tab_width", Config.TAB_WIDTH),
                "wrap_mode": p.get("wrap_mode", Config.WRAP_WORD),
                "ellipsis": p.get("ellipsis", Config.ELLIPSIS),
            },
            "stats": {"measured": 0, "wrapped": 0, "truncated": 0},
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "visible_width": self.visible_width,
            "wrap": self.wrap,
            "truncate": self.truncate,
            "pad": self.pad,
            "strip_ansi": self.strip_ansi,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # strip_ansi
    # ------------------------------------------------------------------
    def strip_ansi(self, params):
        text = self._p(params, "text", "")
        if text is None:
            return (1, "", None)
        out = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b":
                i += 1
                while i < n and text[i] not in ("m", "H", "J", "K", "A", "B", "C", "D"):
                    i += 1
                i += 1
                continue
            out.append(ch)
            i += 1
        return (1, "".join(out), None)

    # ------------------------------------------------------------------
    # visible_width
    # ------------------------------------------------------------------
    def visible_width(self, params):
        text = self._p(params, "text", "")
        if text is None:
            return (1, 0, None)
        w = _visible_width(text, self.state["config"]["tab_width"])
        self.state["stats"]["measured"] += 1
        return (1, w, None)

    # ------------------------------------------------------------------
    # wrap
    # ------------------------------------------------------------------
    def wrap(self, params):
        text = self._p(params, "text", "")
        width = self._p(params, "width", 80)
        mode = self._p(params, "mode", self.state["config"]["wrap_mode"])
        if text is None or width <= 0:
            return (1, [], None)
        lines = _wrap_text(text, width, mode, self.state["config"]["tab_width"])
        self.state["stats"]["wrapped"] += 1
        return (1, lines, None)

    # ------------------------------------------------------------------
    # truncate
    # ------------------------------------------------------------------
    def truncate(self, params):
        text = self._p(params, "text", "")
        width = self._p(params, "width", Config.TRUNCATE_DEFAULT)
        ellipsis = self._p(params, "ellipsis", self.state["config"]["ellipsis"])
        if text is None:
            return (1, "", None)
        result = _truncate(text, width, ellipsis, self.state["config"]["tab_width"])
        self.state["stats"]["truncated"] += 1
        return (1, result, None)

    # ------------------------------------------------------------------
    # pad
    # ------------------------------------------------------------------
    def pad(self, params):
        text = self._p(params, "text", "")
        width = self._p(params, "width", 0)
        align = self._p(params, "align", "left")
        fill = self._p(params, "fill", " ")
        if text is None:
            text = ""
        if len(fill) == 0:
            fill = " "
        vw = _visible_width(text, self.state["config"]["tab_width"])
        if vw >= width:
            return (1, text, None)
        pad_len = width - vw
        if align == "right":
            return (1, fill * pad_len + text, None)
        if align == "center":
            left = pad_len // 2
            right = pad_len - left
            return (1, fill * left + text + fill * right, None)
        return (1, text + fill * pad_len, None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("tab_width", "wrap_mode", "ellipsis"):
            if k in params:
                self.state["config"][k] = params[k]
        return (1, True, None)


# ---------------------------------------------------------------------------
# Module-level helpers (also imported by Constraints.measure)
# ---------------------------------------------------------------------------

def _visible_width(text, tab_width=Config.TAB_WIDTH):
    if text is None:
        return 0
    width = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\x1b":
            i += 1
            while i < n and text[i] not in ("m", "H", "J", "K", "A", "B", "C", "D"):
                i += 1
            i += 1
            continue
        if ch == "\t":
            width += tab_width
        elif ch == "\r":
            pass
        elif ch == "\n":
            pass
        else:
            cp = ord(ch)
            width += 2 if cp in _WIDE_SET else 1
        i += 1
    return width


def _char_width(cp):
    return 2 if cp in _WIDE_SET else 1


def _wrap_text(text, width, mode, tab_width=Config.TAB_WIDTH):
    """Wrap text to `width` visible cells. Returns list of lines (no ANSI)."""
    # First strip ANSI so wrapping works on visible text
    stripped = _strip_ansi(text)
    out = []
    for raw_line in stripped.split("\n"):
        if mode == Config.WRAP_CHAR or mode == Config.WRAP_HARD:
            out.extend(_wrap_char(raw_line, width, tab_width))
        else:
            out.extend(_wrap_word(raw_line, width, tab_width))
    return out


def _wrap_word(line, width, tab_width):
    if _visible_width(line, tab_width) <= width:
        return [line]
    out = []
    cur = ""
    cur_w = 0
    for word in line.split(" "):
        ww = _visible_width(word, tab_width)
        sep = 1 if cur else 0
        if cur_w + sep + ww > width and cur:
            out.append(cur)
            cur = word
            cur_w = ww
        else:
            if cur:
                cur += " " + word
                cur_w += 1 + ww
            else:
                cur = word
                cur_w = ww
    if cur:
        out.append(cur)
    return out if out else [""]


def _wrap_char(line, width, tab_width):
    if _visible_width(line, tab_width) <= width:
        return [line]
    out = []
    cur = ""
    cur_w = 0
    for ch in line:
        cw = 2 if ord(ch) in _WIDE_SET else 1
        if ch == "\t":
            cw = tab_width
        if cur_w + cw > width:
            out.append(cur)
            cur = ch
            cur_w = cw
        else:
            cur += ch
            cur_w += cw
    if cur:
        out.append(cur)
    return out


def _truncate(text, width, ellipsis, tab_width=Config.TAB_WIDTH):
    stripped = _strip_ansi(text)
    if _visible_width(stripped, tab_width) <= width:
        return stripped
    ell_w = _visible_width(ellipsis, tab_width)
    target = width - ell_w
    if target <= 0:
        return ellipsis[:width]
    out = ""
    cur_w = 0
    for ch in stripped:
        cw = 2 if ord(ch) in _WIDE_SET else 1
        if cur_w + cw > target:
            break
        out += ch
        cur_w += cw
    return out + ellipsis


def _strip_ansi(text):
    if text is None:
        return ""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\x1b":
            i += 1
            while i < n and text[i] not in ("m", "H", "J", "K", "A", "B", "C", "D"):
                i += 1
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)
