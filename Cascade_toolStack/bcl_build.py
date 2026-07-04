#!/usr/bin/env python3
"""
BCL Build CLI — Task-driven code generation engine

The CLI owns project state. The AI is a worker that completes one task at a time.

BCL markers in source files advertise what needs to be built:
    [@BCL]{Id=M001 Kind=Method Stage=Pending Name=extract_functions Class=CodeAnalyzer}

Commands:
  scan FILE        — Scan file for BCL markers, register tasks in DB
  plan             — Show all tasks with status
  next             — Get next pending task with context for AI
  apply ID --impl TEXT  — Insert implementation, mark task complete
  status           — Show progress overview
  validate FILE    — Run Pass 4: syntax check, unresolved markers, duplicates
  reset FILE       — Reset all tasks to Pending (re-scan)

The AI never edits the complete file. The CLI performs all assembly.
"""
import os
import re
import sys
import json
import sqlite3
import hashlib
import argparse
import textwrap
from datetime import datetime

# ── MARKER FORMAT ──

BCL_MARKER_RE = re.compile(
    r'#\s*\[@BCL\]\{([^}]+)\}',
    re.MULTILINE
)

BCL_PASS_RE = re.compile(
    r'(\s*)#\s*\[@BCL\]\{([^}]+)\}\n(\s*)def\s+(\w+)\s*\([^)]*\):\s*\n\s*pass'
)

def parse_bcl_attrs(raw: str) -> dict:
    """Parse BCL marker attributes: Id=M001 Kind=Method Stage=Pending Name=foo"""
    attrs = {}
    for pair in raw.split():
        if '=' in pair:
            k, v = pair.split('=', 1)
            attrs[k.strip()] = v.strip()
    return attrs

def format_bcl_attrs(attrs: dict) -> str:
    """Format dict back to BCL marker attrs."""
    return ' '.join(f'{k}={v}' for k, v in attrs.items())

def find_markers(filepath: str) -> list:
    """Find all BCL markers in a file. Returns list of dicts."""
    with open(filepath, "r") as f:
        content = f.read()

    markers = []
    for m in BCL_MARKER_RE.finditer(content):
        raw = m.group(1)
        attrs = parse_bcl_attrs(raw)
        attrs['_raw'] = raw
        attrs['_pos'] = m.start()
        attrs['_line'] = content[:m.start()].count('\n') + 1
        # Check if the method body is just "pass" (unfilled)
        # Pattern: optional def line, optional docstring, then pass
        after = content[m.end():]
        pass_match = re.match(
            r'\s*def\s+\w+\s*\([^)]*\):\s*\n'
            r'(?:\s*""".*?"""\s*\n)?'
            r'\s*pass',
            after, re.DOTALL
        )
        attrs['_filled'] = not bool(pass_match)
        markers.append(attrs)
    return markers

