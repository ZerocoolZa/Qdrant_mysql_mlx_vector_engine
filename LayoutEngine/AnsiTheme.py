#[@GHOST]{[@file<AnsiTheme.py>][@domain<ansi_theme>][@role<theme_color>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<theme>][@return<Tuple3>][@state<preset,palette>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/AnsiTheme.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{ANSI theme system: palette presets, colorize, style codes, apply/reset, 256-color helpers}
#[@CLASS]{AnsiTheme — holds active palette, colorizes text, applies styles, manages presets}
#[@METHOD]{Run dispatch: colorize, style, reset, preset, palette, border, read_state, set_config}

import Config


class AnsiTheme:
    """ANSI theme system.

    Holds an active palette (dict of role -> ANSI code) and provides:
      colorize(text, role)   -> text wrapped in role's color + reset
      style(text, codes)     -> text wrapped in raw style codes + reset
      border(kind, width)    -> border character string for box drawing
      preset(name)           -> switch active palette
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        preset_name = p.get("preset", Config.THEME_DEFAULT)
        self.state = {
            "config": {"preset": preset_name},
            "palette": dict(Config.THEME_PRESETS.get(preset_name, Config.THEME_DARK)),
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "colorize": self.colorize,
            "style": self.style,
            "reset": self.reset,
            "preset": self.preset,
            "palette": self.palette,
            "border": self.border,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # colorize(text, role) -> wrapped string
    # ------------------------------------------------------------------
    def colorize(self, params):
        text = self._p(params, "text", "")
        role = self._p(params, "role", "fg")
        code = self.state["palette"].get(role, self.state["palette"].get("fg", ""))
        if code == "":
            return (1, text, None)
        return (1, code + text + Config.ANSI_RESET, None)

    # ------------------------------------------------------------------
    # style(text, codes) -> wrapped with raw codes
    # ------------------------------------------------------------------
    def style(self, params):
        text = self._p(params, "text", "")
        codes = self._p(params, "codes", "")
        if not codes:
            return (1, text, None)
        if isinstance(codes, list):
            codes = "".join(codes)
        return (1, codes + text + Config.ANSI_RESET, None)

    # ------------------------------------------------------------------
    # reset -> ANSI_RESET string
    # ------------------------------------------------------------------
    def reset(self, params):
        return (1, Config.ANSI_RESET, None)

    # ------------------------------------------------------------------
    # preset(name) -> switch active palette
    # ------------------------------------------------------------------
    def preset(self, params):
        name = self._p(params, "name", Config.THEME_DEFAULT)
        if name not in Config.THEME_PRESETS:
            return (0, None, ("unknown_preset", "no preset: " + str(name), 0))
        self.state["config"]["preset"] = name
        self.state["palette"] = dict(Config.THEME_PRESETS[name])
        return (1, name, None)

    # ------------------------------------------------------------------
    # palette -> current palette dict
    # ------------------------------------------------------------------
    def palette(self, params):
        return (1, dict(self.state["palette"]), None)

    # ------------------------------------------------------------------
    # border(kind, width) -> border string
    #   kind: "horizontal" | "vertical" | "tl" | "tr" | "bl" | "br" | "tee_l" | ...
    # ------------------------------------------------------------------
    def border(self, params):
        kind = self._p(params, "kind", "horizontal")
        width = self._p(params, "width", 1)
        glyphs = {
            "horizontal": "\u2500",
            "vertical": "\u2502",
            "tl": "\u250c",
            "tr": "\u2510",
            "bl": "\u2514",
            "br": "\u2518",
            "tee_t": "\u252c",
            "tee_b": "\u2534",
            "tee_l": "\u251c",
            "tee_r": "\u2524",
            "cross": "\u253c",
            "dash": "\u2504",
            "dot": "\u2506",
            "double_h": "\u2550",
            "double_v": "\u2551",
            "double_tl": "\u2554",
            "double_tr": "\u2557",
            "double_bl": "\u255a",
            "double_br": "\u255d",
            "space": " ",
        }
        g = glyphs.get(kind, glyphs["horizontal"])
        return (1, g * width, None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "palette": dict(self.state["palette"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        if "preset" in params:
            ok, data, err = self.preset({"name": params["preset"]})
            if not ok:
                return (0, None, err)
        if "palette" in params and isinstance(params["palette"], dict):
            self.state["palette"].update(params["palette"])
        return (1, True, None)
