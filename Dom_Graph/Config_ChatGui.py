#!/usr/bin/env python3
#[@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Config_ChatGui.py"
# date="2026-06-27" author="Cascade" session_id="chat-gui-config"
# context="Config constants for ChatGui.py — colors, fonts, DB, autocomplete, slash commands, tokens"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="UPPERCASE constants only"}
#[@FILEID]{id="Config_ChatGui.py" domain="chat_gui" authority="Config"}
#[@SUMMARY]{summary="All ChatGui constants extracted from ChatGui.py. Colors, fonts, DB config, slash commands, fallback tokens, autocomplete config, ghost-text settings, SQL queries for bigram/trigram prediction, stop words, ranking weights."}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<ChatGui constants: colors, fonts, DB config, slash commands, autocomplete, SQL queries. UPPERCASE constants only, no class. Has hardcoded DB credentials (root, empty password) and DEVIN_CMD path. Author=Cascade not Devin.>][@todos<Move DB credentials to environment variables. Fix author to Devin. Consider wrapping in Config class for consistency.>]}

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Devin CLI ─────────────────────────────────────────────────
DEVIN_CMD = os.path.expanduser("~/.local/bin/devin")

# ── MySQL Connection ──────────────────────────────────────────
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_SHARED = "vb_shared"
DB_DEVIN = "devin"
DB_CODE_TEST = "vb_code_test"

# ── Colors ────────────────────────────────────────────────────
COLOR_BG = "#1e1e1e"
COLOR_PANEL = "#252526"
COLOR_INPUT = "#2d2d30"
COLOR_TEXT = "#d4d4d4"
COLOR_USER = "#569cd6"
COLOR_ASSISTANT = "#4ec9b0"
COLOR_SYSTEM = "#c586c0"
COLOR_BUTTON = "#0e639c"
COLOR_BUTTON_HOVER = "#1177bb"
COLOR_BORDER = "#3c3c3c"

# ── Font Sizes ────────────────────────────────────────────────
FONT_CHAT = 14
FONT_INPUT = 14
FONT_HEADER = 16
FONT_BUTTON = 13
FONT_SMALL = 12
FONT_TABLE = 12
FONT_LIST = 13
FONT_STATUS = 11
FONT_FAMILY = "Menlo"

# ── Ghost Text Color (predictive autocomplete) ────────────────
GHOST_TEXT_R = 120
GHOST_TEXT_G = 130
GHOST_TEXT_B = 145

# ── Slash Commands ────────────────────────────────────────────
SLASH_COMMANDS = [
    "/help          - Show available commands",
    "/clear         - Clear chat display",
    "/sessions      - Switch to Sessions tab",
    "/search        - Switch to Knowledge Base tab",
    "/refresh       - Reload session list",
    "/new           - Start new session (deselect current)",
    "/status        - Show current session and status",
    "/cwd           - Show working directory",
    "/rules         - List VBStyle rules from obey.md",
    "/tags          - List all @ tags from token registry",
    "/db            - Search MySQL knowledge base",
    "/code          - Search vb_classes and vb_methods",
    "/problems      - Search known problems",
    "/solutions     - Search known solutions",
    "/rules-db      - Search learned rules",
    "/memunit       - Query MemUnit reasoning state",
    "/bcl           - Query BCL code graph",
    "/stamp         - Query BCL stamps",
    "/gate          - Run pre-execution gate validation",
]

# ── Fallback @ Tokens ─────────────────────────────────────────
FALLBACK_TOKENS = [
    "@mem", "@task", "@plan", "@idea", "@impl", "@roadmap",
    "@codespec", "@meta", "@rules", "@aicomms", "@commsmap", "@logic",
    "@scope", "@must", "@target", "@report", "@safe", "@block",
    "@ban", "@return", "@patch", "@gate", "@proof", "@search",
    "@judge", "@writelock", "@context", "@root", "@nobulk",
    "@dontknow", "@unsure", "@noexec", "@useremotion", "@collab",
    "@noedit", "@nofiles", "@exact", "@noarch", "@norule",
    "@underscore", "@decorators", "@enums", "@print", "@hidden",
    "@hardcode", "@tabs", "@whitespace", "@intstate", "@params",
    "@tuples", "@domain", "@dismap", "@memunit", "@ghost",
    "@vbsty", "@cstyle", "@clshdr", "@mthdr", "@pascal",
    "@upper", "@ctor", "@state", "@noself", "@run",
    "@rdst", "@cfg", "@phelp", "@disp", "@succ",
    "@err", "@t3", "@errfmt", "@auth", "@ram",
    "@rpt", "@selfdb", "@authdb", "@dep", "@mdep",
    "@runst", "@exec", "@know", "@conf", "@meth",
    "@dcon", "@reg", "@exp", "@clu", "@map",
    "@col", "@hrt", "@hst",
    "@rationale", "@decision", "@why", "@problem", "@solution",
    "@fix", "@error", "@action", "@created", "@modified",
    "@result", "@status", "@priority", "@what", "@when",
    "@where", "@how", "@before", "@after",
]