# ── DATABASE ──

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcl_build.db")

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            file TEXT NOT NULL,
            kind TEXT,
            name TEXT,
            class TEXT,
            stage TEXT DEFAULT 'Pending',
            deps TEXT,
            hash TEXT,
            created TEXT,
            updated TEXT,
            line INTEGER
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            action TEXT,
            timestamp TEXT,
            detail TEXT
        )
    """)
    db.commit()
    return db

def log_history(db, task_id, action, detail=""):
    db.execute(
        "INSERT INTO history (task_id, action, timestamp, detail) VALUES (?, ?, ?, ?)",
        (task_id, action, datetime.now().isoformat(), detail)
    )
    db.commit()

# ── SCAN ──

def cmd_scan(filepath: str):
    """Scan file for BCL markers, register tasks in DB."""
    db = get_db()
    markers = find_markers(filepath)
    fname = os.path.basename(filepath)

    registered = 0
    updated = 0

    for m in markers:
        tid = m.get('Id', '')
        if not tid:
            continue

        existing = db.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()

        if existing:
            # Reset to Pending if marker is unfilled (pass), keep Complete if filled
            stage = 'Pending' if not m['_filled'] else existing['stage']
            db.execute(
                "UPDATE tasks SET file=?, kind=?, name=?, class=?, line=?, stage=?, updated=? WHERE id=?",
                (fname, m.get('Kind', ''), m.get('Name', ''), m.get('Class', ''),
                 m.get('_line', 0), stage, datetime.now().isoformat(), tid)
            )
            updated += 1
        else:
            db.execute(
                "INSERT INTO tasks (id, file, kind, name, class, stage, deps, hash, created, updated, line) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, fname, m.get('Kind', ''), m.get('Name', ''), m.get('Class', ''),
                 m.get('Stage', 'Pending'), m.get('Deps', ''), None,
                 datetime.now().isoformat(), datetime.now().isoformat(), m.get('_line', 0))
            )
            registered += 1

        log_history(db, tid, 'scanned', f'file={fname} filled={m["_filled"]}')

    db.commit()
    db.close()

    print(f"Scanned: {filepath}")
    print(f"Markers found: {len(markers)}")
    print(f"New tasks: {registered} | Updated: {updated}")
    return 0

# ── PLAN ──

def cmd_plan():
    """Show all tasks with status."""
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    db.close()

    if not tasks:
        print("No tasks. Run: bcl_build.py scan <file>")
        return 1

    pending = [t for t in tasks if t['stage'] == 'Pending']
    complete = [t for t in tasks if t['stage'] == 'Complete']
    blocked = [t for t in tasks if t['stage'] == 'Blocked']

    print(f"Tasks: {len(tasks)} total | {len(complete)} complete | {len(pending)} pending | {len(blocked)} blocked")
    print("")

    if pending:
        print("PENDING (next to fill):")
        for t in pending:
            cls = f"{t['class']}." if t['class'] else ""
            print(f"  [{t['id']}] {cls}{t['name']} ({t['kind']}) — {t['file']}")
        print("")

    if complete:
        print("COMPLETE:")
        for t in complete:
            cls = f"{t['class']}." if t['class'] else ""
            print(f"  [{t['id']}] {cls}{t['name']} ✓")
        print("")

    if blocked:
        print("BLOCKED:")
        for t in blocked:
            cls = f"{t['class']}." if t['class'] else ""
            deps = t['deps'] or ''
            print(f"  [{t['id']}] {cls}{t['name']} — waiting on: {deps}")
        print("")

    return 0

# ── NEXT ──

def cmd_next():
    """Get next pending task with context for AI generation."""
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE stage = 'Pending' ORDER BY id LIMIT 1"
    ).fetchone()

    if not task:
        db.close()
        print("No pending tasks. All complete!")
        return 1

    # Read the file to get surrounding context
    filepath = None
    # Find the file
    for root, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
        if task['file'] in files:
            filepath = os.path.join(root, task['file'])
            break

    context_lines = []
    if filepath and os.path.exists(filepath):
        with open(filepath, "r") as f:
            lines = f.readlines()
        # Get ±10 lines around the marker
        line_num = task['line'] or 0
        start = max(0, line_num - 10)
        end = min(len(lines), line_num + 10)
        context_lines = lines[start:end]

    db.close()

    # Build the prompt for AI
    cls = f"{task['class']}." if task['class'] else ""
    print(f"TASK: {task['id']}")
    print(f"FILE: {task['file']}")
    print(f"CLASS: {task['class'] or '(none)'}")
    print(f"METHOD: {task['name']}")
    print(f"KIND: {task['kind']}")
    print(f"DEPS: {task['deps'] or '(none)'}")
    print(f"")
    print(f"CONTEXT (surrounding code):")
    print(f"```")
    for line in context_lines:
        print(line.rstrip())
    print(f"```")
    print(f"")
    print(f"Generate ONLY the implementation for {cls}{task['name']}().")
    print(f"Do not modify anything else.")
    print(f"")
    print(f"To apply: bcl_build.py apply {task['id']} --impl \"<implementation>\"")
    print(f"  or:    bcl_build.py apply {task['id']} --file snippet.py")

    return 0

# ── APPLY ──

def cmd_apply(task_id: str, impl_text: str):
    """Insert implementation at a task's marker, mark complete."""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if not task:
        db.close()
        print(f"Task {task_id} not found.")
        return 1

    if task['stage'] == 'Complete':
        db.close()
        print(f"Task {task_id} already complete. Use --force to override.")
        return 1

    # Find the file
    filepath = None
    for root, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
        if task['file'] in files:
            filepath = os.path.join(root, task['file'])
            break

    if not filepath or not os.path.exists(filepath):
        db.close()
        print(f"File {task['file']} not found.")
        return 1

    with open(filepath, "r") as f:
        content = f.read()

    # Find the marker + pass pattern (allows optional docstring between def and pass)
    marker_pattern = re.compile(
        r'(\s*)#\s*\[@BCL\]\{([^}]*Id=' + re.escape(task_id) + r'[^}]*)\}\n'
        r'(\s*)def\s+(\w+)\s*\(([^)]*)\):\s*\n'
        r'(?:\s*""".*?"""\s*\n)?'
        r'(\s*)pass',
        re.DOTALL
    )

    m = marker_pattern.search(content)
    if not m:
        db.close()
        print(f"Marker for {task_id} not found or already filled.")
        return 1

    indent = m.group(1)
    method_indent = m.group(3)
    method_name = m.group(4)
    params = m.group(5)

    # Indent the implementation — find min indent, remove it, then apply body indent
    body_indent = method_indent + '    '
    impl_lines = impl_text.rstrip().split('\n')
    # Find minimum indentation across non-empty lines
    non_empty = [line for line in impl_lines if line.strip()]
    if non_empty:
        min_indent = min(len(line) - len(line.lstrip()) for line in non_empty)
    else:
        min_indent = 0
    # Remove min indent from each line, then add body_indent
    adjusted = []
    for line in impl_lines:
        if line.strip():
            adjusted.append(body_indent + line[min_indent:])
        else:
            adjusted.append(line)
    indented_impl = '\n'.join(adjusted)

    # Update marker to Stage=Complete with hash
    old_attrs = parse_bcl_attrs(m.group(2))
    old_attrs['Stage'] = 'Complete'
    old_attrs['Hash'] = hashlib.sha256(impl_text.encode()).hexdigest()[:12]
    old_attrs['Updated'] = datetime.now().strftime('%Y%m%d%H%M%S')
    new_marker = f"{indent}#[@BCL]{{{format_bcl_attrs(old_attrs)}}}"

    # Build replacement: updated marker + method def + docstring + implementation
    docstring = f'{method_indent}    """{task["name"]} — auto-generated"""'
    replacement = f"{new_marker}\n{method_indent}def {method_name}({params}):\n{docstring}\n{indented_impl}"

    new_content = content[:m.start()] + replacement + content[m.end():]

    with open(filepath, "w") as f:
        f.write(new_content)

    # Update DB
    db.execute(
        "UPDATE tasks SET stage='Complete', hash=?, updated=? WHERE id=?",
        (old_attrs['Hash'], datetime.now().isoformat(), task_id)
    )
    log_history(db, task_id, 'applied', f'{len(impl_lines)} lines inserted')
    db.commit()
    db.close()

    print(f"Applied [{task_id}] — {method_name}() — {len(impl_lines)} lines")
    print(f"Marker updated: Stage=Complete Hash={old_attrs['Hash']}")

    # Show next task
    return cmd_next()

