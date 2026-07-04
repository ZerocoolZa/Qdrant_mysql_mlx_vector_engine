#!/usr/bin/env python3
# [@GHOST]{[@file<GuiAspectRegistry.py>][@domain<gui>][@role<registry>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<registry>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiAspectRegistry — indexes all GuiAspects. Auto-generates help menu, registers shortcuts, syncs settings with config. Every GUI item is registered here. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiAspectRegistry}
# [@METHOD]{Run,register,get,get_all,get_by_category,get_help_menu,get_shortcuts,sync_to_config,sync_from_config,save,load,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Central registry for all GUI aspects. Auto-generates help menu, registers shortcuts, syncs settings. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiAspectRegistry — Central registry for all GUI aspects.

THE PORSCHE PRINCIPLE:
  Every piece exists, belongs, supports the others.
  This registry ensures nothing is missing.

WHAT IT DOES:
  - register:        add a GuiAspect to the registry
  - get:             get an aspect by ID
  - get_all:         get all aspects
  - get_by_category: get aspects grouped by category (for settings dialog)
  - get_help_menu:   auto-generate help menu structure from aspects
  - get_shortcuts:   auto-extract all keyboard shortcuts
  - sync_to_config:  push all settings to config object
  - sync_from_config: pull all settings from config object
  - save:            persist all settings to JSON
  - load:            load all settings from JSON

USAGE:
  from GuiAspectRegistry import GuiAspectRegistry
  from GuiAspect import GuiAspect

  reg = GuiAspectRegistry()
  reg.Run("register", {"aspect": GuiAspect(param={...})})
  reg.Run("register", {"aspect": GuiAspect(param={...})})

  ok, data, err = reg.Run("get", {"id": "voice_enabled"})
  ok, data, err = reg.Run("get_by_category", {"category": "Voice"})
  ok, data, err = reg.Run("get_help_menu")  # → structured help
  ok, data, err = reg.Run("get_shortcuts")  # → all shortcuts
  ok, data, err = reg.Run("sync_to_config", {"config": voice_config})
  ok, data, err = reg.Run("save", {"path": "settings.json"})
