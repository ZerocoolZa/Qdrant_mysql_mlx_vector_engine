#!/usr/bin/env python3
"""
build_c_codebase_db.py

One SQLite database with all C code from MySQL CODEBASE,
parsed into classes + methods as separate rows.

Tables:
  c_classes   — one row per class (struct + ghost header + domain)
  c_methods   — one row per method (function body, linked to class by class_id)
  c_includes  — one row per #include per class
  c_constants — one row per #define per class
  c_files     — source file registry (path, hash, line_count, class_count)

The DB is the truth. Code is a projection of it.
"""

import sqlite3
import mysql.connector
import re
import os
import hashlib
import sys
from pathlib import Path

OUT_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/c_codebase.db"

# ═══════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS c_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT NOT NULL,
    full_path     TEXT,
    content_hash  TEXT NOT NULL,
    line_count    INTEGER DEFAULT 0,
    file_size     INTEGER DEFAULT 0,
    class_count   INTEGER DEFAULT 0,
    method_count  INTEGER DEFAULT 0,
    ingested_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS c_classes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id       INTEGER NOT NULL,
    class_name    TEXT NOT NULL,
    domain        TEXT,
    purpose       TEXT,
    ghost_header  TEXT,
    vbstyle_header TEXT,
    state_struct  TEXT,
    includes_text TEXT,
    constants_text TEXT,
    content_hash  TEXT,
    FOREIGN KEY (file_id) REFERENCES c_files(id)
);

CREATE TABLE IF NOT EXISTS c_methods (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id      INTEGER NOT NULL,
    file_id       INTEGER NOT NULL,
    method_name   TEXT NOT NULL,
    return_type   TEXT,
    params        TEXT,
    method_body   TEXT,
    full_signature TEXT,
    bracket_sig   TEXT,
    dispatch_key  TEXT,
    line_number   INTEGER,
    content_hash  TEXT,
    FOREIGN KEY (class_id) REFERENCES c_classes(id),
    FOREIGN KEY (file_id) REFERENCES c_files(id)
);

CREATE TABLE IF NOT EXISTS c_includes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id      INTEGER NOT NULL,
    include_path  TEXT NOT NULL,
    is_system     INTEGER DEFAULT 0,
    FOREIGN KEY (class_id) REFERENCES c_classes(id)
);

CREATE TABLE IF NOT EXISTS c_constants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id      INTEGER NOT NULL,
    const_name    TEXT NOT NULL,
    const_value   TEXT,
    FOREIGN KEY (class_id) REFERENCES c_classes(id)
);