# ── STATUS ──

def cmd_status():
    """Show progress overview."""
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks").fetchall()
    db.close()

    if not tasks:
        print("No tasks. Run: bcl_build.py scan <file>")
        return 1

    total = len(tasks)
    complete = sum(1 for t in tasks if t['stage'] == 'Complete')
    pending = sum(1 for t in tasks if t['stage'] == 'Pending')
    blocked = sum(1 for t in tasks if t['stage'] == 'Blocked')

    pct = (complete / total * 100) if total else 0

    bar_len = 30
    filled = int(bar_len * complete / total) if total else 0
    bar = '█' * filled + '░' * (bar_len - filled)

    print(f"Progress: [{bar}] {pct:.0f}% ({complete}/{total})")
    print(f"Pending: {pending} | Blocked: {blocked}")
    return 0

# ── VALIDATE (Pass 4) ──

def cmd_validate(filepath: str):
    """Run Pass 4: syntax check, unresolved markers, duplicates."""
    issues = []

    # 1. Syntax check
    import py_compile
    try:
        py_compile.compile(filepath, doraise=True)
        print("✓ Syntax: OK")
    except py_compile.PyCompileError as e:
        print(f"✗ Syntax: FAIL")
        issues.append(f"Syntax error: {e}")

    # 2. Unresolved markers (pass placeholders)
    with open(filepath, "r") as f:
        content = f.read()

    pass_markers = re.findall(r'#\s*\[@BCL\]\{[^}]*Stage=Pending[^}]*\}', content)
    if pass_markers:
        print(f"✗ Unresolved: {len(pass_markers)} pending markers")
        for pm in pass_markers:
            issues.append(f"Unresolved marker: {pm}")
    else:
        print("✓ Markers: All resolved")

    # 3. Duplicate definitions
    func_defs = re.findall(r'^\s*def\s+(\w+)\s*\(', content, re.MULTILINE)
    seen = set()
    dupes = []
    for f in func_defs:
        if f in seen:
            dupes.append(f)
        seen.add(f)
    if dupes:
        print(f"✗ Duplicates: {dupes}")
        issues.append(f"Duplicate functions: {dupes}")
    else:
        print("✓ Duplicates: None")

    # 4. Check for leftover "pass" in non-dunder methods
    pass_lines = re.findall(r'(\s+)pass\s*$', content, re.MULTILINE)
    if len(pass_lines) > 0:
        print(f"⚠ Leftover pass: {len(pass_lines)} occurrences")
        issues.append(f"Leftover pass statements: {len(pass_lines)}")
    else:
        print("✓ Pass: None leftover")

    print("")
    if issues:
        print(f"VALIDATION: {len(issues)} issues found")
        for i in issues:
            print(f"  - {i}")
        return 1
    else:
        print("VALIDATION: All checks passed ✓")
        return 0

