#!/usr/bin/env python3
# [@GHOST]{[@file<GuiAspects.py>][@domain<gui>][@role<aspect_factory>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<aspect_factory>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiAspects — factory that creates and registers all GuiAspect definitions for ChatGui. Every configurable item defined here with setting, help, tooltip, shortcut, icon. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiAspects}
# [@METHOD]{Run,build_voice,build_stt,build_theme,build_font,build_window,build_all,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Factory that creates and registers all GuiAspect definitions for ChatGui. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiAspects — Factory for all GUI aspect definitions.

THE PORSCHE PRINCIPLE:
  Every piece exists, belongs, supports the others.
  This file defines EVERY configurable item in the GUI.
  Nothing is missing. Nothing is left to chance.

CATEGORIES:
  Voice  — TTS settings (enabled, voice, rate)
  STT    — Speech recognition settings (language, on-device, buffer, silence, etc.)
  Theme  — Color theme selection
  Font   — Font sizes (chat, input, list)
  Window — Window settings (opacity, always-on-top, position, size)

EACH ASPECT HAS:
  - setting:  current value
  - help:     full help text
  - tooltip:  hover tooltip
  - shortcut: keyboard shortcut
  - icon:     icon name
  - label:    display label
  - widget:   widget type (checkbox, spinbox, combobox, etc.)
  - config_key: maps to VoiceConfig / Config.py key
  - persistent: saved to settings file

USAGE:
  from GuiAspects import GuiAspects
  from GuiAspectRegistry import GuiAspectRegistry

  factory = GuiAspects()
  reg = GuiAspectRegistry()
  ok, data, err = factory.Run("build_all", {"registry": reg})
  # Now reg has all aspects registered
  ok, data, err = reg.Run("get_help_menu")  # → complete help menu
  ok, data, err = reg.Run("get_shortcuts")  # → all shortcuts
