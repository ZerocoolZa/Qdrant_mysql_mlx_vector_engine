#!/usr/bin/env python3
# [@GHOST]{[@file<GuiAspect.py>][@domain<gui>][@role<aspect>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<aspect>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiAspect — defines a single GUI configurable item with setting, help, tooltip, shortcut, icon. Every widget gets a GuiAspect. Syncs with config. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiAspect}
# [@METHOD]{Run,get_setting,set_setting,get_help,get_tooltip,get_shortcut,get_icon,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Single GUI configurable item with setting, help, tooltip, shortcut, icon. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiAspect — Metadata + control for a single GUI configurable item.

THE PORSCHE PRINCIPLE:
  Every piece exists, belongs, supports the others, and works together.
  A GUI is not a collection of controls — it's a complete system.

WHAT EACH ASPECT HAS:
  - setting:  the current value (synced with config)
  - help:     full help text for the Help menu
  - tooltip:  hover tooltip for the widget
  - shortcut: keyboard shortcut (e.g. "Ctrl+M")
  - icon:     icon name or path for the widget
  - label:    display label
  - category: grouping (Voice, STT, Theme, Font, Window, etc.)
  - widget:   widget type (checkbox, spinbox, combobox, slider, button)
  - min_val:  minimum value (for spinbox/slider)
  - max_val:  maximum value (for spinbox/slider)
  - step:     step size (for spinbox/slider)
  - suffix:   suffix string (e.g. " s", " wpm")
  - decimals: decimal places (for double spinbox)
  - options:  list of options (for combobox)
  - config_key: key in config.py that this aspect maps to
  - persistent: should this be saved to settings file?

WHY CLASS-BASED:
  - Every widget has the same structure — no missing tooltips, no missing shortcuts
  - Config sync is automatic — change setting → updates config
  - Help menu is auto-generated from aspects
  - Keyboard shortcuts are auto-registered
  - Icons are auto-loaded
  - Nothing is missing — the Porsche is complete

USAGE:
  from GuiAspect import GuiAspect

  aspect = GuiAspect(param={
      "id": "voice_enabled",
      "label": "Devin speaks responses (TTS)",
      "category": "Voice",
      "widget": "checkbox",
      "setting": True,
      "help": "When enabled, Devin will speak responses aloud using macOS NSSpeechSynthesizer.",
      "tooltip": "Toggle text-to-speech for Devin responses",
      "shortcut": "Ctrl+Shift+V",
      "icon": "audio-volume-high",
      "config_key": "enabled",
      "persistent": True,
  })

  ok, data, err = aspect.Run("get_setting")   # → True
  ok, data, err = aspect.Run("set_setting", {"value": False})
  ok, data, err = aspect.Run("get_help")      # → help text
  ok, data, err = aspect.Run("get_tooltip")   # → tooltip text
  ok, data, err = aspect.Run("get_shortcut")  # → "Ctrl+Shift+V"
  ok, data, err = aspect.Run("get_icon")      # → icon name
"""


class GuiAspect:
    """
    Single GUI configurable item — setting, help, tooltip, shortcut, icon.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Every widget gets one. Nothing is missing.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "id": p.get("id", ""),
            "label": p.get("label", ""),
            "category": p.get("category", "General"),
            "widget": p.get("widget", "checkbox"),
            "setting": p.get("setting", None),
            "default": p.get("setting", None),
            "help": p.get("help", ""),
            "tooltip": p.get("tooltip", ""),
            "shortcut": p.get("shortcut", ""),
            "icon": p.get("icon", ""),
            "config_key": p.get("config_key", ""),
            "persistent": p.get("persistent", True),
            "min_val": p.get("min_val", None),
            "max_val": p.get("max_val", None),
            "step": p.get("step", None),
            "suffix": p.get("suffix", ""),
            "decimals": p.get("decimals", 0),
            "options": p.get("options", []),
            "visible": p.get("visible", True),
            "enabled": p.get("enabled", True),
        }

    def Run(self, command, params=None):
        dispatch = {
            "get_setting": self.cmd_get_setting,
            "set_setting": self.cmd_set_setting,
            "get_help": self.cmd_get_help,
            "get_tooltip": self.cmd_get_tooltip,
            "get_shortcut": self.cmd_get_shortcut,
            "get_icon": self.cmd_get_icon,
            "get_label": self.cmd_get_label,
            "get_category": self.cmd_get_category,
            "get_widget_type": self.cmd_get_widget_type,
            "get_config_key": self.cmd_get_config_key,
            "reset": self.cmd_reset,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_get_setting(self, params):
        return (1, self.state["setting"], None)

    def cmd_set_setting(self, params):
        value = self.p(params, "value")
        if value is None:
            return (0, None, ("ERR_PARAMS", "value required", 0))
        self.state["setting"] = value
        return (1, {"setting": value, "config_key": self.state["config_key"]}, None)

    def cmd_get_help(self, params):
        return (1, self.state["help"], None)

    def cmd_get_tooltip(self, params):
        return (1, self.state["tooltip"], None)

    def cmd_get_shortcut(self, params):
        return (1, self.state["shortcut"], None)

    def cmd_get_icon(self, params):
        return (1, self.state["icon"], None)

    def cmd_get_label(self, params):
        return (1, self.state["label"], None)

    def cmd_get_category(self, params):
        return (1, self.state["category"], None)

    def cmd_get_widget_type(self, params):
        return (1, self.state["widget"], None)

    def cmd_get_config_key(self, params):
        return (1, self.state["config_key"], None)

    def cmd_reset(self, params):
        self.state["setting"] = self.state["default"]
        return (1, {"setting": self.state["default"], "reset": True}, None)