# ── RESET ──

def cmd_reset(filepath: str):
    """Reset all tasks to Pending, re-scan."""
    db = get_db()
    fname = os.path.basename(filepath)
    db.execute("UPDATE tasks SET stage='Pending', hash=NULL WHERE file=?", (fname,))
    log_history(db, 'ALL', 'reset', f'file={fname}')
    db.commit()
    db.close()
    print(f"Reset all tasks for {fname} to Pending")
    return cmd_scan(filepath)

# ── SQLITE-BACKED RESOURCE MANAGER ──
#
# Templates are stored as rows in the internal SQLite database (bcl_build.db).
# The binary contains its own DB — no external template files needed.
#
# Table: templates
#   name        TEXT PRIMARY KEY   (e.g. 'templates/c/unit')
#   category    TEXT               (e.g. 'templates', 'prompts')
#   language    TEXT               (e.g. 'c', 'python', 'generic')
#   content     TEXT               (raw template text with {{PLACEHOLDER}} vars)
#   created     TEXT
#   updated     TEXT
#
# This mirrors the C binary pattern: a .c file with an internal SQLite DB
# that stores templates as rows. The DB is the single source of truth for
# both templates (static) and task state (dynamic).

def init_templates(db):
    """Create templates table and seed default templates if empty."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            name TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            language TEXT NOT NULL,
            content TEXT NOT NULL,
            created TEXT,
            updated TEXT
        )
    """)
    # Only seed if table is empty
    count = db.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    if count > 0:
        return

    now = datetime.now().isoformat()
    defaults = _default_templates()
    for name, category, language, content in defaults:
        db.execute(
            "INSERT INTO templates (name, category, language, content, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
            (name, category, language, content, now, now)
        )
    db.commit()

def _default_templates() -> list:
    """Return list of (name, category, language, content) tuples for seeding."""
    return [
        ('templates/c/unit', 'templates', 'c', _C_UNIT_TEMPLATE),
        ('templates/python/module', 'templates', 'python', _PY_MODULE_TEMPLATE),
        ('prompts/pass1', 'prompts', 'generic', _PROMPT_PASS1),
        ('prompts/pass2', 'prompts', 'generic', _PROMPT_PASS2),
        ('prompts/pass3', 'prompts', 'generic', _PROMPT_PASS3),
    ]

class ResourceManager:
    """SQLite-backed template manager.
    Templates live as rows in the templates table inside bcl_build.db.
    API: get(name) -> str, list() -> list, register(name, content), size(name) -> int."""

    def __init__(self, db_path: str = None):
        self._db_path = db_path or DB_PATH
        self._cache = {}

    def _conn(self):
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        init_templates(db)
        return db

    def get(self, name: str) -> str:
        """Fetch a template by name from SQLite."""
        if name in self._cache:
            return self._cache[name]
        db = self._conn()
        row = db.execute("SELECT content FROM templates WHERE name = ?", (name,)).fetchone()
        db.close()
        if not row:
            raise KeyError(f"Template not found: {name}")
        self._cache[name] = row['content']
        return row['content']

    def register(self, name: str, content: str, category: str = 'custom', language: str = 'generic'):
        """Insert or update a template in the SQLite templates table."""
        db = self._conn()
        now = datetime.now().isoformat()
        existing = db.execute("SELECT name FROM templates WHERE name = ?", (name,)).fetchone()
        if existing:
            db.execute("UPDATE templates SET content=?, category=?, language=?, updated=? WHERE name=?",
                       (content, category, language, now, name))
        else:
            db.execute("INSERT INTO templates (name, category, language, content, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
                       (name, category, language, content, now, now))
        db.commit()
        db.close()
        self._cache[name] = content

    def list(self) -> list:
        """List all template names."""
        db = self._conn()
        rows = db.execute("SELECT name FROM templates ORDER BY name").fetchall()
        db.close()
        return [r['name'] for r in rows]

    def size(self, name: str) -> int:
        """Raw byte size of a template."""
        try:
            return len(self.get(name).encode('utf-8'))
        except KeyError:
            return 0

    def raw_size(self, name: str) -> int:
        """Alias for size()."""
        return self.size(name)

    def info(self, name: str) -> dict:
        """Get full metadata for a template."""
        db = self._conn()
        row = db.execute("SELECT * FROM templates WHERE name = ?", (name,)).fetchone()
        db.close()
        if not row:
            return None
        return dict(row)

    def search(self, pattern: str) -> list:
        """Search templates by name pattern."""
        db = self._conn()
        rows = db.execute("SELECT name, category, language FROM templates WHERE name LIKE ? ORDER BY name",
                          (f'%{pattern}%',)).fetchall()
        db.close()
        return [dict(r) for r in rows]

