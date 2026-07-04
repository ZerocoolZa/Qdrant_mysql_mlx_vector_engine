#!/usr/bin/env python3
"""Edge case test file for config_extractor.py"""

import os
from pathlib import Path

# ── Module constants ────────────────────────────────────────────
DB_PATH = "test.db"
MAX_RETRIES = 3
TIMEOUT_MS = 5000
ENABLED = True
PI = 3.14159
ZERO = 0
NEGATIVE = -1
EMPTY_STRING = ""
LONG_STRING = "a" * 200

# ── Path expressions (should these be caught?) ──────────────────
BASE = Path(__file__).parent
NESTED_PATH = Path(__file__).parent / "db" / "data.db"
CONCAT_PATH = str(BASE / "config" / "settings.json")

# ── Dict/list constants ─────────────────────────────────────────
COLOR_MAP = {"red": "#FF0000", "blue": "#0000FF", "green": "#00FF00"}
FONT_SIZES = [12, 14, 16, 18, 20]
WEIGHTS = ("bold", "normal", "light")
NESTED_DICT = {
    "color": {"bg": "#FFFFFF", "text": "#000000"},
    "font": {"size": 14, "weight": "normal"},
}

# ── Constants with expressions ──────────────────────────────────
COMPUTED = 60 * 60 * 24
DYNAMIC = os.environ.get("MY_VAR", "default_value")
BINARY = 0b1010
HEX_VAL = 0xFF
SCIENTIFIC = 1e5

# ── Class with various patterns ─────────────────────────────────
class TestWidget:
    def __init__(self, mem=None, db=None, param=None):
        self.color = "#FF5733"
        self.size = 22
        self.path = "/usr/local/bin"
        self.port = 8080
        self.enabled = True
        self.ratio = 0.85
    
    def configure(self, width=400, height=300, title="My App", resizable=True):
        pass
    
    def render(self, bg_color="#FFFFFF", opacity=1.0, font_size=14):
        style = self._get_style("background", "#EEEEEE")
        border = self._get_style("border", "#000000")
        padding = self._get_style("padding", 8)
        return style
    
    def _get_style(self, key, fallback):
        return fallback
    
    def load_config(self, config_path="config/settings.json"):
        with open(config_path, "r") as f:
            pass

# ── Nested class ────────────────────────────────────────────────
class OuterClass:
    class InnerAuthority:
        def Run(self, command="default", count=10):
            pass
        
        def read_state(self):
            return {"status": "active", "count": 0}
    
    def __init__(self):
        self.state = {}

# ── Edge cases ──────────────────────────────────────────────────
SINGLE_QUOTE = 'single'
DOUBLE_QUOTE = "double"
MIXED_QUOTES = "it's a test"
UNICODE = "café"
MULTILINE_STR = """this is
a multiline
string"""
RAW_STRING = r"C:\Users\test"

# Numbers that should/shouldn't be caught
PORT = 7011
BIG_NUMBER = 999999
SMALL_FLOAT = 0.001
SCORE = 0.95
PERCENT = 100
ZERO_FLOAT = 0.0
NEGATIVE_FLOAT = -0.5

# String that looks like config but isn't
ERROR_MSG = "Something went wrong at line 42 in module foo_bar"
SQL_QUERY = "SELECT * FROM users WHERE id = ?"
REGEX_PATTERN = r"^[a-z][a-z_]+$"

# Boolean-like
IS_DEBUG = False
IS_PROD = True

# Tuple unpacking (should NOT be caught as constant)
X, Y, Z = 1, 2, 3

# Augmented assignment (should NOT be caught)
COUNT = 0
COUNT += 1

# Multiple assignment
A = B = C = "shared_value"

# Conditional expression
DYNAMIC_TITLE = "App" if IS_DEBUG else "MyApp"

# f-strings (should NOT be caught as string literals)
NAME = "test"
FSTRING = f"Hello {NAME}"
