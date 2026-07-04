#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     config.py
# Domain:   Configuration
# Authority: Centralized paths, constants, and documentation for BookSystem
# DB:       None (this IS the config)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — NO hardcoded paths. All paths derived from BASE_DIR.
#              Env vars override defaults. Single source of truth.
# ============================================================================
#
# AI GUIDE — READ THIS FIRST
# ----------------------------------------------------------------------------
# This file is the single source of truth for the BookSystem project.
# It contains three documentation constants that serve as a guide:
#
#   Config.ABOUT  — One-paragraph description of what the system is
#   Config.HELP   — Quick start + command reference (for --help output)
#   Config.README — Full project documentation (was README.md (now deleted, this IS the docs))
#
# AI agents working on this codebase should read Config.README to understand:
#   - The architecture (config → schema → CLI + viewer)
#   - The 37 CLI commands and their parameters
#   - The schema (15 tables, 5 views)
#   - The viewer features (search, highlight, annotate)
#   - VBStyle compliance rules
#
# All paths are derived from BASE_DIR (this file's location).
# Env vars BOOK_DB and BOOK_SCHEMA override defaults.
# No other file should hardcode paths — import Config instead.
# ============================================================================

import os
import zlib
import base64

# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  Config
# Domain: Configuration
# Authority: Single source of truth for all paths, constants, and docs
# Dependencies: os (for path derivation and env vars)
# ============================================================================