# ── DEFAULT TEMPLATE CONTENT ──

_C_UNIT_TEMPLATE = '''//@GHOST]{file_path="{{FILE_PATH}}" date="{{DATE}}" author="{{AUTHOR}}" session_id="{{SESSION_ID}}" context="BCL unit - {{SUMMARY}}"}
//@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
//@FILEID]{id="{{FILE_NAME}}" domain="{{DOMAIN}}" authority="{{CLASS_NAME}}"}
//@SUMMARY]{summary="{{SUMMARY}}"}
//@CLASS]{class="{{CLASS_NAME}}" domain="{{DOMAIN}}" authority="single"}
//@METHOD]{method="Init" type="command"}
//@METHOD]{method="Run" type="dispatch"}
//@METHOD]{method="Close" type="command"}
//@METHOD]{method="State" type="query"}

#include "bcl_toolstack.h"

static struct {
    int initialized;
} STATE;

int {{CLASS_NAME}}_Init(void) {
    memset(&STATE, 0, sizeof(STATE));
    STATE.initialized = 1;
    return 1;
}

int {{CLASS_NAME}}_Run(const char *cmd, const char *bcl_in, char *bcl_out, size_t out_sz) {
    if (!STATE.initialized) {{CLASS_NAME}}_Init();
    if (strcmp(cmd, "read_state") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@INITIALIZED]{1}");
    }
    if (strcmp(cmd, "set_config") == 0) {
        return BclResult_Ok(bcl_out, out_sz, "[@STATUS]{config_set}");
    }
    return BclResult_Err(bcl_out, out_sz, 50, "not implemented - stub unit");
}

int {{CLASS_NAME}}_Close(void) {
    STATE.initialized = 0;
    return 1;
}

const char * {{CLASS_NAME}}_State(void) {
    static char buf[128];
    snprintf(buf, sizeof(buf), "{{CLASS_NAME}}: initialized=%d", STATE.initialized);
    return buf;
}
'''

_PY_MODULE_TEMPLATE = '''"""
{{MODULE_NAME}} — {{DESCRIPTION}}
Generated by bcl_build.py scaffold — {{DATE}}
"""

import re
from collections import defaultdict


class {{CLASS_NAME}}:
    """{{DESCRIPTION}}"""

    def __init__(self):
        self.state = {}

    #[@BCL]{Id=M001 Kind=Method Stage=Pending Name=Init Class={{CLASS_NAME}}}
    def Init(self):
        """Initialize the module."""
        pass

    #[@BCL]{Id=M002 Kind=Method Stage=Pending Name=Run Class={{CLASS_NAME}}}
    def Run(self, command, params=None):
        """Dispatch a command."""
        pass

    #[@BCL]{Id=M003 Kind=Method Stage=Pending Name=Close Class={{CLASS_NAME}}}
    def Close(self):
        """Clean up resources."""
        pass

    #[@BCL]{Id=M004 Kind=Method Stage=Pending Name=State Class={{CLASS_NAME}}}
    def State(self):
        """Return state snapshot."""
        pass


# [@BCL]{Id=ENTRY Kind=EntryPoint Stage=Pending Name=main}
def main():
    pass

if __name__ == "__main__":
    main()
'''

_PROMPT_PASS1 = '''You are generating a SKELETON for a {{LANGUAGE}} module.

Module: {{MODULE_NAME}}
Description: {{DESCRIPTION}}
Classes:
{{CLASSES}}

Rules:
- Generate ONLY class declarations, method signatures, and pass placeholders
- Use BCL markers: #[@BCL]{Id=XXX Kind=Method Stage=Pending Name=YYY Class=ZZZ}
- NO implementation logic
- NO imports (the CLI will add them)
- NO CLI code

Output the skeleton code only. No explanations.
'''

