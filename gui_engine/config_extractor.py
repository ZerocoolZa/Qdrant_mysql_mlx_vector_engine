#!/usr/bin/env python3
"""
ConfigExtractor — regex-based, no AST needed.
Reads any Python file (even with syntax errors) and extracts config-like values.

Usage: python3 config_extractor.py <source.py> [source2.py ...] > Config.py
"""

import sys
import re
from pathlib import Path


def extract_from_file(filepath):
    src = Path(filepath).read_text()
    fname = Path(filepath).name
    results = {
        'file': fname,
        'constants': {},
        'strings': set(),
        'numbers': set(),
        'defaults': {},
        'get_fallbacks': {},
        'classes': [],
        'methods': {},
    }

    # Module-level constants: UPPER_CASE = value
    for m in re.finditer(r'^([A-Z][A-Z_0-9]+)\s*=\s*(.+?)$', src, re.MULTILINE):
        name = m.group(1)
        raw = m.group(2).strip()
        val = parse_literal(raw)
        if val is not None:
            results['constants'][name] = val

    # Class names
    for m in re.finditer(r'^class\s+(\w+)', src, re.MULTILINE):
        results['classes'].append(m.group(1))

    # Method names per class
    current_class = None
    for line in src.split('\n'):
        cm = re.match(r'^class\s+(\w+)', line)
        if cm:
            current_class = cm.group(1)
            results['methods'][current_class] = []
            continue
        if current_class:
            mm = re.match(r'^\s+def\s+(\w+)', line)
            if mm:
                results['methods'][current_class].append(mm.group(1))

    # Default parameters: def foo(self, x="value", y=42)
    for m in re.finditer(r'def\s+\w+\s*\(([^)]*)\)', src, re.DOTALL):
        params = m.group(1)
        for pm in re.finditer(r'(\w+)\s*=\s*([^,)]+)', params):
            pname = pm.group(1)
            praw = pm.group(2).strip()
            if pname in ('self', 'mem', 'db', 'param'):
                continue
            val = parse_literal(praw)
            if val is not None:
                results['defaults'][pname] = val

    # .get("key", "fallback") calls
    for m in re.finditer(r'\.get\(\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\)', src):
        key = m.group(1)
        fallback_raw = m.group(2).strip()
        val = parse_literal(fallback_raw)
        if val is not None:
            results['get_fallbacks'][key] = val

    # All string literals
    for m in re.finditer(r'["\']([^"\']{1,200})["\']', src):
        s = m.group(1)
        if is_config_string(s):
            results['strings'].add(s)

    # All number literals
    for m in re.finditer(r'(?<![\w.])(\d+\.?\d*)(?![\w.])', src):
        raw = m.group(1)
        try:
            if '.' in raw:
                n = float(raw)
            else:
                n = int(raw)
            if is_config_number(n):
                results['numbers'].add(n)
        except ValueError:
            pass

    return results


def parse_literal(raw):
    raw = raw.strip().rstrip(',')
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw in ('None', 'True', 'False'):
        return raw == 'True' if raw != 'None' else None
    try:
        if '.' in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return None


def is_config_string(s):
    if not s or len(s) > 200:
        return False
    if s.endswith('.db') or s.endswith('.sql'):
        return True
    if re.match(r'^#[0-9A-Fa-f]{3,8}$', s):
        return True
    if re.match(r'^[a-z][a-z_]+$', s) and '_' in s and len(s) > 3:
        return True
    if s in ('color', 'font', 'format', 'spacing', 'background', 'text',
             'border', 'padding', 'margin', 'size', 'weight', 'border_width'):
        return True
    if s in ('bold', 'normal', 'light'):
        return True
    if '/' in s and not s.startswith('http') and len(s) < 100:
        return True
    if s.isdigit() and len(s) <= 5:
        return True
    if s in ('true', 'false'):
        return True
    if s in ('data_shape', 'user_intent', 'interaction_type', 'device_type'):
        return True
    return False


def is_config_number(n):
    if isinstance(n, bool):
        return False
    if 1000 <= n <= 9999:
        return True
    if n in (0, 1, 2, 4, 8, 12, 14, 16, 18, 20, 22, 24, 28, 32, 48, 64, 100, 200):
        return True
    if isinstance(n, float) and 0.0 <= n <= 1.0:
        return True
    return False