class Config:
    # ------------------------------------------------------------------------
    # BASE DIRECTORY — everything is relative to this file's location
    # ------------------------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # ------------------------------------------------------------------------
    # FILE PATHS — derived from BASE_DIR, overridable by env vars
    # ------------------------------------------------------------------------
    DB_PATH = os.environ.get("BOOK_DB", os.path.join(BASE_DIR, "book.db"))
    MARKDOWN_PATH = os.path.join(BASE_DIR, "Binary_congf_intenaldb_gui.md")

    # ------------------------------------------------------------------------
    # ENV VAR NAMES — for documentation / help text
    # ------------------------------------------------------------------------
    ENV_DB = "BOOK_DB"

    # ------------------------------------------------------------------------
    # VERSIONS
    # ------------------------------------------------------------------------
    CLI_VERSION = "1.0"
    VIEWER_VERSION = "2.0"
    SCHEMA_VERSION = "2.0"

    # ------------------------------------------------------------------------
    # VIEWER CONSTANTS
    # ------------------------------------------------------------------------
    WINDOW_TITLE = "VBStyle Book Viewer"
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 700
    BOOK_TITLE = "VBStyle Architecture Blueprint"
    BOOK_SUBTITLE = "A Blueprint for Self-Contained C Binaries"

    # ------------------------------------------------------------------------
    # FLIPBOOK CONSTANTS
    # ------------------------------------------------------------------------
    FLIPBOOK_WIDTH = 900
    FLIPBOOK_HEIGHT = 600

    # ------------------------------------------------------------------------
    # ANNOTATION COLORS
    # ------------------------------------------------------------------------
    COLOR_HIGHLIGHT = "#fef08a"   # yellow
    COLOR_ANNOTATION = "#bfdbfe"  # blue
    COLOR_SEARCH = "#ff9633"      # orange

    # ------------------------------------------------------------------------
    # TOOLTIPS — Hover hints for viewer buttons and controls
    # Purpose: Single source for all UI tooltip text, used by BookViewer.py
    # ------------------------------------------------------------------------
    TOOLTIPS = {
        # Navigation
        "prev":          "Go to previous page (or press Left arrow)",
        "next":          "Go to next page (or press Right arrow)",
        "export":        "Save the flipbook as a standalone HTML file",
        "refresh":       "Reload the book from the database (after edits via Book.py)",
        # Search
        "search_box":    "Type a term and press Enter to highlight all matches in orange",
        "search_btn":    "Highlight all matches of the search term (orange)",
        "clear":         "Remove all search highlights",
        # Annotations
        "highlight":     "Highlight the selected text in yellow (saved to database)",
        "annotate":      "Add a note to the selected text (blue mark, saved to database)",
        # Menus
        "help":          "Show full help: all 37 CLI commands + viewer features",
        "about":         "Show a short description of the VBStyle Book System",
        "read":          "Read the current page aloud (Ctrl+Space). Click again to pause.",
        "stop":          "Stop reading (Ctrl+.)",
        "voice":         "Choose voice, speed, and pitch (Ctrl+Shift+V)",
    }

    # ------------------------------------------------------------------------
    # THEME — All GUI layout, colors, fonts, and styles in one place
    # Purpose: Single source for every visual value. Change here → entire
    #          GUI updates. No style strings scattered in BookViewer.py.
    # ------------------------------------------------------------------------
    THEME = {
        # --- Window ---
        "window_bg":          "#2a2a2a",         # dark grey behind the book
        "window_width":       1000,
        "window_height":      700,

        # --- Toolbar layout ---
        "toolbar_margin":     (8, 4, 8, 2),      # left, top, right, bottom
        "toolbar2_margin":    (8, 2, 8, 4),
        "toolbar_spacing":    20,                # gap between search and highlight

        # --- Qt widget styles ---
        "title_label_style":  "font-size: 13px; font-weight: bold; color: #1a365d;",
        "search_box_style":   "padding: 4px 8px; font-size: 13px;",
        "search_placeholder": "Search in book...",
        "highlight_btn_style": "background: #fef08a; padding: 4px 12px;",
        "annotate_btn_style":  "background: #bfdbfe; padding: 4px 12px;",
        "error_label_style":  "color: red; font-size: 14px; padding: 40px;",

        # --- Shared dialog styles (Help and About are siblings) ---
        "dialog_bg":            "#1a365d",
        "dialog_header_height": 64,
        "dialog_header_style":  "background: #1a365d; color: white; "
                                "padding: 0 20px; font-size: 16px; "
                                "font-weight: bold;",
        "dialog_header_icon":   "\U0001f4d6",  # 📖
        "dialog_header_icon_style": "font-size: 22px; color: white;",
        "dialog_header_title_style": "color: white; font-size: 16px; "
                                     "font-weight: bold;",
        "dialog_header_sub_style":   "color: #a0aec0; font-size: 12px;",
        "dialog_body_style":    "background: #fdfdfd; padding: 20px; "
                                "font-size: 13px; color: #1a1a1a; "
                                "line-height: 1.6;",
        "dialog_body_font":     "Menlo, Monaco, monospace",
        "dialog_body_size":     "12px",
        "dialog_close_style":   "background: #1a365d; color: white; "
                                "padding: 8px 24px; font-size: 13px; "
                                "font-weight: bold; border: none; "
                                "border-radius: 4px;",
        "dialog_close_hover":   "background: #2c5282;",
        "dialog_separator":     "1px solid #e2e8f0",

        # --- Help dialog (uses shared dialog styles + these) ---
        "help_dialog_width":    650,
        "help_dialog_height":   550,
        "help_dialog_title":    "VBStyle Book System — Help",
        "help_header_title":    "Help",
        "help_header_subtitle": "Quick Reference",
        "help_body_style":      "background: #fdfdfd; padding: 16px 20px; "
                                "font-family: Menlo, Monaco, monospace; "
                                "font-size: 12px; color: #1a1a1a; "
                                "line-height: 1.5;",

        # --- About dialog (uses shared dialog styles + these) ---
        "about_dialog_width":   550,
        "about_dialog_height":  450,
        "about_dialog_title":   "About VBStyle Book System",
        "about_header_title":   "About",
        "about_header_subtitle": "System Info",
        "about_app_title":      "VBStyle Book System",
        "about_app_subtitle":   "Book authoring & rendering tool",
        "about_developer_label": "Developer",
        "about_developer_name":  "Wayne's World Solutions",
        "about_developer_tagline": "Crazy solutions for even Crazier Problems :)",
        "about_contact_label":   "Contact",
        "about_contact_email":   "wlundall@yahoo.com",
        "about_license_label":   "License",
        "about_license":         "MIT — do whatever you want",
        "about_repo_label":      "Source",
        "about_repo":            "~/bin/BookSystem/",
        "about_built_with":      "Python 3 + PyQt6 + turn.js + SQLite",
        "about_body_style":     "background: #fdfdfd; padding: 20px; "
                                "font-family: Georgia, serif; "
                                "font-size: 13px; color: #333; "
                                "line-height: 1.7;",
        "about_book_title_style": "font-size: 18px; font-weight: bold; "
                                   "color: #1a365d; padding: 4px 0;",
        "about_book_sub_style":   "font-size: 13px; color: #2c5282; "
                                   "padding: 2px 0 12px 0; "
                                   "font-style: italic;",
        "about_version_style":  "font-size: 11px; color: #888; "
                                "padding: 12px 0 0 0; "
                                "border-top: 1px solid #e2e8f0; "
                                "margin-top: 12px;",
        "about_info_label_style": "font-size: 11px; color: #888; "
                                   "font-weight: bold; padding: 0;",
        "about_info_value_style": "font-size: 12px; color: #333; "
                                   "padding: 0 0 6px 0;",
        "about_info_separator":  "1px solid #f0f0f0",

        # --- Flipbook page colors ---
        "page_bg":            "#fdfdfd",         # page background (off-white)
        "page_text":          "#1a1a1a",         # body text color
        "page_font_family":   "Georgia, 'Times New Roman', serif",
        "page_font_size":     "13px",
        "page_line_height":   "1.6",
        "page_padding":       "40px 35px",

        # --- Cover colors ---
        "cover_gradient":     "linear-gradient(135deg, #1a365d 0%, #2c5282 100%)",
        "cover_bg_solid":     "#1a365d",
        "cover_text":         "white",
        "cover_title_size":   "28px",
        "cover_subtitle_size": "14px",
        "cover_hint_size":    "12px",

        # --- Headings ---
        "h2_size":            "18px",
        "h2_color":           "#1a365d",
        "h3_size":            "15px",
        "h3_color":           "#2c5282",

        # --- Page header/footer ---
        "header_color":       "#888",
        "header_size":        "10px",
        "footer_color":       "#aaa",
        "footer_size":        "9px",
        "footer_border":      "#eee",

        # --- Code blocks ---
        "code_bg":            "#f4f4f4",
        "code_border":        "#ddd",
        "code_accent":        "#2c5282",         # left border accent
        "code_text":          "#333",
        "code_font_family":   "'Menlo', 'Monaco', 'Courier New', monospace",
        "code_font_size":     "11px",
        "code_line_height":   "1.4",

        # --- Callouts ---
        "callout_bg":         "#fef3c7",
        "callout_border":     "#f59e0b",
        "callout_font_size":  "12px",

        # --- Inline code ---
        "inline_code_bg":     "#f0f0f0",
        "inline_code_size":   "11px",

        # --- Tables ---
        "table_th_bg":        "#e2e8f0",
        "table_border":       "#cbd5e0",
        "table_font_size":    "11px",

        # --- Blockquote ---
        "blockquote_border":  "#6897bb",
        "blockquote_bg":      "#f7f7f7",
        "blockquote_text":    "#555",

        # --- Search highlight (orange) ---
        "search_mark_bg":     "#ff9633",
        "search_mark_text":   "#000",

        # --- User highlight (yellow) ---
        "user_hl_bg":         "#fef08a",
        "user_hl_border":     "#eab308",

        # --- User annotation (blue) ---
        "user_annot_bg":      "#bfdbfe",
        "user_annot_border":  "#2563eb",
        "user_annot_tooltip_bg": "#1e3a5f",
        "user_annot_tooltip_text": "white",

        # --- Annotation panel ---
        "annot_panel_bg":     "white",
        "annot_panel_border": "#ccc",
        "annot_panel_shadow": "0 4px 12px rgba(0,0,0,0.15)",
        "annot_panel_width":  "280px",
        "annot_panel_title_color": "#1a365d",
        "annot_item_hover_bg": "#f0f4f8",
        "annot_text_color":   "#555",
        "annot_note_color":   "#2563eb",
        "annot_remove_color": "#dc2626",

        # --- Bold/italic ---
        "bold_color":         "#1a365d",
        "italic_color":       "#555",
    }

    # ------------------------------------------------------------------------
    # ICONS — Unicode glyphs or file paths for toolbar buttons
    # Purpose: Single source for all icons. Values can be:
    #   - Unicode emoji/glyph (used directly in button text)
    #   - File path (loaded as QIcon when icon support is added)
    # Currently buttons use text + glyph. When icon support is added,
    # BookViewer.py will read these and load from ICON_DIR if path is set.
    # ------------------------------------------------------------------------
    ICON_DIR = ""  # if set, icons loaded from this directory

    ICONS = {
        "prev":          "\u25c0",   # ◀
        "next":          "\u25b6",   # ▶
        "search":        "\U0001f50d",  # 🔍
        "clear":         "\u2717",   # ✗
        "highlight":     "\u270f",   # ✏
        "annotate":      "\U0001f4dd",  # 📝
        "export":        "\U0001f4be",  # 💾
        "refresh":       "\u21bb",   # ↻
        "help":          "?",
        "about":         "i",
        "close":         "\u2715",   # ✕
        "book":          "\U0001f4d6",  # 📖
        "bookmark":      "\U0001f516",  # 🔖
        "settings":      "\u2699",   # ⚙
        "error":         "\u26a0",   # ⚠
        "success":       "\u2713",   # ✓
        "read":          "\U0001f50a",  # 🔊
        "pause":         "\u23f8",   # ⏸
        "stop":          "\u23f9",   # ⏹
        "voice":         "\U0001f3a4",  # 🎤
    }

    # ------------------------------------------------------------------------
    # SHORTCUTS — Keyboard shortcuts for all actions
    # Purpose: Single source for key bindings. BookViewer.py reads these
    #          to wire QShortcut objects. Change here → GUI updates.
    # Format:  Qt key sequence strings (e.g. "Ctrl+F", "Left", "Right")
    # ------------------------------------------------------------------------
    SHORTCUTS = {
        "prev_page":     "Left",
        "next_page":     "Right",
        "search":        "Ctrl+F",
        "clear_search":  "Escape",
        "highlight":     "Ctrl+H",
        "annotate":      "Ctrl+N",
        "export":        "Ctrl+E",
        "refresh":       "Ctrl+R",
        "help":          "F1",
        "about":         "F2",
        "toggle_panel":  "Ctrl+Shift+A",
        "close":         "Ctrl+Q",
        "read":          "Ctrl+Space",
        "stop":          "Ctrl+.",
        "voice_picker":  "Ctrl+Shift+V",
    }

    # ------------------------------------------------------------------------
    # BUTTONS — Button labels and visibility flags
    # Purpose: Control which buttons appear and what they say.
    #          A settings editor can toggle visibility without code changes.
    # ------------------------------------------------------------------------
    BUTTONS = {
        # (label, visible, key for tooltip, key for icon)
        "prev":        {"label": "Prev",      "visible": True,  "icon": "prev"},
        "next":        {"label": "Next",      "visible": True,  "icon": "next"},
        "export":      {"label": "Export",    "visible": True,  "icon": "export"},
        "refresh":     {"label": "Refresh",   "visible": True,  "icon": "refresh"},
        "help":        {"label": "Help",      "visible": True,  "icon": "help"},
        "about":       {"label": "About",     "visible": True,  "icon": "about"},
        "search":      {"label": "Search",    "visible": True,  "icon": "search"},
        "clear":       {"label": "Clear",     "visible": True,  "icon": "clear"},
        "highlight":   {"label": "Highlight", "visible": True,  "icon": "highlight"},
        "annotate":    {"label": "Annotate",  "visible": True,  "icon": "annotate"},
        "read":        {"label": "Read",      "visible": True,  "icon": "read"},
        "stop":        {"label": "Stop",      "visible": True,  "icon": "stop"},
        "voice":       {"label": "Voice",     "visible": True,  "icon": "voice"},
    }

    # ------------------------------------------------------------------------
    # MENU — Menu bar structure
    # Purpose: Define menu items in data, not code. A future menu bar
    #          can be built by iterating this dict. Each item maps to
    #          a dispatch command or a viewer method.
    # ------------------------------------------------------------------------
    MENU = {
        "File": {
            "Export HTML...":   "export",
            "Refresh from DB":  "refresh",
            "---":              None,
            "Quit":             "close",
        },
        "Edit": {
            "Highlight Selection":  "highlight",
            "Annotate Selection...": "annotate",
        },
        "View": {
            "Previous Page":    "prev",
            "Next Page":        "next",
            "---":              None,
            "Clear Search":     "clear_search",
        },
        "Search": {
            "Find...":          "search",
        },
        "Help": {
            "Help...":          "help",
            "About...":         "about",
        },
    }

    # ------------------------------------------------------------------------
    # WINDOW — Window behavior flags
    # Purpose: Window properties that a settings editor can toggle
    # ------------------------------------------------------------------------
    WINDOW = {
        "title":            "VBStyle Book Viewer",
        "width":            1000,
        "height":           700,
        "min_width":        800,
        "min_height":       600,
        "resizable":        True,
        "fullscreen":       False,
        "always_on_top":    False,
        "remember_size":    True,
        "remember_position": True,
        "show_statusbar":   True,
        "show_menubar":     False,   # when True, build from MENU dict
        "show_toolbar":     True,
    }

    # ------------------------------------------------------------------------
    # SEARCH — Search behavior settings
    # ------------------------------------------------------------------------
    SEARCH = {
        "min_chars":        2,
        "highlight_color":  "#ff9633",
        "case_sensitive":   False,
        "whole_word":       False,
        "regex":            False,
    }

    # ------------------------------------------------------------------------
    # ANNOTATION — Annotation behavior settings
    # ------------------------------------------------------------------------
    ANNOTATION = {
        "highlight_color":  "#fef08a",
        "annotation_color": "#bfdbfe",
        "show_panel":       False,
        "panel_position":   "top-right",
        "auto_save":        True,
        "prompt_for_note":  True,
    }

    # ------------------------------------------------------------------------
    # FLIPBOOK — turn.js behavior settings
    # ------------------------------------------------------------------------
    FLIPBOOK = {
        "width":            900,
        "height":           600,
        "display":          "double",
        "auto_center":      True,
        "acceleration":     True,
        "gradients":        True,
        "elevation":        50,
        "duration":         600,
    }

    # ------------------------------------------------------------------------
    # TTS — Text-to-Speech settings (Web Speech API, offline, no deps)
    # Purpose: Read book aloud for users on the move (plane, car, etc.)
    #          No wifi needed — voices are local to macOS.
    # ------------------------------------------------------------------------
    TTS = {
        "enabled":           True,
        "default_voice":     "",        # empty = system default voice
        "rate":              1.0,       # 0.1 (slow) to 10.0 (fast), 1.0 = normal
        "pitch":             1.0,       # 0 (low) to 2 (high), 1.0 = normal
        "volume":            1.0,       # 0 (silent) to 1 (max)
        "auto_flip":         True,      # flip to next page when current finishes
        "word_highlight":    True,      # highlight each word as spoken
        "word_highlight_bg": "#ff9633", # color for current word being spoken
        "word_highlight_color": "#000", # text color for spoken word
        "read_selection_only": False,   # if True, only read highlighted text
    }

    # ------------------------------------------------------------------------
    # STATUS MESSAGES — Text shown in status bar
    # Purpose: Single source for all status messages, ready for i18n
    # ------------------------------------------------------------------------
    STATUS = {
        "loading":          "Loading...",
        "loaded":           "{count} pages loaded",
        "prev_page":        "Previous page",
        "next_page":        "Next page",
        "search_results":   "Search '{term}': {count} matches",
        "no_results":       "No matches for '{term}'",
        "search_cleared":   "Search cleared",
        "highlighted":      "Highlighted selection",
        "annotated":        "Annotated selection",
        "exported":         "Exported to {path}",
        "refreshed":        "Refreshed from database",
        "no_db":            "No database connection",
        "db_error":         "Error: {message}",
        "tts_reading":      "Reading page {page}...",
        "tts_paused":       "Reading paused",
        "tts_resumed":      "Reading resumed",
        "tts_stopped":      "Reading stopped",
        "tts_finished":     "Finished reading page {page}",
        "tts_no_voices":    "No TTS voices available on this system",
        "tts_no_text":      "No text to read on this page",
    }

    # ------------------------------------------------------------------------
    # ERROR MESSAGES — User-facing error text WITH actionable steps
    # Each error has: "message" (what went wrong) + "action" (what to do)
    # The GUI can show the message and offer the action as a button.
    # ------------------------------------------------------------------------
    ERRORS = {
        "db_not_found": {
            "message": "Database not found: {path}",
            "action":  "Initialize a new database",
            "command": "python3 Book.py init",
            "details": "This will create a fresh book.db from the embedded schema. "
                       "Then run: python3 Book.py import-md Binary_congf_intenaldb_gui.md "
                       "to populate it with the book content.",
        },
        "db_empty": {
            "message": "Database exists but has no content (0 rows in sections).",
            "action":  "Import the book markdown",
            "command": "python3 Book.py import-md Binary_congf_intenaldb_gui.md",
            "details": "The database was created but never populated. "
                       "Import the markdown source to fill it with chapters and sections.",
        },
        "schema_missing": {
            "message": "Schema file not found: {path}",
            "action":  "Use embedded schema from config.py",
            "command": "python3 Book.py init",
            "details": "The .sql file is missing, but config.py has the schema embedded. "
                       "Book.py will use Config.SCHEMA_SQL if the file is not found.",
        },
        "no_selection": {
            "message": "Select text first, then click {button}.",
            "action":  "Click in the book page and drag to select text",
            "command": None,
            "details": "Highlight and Annotate work on the currently selected text. "
                       "Click on a page, drag across the text you want to mark, "
                       "then click the button again.",
        },
        "no_section_id": {
            "message": "Cannot {action} this page (no section ID).",
            "action":  "Navigate to a content page (not cover/TOC)",
            "command": None,
            "details": "Cover pages, table of contents, and glossary pages "
                       "do not have section IDs. Annotations only work on "
                       "actual chapter content pages.",
        },
        "bridge_not_ready": {
            "message": "Bridge not ready — page is still loading.",
            "action":  "Wait for the book to finish loading, then try again",
            "command": None,
            "details": "The JavaScript bridge between Python and the web page "
                       "is not yet connected. Wait a moment for the page to "
                       "finish rendering, then retry.",
        },
        "save_failed": {
            "message": "Error saving annotation: {message}",
            "action":  "Check database permissions and try again",
            "command": "ls -la {db_path}",
            "details": "The annotation could not be written to the database. "
                       "This may be a permissions issue or the database may be locked. "
                       "Verify the file is writable.",
        },
        "no_db_connection": {
            "message": "No database connection.",
            "action":  "Verify book.db exists and is valid",
            "command": "python3 Book.py stats",
            "details": "The viewer could not open the database. Run 'Book.py stats' "
                       "from the terminal to check if the database is accessible.",
        },
        "export_failed": {
            "message": "Export failed: {message}",
            "action":  "Choose a different file path and try again",
            "command": None,
            "details": "The flipbook could not be exported. The destination "
                       "path may be read-only or the disk may be full.",
        },
        "import_failed": {
            "message": "Import failed: {message}",
            "action":  "Verify the markdown file exists and is valid",
            "command": "python3 Book.py import-md {file}",
            "details": "The markdown file could not be imported. Check that "
                       "the file path is correct and the file contains valid "
                       "markdown with chapter and section headers.",
        },
    }

    # ------------------------------------------------------------------------
    # SCHEMA SQL — The complete database schema, embedded in config.py
    # Purpose: Single source of truth for the schema. Book.py uses this
    #          when the .sql file is missing or BOOK_SCHEMA env var is unset.
    #          The .sql file is kept for backwards compatibility and direct
    #          sqlite3 CLI usage, but config.py is the authority.
    # ------------------------------------------------------------------------
    SCHEMA_SQL = """\
-- ============================================================================
-- VBStyle Book Database Schema (v2)
-- Book: "From Stress & Mess to VB Bless"
-- Each row = one section/page. Query by chapter, part, or rule tag.
--
-- ============================================================================
-- WHY A DATABASE FOR A BOOK?
-- ============================================================================
--
-- The book "From Stress & Mess to VB Bless" documents 71 VBStyle rules,
-- 17 chapters, and dozens of code samples across Python and C. Managing
-- this in a flat markdown file creates problems:
--
--   1. No queryable structure. "Which sections cover @tuples?" requires
--      full-text grep, which is slow and error-prone (matches @tuplesomething).
--
--   2. No cross-reference tracking. "See Chapter 8" links are invisible
--      to tooling — you can't find broken refs or build a dependency graph.
--
--   3. No rule-to-section mapping. The 71 VBStyle rules are the backbone
--      of the book, but in markdown they're just prose. In a DB, each rule
--      is a first-class row linked to the sections that teach it.
--
--   4. No structured comparison tables. The book uses comparison matrices
--      (variant vs variant, pros vs cons). In markdown these are text —
--      unqueryable. In a DB they're rows and columns.
--
--   5. No multi-code-block sections. Many sections have 2-5 code blocks
--      in different languages (C + SQL + bash), interleaved with text
--      paragraphs. A single TEXT column can't represent that cleanly,
--      and a separate code_samples table without ordering relative to
--      text blocks can't represent interleaving (text → code → text).
--
-- WHY SQLITE SPECIFICALLY?
--
--   - Single-file, zero-config, built into macOS (no server, no install)
--   - The book itself documents SQLite patterns (Chapters 2, 3, 8) —
--     using SQLite for the book's own storage practices what it preaches
--   - WAL mode for concurrent read during editing
--   - Foreign keys for relational integrity
--   - Views for markdown export (v_export_chapter assembles sections
--     into ordered markdown — no external "compiler" needed)
--
-- WHY THIS STRUCTURE (parts → chapters → sections)?
--
--   - Parts: top-level divisions (Foundations, Variants, Operations)
--   - Chapters: numbered chapters within parts (1-17)
--   - Sections: numbered sub-sections within chapters (1.1, 1.2, 1.1a)
--     Each section is one atomic content unit — a page, a concept, a
--     code walkthrough. This is the unit of query, edit, and export.
--
-- WHY JUNCTION TABLES INSTEAD OF COMMA-SEPARATED TEXT?
--
--   v1 used rule_tags TEXT ("@tuples,@nofiles,@hardcode") — this is an
--   anti-pattern. It makes queries require LIKE '%tuples%' which is:
--     - Slow (full scan, no index)
--     - Wrong (matches @tuplesomething)
--     - Unnormalized (can't enforce FK to rules table)
--
--   v2 uses section_rules(section_id, rule_id) — a proper junction table
--   with foreign keys. Now: JOIN section_rules JOIN rules WHERE tag='@tuples'
--   is indexed, exact, and referentially enforced.
--
-- WHY section_type INSTEAD OF SEPARATE TABLES FOR PREFACE/APPENDIX?
--
--   Preface, conventions, content, summary, appendix, glossary — these
--   all share the same structure (title, content, code samples, page
--   number). They differ only in how they're rendered and ordered.
--   A type column is simpler than 6 tables with identical schemas.
--
-- WHY VIEWS INSTEAD OF A "COMPILATION ENGINE"?
--
--   The export problem is: "assemble sections into ordered markdown."
--   That's SELECT + ORDER BY — a query, not a compiler. v_export_chapter
--   is a SQL view that does exactly this. No build system, no validation
--   pass, no error reporting layer needed. If the data is wrong, the
--   query returns wrong output — same as any DB.
--
-- WHAT WE EXPLICITLY REJECTED (AND WHY):
--
--   - section_history table: Git on exported markdown handles versioning.
--     Adding history tables for a single-author book is complexity
--     without payoff.
--   - Rule evaluation engine: Our rules table is REFERENCE MATERIAL the
--     book teaches — the 71 VBStyle Python coding rules. It's not a
--     rules engine that validates the DB's own content. Different concept.
--   - Build graph / validation pass: Over-engineered. The "build" is
--     a SELECT query. The "validation" is running the query and reading
--     the output.
--
-- ============================================================================
-- CHANGELOG (v1 → v2)
-- ============================================================================
--
--   - sec_num TEXT + sort_order INTEGER (was REAL, couldn't store "1.1a")
--   - Junction tables for rule_tags (was comma-separated TEXT)
--   - content_blocks table (replaces sections.content TEXT + code_samples)
--     — supports interleaved text/code/table/callout blocks ordered within
--     each section, so export view produces correct paragraph → code →
--     paragraph ordering instead of "all code then all text"
--   - comparison_tables table (was lost in markdown content)
--   - section_type column (preface, content, summary, appendix, glossary)
--   - cross_refs table (queryable cross-references)
--   - chapter_summaries table
--   - schema_meta table (practice what Chapter 15 preaches)
--   - rule_relations junction table (was comma-separated related_rules)
--   - Timestamps on sections and chapters
--   - 5 export/query views (v_export_chapter, v_chapter_outline,
--     v_rules_index, v_glossary_index, v_cross_ref_graph)
-- ============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================================
-- SCHEMA META — Version tracking (see Chapter 15)
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '2');
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('created_at', datetime('now'));

-- ============================================================================
-- PARTS — Top-level book divisions
-- ============================================================================
CREATE TABLE IF NOT EXISTS parts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    part_num    INTEGER NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    subtitle    TEXT,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ============================================================================
-- CHAPTERS — Chapters within parts
-- ============================================================================
CREATE TABLE IF NOT EXISTS chapters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id     INTEGER NOT NULL,
    ch_num      INTEGER NOT NULL,
    title       TEXT NOT NULL,
    subtitle    TEXT,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
    UNIQUE(part_id, ch_num)
);

-- ============================================================================
-- SECTIONS — Pages within chapters (each row = one page/section)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id    INTEGER NOT NULL,
    sec_num       TEXT NOT NULL,    -- '1.1', '1.2', '1.1a' for display
    sort_order    INTEGER NOT NULL, -- 1, 2, 3... for ORDER BY
    title         TEXT NOT NULL,
    section_type  TEXT NOT NULL DEFAULT 'content',
                  -- 'preface', 'conventions', 'content', 'summary',
                  -- 'appendix', 'glossary', 'who_for'
    word_count    INTEGER DEFAULT 0,
    page_num      INTEGER,          -- estimated page number for print layout
    page_confirmed INTEGER DEFAULT 0, -- 1 = page_num verified against layout
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE(chapter_id, sec_num)
);

-- ============================================================================
-- RULES — The 71 VBStyle rules (reference table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_num    INTEGER NOT NULL UNIQUE,
    tag         TEXT NOT NULL UNIQUE,     -- e.g. "@decorators"
    category    TEXT NOT NULL,            -- 'meta', 'syntax', 'header', 'dispatch',
                                          -- 'db', 'analysis', 'validation'
    short_desc  TEXT NOT NULL,            -- one-line description
    full_desc   TEXT,                     -- detailed explanation
    example_bad TEXT,                     -- code that violates the rule
    example_good TEXT,                    -- code that follows the rule
    chapter_id  INTEGER,                  -- primary chapter that covers this rule
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

-- ============================================================================
-- RULE RELATIONS — Many-to-many: which rules are related to which
-- (Replaces comma-separated related_rules TEXT column)
-- ============================================================================
CREATE TABLE IF NOT EXISTS rule_relations (
    rule_id         INTEGER NOT NULL,
    related_rule_id INTEGER NOT NULL,
    note            TEXT,                 -- optional: why they're related
    PRIMARY KEY(rule_id, related_rule_id),
    FOREIGN KEY(rule_id)         REFERENCES rules(id) ON DELETE CASCADE,
    FOREIGN KEY(related_rule_id) REFERENCES rules(id) ON DELETE CASCADE
);

-- ============================================================================
-- SECTION RULES — Many-to-many: which rules are covered in which section
-- (Replaces comma-separated rule_tags TEXT column in sections)
-- ============================================================================
CREATE TABLE IF NOT EXISTS section_rules (
    section_id  INTEGER NOT NULL,
    rule_id     INTEGER NOT NULL,
    PRIMARY KEY(section_id, rule_id),
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY(rule_id)    REFERENCES rules(id) ON DELETE CASCADE
);

-- ============================================================================
-- CHAPTER RULES — Many-to-many: which rules are covered in which chapter
-- (Replaces comma-separated rules_covered TEXT column in chapters)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chapter_rules (
    chapter_id  INTEGER NOT NULL,
    rule_id     INTEGER NOT NULL,
    PRIMARY KEY(chapter_id, rule_id),
    FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    FOREIGN KEY(rule_id)    REFERENCES rules(id) ON DELETE CASCADE
);

-- ============================================================================
-- CONTENT BLOCKS — Ordered text + code blocks within a section
-- (Replaces both sections.content TEXT and code_samples table.
--  Solves interleaving: a section can be text → code → text → code → table,
--  with each block ordered by block_order. This is how real book sections
--  work — paragraphs and code blocks alternate, not "all code then all text.")
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_blocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  INTEGER NOT NULL,
    block_type  TEXT NOT NULL,        -- 'text' | 'code' | 'table' | 'callout'
    block_order INTEGER NOT NULL,     -- 1, 2, 3... ordering within section
    content     TEXT NOT NULL,        -- markdown text / code source / callout body
    lang        TEXT,                 -- for block_type='code': 'python','c','sql','bash'
    caption     TEXT,                 -- optional caption above the block
    table_id    INTEGER,              -- for block_type='table': FK to comparison_tables
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY(table_id)   REFERENCES comparison_tables(id) ON DELETE SET NULL
);

-- ============================================================================
-- COMPARISON TABLES — Structured comparison matrices
-- (Not lost in markdown — queryable rows and columns)
-- ============================================================================
CREATE TABLE IF NOT EXISTS comparison_tables (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id    INTEGER NOT NULL,
    title         TEXT NOT NULL,
    column_headers TEXT NOT NULL,     -- JSON array: ["Aspect", "wcmd", "Cleaner"]
    rows          TEXT NOT NULL,      -- JSON array of arrays: [["Lines","2061","560"],...]
    sort_order    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
);

-- ============================================================================
-- CROSS REFERENCES — Queryable "see Chapter X" / "see section Y.Z"
-- ============================================================================
CREATE TABLE IF NOT EXISTS cross_refs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_section  INTEGER NOT NULL,
    to_section    INTEGER,            -- NULL if reference is chapter-level only
    to_chapter    INTEGER,            -- NULL if reference is section-level only
    ref_text      TEXT,               -- "see Chapter 8 for Tuple3 details"
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(from_section) REFERENCES sections(id)  ON DELETE CASCADE,
    FOREIGN KEY(to_section)   REFERENCES sections(id)  ON DELETE SET NULL,
    FOREIGN KEY(to_chapter)   REFERENCES chapters(id)  ON DELETE SET NULL
);

-- ============================================================================
-- CHAPTER SUMMARIES — End-of-chapter recap (O'Reilly convention)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chapter_summaries (
    chapter_id  INTEGER PRIMARY KEY,
    summary     TEXT NOT NULL,        -- markdown bullet list
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- ============================================================================
-- GLOSSARY — Terms used in the book
-- ============================================================================
CREATE TABLE IF NOT EXISTS glossary (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT NOT NULL UNIQUE,
    definition  TEXT NOT NULL,
    chapter_id  INTEGER,              -- first chapter where term appears
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

-- ============================================================================
-- ANNOTATIONS — User highlights and notes on section content
-- (Persists across page reloads. Each annotation anchors to a section
--  and stores the selected text so it can be re-applied after re-render.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id      INTEGER NOT NULL,
    selected_text   TEXT NOT NULL,        -- the text that was highlighted
    note_text       TEXT,                 -- optional user note (empty = highlight only)
    color           TEXT DEFAULT '#fef08a', -- highlight color (yellow default)
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
);

-- ============================================================================
-- INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_chapters_part       ON chapters(part_id);
CREATE INDEX IF NOT EXISTS idx_chapters_num        ON chapters(part_id, ch_num);

CREATE INDEX IF NOT EXISTS idx_sections_chapter    ON sections(chapter_id);
CREATE INDEX IF NOT EXISTS idx_sections_sort       ON sections(chapter_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_sections_page       ON sections(page_num);
CREATE INDEX IF NOT EXISTS idx_sections_type       ON sections(section_type);

CREATE INDEX IF NOT EXISTS idx_rules_category      ON rules(category);
CREATE INDEX IF NOT EXISTS idx_rules_chapter       ON rules(chapter_id);
CREATE INDEX IF NOT EXISTS idx_rules_tag           ON rules(tag);

CREATE INDEX IF NOT EXISTS idx_section_rules_sec   ON section_rules(section_id);
CREATE INDEX IF NOT EXISTS idx_section_rules_rule  ON section_rules(rule_id);

CREATE INDEX IF NOT EXISTS idx_chapter_rules_ch    ON chapter_rules(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapter_rules_rule  ON chapter_rules(rule_id);

CREATE INDEX IF NOT EXISTS idx_rule_relations_a    ON rule_relations(rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_relations_b    ON rule_relations(related_rule_id);

CREATE INDEX IF NOT EXISTS idx_content_blocks_sec  ON content_blocks(section_id, block_order);

CREATE INDEX IF NOT EXISTS idx_comparison_sec      ON comparison_tables(section_id);

CREATE INDEX IF NOT EXISTS idx_cross_refs_from     ON cross_refs(from_section);
CREATE INDEX IF NOT EXISTS idx_cross_refs_to_sec   ON cross_refs(to_section);
CREATE INDEX IF NOT EXISTS idx_cross_refs_to_ch    ON cross_refs(to_chapter);

CREATE INDEX IF NOT EXISTS idx_glossary_term       ON glossary(term);
CREATE INDEX IF NOT EXISTS idx_glossary_chapter    ON glossary(chapter_id);

CREATE INDEX IF NOT EXISTS idx_annotations_sec     ON annotations(section_id);

-- ============================================================================
-- TRIGGERS — Auto-update updated_at timestamps
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS trg_parts_updated
    AFTER UPDATE ON parts
    FOR EACH ROW
    BEGIN
        UPDATE parts SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_chapters_updated
    AFTER UPDATE ON chapters
    FOR EACH ROW
    BEGIN
        UPDATE chapters SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_sections_updated
    AFTER UPDATE ON sections
    FOR EACH ROW
    BEGIN
        UPDATE sections SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_summaries_updated
    AFTER UPDATE ON chapter_summaries
    FOR EACH ROW
    BEGIN
        UPDATE chapter_summaries SET updated_at = datetime('now') WHERE chapter_id = OLD.chapter_id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_meta_updated
    AFTER UPDATE ON schema_meta
    FOR EACH ROW
    BEGIN
        UPDATE schema_meta SET updated_at = datetime('now') WHERE key = OLD.key;
    END;

-- ============================================================================
-- VIEWS — Markdown export queries (not a "compilation engine" — just SELECTs)
-- ============================================================================

-- v_export_chapter: Assemble all sections of a chapter into ordered markdown
-- Interleaves text and code blocks correctly via content_blocks.block_order.
-- Usage: SELECT line FROM v_export_chapter WHERE ch_num = 1 ORDER BY line_order;
CREATE VIEW IF NOT EXISTS v_export_chapter AS
-- Section headers
SELECT
    c.ch_num,
    c.title AS ch_title,
    s.sort_order * 100000 AS line_order,
    '## ' || s.sec_num || ' ' || s.title AS line
FROM chapters c
JOIN sections s ON s.chapter_id = c.id

UNION ALL

-- Content blocks (text, code, callout — interleaved by block_order)
SELECT
    c.ch_num,
    c.title AS ch_title,
    s.sort_order * 100000 + cb.block_order AS line_order,
    CASE
        WHEN cb.block_type = 'code'
            THEN '```' || COALESCE(cb.lang, '') || char(10) || cb.content || char(10) || '```'
        WHEN cb.block_type = 'callout'
            THEN '> **' || COALESCE(cb.caption, 'Note') || ':** ' || cb.content
        ELSE cb.content
    END AS line
FROM chapters c
JOIN sections s ON s.chapter_id = c.id
JOIN content_blocks cb ON cb.section_id = s.id

ORDER BY ch_num, line_order;

-- v_chapter_outline: Quick TOC view (chapter + section titles only)
-- Usage: SELECT * FROM v_chapter_outline WHERE ch_num = 1;
CREATE VIEW IF NOT EXISTS v_chapter_outline AS
SELECT
    p.part_num,
    c.ch_num,
    c.title AS ch_title,
    s.sec_num,
    s.title AS sec_title,
    s.section_type,
    s.word_count,
    s.page_num,
    s.sort_order
FROM parts p
JOIN chapters c ON c.part_id = p.id
JOIN sections s ON s.chapter_id = c.id
ORDER BY p.part_num, c.ch_num, s.sort_order;

-- v_rules_index: All rules with their primary chapter and section coverage
-- Usage: SELECT * FROM v_rules_index ORDER BY rule_num;
CREATE VIEW IF NOT EXISTS v_rules_index AS
SELECT
    r.rule_num,
    r.tag,
    r.category,
    r.short_desc,
    c.ch_num AS primary_chapter,
    (SELECT COUNT(*) FROM section_rules sr WHERE sr.rule_id = r.id) AS section_count,
    (SELECT COUNT(*) FROM chapter_rules cr WHERE cr.rule_id = r.id) AS chapter_count
FROM rules r
LEFT JOIN chapters c ON c.id = r.chapter_id
ORDER BY r.rule_num;

-- v_glossary_index: Glossary terms with first-appearance chapter
-- Usage: SELECT * FROM v_glossary_index ORDER BY term;
CREATE VIEW IF NOT EXISTS v_glossary_index AS
SELECT
    g.term,
    g.definition,
    c.ch_num AS first_chapter,
    c.title AS chapter_title
FROM glossary g
LEFT JOIN chapters c ON c.id = g.chapter_id
ORDER BY g.term;

-- v_cross_ref_graph: All cross-references with resolved titles
-- Usage: SELECT * FROM v_cross_ref_graph WHERE from_ch_num = 1;
CREATE VIEW IF NOT EXISTS v_cross_ref_graph AS
SELECT
    fc.ch_num AS from_ch_num,
    fc.title AS from_chapter,
    fs.sec_num AS from_sec,
    fs.title AS from_section,
    tc.ch_num AS to_ch_num,
    tc.title AS to_chapter,
    ts.sec_num AS to_sec,
    ts.title AS to_section,
    cr.ref_text
FROM cross_refs cr
JOIN sections fs ON fs.id = cr.from_section
JOIN chapters fc ON fc.id = fs.chapter_id
LEFT JOIN sections ts ON ts.id = cr.to_section
LEFT JOIN chapters tc ON tc.id = cr.to_chapter
ORDER BY fc.ch_num, fs.sort_order;
"""

    # ------------------------------------------------------------------------
    # TURNJS_COMPRESSED — turn.js library, zlib-compressed + base64-encoded
    # Purpose: Embedded so no external .js file is needed. Decompressed at
    #          runtime by GetTurnJs(). Saves 56% vs raw (23KB → 10KB).
    #          BookViewer.py and Book.py export-flipbook both use this.
    # ------------------------------------------------------------------------
    TURNJS_COMPRESSED = (
        "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"
    )

    # ------------------------------------------------------------------------
    # ABOUT — One-paragraph system description
    # Purpose: Quick orientation for AI agents and new developers
    # ------------------------------------------------------------------------
    ABOUT = (
        "VBStyle Book System — A SQLite-backed book authoring and rendering "
        "system for the 'VBStyle Architecture Blueprint', a technical book "
        "documenting self-contained C binaries with embedded SQLite, MySQL "
        "ingestion, and PyQt6 configuration interfaces. "
        "Three components share one database: "
        "(1) config.py (Config.SCHEMA_SQL) — 15 tables, 5 views, FK cascades; "
        "(2) Book.py — CLI with 37 commands for add/update/remove/import/"
        "export/search/check/annotate; "
        "(3) BookViewer.py — PyQt6 + QWebEngineView rendering turn.js "
        "page-flip animation with search, highlight, and annotate features. "
        "All paths and constants are centralized in config.py. "
        "All code follows VBStyle rules (Run dispatch, Tuple3 returns, "
        "no decorators, no print, PascalCase, UPPERCASE constants)."
    )

    # ------------------------------------------------------------------------
    # HELP — Quick start + command reference
    # Purpose: Output for `Book.py help` and `BookViewer.py --help`
    # ------------------------------------------------------------------------
    HELP = """\
VBStyle Book System — Quick Reference
======================================

QUICK START
-----------
  python3 Book.py init                          Create DB from schema
  python3 Book.py import-md Binary_congf_intenaldb_gui.md  Import book
  python3 Book.py stats                         Row counts per table
  python3 Book.py outline                       Table of contents
  python3 BookViewer.py                         Launch flipbook viewer
  python3 Book.py export-flipbook book.html     Export standalone HTML

CLI COMMANDS (37)
-----------------
  Setup:
    init                                        Create DB from schema
    stats                                       Row counts per table

  Add:
    add-part <num> <title> [subtitle]
    add-chapter <pid> <num> <title> [subtitle]
    add-section <cid> <sec> <sort> <title> [type]
    add-block <sid> <type> <order> <content> [lang]
    add-rule <num> <tag> <cat> <desc> [ch_id]
    link-rule <rid> <section|chapter> <id>
    add-glossary <term> <def> [ch_id]
    add-summary <ch_id> <summary>
    add-xref <from_sec> <to_ch> [to_sec] <text>
    add-table <sid> <title> <headers_json> <rows_json>

  Update:
    update-part <num> [title] [subtitle]
    update-chapter <num> [title] [subtitle]
    update-section <sid> [title] [type] [wc] [page]
    update-block <bid> [content] [lang] [caption] [order]
    update-glossary <term> [new_term] [def] [ch_id]
    update-rule <num> [tag] [cat] [desc] [ch_id]

  Remove:
    remove-section <sid>
    remove-block <bid>
    remove-xref <xid>

  Import & Export:
    import-md <file>
    export <ch_num>
    export-all
    export-flipbook <file> [title]

  Query & Check:
    search <term>
    check
    outline [ch_num]
    list-rules
    list-glossary
    list-xrefs [ch_num]
    list-annotations [sid]
    info <ch_num>
    state

  Annotations:
    add-annotation <sid> <text> [note] [color]
    remove-annotation <id>

VIEWER FEATURES
---------------
  Page flip       Drag pages or use arrow keys
  Search          Type in search box → orange highlights
  Highlight       Select text → click Highlight → yellow, saved to DB
  Annotate        Select text → click Annotate → blue + note, saved to DB
  Export HTML     Save flipbook as standalone .html
  Refresh         Reload from DB after edits

ENV VARS
--------
  BOOK_DB         Path to book.db (default: ./book.db)

For full documentation, see Config.README (embedded in config.py)
"""

    # ------------------------------------------------------------------------
    # README — Full project documentation
    # Purpose: AI guide + full project documentation (README.md was deleted — this replaces it)
    # ------------------------------------------------------------------------
    README = """\
VBStyle Book System
===================

A SQLite-backed book authoring and rendering system for the
'VBStyle Architecture Blueprint' — a technical book documenting
self-contained C binaries with embedded SQLite, MySQL ingestion,
and PyQt6 configuration interfaces.

WHAT THIS IS
------------
Three components that share one SQLite database:

  config.py  ← single source of truth (paths, constants, docs)
       │
       ├── config.py (SCHEMA_SQL)  (15 tables, 5 views)
       │         │
       │    book.db  (SQLite database)
       │         │
       ├── Book.py  (CLI, 37 commands)
       └── BookViewer.py  (PyQt6 + turn.js flipbook)

- Schema — The data model. 15 tables (parts, chapters, sections,
  content_blocks, rules, annotations, glossary, etc.) with FK cascades
  and 5 export/query views.
- CLI — Book.py. 37 commands for adding, updating, removing,
  importing, exporting, searching, and annotating book content.
  AI uses this to populate and edit the book as structured data.
- Viewer — BookViewer.py. PyQt6 + QWebEngineView rendering
  turn.js page-flip animation. Search, highlight, annotate — all
  persisted to the DB.

FILES
-----
  config.py                  Single source of truth — ALL configuration:
                             paths, theme (75 colors/fonts/sizes), icons (16),
                             shortcuts (12), buttons (10), menu (5), window (13),
                             search (5), annotation (6), flipbook (8), status (13),
                             errors (10 actionable), tooltips (11),
                             SCHEMA_SQL (embedded, 22KB), TURNJS_COMPRESSED (10KB),
                             ABOUT, HELP, README (full docs)
  Book.py                    CLI — 37 commands
  BookViewer.py              PyQt6 desktop viewer (flipbook + search + highlight + annotate)
  Binary_congf_intenaldb_gui.md  The book (source markdown, 17 chapters)
  book.db                    The SQLite database (generated by init, populated by import-md)

QUICK START
-----------
  python3 Book.py init
  python3 Book.py import-md Binary_congf_intenaldb_gui.md
  python3 Book.py stats
  python3 Book.py outline
  python3 BookViewer.py
  python3 Book.py export-flipbook book.html

CLI COMMANDS (37)
-----------------
  Setup:
    init                          Create DB from schema
    stats                         Row counts per table

  Add:
    add-part <num> <title> [subtitle]
    add-chapter <pid> <num> <title> [subtitle]
    add-section <cid> <sec> <sort> <title> [type]
    add-block <sid> <type> <order> <content> [lang]
    add-rule <num> <tag> <cat> <desc> [ch_id]
    link-rule <rid> <section|chapter> <id>
    add-glossary <term> <def> [ch_id]
    add-summary <ch_id> <summary>
    add-xref <from_sec> <to_ch> [to_sec] <text>
    add-table <sid> <title> <headers_json> <rows_json>

  Update:
    update-part <num> [title] [subtitle]
    update-chapter <num> [title] [subtitle]
    update-section <sid> [title] [type] [wc] [page]
    update-block <bid> [content] [lang] [caption] [order]
    update-glossary <term> [new_term] [def] [ch_id]
    update-rule <num> [tag] [cat] [desc] [ch_id]

  Remove:
    remove-section <sid>
    remove-block <bid>
    remove-xref <xid>

  Import & Export:
    import-md <file>
    export <ch_num>
    export-all
    export-flipbook <file> [title]

  Query & Check:
    search <term>
    check
    outline [ch_num]
    list-rules
    list-glossary
    list-xrefs [ch_num]
    list-annotations [sid]
    info <ch_num>
    state

  Annotations:
    add-annotation <sid> <text> [note] [color]
    remove-annotation <id>

VIEWER FEATURES
---------------
  Page flip       Drag pages or use arrow keys
  Two-page spread Shows left + right pages like an open book
  Search          Type in search box → orange highlights
  Highlight       Select text → click Highlight → yellow, saved to DB
  Annotate        Select text → click Annotate → blue + note, saved to DB
  Annotation panel  Top-right panel lists all annotations
  Export HTML     Save flipbook as standalone .html
  Refresh         Reload from DB after edits

SCHEMA OVERVIEW
---------------
  parts (1-N)
    └── chapters (1-N)
          └── sections (1-N)
                └── content_blocks (1-N, interleaved text/code/table/callout)

  rules (71 VBStyle rules)
    ├── section_rules (M:N junction)
    └── chapter_rules (M:N junction)

  rule_relations (M:N rule graph)
  comparison_tables (structured data)
  cross_refs (document graph)
  chapter_summaries (per-chapter summary text)
  glossary (term → definition)
  annotations (user highlights + notes, persisted)
  schema_meta (version tracking)

ENVIRONMENT VARIABLES
---------------------
  BOOK_DB         Path to book.db (default: ./book.db next to config.py)

REQUIREMENTS
------------
  Python 3.10+
  PyQt6 (pip install PyQt6) — for the viewer only
  SQLite3 (built into macOS)

VBSTYLE COMPLIANCE
------------------
  All Python code follows VBStyle rules:
  - Run() dispatch entry point
  - Tuple3 (ok, data, error) returns
  - self.state dict (no self._)
  - PascalCase classes, UPPERCASE constants
  - Ghost + VBStyle + Class + Method headers
  - No decorators, no print, no hardcoded values
"""

    # ------------------------------------------------------------------------
    # METHOD: GetPath
    # Purpose: Resolve a path with env var override + fallback
    # Params:  env_var (str), default_path (str)
    # Returns: str — resolved path
    # ------------------------------------------------------------------------
    def GetPath(self, env_var, default_path):
        return os.environ.get(env_var, default_path)

    # ------------------------------------------------------------------------
    # METHOD: GetAbout
    # Purpose: Return the ABOUT string (one-paragraph system description)
    # Params:  None
    # Returns: str
    # ------------------------------------------------------------------------
    def GetAbout(self, ):
        return Config.ABOUT

    # ------------------------------------------------------------------------
    # METHOD: GetHelp
    # Purpose: Return the HELP string (quick start + command reference)
    # Params:  None
    # Returns: str
    # ------------------------------------------------------------------------
    def GetHelp(self, ):
        return Config.HELP

    # ------------------------------------------------------------------------
    # METHOD: GetReadme
    # Purpose: Return the README string (full project documentation)
    # Params:  None
    # Returns: str
    # ------------------------------------------------------------------------
    def GetReadme(self, ):
        return Config.README

    # ------------------------------------------------------------------------
    # METHOD: GetTooltip
    # Purpose: Return tooltip text for a UI element key
    # Params:  key (str) — one of: prev, next, export, refresh, search_box,
    #          search_btn, clear, highlight, annotate, help, about
    # Returns: str — tooltip text, or empty string if key not found
    # ------------------------------------------------------------------------
    def GetTooltip(self, key):
        return Config.TOOLTIPS.get(key, "")

    # ------------------------------------------------------------------------
    # METHOD: GetTheme
    # Purpose: Return a theme value by key
    # Params:  key (str) — any key from THEME dict
    # Returns: value (str, int, or tuple), or None if key not found
    # ------------------------------------------------------------------------
    def GetTheme(self, key):
        return Config.THEME.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetTurnJs
    # Purpose: Decompress and return the turn.js library source code
    #          Used by BookViewer.py and Book.py export-flipbook
    # Params:  None
    # Returns: str — turn.js JavaScript source (23KB uncompressed)
    # ------------------------------------------------------------------------
    def GetTurnJs(self, ):
        raw = base64.b64decode(Config.TURNJS_COMPRESSED)
        return zlib.decompress(raw).decode("utf-8")

    # ------------------------------------------------------------------------
    # METHOD: GetThemeCss
    # Purpose: Return the complete flipbook CSS block, built from THEME values
    #          Used by BookViewer.py and Book.py export-flipbook
    # Params:  None
    # Returns: str — CSS string for embedding in HTML
    # ------------------------------------------------------------------------
    def GetThemeCss(self, ):
        t = Config.THEME
        return f"""* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: {t['window_bg']}; overflow: hidden;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    min-height: 100vh;
    font-family: {t['page_font_family']};
}}
#flipbook {{ width: {Config.FLIPBOOK_WIDTH}px; height: {Config.FLIPBOOK_HEIGHT}px; }}
#flipbook .page-content {{
    background: {t['page_bg']}; color: {t['page_text']};
    padding: {t['page_padding']}; overflow: hidden;
    font-size: {t['page_font_size']}; line-height: {t['page_line_height']};
}}
#flipbook .hard {{ background: {t['cover_bg_solid']}; }}
#flipbook .page-header {{
    font-size: {t['header_size']}; color: {t['header_color']}; text-transform: uppercase;
    letter-spacing: 1px; border-bottom: 1px solid {t['footer_border']};
    padding-bottom: 5px; margin-bottom: 15px;
}}
#flipbook .page-footer {{
    font-size: {t['footer_size']}; color: {t['footer_color']}; text-align: center;
    border-top: 1px solid {t['footer_border']}; padding-top: 5px;
    position: absolute; bottom: 20px; left: 35px; right: 35px;
}}
#flipbook h2 {{
    font-size: {t['h2_size']}; color: {t['h2_color']}; margin-bottom: 12px;
    font-family: Georgia, serif;
}}
#flipbook h3 {{ font-size: {t['h3_size']}; color: {t['h3_color']}; margin: 10px 0; }}
#flipbook p {{ margin: 6px 0; }}
#flipbook ul {{ padding-left: 20px; margin: 6px 0; }}
#flipbook li {{ margin: 3px 0; }}
#flipbook .code-block {{
    background: {t['code_bg']}; border: 1px solid {t['code_border']};
    border-left: 3px solid {t['code_accent']}; padding: 8px 12px;
    font-family: {t['code_font_family']};
    font-size: {t['code_font_size']}; line-height: {t['code_line_height']}; white-space: pre-wrap;
    overflow-x: auto; margin: 8px 0; color: {t['code_text']};
}}
#flipbook .callout {{
    background: {t['callout_bg']}; border-left: 4px solid {t['callout_border']};
    padding: 8px 12px; margin: 8px 0; font-size: {t['callout_font_size']};
}}
#flipbook .text-block {{ margin: 6px 0; }}
#flipbook .text-block p {{ margin: 4px 0; }}
#flipbook b, #flipbook strong {{ color: {t['bold_color']}; }}
#flipbook i, #flipbook em {{ color: {t['italic_color']}; }}
#flipbook code {{
    font-family: 'Menlo', 'Monaco', monospace; font-size: {t['inline_code_size']};
    background: {t['inline_code_bg']}; padding: 1px 3px;
}}
#flipbook table {{ border-collapse: collapse; margin: 8px 0; font-size: {t['table_font_size']}; }}
#flipbook th {{ background: {t['table_th_bg']}; padding: 4px 8px; border: 1px solid {t['table_border']}; }}
#flipbook td {{ padding: 4px 8px; border: 1px solid {t['table_border']}; }}
#flipbook blockquote {{
    border-left: 3px solid {t['blockquote_border']}; margin: 8px 0; padding: 4px 12px;
    background: {t['blockquote_bg']}; color: {t['blockquote_text']};
}}
/* Search highlight (orange) */
mark.search-mark {{
    background: {t['search_mark_bg']}; color: {t['search_mark_text']}; padding: 1px 2px;
    border-radius: 2px;
}}
/* User highlight (yellow) */
.user-highlight {{
    background: {t['user_hl_bg']}; padding: 1px 2px;
    border-radius: 2px; cursor: pointer;
    border-bottom: 2px solid {t['user_hl_border']};
}}
/* User annotation (blue with dotted underline) */
.user-annotation {{
    background: {t['user_annot_bg']}; padding: 1px 2px;
    border-bottom: 2px dotted {t['user_annot_border']};
    cursor: pointer; position: relative;
}}
.user-annotation:hover::after {{
    content: attr(data-note);
    position: absolute; bottom: 100%; left: 0;
    background: {t['user_annot_tooltip_bg']}; color: {t['user_annot_tooltip_text']};
    padding: 6px 10px; border-radius: 4px;
    font-size: 11px; white-space: pre-wrap;
    max-width: 300px; z-index: 1000;
    font-family: Helvetica, sans-serif;
}}
/* Annotation list panel */
#annot-panel {{
    position: fixed; top: 10px; right: 10px;
    width: {t['annot_panel_width']}; max-height: 400px; overflow-y: auto;
    background: {t['annot_panel_bg']}; border: 1px solid {t['annot_panel_border']};
    border-radius: 8px; padding: 12px;
    font-family: Helvetica, sans-serif; font-size: 12px;
    box-shadow: {t['annot_panel_shadow']};
    z-index: 9999; display: none;
}}
#annot-panel h3 {{
    font-size: 14px; margin-bottom: 8px; color: {t['annot_panel_title_color']};
}}
.annot-item {{
    padding: 6px; margin: 4px 0; border-bottom: 1px solid #eee;
    cursor: pointer;
}}
.annot-item:hover {{ background: {t['annot_item_hover_bg']}; }}
.annot-text {{ font-style: italic; color: {t['annot_text_color']}; }}
.annot-note {{ color: {t['annot_note_color']}; margin-top: 2px; }}
.annot-remove {{
    color: {t['annot_remove_color']}; font-size: 10px; float: right; cursor: pointer;
}}"""

    # ------------------------------------------------------------------------
    # AI / ML — Embedding models, LLMs, QA models, rerankers, vector backends
    # Purpose: Central registry for all AI model configs. Apps read only what
    #          they need. Unused entries are dormant, not bloat.
    # ------------------------------------------------------------------------
    EMBEDDING_MODELS = {
        "bge_small": {
            "type":         "sentence_transformer",
            "name":         "BAAI/bge-small-en-v1.5",
            "dim":          384,
            "max_seq":      512,
            "device":       "auto",
        },
        "bge_small_mlx": {
            "type":         "mlx",
            "name":         "mlx-community/bge-small-en-v1.5-bf16",
            "dim":          384,
            "max_seq":      512,
            "device":       "metal",
        },
        "bge_m3_mlx": {
            "type":         "mlx",
            "name":         "mlx-community/bge-m3-mlx-fp16",
            "dim":          1024,
            "max_seq":      8192,
            "device":       "metal",
        },
        "minilm_l12": {
            "type":         "coreml",
            "name":         "all-MiniLM-L12-v2",
            "dim":          384,
            "max_seq":      256,
            "device":       "metal",
        },
        "codebert": {
            "type":         "coreml",
            "name":         "microsoft_codebert-base",
            "dim":          768,
            "max_seq":      512,
            "device":       "metal",
        },
        "token_embedder": {
            "type":         "coreml",
            "name":         "TokenEmbedder_V2",
            "dim":          384,
            "max_seq":      128,
            "device":       "metal",
        },
    }
    EMBEDDING_ACTIVE = "bge_small"

    LLM_MODELS = {
        "qwen25_coder_4bit": {
            "type":         "mlx",
            "name":         "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit",
            "max_tokens":   200,
            "device":       "metal",
        },
        "qwen25_coder_8bit": {
            "type":         "mlx",
            "name":         "mlx-community/Qwen2.5-Coder-1.5B-Instruct-8bit",
            "max_tokens":   200,
            "device":       "metal",
        },
        "llama3_8b": {
            "type":         "mlx",
            "name":         "mlx-community/Meta-Llama-3-8B-Instruct-4bit",
            "max_tokens":   500,
            "device":       "metal",
        },
        "openai_gpt4": {
            "type":         "api",
            "name":         "gpt-4",
            "max_tokens":   2000,
            "api_key_env":  "OPENAI_API_KEY",
            "endpoint":     "https://api.openai.com/v1/chat/completions",
        },
        "anthropic_claude": {
            "type":         "api",
            "name":         "claude-3-5-sonnet",
            "max_tokens":   2000,
            "api_key_env":  "ANTHROPIC_API_KEY",
            "endpoint":     "https://api.anthropic.com/v1/messages",
        },
        "none": {
            "type":         "none",
            "name":         "no_llm",
        },
    }
    LLM_ACTIVE = "qwen25_coder_4bit"
    LLM_ENABLED = True

    QA_MODELS = {
        "bert_squad_fp16": {
            "type":             "coreml",
            "name":             "BERTSquadFP16",
            "tokenizer":        "bert-base-uncased",
            "max_length":       384,
            "device":           "metal",
        },
        "bert_squad_int8": {
            "type":             "coreml",
            "name":             "BERTSquadINT8",
            "tokenizer":        "bert-base-uncased",
            "max_length":       384,
            "device":           "metal",
        },
    }
    QA_ACTIVE = "bert_squad_fp16"
    QA_CONFIDENCE_THRESHOLD = 0.0
    QA_MAX_ANSWER_LENGTH = 50
    QA_SPAN_EXTRACTION_MODE = "best_span"
    QA_MULTI_ANSWER_MODE = False

    RERANKERS = {
        "cohere_rerank_3_5": {
            "type":         "api",
            "name":         "cohere-rerank-3.5",
            "api_key_env":  "COHERE_API_KEY",
            "endpoint":     "https://api.cohere.com/v1/rerank",
        },
        "bge_reranker_v2_m3": {
            "type":         "local",
            "name":         "BAAI/bge-reranker-v2-m3",
            "device":       "metal",
        },
        "pinecone_rerank_v0": {
            "type":         "api",
            "name":         "pinecone-rerank-v0",
            "api_key_env":  "PINECONE_API_KEY",
        },
    }
    RERANKER_ACTIVE = ""
    RERANKING_ENABLED = False

    VECTOR_BACKENDS = {
        "qdrant": {
            "url":              "http://localhost:6333",
            "collections":      ["dim_semantic", "dim_structural", "dim_capability",
                                 "dim_lifecycle", "dim_bracket"],
            "default_collection": "dim_semantic",
        },
        "faiss": {
            "index_type":       "IndexFlatIP",
            "path":             "",
        },
        "sqlite_vector": {
            "path":             "",
            "table":            "embeddings",
        },
        "ram": {
            "index_type":       "numpy",
        },
    }
    VECTOR_BACKEND_ACTIVE = "qdrant"

    MODEL_DEVICE = {
        "active":           "auto",
        "fallback_chain":   ["metal", "gpu", "cpu"],
        "max_vram_mb":      2048,
        "max_ram_mb":       4096,
        "detect_on_init":   True,
    }

    # ------------------------------------------------------------------------
    # DATABASE PRAGMA — SQLite tuning parameters
    # Purpose: Central source for all PRAGMA settings. Applied on every
    #          connection. Change here → all DB connections update.
    # ------------------------------------------------------------------------
    DB_PRAGMA = {
        "journal_mode":         "WAL",
        "cache_size":           -64000,
        "foreign_keys":         "ON",
        "synchronous":          "NORMAL",
        "wal_autocheckpoint":   1000,
        "temp_store":           "MEMORY",
        "mmap_size":            268435456,
        "busy_timeout":         5000,
    }

    DB_POOL = {
        "pool_size":            5,
        "timeout":              10,
        "retry_count":          3,
        "retry_delay":          0.5,
    }

    DB_BACKUP = {
        "backup_dir":           "backups",
        "auto_backup":          False,
        "interval_hours":       24,
        "max_backups":          10,
        "compress":             True,
    }

    DB_MIGRATION = {
        "migration_dir":        "migrations",
        "auto_migrate":         True,
        "version_table":        "_schema_version",
    }

    # ------------------------------------------------------------------------
    # MCP — Model Context Protocol server configs and permissions
    # Purpose: Central registry for MCP servers, their tools, and access
    #          control. Apps read this to know which servers to start and
    #          which tools are auto-approved vs require confirmation.
    # ------------------------------------------------------------------------
    MCP_SERVERS = {
        "filesystem": {
            "command":          "npx",
            "args":             ["-y", "@anthropic/mcp-filesystem"],
            "env":              {},
            "enabled":          True,
        },
        "gmail": {
            "command":          "npx",
            "args":             ["-y", "@anthropic/mcp-gmail"],
            "env":              {},
            "enabled":          True,
        },
        "pinecone": {
            "command":          "npx",
            "args":             ["-y", "@anthropic/mcp-pinecone"],
            "env":              {"PINECONE_API_KEY": ""},
            "enabled":          True,
        },
        "contextram": {
            "command":          "contextram",
            "args":             [],
            "env":              {},
            "enabled":          True,
        },
        "taskplanner": {
            "command":          "taskplanner",
            "args":             [],
            "env":              {},
            "enabled":          True,
        },
    }

    MCP_PERMISSIONS = {
        "auto_approve":         [],
        "ask_before":           ["delete_file", "send_email", "deploy"],
        "deny":                 [],
        "resource_read_paths":  [],
        "resource_write_paths": [],
    }

    MCP_RESOURCES = {
        "allowed_paths":        [],
        "read_only":            True,
        "max_file_size_mb":     10,
    }

    # ------------------------------------------------------------------------
    # SECURITY / PERMISSIONS — File, network, and API key policies
    # Purpose: Central source for all access control. Apps check these
    #          before performing sensitive operations.
    # ------------------------------------------------------------------------
    FILE_ACCESS = {
        "allowed_dirs":         [],
        "denied_paths":         [],
        "read_only_paths":      [],
        "require_confirmation": [],
    }

    NETWORK_ACCESS = {
        "allowed_hosts":        [],
        "denied_hosts":         [],
        "proxy_host":           "",
        "proxy_port":           0,
        "proxy_env":            "HTTP_PROXY",
        "timeout_seconds":      30,
    }

    API_KEYS = {
        "openai_env":           "OPENAI_API_KEY",
        "anthropic_env":        "ANTHROPIC_API_KEY",
        "cohere_env":           "COHERE_API_KEY",
        "pinecone_env":         "PINECONE_API_KEY",
        "qdrant_env":           "QDRANT_API_KEY",
        "rotation_days":        90,
    }

    RATE_LIMITS = {
        "requests_per_second":  10,
        "burst_size":           20,
        "cooldown_seconds":     5,
    }

    # ------------------------------------------------------------------------
    # LOGGING — Log level, format, rotation, output destinations
    # Purpose: Single source for all logging config. Apps import this
    #          instead of hardcoding log levels and formats.
    # ------------------------------------------------------------------------
    LOGGING = {
        "level":                "INFO",
        "format":               "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "date_format":          "%Y-%m-%d %H:%M:%S",
        "log_file":             "",
        "console_output":       True,
        "rotation_size_mb":     10,
        "max_log_files":        5,
        "log_levels":           ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    }

    # ------------------------------------------------------------------------
    # NETWORK / ENDPOINTS — API URLs, timeouts, retry strategies
    # Purpose: Central registry for all external endpoints. Change a URL
    #          here → all consumers update. No hardcoded URLs in code.
    # ------------------------------------------------------------------------
    ENDPOINTS = {
        "openai": {
            "url":              "https://api.openai.com/v1",
            "timeout":          30,
            "retry_count":      3,
            "backoff":          "exponential",
        },
        "anthropic": {
            "url":              "https://api.anthropic.com/v1",
            "timeout":          30,
            "retry_count":      3,
            "backoff":          "exponential",
        },
        "cohere": {
            "url":              "https://api.cohere.com/v1",
            "timeout":          30,
            "retry_count":      3,
            "backoff":          "exponential",
        },
        "qdrant": {
            "url":              "http://localhost:6333",
            "timeout":          10,
            "retry_count":      2,
            "backoff":          "linear",
        },
        "pinecone": {
            "url":              "https://api.pinecone.io",
            "timeout":          30,
            "retry_count":      3,
            "backoff":          "exponential",
        },
    }

    PROXY = {
        "host":                 "",
        "port":                 0,
        "auth_env":             "PROXY_AUTH",
        "no_proxy":             ["localhost", "127.0.0.1"],
    }

    # ------------------------------------------------------------------------
    # PERFORMANCE — Cache, memory limits, threading
    # Purpose: Central tuning for all performance-related settings.
    # ------------------------------------------------------------------------
    CACHE = {
        "enabled":              True,
        "max_size_mb":          100,
        "ttl_seconds":          3600,
        "eviction_policy":      "lru",
        "cache_dir":            "",
    }

    MEMORY_LIMITS = {
        "max_ram_mb":           4096,
        "max_vram_mb":          2048,
        "warning_threshold":    0.85,
        "critical_threshold":   0.95,
    }

    THREADING = {
        "pool_size":            4,
        "queue_size":           100,
        "timeout_seconds":      30,
        "daemon_threads":       True,
    }

    # ------------------------------------------------------------------------
    # INTERNATIONALIZATION — Locale, date/time formats, timezone
    # Purpose: Single source for all i18n settings. Ready for multi-language.
    # ------------------------------------------------------------------------
    I18N = {
        "locale":               "en_US",
        "language":             "en",
        "date_format":          "%Y-%m-%d",
        "time_format":          "%H:%M:%S",
        "datetime_format":      "%Y-%m-%d %H:%M:%S",
        "number_format":        "{:,.2f}",
        "timezone":             "local",
        "first_day_of_week":    0,
        "language_file":        "",
        "supported_locales":    ["en_US", "af_ZA"],
    }

    # ------------------------------------------------------------------------
    # ACCESSIBILITY — Visual aids, keyboard nav, screen reader support
    # Purpose: Central source for a11y settings. Apps read these to adjust
    #          rendering for users who need assistance.
    # ------------------------------------------------------------------------
    A11Y = {
        "font_scale":           1.0,
        "high_contrast":        False,
        "screen_reader_mode":   False,
        "keyboard_nav_mode":    False,
        "reduced_motion":       False,
        "colorblind_palette":   "none",
        "min_font_size":        10,
        "max_font_size":        32,
    }

    # ------------------------------------------------------------------------
    # EXPORT / IMPORT — Supported formats, default paths, options
    # Purpose: Central registry for all export/import capabilities.
    # ------------------------------------------------------------------------
    EXPORT = {
        "formats":              ["html", "pdf", "md", "json"],
        "default_format":       "html",
        "export_dir":           "",
        "include_annotations":  True,
        "include_metadata":     True,
        "overwrite":            False,
    }

    IMPORT = {
        "formats":              ["md", "json", "csv", "txt"],
        "import_dir":           "",
        "overwrite":            False,
        "validate_before":      True,
    }

    # ------------------------------------------------------------------------
    # PLUGINS / EXTENSIONS — Plugin directory, enabled list, configs
    # Purpose: Central registry for plugin system. Apps scan the plugin
    #          dir and load only enabled plugins with their configs.
    # ------------------------------------------------------------------------
    PLUGINS = {
        "plugin_dir":           "plugins",
        "enabled":              [],
        "configs":              {},
        "auto_discover":        True,
        "load_order":           [],
    }

    # ------------------------------------------------------------------------
    # EDITOR / CODE VIEW — Syntax highlighting, font, line numbers
    # Purpose: Central source for code editor settings in GUI apps.
    # ------------------------------------------------------------------------
    EDITOR = {
        "syntax_theme":         "dark",
        "tab_size":             4,
        "show_line_numbers":    True,
        "show_whitespace":      False,
        "auto_complete":        True,
        "font_family":          "Menlo, Monaco, monospace",
        "font_size":            13,
        "word_wrap":            True,
        "minimap":              False,
        "bracket_matching":     True,
    }

    # ------------------------------------------------------------------------
    # UPDATE / VERSIONING — Auto-update check, channels, URLs
    # Purpose: Central config for update mechanism.
    # ------------------------------------------------------------------------
    UPDATE = {
        "auto_check":           True,
        "check_interval_hours": 24,
        "update_url":           "",
        "channel":              "stable",
        "channels":             ["stable", "beta", "dev"],
        "last_check":           "",
    }

    # ------------------------------------------------------------------------
    # WINDOW STATE — Persisted window geometry and recent files
    # Purpose: Central source for window state that should survive restart.
    # ------------------------------------------------------------------------
    WINDOW_STATE = {
        "last_x":               100,
        "last_y":               100,
        "last_width":           1000,
        "last_height":          700,
        "maximized":            False,
        "splitter_positions":   [],
        "recent_files":         [],
        "max_recent_files":     10,
    }

    # ------------------------------------------------------------------------
    # TELEMETRY / METRICS — What to record, export interval, storage
    # Purpose: Central config for telemetry. Disabled by default.
    # ------------------------------------------------------------------------
    METRICS = {
        "enabled":              False,
        "record_latencies":     True,
        "record_ram_usage":     True,
        "record_cpu_usage":     False,
        "record_retrieval_scores": True,
        "record_qa_confidence": True,
        "export_interval_seconds": 300,
        "storage_path":         "",
        "max_records":          10000,
    }

    # ------------------------------------------------------------------------
    # MOUSE / GESTURES — Mouse actions and touchpad gesture bindings
    # Purpose: Central source for all mouse/gesture settings.
    # ------------------------------------------------------------------------
    MOUSE = {
        "double_click_action":  "select_word",
        "right_click_menu":     True,
        "scroll_behavior":      "smooth",
        "drag_sensitivity":     1.0,
        "middle_click_paste":   True,
    }

    GESTURES = {
        "swipe_left":           "next_page",
        "swipe_right":          "prev_page",
        "pinch_zoom":           True,
        "two_finger_scroll":    True,
        "tap_to_select":        True,
    }

    # ------------------------------------------------------------------------
    # BOOK CONTENT — Metadata, chapter ordering, bookmarks
    # Purpose: Central source for book-level metadata and navigation.
    # ------------------------------------------------------------------------
    BOOK_META = {
        "title":                "VBStyle Architecture Blueprint",
        "subtitle":             "A Blueprint for Self-Contained C Binaries",
        "author":               "",
        "isbn":                 "",
        "publisher":            "",
        "copyright_year":       "",
        "language":             "en",
        "cover_image":          "",
        "edition":              "1",
    }

    CHAPTERS = {
        "ordering":             "numerical",
        "default_landing_page": "cover",
        "bookmarks":            [],
        "max_bookmarks":        50,
    }

    # ------------------------------------------------------------------------
    # RETRIEVAL — Vector search settings for AI-powered search
    # Purpose: Central source for retrieval pipeline tuning.
    # ------------------------------------------------------------------------
    RETRIEVAL = {
        "top_k":                5,
        "similarity_threshold": 0.30,
        "distance_metric":      "cosine",
        "chunk_size":           400,
        "chunk_overlap":        80,
        "reranking_enabled":    False,
        "reranker_model":       "",
        "max_depth":            10,
    }

    # ------------------------------------------------------------------------
    # PIPELINE — Processing pipeline modes and stage definitions
    # Purpose: Central source for pipeline configuration. Each mode defines
    #          which stages run and in what order.
    # ------------------------------------------------------------------------
    PIPELINE = {
        "default_mode":         "B",
        "modes": {
            "A": ["embed", "search"],
            "B": ["embed", "search", "qa_extract", "classify"],
            "C": ["embed", "search", "qa_extract", "classify", "llm_format"],
            "D": ["embed", "search", "llm_format"],
            "E": ["qa_extract", "classify"],
            "R": ["route", "embed", "search", "qa_extract", "classify", "llm_format"],
        },
    }

    # ------------------------------------------------------------------------
    # CLASSIFICATION — Thresholds for true/unknown/false classification
    # Purpose: Central source for classification tuning.
    # ------------------------------------------------------------------------
    CLASSIFICATION = {
        "true_threshold":       5.0,
        "unknown_threshold":    0.0,
        "false_threshold":      0.0,
        "min_confidence":       0.0,
        "max_results":          10,
    }

    # ------------------------------------------------------------------------
    # FAILURE ATTRIBUTION — Failure stage definitions for diagnostics
    # Purpose: Central source for failure stage tracking.
    # ------------------------------------------------------------------------
    FAILURE_STAGES = [
        "DOCUMENT_LOAD", "CHUNKING", "EMBEDDING", "VECTOR_STORE",
        "RETRIEVAL", "RERANKING", "QA_EXTRACTION", "CLASSIFICATION",
        "RESOURCE_LIMIT", "NONE",
    ]

    # ------------------------------------------------------------------------
    # STORAGE — Storage mode, persistence policy, refresh policy
    # Purpose: Central source for data storage behavior.
    # ------------------------------------------------------------------------
    STORAGE = {
        "mode":                 "persistent",
        "modes":                ["ram_only", "persistent", "hybrid"],
        "persistence_policy":   "save_on_demand",
        "refresh_policy":       "manual",
    }

    # ------------------------------------------------------------------------
    # EXECUTION — Execution mode and hardware detection
    # Purpose: Central source for execution environment config.
    # ------------------------------------------------------------------------
    EXECUTION = {
        "mode":                 "auto",
        "modes":                ["cpu", "gpu", "auto", "hybrid"],
        "detect_on_init":       True,
    }

    # ------------------------------------------------------------------------
    # NOTIFICATIONS — Desktop notification settings
    # Purpose: Central source for system notification behavior.
    # ------------------------------------------------------------------------
    NOTIFICATIONS = {
        "enabled":              True,
        "sound":                True,
        "duration_seconds":     5,
        "position":             "bottom_right",
        "max_visible":          3,
    }

    # ------------------------------------------------------------------------
    # SESSION — Session management, timeout, persistence
    # Purpose: Central source for session behavior.
    # ------------------------------------------------------------------------
    SESSION = {
        "timeout_minutes":      30,
        "persist_state":        True,
        "state_file":           "",
        "auto_save_interval":   60,
        "max_sessions":         5,
    }

    # ------------------------------------------------------------------------
    # FEATURES — Feature flags for toggling functionality on/off
    # Purpose: Central source for feature toggles. Apps check these flags
    #          to enable/disable features without code changes.
    # ------------------------------------------------------------------------
    FEATURES = {
        "tts_enabled":          True,
        "search_enabled":       True,
        "annotations_enabled":  True,
        "export_enabled":       True,
        "import_enabled":       True,
        "flipbook_enabled":     True,
        "ai_search_enabled":    False,
        "vector_search_enabled": False,
        "llm_enabled":          False,
        "plugin_system_enabled": False,
        "telemetry_enabled":    False,
        "auto_update_enabled":  True,
        "beta_features_enabled": False,
    }

    # ------------------------------------------------------------------------
    # PYQT6 WIDGET PROPERTIES — Centralized defaults for every PyQt6 widget
    # Purpose: When building GUIs, import these instead of hardcoding. Every
    #          property PyQt6 exposes is here. Use what you need, ignore rest.
    # ------------------------------------------------------------------------

    # --- QMainWindow ---
    PYQT_MAINWINDOW = {
        "animated_docks":           True,
        "dock_nesting_enabled":     False,
        "dock_options":             "AnimatedDocks|AllowTabbedDocks",
        "tab_shape":                "Rounded",
        "tab_position":             "North",
        "icon_size":                (24, 24),
        "tool_button_style":        "ToolButtonTextBesideIcon",
        "unified_title_and_toolbar_on_mac": True,
        "uses_scroll_area":         True,
    }

    # --- QWidget (base for all widgets) ---
    PYQT_WIDGET = {
        "enabled":                  True,
        "visible":                  True,
        "accept_drops":             False,
        "auto_fill_background":     False,
        "base_size":                (0, 0),
        "contents_margins":         (0, 0, 0, 0),
        "context_menu_policy":      "DefaultContextMenu",
        "cursor":                   "ArrowCursor",
        "focus_policy":             "NoFocus",
        "font":                     "default",
        "fullscreen":               False,
        "layout_direction":         "LeftToRight",
        "locale":                   "default",
        "maximized":                False,
        "maximum_size":             (16777215, 16777215),
        "minimum_size":             (0, 0),
        "minimum_width":            0,
        "minimum_height":           0,
        "maximum_width":            16777215,
        "maximum_height":           16777215,
        "mouse_tracking":           False,
        "palette":                  "default",
        "pos":                      (0, 0),
        "size":                     (640, 480),
        "size_policy":              ("Preferred", "Preferred"),
        "size_increment":           (1, 1),
        "status_tip":               "",
        "style_sheet":              "",
        "tool_tip":                 "",
        "tool_tip_duration":        -1,
        "updates_enabled":          True,
        "visible":                  True,
        "whats_this":               "",
        "window_flags":             "Widget",
        "window_icon":              "",
        "window_modality":          "NonModal",
        "window_opacity":           1.0,
        "window_title":             "",
        "x":                        0,
        "y":                        0,
        "width":                    640,
        "height":                   480,
        "accessible_name":          "",
        "accessible_description":   "",
    }

    # --- QPushButton ---
    PYQT_PUSHBUTTON = {
        "auto_default":             True,
        "default":                  False,
        "flat":                     False,
        "icon":                     "",
        "icon_size":                (16, 16),
        "auto_repeat":              False,
        "auto_repeat_delay":        300,
        "auto_repeat_interval":     100,
        "checkable":                False,
        "checked":                  False,
        "down":                     False,
        "text":                     "",
        "shortcut":                 "",
        "tool_tip":                 "",
        "status_tip":               "",
        "whats_this":               "",
        "minimum_width":            0,
        "minimum_height":           0,
        "maximum_width":            16777215,
        "maximum_height":           16777215,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
        "focus_policy":             "StrongFocus",
        "context_menu_policy":      "DefaultContextMenu",
        "size_policy":              ("Minimum", "Fixed"),
    }

    # --- QLineEdit ---
    PYQT_LINEEDIT = {
        "text":                     "",
        "placeholder_text":         "",
        "echo_mode":                "Normal",
        "max_length":               32767,
        "frame":                    True,
        "alignment":                "AlignLeft|AlignVCenter",
        "cursor_position":          0,
        "read_only":                False,
        "clear_button_enabled":     False,
        "drag_enabled":             True,
        "cursor_move_style":        "LogicalMoveStyle",
        "size_policy":              ("Expanding", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "input_mask":               "",
        "validator":                None,
        "completion":               None,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "context_menu_policy":      "DefaultContextMenu",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QTextEdit ---
    PYQT_TEXTEDIT = {
        "plain_text":               "",
        "html":                     "",
        "accept_rich_text":         True,
        "line_wrap_mode":           "WidgetWidth",
        "line_wrap_column_or_width": 80,
        "read_only":                False,
        "tab_changes_focus":        False,
        "tab_stop_distance":        80,
        "cursor_width":             1,
        "overwrite_mode":           False,
        "undo_redo_enabled":        True,
        "auto_formatting":          "AutoNone",
        "text_interaction_flags":   "TextBrowserInteraction",
        "frame":                    True,
        "frame_shadow":             "Plain",
        "frame_shape":              "NoFrame",
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
        "placeholder_text":         "",
    }

    # --- QLabel ---
    PYQT_LABEL = {
        "text":                     "",
        "text_format":              "AutoText",
        "pixmap":                   "",
        "alignment":                "AlignLeft|AlignVCenter",
        "word_wrap":                False,
        "indent":                   -1,
        "margin":                   0,
        "open_external_links":      False,
        "text_interaction_flags":   "NoTextInteraction",
        "buddy":                    None,
        "scaled_contents":          False,
        "size_policy":              ("Preferred", "Preferred"),
        "minimum_width":            0,
        "minimum_height":           0,
        "frame":                    False,
        "frame_shape":              "NoFrame",
        "frame_shadow":             "Plain",
        "style_sheet":              "",
        "focus_policy":             "NoFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
        "text_color":               "",
        "background_color":         "",
    }

    # --- QComboBox ---
    PYQT_COMBOBOX = {
        "items":                    [],
        "current_text":             "",
        "current_index":            -1,
        "editable":                 False,
        "max_visible_items":        10,
        "max_count":                2147483647,
        "size_adjust_policy":       "AdjustToContentsOnFirstShow",
        "icon_size":                (16, 16),
        "insert_policy":            "InsertAtBottom",
        "duplicates_enabled":       False,
        "frame":                    True,
        "model_column":             0,
        "minimum_contents_length":  0,
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QSlider ---
    PYQT_SLIDER = {
        "orientation":              "Horizontal",
        "minimum":                  0,
        "maximum":                  99,
        "single_step":              1,
        "page_step":                10,
        "value":                    0,
        "slider_position":          0,
        "tracking":                 True,
        "orientation":              "Horizontal",
        "tick_position":            "NoTicks",
        "tick_interval":            0,
        "inverted_appearance":      False,
        "inverted_controls":        False,
        "size_policy":              ("Expanding", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QCheckBox ---
    PYQT_CHECKBOX = {
        "text":                     "",
        "checked":                  False,
        "check_state":              "Unchecked",
        "tristate":                 False,
        "auto_exclusive":           False,
        "icon":                     "",
        "icon_size":                (16, 16),
        "shortcut":                 "",
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QRadioButton ---
    PYQT_RADIOBUTTON = {
        "text":                     "",
        "checked":                  False,
        "auto_exclusive":           True,
        "icon":                     "",
        "icon_size":                (16, 16),
        "shortcut":                 "",
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QSpinBox ---
    PYQT_SPINBOX = {
        "value":                    0,
        "minimum":                  0,
        "maximum":                  99,
        "single_step":              1,
        "prefix":                   "",
        "suffix":                   "",
        "clean_text":               True,
        "alignment":                "AlignLeft|AlignVCenter",
        "button_symbols":           "UpDownArrows",
        "correction_mode":          "CorrectToPreviousValue",
        "frame":                    True,
        "keyboard_tracking":        True,
        "special_value_text":       "",
        "accelerated":              False,
        "show_group_separator":     False,
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QDoubleSpinBox ---
    PYQT_DOUBLESPINBOX = {
        "value":                    0.0,
        "minimum":                  0.0,
        "maximum":                  99.99,
        "single_step":              1.0,
        "decimals":                 2,
        "prefix":                   "",
        "suffix":                   "",
        "clean_text":               True,
        "alignment":                "AlignLeft|AlignVCenter",
        "button_symbols":           "UpDownArrows",
        "correction_mode":          "CorrectToPreviousValue",
        "frame":                    True,
        "keyboard_tracking":        True,
        "special_value_text":       "",
        "accelerated":              False,
        "show_group_separator":     False,
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QProgressBar ---
    PYQT_PROGRESSBAR = {
        "value":                    0,
        "minimum":                  0,
        "maximum":                  100,
        "text":                     "",
        "text_visible":             True,
        "text_direction":           "TopToBottom",
        "text_alignment":           "AlignCenter",
        "orientation":              "Horizontal",
        "inverted_appearance":      False,
        "format":                   "%p%",
        "size_policy":              ("Expanding", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "NoFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QToolBar ---
    PYQT_TOOLBAR = {
        "movable":                  True,
        "floatable":                True,
        "allowed_areas":            "AllToolBarAreas",
        "icon_size":                (24, 24),
        "tool_button_style":        "ToolButtonIconOnly",
        "orientation":              "Horizontal",
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QMenuBar ---
    PYQT_MENUBAR = {
        "default_up":               False,
        "native_menu_bar":          True,
        "size_policy":              ("MinimumExpanding", "Minimum"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QStatusBar ---
    PYQT_STATUSBAR = {
        "size_grip_enabled":        True,
        "size_policy":              ("Preferred", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QTabWidget ---
    PYQT_TABWIDGET = {
        "tab_position":             "North",
        "tab_shape":                "Rounded",
        "tabs_closable":            False,
        "movable":                  False,
        "tab_bar_auto_hide":        False,
        "current_index":            -1,
        "icon_size":                (16, 16),
        "elide_mode":               "ElideRight",
        "document_mode":            False,
        "uses_scroll_buttons":      True,
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QSplitter ---
    PYQT_SPLITTER = {
        "orientation":              "Horizontal",
        "opaque_resize":            True,
        "children_collapsible":     True,
        "handle_width":             8,
        "children_collapsible":     True,
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QGroupBox ---
    PYQT_GROUPBOX = {
        "title":                    "",
        "alignment":                "AlignLeft|AlignVCenter",
        "flat":                     False,
        "checkable":                False,
        "checked":                  True,
        "enabled":                  True,
        "visible":                  True,
        "size_policy":              ("Preferred", "Preferred"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "NoFocus",
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QListView ---
    PYQT_LISTVIEW = {
        "model":                    None,
        "selection_mode":           "SingleSelection",
        "selection_behavior":       "SelectItems",
        "edit_triggers":            "DoubleClicked|EditKeyPressed",
        "drag_enabled":             False,
        "drag_drop_mode":           "NoDragDrop",
        "default_drop_action":      "CopyAction",
        "alternating_row_colors":   False,
        "grid_style":               "NoGrid",
        "icon_size":                (16, 16),
        "movement":                 "Static",
        "flow":                     "TopToBottom",
        "is_wrapping":              False,
        "resize_mode":              "Fixed",
        "layout_mode":              "SinglePass",
        "spacing":                  0,
        "view_mode":                "ListMode",
        "uniform_item_sizes":       False,
        "word_wrap":                False,
        "item_alignment":           "AlignLeft",
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QTreeView ---
    PYQT_TREEVIEW = {
        "model":                    None,
        "root_is_decorated":        True,
        "uniform_row_heights":      False,
        "items_expandable":         True,
        "expands_on_double_click":  True,
        "auto_expand_delay":        -1,
        "header_hidden":            False,
        "header_default_section_size": 100,
        "header_minimum_section_size":  50,
        "header_stretch_last_section":  True,
        "header_cascading_section_resizes": False,
        "indentation":              20,
        "sorting_enabled":          False,
        "animated":                 False,
        "all_columns_show_focus":   False,
        "word_wrap":                False,
        "selection_mode":           "SingleSelection",
        "selection_behavior":       "SelectRows",
        "edit_triggers":            "DoubleClicked|EditKeyPressed",
        "drag_enabled":             False,
        "drag_drop_mode":           "NoDragDrop",
        "alternating_row_colors":   False,
        "root_index":               None,
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QTableView ---
    PYQT_TABLEVIEW = {
        "model":                    None,
        "show_grid":                True,
        "grid_style":               "SolidLine",
        "corner_button_enabled":    True,
        "sorting_enabled":          False,
        "word_wrap":                True,
        "corner_widget":            None,
        "horizontal_header":        "default",
        "vertical_header":          "default",
        "selection_mode":           "SingleSelection",
        "selection_behavior":       "SelectRows",
        "edit_triggers":            "DoubleClicked|EditKeyPressed",
        "drag_enabled":             False,
        "drag_drop_mode":           "NoDragDrop",
        "alternating_row_colors":   False,
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QScrollArea ---
    PYQT_SCROLLAREA = {
        "widget_resizable":         True,
        "horizontal_scroll_bar_policy": "ScrollBarAsNeeded",
        "vertical_scroll_bar_policy":   "ScrollBarAsNeeded",
        "alignment":                "AlignLeft|AlignTop",
        "frame_shape":              "StyledPanel",
        "frame_shadow":             "Sunken",
        "line_width":               1,
        "mid_line_width":           0,
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "NoFocus",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QWebEngineView ---
    PYQT_WEBENGINEVIEW = {
        "url":                      "",
        "html":                     "",
        "zoom_factor":              1.0,
        "title":                    "",
        "icon":                     "",
        "selected_text":            "",
        "has_selection":            False,
        "find_text":                "",
        "size_policy":              ("Expanding", "Expanding"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QWebEngineSettings (per-page web settings) ---
    PYQT_WEBENGINE_SETTINGS = {
        "javascript_enabled":           True,
        "javascript_can_open_windows":  False,
        "javascript_can_access_clipboard": False,
        "plugins_enabled":              False,
        "local_storage_enabled":        True,
        "local_content_can_access_remote_urls": False,
        "local_content_can_access_file_urls": False,
        "xss_auditing_enabled":         True,
        "spatial_navigation_enabled":   False,
        "linksIncludedInFocusChain":    False,
        "print_element_backgrounds":    True,
        "allow_running_insecure_content": False,
        "allow_geolocation_on_insecure_origins": False,
        "allow_window_activation_from_js": False,
        "show_scroll_bars":             True,
        "scroll_bars_animating":        True,
        "webgl_enabled":                True,
        "accelerated_2d_canvas_enabled": False,
        "force_dark_mode":              False,
        "default_text_encoding":        "UTF-8",
        "font_family_standard":         "Times New Roman",
        "font_family_fixed":            "Courier New",
        "font_family_serif":            "Times New Roman",
        "font_family_sans_serif":       "Arial",
        "font_family_cursive":          "Cursive",
        "font_family_fantasy":          "Fantasy",
        "font_size_minimum":            16,
        "font_size_minimum_logical":    12,
        "font_size_default":            16,
        "font_size_default_fixed":      13,
        "unknown_url_scheme_policy":    "DisallowUnknownUrlSchemes",
        "pdf_viewer_enabled":           True,
        "nice_loopback_enabled":        False,
    }

    # --- QDialog ---
    PYQT_DIALOG = {
        "modal":                    False,
        "size_grip_enabled":        True,
        "size_policy":              ("Preferred", "Preferred"),
        "minimum_width":            0,
        "minimum_height":           0,
        "maximum_width":            16777215,
        "maximum_height":           16777215,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "window_modality":          "NonModal",
        "window_title":             "",
    }

    # --- QFileDialog ---
    PYQT_FILEDIALOG = {
        "accept_mode":              "AcceptOpen",
        "file_mode":                "AnyFile",
        "view_mode":                "Detail",
        "directory":                "",
        "filter":                   "All Files (*)",
        "default_suffix":           "",
        "name_filter":              "",
        "options":                  "ShowDirsOnly",
        "selected_files":           [],
        "selected_filter":          "",
        "supported_schemes":        [],
        "label_text":               {},
        "size_policy":              ("Preferred", "Preferred"),
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QInputDialog ---
    PYQT_INPUTDIALOG = {
        "input_mode":               "TextInput",
        "text_value":               "",
        "int_value":                0,
        "int_minimum":              -2147483647,
        "int_maximum":              2147483647,
        "int_step":                 1,
        "double_value":             0.0,
        "double_minimum":           -2147483647.0,
        "double_maximum":           2147483647.0,
        "double_decimals":          2,
        "label_text":               "",
        "ok_button_text":           "OK",
        "cancel_button_text":       "Cancel",
        "options":                  "UseListViewForComboBoxItems",
        "size_policy":              ("Preferred", "Preferred"),
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QMessageDialog / QMessageBox ---
    PYQT_MESSAGEBOX = {
        "icon":                     "NoIcon",
        "text":                     "",
        "informative_text":         "",
        "detailed_text":            "",
        "standard_buttons":         "Ok",
        "default_button":           "NoButton",
        "escape_button":            "NoButton",
        "text_format":              "AutoText",
        "text_interaction_flags":   "LinksAccessibleByMouse",
        "size_policy":              ("Preferred", "Preferred"),
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
        "modal":                    True,
    }

    # --- QToolButton ---
    PYQT_TOOLBUTTON = {
        "text":                     "",
        "icon":                     "",
        "icon_size":                (16, 16),
        "arrow_type":               "NoArrow",
        "popup_mode":               "DelayedPopup",
        "tool_button_style":        "ToolButtonIconOnly",
        "auto_raise":               False,
        "checkable":                False,
        "checked":                  False,
        "auto_repeat":              False,
        "auto_repeat_delay":        300,
        "auto_repeat_interval":     100,
        "size_policy":              ("Fixed", "Fixed"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "focus_policy":             "StrongFocus",
        "enabled":                  True,
        "visible":                  True,
        "tool_tip":                 "",
        "whats_this":               "",
    }

    # --- QFont (font properties for all widgets) ---
    PYQT_FONT = {
        "family":                   "SF Pro Text",
        "point_size":               -1,
        "pixel_size":               -1,
        "weight":                   "Normal",
        "bold":                     False,
        "italic":                   False,
        "underline":                False,
        "overline":                 False,
        "strike_out":               False,
        "fixed_pitch":              False,
        "kerning":                  True,
        "letter_spacing":           0,
        "letter_spacing_type":      "PercentageSpacing",
        "word_spacing":             0,
        "stretch":                  100,
        "style":                    "StyleNormal",
        "style_hint":               "AnyStyle",
        "style_strategy":           "PreferDefault",
        "hinting_preference":       "PreferDefaultHinting",
        "capitalization":           "MixedCase",
        "families":                 [],
        "resolve_mask":             0,
    }

    # --- QPalette (color roles) ---
    PYQT_PALETTE = {
        "Window":                   "#2a2a2a",
        "WindowText":               "#ffffff",
        "Base":                     "#1a1a1a",
        "AlternateBase":            "#2a2a2a",
        "Text":                     "#ffffff",
        "Button":                   "#3a3a3a",
        "ButtonText":               "#ffffff",
        "BrightText":               "#ff0000",
        "Highlight":                "#1a365d",
        "HighlightedText":          "#ffffff",
        "Link":                     "#4a90d9",
        "LinkVisited":              "#8a2be2",
        "ToolTipBase":              "#1a1a1a",
        "ToolTipText":              "#ffffff",
        "PlaceholderText":          "#888888",
        # Disabled state
        "Window_disabled":          "#2a2a2a",
        "WindowText_disabled":      "#888888",
        "Text_disabled":            "#888888",
        "Button_disabled":          "#2a2a2a",
        "ButtonText_disabled":      "#888888",
        "Highlight_disabled":       "#444444",
        "HighlightedText_disabled": "#888888",
    }

    # --- QSizePolicy (horizontal/vertical policies) ---
    PYQT_SIZEPOLICY = {
        "horizontal":               "Preferred",
        "vertical":                 "Preferred",
        "horizontal_stretch":       0,
        "vertical_stretch":         0,
        "height_for_width":         False,
        "width_for_height":         False,
        "control_type":             "Default",
        "policies": {
            "Fixed":                0,
            "Minimum":              1,
            "Maximum":              4,
            "Preferred":            5,
            "MinimumExpanding":     3,
            "Expanding":            7,
            "Ignored":              0,
        },
    }

    # --- QCursor shapes ---
    PYQT_CURSOR_SHAPES = [
        "ArrowCursor", "UpArrowCursor", "CrossCursor", "WaitCursor",
        "IBeamCursor", "SizeVerCursor", "SizeHorCursor", "SizeBDiagCursor",
        "SizeFDiagCursor", "SizeAllCursor", "BlankCursor", "SplitVCursor",
        "SplitHCursor", "PointingHandCursor", "ForbiddenCursor",
        "WhatsThisCursor", "BusyCursor", "OpenHandCursor", "ClosedHandCursor",
        "DragCopyCursor", "DragMoveCursor", "DragLinkCursor",
        "BitmapCursor", "CustomCursor",
    ]

    # --- Qt focus policies ---
    PYQT_FOCUS_POLICIES = [
        "NoFocus", "TabFocus", "ClickFocus", "StrongFocus", "WheelFocus",
    ]

    # --- Qt context menu policies ---
    PYQT_CONTEXT_MENU_POLICIES = [
        "NoContextMenu", "DefaultContextMenu",
        "ActionsContextMenu", "CustomContextMenu",
    ]

    # --- Qt scroll bar policies ---
    PYQT_SCROLLBAR_POLICIES = [
        "ScrollBarAsNeeded", "ScrollBarAlwaysOff", "ScrollBarAlwaysOn",
    ]

    # --- Qt window flags ---
    PYQT_WINDOW_FLAGS = [
        "Widget", "Window", "Dialog", "Sheet", "Drawer", "Popup", "Tool",
        "SplashScreen", "WindowType_Mask", "ForeignWindow", "CoverWindow",
        "WindowStaysOnTop", "WindowStaysOnBottom", "X11BypassWindowManagerHint",
        "FramelessWindowHint", "CustomizeWindowHint",
        "WindowTitleHint", "WindowSystemMenuHint", "WindowMinimizeButtonHint",
        "WindowMaximizeButtonHint", "WindowMinMaxButtonsHint",
        "WindowContextHelpButtonHint", "WindowShadeButtonHint",
        "WindowStaysOnTopHint", "WindowTransparentForInput",
        "WindowOverridesSystemGestures", "WindowDoesNotAcceptFocus",
        "MaximizeUsingFullscreenGeometryHint", "WindowStaysOnBottomHint",
        "BypassWindowProxy", "NoDropShadowWindowHint",
    ]

    # --- Qt window states ---
    PYQT_WINDOW_STATES = [
        "WindowNoState", "WindowMinimized", "WindowMaximized",
        "WindowFullScreen", "WindowActive",
    ]

    # --- Qt alignment flags ---
    PYQT_ALIGNMENT_FLAGS = [
        "AlignLeft", "AlignRight", "AlignHCenter", "AlignJustify",
        "AlignTop", "AlignBottom", "AlignVCenter", "AlignCenter",
        "AlignAbsolute", "AlignLeading", "AlignTrailing",
        "AlignHorizontal_Mask", "AlignVertical_Mask",
    ]

    # --- Qt orientation ---
    PYQT_ORIENTATIONS = [
        "Horizontal", "Vertical",
    ]

    # --- Qt text formats ---
    PYQT_TEXT_FORMATS = [
        "PlainText", "RichText", "AutoText", "MarkdownText",
    ]

    # --- Qt text interaction flags ---
    PYQT_TEXT_INTERACTION_FLAGS = [
        "NoTextInteraction", "TextSelectableByMouse",
        "TextSelectableByKeyboard", "LinksAccessibleByMouse",
        "LinksAccessibleByKeyboard", "TextEditable",
        "TextEditorInteraction", "TextBrowserInteraction",
    ]

    # --- Qt check states ---
    PYQT_CHECK_STATES = [
        "Unchecked", "PartiallyChecked", "Checked",
    ]

    # --- Qt echo modes (QLineEdit) ---
    PYQT_ECHO_MODES = [
        "Normal", "NoEcho", "Password", "PasswordEchoOnEdit",
    ]

    # --- Qt line wrap modes (QTextEdit) ---
    PYQT_LINE_WRAP_MODES = [
        "NoWrap", "WidgetWidth", "FixedPixelWidth", "FixedColumnWidth",
    ]

    # --- Qt selection modes ---
    PYQT_SELECTION_MODES = [
        "NoSelection", "SingleSelection", "MultiSelection",
        "ExtendedSelection", "ContiguousSelection",
    ]

    # --- Qt selection behaviors ---
    PYQT_SELECTION_BEHAVIORS = [
        "SelectItems", "SelectRows", "SelectColumns",
    ]

    # --- Qt drag drop modes ---
    PYQT_DRAG_DROP_MODES = [
        "NoDragDrop", "DragOnly", "DropOnly",
        "DragDrop", "InternalMove",
    ]

    # --- Qt edit triggers ---
    PYQT_EDIT_TRIGGERS = [
        "NoEditTriggers", "CurrentChanged", "DoubleClicked",
        "SelectedClicked", "EditKeyPressed", "AnyKeyPressed",
        "AllEditTriggers",
    ]

    # --- Qt view modes (QListView) ---
    PYQT_VIEW_MODES = [
        "ListMode", "IconMode",
    ]

    # --- Qt tick positions (QSlider) ---
    PYQT_TICK_POSITIONS = [
        "NoTicks", "TicksAbove", "TicksBelow",
        "TicksLeft", "TicksRight", "TicksBothSides",
    ]

    # --- Qt tab positions ---
    PYQT_TAB_POSITIONS = [
        "North", "South", "West", "East",
    ]

    # --- Qt tab shapes ---
    PYQT_TAB_SHAPES = [
        "Rounded", "Triangular",
    ]

    # --- Qt tool button styles ---
    PYQT_TOOL_BUTTON_STYLES = [
        "ToolButtonIconOnly", "ToolButtonTextOnly",
        "ToolButtonTextBesideIcon", "ToolButtonTextUnderIcon",
        "ToolButtonFollowStyle",
    ]

    # --- Qt message box icons ---
    PYQT_MESSAGEBOX_ICONS = [
        "NoIcon", "Question", "Information", "Warning", "Critical",
    ]

    # --- Qt message box standard buttons ---
    PYQT_MESSAGEBOX_BUTTONS = [
        "Ok", "Open", "Save", "Cancel", "Close", "Discard", "Apply",
        "Reset", "RestoreDefaults", "Help", "SaveAll", "Yes", "YesToAll",
        "No", "NoToAll", "Abort", "Retry", "Ignore", "NoButton",
    ]

    # --- Qt file dialog modes ---
    PYQT_FILE_DIALOG_MODES = [
        "AnyFile", "ExistingFile", "Directory", "ExistingFiles",
        "DirectoryOnly",
    ]

    # --- Qt file dialog accept modes ---
    PYQT_FILE_DIALOG_ACCEPT_MODES = [
        "AcceptOpen", "AcceptSave",
    ]

    # --- Qt file dialog view modes ---
    PYQT_FILE_DIALOG_VIEW_MODES = [
        "Detail", "List",
    ]

    # --- Qt input dialog modes ---
    PYQT_INPUT_DIALOG_MODES = [
        "TextInput", "IntInput", "DoubleInput",
    ]

    # --- Qt dialog button box standard buttons ---
    PYQT_DIALOG_BUTTONS = [
        "Ok", "Cancel", "Yes", "No", "Save", "Discard", "Close",
        "Apply", "Reset", "RestoreDefaults", "Help", "SaveAll",
        "YesToAll", "NoToAll", "Abort", "Retry", "Ignore",
    ]

    # --- Qt dialog button box button roles ---
    PYQT_DIALOG_BUTTON_ROLES = [
        "InvalidRole", "AcceptRole", "RejectRole", "DestructiveRole",
        "ActionRole", "HelpRole", "YesRole", "NoRole", "ApplyRole",
        "ResetRole",
    ]

    # --- Qt key codes (commonly used) ---
    PYQT_KEY_CODES = {
        "Enter":            "Key_Return",
        "Enter_KP":         "Key_Enter",
        "Escape":           "Key_Escape",
        "Tab":              "Key_Tab",
        "Backtab":          "Key_Backtab",
        "Backspace":        "Key_Backspace",
        "Insert":           "Key_Insert",
        "Delete":           "Key_Delete",
        "Pause":            "Key_Pause",
        "Print":            "Key_Print",
        "Home":             "Key_Home",
        "End":              "Key_End",
        "PageUp":           "Key_PageUp",
        "PageDown":         "Key_PageDown",
        "Left":             "Key_Left",
        "Right":            "Key_Right",
        "Up":               "Key_Up",
        "Down":             "Key_Down",
        "Space":            "Key_Space",
        "F1":               "Key_F1",
        "F2":               "Key_F2",
        "F3":               "Key_F3",
        "F4":               "Key_F4",
        "F5":               "Key_F5",
        "F6":               "Key_F6",
        "F7":               "Key_F7",
        "F8":               "Key_F8",
        "F9":               "Key_F9",
        "F10":              "Key_F10",
        "F11":              "Key_F11",
        "F12":              "Key_F12",
        "A":                "Key_A",
        "B":                "Key_B",
        "C":                "Key_C",
        "D":                "Key_D",
        "E":                "Key_E",
        "F":                "Key_F",
        "G":                "Key_G",
        "H":                "Key_H",
        "I":                "Key_I",
        "J":                "Key_J",
        "K":                "Key_K",
        "L":                "Key_L",
        "M":                "Key_M",
        "N":                "Key_N",
        "O":                "Key_O",
        "P":                "Key_P",
        "Q":                "Key_Q",
        "R":                "Key_R",
        "S":                "Key_S",
        "T":                "Key_T",
        "U":                "Key_U",
        "V":                "Key_V",
        "W":                "Key_W",
        "X":                "Key_X",
        "Y":                "Key_Y",
        "Z":                "Key_Z",
        "0":                "Key_0",
        "1":                "Key_1",
        "2":                "Key_2",
        "3":                "Key_3",
        "4":                "Key_4",
        "5":                "Key_5",
        "6":                "Key_6",
        "7":                "Key_7",
        "8":                "Key_8",
        "9":                "Key_9",
        "Period":           "Key_Period",
        "Comma":            "Key_Comma",
        "Minus":            "Key_Minus",
        "Plus":             "Key_Plus",
        "Equal":            "Key_Equal",
        "BracketLeft":      "Key_BracketLeft",
        "BracketRight":     "Key_BracketRight",
        "Semicolon":        "Key_Semicolon",
        "Apostrophe":       "Key_Apostrophe",
        "Slash":            "Key_Slash",
        "Backslash":        "Key_Backslash",
        "Shift":            "Key_Shift",
        "Control":          "Key_Control",
        "Alt":              "Key_Alt",
        "Meta":             "Key_Meta",
    }

    # --- Qt keyboard modifiers ---
    PYQT_KEYBOARD_MODIFIERS = [
        "NoModifier", "ShiftModifier", "ControlModifier",
        "AltModifier", "MetaModifier", "KeypadModifier",
        "GroupSwitchModifier",
    ]

    # --- Qt mouse buttons ---
    PYQT_MOUSE_BUTTONS = [
        "NoButton", "LeftButton", "RightButton", "MiddleButton",
        "BackButton", "ForwardButton", "TaskButton",
        "ExtraButton1", "ExtraButton2", "ExtraButton3",
        "ExtraButton4", "ExtraButton5", "ExtraButton6",
        "ExtraButton7", "ExtraButton8", "ExtraButton9",
        "ExtraButton10", "ExtraButton11", "ExtraButton12",
        "ExtraButton13", "ExtraButton14", "ExtraButton15",
        "ExtraButton16", "ExtraButton17", "ExtraButton18",
        "ExtraButton19", "ExtraButton20", "ExtraButton21",
        "ExtraButton22", "ExtraButton23", "ExtraButton24",
        "AllButtons", "XButton1", "XButton2",
    ]

    # --- Qt scroll bar orientations ---
    PYQT_SCROLLBAR_ORIENTATIONS = [
        "Horizontal", "Vertical",
    ]

    # --- Qt item data roles (model/view) ---
    PYQT_ITEM_DATA_ROLES = [
        "DisplayRole", "DecorationRole", "EditRole", "ToolTipRole",
        "StatusTipRole", "WhatsThisRole", "FontRole", "TextAlignmentRole",
        "BackgroundRole", "ForegroundRole", "CheckStateRole",
        "SizeHintRole", "InitialSortOrderRole", "UserRole",
    ]

    # --- Qt item flags (model/view) ---
    PYQT_ITEM_FLAGS = [
        "NoItemFlags", "ItemIsSelectable", "ItemIsEditable",
        "ItemIsDragEnabled", "ItemIsDropEnabled", "ItemIsUserCheckable",
        "ItemIsEnabled", "ItemIsAutoTristate", "ItemNeverHasChildren",
        "ItemIsUserTristate",
    ]

    # --- Qt layout directions ---
    PYQT_LAYOUT_DIRECTIONS = [
        "LeftToRight", "RightToLeft", "LayoutDirectionAuto",
    ]

    # --- Qt widget attributes ---
    PYQT_WIDGET_ATTRIBUTES = [
        "WA_Disabled", "WA_UnderMouse", "WA_Hover",
        "WA_ForceDisabled", "WA_SetPalette", "WA_SetFont",
        "WA_SetCursor", "WA_NoChildEventsForParent",
        "WA_NoMousePropagation", "WA_DontCreateNativeAncestors",
        "WA_DontShowOnScreen", "WA_DeleteOnClose",
        "WA_RightToLeft", "WA_LayoutDirection",
        "WA_NoSystemBackground", "WA_OpaquePaintEvent",
        "WA_TranslucentBackground", "WA_NativeWindow",
        "WA_AcceptDrops", "WA_DropSiteRegistered",
        "WA_InputMethodEnabled", "WA_KeyCompression",
        "WA_ForceAcceptDrops",
    ]

    # --- QShortcut properties ---
    PYQT_SHORTCUT = {
        "key":                      "",
        "enabled":                  True,
        "auto_repeat":              True,
        "context":                  "WindowShortcut",
        "whats_this":               "",
        "shortcut_tip":             "",
    }

    # --- QLayout (base layout properties) ---
    PYQT_LAYOUT = {
        "spacing":                  6,
        "margins":                  (0, 0, 0, 0),
        "alignment":                "AlignTop|AlignLeft",
        "size_constraint":          "SetDefaultConstraint",
        "enabled":                  True,
        "activate":                 True,
    }

    # --- QHBoxLayout / QVBoxLayout ---
    PYQT_BOXLAYOUT = {
        "spacing":                  6,
        "margins":                  (0, 0, 0, 0),
        "alignment":                "AlignTop|AlignLeft",
        "size_constraint":          "SetDefaultConstraint",
        "direction":                "LeftToRight",
        "stretch_factors":          [],
        "enabled":                  True,
    }

    # --- QGridLayout ---
    PYQT_GRIDLAYOUT = {
        "spacing":                  6,
        "margins":                  (0, 0, 0, 0),
        "alignment":                "AlignTop|AlignLeft",
        "size_constraint":          "SetDefaultConstraint",
        "horizontal_spacing":       6,
        "vertical_spacing":         6,
        "enabled":                  True,
    }

    # --- QFormLayout ---
    PYQT_FORMLAYOUT = {
        "spacing":                  6,
        "margins":                  (0, 0, 0, 0),
        "alignment":                "AlignTop|AlignLeft",
        "size_constraint":          "SetDefaultConstraint",
        "field_growth_policy":      "ExpandingFieldsGrow",
        "row_wrap_policy":          "DontWrapRows",
        "label_alignment":          "AlignLeft",
        "form_alignment":           "AlignLeft|AlignTop",
        "horizontal_spacing":       6,
        "vertical_spacing":         6,
        "enabled":                  True,
    }

    # --- QStackedLayout ---
    PYQT_STACKEDLAYOUT = {
        "spacing":                  6,
        "margins":                  (0, 0, 0, 0),
        "alignment":                "AlignTop|AlignLeft",
        "size_constraint":          "SetDefaultConstraint",
        "current_index":            -1,
        "stacking_mode":            "StackOne",
        "enabled":                  True,
    }

    # --- QSizePolicy control types ---
    PYQT_SIZEPOLICY_CONTROL_TYPES = [
        "Default", "ButtonBox", "CheckBox", "ComboBox", "Dial",
        "Dialog", "GroupBox", "Label", "Line", "LineEdit",
        "PushButton", "RadioButton", "Slider", "SpinBox",
        "TabWidget", "ToolButton", "ScrollArea", "TreeView",
        "TableView", "ListView",
    ]

    # --- QFrame properties ---
    PYQT_FRAME = {
        "frame_shape":              "NoFrame",
        "frame_shadow":             "Plain",
        "line_width":               1,
        "mid_line_width":           0,
        "frame_width":              1,
        "frame_rect":               (0, 0, 0, 0),
        "size_policy":              ("Preferred", "Preferred"),
        "minimum_width":            0,
        "minimum_height":           0,
        "style_sheet":              "",
        "enabled":                  True,
        "visible":                  True,
    }

    # --- QFrame shapes ---
    PYQT_FRAME_SHAPES = [
        "NoFrame", "Box", "Panel", "StyledPanel", "HLine", "VLine",
        "WinPanel",
    ]

    # --- QFrame shadows ---
    PYQT_FRAME_SHADOWS = [
        "Plain", "Raised", "Sunken",
    ]

    # --- QSizePolicy size constraints ---
    PYQT_SIZE_CONSTRAINTS = [
        "SetDefaultConstraint", "SetFixedSize", "SetMinimumSize",
        "SetMaximumSize", "SetMinAndMaxSize", "SetNoConstraint",
    ]

    # --- QSizePolicy stretch factors ---
    PYQT_STRETCH_FACTORS = {
        "default_horizontal":       0,
        "default_vertical":         0,
        "toolbar_horizontal":       1,
        "toolbar_vertical":         0,
        "content_horizontal":       1,
        "content_vertical":         1,
        "sidebar_horizontal":       0,
        "sidebar_vertical":         1,
    }

    # --- QSizePolicy control types ---
    PYQT_CONTROL_TYPES = [
        "Default", "ButtonBox", "CheckBox", "ComboBox", "Dial",
        "Dialog", "GroupBox", "Label", "Line", "LineEdit",
        "PushButton", "RadioButton", "Slider", "SpinBox",
        "TabWidget", "ToolButton", "ScrollArea", "TreeView",
        "TableView", "ListView",
    ]

    # --- Qt stylesheet selectors (for QSS reference) ---
    PYQT_QSS_SELECTORS = [
        "QWidget", "QMainWindow", "QLabel", "QPushButton", "QLineEdit",
        "QTextEdit", "QComboBox", "QCheckBox", "QRadioButton",
        "QSlider", "QProgressBar", "QToolBar", "QMenuBar", "QMenu",
        "QStatusBar", "QTabWidget", "QTabBar", "QTab",
        "QTableView", "QHeaderView", "QTreeView", "QListView",
        "QScrollArea", "QScrollBar", "QGroupBox", "QFrame",
        "QDialog", "QFileDialog", "QInputDialog", "QMessageBox",
        "QToolButton", "QSplitter", "QSplitterHandle",
        "QWebEngineView", "QStackedWidget",
    ]

    # --- Qt stylesheet properties (for QSS reference) ---
    PYQT_QSS_PROPERTIES = [
        "background", "background-color", "background-image",
        "background-repeat", "background-position", "background-attachment",
        "color", "font", "font-family", "font-size", "font-weight",
        "font-style", "text-decoration", "border", "border-top",
        "border-bottom", "border-left", "border-right", "border-radius",
        "border-style", "border-width", "border-color",
        "padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
        "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
        "min-width", "min-height", "max-width", "max-height",
        "width", "height", "spacing", "icon-size",
        "outline", "outline-color", "outline-style", "outline-width",
        "text-align", "alternate-background-color",
        "selection-background-color", "selection-color",
        "border-image", "image", "position", "left", "top", "right", "bottom",
        "show-decoration-selected", "border-collapse",
        "corner-radius", "gridline-color", "gridline-style", "gridline-width",
    ]

    # --- Qt pseudo-states (for QSS reference) ---
    PYQT_QSS_PSEUDO_STATES = [
        ":active", ":adjoins-item", ":alternate", ":bottom", ":checked",
        ":closable", ":closed", ":default", ":disabled", ":edit-focus",
        ":editable", ":enabled", ":exclusive", ":first", ":flat", ":floatable",
        ":focus", ":has-children", ":has-siblings", ":horizontal", ":hover",
        ":pressed", ":indeterminate", ":last", ":left", ":maximized",
        ":middle", ":minimized", ":movable", ":no-frame", ":non-exclusive",
        ":off", ":on", ":only", ":open", ":next-selected", ":pressed",
        ":previous-selected", ":read-only", ":right", ":selected", ":top",
        ":unchecked", ":vertical", ":window",
    ]

    # --- Qt sub-controls (for QSS reference) ---
    PYQT_QSS_SUB_CONTROLS = [
        "::add-line", "::add-page", "branch", "chunk", "close-button",
        "corner", "down-arrow", "down-button", "drop-down",
        "float-button", "groove", "indicator", "handle",
        "icon", "item", "left-arrow", "left-corner", "menu",
        "menu-button", "menu-indicator", "right-arrow", "right-corner",
        "pane", "scroller", "section", "separator", "sub-line",
        "sub-page", "tab", "tab-bar", "tear", "tearoff",
        "text", "title", "up-arrow", "up-button",
    ]

    # --- QSizePolicy enum values (for programmatic reference) ---
    PYQT_POLICY_VALUES = {
        "Fixed":                0,
        "Minimum":              1,
        "Maximum":              4,
        "Preferred":            5,
        "MinimumExpanding":     3,
        "Expanding":            7,
        "Ignored":              0,
    }

    # --- QSizePolicy control type values ---
    PYQT_CONTROL_TYPE_VALUES = {
        "Default":              0,
        "ButtonBox":            1,
        "CheckBox":             2,
        "ComboBox":             3,
        "Dial":                 4,
        "Dialog":               5,
        "GroupBox":             6,
        "Label":                7,
        "Line":                 8,
        "LineEdit":             9,
        "PushButton":           10,
        "RadioButton":          11,
        "Slider":               12,
        "SpinBox":              13,
        "TabWidget":            14,
        "ToolButton":           15,
        "ScrollArea":           16,
        "TreeView":             17,
        "TableView":            18,
        "ListView":             19,
    }

    # ------------------------------------------------------------------------
    # HUGGING FACE — Model hub, token, cache, download settings
    # Purpose: Central source for all Hugging Face Hub interactions.
    #          Apps read these to know which models to download, where to
    #          cache them, and how to authenticate.
    # ------------------------------------------------------------------------
    HUGGINGFACE = {
        "token_env":               "HUGGINGFACE_HUB_TOKEN",
        "token":                   "",
        "endpoint":                "https://huggingface.co",
        "api_endpoint":            "https://huggingface.co/api",
        "inference_endpoint":      "https://api-inference.huggingface.co",
        "cache_dir":               "",
        "default_download_dir":    "models",
        "offline_mode":            False,
        "verify_ssl":              True,
        "request_timeout":         30,
        "max_retries":             3,
        "retry_delay":             1.0,
        "max_file_size_gb":        50,
        "resume_downloads":        True,
        "parallel_downloads":      4,
        "etag_timeout":            10,
        "local_files_only":        False,
    }

    HUGGINGFACE_MODELS = {
        "embedding": {
            "bge_small_en":        "BAAI/bge-small-en-v1.5",
            "bge_m3":              "BAAI/bge-m3",
            "minilm_l12":          "sentence-transformers/all-MiniLM-L12-v2",
            "minilm_l6":           "sentence-transformers/all-MiniLM-L6-v2",
            "mpnet_base":          "sentence-transformers/all-mpnet-base-v2",
            "e5_large":            "intfloat/multilingual-e5-large",
            "codebert":            "microsoft/codebert-base",
            "unixcoder":           "microsoft/unixcoder-base",
        },
        "llm": {
            "qwen25_coder_1_5b":   "Qwen/Qwen2.5-Coder-1.5B-Instruct",
            "qwen25_coder_7b":     "Qwen/Qwen2.5-Coder-7B-Instruct",
            "llama3_8b":           "meta-llama/Meta-Llama-3-8B-Instruct",
            "llama3_1_8b":         "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "mistral_7b":          "mistralai/Mistral-7B-Instruct-v0.3",
            "gemma2_9b":           "google/gemma-2-9b-it",
            "phi3_mini":           "microsoft/Phi-3-mini-4k-instruct",
            "deepseek_coder_6_7b": "deepseek-ai/deepseek-coder-6.7b-instruct",
        },
        "qa": {
            "bert_squad":          "deepset/bert-base-cased-squad2",
            "roberta_squad":       "deepset/roberta-base-squad2",
            "distilbert_squad":    "distilbert/distilbert-base-cased-distilled-squad",
        },
        "reranker": {
            "bge_reranker_v2_m3":  "BAAI/bge-reranker-v2-m3",
            "cohere_rerank":       "Cohere/rerank-english-v3.0",
            "jina_reranker":       "jinaai/jina-reranker-v2-base-multilingual",
        },
        "classification": {
            "bert_base":           "bert-base-uncased",
            "distilbert":          "distilbert/distilbert-base-uncased",
            "roberta":             "FacebookAI/roberta-base",
        },
        "speech": {
            "whisper_small":       "openai/whisper-small",
            "whisper_medium":      "openai/whisper-medium",
            "whisper_large":       "openai/whisper-large-v3",
        },
        "vision": {
            "clip_base":           "openai/clip-vit-base-patch32",
            "clip_large":          "openai/clip-vit-large-patch14",
            "siglip":              "google/siglip-so400m-patch14-384",
        },
        "code": {
            "starcoder2_3b":       "bigcode/starcoder2-3b",
            "starcoder2_7b":       "bigcode/starcoder2-7b",
            "codegemma_7b":        "google/codegemma-7b-it",
        },
    }

    HUGGINGFACE_PIPELINE_TYPES = [
        "text-generation", "text-classification", "token-classification",
        "question-answering", "fill-mask", "summarization", "translation",
        "text2text-generation", "zero-shot-classification",
        "feature-extraction", "sentence-similarity",
        "image-classification", "object-detection", "image-segmentation",
        "text-to-image", "image-to-text", "automatic-speech-recognition",
        "text-to-speech", "audio-classification", "voice-activity-detection",
    ]

    HUGGINGFACE_QUANTIZATION = {
        "none":                    "fp16",
        "modes":                   ["fp32", "fp16", "bf16", "int8", "int4",
                                    "4bit", "8bit", "gptq", "awq", "exl2"],
        "default_4bit":            "bnb_4bit",
        "default_8bit":            "bnb_8bit",
        "compute_dtype":           "bfloat16",
        "double_quant":            True,
        "quant_type":              "nf4",
        "device_map":              "auto",
    }

    # ------------------------------------------------------------------------
    # GITHUB — API, tokens, repository settings
    # Purpose: Central source for all GitHub API interactions.
    #          Apps read these for repo access, issue tracking, CI/CD.
    # ------------------------------------------------------------------------
    GITHUB = {
        "token_env":               "GITHUB_TOKEN",
        "token":                   "",
        "api_endpoint":            "https://api.github.com",
        "api_version":             "2022-11-28",
        "raw_endpoint":            "https://raw.githubusercontent.com",
        "web_endpoint":            "https://github.com",
        "default_owner":           "",
        "default_repo":            "",
        "default_branch":          "main",
        "per_page":                100,
        "max_pages":               10,
        "request_timeout":         30,
        "max_retries":             3,
        "retry_delay":             1.0,
        "verify_ssl":              True,
        "user_agent":              "VBStyle-App/1.0",
        "media_type":              "application/vnd.github+json",
    }

    GITHUB_AUTH = {
        "oauth_client_id_env":     "GITHUB_CLIENT_ID",
        "oauth_client_secret_env": "GITHUB_CLIENT_SECRET",
        "oauth_redirect_uri":      "http://localhost:8080/callback",
        "oauth_scopes":            ["repo", "read:org", "gist", "workflow"],
        "oauth_authorize_url":     "https://github.com/login/oauth/authorize",
        "oauth_token_url":         "https://github.com/login/oauth/access_token",
        "device_code_url":         "https://github.com/login/device/code",
        "app_id_env":              "GITHUB_APP_ID",
        "app_private_key_env":     "GITHUB_APP_PRIVATE_KEY",
        "app_installation_id":     0,
    }

    GITHUB_WEBHOOK = {
        "secret_env":              "GITHUB_WEBHOOK_SECRET",
        "events":                  ["push", "pull_request", "issues", "release",
                                    "workflow_run", "deployment"],
        "payload_url":             "",
        "content_type":            "json",
        "insecure_ssl":            False,
    }

    GITHUB_ACTIONS = {
        "workflow_dir":            ".github/workflows",
        "default_runner":          "ubuntu-latest",
        "runners":                 ["ubuntu-latest", "ubuntu-22.04",
                                    "macos-latest", "macos-14",
                                    "windows-latest", "self-hosted"],
        "cache_timeout_minutes":   10,
        "artifact_retention_days": 90,
        "concurrency_group":       "ci",
        "cancel_in_progress":      True,
    }

    # ------------------------------------------------------------------------
    # GITLAB — API, tokens, CI/CD settings
    # Purpose: Central source for GitLab interactions (self-hosted or .com).
    # ------------------------------------------------------------------------
    GITLAB = {
        "token_env":               "GITLAB_TOKEN",
        "token":                   "",
        "api_endpoint":            "https://gitlab.com/api/v4",
        "web_endpoint":            "https://gitlab.com",
        "default_project":         "",
        "default_branch":          "main",
        "per_page":                100,
        "request_timeout":         30,
        "max_retries":             3,
        "verify_ssl":              True,
    }

    GITLAB_CI = {
        "pipeline_dir":            ".gitlab-ci",
        "default_runner":          "shared",
        "runners":                 ["shared", "private", "self-hosted"],
        "artifact_expire_in":      "1 week",
        "cache_key_prefix":        "ci",
    }

    # ------------------------------------------------------------------------
    # BITBUCKET — API, tokens, repository settings
    # Purpose: Central source for Bitbucket interactions.
    # ------------------------------------------------------------------------
    BITBUCKET = {
        "username_env":            "BITBUCKET_USERNAME",
        "app_password_env":        "BITBUCKET_APP_PASSWORD",
        "api_endpoint":            "https://api.bitbucket.org/2.0",
        "web_endpoint":            "https://bitbucket.org",
        "default_workspace":       "",
        "default_repo":            "",
        "request_timeout":         30,
        "max_retries":             3,
        "verify_ssl":              True,
    }

    # ------------------------------------------------------------------------
    # AUTHENTICATION / LOGIN — Credentials, OAuth providers, session auth
    # Purpose: Central source for all authentication mechanisms. Apps check
    #          these to know how to authenticate users and services.
    # ------------------------------------------------------------------------
    AUTH = {
        "mode":                    "none",
        "modes":                   ["none", "basic", "bearer", "oauth2",
                                    "api_key", "session", "jwt", "saml",
                                    "ldap", "custom"],
        "default_token_env":       "AUTH_TOKEN",
        "default_username_env":    "AUTH_USERNAME",
        "default_password_env":    "AUTH_PASSWORD",
        "token_refresh_enabled":   False,
        "token_refresh_threshold": 0.1,
        "token_lifetime_seconds":  3600,
        "session_cookie_name":     "session",
        "session_timeout_minutes": 30,
        "max_login_attempts":      5,
        "lockout_duration_minutes": 15,
        "password_min_length":     12,
        "password_require_upper":  True,
        "password_require_lower":  True,
        "password_require_digit":  True,
        "password_require_special": True,
        "password_history_count":  5,
        "2fa_enabled":             False,
        "2fa_method":              "totp",
        "2fa_methods":             ["totp", "sms", "email", "hardware_key"],
    }

    OAUTH_PROVIDERS = {
        "google": {
            "client_id_env":       "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env":   "GOOGLE_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://accounts.google.com/o/oauth2/auth",
            "token_url":           "https://oauth2.googleapis.com/token",
            "userinfo_url":        "https://www.googleapis.com/oauth2/v2/userinfo",
            "scopes":              ["openid", "email", "profile"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "github": {
            "client_id_env":       "GITHUB_OAUTH_CLIENT_ID",
            "client_secret_env":   "GITHUB_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://github.com/login/oauth/authorize",
            "token_url":           "https://github.com/login/oauth/access_token",
            "userinfo_url":        "https://api.github.com/user",
            "scopes":              ["repo", "read:org"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "microsoft": {
            "client_id_env":       "MS_OAUTH_CLIENT_ID",
            "client_secret_env":   "MS_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url":           "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "userinfo_url":        "https://graph.microsoft.com/oidc/userinfo",
            "scopes":              ["openid", "email", "profile", "User.Read"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "apple": {
            "client_id_env":       "APPLE_OAUTH_CLIENT_ID",
            "client_secret_env":   "APPLE_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://appleid.apple.com/auth/authorize",
            "token_url":           "https://appleid.apple.com/auth/token",
            "scopes":              ["name", "email"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "facebook": {
            "client_id_env":       "FACEBOOK_OAUTH_CLIENT_ID",
            "client_secret_env":   "FACEBOOK_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://www.facebook.com/v18.0/dialog/oauth",
            "token_url":           "https://graph.facebook.com/v18.0/oauth/access_token",
            "userinfo_url":        "https://graph.facebook.com/me",
            "scopes":              ["email", "public_profile"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "linkedin": {
            "client_id_env":       "LINKEDIN_OAUTH_CLIENT_ID",
            "client_secret_env":   "LINKEDIN_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://www.linkedin.com/oauth/v2/authorization",
            "token_url":           "https://www.linkedin.com/oauth/v2/accessToken",
            "userinfo_url":        "https://api.linkedin.com/v2/me",
            "scopes":              ["r_liteprofile", "r_emailaddress"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "slack": {
            "client_id_env":       "SLACK_OAUTH_CLIENT_ID",
            "client_secret_env":   "SLACK_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://slack.com/oauth/v2/authorize",
            "token_url":           "https://slack.com/api/oauth.v2.access",
            "scopes":              ["chat:write", "channels:read"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
        "discord": {
            "client_id_env":       "DISCORD_OAUTH_CLIENT_ID",
            "client_secret_env":   "DISCORD_OAUTH_CLIENT_SECRET",
            "authorize_url":       "https://discord.com/api/oauth2/authorize",
            "token_url":           "https://discord.com/api/oauth2/token",
            "userinfo_url":        "https://discord.com/api/users/@me",
            "scopes":              ["identify", "email"],
            "redirect_uri":        "http://localhost:8080/callback",
        },
    }

    # ------------------------------------------------------------------------
    # SSH / GIT CREDENTIALS — Key paths, known hosts, agent settings
    # Purpose: Central source for SSH and Git credential management.
    # ------------------------------------------------------------------------
    SSH = {
        "key_dir":                 "~/.ssh",
        "default_key":             "id_ed25519",
        "key_types":               ["ed25519", "rsa", "ecdsa", "dsa"],
        "default_port":            22,
        "known_hosts_file":        "~/.ssh/known_hosts",
        "config_file":             "~/.ssh/config",
        "agent_forwarding":        False,
        "strict_host_checking":    True,
        "connect_timeout":         10,
        "server_alive_interval":   60,
        "server_alive_count_max":  3,
        "compression":             True,
    }

    GIT_CREDENTIALS = {
        "store_type":              "osxkeychain",
        "store_types":             ["osxkeychain", "manager", "store", "cache", "none"],
        "cache_timeout_seconds":   900,
        "credential_file":         "~/.git-credentials",
        "helper":                  "osxkeychain",
    }

    # ------------------------------------------------------------------------
    # CREDENTIAL VAULT — Environment variable mapping for all secrets
    # Purpose: Single registry of every env var the app might need. Apps
    #          read this to know which env vars to check. Never store
    #          actual secrets in config — only the env var NAMES.
    # ------------------------------------------------------------------------
    CREDENTIALS = {
        # AI / ML
        "openai_api_key":          "OPENAI_API_KEY",
        "anthropic_api_key":       "ANTHROPIC_API_KEY",
        "cohere_api_key":          "COHERE_API_KEY",
        "huggingface_token":       "HUGGINGFACE_HUB_TOKEN",
        "replicate_api_token":     "REPLICATE_API_TOKEN",
        "together_api_key":        "TOGETHER_API_KEY",
        "groq_api_key":            "GROQ_API_KEY",
        "perplexity_api_key":      "PERPLEXITY_API_KEY",
        "mistral_api_key":         "MISTRAL_API_KEY",
        "deepseek_api_key":        "DEEPSEEK_API_KEY",
        # Vector DBs
        "pinecone_api_key":        "PINECONE_API_KEY",
        "qdrant_api_key":          "QDRANT_API_KEY",
        "weaviate_api_key":        "WEAVIATE_API_KEY",
        "milvus_api_key":          "MILVUS_API_KEY",
        # Cloud
        "aws_access_key_id":       "AWS_ACCESS_KEY_ID",
        "aws_secret_access_key":   "AWS_SECRET_ACCESS_KEY",
        "aws_region":              "AWS_DEFAULT_REGION",
        "gcp_project_id":          "GCP_PROJECT_ID",
        "gcp_credentials":         "GOOGLE_APPLICATION_CREDENTIALS",
        "azure_client_id":         "AZURE_CLIENT_ID",
        "azure_client_secret":     "AZURE_CLIENT_SECRET",
        "azure_tenant_id":         "AZURE_TENANT_ID",
        # Git
        "github_token":            "GITHUB_TOKEN",
        "gitlab_token":            "GITLAB_TOKEN",
        "bitbucket_app_password":  "BITBUCKET_APP_PASSWORD",
        # Database
        "mysql_password":          "MYSQL_PASSWORD",
        "postgres_password":       "POSTGRES_PASSWORD",
        "redis_password":          "REDIS_PASSWORD",
        "mongo_password":          "MONGO_PASSWORD",
        # Email
        "gmail_app_password":      "GMAIL_APP_PASSWORD",
        "yahoo_app_password":      "YAHOO_APP_PASSWORD",
        "outlook_password":        "OUTLOOK_PASSWORD",
        "sendgrid_api_key":        "SENDGRID_API_KEY",
        "mailgun_api_key":         "MAILGUN_API_KEY",
        "postmark_api_key":        "POSTMARK_API_KEY",
        # Communication
        "slack_bot_token":         "SLACK_BOT_TOKEN",
        "slack_webhook_url":       "SLACK_WEBHOOK_URL",
        "discord_bot_token":       "DISCORD_BOT_TOKEN",
        "teams_webhook_url":       "TEAMS_WEBHOOK_URL",
        "telegram_bot_token":      "TELEGRAM_BOT_TOKEN",
        # Monitoring
        "sentry_dsn":              "SENTRY_DSN",
        "datadog_api_key":         "DATADOG_API_KEY",
        "datadog_app_key":         "DATADOG_APP_KEY",
        "new_relic_license_key":   "NEW_RELIC_LICENSE_KEY",
        # Payment
        "stripe_secret_key":       "STRIPE_SECRET_KEY",
        "stripe_publishable_key":  "STRIPE_PUBLISHABLE_KEY",
        "stripe_webhook_secret":   "STRIPE_WEBHOOK_SECRET",
        "paypal_client_id":        "PAYPAL_CLIENT_ID",
        "paypal_client_secret":    "PAYPAL_CLIENT_SECRET",
        # Storage
        "digitalocean_token":      "DIGITALOCEAN_ACCESS_TOKEN",
        "cloudflare_api_token":    "CLOUDFLARE_API_TOKEN",
        "backblaze_key_id":        "B2_KEY_ID",
        "backblaze_app_key":       "B2_APPLICATION_KEY",
    }

    # ------------------------------------------------------------------------
    # JWT — Token signing, verification, claims
    # Purpose: Central source for JWT configuration.
    # ------------------------------------------------------------------------
    JWT = {
        "algorithm":               "HS256",
        "algorithms":              ["HS256", "HS384", "HS512",
                                    "RS256", "RS384", "RS512",
                                    "ES256", "ES384", "ES512",
                                    "PS256", "PS384", "PS512"],
        "secret_env":              "JWT_SECRET",
        "private_key_env":         "JWT_PRIVATE_KEY",
        "public_key_env":          "JWT_PUBLIC_KEY",
        "issuer":                  "",
        "audience":                "",
        "access_token_ttl":        900,
        "refresh_token_ttl":       604800,
        "leeway_seconds":          0,
        "verify_exp":              True,
        "verify_iat":              True,
        "verify_aud":              True,
        "verify_iss":              True,
        "verify_sub":              False,
        "verify_jti":              False,
        "require_exp":             True,
        "require_iat":             True,
        "require_sub":             True,
    }

    # ------------------------------------------------------------------------
    # API KEYS — Key management, rotation, validation
    # Purpose: Central source for API key lifecycle management.
    # ------------------------------------------------------------------------
    API_KEY_MANAGEMENT = {
        "header_name":             "X-API-Key",
        "query_param_name":        "api_key",
        "prefix":                  "vb_",
        "length":                  48,
        "encoding":                "hex",
        "hash_algorithm":          "sha256",
        "rotation_days":           90,
        "grace_period_days":       7,
        "max_keys_per_user":       5,
        "rate_limit_per_hour":     1000,
        "validate_on_request":     True,
        "store_hashed":            True,
    }

    # ------------------------------------------------------------------------
    # SERVICE ACCOUNTS — External service credentials registry
    # Purpose: Central registry for service-to-service authentication.
    # ------------------------------------------------------------------------
    SERVICE_ACCOUNTS = {
        "default": {
            "type":                "service_account",
            "auth_mode":           "api_key",
            "token_env":           "",
            "endpoint":            "",
            "timeout":             30,
        },
        "internal_api": {
            "type":                "service_account",
            "auth_mode":           "bearer",
            "token_env":           "INTERNAL_API_TOKEN",
            "endpoint":            "http://localhost:8000",
            "timeout":             10,
        },
    }

    # ------------------------------------------------------------------------
    # KEYRING / SECRET STORAGE — OS keyring integration
    # Purpose: Central config for storing secrets in OS keyring.
    # ------------------------------------------------------------------------
    KEYRING = {
        "backend":                 "auto",
        "backends":                ["auto", "osxkeychain", "windows", "kwallet",
                                    "secretstorage", "file"],
        "service_name":            "vbstyle_app",
        "key_prefix":              "vb_",
        "fallback_to_env":         True,
        "fallback_to_file":        False,
        "encrypted_file_path":     "",
    }

    # ------------------------------------------------------------------------
    # METHOD: GetIcon
    # Purpose: Return icon glyph or path by key
    # Params:  key (str) — one of: prev, next, search, clear, highlight,
    #          annotate, export, refresh, help, about, close, book,
    #          bookmark, settings, error, success
    # Returns: str — glyph or path, or empty string if not found
    # ------------------------------------------------------------------------
    def GetIcon(self, key):
        return Config.ICONS.get(key, "")

    # ------------------------------------------------------------------------
    # METHOD: GetShortcut
    # Purpose: Return keyboard shortcut string by action key
    # Params:  key (str) — one of: prev_page, next_page, search,
    #          clear_search, highlight, annotate, export, refresh,
    #          help, about, toggle_panel, close
    # Returns: str — Qt key sequence, or empty string if not found
    # ------------------------------------------------------------------------
    def GetShortcut(self, key):
        return Config.SHORTCUTS.get(key, "")

    # ------------------------------------------------------------------------
    # METHOD: GetButton
    # Purpose: Return button config dict by key
    # Params:  key (str) — one of: prev, next, export, refresh, help,
    #          about, search, clear, highlight, annotate
    # Returns: dict — {label, visible, icon} or None if not found
    # ------------------------------------------------------------------------
    def GetButton(self, key):
        return Config.BUTTONS.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetMenu
    # Purpose: Return the complete menu structure dict
    # Params:  None
    # Returns: dict — {MenuName: {ItemName: command_or_None}}
    # ------------------------------------------------------------------------
    def GetMenu(self, ):
        return Config.MENU

    # ------------------------------------------------------------------------
    # METHOD: GetWindow
    # Purpose: Return a window setting by key
    # Params:  key (str) — any key from WINDOW dict
    # Returns: value (str, int, or bool), or None if not found
    # ------------------------------------------------------------------------
    def GetWindow(self, key):
        return Config.WINDOW.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetSearch
    # Purpose: Return a search setting by key
    # Params:  key (str) — any key from SEARCH dict
    # Returns: value, or None if not found
    # ------------------------------------------------------------------------
    def GetSearch(self, key):
        return Config.SEARCH.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetAnnotation
    # Purpose: Return an annotation setting by key
    # Params:  key (str) — any key from ANNOTATION dict
    # Returns: value, or None if not found
    # ------------------------------------------------------------------------
    def GetAnnotation(self, key):
        return Config.ANNOTATION.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetFlipbook
    # Purpose: Return a flipbook setting by key
    # Params:  key (str) — any key from FLIPBOOK dict
    # Returns: value, or None if not found
    # ------------------------------------------------------------------------
    def GetFlipbook(self, key):
        return Config.FLIPBOOK.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetTts
    # Purpose: Return a TTS setting by key
    # Params:  key (str) — any key from TTS dict
    # Returns: value, or None if not found
    # ------------------------------------------------------------------------
    def GetTts(self, key):
        return Config.TTS.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetStatus
    # Purpose: Return a status message template by key
    # Params:  key (str) — any key from STATUS dict
    # Returns: str — message template (may contain {placeholders}), or ""
    # ------------------------------------------------------------------------
    def GetStatus(self, key):
        return Config.STATUS.get(key, "")

    # ------------------------------------------------------------------------
    # METHOD: GetError
    # Purpose: Return an error dict by key
    # Params:  key (str) — any key from ERRORS dict
    # Returns: dict — {message, action, command, details} or None if not found
    # ------------------------------------------------------------------------
    def GetError(self, key):
        return Config.ERRORS.get(key)

    # ------------------------------------------------------------------------
    # METHOD: GetAllSettings
    # Purpose: Return all configuration dicts as a single dict.
    #          Used by a future settings editor to load/save the entire config.
    # Params:  None
    # Returns: dict — {section_name: section_dict}
    # ------------------------------------------------------------------------
    def GetAllSettings(self, ):
        return {
            # --- Original sections ---
            "THEME":          Config.THEME,
            "ICONS":          Config.ICONS,
            "SHORTCUTS":      Config.SHORTCUTS,
            "BUTTONS":        Config.BUTTONS,
            "MENU":           Config.MENU,
            "WINDOW":         Config.WINDOW,
            "SEARCH":         Config.SEARCH,
            "ANNOTATION":     Config.ANNOTATION,
            "FLIPBOOK":       Config.FLIPBOOK,
            "TTS":            Config.TTS,
            "STATUS":         Config.STATUS,
            "ERRORS":         Config.ERRORS,
            "TOOLTIPS":       Config.TOOLTIPS,
            # --- AI / ML ---
            "EMBEDDING_MODELS":   Config.EMBEDDING_MODELS,
            "LLM_MODELS":         Config.LLM_MODELS,
            "QA_MODELS":          Config.QA_MODELS,
            "RERANKERS":          Config.RERANKERS,
            "VECTOR_BACKENDS":    Config.VECTOR_BACKENDS,
            "MODEL_DEVICE":       Config.MODEL_DEVICE,
            # --- Database ---
            "DB_PRAGMA":          Config.DB_PRAGMA,
            "DB_POOL":            Config.DB_POOL,
            "DB_BACKUP":          Config.DB_BACKUP,
            "DB_MIGRATION":       Config.DB_MIGRATION,
            # --- MCP ---
            "MCP_SERVERS":        Config.MCP_SERVERS,
            "MCP_PERMISSIONS":    Config.MCP_PERMISSIONS,
            "MCP_RESOURCES":      Config.MCP_RESOURCES,
            # --- Security ---
            "FILE_ACCESS":        Config.FILE_ACCESS,
            "NETWORK_ACCESS":     Config.NETWORK_ACCESS,
            "API_KEYS":           Config.API_KEYS,
            "RATE_LIMITS":        Config.RATE_LIMITS,
            # --- Logging ---
            "LOGGING":            Config.LOGGING,
            # --- Network ---
            "ENDPOINTS":          Config.ENDPOINTS,
            "PROXY":              Config.PROXY,
            # --- Performance ---
            "CACHE":              Config.CACHE,
            "MEMORY_LIMITS":      Config.MEMORY_LIMITS,
            "THREADING":          Config.THREADING,
            # --- I18N / A11Y ---
            "I18N":               Config.I18N,
            "A11Y":               Config.A11Y,
            # --- Export / Import ---
            "EXPORT":             Config.EXPORT,
            "IMPORT":             Config.IMPORT,
            # --- Plugins ---
            "PLUGINS":            Config.PLUGINS,
            # --- Editor ---
            "EDITOR":             Config.EDITOR,
            # --- Update ---
            "UPDATE":             Config.UPDATE,
            # --- Window State ---
            "WINDOW_STATE":       Config.WINDOW_STATE,
            # --- Telemetry ---
            "METRICS":            Config.METRICS,
            # --- Mouse / Gestures ---
            "MOUSE":              Config.MOUSE,
            "GESTURES":           Config.GESTURES,
            # --- Book Content ---
            "BOOK_META":          Config.BOOK_META,
            "CHAPTERS":           Config.CHAPTERS,
            # --- AI Pipeline ---
            "RETRIEVAL":          Config.RETRIEVAL,
            "PIPELINE":           Config.PIPELINE,
            "CLASSIFICATION":     Config.CLASSIFICATION,
            "FAILURE_STAGES":     Config.FAILURE_STAGES,
            "STORAGE":            Config.STORAGE,
            "EXECUTION":          Config.EXECUTION,
            # --- Notifications / Session ---
            "NOTIFICATIONS":      Config.NOTIFICATIONS,
            "SESSION":            Config.SESSION,
            # --- Features ---
            "FEATURES":           Config.FEATURES,
            # --- PyQt6 Widget Properties ---
            "PYQT_MAINWINDOW":          Config.PYQT_MAINWINDOW,
            "PYQT_WIDGET":              Config.PYQT_WIDGET,
            "PYQT_PUSHBUTTON":          Config.PYQT_PUSHBUTTON,
            "PYQT_LINEEDIT":            Config.PYQT_LINEEDIT,
            "PYQT_TEXTEDIT":            Config.PYQT_TEXTEDIT,
            "PYQT_LABEL":               Config.PYQT_LABEL,
            "PYQT_COMBOBOX":            Config.PYQT_COMBOBOX,
            "PYQT_SLIDER":              Config.PYQT_SLIDER,
            "PYQT_CHECKBOX":            Config.PYQT_CHECKBOX,
            "PYQT_RADIOBUTTON":         Config.PYQT_RADIOBUTTON,
            "PYQT_SPINBOX":             Config.PYQT_SPINBOX,
            "PYQT_DOUBLESPINBOX":       Config.PYQT_DOUBLESPINBOX,
            "PYQT_PROGRESSBAR":         Config.PYQT_PROGRESSBAR,
            "PYQT_TOOLBAR":             Config.PYQT_TOOLBAR,
            "PYQT_MENUBAR":             Config.PYQT_MENUBAR,
            "PYQT_STATUSBAR":           Config.PYQT_STATUSBAR,
            "PYQT_TABWIDGET":           Config.PYQT_TABWIDGET,
            "PYQT_SPLITTER":            Config.PYQT_SPLITTER,
            "PYQT_GROUPBOX":            Config.PYQT_GROUPBOX,
            "PYQT_LISTVIEW":            Config.PYQT_LISTVIEW,
            "PYQT_TREEVIEW":            Config.PYQT_TREEVIEW,
            "PYQT_TABLEVIEW":           Config.PYQT_TABLEVIEW,
            "PYQT_SCROLLAREA":          Config.PYQT_SCROLLAREA,
            "PYQT_WEBENGINEVIEW":       Config.PYQT_WEBENGINEVIEW,
            "PYQT_WEBENGINE_SETTINGS":  Config.PYQT_WEBENGINE_SETTINGS,
            "PYQT_DIALOG":              Config.PYQT_DIALOG,
            "PYQT_FILEDIALOG":          Config.PYQT_FILEDIALOG,
            "PYQT_INPUTDIALOG":         Config.PYQT_INPUTDIALOG,
            "PYQT_MESSAGEBOX":          Config.PYQT_MESSAGEBOX,
            "PYQT_TOOLBUTTON":          Config.PYQT_TOOLBUTTON,
            "PYQT_FONT":                Config.PYQT_FONT,
            "PYQT_PALETTE":             Config.PYQT_PALETTE,
            "PYQT_SIZEPOLICY":          Config.PYQT_SIZEPOLICY,
            "PYQT_SHORTCUT":            Config.PYQT_SHORTCUT,
            "PYQT_LAYOUT":              Config.PYQT_LAYOUT,
            "PYQT_BOXLAYOUT":           Config.PYQT_BOXLAYOUT,
            "PYQT_GRIDLAYOUT":          Config.PYQT_GRIDLAYOUT,
            "PYQT_FORMLAYOUT":          Config.PYQT_FORMLAYOUT,
            "PYQT_STACKEDLAYOUT":       Config.PYQT_STACKEDLAYOUT,
            "PYQT_FRAME":               Config.PYQT_FRAME,
            "PYQT_STRETCH_FACTORS":     Config.PYQT_STRETCH_FACTORS,
            "PYQT_POLICY_VALUES":       Config.PYQT_POLICY_VALUES,
            "PYQT_CONTROL_TYPE_VALUES": Config.PYQT_CONTROL_TYPE_VALUES,
            # --- PyQt6 Enum/Flag References ---
            "PYQT_CURSOR_SHAPES":           Config.PYQT_CURSOR_SHAPES,
            "PYQT_FOCUS_POLICIES":          Config.PYQT_FOCUS_POLICIES,
            "PYQT_CONTEXT_MENU_POLICIES":   Config.PYQT_CONTEXT_MENU_POLICIES,
            "PYQT_SCROLLBAR_POLICIES":      Config.PYQT_SCROLLBAR_POLICIES,
            "PYQT_WINDOW_FLAGS":            Config.PYQT_WINDOW_FLAGS,
            "PYQT_WINDOW_STATES":           Config.PYQT_WINDOW_STATES,
            "PYQT_ALIGNMENT_FLAGS":         Config.PYQT_ALIGNMENT_FLAGS,
            "PYQT_ORIENTATIONS":            Config.PYQT_ORIENTATIONS,
            "PYQT_TEXT_FORMATS":            Config.PYQT_TEXT_FORMATS,
            "PYQT_TEXT_INTERACTION_FLAGS":  Config.PYQT_TEXT_INTERACTION_FLAGS,
            "PYQT_CHECK_STATES":            Config.PYQT_CHECK_STATES,
            "PYQT_ECHO_MODES":              Config.PYQT_ECHO_MODES,
            "PYQT_LINE_WRAP_MODES":         Config.PYQT_LINE_WRAP_MODES,
            "PYQT_SELECTION_MODES":         Config.PYQT_SELECTION_MODES,
            "PYQT_SELECTION_BEHAVIORS":     Config.PYQT_SELECTION_BEHAVIORS,
            "PYQT_DRAG_DROP_MODES":         Config.PYQT_DRAG_DROP_MODES,
            "PYQT_EDIT_TRIGGERS":           Config.PYQT_EDIT_TRIGGERS,
            "PYQT_VIEW_MODES":              Config.PYQT_VIEW_MODES,
            "PYQT_TICK_POSITIONS":          Config.PYQT_TICK_POSITIONS,
            "PYQT_TAB_POSITIONS":           Config.PYQT_TAB_POSITIONS,
            "PYQT_TAB_SHAPES":              Config.PYQT_TAB_SHAPES,
            "PYQT_TOOL_BUTTON_STYLES":      Config.PYQT_TOOL_BUTTON_STYLES,
            "PYQT_MESSAGEBOX_ICONS":        Config.PYQT_MESSAGEBOX_ICONS,
            "PYQT_MESSAGEBOX_BUTTONS":      Config.PYQT_MESSAGEBOX_BUTTONS,
            "PYQT_FILE_DIALOG_MODES":       Config.PYQT_FILE_DIALOG_MODES,
            "PYQT_FILE_DIALOG_ACCEPT_MODES": Config.PYQT_FILE_DIALOG_ACCEPT_MODES,
            "PYQT_FILE_DIALOG_VIEW_MODES":  Config.PYQT_FILE_DIALOG_VIEW_MODES,
            "PYQT_INPUT_DIALOG_MODES":      Config.PYQT_INPUT_DIALOG_MODES,
            "PYQT_DIALOG_BUTTONS":          Config.PYQT_DIALOG_BUTTONS,
            "PYQT_DIALOG_BUTTON_ROLES":     Config.PYQT_DIALOG_BUTTON_ROLES,
            "PYQT_KEY_CODES":               Config.PYQT_KEY_CODES,
            "PYQT_KEYBOARD_MODIFIERS":      Config.PYQT_KEYBOARD_MODIFIERS,
            "PYQT_MOUSE_BUTTONS":           Config.PYQT_MOUSE_BUTTONS,
            "PYQT_ITEM_DATA_ROLES":         Config.PYQT_ITEM_DATA_ROLES,
            "PYQT_ITEM_FLAGS":              Config.PYQT_ITEM_FLAGS,
            "PYQT_LAYOUT_DIRECTIONS":       Config.PYQT_LAYOUT_DIRECTIONS,
            "PYQT_WIDGET_ATTRIBUTES":       Config.PYQT_WIDGET_ATTRIBUTES,
            "PYQT_FRAME_SHAPES":            Config.PYQT_FRAME_SHAPES,
            "PYQT_FRAME_SHADOWS":           Config.PYQT_FRAME_SHADOWS,
            "PYQT_SIZE_CONSTRAINTS":        Config.PYQT_SIZE_CONSTRAINTS,
            "PYQT_QSS_SELECTORS":           Config.PYQT_QSS_SELECTORS,
            "PYQT_QSS_PROPERTIES":          Config.PYQT_QSS_PROPERTIES,
            "PYQT_QSS_PSEUDO_STATES":       Config.PYQT_QSS_PSEUDO_STATES,
            "PYQT_QSS_SUB_CONTROLS":        Config.PYQT_QSS_SUB_CONTROLS,
            # --- Hugging Face ---
            "HUGGINGFACE":                  Config.HUGGINGFACE,
            "HUGGINGFACE_MODELS":           Config.HUGGINGFACE_MODELS,
            "HUGGINGFACE_PIPELINE_TYPES":   Config.HUGGINGFACE_PIPELINE_TYPES,
            "HUGGINGFACE_QUANTIZATION":     Config.HUGGINGFACE_QUANTIZATION,
            # --- GitHub ---
            "GITHUB":                       Config.GITHUB,
            "GITHUB_AUTH":                  Config.GITHUB_AUTH,
            "GITHUB_WEBHOOK":               Config.GITHUB_WEBHOOK,
            "GITHUB_ACTIONS":               Config.GITHUB_ACTIONS,
            # --- GitLab ---
            "GITLAB":                       Config.GITLAB,
            "GITLAB_CI":                    Config.GITLAB_CI,
            # --- Bitbucket ---
            "BITBUCKET":                    Config.BITBUCKET,
            # --- Authentication / Login ---
            "AUTH":                         Config.AUTH,
            "OAUTH_PROVIDERS":              Config.OAUTH_PROVIDERS,
            # --- SSH / Git Credentials ---
            "SSH":                          Config.SSH,
            "GIT_CREDENTIALS":              Config.GIT_CREDENTIALS,
            # --- Credential Vault ---
            "CREDENTIALS":                  Config.CREDENTIALS,
            # --- JWT ---
            "JWT":                          Config.JWT,
            # --- API Key Management ---
            "API_KEY_MANAGEMENT":           Config.API_KEY_MANAGEMENT,
            # --- Service Accounts ---
            "SERVICE_ACCOUNTS":             Config.SERVICE_ACCOUNTS,
            # --- Keyring / Secret Storage ---
            "KEYRING":                      Config.KEYRING,
        }


# ============================================================================
# SINGLETON INSTANCE — VBStyle compliant (no @staticmethod)
# Use cfg.Method() instead of Config.Method()
# ============================================================================
cfg = Config()