_PROMPT_PASS2 = '''You are implementing ONE METHOD in a {{LANGUAGE}} module.

File: {{FILE_NAME}}
Class: {{CLASS_NAME}}
Method: {{METHOD_NAME}}
Signature: {{METHOD_SIGNATURE}}
Description: {{METHOD_DESC}}
Dependencies (already implemented):
{{DEPS}}

Rules:
- Generate ONLY the method body (no def line, no class line)
- The method is inside a class, so use self. for instance access
- Do NOT add CLI code, orchestration, or cross-method coordination
- Return the implementation text only, no markdown fences

Context (surrounding code):
{{CONTEXT}}
'''

_PROMPT_PASS3 = '''You are writing the ENTRY POINT for a {{LANGUAGE}} module.

File: {{FILE_NAME}}
Module: {{MODULE_NAME}}

The following methods are already implemented:
{{METHODS}}

Rules:
- Write a main() function that wires everything together
- Add if __name__ == "__main__": main()
- Keep it minimal — just orchestration

Output the entry point code only.
'''

# Initialize the global resource manager — backed by SQLite
RESOURCES = ResourceManager()

# ── TEMPLATE SUBSTITUTION ──

def fill_template(template: str, vars_dict: dict) -> str:
    """Replace {{KEY}} placeholders in a template with values."""
    result = template
    for key, val in vars_dict.items():
        result = result.replace('{{' + key.upper() + '}}', str(val))
    return result

# ── SCAFFOLD COMMAND ──

def cmd_scaffold(template_name: str, output_path: str, **kwargs):
    """Generate a file from an embedded template with variable substitution."""
    try:
        template = RESOURCES.get(template_name)
    except KeyError:
        print(f"Template not found: {template_name}")
        print(f"Available: {', '.join(RESOURCES.list())}")
        return 1

    # Build variable dict with defaults
    now = datetime.now()
    vars_dict = {
        'DATE': now.strftime('%Y-%m-%d'),
        'AUTHOR': 'cascade',
        'SESSION_ID': 'bcl-build',
        'FILE_NAME': os.path.basename(output_path),
        'FILE_PATH': output_path,
        'DOMAIN': 'cascade_tools',
        'SUMMARY': 'Auto-generated BCL unit',
    }
    vars_dict.update(kwargs)

    # Ensure required vars for C template
    if 'c/unit' in template_name:
        if 'CLASS_NAME' not in vars_dict:
            base = os.path.basename(output_path).replace('.c', '').replace('bcl_', '')
            vars_dict['CLASS_NAME'] = base.capitalize()

    # Ensure required vars for Python template
    if 'python' in template_name:
        if 'CLASS_NAME' not in vars_dict:
            base = os.path.basename(output_path).replace('.py', '')
            vars_dict['CLASS_NAME'] = ''.join(w.capitalize() for w in base.split('_'))
        if 'MODULE_NAME' not in vars_dict:
            vars_dict['MODULE_NAME'] = os.path.basename(output_path).replace('.py', '')
        if 'DESCRIPTION' not in vars_dict:
            vars_dict['DESCRIPTION'] = 'Auto-generated module'

    content = fill_template(template, vars_dict)

    with open(output_path, "w") as f:
        f.write(content)

    # Count BCL markers if any
    markers = BCL_MARKER_RE.findall(content)

    print(f"Scaffold: {output_path}")
    print(f"Template: {template_name}")
    print(f"Size: {len(content)} bytes, {len(content.splitlines())} lines")
    if markers:
        print(f"BCL markers: {len(markers)} (ready for scan + apply)")
    print(f"")
    if markers:
        print(f"Next steps:")
        print(f"  1. bcl_build.py scan {output_path}")
        print(f"  2. bcl_build.py plan")
        print(f"  3. bcl_build.py next")
    return 0

# ── RESOURCES COMMAND ──

def cmd_resources(search_term: str = None):
    """List all templates stored in the SQLite database."""
    if search_term:
        results = RESOURCES.search(search_term)
        if not results:
            print(f"No templates matching '{search_term}'")
            return 1
        print(f"Search results for '{search_term}' ({len(results)}):")
        print("")
        print(f"{'Name':<30} {'Category':<12} {'Language':<10}")
        print(f"{'-'*30} {'-'*12} {'-'*10}")
        for r in results:
            print(f"{r['name']:<30} {r['category']:<12} {r['language']:<10}")
        return 0

    names = RESOURCES.list()
    print(f"SQLite Templates ({len(names)}):")
    print("")
    print(f"{'Name':<30} {'Category':<12} {'Language':<10} {'Size':>8}")
    print(f"{'-'*30} {'-'*12} {'-'*10} {'-'*8}")
    for name in names:
        info = RESOURCES.info(name)
        size = RESOURCES.size(name)
        print(f"{name:<30} {info['category']:<12} {info['language']:<10} {size:>8}")
    print("")
    print(f"Storage: SQLite ({DB_PATH})")
    print(f"Table: templates (name, category, language, content, created, updated)")
    return 0