def safe_name(s):
    if re.match(r'^#[0-9A-Fa-f]+$', s):
        return f'COLOR_{s.lstrip("#").upper()}'
    if s.endswith('.db'):
        return f'DB_PATH_{s.replace(".db", "").upper()}'
    if s.endswith('.sql'):
        return f'SQL_FILE_{s.replace(".sql", "").upper()}'
    if '/' in s:
        parts = s.strip('/').split('/')
        return 'PATH_' + '_'.join(p.upper() for p in parts if p)
    if s in ('color', 'font', 'format', 'spacing'):
        return f'STORE_{s.upper()}'
    if s in ('background', 'text', 'border', 'padding', 'margin', 'size', 'weight', 'border_width'):
        return f'PROP_{s.upper()}'
    if s in ('bold', 'normal', 'light'):
        return f'FONT_WEIGHT_{s.upper()}'
    if s in ('true', 'false'):
        return f'BOOL_{s.upper()}'
    if s in ('data_shape', 'user_intent', 'interaction_type', 'device_type'):
        return f'CONTEXT_{s.upper()}'
    if s.isdigit():
        return f'PORT_{s}'
    if re.match(r'^[a-z_]+$', s):
        return f'TABLE_{s.upper()}'
    return 'STR_' + re.sub(r'[^A-Z0-9]', '_', s.upper())


def safe_name_num(n):
    if isinstance(n, float):
        return f'NUM_{str(n).replace(".", "_")}'
    if 1000 <= n <= 9999:
        return f'PORT_{n}'
    if n <= 100:
        return f'SIZE_{n}'
    return f'NUM_{n}'


def generate_config(all_results):
    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append('"""Config — auto-generated by config_extractor.py"""')
    lines.append('')
    lines.append('from pathlib import Path')
    lines.append('')
    lines.append('BASE_DIR = Path(__file__).parent')
    lines.append('')

    constants = {}
    strings = set()
    numbers = set()
    defaults = {}
    get_fallbacks = {}
    classes = []
    methods = {}
    sources = []

    for r in all_results:
        sources.append(r['file'])
        constants.update(r['constants'])
        strings.update(r['strings'])
        numbers.update(r['numbers'])
        defaults.update(r['defaults'])
        get_fallbacks.update(r['get_fallbacks'])
        classes.extend(r['classes'])
        methods.update(r['methods'])

    lines.append(f'# Sources: {", ".join(sources)}')
    lines.append('')

    if constants:
        lines.append('# ── Module Constants ───────────────────────────────────────────')
        for name, val in sorted(constants.items()):
            lines.append(f'{name} = {repr(val)}')
        lines.append('')

    if defaults:
        lines.append('# ── Default Parameters ────────────────────────────────────────')
        for name, val in sorted(defaults.items()):
            lines.append(f'DEFAULT_{name.upper()} = {repr(val)}')
        lines.append('')

    if get_fallbacks:
        lines.append('# ── Fallback Defaults (from .get() calls) ─────────────────────')
        for key, val in sorted(get_fallbacks.items()):
            safe = key.upper().replace('.', '_').replace('-', '_')
            lines.append(f'FALLBACK_{safe} = {repr(val)}')
        lines.append('')

    if strings:
        lines.append('# ── Hardcoded Strings ─────────────────────────────────────────')
        seen = set()
        for s in sorted(strings):
            sn = safe_name(s)
            if sn not in seen:
                seen.add(sn)
                lines.append(f'{sn} = {repr(s)}')
        lines.append('')

    if numbers:
        lines.append('# ── Hardcoded Numbers ────────────────────────────────────────')
        for n in sorted(numbers, key=lambda x: (isinstance(x, float), x)):
            lines.append(f'{safe_name_num(n)} = {repr(n)}')
        lines.append('')

    if classes:
        lines.append('# ── Classes ───────────────────────────────────────────────────')
        for cls in classes:
            ms = methods.get(cls, [])
            lines.append(f'# {cls}: {", ".join(ms) if ms else "no methods"}')
        lines.append('')

    return '\n'.join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 config_extractor.py <source.py> [source2.py ...] > Config.py")
        sys.exit(1)

    all_results = []
    for filepath in sys.argv[1:]:
        try:
            all_results.append(extract_from_file(filepath))
        except Exception as e:
            print(f"# ERROR reading {filepath}: {e}", file=sys.stderr)

    print(generate_config(all_results))
