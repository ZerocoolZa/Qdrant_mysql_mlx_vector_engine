#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_svg_engine.py>][@domain<svg_engine>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for svg_engine domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- File Inventory --------------------------------------------
    # -- Config_svg_engine.py --
    # Purpose: Gold Standard Config for SVG Engine + QA Bridge.
    # Lines: 365 | Classes: 1 | Methods: 0
    #   Class: Config -- methods: __init__, theme, btn, pipeline_mode_names, pipeline_mode_list
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- wizard_animation_engine.py --
    # Purpose: Wizard SVG Animation Engine — Live Preview
    # Lines: 309 | Classes: 7 | Methods: 1
    #   Class: Vec2 -- methods: 
    #   Class: Keyframe -- methods: 
    #   Class: Object -- methods: 
    #   Class: Particle -- methods: 
    #   Class: Scene -- methods: 
    #   Class: WizardEngine -- methods: __init__, set_preset, render
    #   Class: AnimationPreviewUI -- methods: __init__, tick, toggle_play, reset_time, change_speed, toggle_loop, change_preset, save_frame
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- wizard_mockup.py --
    # Purpose: Mockup of the Unified MCP Setup Wizard GUI.
    # Lines: 864 | Classes: 15 | Methods: 1
    #   Class: WizardMascot -- methods: paintEvent, _draw_star
    #   Class: StepIndicator -- methods: __init__, _build, set_current, _update
    #   Class: WizardPage -- methods: __init__, _build, add_widget, add_layout, is_valid
    #   Class: WelcomePage -- methods: __init__
    #   Class: PasswordPage -- methods: __init__, _input_style, _check_strength, _check_match, is_valid
    #   Class: VaultPage -- methods: __init__
    #   Class: ChromePage -- methods: __init__, _btn_style
    #   Class: GoogleAccountPage -- methods: __init__, _input_style, _combo_style
    #   Class: DrivePage -- methods: __init__
    #   Class: GmailPage -- methods: __init__
    #   Class: YahooPage -- methods: __init__
    #   Class: ModelConfigPage -- methods: __init__
    #   Class: VerificationPage -- methods: __init__
    #   Class: FinishPage -- methods: __init__
    #   Class: WizardWindow -- methods: __init__, _apply_dark_theme, _nav_btn_style, _update_ui, go_next, go_back
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- wizard_mockup_v2.py --
    # Purpose: Unified MCP Setup Wizard GUI — v2 with proper SVG wizard mascots.
    # Lines: 941 | Classes: 14 | Methods: 1
    #   Class: StepIndicator -- methods: __init__, _build, set_current, _update
    #   Class: WizardPage -- methods: __init__, _build, add_widget, add_layout, is_valid
    #   Class: WelcomePage -- methods: __init__
    #   Class: PasswordPage -- methods: __init__, _input_style, _check_strength, _check_match, is_valid
    #   Class: VaultPage -- methods: __init__
    #   Class: ChromePage -- methods: __init__
    #   Class: GoogleAccountPage -- methods: __init__, _input_style, _combo_style
    #   Class: DrivePage -- methods: __init__
    #   Class: GmailPage -- methods: __init__
    #   Class: YahooPage -- methods: __init__
    #   Class: ModelConfigPage -- methods: __init__
    #   Class: VerificationPage -- methods: __init__
    #   Class: FinishPage -- methods: __init__
    #   Class: WizardWindow -- methods: __init__, _set_wizard, _on_wizard_change, _apply_dark_theme, _nav_btn_style, _update_ui, go_next, go_back
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- wizard_qa_bridge.py --
    # Purpose: SVG Engine ↔ QA Engine Bridge
    # Lines: 638 | Classes: 4 | Methods: 1
    #   Class: QABridge -- methods: __init__, available, _try_init, ask, status
    #   Class: QASpeechBubble -- methods: render_bubble, render_thinking
    #   Class: QAQueryThread -- methods: __init__, run
    #   Class: WizardQAUI -- methods: __init__, _build_ui, _check_qa_status, _ask_question, _on_qa_result, _clear_chat, _load_preset, _on_mode_changed, _on_model_changed, _apply_settings
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- wizard_qa_bridge_v2.py --
    # Purpose: SVG Engine ↔ QA Engine Bridge
    # Lines: 805 | Classes: 9 | Methods: 1
    #   Class: QABridge -- methods: __init__, available, _try_init, ask, status
    #   Class: QASpeechBubble -- methods: render_bubble, render_thinking
    #   Class: QAQueryThread -- methods: __init__, run
    #   Class: ActivityBar -- methods: __init__, _build, _on_click, set_active
    #   Class: SettingsPanel -- methods: __init__, _build, _apply_settings
    #   Class: ChatPanel -- methods: __init__, _build
    #   Class: ExportPanel -- methods: __init__, _build, _export_svg, _export_png, _export_json, _export_frames
    #   Class: InfoPanel -- methods: __init__
    #   Class: WizardQAUI -- methods: __init__, _build_ui, _on_activity_clicked, _get_chat_display, _check_qa_status, _ask_question, _on_qa_result, _clear_chat, _load_preset, _toggle_play
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- wizard_scene_editor.py --
    # Purpose: Wizard SVG Animation Engine — FULL SCENE EDITOR
    # Lines: 798 | Classes: 9 | Methods: 1
    #   Class: Vec2 -- methods: 
    #   Class: Keyframe -- methods: 
    #   Class: Object -- methods: 
    #   Class: Particle -- methods: 
    #   Class: Scene -- methods: 
    #   Class: WizardEngine -- methods: __init__, _setup_ffi, load_preset, add_object, remove_object, clear_scene, set_pos, set_rot, set_scale, set_opacity
    #   Class: StyleHelper -- methods: dark, btn, btn_danger
    #   Class: PropertyEditor -- methods: __init__, _build, load_object, _on_changed, _pick_color, _add_keyframe, _clear_keyframes, _refresh_keyframes, _delete_object
    #   Class: SceneEditorUI -- methods: __init__, _build_ui, _start_timer, _tick, _refresh_object_list, _on_select_object, _on_prop_changed, _add_object, _quick_add, _clear_scene
    #   Functions: main
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- wizard_scheme_generator.py --
    # Purpose: Procedural Wizard SVG Scheme Generator — MAX EDITION
    # Lines: 801 | Classes: 3 | Methods: 2
    #   Class: WizardSVGSchemeGenerator -- methods: __init__, _stars, _runes, _nebula, _circles, _background, _hat, _beard, _face, _coat
    #   Class: WizardPreviewCard -- methods: __init__, mousePressEvent
    #   Class: SchemeGeneratorUI -- methods: __init__, _get_params, regenerate, generate_gallery, _gallery_click, save_svg, save_png, save_go
    #   Functions: star_polygon_pts, main
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "Config_svg_engine.py": {
        "purpose": "Gold Standard Config for SVG Engine + QA Bridge.",
        "lines": 365,
        "classes": ["Config"],
        "methods": [],
    },
    "wizard_animation_engine.py": {
        "purpose": "Wizard SVG Animation Engine — Live Preview",
        "lines": 309,
        "classes": ["Vec2", "Keyframe", "Object", "Particle", "Scene", "WizardEngine", "AnimationPreviewUI"],
        "methods": ["main"],
    },
    "wizard_mockup.py": {
        "purpose": "Mockup of the Unified MCP Setup Wizard GUI.",
        "lines": 864,
        "classes": ["WizardMascot", "StepIndicator", "WizardPage", "WelcomePage", "PasswordPage", "VaultPage", "ChromePage", "GoogleAccountPage", "DrivePage", "GmailPage", "YahooPage", "ModelConfigPage", "VerificationPage", "FinishPage", "WizardWindow"],
        "methods": ["main"],
    },
    "wizard_mockup_v2.py": {
        "purpose": "Unified MCP Setup Wizard GUI — v2 with proper SVG wizard mascots.",
        "lines": 941,
        "classes": ["StepIndicator", "WizardPage", "WelcomePage", "PasswordPage", "VaultPage", "ChromePage", "GoogleAccountPage", "DrivePage", "GmailPage", "YahooPage", "ModelConfigPage", "VerificationPage", "FinishPage", "WizardWindow"],
        "methods": ["main"],
    },
    "wizard_qa_bridge.py": {
        "purpose": "SVG Engine ↔ QA Engine Bridge",
        "lines": 638,
        "classes": ["QABridge", "QASpeechBubble", "QAQueryThread", "WizardQAUI"],
        "methods": ["main"],
    },
    "wizard_qa_bridge_v2.py": {
        "purpose": "SVG Engine ↔ QA Engine Bridge",
        "lines": 805,
        "classes": ["QABridge", "QASpeechBubble", "QAQueryThread", "ActivityBar", "SettingsPanel", "ChatPanel", "ExportPanel", "InfoPanel", "WizardQAUI"],
        "methods": ["main"],
    },
    "wizard_scene_editor.py": {
        "purpose": "Wizard SVG Animation Engine — FULL SCENE EDITOR",
        "lines": 798,
        "classes": ["Vec2", "Keyframe", "Object", "Particle", "Scene", "WizardEngine", "StyleHelper", "PropertyEditor", "SceneEditorUI"],
        "methods": ["main"],
    },
    "wizard_scheme_generator.py": {
        "purpose": "Procedural Wizard SVG Scheme Generator — MAX EDITION",
        "lines": 801,
        "classes": ["WizardSVGSchemeGenerator", "WizardPreviewCard", "SchemeGeneratorUI"],
        "methods": ["star_polygon_pts", "main"],
    },
}
# -- Classes Dict ----------------------------------------------
CLASSES = {
    "Config": {
        "file": "Config_svg_engine.py",
        "methods": ["__init__", "theme", "btn", "pipeline_mode_names", "pipeline_mode_list"],
    },
    "Vec2": {
        "file": "wizard_animation_engine.py",
        "methods": [],
    },
    "Keyframe": {
        "file": "wizard_animation_engine.py",
        "methods": [],
    },
    "Object": {
        "file": "wizard_animation_engine.py",
        "methods": [],
    },
    "Particle": {
        "file": "wizard_animation_engine.py",
        "methods": [],
    },
    "Scene": {
        "file": "wizard_animation_engine.py",
        "methods": [],
    },
    "WizardEngine": {
        "file": "wizard_animation_engine.py",
        "methods": ["__init__", "set_preset", "render"],
    },
    "AnimationPreviewUI": {
        "file": "wizard_animation_engine.py",
        "methods": ["__init__", "tick", "toggle_play", "reset_time", "change_speed", "toggle_loop", "change_preset", "save_frame"],
    },
    "WizardMascot": {
        "file": "wizard_mockup.py",
        "methods": ["paintEvent", "_draw_star"],
    },
    "StepIndicator": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_build", "set_current", "_update"],
    },
    "WizardPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_build", "add_widget", "add_layout", "is_valid"],
    },
    "WelcomePage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "PasswordPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_input_style", "_check_strength", "_check_match", "is_valid"],
    },
    "VaultPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "ChromePage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_btn_style"],
    },
    "GoogleAccountPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_input_style", "_combo_style"],
    },
    "DrivePage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "GmailPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "YahooPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "ModelConfigPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "VerificationPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "FinishPage": {
        "file": "wizard_mockup.py",
        "methods": ["__init__"],
    },
    "WizardWindow": {
        "file": "wizard_mockup.py",
        "methods": ["__init__", "_apply_dark_theme", "_nav_btn_style", "_update_ui", "go_next", "go_back"],
    },
    "StepIndicator": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__", "_build", "set_current", "_update"],
    },
    "WizardPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__", "_build", "add_widget", "add_layout", "is_valid"],
    },
    "WelcomePage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "PasswordPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__", "_input_style", "_check_strength", "_check_match", "is_valid"],
    },
    "VaultPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "ChromePage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "GoogleAccountPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__", "_input_style", "_combo_style"],
    },
    "DrivePage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "GmailPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "YahooPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "ModelConfigPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "VerificationPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "FinishPage": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__"],
    },
    "WizardWindow": {
        "file": "wizard_mockup_v2.py",
        "methods": ["__init__", "_set_wizard", "_on_wizard_change", "_apply_dark_theme", "_nav_btn_style", "_update_ui", "go_next", "go_back"],
    },
    "QABridge": {
        "file": "wizard_qa_bridge.py",
        "methods": ["__init__", "available", "_try_init", "ask", "status"],
    },
    "QASpeechBubble": {
        "file": "wizard_qa_bridge.py",
        "methods": ["render_bubble", "render_thinking"],
    },
    "QAQueryThread": {
        "file": "wizard_qa_bridge.py",
        "methods": ["__init__", "run"],
    },
    "WizardQAUI": {
        "file": "wizard_qa_bridge.py",
        "methods": ["__init__", "_build_ui", "_check_qa_status", "_ask_question", "_on_qa_result", "_clear_chat", "_load_preset", "_on_mode_changed", "_on_model_changed", "_apply_settings", "_toggle_play", "_start_timer", "_tick"],
    },
    "QABridge": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "available", "_try_init", "ask", "status"],
    },
    "QASpeechBubble": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["render_bubble", "render_thinking"],
    },
    "QAQueryThread": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "run"],
    },
    "ActivityBar": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "_build", "_on_click", "set_active"],
    },
    "SettingsPanel": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "_build", "_apply_settings"],
    },
    "ChatPanel": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "_build"],
    },
    "ExportPanel": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "_build", "_export_svg", "_export_png", "_export_json", "_export_frames"],
    },
    "InfoPanel": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__"],
    },
    "WizardQAUI": {
        "file": "wizard_qa_bridge_v2.py",
        "methods": ["__init__", "_build_ui", "_on_activity_clicked", "_get_chat_display", "_check_qa_status", "_ask_question", "_on_qa_result", "_clear_chat", "_load_preset", "_toggle_play", "_start_timer", "_tick"],
    },
    "Vec2": {
        "file": "wizard_scene_editor.py",
        "methods": [],
    },
    "Keyframe": {
        "file": "wizard_scene_editor.py",
        "methods": [],
    },
    "Object": {
        "file": "wizard_scene_editor.py",
        "methods": [],
    },
    "Particle": {
        "file": "wizard_scene_editor.py",
        "methods": [],
    },
    "Scene": {
        "file": "wizard_scene_editor.py",
        "methods": [],
    },
    "WizardEngine": {
        "file": "wizard_scene_editor.py",
        "methods": ["__init__", "_setup_ffi", "load_preset", "add_object", "remove_object", "clear_scene", "set_pos", "set_rot", "set_scale", "set_opacity", "set_color", "clear_keys", "add_keyframe", "get_obj_count", "get_obj_info", "set_bg", "render", "render_static_svg", "render_png", "export_scene_json"],
    },
    "StyleHelper": {
        "file": "wizard_scene_editor.py",
        "methods": ["dark", "btn", "btn_danger"],
    },
    "PropertyEditor": {
        "file": "wizard_scene_editor.py",
        "methods": ["__init__", "_build", "load_object", "_on_changed", "_pick_color", "_add_keyframe", "_clear_keyframes", "_refresh_keyframes", "_delete_object"],
    },
    "SceneEditorUI": {
        "file": "wizard_scene_editor.py",
        "methods": ["__init__", "_build_ui", "_start_timer", "_tick", "_refresh_object_list", "_on_select_object", "_on_prop_changed", "_add_object", "_quick_add", "_clear_scene", "_load_preset", "_toggle_play", "_reset_time", "_change_speed", "_scrub_timeline", "_export_svg", "_export_png", "_export_json", "_export_frames"],
    },
    "WizardSVGSchemeGenerator": {
        "file": "wizard_scheme_generator.py",
        "methods": ["__init__", "_stars", "_runes", "_nebula", "_circles", "_background", "_hat", "_beard", "_face", "_coat", "_wand", "_magic", "_glow", "_accessory", "build", "to_bytes", "to_base64", "save", "save_png", "save_go_embed"],
    },
    "WizardPreviewCard": {
        "file": "wizard_scheme_generator.py",
        "methods": ["__init__", "mousePressEvent"],
    },
    "SchemeGeneratorUI": {
        "file": "wizard_scheme_generator.py",
        "methods": ["__init__", "_get_params", "regenerate", "generate_gallery", "_gallery_click", "save_svg", "save_png", "save_go"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 8,
    "files_with_Run": 0,
    "files_with_state": 0,
    "files_with_print": 0,
    "files_with_decorator": 3,
    "pass_rate": 0.0,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "svg_engine"
FILE_COUNT = 8
CLASS_COUNT = 62