# ── PROMPT COMMAND ──

def cmd_prompt(pass_num: int, **kwargs):
    """Generate a prompt for the AI based on a pass template."""
    template_name = f"prompts/pass{pass_num}"
    try:
        template = RESOURCES.get(template_name)
    except KeyError:
        print(f"No prompt template for pass {pass_num}")
        return 1

    content = fill_template(template, kwargs)
    print(content)
    return 0

# ── SKELETON GENERATOR (Pass 1) ──

def cmd_skeleton(spec_path: str, output_path: str):
    """Generate a skeleton file with BCL markers from a JSON spec."""
    with open(spec_path, "r") as f:
        spec = json.load(f)

    lines = []
    lines.append(f'"""')
    lines.append(f'{spec.get("module_name", "module")} — {spec.get("description", "")}')
    lines.append(f'Generated by bcl_build.py skeleton — {datetime.now().isoformat()}')
    lines.append(f'"""')
    lines.append("")

    task_counter = 0

    for cls in spec.get("classes", []):
        lines.append(f'class {cls["name"]}:')
        lines.append(f'    """{cls.get("description", "")}"""')
        lines.append("")

        for method in cls.get("methods", []):
            task_counter += 1
            tid = method.get("id", f"M{task_counter:03d}")
            deps = method.get("deps", "")
            dep_str = f" Deps={deps}" if deps else ""

            lines.append(f'    #[@BCL]{{Id={tid} Kind=Method Stage=Pending Name={method["name"]} Class={cls["name"]}{dep_str}}}')
            lines.append(f'    def {method["name"]}{method.get("signature", "(self)")}:')
            lines.append(f'        """{method.get("desc", "")}"""')
            lines.append(f'        pass')
            lines.append("")

        lines.append("")

    lines.append("")
    lines.append("# [@BCL]{Id=ENTRY Kind=EntryPoint Stage=Pending Name=main}")
    lines.append("def main():")
    lines.append("    pass")
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    main()")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Skeleton: {output_path}")
    print(f"Tasks: {task_counter + 1} markers (M001..M{task_counter:03d} + ENTRY)")
    print(f"")
    print(f"Next steps:")
    print(f"  1. bcl_build.py scan {output_path}")
    print(f"  2. bcl_build.py plan")
    print(f"  3. bcl_build.py next")
    return 0

# ── CLI ──