"""

import json
import os
from GuiAspect import GuiAspect


class GuiAspectRegistry:
    """
    Central registry for all GUI aspects.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Ensures every GUI item has setting, help, tooltip, shortcut, icon.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "aspects": {},  # id → GuiAspect instance
            "categories": [],  # ordered category list
            "persist_path": param.get("persist_path", "") if param else "",
            "stats": {"registered": 0, "synced": 0, "saved": 0, "loaded": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "register": self.cmd_register,
            "get": self.cmd_get,
            "get_all": self.cmd_get_all,
            "get_by_category": self.cmd_get_by_category,
            "get_categories": self.cmd_get_categories,
            "get_help_menu": self.cmd_get_help_menu,
            "get_shortcuts": self.cmd_get_shortcuts,
            "get_tooltips": self.cmd_get_tooltips,
            "sync_to_config": self.cmd_sync_to_config,
            "sync_from_config": self.cmd_sync_from_config,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, {
            "categories": list(self.state["categories"]),
            "aspect_count": len(self.state["aspects"]),
            "aspect_ids": list(self.state["aspects"].keys()),
            "stats": dict(self.state["stats"]),
            "persist_path": self.state["persist_path"],
        }, None)

    def set_config(self, params):
        if "persist_path" in params:
            self.state["persist_path"] = params["persist_path"]
        return (1, dict(self.state), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_register(self, params):
        aspect = self.p(params, "aspect")
        if aspect is None or not isinstance(aspect, GuiAspect):
            return (0, None, ("ERR_PARAMS", "GuiAspect instance required", 0))
        aspectId = aspect.state["id"]
        if not aspectId:
            return (0, None, ("ERR_PARAMS", "aspect must have an id", 0))
        self.state["aspects"][aspectId] = aspect
        cat = aspect.state["category"]
        if cat not in self.state["categories"]:
            self.state["categories"].append(cat)
        self.state["stats"]["registered"] += 1
        return (1, {"registered": True, "id": aspectId, "category": cat}, None)

    def cmd_get(self, params):
        aspectId = self.p(params, "id")
        if not aspectId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        aspect = self.state["aspects"].get(aspectId)
        if aspect is None:
            return (0, None, ("ERR_NOT_FOUND", "aspect not found: %s" % aspectId, 0))
        return (1, aspect, None)

    def cmd_get_all(self, params):
        result = {}
        for aspectId, aspect in self.state["aspects"].items():
            ok, data, err = aspect.Run("read_state")
            if ok:
                result[aspectId] = data
        return (1, result, None)

    def cmd_get_by_category(self, params):
        category = self.p(params, "category")
        if not category:
            return (0, None, ("ERR_PARAMS", "category required", 0))
        result = []
        for aspectId, aspect in self.state["aspects"].items():
            if aspect.state["category"] == category:
                ok, data, err = aspect.Run("read_state")
                if ok:
                    result.append(data)
        return (1, result, None)

    def cmd_get_categories(self, params):
        return (1, list(self.state["categories"]), None)

    def cmd_get_help_menu(self, params):
        """Auto-generate help menu structure from all aspects."""
        menu = {}
        for cat in self.state["categories"]:
            menu[cat] = []
            for aspectId, aspect in self.state["aspects"].items():
                if aspect.state["category"] == cat:
                    ok, helpText, err = aspect.Run("get_help")
                    ok2, label, err2 = aspect.Run("get_label")
                    ok3, shortcut, err3 = aspect.Run("get_shortcut")
                    menu[cat].append({
                        "id": aspectId,
                        "label": label or aspectId,
                        "help": helpText or "",
                        "shortcut": shortcut or "",
                    })
        return (1, menu, None)

    def cmd_get_shortcuts(self, params):
        """Auto-extract all keyboard shortcuts."""
        shortcuts = {}
        for aspectId, aspect in self.state["aspects"].items():
            ok, shortcut, err = aspect.Run("get_shortcut")
            if ok and shortcut:
                ok2, label, err2 = aspect.Run("get_label")
                shortcuts[shortcut] = {
                    "id": aspectId,
                    "label": label or aspectId,
                }
        return (1, shortcuts, None)

    def cmd_get_tooltips(self, params):
        """Auto-extract all tooltips."""
        tooltips = {}
        for aspectId, aspect in self.state["aspects"].items():
            ok, tooltip, err = aspect.Run("get_tooltip")
            if ok and tooltip:
                tooltips[aspectId] = tooltip
        return (1, tooltips, None)

    def cmd_sync_to_config(self, params):
        """Push all aspect settings to a config object (VoiceConfig or similar)."""
        config = self.p(params, "config")
        if config is None:
            return (0, None, ("ERR_PARAMS", "config object required", 0))
        updates = {}
        for aspectId, aspect in self.state["aspects"].items():
            configKey = aspect.state["config_key"]
            if not configKey:
                continue
            ok, setting, err = aspect.Run("get_setting")
            if ok and setting is not None:
                updates[configKey] = setting
        if updates:
            config.Run("set_config", updates)
        self.state["stats"]["synced"] += 1
        return (1, {"synced": True, "keys": len(updates), "updates": updates}, None)

    def cmd_sync_from_config(self, params):
        """Pull all settings from a config object into aspects."""
        config = self.p(params, "config")
        if config is None:
            return (0, None, ("ERR_PARAMS", "config object required", 0))
        ok, cfgData, err = config.Run("get")
        if not ok:
            return (0, None, err)
        updated = 0
        for aspectId, aspect in self.state["aspects"].items():
            configKey = aspect.state["config_key"]
            if not configKey:
                continue
            if configKey in cfgData:
                aspect.Run("set_setting", {"value": cfgData[configKey]})
                updated += 1
        return (1, {"synced": True, "updated": updated}, None)

    def cmd_save(self, params):
        """Persist all aspect settings to JSON file."""
        path = self.p(params, "path", self.state["persist_path"])
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        data = {}
        for aspectId, aspect in self.state["aspects"].items():
            if not aspect.state["persistent"]:
                continue
            ok, setting, err = aspect.Run("get_setting")
            if ok and setting is not None:
                data[aspectId] = setting
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.state["persist_path"] = path
            self.state["stats"]["saved"] += 1
            return (1, {"saved": True, "path": path, "keys": len(data)}, None)
        except Exception as e:
            return (0, None, ("ERR_SAVE", str(e), 0))

    def cmd_load(self, params):
        """Load all aspect settings from JSON file."""
        path = self.p(params, "path", self.state["persist_path"])
        if not path or not os.path.exists(path):
            return (0, None, ("ERR_PARAMS", "path required or not found", 0))
        try:
            with open(path, "r") as f:
                data = json.load(f)
            loaded = 0
            for aspectId, value in data.items():
                aspect = self.state["aspects"].get(aspectId)
                if aspect:
                    aspect.Run("set_setting", {"value": value})
                    loaded += 1
            self.state["persist_path"] = path
            self.state["stats"]["loaded"] += 1
            return (1, {"loaded": True, "path": path, "keys": loaded}, None)
        except Exception as e:
            return (0, None, ("ERR_LOAD", str(e), 0))
