#!/usr/bin/env python3

#[@GHOST]{[@file<Prj_VBScanner.py>][@domain<project_indexer>][@role<folder_scanner>][@auth<devin>][@date<2026-06-23>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<project_indexer>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}
#[@Class]{[@name<Prj_VBScanner>][@desc<Scans a folder for .py files, extracts classes/methods/functions/BCL headers/VBStyle compliance, generates FILE_INDEX entries, and appends them to Config.py>][@dispatch<Run>][@returns<Tuple3>]}

"""
Prj_VBScanner — Project VBStyle Scanner
========================================
Scans a folder for .py files and generates a FILE_INDEX matching the
gold standard format from chat_mover/Config.py.

For each .py file in the folder, extracts:
  - filename, purpose (from docstring), size, lines
  - classes (names + methods)
  - functions (top-level)
  - VBStyle compliance (Run dispatch, Tuple3, self.state, no print, etc.)
  - BCL headers (ghost, vbstyle, class, method)
  - created/modified timestamps

Then appends the FILE_INDEX to Config.py in the same folder.
If Config.py doesn't exist, creates it from the gold standard template.

Usage:
  python3 Prj_VBScanner.py /path/to/folder
  python3 Prj_VBScanner.py /path/to/folder --create-config
  python3 Prj_VBScanner.py /path/to/folder --append-only

VBStyle:
  Run(command, params) → Tuple3(ok, data, error)
  Commands: scan, generate_config, append_index, full_run
"""

import os
import re
import ast
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# ── VBStyle compliance regexes (from vbstyle_dom_scanner.py) ──
GHOST_RE = re.compile(r'#\[@GHOST\]', re.IGNORECASE)
VBSTYLE_RE = re.compile(r'#\[@VBSTYLE\]', re.IGNORECASE)
TUPLE3_RE = re.compile(r'Tuple3|tuple3|\(1,\s*\w+,\s*None\)|\(0,\s*None,', re.IGNORECASE)
STATE_DICT_RE = re.compile(r'self\.state\s*=')
RUN_DISPATCH_RE = re.compile(r'def\s+Run\s*\(')
DECORATOR_RE = re.compile(r'^\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)')
PRINT_RE = re.compile(r'\bprint\s*\(')
SELF_UNDERSCORE_RE = re.compile(r'self\._[a-z]')
HARDCODED_PATH_RE = re.compile(r'["\']/(?:Users|home|tmp|var|opt)/')
CLASS_RE = re.compile(r'^(\s*)class\s+(\w+)')
DEF_RE = re.compile(r'^(\s+)def\s+(\w+)\((.*)\)')
BCL_HEADER_START_RE = re.compile(r'^\s*#\[@(\w+)\]')