CREATE INDEX IF NOT EXISTS idx_methods_class ON c_methods(class_id);
CREATE INDEX IF NOT EXISTS idx_methods_name ON c_methods(method_name);
CREATE INDEX IF NOT EXISTS idx_classes_name ON c_classes(class_name);
CREATE INDEX IF NOT EXISTS idx_files_hash ON c_files(content_hash);
"""

# ═══════════════════════════════════════════════════════════════
# C PARSER
# ═══════════════════════════════════════════════════════════════

class CParser:
    """Parse a C file into classes and methods."""

    def __init__(self, content, filename, full_path):
        self.content = content
        self.filename = filename
        self.full_path = full_path
        self.lines = content.split('\n')
        self.classes = []
        self.methods = []
        self.includes = []
        self.constants = []
        self.ghost_header = ""
        self.vbstyle_header = ""
        self.classinfo = {}

    def parse(self):
        self._extract_ghost_header()
        self._extract_classinfo()
        self._extract_includes()
        self._extract_constants()
        self._extract_structs()
        self._extract_functions()
        self._group_into_classes()
        return self

    def _extract_ghost_header(self):
        """Extract Ghost header from first comment block."""
        # Old format: /* Ghost{[ClassName]...} */
        m = re.search(r'/\*\s*Ghost\{([^}]+)\}', self.content)
        if m:
            self.ghost_header = "Ghost{" + m.group(1) + "}"
            return

        # New format: [@GHOST]{[@file<...>][@domain<...>]}
        m = re.search(r'\[@GHOST\]\{([^}]+)\}', self.content)
        if m:
            self.ghost_header = "[@GHOST]{" + m.group(1) + "}"
            return

        # Alt format: #   Ghost[ClassName:...]
        m = re.search(r'#\s*Ghost\[([^\]]+)\]', self.content)
        if m:
            self.ghost_header = "Ghost[" + m.group(1) + "]"
            return

    def _extract_classinfo(self):
        """Extract CLASSINFO block."""
        m = re.search(r'CLASSINFO\s*\n((?:\s*\*.*\n)*)', self.content)
        if m:
            block = m.group(1)
            for line in block.split('\n'):
                line = line.strip().lstrip('*').strip()
                if line.startswith('DOMAIN:'):
                    self.classinfo['domain'] = line[7:].strip()
                elif line.startswith('PURPOSE:'):
                    self.classinfo['purpose'] = line[8:].strip()
                elif line.startswith('STRUCTS:'):
                    self.classinfo['structs'] = line[8:].strip()
                elif line.startswith('FUNCTIONS:'):
                    self.classinfo['functions'] = line[10:].strip()
                elif line.startswith('INCLUDES:'):
                    self.classinfo['includes'] = line[9:].strip()

        # Also try [@GHOST] format for domain
        if 'domain' not in self.classinfo:
            m = re.search(r'\[@domain<([^>]+)>\]', self.content)
            if m:
                self.classinfo['domain'] = m.group(1)

        # Try [@VBSTYLE] header
        m = re.search(r'\[@VBSTYLE\]\{([^}]+)\}', self.content)
        if m:
            self.vbstyle_header = "[@VBSTYLE]{" + m.group(1) + "}"

    def _extract_includes(self):
        """Extract all #include lines."""
        for line in self.lines:
            line = line.strip()
            m = re.match(r'#include\s+[<"]([^>"]+)[>"]', line)
            if m:
                path = m.group(1)
                is_system = 1 if line.startswith('#include <') else 0
                self.includes.append((path, is_system))

    def _extract_constants(self):
        """Extract #define constants."""
        for line in self.lines:
            line = line.strip()
            m = re.match(r'#define\s+(\w+)\s+(.+)', line)
            if m:
                name = m.group(1)
                value = m.group(2).strip()
                # Skip include guards
                if name.endswith('_H') and value == '':
                    continue
                self.constants.append((name, value))

    def _extract_structs(self):
        """Extract typedef struct definitions."""
        self.structs = []
        # Match: typedef struct { ... } Name;
        # Also: struct Name { ... };
        pattern = r'(?:typedef\s+)?struct\s+(\w+)?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*\}\s*(\w+)?)\s*;'
        for m in re.finditer(pattern, self.content, re.DOTALL):
            name_before = m.group(1) or ""
            body = m.group(2)
            name_after = m.group(3) or ""
            name = name_after or name_before or "anonymous"
            self.structs.append({
                'name': name,
                'body': body.strip()
            })

    def _extract_functions(self):
        """Extract function definitions (not declarations)."""
        # Pattern: return_type function_name(params) {
        # Must have a body (not just a declaration ending in ;)
        # Handle multi-line signatures

        # First, find all function-like patterns with bodies
        # We look for: word(s) word(params) { at the start of a line
        pattern = r'^([a-zA-Z_][a-zA-Z0-9_\s\*]*?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*\{'

        for m in re.finditer(pattern, self.content, re.MULTILINE):
            return_type = m.group(1).strip()
            func_name = m.group(2).strip()
            params = m.group(3).strip()

            # Skip control flow keywords
            if func_name in ('if', 'else', 'while', 'for', 'switch', 'do', 'return'):
                continue
            # Skip if return_type is a keyword
            if return_type in ('if', 'else', 'while', 'for', 'switch'):
                continue

            # Find the line number
            pos = m.start()
            line_num = self.content[:pos].count('\n') + 1

            # Extract the body — find matching closing brace
            body_start = m.end()  # right after the opening {
            brace_count = 1
            i = body_start
            while i < len(self.content) and brace_count > 0:
                if self.content[i] == '{':
                    brace_count += 1
                elif self.content[i] == '}':
                    brace_count -= 1
                i += 1
            body = self.content[body_start:i-1].strip() if i <= len(self.content) else ""

            # Skip static inline functions that are very short (likely helpers)
            # Actually keep them — they're still methods

            # Build full signature
            full_sig = f"{return_type} {func_name}({params})"

            # Generate bracket signature
            bracket_sig = f"[@{func_name}]{{(@return<{return_type}>)(@params<{params}>)}}"

            # Dispatch key is the function name without class prefix
            dispatch_key = func_name

            self.methods.append({
                'name': func_name,
                'return_type': return_type,
                'params': params,
                'body': body,
                'full_signature': full_sig,
                'bracket_sig': bracket_sig,
                'dispatch_key': dispatch_key,
                'line_number': line_num,
            })

    def _group_into_classes(self):
        """Group functions into classes by name prefix."""

        # If we have CLASSINFO, that's the class name
        # Try to extract from Ghost header
        class_name = None

        # From CLASSINFO Ghost header
        m = re.search(r'Ghost\{\[(\w+)\]', self.ghost_header)
        if m:
            class_name = m.group(1)
        else:
            m = re.search(r'Ghost\[(\w+):', self.ghost_header)
            if m:
                class_name = m.group(1)

        # From [@GHOST] header
        if not class_name:
            m = re.search(r'\[@file<([^>]+)>\]', self.ghost_header)
            if m:
                class_name = m.group(1).replace('.c', '').replace('.h', '')

        # If we have functions, group by prefix
        if not self.methods:
            # No functions — still create a class from the file
            if not class_name:
                class_name = self.filename.replace('.c', '').replace('.h', '')
            self.classes.append({
                'name': class_name,
                'domain': self.classinfo.get('domain', ''),
                'purpose': self.classinfo.get('purpose', ''),
                'ghost_header': self.ghost_header,
                'vbstyle_header': self.vbstyle_header,
                'state_struct': '',
                'includes': self.includes[:],
                'constants': self.constants[:],
                'methods': [],
            })
            return

        # Group methods by prefix (prefix_name → class)
        # e.g., Core_ai_analyze → class "Core_ai", method "analyze"
        # e.g., MDB_init → class "MDB", method "init"
        groups = {}
        ungrouped = []

        for method in self.methods:
            name = method['name']
            # Try to split: Prefix_MethodName
            parts = name.split('_', 1)
            if len(parts) == 2 and len(parts[0]) >= 2:
                prefix = parts[0]
                # Check if prefix is a known pattern (starts with uppercase or is all caps)
                if prefix[0].isupper() or prefix.isupper():
                    if prefix not in groups:
                        groups[prefix] = []
                    method['class_prefix'] = prefix
                    method['method_name_clean'] = parts[1]
                    groups[prefix].append(method)
                else:
                    ungrouped.append(method)
            else:
                ungrouped.append(method)

        # Also try 2-level prefix: Core_ai_fix_run → Core_ai_fix
        if ungrouped:
            new_groups = {}
            still_ungrouped = []
            for method in ungrouped:
                name = method['name']
                parts = name.split('_', 2)
                if len(parts) >= 3:
                    prefix = parts[0] + '_' + parts[1]
                    if prefix[0].isupper():
                        if prefix not in new_groups:
                            new_groups[prefix] = []
                        method['class_prefix'] = prefix
                        method['method_name_clean'] = '_'.join(parts[2:])
                        new_groups[prefix].append(method)
                    else:
                        still_ungrouped.append(method)
                else:
                    still_ungrouped.append(method)
            groups.update(new_groups)
            ungrouped = still_ungrouped

        # If we have a class_name from header, put ungrouped methods there
        if class_name and ungrouped:
            if class_name not in groups:
                groups[class_name] = []
            for method in ungrouped:
                method['class_prefix'] = class_name
                method['method_name_clean'] = method['name']
                groups[class_name].append(method)
        elif ungrouped:
            # Put ungrouped in a class named after the file
            file_class = self.filename.replace('.c', '').replace('.h', '')
            if file_class not in groups:
                groups[file_class] = []
            for method in ungrouped:
                method['class_prefix'] = file_class
                method['method_name_clean'] = method['name']
                groups[file_class].append(method)

        # If we have a class_name from header, merge all groups into it
        # (single-class file)
        if class_name and len(groups) <= 3:
            all_methods = []
            for prefix, methods in groups.items():
                all_methods.extend(methods)
            groups = {class_name: all_methods}

        # Create class records
        for prefix, methods in groups.items():
            # Find state struct for this class
            state_struct = ""
            for s in self.structs:
                if prefix.lower() in s['name'].lower():
                    state_struct = s['name'] + " { " + s['body'][:200] + " }"
                    break

            self.classes.append({
                'name': prefix,
                'domain': self.classinfo.get('domain', ''),
                'purpose': self.classinfo.get('purpose', ''),
                'ghost_header': self.ghost_header,
                'vbstyle_header': self.vbstyle_header,
                'state_struct': state_struct,
                'includes': self.includes[:],
                'constants': self.constants[:],
                'methods': methods,
            })


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # Remove old db
    if os.path.exists(OUT_PATH):
        os.remove(OUT_PATH)

    # Create SQLite
    sconn = sqlite3.connect(OUT_PATH)
    scur = sconn.cursor()

    # Create schema
    scur.executescript(SCHEMA)
    sconn.commit()

    print("=" * 70)
    print("BUILDING C_CODEBASE.DB — Method-level AST storage")
    print("=" * 70)

    # Connect to MySQL
    mconn = mysql.connector.connect(host="localhost", user="root", password="")
    mcur = mconn.cursor()

    # Get ALL unique C-family files (.c, .h, .cpp) — de-duplicated by content_hash
    mcur.execute("""
        SELECT id, filename, full_path, content_hash, line_count, file_size
        FROM CODEBASE.c_files
        WHERE (filename LIKE '%.c' OR filename LIKE '%.h' OR filename LIKE '%.cpp')
        AND id IN (
            SELECT MIN(id) FROM CODEBASE.c_files
            WHERE (filename LIKE '%.c' OR filename LIKE '%.h' OR filename LIKE '%.cpp')
            GROUP BY content_hash
        )
        ORDER BY line_count DESC
    """)

    files = mcur.fetchall()
    total_files = len(files)
    print(f"\nUnique .c files to process: {total_files}")

    total_classes = 0
    total_methods = 0
    total_includes = 0
    total_constants = 0
    errors = 0
    processed = 0

    for row in files:
        file_id_mysql, filename, full_path, content_hash, line_count, file_size = row
        processed += 1

        if processed % 500 == 0:
            print(f"  Progress: {processed}/{total_files} files, {total_classes} classes, {total_methods} methods so far...")
            sconn.commit()

        # Fetch content
        try:
            mcur.execute("SELECT content FROM CODEBASE.c_files WHERE id = %s", (file_id_mysql,))
            content_row = mcur.fetchone()
            if not content_row:
                errors += 1
                continue
            content = content_row[0]
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
        except Exception as e:
            errors += 1
            continue

        # Parse
        try:
            parser = CParser(content, filename, full_path or "")
            parser.parse()
        except Exception as e:
            errors += 1
            continue

        # Insert file record
        scur.execute("""
            INSERT INTO c_files (filename, full_path, content_hash, line_count, file_size, class_count, method_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (filename, full_path or "", content_hash, line_count or 0, file_size or 0,
              len(parser.classes), len(parser.methods)))
        file_id = scur.lastrowid

        # Insert classes
        for cls in parser.classes:
            cls_hash = hashlib.sha256(
                (cls['name'] + cls.get('ghost_header', '') + str(line_count)).encode()
            ).hexdigest()

            scur.execute("""
                INSERT INTO c_classes (file_id, class_name, domain, purpose, ghost_header,
                                      vbstyle_header, state_struct, includes_text, constants_text, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                cls['name'],
                cls.get('domain', ''),
                cls.get('purpose', ''),
                cls.get('ghost_header', ''),
                cls.get('vbstyle_header', ''),
                cls.get('state_struct', ''),
                ', '.join([i[0] for i in cls.get('includes', [])]),
                ', '.join([c[0] + '=' + c[1] for c in cls.get('constants', [])]),
                cls_hash
            ))
            class_id = scur.lastrowid
            total_classes += 1

            # Insert includes
            for inc_path, is_system in cls.get('includes', []):
                scur.execute("INSERT INTO c_includes (class_id, include_path, is_system) VALUES (?, ?, ?)",
                             (class_id, inc_path, is_system))
                total_includes += 1

            # Insert constants
            for const_name, const_value in cls.get('constants', []):
                scur.execute("INSERT INTO c_constants (class_id, const_name, const_value) VALUES (?, ?, ?)",
                             (class_id, const_name, const_value))
                total_constants += 1

            # Insert methods
            for method in cls.get('methods', []):
                method_hash = hashlib.sha256(
                    (method['name'] + method.get('body', '')[:200]).encode()
                ).hexdigest()

                scur.execute("""
                    INSERT INTO c_methods (class_id, file_id, method_name, return_type, params,
                                          method_body, full_signature, bracket_sig, dispatch_key,
                                          line_number, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    class_id,
                    file_id,
                    method['name'],
                    method.get('return_type', ''),
                    method.get('params', ''),
                    method.get('body', ''),
                    method.get('full_signature', ''),
                    method.get('bracket_sig', ''),
                    method.get('dispatch_key', ''),
                    method.get('line_number', 0),
                    method_hash
                ))
                total_methods += 1

    sconn.commit()

    # ═══════════════════════════════════════════════════════════════
    # VERIFY
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("VERIFICATION")
    print(f"{'='*70}")

    for tname in ["c_files", "c_classes", "c_methods", "c_includes", "c_constants"]:
        scur.execute(f"SELECT COUNT(*) FROM {tname}")
        count = scur.fetchone()[0]
        print(f"  {tname:<15} {count:>7} rows")

    print(f"\n  Errors: {errors}")
    print(f"  Processed: {processed}/{total_files}")

    db_size = os.path.getsize(OUT_PATH)
    print(f"\n  Database: {OUT_PATH}")
    print(f"  Size: {db_size:,} bytes ({db_size // (1024*1024)} MB)")

    # Sample some classes
    print(f"\n{'='*70}")
    print("SAMPLE CLASSES (top 10 by method count)")
    print(f"{'='*70}")
    scur.execute("""
        SELECT c.class_name, c.domain, COUNT(m.id) as method_count, c.ghost_header
        FROM c_classes c
        LEFT JOIN c_methods m ON m.class_id = c.id
        GROUP BY c.id
        ORDER BY method_count DESC
        LIMIT 10
    """)
    for row in scur.fetchall():
        gh = (row[3] or '')[:40]
        print(f"  {row[0]:<30} domain={row[1] or '?':<15} methods={row[2]:>4}  ghost={gh}")

    print(f"\n{'='*70}")
    print("DONE — ONE SQLITE DB WITH ALL C CODE AS CLASSES + METHODS")
    print(f"{'='*70}")

    scur.close()
    sconn.close()
    mcur.close()
    mconn.close()

if __name__ == "__main__":
    main()
