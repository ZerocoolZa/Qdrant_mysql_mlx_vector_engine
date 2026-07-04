#[@GHOST]{[@file<Config.py>][@domain<layout_engine_config>][@role<configuration>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<config>][@return<Tuple3>][@state<paths,limits,defaults>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/Config.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Configuration constants for the unified Layout Graph kernel (terminal + Qt)}
#[@CLASS]{Config — holds paths, layout defaults, breakpoint thresholds, solver params}
#[@METHOD]{none — constants only}

import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

PYTHON_BIN = "/usr/local/bin/python3"

# ---------------------------------------------------------------------------
# Viewport / terminal defaults
# ---------------------------------------------------------------------------
DEFAULT_TERM_WIDTH = 120
DEFAULT_TERM_HEIGHT = 40
DEFAULT_QT_WIDTH = 1280
DEFAULT_QT_HEIGHT = 800
MIN_VIEWPORT_WIDTH = 20
MIN_VIEWPORT_HEIGHT = 10

# ---------------------------------------------------------------------------
# Bootstrap-like responsive breakpoints (width in cells / px)
# 12-column grid. Below a breakpoint, columns collapse to stacked rows.
# ---------------------------------------------------------------------------
BREAKPOINT_XS = 0
BREAKPOINT_S = 48
BREAKPOINT_M = 80
BREAKPOINT_L = 110
BREAKPOINT_XL = 160
BREAKPOINT_ORDER = ["xs", "s", "m", "l", "xl"]
BREAKPOINT_THRESHOLDS = {
    "xs": BREAKPOINT_XS,
    "s": BREAKPOINT_S,
    "m": BREAKPOINT_M,
    "l": BREAKPOINT_L,
    "xl": BREAKPOINT_XL,
}
GRID_COLUMNS = 12
GUTTER_DEFAULT = 1
PADDING_DEFAULT = 1

# ---------------------------------------------------------------------------
# Constraint solver defaults
# ---------------------------------------------------------------------------
WEIGHT_DEFAULT = 1.0
FLEX_GROW_DEFAULT = 0.0
FLEX_SHRINK_DEFAULT = 1.0
MIN_SIZE_DEFAULT = 0
MAX_SIZE_DEFAULT = 1000000
PRIORITY_NORMAL = 0
PRIORITY_HIGH = 100
PRIORITY_FORCE = 1000
OVERFLOW_STRATEGY = "shrink"   # shrink | clip | scroll | wrap
ALIGN_DEFAULT = "start"        # start | center | end | stretch
JUSTIFY_DEFAULT = "start"      # start | center | end | between | around | evenly
DIRECTION_DEFAULT = "row"      # row | column | row-reverse | column-reverse
WRAP_DEFAULT = "nowrap"        # nowrap | wrap | wrap-reverse

# ---------------------------------------------------------------------------
# Invalidation / lifecycle
# ---------------------------------------------------------------------------
DIRTY_NONE = 0
DIRTY_MEASURE = 1
DIRTY_LAYOUT = 2
DIRTY_RENDER = 4
DIRTY_ALL = 7
CACHE_ENABLED = True

# ---------------------------------------------------------------------------
# ANSI theme defaults
# ---------------------------------------------------------------------------
ANSI_RESET = "\x1b[0m"
ANSI_BOLD = "\x1b[1m"
ANSI_DIM = "\x1b[2m"
ANSI_ITALIC = "\x1b[3m"
ANSI_UNDERLINE = "\x1b[4m"
ANSI_BLINK = "\x1b[5m"
ANSI_REVERSE = "\x1b[7m"
ANSI_STRIKE = "\x1b[9m"

THEME_DARK = {
    "bg": "\x1b[48;5;236m",
    "fg": "\x1b[38;5;255m",
    "muted": "\x1b[38;5;245m",
    "accent": "\x1b[38;5;39m",
    "border": "\x1b[38;5;240m",
    "title": "\x1b[38;5;213m",
    "ok": "\x1b[38;5;114m",
    "warn": "\x1b[38;5;221m",
    "err": "\x1b[38;5;203m",
    "row_alt": "\x1b[48;5;238m",
}

THEME_LIGHT = {
    "bg": "\x1b[48;5;255m",
    "fg": "\x1b[38;5;232m",
    "muted": "\x1b[38;5;242m",
    "accent": "\x1b[38;5;27m",
    "border": "\x1b[38;5;250m",
    "title": "\x1b[38;5;93m",
    "ok": "\x1b[38;5;29m",
    "warn": "\x1b[38;5;130m",
    "err": "\x1b[38;5;124m",
    "row_alt": "\x1b[48;5;254m",
}

THEME_PRESETS = {"dark": THEME_DARK, "light": THEME_LIGHT}
THEME_DEFAULT = "dark"

# ---------------------------------------------------------------------------
# CJK / text layout
# ---------------------------------------------------------------------------
CJK_WIDE_RANGES = [
    (0x1100, 0x115F), (0x2E80, 0x303E), (0x3040, 0x33BF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
    (0xFE10, 0xFE19), (0xFE30, 0xFE6F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6),
    (0x1F300, 0x1F64F), (0x1F900, 0x1F9FF), (0x20000, 0x2FFFD), (0x30000, 0x3FFFD),
]
TAB_WIDTH = 4
WRAP_WORD = "word"
WRAP_CHAR = "char"
WRAP_HARD = "hard"
ELLIPSIS = "..."
TRUNCATE_DEFAULT = 200

# ---------------------------------------------------------------------------
# Node kinds
# ---------------------------------------------------------------------------
KIND_CONTAINER = "container"
KIND_ROW = "row"
KIND_COLUMN = "column"
KIND_BLOCK = "block"
KIND_WIDGET = "widget"
KIND_TEXT = "text"
KIND_TABLE = "table"
KIND_TREE = "tree"
KIND_PIPELINE = "pipeline"
KIND_SPACER = "spacer"
KIND_DIVIDER = "divider"

# ---------------------------------------------------------------------------
# Render targets
# ---------------------------------------------------------------------------
TARGET_TERMINAL = "terminal"
TARGET_QT = "qt"


def ensure_output_dir():
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    return (1, OUTPUT_DIR, None)