"""

from GuiAspect import GuiAspect


class GuiAspects:
    """
    Factory for all GUI aspect definitions.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": p.get("config", None),
            "built": False,
            "aspect_count": 0,
        }

    def Run(self, command, params=None):
        dispatch = {
            "build_voice": self.cmd_build_voice,
            "build_stt": self.cmd_build_stt,
            "build_theme": self.cmd_build_theme,
            "build_font": self.cmd_build_font,
            "build_window": self.cmd_build_window,
            "build_all": self.cmd_build_all,
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

    def reg(self, params):
        registry = self.p(params, "registry")
        if registry is None:
            return None
        return registry

    def registerAspect(self, registry, aspectParam):
        aspect = GuiAspect(param=aspectParam)
        ok, data, err = registry.Run("register", {"aspect": aspect})
        if ok:
            self.state["aspect_count"] += 1
        return ok

    def getConfigVal(self, key, default=None):
        cfg = self.state["config"]
        if cfg is None:
            return default
        ok, data, err = cfg.Run("get", {"key": key})
        if ok and data is not None:
            return data
        return default

    # ════════════════════════════════════════════
    # BUILDERS — one per category
    # ════════════════════════════════════════════

    def cmd_build_voice(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        # Voice enabled
        self.registerAspect(registry, {
            "id": "voice_enabled",
            "label": "Devin speaks responses (TTS)",
            "category": "Voice",
            "widget": "checkbox",
            "setting": self.getConfigVal("enabled", False),
            "help": "When enabled, Devin will speak responses aloud using macOS NSSpeechSynthesizer. This is text-to-speech (TTS). You can change the voice and speaking rate below.",
            "tooltip": "Toggle text-to-speech for Devin responses",
            "shortcut": "Ctrl+Shift+V",
            "icon": "audio-volume-high",
            "config_key": "enabled",
            "persistent": True,
        })

        # Voice name
        self.registerAspect(registry, {
            "id": "voice_name",
            "label": "Voice",
            "category": "Voice",
            "widget": "combobox",
            "setting": self.getConfigVal("voice", "Samantha"),
            "help": "Select the macOS voice used for text-to-speech. macOS includes 80+ voices in multiple languages. Popular choices: Samantha (natural), Alex (male), Daniel (British), Karen (Australian).",
            "tooltip": "Select TTS voice",
            "shortcut": "",
            "icon": "user-identity",
            "config_key": "voice",
            "persistent": True,
            "options": ["Samantha", "Alex", "Daniel", "Karen", "Moira", "Tessa", "Fiona", "Veena"],
        })

        # Voice rate
        self.registerAspect(registry, {
            "id": "voice_rate",
            "label": "Rate (words per minute)",
            "category": "Voice",
            "widget": "spinbox",
            "setting": self.getConfigVal("rate", 180),
            "help": "Speaking rate in words per minute. Default is 180. Range: 80 (very slow) to 400 (very fast). 200 is a natural conversational pace.",
            "tooltip": "TTS speaking speed",
            "shortcut": "",
            "icon": "preferences-system-time",
            "config_key": "rate",
            "persistent": True,
            "min_val": 80,
            "max_val": 400,
            "step": 10,
            "suffix": " wpm",
            "decimals": 0,
        })

        return (1, {"built": True, "category": "Voice", "count": 3}, None)

    def cmd_build_stt(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        # STT on-device
        self.registerAspect(registry, {
            "id": "stt_on_device",
            "label": "On-device recognition (privacy + speed)",
            "category": "STT",
            "widget": "checkbox",
            "setting": self.getConfigVal("stt_on_device", True),
            "help": "When enabled, speech recognition happens on your Mac using the Neural Engine. This is faster (180-280ms vs 450-1400ms cloud) and private (audio never leaves your device). Requires macOS 10.15+ and A12/M1 or newer.",
            "tooltip": "Use on-device speech recognition for privacy and speed",
            "shortcut": "Ctrl+Shift+O",
            "icon": "computer",
            "config_key": "stt_on_device",
            "persistent": True,
        })

        # STT language
        self.registerAspect(registry, {
            "id": "stt_language",
            "label": "Language",
            "category": "STT",
            "widget": "combobox",
            "setting": self.getConfigVal("stt_language", "en-US"),
            "help": "Language for speech recognition. Must match the language you speak. On-device recognition requires the language model to be downloaded (System Settings > Accessibility > Speech).",
            "tooltip": "Speech recognition language",
            "shortcut": "",
            "icon": "preferences-desktop-locale",
            "config_key": "stt_language",
            "persistent": True,
            "options": ["en-US", "en-GB", "en-AU", "en-IE", "en-ZA", "en-IN", "en-SG"],
        })

        # STT buffer size
        self.registerAspect(registry, {
            "id": "stt_buffer_size",
            "label": "Buffer size",
            "category": "STT",
            "widget": "spinbox",
            "setting": self.getConfigVal("stt_buffer_size", 4096),
            "help": "Audio buffer size in samples. Larger buffers capture more audio per callback but add latency. 4096 samples is about 93ms at 44.1kHz. The OS enforces a minimum of ~4800 frames regardless of this setting.",
            "tooltip": "Audio capture buffer size",
            "shortcut": "",
            "icon": "drive-harddisk",
            "config_key": "stt_buffer_size",
            "persistent": True,
            "min_val": 512,
            "max_val": 16384,
            "step": 512,
            "suffix": " samples",
            "decimals": 0,
        })

        # STT silence timeout
        self.registerAspect(registry, {
            "id": "stt_silence_timeout",
            "label": "Silence timeout",
            "category": "STT",
            "widget": "doublespinbox",
            "setting": self.getConfigVal("stt_silence_timeout", 2.5),
            "help": "Seconds of silence before transcription auto-finalizes. If you stop talking for this duration, the mic stops and sends what it heard. Lower values = faster response but may cut off pauses. Higher values = more natural but slower.",
            "tooltip": "How long to wait after you stop talking",
            "shortcut": "",
            "icon": "preferences-system-time",
            "config_key": "stt_silence_timeout",
            "persistent": True,
            "min_val": 0.5,
            "max_val": 10.0,
            "step": 0.5,
            "suffix": " s",
            "decimals": 1,
        })

        # STT min listen
        self.registerAspect(registry, {
            "id": "stt_min_listen",
            "label": "Min listen time",
            "category": "STT",
            "widget": "doublespinbox",
            "setting": self.getConfigVal("stt_min_listen", 1.0),
            "help": "Minimum listen time before silence detection kicks in. Prevents cutting off short utterances. The mic will listen for at least this long before considering silence as end-of-speech.",
            "tooltip": "Minimum listening duration",
            "shortcut": "",
            "icon": "media-playback-start",
            "config_key": "stt_min_listen",
            "persistent": True,
            "min_val": 0.1,
            "max_val": 10.0,
            "step": 0.1,
            "suffix": " s",
            "decimals": 1,
        })

        # STT max timeout
        self.registerAspect(registry, {
            "id": "stt_max_timeout",
            "label": "Max listen time",
            "category": "STT",
            "widget": "spinbox",
            "setting": self.getConfigVal("stt_max_timeout", 60),
            "help": "Maximum listen time in seconds. The mic will auto-stop after this duration regardless of speech. Prevents infinite listening if silence detection fails.",
            "tooltip": "Maximum listening duration",
            "shortcut": "",
            "icon": "dialog-cancel",
            "config_key": "stt_max_timeout",
            "persistent": True,
            "min_val": 5,
            "max_val": 300,
            "step": 5,
            "suffix": " s",
            "decimals": 0,
        })

        # STT runloop interval
        self.registerAspect(registry, {
            "id": "stt_runloop_interval",
            "label": "Runloop interval",
            "category": "STT",
            "widget": "doublespinbox",
            "setting": self.getConfigVal("stt_runloop_interval", 0.05),
            "help": "How often the speech recognition event loop runs, in seconds. 0.05s (50ms) is balanced. Lower values reduce latency but increase CPU. 0.01s can cause 100% CPU spikes. Don't change unless you know what you're doing.",
            "tooltip": "Event loop polling interval",
            "shortcut": "",
            "icon": "system-search",
            "config_key": "stt_runloop_interval",
            "persistent": True,
            "min_val": 0.01,
            "max_val": 0.5,
            "step": 0.01,
            "suffix": " s",
            "decimals": 2,
        })

        # STT silence threshold
        self.registerAspect(registry, {
            "id": "stt_silence_threshold",
            "label": "Silence threshold (RMS)",
            "category": "STT",
            "widget": "doublespinbox",
            "setting": self.getConfigVal("stt_silence_threshold", 0.01),
            "help": "Audio level threshold for detecting speech vs silence. RMS values below this are considered silence. 0.01 is quiet. 0.05 is normal room. 0.1 is noisy environment. Raise this if ambient noise triggers the mic. Lower it if quiet speech isn't detected.",
            "tooltip": "Microphone sensitivity — raise to ignore ambient noise",
            "shortcut": "Ctrl+Shift+T",
            "icon": "audio-input-microphone",
            "config_key": "stt_silence_threshold",
            "persistent": True,
            "min_val": 0.001,
            "max_val": 0.1,
            "step": 0.001,
            "suffix": "",
            "decimals": 3,
        })

        return (1, {"built": True, "category": "STT", "count": 8}, None)

    def cmd_build_theme(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        self.registerAspect(registry, {
            "id": "theme",
            "label": "Color theme",
            "category": "Theme",
            "widget": "combobox",
            "setting": "Dark",
            "help": "Select the color theme for the chat interface. Dark is easy on the eyes in low light. Light is better in bright environments. Matrix is green-on-black for the hacker aesthetic.",
            "tooltip": "Change color theme",
            "shortcut": "Ctrl+Shift+T",
            "icon": "preferences-desktop-color",
            "config_key": "",
            "persistent": True,
            "options": ["Dark", "Light", "Matrix"],
        })

        return (1, {"built": True, "category": "Theme", "count": 1}, None)

    def cmd_build_font(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        self.registerAspect(registry, {
            "id": "font_chat",
            "label": "Chat font size",
            "category": "Font",
            "widget": "spinbox",
            "setting": 14,
            "help": "Font size for chat messages in pixels. Default is 14. Increase for readability, decrease to fit more text.",
            "tooltip": "Chat message font size",
            "shortcut": "Ctrl+=",
            "icon": "format-text-size",
            "config_key": "",
            "persistent": True,
            "min_val": 8,
            "max_val": 32,
            "step": 1,
            "suffix": " px",
            "decimals": 0,
        })

        self.registerAspect(registry, {
            "id": "font_input",
            "label": "Input font size",
            "category": "Font",
            "widget": "spinbox",
            "setting": 14,
            "help": "Font size for the text input area in pixels. Default is 14.",
            "tooltip": "Input area font size",
            "shortcut": "",
            "icon": "format-text-size",
            "config_key": "",
            "persistent": True,
            "min_val": 8,
            "max_val": 32,
            "step": 1,
            "suffix": " px",
            "decimals": 0,
        })

        self.registerAspect(registry, {
            "id": "font_list",
            "label": "List font size",
            "category": "Font",
            "widget": "spinbox",
            "setting": 12,
            "help": "Font size for session list and other lists in pixels. Default is 12.",
            "tooltip": "List font size",
            "shortcut": "",
            "icon": "format-text-size",
            "config_key": "",
            "persistent": True,
            "min_val": 8,
            "max_val": 32,
            "step": 1,
            "suffix": " px",
            "decimals": 0,
        })

        return (1, {"built": True, "category": "Font", "count": 3}, None)

    def cmd_build_window(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        self.registerAspect(registry, {
            "id": "window_opacity",
            "label": "Window opacity",
            "category": "Window",
            "widget": "slider",
            "setting": 95,
            "help": "Window transparency. 100% is fully opaque. 50% is half transparent. Useful for overlaying on other windows.",
            "tooltip": "Window transparency",
            "shortcut": "",
            "icon": "view-visible",
            "config_key": "",
            "persistent": True,
            "min_val": 20,
            "max_val": 100,
            "step": 5,
            "suffix": " %",
            "decimals": 0,
        })

        self.registerAspect(registry, {
            "id": "window_ontop",
            "label": "Always on top",
            "category": "Window",
            "widget": "checkbox",
            "setting": False,
            "help": "Keep the window floating above all other windows. Useful when you want to see the chat while working in other apps.",
            "tooltip": "Keep window on top",
            "shortcut": "Ctrl+Shift+P",
            "icon": "window-pin",
            "config_key": "",
            "persistent": True,
        })

        self.registerAspect(registry, {
            "id": "window_geometry",
            "label": "Window position and size",
            "category": "Window",
            "widget": "hidden",
            "setting": [100, 100, 900, 700],
            "help": "Window position (x, y) and size (width, height) in pixels. Automatically saved when you move or resize the window.",
            "tooltip": "",
            "shortcut": "",
            "icon": "window",
            "config_key": "",
            "persistent": True,
        })

        return (1, {"built": True, "category": "Window", "count": 3}, None)

    def cmd_build_all(self, params):
        registry = self.reg(params)
        if registry is None:
            return (0, None, ("ERR_PARAMS", "registry required", 0))

        results = {}
        for builder in ["build_voice", "build_stt", "build_theme", "build_font", "build_window"]:
            ok, data, err = self.Run(builder, {"registry": registry})
            if ok:
                results[data["category"]] = data["count"]
            else:
                return (0, None, err)

        self.state["built"] = True
        total = sum(results.values())
        return (1, {"built": True, "total": total, "by_category": results}, None)