# ── Autocomplete DB ───────────────────────────────────────────
AUTOCOMPLETE_DB_PATH = str(
    BASE_DIR.parent / "Dom_Smart_system_seach" / "autocomplete.db"
)

# ── Autocomplete Timer (ms) ───────────────────────────────────
TIMER_AUTOCOMPLETE = 250

# ── Autocomplete Limits ───────────────────────────────────────
AUTOCOMPLETE_PREFIX_LIMIT = 20
AUTOCOMPLETE_NEXT_LIMIT = 20
AUTOCOMPLETE_WORD_SCAN = 500
AUTOCOMPLETE_PREFIX_MIN = 1
AUTOCOMPLETE_MIN_WORD_LEN = 2

# ── Ranking Weights ───────────────────────────────────────────
RANK_WEIGHT_SYMBOL = 100
RANK_WEIGHT_TRIGRAM = 80
RANK_WEIGHT_BIGRAM = 60
RANK_WEIGHT_PREFIX = 40
RANK_WEIGHT_USER_HISTORY = 120

# ── SQL: Bigram/Trigram/WordFreq/UserHistory ──────────────────
SQL_SELECT_BIGRAM_NEXT = (
    'SELECT w2, freq FROM bigrams WHERE w1 = ? ORDER BY freq DESC LIMIT 20'
)
SQL_SELECT_TRIGRAM_NEXT = (
    'SELECT w3, freq FROM trigrams WHERE w1 = ? AND w2 = ? ORDER BY freq DESC LIMIT 20'
)
SQL_SELECT_WORD_PREFIX = (
    'SELECT word, freq FROM word_freq WHERE word LIKE ? ORDER BY freq DESC LIMIT 20'
)
SQL_CREATE_USER_HISTORY = (
    'CREATE TABLE IF NOT EXISTS user_history '
    '(word TEXT, context TEXT, freq INTEGER, PRIMARY KEY(word, context))'
)
SQL_UPSERT_USER_HISTORY = (
    'INSERT INTO user_history (word, context, freq) VALUES (?, ?, 1) '
    'ON CONFLICT(word, context) DO UPDATE SET freq = freq + 1'
)
SQL_SELECT_USER_HISTORY_PREFIX = (
    'SELECT word, freq FROM user_history '
    'WHERE word LIKE ? AND context = ? ORDER BY freq DESC LIMIT 20'
)

# ── Stop Words ────────────────────────────────────────────────
STOP_WORDS = frozenset({
    'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'a', 'an', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
    'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where',
    'when', 'why', 'how', 'there', 'here', 'if', 'then', 'else', 'because',
    'although', 'though', 'while', 'since', 'until', 'unless', 'before',
    'after', 'during', 'through', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'both',
    'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'also', 'now', 'get', 'like', 'know', 'mean', 'well', 'back', 'still',
})

# ── Window Settings ───────────────────────────────────────────
WINDOW_TITLE = "Devin Chat GUI"
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 600
WINDOW_WIDTH_RATIO = 0.35
WINDOW_HEIGHT_RATIO = 0.9

# ── Toolbar ───────────────────────────────────────────────────
TOOLBAR_WIDTH = 48
TOOLBAR_BUTTON_SIZE = 40
TOOLBAR_ICON_KB = "\U0001F50D"
TOOLBAR_ICON_SESSIONS = "\u2630"

# ── Splitter ──────────────────────────────────────────────────
SPLITTER_CHAT_SIZE = 700
SPLITTER_RIGHT_SIZE = 500

# ── Chat Bubbles ──────────────────────────────────────────────
BUBBLE_COLOR_USER = "#264f78"
BUBBLE_COLOR_ASSISTANT = "#2d2d30"
BUBBLE_COLOR_SYSTEM = "#1e1e1e"
BUBBLE_COLOR_SYSTEM_BORDER = "#3c3c3c"
BUBBLE_COLOR_ERROR = "#5a1e1e"
BUBBLE_TEXT_COLOR_USER = "white"
BUBBLE_TEXT_COLOR_ASSISTANT = "#4ec9b0"
BUBBLE_TEXT_COLOR_SYSTEM = "#c586c0"
BUBBLE_TEXT_COLOR_ERROR = "#f44747"
BUBBLE_RADIUS = 10
BUBBLE_PADDING = 10
BUBBLE_LABEL_FONT = 11
BUBBLE_TIME_FONT = 10