class Prj_VBScanner:
    """VBStyle Project Scanner — scans folders and generates FILE_INDEX for Config.py.

    self.state holds all runtime state:
      state['folder']: the folder being scanned
      state['files']: list of file index entries
      state['config_path']: path to Config.py
      state['errors']: list of errors encountered
    """

    def __init__(self):
        self.state = {
            'folder': None,
            'files': [],
            'config_path': None,
            'errors': [],
            'created_count': 0,
            'appended_count': 0,
        }

    def Run(self, command, params=None):
        """Dispatch entry point.

        Args:
            command: one of 'scan', 'generate_config', 'append_index', 'full_run'
            params: dict with 'folder' key (path to scan)

        Returns:
            Tuple3 (ok, data, error)
        """
        if params is None:
            params = {}

        handlers = {
            'scan': self.Scan,
            'generate_config': self.GenerateConfig,
            'append_index': self.AppendIndex,
            'full_run': self.FullRun,
            'status': self.Status,
        }

        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}. Valid: {list(handlers.keys())}", 1))

    def Scan(self, params):
        """Scan a folder for .py files and extract file index entries.

        params: {'folder': '/path/to/folder'}
        Returns: (1, file_index_list, None) or (0, None, error)
        """
        folder = params.get('folder')
        if not folder:
            return (0, None, ("MISSING_PARAM", "params must contain 'folder' key", 1))

        folder = os.path.abspath(folder)
        if not os.path.isdir(folder):
            return (0, None, ("NOT_FOUND", f"Folder not found: {folder}", 1))

        self.state['folder'] = folder
        self.state['files'] = []

        py_files = sorted([
            f for f in os.listdir(folder)
            if f.endswith('.py') and not f.startswith('.')
        ])

        for fname in py_files:
            fpath = os.path.join(folder, fname)
            entry = self._scan_file(fpath, fname)
            if entry:
                self.state['files'].append(entry)

        # Also index non-.py files (md, sql, json, etc.)
        other_files = sorted([
            f for f in os.listdir(folder)
            if not f.endswith('.py') and not f.startswith('.')
            and os.path.isfile(os.path.join(folder, f))
        ])
        for fname in other_files:
            fpath = os.path.join(folder, fname)
            entry = self._scan_non_py_file(fpath, fname)
            if entry:
                self.state['files'].append(entry)

        return (1, self.state['files'], None)

    def GenerateConfig(self, params):
        """Create a Config.py from the gold standard template if it doesn't exist.

        params: {'folder': '/path/to/folder', 'domain': 'optional_domain_name'}
        Returns: (1, config_path, None) or (0, None, error)
        """
        folder = params.get('folder')
        if not folder:
            return (0, None, ("MISSING_PARAM", "params must contain 'folder' key", 1))

        folder = os.path.abspath(folder)
        domain = params.get('domain', os.path.basename(folder))

        config_path = os.path.join(folder, 'Config.py')

        if os.path.exists(config_path):
            self.state['config_path'] = config_path
            return (1, config_path, None)  # Already exists, don't overwrite

        # Generate from template
        config_content = self._config_template(domain, folder)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            self.state['config_path'] = config_path
            self.state['created_count'] += 1
            return (1, config_path, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 2))

    def AppendIndex(self, params):
        """Append FILE_INDEX to Config.py.

        params: {'folder': '/path/to/folder'}
        Returns: (1, entries_appended, None) or (0, None, error)
        """
        folder = params.get('folder')
        if not folder:
            return (0, None, ("MISSING_PARAM", "params must contain 'folder' key", 1))

        folder = os.path.abspath(folder)
        config_path = os.path.join(folder, 'Config.py')

        # Scan first if not already done
        if not self.state['files'] or self.state['folder'] != folder:
            result = self.Scan({'folder': folder})
            if result[0] != 1:
                return result

        # Generate the FILE_INDEX block
        index_block = self._format_file_index(self.state['files'])

        # Read existing Config.py
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = f.read()
        except FileNotFoundError:
            # Create it first
            result = self.GenerateConfig({'folder': folder})
            if result[0] != 1:
                return result
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = f.read()
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 2))

        # Check if FILE_INDEX already exists
        if 'FILE_INDEX' in existing:
            # Replace the existing FILE_INDEX
            updated = self._replace_file_index(existing, index_block)
        else:
            # Append FILE_INDEX before the CONFIG CLASS section or at end
            updated = self._insert_file_index(existing, index_block)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(updated)
            self.state['config_path'] = config_path
            self.state['appended_count'] += 1
            return (1, len(self.state['files']), None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 2))

    def FullRun(self, params):
        """Full run: scan folder → generate Config.py if needed → append FILE_INDEX.

        params: {'folder': '/path/to/folder', 'domain': 'optional'}
        Returns: (1, summary, None) or (0, None, error)
        """
        folder = params.get('folder')
        if not folder:
            return (0, None, ("MISSING_PARAM", "params must contain 'folder' key", 1))

        # Step 1: Generate Config.py if needed
        result = self.GenerateConfig(params)
        if result[0] != 1:
            return result

        # Step 2: Scan folder
        result = self.Scan({'folder': folder})
        if result[0] != 1:
            return result

        # Step 3: Append FILE_INDEX
        result = self.AppendIndex({'folder': folder})
        if result[0] != 1:
            return result

        summary = {
            'folder': folder,
            'config_path': self.state['config_path'],
            'files_indexed': len(self.state['files']),
            'config_created': self.state['created_count'] > 0,
            'index_appended': True,
        }
        return (1, summary, None)

    def Status(self, params):
        """Return current scanner state."""
        return (1, dict(self.state), None)

    # ════════════════════════════════════════════════════════════════
    # INTERNAL: File scanning
    # ════════════════════════════════════════════════════════════════

    def _scan_file(self, fpath, fname):
        """Scan a single .py file and return a FILE_INDEX entry."""
        try:
            stat = os.stat(fpath)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            lines = content.splitlines()
        except Exception as e:
            self.state['errors'].append(f"{fname}: {e}")
            return None

        # Parse with AST
        classes = []
        functions = []
        purpose = ""

        try:
            tree = ast.parse(content)
            # Extract docstring as purpose
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                doc = tree.body[0].value.value
                if isinstance(doc, str):
                    purpose = doc.strip().split('\n')[0][:200]

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes.append({
                        'name': node.name,
                        'methods': methods,
                    })
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
                    # Only top-level functions (not inside classes)
                    if not hasattr(node, '_in_class'):
                        functions.append(node.name)
        except SyntaxError:
            # Fall back to regex parsing
            classes, functions, purpose = self._regex_parse(lines)

        # Check VBStyle compliance
        compliance = self._check_vbstyle(lines)

        # Check BCL headers
        bcl_headers = self._check_bcl_headers(lines)

        # Build entry matching gold standard format
        all_methods = []
        for cls in classes:
            for m in cls['methods']:
                all_methods.append(f"{cls['name']}.{m}")

        entry = {
            'file': fname,
            'purpose': purpose or '(no docstring)',
            'classes': [cls['name'] for cls in classes],
            'methods': all_methods if all_methods else [],
            'functions': functions,
            'vbstyle_compliant': compliance['is_compliant'],
            'vbstyle_rules_passed': compliance['passed'],
            'vbstyle_rules_total': compliance['total'],
            'vbstyle_failed': compliance['failed'],
            'has_bcl': bcl_headers['has_bcl'],
            'bcl_headers_found': bcl_headers['headers'],
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size': stat.st_size,
            'lines': len(lines),
        }
        return entry

    def _scan_non_py_file(self, fpath, fname):
        """Scan a non-.py file (md, sql, json, etc.) and return a basic entry."""
        try:
            stat = os.stat(fpath)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            lines = content.splitlines()
        except Exception as e:
            self.state['errors'].append(f"{fname}: {e}")
            return None

        # Extract purpose from first non-empty line
        purpose = ""
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                purpose = line.strip()[:200]
                break
            elif line.strip().startswith('#') and not line.strip().startswith('#!'):
                purpose = line.strip().lstrip('#').strip()[:200]
                break

        entry = {
            'file': fname,
            'purpose': purpose or '(non-Python file)',
            'classes': [],
            'methods': [],
            'functions': [],
            'vbstyle_compliant': False,
            'vbstyle_rules_passed': 0,
            'vbstyle_rules_total': 0,
            'vbstyle_failed': [],
            'has_bcl': False,
            'bcl_headers_found': [],
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size': stat.st_size,
            'lines': len(lines),
        }
        return entry

    def _regex_parse(self, lines):
        """Fallback regex parsing when AST fails."""
        classes = []
        functions = []
        purpose = ""

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if not purpose:
                    purpose = stripped.strip('"""').strip("'''")[:200]

            m = CLASS_RE.match(stripped)
            if m:
                classes.append({'name': m.group(2), 'methods': []})

            m = DEF_RE.match(stripped)
            if m and not m.group(2).startswith('_'):
                functions.append(m.group(2))

        return classes, functions, purpose

    def _check_vbstyle(self, lines):
        """Check VBStyle compliance rules."""
        full_text = "".join(lines)
        checks = {
            'ghost_header': bool(GHOST_RE.search(full_text)),
            'vbstyle_header': bool(VBSTYLE_RE.search(full_text)),
            'tuple3_return': bool(TUPLE3_RE.search(full_text)),
            'state_dict': bool(STATE_DICT_RE.search(full_text)),
            'run_dispatch': bool(RUN_DISPATCH_RE.search(full_text)),
            'no_decorators': not any(DECORATOR_RE.match(l) for l in lines),
            'no_print': not any(PRINT_RE.search(l) for l in lines if not l.strip().startswith("#")),
            'no_self_underscore': not any(SELF_UNDERSCORE_RE.search(l) for l in lines if not l.strip().startswith("#")),
            'no_hardcoded_paths': not any(HARDCODED_PATH_RE.search(l) for l in lines if not l.strip().startswith("#")),
        }

        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        failed = [k for k, v in checks.items() if not v]
        is_compliant = passed == total

        return {
            'is_compliant': is_compliant,
            'passed': passed,
            'total': total,
            'failed': failed,
        }

    def _check_bcl_headers(self, lines):
        """Check for BCL headers in the file."""
        headers = []
        for line in lines:
            m = BCL_HEADER_START_RE.match(line)
            if m:
                headers.append(m.group(1))

        return {
            'has_bcl': len(headers) > 0,
            'headers': headers,
        }

    # ════════════════════════════════════════════════════════════════
    # INTERNAL: Config.py generation
    # ════════════════════════════════════════════════════════════════

    def _config_template(self, domain, folder):
        """Generate a gold-standard Config.py from template."""
        folder_name = os.path.basename(folder)
        now = datetime.now().strftime('%Y-%m-%d')

        return f'''#!/usr/bin/env python3

#[@GHOST]{{[@file<Config.py>][@domain<{domain}>][@role<config>][@auth<devin>][@date<{now}>][@ver<1.0>]}}
#[@VBSTYLE]{{[@auth<system>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}}

"""
Gold Standard Config for {domain} domain.
Auto-generated by Prj_VBScanner.
All settings in SQLite config table — key/value/description.
Env vars override SQLite values at runtime.
"""

import os
import json
import sqlite3

# ─── BASE DIR ──────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.expanduser("~/.config/{domain}")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_DB_PATH = os.path.join(CONFIG_DIR, "{domain}_config.db")

# ─── VERSIONS ──────────────────────────────────────────────────────────────

DOMAIN_VERSION = "1.0.0"
CONFIG_VERSION = "1.0.0"

# ─── CONFIG SEED SQL (embedded — no external .sql file) ────────────────────

CONFIG_SEED_SQL = """
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    description TEXT
);

INSERT OR IGNORE INTO config VALUES
('domain',                  '{domain}',                           'Domain name'),
('v20_db_path',             '',                                   'Path to v20_hybrid_best.db (empty = default)');
"""

# ─── ENV VAR OVERRIDE MAP ──────────────────────────────────────────────────

ENV_OVERRIDES = {{
    "{domain.upper()}_V20_DB_PATH":  "v20_db_path",
}}


# ─── FILE INDEX ────────────────────────────────────────────────────────────
# Full index of all files in this folder. Auto-generated by Prj_VBScanner.
# Each entry is a BCL token: [@File:name]{{("field";"value")...}}
# DO NOT EDIT MANUALLY — run: python3 Prj_VBScanner.py {folder} --append-only
# BCL fields: file, purpose, classes, methods, functions, vbstyle,
#             vbstyle_passed, vbstyle_total, vbstyle_failed, bcl, bcl_headers,
#             created, modified, size, lines

FILE_INDEX = [
    # Prj_VBScanner will append BCL entries here
]


# ─── CONFIG CLASS ──────────────────────────────────────────────────────────

class {self._pascal_case(domain)}Config:
    """Single source of truth for {domain} configuration.

    Loads all values from SQLite config table on init.
    Env vars override SQLite values.
    """

    DOMAIN_VERSION = DOMAIN_VERSION
    FILE_INDEX = FILE_INDEX

    def __init__(self):
        self._db_path = CONFIG_DB_PATH
        self._values = {{}}
        self._load()

    def _load(self):
        """Load config from SQLite, apply env overrides."""
        conn = sqlite3.connect(self._db_path)
        cur = conn.cursor()
        cur.executescript(CONFIG_SEED_SQL)
        conn.commit()
        cur.execute("SELECT key, value FROM config")
        for key, value in cur.fetchall():
            self._values[key] = value
        cur.close()
        conn.close()
        for env_name, config_key in ENV_OVERRIDES.items():
            env_val = os.environ.get(env_name)
            if env_val is not None:
                self._values[config_key] = env_val

    def _get(self, key, default=None):
        return self._values.get(key, default)

    def GetFileIndex(self):
        """Return full file index for this folder — list of BCL token strings."""
        return self.FILE_INDEX

    def GetFileList(self):
        """Return just the list of filenames from BCL entries."""
        import re
        names = []
        for entry in self.FILE_INDEX:
            m = re.search(r'\("file";"([^"]+)"\)', entry)
            if m:
                names.append(m.group(1))
        return names

    def GetFileEntry(self, filename):
        """Return the BCL entry for a specific file."""
        for entry in self.FILE_INDEX:
            if '("file";"' + filename + '")' in entry:
                return entry
        return None


# ─── SINGLETON ─────────────────────────────────────────────────────────────

cfg = {self._pascal_case(domain)}Config()
'''

    def _pascal_case(self, s):
        """Convert snake_case or lowercase to PascalCase."""
        return ''.join(word.capitalize() for word in s.split('_'))

    def _format_file_index(self, files):
        """Format the file index as BCL tokens.

        Each file entry is a BCL token:
        # [@File:name.py]{("purpose";"...")("classes";"...")("methods";"...")...}

        This is consistent with the system's BCL-first philosophy.
        The FILE_INDEX is a Python list of BCL token strings.
        """
        lines = []
        lines.append("FILE_INDEX = [")
        for entry in files:
            # Build BCL token for this file
            bcl = self._entry_to_bcl(entry)
            lines.append(f"    {json.dumps(bcl)},")
        lines.append("]")
        return '\n'.join(lines)

    def _entry_to_bcl(self, entry):
        """Convert a file entry dict to a BCL token string.

        Format:
        [@File:name.py]{("purpose";"...")("classes";"A,B,C")("methods";"A.run,A.scan")...}
        """
        fname = entry['file']
        # BCL-safe name (remove special chars for token name)
        safe_name = fname.replace('.', '_').replace('-', '_')
        # Join lists with commas for compact BCL
        classes_str = ','.join(entry['classes'])
        methods_str = ','.join(entry['methods'])
        functions_str = ','.join(entry['functions'])
        failed_str = ','.join(entry['vbstyle_failed'])
        bcl_headers_str = ','.join(entry['bcl_headers_found'])

        bcl = (f"# [@File:{safe_name}]{{"
               f"(\"file\";\"{fname}\")"
               f"(\"purpose\";\"{entry['purpose']}\")"
               f"(\"classes\";\"{classes_str}\")"
               f"(\"methods\";\"{methods_str}\")"
               f"(\"functions\";\"{functions_str}\")"
               f"(\"vbstyle\";\"{entry['vbstyle_compliant']}\")"
               f"(\"vbstyle_passed\";\"{entry['vbstyle_rules_passed']}\")"
               f"(\"vbstyle_total\";\"{entry['vbstyle_rules_total']}\")"
               f"(\"vbstyle_failed\";\"{failed_str}\")"
               f"(\"bcl\";\"{entry['has_bcl']}\")"
               f"(\"bcl_headers\";\"{bcl_headers_str}\")"
               f"(\"created\";\"{entry['created']}\")"
               f"(\"modified\";\"{entry['modified']}\")"
               f"(\"size\";\"{entry['size']}\")"
               f"(\"lines\";\"{entry['lines']}\")"
               f"}}")
        return bcl

    def _replace_file_index(self, existing, new_index_block):
        """Replace existing FILE_INDEX in Config.py with new one."""
        # Find FILE_INDEX = [ ... ] — match from FILE_INDEX to the next line that starts with ]
        # at the same indentation level (closing bracket of the list)
        lines = existing.split('\n')
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^FILE_INDEX\s*=\s*\[', line):
                start_idx = i
                continue
            if start_idx is not None and i > start_idx and re.match(r'^\]', line):
                end_idx = i
                break

        if start_idx is not None and end_idx is not None:
            # Replace lines start_idx through end_idx (inclusive)
            new_lines = lines[:start_idx] + new_index_block.split('\n') + lines[end_idx + 1:]
            return '\n'.join(new_lines)
        elif start_idx is not None:
            # Fallback: replace from start to end of file
            new_lines = lines[:start_idx] + new_index_block.split('\n')
            return '\n'.join(new_lines)
        else:
            # No existing FILE_INDEX — insert it
            return self._insert_file_index(existing, new_index_block)

    def _insert_file_index(self, existing, index_block):
        """Insert FILE_INDEX into Config.py (before CONFIG CLASS section)."""
        # Find the CONFIG CLASS section
        marker = "# ─── CONFIG CLASS"
        if marker in existing:
            parts = existing.split(marker, 1)
            return parts[0] + index_block + "\n\n" + marker + parts[1]
        else:
            # Append at end
            return existing + "\n\n" + index_block + "\n"


# ════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 Prj_VBScanner.py <folder> [--create-config] [--append-only]")
        print("       python3 Prj_VBScanner.py <folder>  # full run: create config + scan + append index")
        sys.exit(1)

    folder = sys.argv[1]
    create_only = '--create-config' in sys.argv
    append_only = '--append-only' in sys.argv

    scanner = Prj_VBScanner()

    if create_only:
        result = scanner.Run('generate_config', {'folder': folder})
    elif append_only:
        result = scanner.Run('append_index', {'folder': folder})
    else:
        result = scanner.Run('full_run', {'folder': folder})

    ok, data, error = result

    if ok:
        if isinstance(data, dict) and 'files_indexed' in data:
            print(f"✅ Full run complete")
            print(f"   Folder: {data['folder']}")
            print(f"   Config: {data['config_path']}")
            print(f"   Files indexed: {data['files_indexed']}")
            print(f"   Config created: {data['config_created']}")
            print(f"   Index appended: {data['index_appended']}")
        elif isinstance(data, list):
            print(f"✅ Scanned {len(data)} files")
            for entry in data:
                vb = "VBStyle" if entry['vbstyle_compliant'] else f"NOT VBStyle ({entry['vbstyle_rules_passed']}/{entry['vbstyle_rules_total']})"
                bcl = "BCL" if entry['has_bcl'] else "no BCL"
                print(f"   {entry['file']:40} {entry['lines']:>6} lines  {vb:30} {bcl}")
        elif isinstance(data, str):
            print(f"✅ Config.py: {data}")
        else:
            print(f"✅ Done: {data}")
    else:
        err_code, err_msg, err_sev = error
        print(f"❌ Error [{err_code}]: {err_msg} (severity {err_sev})")
        sys.exit(1)

    # Show errors if any
    if scanner.state['errors']:
        print(f"\n⚠️  {len(scanner.state['errors'])} errors:")
        for e in scanner.state['errors']:
            print(f"   {e}")


if __name__ == "__main__":
    main()