def main():
    parser = argparse.ArgumentParser(
        description="BCL Build CLI — task-driven code generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("plan", help="Show all tasks with status")
    sub.add_parser("next", help="Get next pending task with AI context")
    sub.add_parser("status", help="Show progress overview")

    p_scan = sub.add_parser("scan", help="Scan file for BCL markers")
    p_scan.add_argument("file", help="Python file to scan")

    p_apply = sub.add_parser("apply", help="Insert implementation for a task")
    p_apply.add_argument("id", help="Task ID (e.g. M001)")
    p_apply.add_argument("--impl", help="Implementation text (inline)")
    p_apply.add_argument("--file", dest="impl_file", help="Implementation file")
    p_apply.add_argument("--force", action="store_true", help="Override complete status")

    p_val = sub.add_parser("validate", help="Pass 4: validate assembled file")
    p_val.add_argument("file", help="File to validate")

    p_reset = sub.add_parser("reset", help="Reset tasks to Pending")
    p_reset.add_argument("file", help="File to reset")

    p_skel = sub.add_parser("skeleton", help="Generate skeleton from JSON spec")
    p_skel.add_argument("--spec", required=True, help="JSON spec file")
    p_skel.add_argument("--output", required=True, help="Output skeleton file")

    p_scaffold = sub.add_parser("scaffold", help="Generate file from embedded template")
    p_scaffold.add_argument("--template", required=True, help="Template name (e.g. templates/c/unit)")
    p_scaffold.add_argument("--output", required=True, help="Output file path")
    p_scaffold.add_argument("--class-name", dest="class_name", help="Class name override")
    p_scaffold.add_argument("--module-name", dest="module_name", help="Module name override")
    p_scaffold.add_argument("--description", help="Description override")
    p_scaffold.add_argument("--domain", help="Domain override")
    p_scaffold.add_argument("--author", help="Author override")
    p_scaffold.add_argument("--summary", help="Summary override")

    p_res = sub.add_parser("resources", help="List templates stored in SQLite")
    p_res.add_argument("--search", dest="search_term", help="Search templates by name pattern")

    p_add_tpl = sub.add_parser("add-template", help="Add or update a template in SQLite")
    p_add_tpl.add_argument("--name", required=True, help="Template name (e.g. templates/c/analyzer)")
    p_add_tpl.add_argument("--file", required=True, help="File containing template content")
    p_add_tpl.add_argument("--category", default="custom", help="Template category")
    p_add_tpl.add_argument("--language", default="generic", help="Target language")

    p_dump_tpl = sub.add_parser("dump-template", help="Print a template's raw content")
    p_dump_tpl.add_argument("name", help="Template name")

    p_prompt = sub.add_parser("prompt", help="Generate AI prompt for a pass")
    p_prompt.add_argument("pass", type=int, help="Pass number (1, 2, or 3)")
    p_prompt.add_argument("--language", default="Python", help="Target language")
    p_prompt.add_argument("--module-name", dest="module_name", default="module", help="Module name")
    p_prompt.add_argument("--description", default="", help="Module description")
    p_prompt.add_argument("--classes", default="", help="Class list for pass 1")
    p_prompt.add_argument("--file-name", dest="file_name", default="", help="File name for pass 2/3")
    p_prompt.add_argument("--class-name", dest="class_name", default="", help="Class name for pass 2")
    p_prompt.add_argument("--method-name", dest="method_name", default="", help="Method name for pass 2")
    p_prompt.add_argument("--method-sig", dest="method_sig", default="", help="Method signature")
    p_prompt.add_argument("--method-desc", dest="method_desc", default="", help="Method description")
    p_prompt.add_argument("--deps", default="(none)", help="Dependencies")
    p_prompt.add_argument("--context", default="", help="Surrounding code context")
    p_prompt.add_argument("--methods", default="", help="Implemented methods list for pass 3")

    args = parser.parse_args()

    if args.command == "scan":
        return cmd_scan(args.file)

    elif args.command == "plan":
        return cmd_plan()

    elif args.command == "next":
        return cmd_next()

    elif args.command == "apply":
        if args.impl_file:
            with open(args.impl_file, "r") as f:
                impl = f.read()
        elif args.impl:
            impl = args.impl
        else:
            print("Provide --impl TEXT or --file FILE")
            return 1

        if args.force:
            db = get_db()
            db.execute("UPDATE tasks SET stage='Pending' WHERE id=?", (args.id,))
            db.commit()
            db.close()

        return cmd_apply(args.id, impl)

    elif args.command == "status":
        return cmd_status()

    elif args.command == "validate":
        return cmd_validate(args.file)

    elif args.command == "reset":
        return cmd_reset(args.file)

    elif args.command == "skeleton":
        return cmd_skeleton(args.spec, args.output)

    elif args.command == "scaffold":
        kwargs = {}
        if args.class_name: kwargs['CLASS_NAME'] = args.class_name
        if args.module_name: kwargs['MODULE_NAME'] = args.module_name
        if args.description: kwargs['DESCRIPTION'] = args.description
        if args.domain: kwargs['DOMAIN'] = args.domain
        if args.author: kwargs['AUTHOR'] = args.author
        if args.summary: kwargs['SUMMARY'] = args.summary
        return cmd_scaffold(args.template, args.output, **kwargs)

    elif args.command == "resources":
        return cmd_resources(args.search_term)

    elif args.command == "add-template":
        with open(args.file, "r") as f:
            content = f.read()
        RESOURCES.register(args.name, content, args.category, args.language)
        print(f"Template stored: {args.name} ({len(content)} bytes) in SQLite")
        return 0

    elif args.command == "dump-template":
        try:
            content = RESOURCES.get(args.name)
            print(content)
            return 0
        except KeyError:
            print(f"Template not found: {args.name}")
            return 1

    elif args.command == "prompt":
        kwargs = {
            'LANGUAGE': args.language,
            'MODULE_NAME': args.module_name,
            'DESCRIPTION': args.description,
            'CLASSES': args.classes,
            'FILE_NAME': args.file_name,
            'CLASS_NAME': args.class_name,
            'METHOD_NAME': args.method_name,
            'METHOD_SIGNATURE': args.method_sig,
            'METHOD_DESC': args.method_desc,
            'DEPS': args.deps,
            'CONTEXT': args.context,
            'METHODS': args.methods,
        }
        return cmd_prompt(getattr(args, 'pass'), **kwargs)

    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
#casacade read  please it not a eroor #
#im trying to hgte. ur attention. u need to read the next 5 messages to get up todye 