# ── Status Indicator ──────────────────────────────────────────
COLOR_READY = "#4ec9b0"
COLOR_BUSY = "#d29922"
COLOR_ERROR = "#f44747"
STATUS_DOT_SIZE = 12

# ── Role Labels ───────────────────────────────────────────────
ROLE_LABEL_USER = "YOU"
ROLE_LABEL_ASSISTANT = "DEVIN"
ROLE_LABEL_SYSTEM = "SYSTEM"
ROLE_LABEL_ERROR = "ERROR"

# ── Theme Presets ─────────────────────────────────────────────
THEMES = {
    "VSCode Dark": {
        "bg": "#1e1e1e", "panel": "#252526", "input": "#2d2d30",
        "text": "#d4d4d4", "border": "#3c3c3c", "button": "#0e639c",
        "button_hover": "#1177bb", "user_bg": "#264f78", "assistant_bg": "#2d2d30",
        "system_bg": "#1e1e1e", "user": "#569cd6", "assistant": "#4ec9b0", "system": "#ce9178",
    },
    "Midnight Blue": {
        "bg": "#0f172a", "panel": "#1e293b", "input": "#334155",
        "text": "#e2e8f0", "border": "#475569", "button": "#2563eb",
        "button_hover": "#1d4ed8", "user_bg": "#1e40af", "assistant_bg": "#1e293b",
        "system_bg": "#0f172a", "user": "#60a5fa", "assistant": "#38bdf8", "system": "#f59e0b",
    },
    "Solarized Dark": {
        "bg": "#002b36", "panel": "#073642", "input": "#094856",
        "text": "#93a1a1", "border": "#586e75", "button": "#268bd2",
        "button_hover": "#3699d2", "user_bg": "#1a4a5a", "assistant_bg": "#073642",
        "system_bg": "#002b36", "user": "#268bd2", "assistant": "#2aa198", "system": "#cb4b16",
    },
    "GitHub Dark": {
        "bg": "#0d1117", "panel": "#161b22", "input": "#21262d",
        "text": "#e6edf3", "border": "#30363d", "button": "#238636",
        "button_hover": "#2ea043", "user_bg": "#1f6feb", "assistant_bg": "#21262d",
        "system_bg": "#0d1117", "user": "#58a6ff", "assistant": "#3fb950", "system": "#d29922",
    },
    "Monokai": {
        "bg": "#272822", "panel": "#2d2e27", "input": "#3e3d32",
        "text": "#f8f8f2", "border": "#49483e", "button": "#fd971f",
        "button_hover": "#eda71f", "user_bg": "#59545a", "assistant_bg": "#3e3d32",
        "system_bg": "#272822", "user": "#66d9ef", "assistant": "#a6e22e", "system": "#cc7832",
    },
    "One Dark Pro": {
        "bg": "#282c34", "panel": "#21252b", "input": "#2c313a",
        "text": "#abb2bf", "border": "#3b4048", "button": "#4d78cc",
        "button_hover": "#5d88dc", "user_bg": "#3a4f6a", "assistant_bg": "#2c313a",
        "system_bg": "#282c34", "user": "#61afef", "assistant": "#98c379", "system": "#e06c75",
    },
    "Nord": {
        "bg": "#2e3440", "panel": "#3b4252", "input": "#434c5e",
        "text": "#d8dee9", "border": "#4c566a", "button": "#88c0d0",
        "button_hover": "#98d0e0", "user_bg": "#5e81ac", "assistant_bg": "#434c5e",
        "system_bg": "#2e3440", "user": "#81a1c1", "assistant": "#a3be8c", "system": "#d08770",
    },
    "Gruvbox Dark": {
        "bg": "#282828", "panel": "#3c3836", "input": "#504945",
        "text": "#ebdbb2", "border": "#665c54", "button": "#d79921",
        "button_hover": "#e7a931", "user_bg": "#7c6f64", "assistant_bg": "#504945",
        "system_bg": "#282828", "user": "#83a598", "assistant": "#b8bb26", "system": "#fb4934",
    },
    "Everforest Dark": {
        "bg": "#2d353b", "panel": "#343f44", "input": "#3d484d",
        "text": "#d3c6aa", "border": "#475258", "button": "#7fbbb3",
        "button_hover": "#8fcbb3", "user_bg": "#475258", "assistant_bg": "#3d484d",
        "system_bg": "#2d353b", "user": "#83c098", "assistant": "#a7c080", "system": "#e69875",
    },
    "Steel Gray": {
        "bg": "#1a1a1a", "panel": "#242424", "input": "#2e2e2e",
        "text": "#c8c8c8", "border": "#3a3a3a", "button": "#4a6fa5",
        "button_hover": "#5a7fb5", "user_bg": "#3a5a8a", "assistant_bg": "#2e2e2e",
        "system_bg": "#1a1a1a", "user": "#6a9fd5", "assistant": "#8ab4d8", "system": "#cc7832",
    },
    "Matrix Green": {
        "bg": "#000000", "panel": "#0a0a0a", "input": "#0f0f0f",
        "text": "#00ff41", "border": "#1a3a1a", "button": "#008f11",
        "button_hover": "#00bf15", "user_bg": "#1a3a1a", "assistant_bg": "#0f0f0f",
        "system_bg": "#000000", "user": "#00ff41", "assistant": "#39ff14", "system": "#0affef",
    },
    "Terminal Amber": {
        "bg": "#1a0a00", "panel": "#241200", "input": "#2e1800",
        "text": "#ffb000", "border": "#3a2400", "button": "#cc7700",
        "button_hover": "#dd8800", "user_bg": "#3a2400", "assistant_bg": "#2e1800",
        "system_bg": "#1a0a00", "user": "#ffb000", "assistant": "#ffcc44", "system": "#ff6600",
    },
    "Military": {
        "bg": "#1c1c16", "panel": "#26261e", "input": "#303028",
        "text": "#c5c5a8", "border": "#3a3a30", "button": "#5a6a3a",
        "button_hover": "#6a7a4a", "user_bg": "#3a4a2a", "assistant_bg": "#303028",
        "system_bg": "#1c1c16", "user": "#8a9a5a", "assistant": "#a5b56a", "system": "#cc8833",
    },
    "Carbon": {
        "bg": "#0a0a0a", "panel": "#141414", "input": "#1c1c1c",
        "text": "#b0b0b0", "border": "#2a2a2a", "button": "#3a3a3a",
        "button_hover": "#4a4a4a", "user_bg": "#2a2a2a", "assistant_bg": "#1c1c1c",
        "system_bg": "#0a0a0a", "user": "#6a9fd5", "assistant": "#5a5a5a", "system": "#cc5555",
    },
    "Cobalt": {
        "bg": "#0a0e27", "panel": "#111638", "input": "#1a1f4a",
        "text": "#c8d4ff", "border": "#2a3060", "button": "#1a5fb4",
        "button_hover": "#2a6fc4", "user_bg": "#1a3a6a", "assistant_bg": "#1a1f4a",
        "system_bg": "#0a0e27", "user": "#4a9fff", "assistant": "#00b4d8", "system": "#ff9500",
    },
    "Rust": {
        "bg": "#1a1208", "panel": "#241a0e", "input": "#2e2214",
        "text": "#d4a86a", "border": "#3a2e1a", "button": "#b85c00",
        "button_hover": "#c86c10", "user_bg": "#3a2a14", "assistant_bg": "#2e2214",
        "system_bg": "#1a1208", "user": "#cc8833", "assistant": "#aa7744", "system": "#ff6633",
    },
}
CURRENT_THEME = "VSCode Dark"

# ── Window Opacity ────────────────────────────────────────────
WINDOW_OPACITY = 1.0

# ── Voice / TTS ───────────────────────────────────────────────
VOICE_ENABLED = False
VOICE_NAME = "Samantha"
VOICE_RATE = 180
VOICE_TTS_ENGINE = "say"

# ── Voice / STT ───────────────────────────────────────────────
STT_ENABLED = False
STT_LANGUAGE = "en-US"
STT_ON_DEVICE = True          # Force on-device recognition (privacy + speed)
STT_BUFFER_SIZE = 4096        # Audio buffer size in samples (bigger = better capture)
STT_SILENCE_TIMEOUT = 2.5     # Seconds of silence before auto-finalizing
STT_MIN_LISTEN = 1.0          # Minimum listen time before silence detection kicks in
STT_MAX_TIMEOUT = 60          # Maximum listen time in seconds
STT_RUNLOOP_INTERVAL = 0.05   # NSRunLoop pump interval (seconds)
STT_SILENCE_THRESHOLD = 0.01  # RMS audio level threshold for speech vs silence

# ── macOS say voices (popular subset) ─────────────────────────
MACOS_VOICES = [
    "Samantha", "Alex", "Daniel", "Karen", "Moira", "Tessa",
    "Fiona", "Veena", "Susan", "Allison", "Ava", "Tom",
    "Lee", "Olivia", "Serena", "Nora", "Rishi", "Aaron",
]

# ── Settings persistence ──────────────────────────────────────
SETTINGS_FILE = str(BASE_DIR / "chatgui_settings.json")
