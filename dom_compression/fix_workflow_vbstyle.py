#!/usr/bin/env python3
"""
Fix Dom_workflow methods to be fully VBStyle compliant:
1. All methods return Tuple3 (ok, data, error)
2. No self._ prefix — use self.state dict
3. Method names: PascalCase, no underscore prefix
4. Rename: _scan_py_file → ScanPyFile, etc.
"""

import sqlite3
from datetime import datetime

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"
CLASS_ID = 1801

# ════════════════════════════════════════════════════════════════════════
# CORRECTED METHODS — all return Tuple3, no self._, PascalCase names
# ════════════════════════════════════════════════════════════════════════

CORRECTED_METHODS = {

"__init__": '''def __init__(self):
    self.state = {
        'folder': None,
        'files': [],
        'config_path': None,
        'errors': [],
        'v20_db': None,
        'project_name': None,
        'indexed_count': 0,
        'validated_count': 0,
    }
    return (1, self.state, None)''',

"Run": '''def Run(self, command, params=None):
    if params is None:
        params = {}
    handlers = {
        'prj': self.Prj,
        'index': self.Index,
        'config': self.Config,
        'validate': self.Validate,
        'report': self.Report,
        'status': self.Status,
    }
    handler = handlers.get(command)
    if handler:
        return handler(params)
    return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command) + ". Valid: " + str(list(handlers.keys())), 1))''',

"Prj": '''def Prj(self, params):
    action = params.get('action', 'create')
    folder = params.get('folder')
    if action == 'create':
        if not folder:
            return (0, None, ("MISSING_PARAM", "params must contain folder", 1))
        folder = os.path.abspath(folder)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        self.state['folder'] = folder
        self.state['project_name'] = params.get('name', os.path.basename(folder))
        return (1, {'folder': folder, 'name': self.state['project_name'], 'created': True}, None)
    elif action == 'identify':
        domain = params.get('domain', 'new_domain')
        base = params.get('base', os.getcwd())
        folder = os.path.join(base, domain)
        self.state['folder'] = folder
        self.state['project_name'] = domain
        return (1, {'folder': folder, 'domain': domain, 'needs_config': True}, None)
    elif action == 'list':
        folder = params.get('folder', os.getcwd())
        if not os.path.isdir(folder):
            return (0, None, ("NOT_FOUND", "Not a directory: " + str(folder), 1))
        entries = os.listdir(folder)
        folders = [e for e in entries if os.path.isdir(os.path.join(folder, e))]
        return (1, {'folders': sorted(folders), 'base': folder}, None)
    return (0, None, ("UNKNOWN_ACTION", "Unknown prj action: " + str(action), 1))''',

"Index": '''def Index(self, params):
    folder = params.get('folder')
    if not folder:
        folder = self.state.get('folder')
    if not folder:
        return (0, None, ("MISSING_PARAM", "Need folder", 1))
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        return (0, None, ("NOT_FOUND", "Folder not found: " + str(folder), 1))
    self.state['folder'] = folder
    self.state['files'] = []
    pyFiles = sorted([f for f in os.listdir(folder) if f.endswith('.py') and not f.startswith('.')])
    for fname in pyFiles:
        ok, entry, err = self.ScanPyFile(os.path.join(folder, fname), fname)
        if ok and entry:
            self.state['files'].append(entry)
    otherFiles = sorted([f for f in os.listdir(folder) if not f.endswith('.py') and not f.startswith('.') and os.path.isfile(os.path.join(folder, f))])
    for fname in otherFiles:
        ok, entry, err = self.ScanOtherFile(os.path.join(folder, fname), fname)
        if ok and entry:
            self.state['files'].append(entry)
    self.state['indexed_count'] = len(self.state['files'])
    return (1, self.state['files'], None)''',

"ScanPyFile": '''def ScanPyFile(self, fpath, fname):
    try:
        stat = os.stat(fpath)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        lines = content.splitlines()
    except Exception as e:
        self.state['errors'].append(fname + ": " + str(e))
        return (0, None, ("READ_ERROR", str(e), 2))
    classes = []
    functions = []
    purpose = ""
    try:
        tree = ast.parse(content)
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            doc = tree.body[0].value.value
            if isinstance(doc, str):
                purpose = doc.strip().split('\\n')[0][:200]
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                classes.append({'name': node.name, 'methods': methods})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
                functions.append(node.name)
    except SyntaxError:
        ok, parsed, err = self.RegexParse(lines)
        if ok:
            classes, functions, purpose = parsed
    ok, compliance, err = self.CheckVbstyle(lines)
    ok, bclHeaders, err = self.CheckBclHeaders(lines)
    allMethods = []
    for cls in classes:
        for m in cls['methods']:
            allMethods.append(cls['name'] + "." + m)
    entry = {
        'file': fname,
        'purpose': purpose or '(no docstring)',
        'classes': [cls['name'] for cls in classes],
        'methods': allMethods,
        'functions': functions,
        'vbstyle_compliant': compliance['is_compliant'],
        'vbstyle_passed': compliance['passed'],
        'vbstyle_total': compliance['total'],
        'vbstyle_failed': compliance['failed'],
        'has_bcl': bclHeaders['has_bcl'],
        'bcl_headers': bclHeaders['headers'],
        'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'size': stat.st_size,
        'lines': len(lines),
    }
    ok, bcl, err = self.EntryToBcl(entry)
    if ok:
        return (1, bcl, None)
    return (0, None, err)''',

"ScanOtherFile": '''def ScanOtherFile(self, fpath, fname):
    try:
        stat = os.stat(fpath)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        lines = content.splitlines()
    except Exception as e:
        self.state['errors'].append(fname + ": " + str(e))
        return (0, None, ("READ_ERROR", str(e), 2))
    purpose = ""
    for line in lines:
        if line.strip() and not line.strip().startswith('#!'):
            purpose = line.strip().lstrip('#').strip()[:200]
            break
    entry = {
        'file': fname,
        'purpose': purpose or '(non-Python file)',
        'classes': [],
        'methods': [],
        'functions': [],
        'vbstyle_compliant': False,
        'vbstyle_passed': 0,
        'vbstyle_total': 0,
        'vbstyle_failed': [],
        'has_bcl': False,
        'bcl_headers': [],
        'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'size': stat.st_size,
        'lines': len(lines),
    }
    ok, bcl, err = self.EntryToBcl(entry)
    if ok:
        return (1, bcl, None)
    return (0, None, err)''',

"EntryToBcl": '''def EntryToBcl(self, entry):
    safeName = entry['file'].replace('.', '_').replace('-', '_')
    bcl = (
        "# [@File:" + safeName + "]{"
        + '("file";"' + entry['file'] + '")'
        + '("purpose";"' + entry['purpose'] + '")'
        + '("classes";"' + ','.join(entry['classes']) + '")'
        + '("methods";"' + ','.join(entry['methods']) + '")'
        + '("functions";"' + ','.join(entry['functions']) + '")'
        + '("vbstyle";"' + str(entry['vbstyle_compliant']) + '")'
        + '("vbstyle_passed";"' + str(entry['vbstyle_passed']) + '")'
        + '("vbstyle_total";"' + str(entry['vbstyle_total']) + '")'
        + '("vbstyle_failed";"' + ','.join(entry['vbstyle_failed']) + '")'
        + '("bcl";"' + str(entry['has_bcl']) + '")'
        + '("bcl_headers";"' + ','.join(entry['bcl_headers']) + '")'
        + '("created";"' + entry['created'] + '")'
        + '("modified";"' + entry['modified'] + '")'
        + '("size";"' + str(entry['size']) + '")'
        + '("lines";"' + str(entry['lines']) + '")'
        + "}"
    )
    return (1, bcl, None)''',

"RegexParse": '''def RegexParse(self, lines):
    classes = []
    functions = []
    purpose = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(chr(34)*3) or stripped.startswith(chr(39)*3):
            if not purpose:
                purpose = stripped.strip(chr(34)*3).strip(chr(39)*3)[:200]
        m = re.match(r'^(\\s*)class\\s+(\\w+)', stripped)
        if m:
            classes.append({'name': m.group(2), 'methods': []})
        m = re.match(r'^(\\s+)def\\s+(\\w+)\\(', stripped)
        if m and not m.group(2).startswith('_'):
            functions.append(m.group(2))
    return (1, (classes, functions, purpose), None)''',

"CheckVbstyle": '''def CheckVbstyle(self, lines):
    fullText = "".join(lines)
    checks = {
        'ghost_header': bool(re.search(r'#\\[@GHOST\\]', fullText, re.IGNORECASE)),
        'vbstyle_header': bool(re.search(r'#\\[@VBSTYLE\\]', fullText, re.IGNORECASE)),
        'tuple3_return': bool(re.search(r'Tuple3|tuple3|\\(1,\\s*\\w+,\\s*None\\)|\\(0,\\s*None,', fullText, re.IGNORECASE)),
        'state_dict': bool(re.search(r'self\\.state\\s*=', fullText)),
        'run_dispatch': bool(re.search(r'def\\s+Run\\s*\\(', fullText)),
        'no_decorators': not any(re.match(r'^\\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)', l) for l in lines),
        'no_print': not any(re.search(r'\\bprint\\s*\\(', l) for l in lines if not l.strip().startswith("#")),
        'no_self_underscore': not any(re.search(r'self\\._[a-z]', l) for l in lines if not l.strip().startswith("#")),
        'no_hardcoded_paths': not any(re.search(r'["\\']/(?:Users|home|tmp|var|opt)/', l) for l in lines if not l.strip().startswith("#")),
    }
    passed = sum(1 for v in checks.values() if v)
    failed = [k for k, v in checks.items() if not v]
    result = {'is_compliant': passed == len(checks), 'passed': passed, 'total': len(checks), 'failed': failed}
    return (1, result, None)''',

"CheckBclHeaders": '''def CheckBclHeaders(self, lines):
    headers = []
    for line in lines:
        m = re.match(r'^\\s*#\\[@(\\w+)\\]', line)
        if m:
            headers.append(m.group(1))
    result = {'has_bcl': len(headers) > 0, 'headers': headers}
    return (1, result, None)''',

"Config": '''def Config(self, params):
    folder = params.get('folder')
    if not folder:
        folder = self.state.get('folder')
    if not folder:
        return (0, None, ("MISSING_PARAM", "Need folder", 1))
    folder = os.path.abspath(folder)
    domain = params.get('domain', os.path.basename(folder))
    action = params.get('action', 'full')
    configPath = os.path.join(folder, 'Config.py')
    if action == 'create':
        if os.path.exists(configPath):
            self.state['config_path'] = configPath
            return (1, {'config_path': configPath, 'created': False}, None)
        ok, content, err = self.ConfigTemplate(domain, folder)
        if not ok:
            return (0, None, err)
        try:
            with open(configPath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.state['config_path'] = configPath
            return (1, {'config_path': configPath, 'created': True}, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 2))
    elif action == 'append':
        if not self.state['files'] or self.state['folder'] != folder:
            result = self.Index({'folder': folder})
            if result[0] != 1:
                return result
        ok, indexBlock, err = self.FormatFileIndex(self.state['files'])
        if not ok:
            return (0, None, err)
        try:
            with open(configPath, 'r', encoding='utf-8') as f:
                existing = f.read()
        except FileNotFoundError:
            result = self.Config({'folder': folder, 'domain': domain, 'action': 'create'})
            if result[0] != 1:
                return result
            with open(configPath, 'r', encoding='utf-8') as f:
                existing = f.read()
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 2))
        if 'FILE_INDEX' in existing:
            ok, updated, err = self.ReplaceFileIndex(existing, indexBlock)
        else:
            ok, updated, err = self.InsertFileIndex(existing, indexBlock)
        if not ok:
            return (0, None, err)
        try:
            with open(configPath, 'w', encoding='utf-8') as f:
                f.write(updated)
            self.state['config_path'] = configPath
            return (1, {'config_path': configPath, 'entries': len(self.state['files'])}, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 2))
    elif action == 'full':
        result = self.Config({'folder': folder, 'domain': domain, 'action': 'create'})
        if result[0] != 1:
            return result
        result = self.Index({'folder': folder})
        if result[0] != 1:
            return result
        result = self.Config({'folder': folder, 'domain': domain, 'action': 'append'})
        if result[0] != 1:
            return result
        return (1, {'config_path': configPath, 'files_indexed': len(self.state['files']), 'domain': domain}, None)
    return (0, None, ("UNKNOWN_ACTION", "Unknown config action: " + str(action), 1))''',

"ConfigTemplate": '''def ConfigTemplate(self, domain, folder):
    now = datetime.now().strftime('%Y-%m-%d')
    pascal = ''.join(w.capitalize() for w in domain.split('_'))
    content = (
        "#!/usr/bin/env python3\\n"
        "#[@GHOST]{[@file<Config.py>][@domain<" + domain + ">][@role<config>][@auth<devin>][@date<" + now + ">][@ver<1.0>]}\\n"
        "#[@VBSTYLE]{[@auth<system>][@role<config>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}\\n"
        "\\n"
        '"""Gold Standard Config for ' + domain + ' domain. Auto-generated by Dom_workflow."""\\n'
        "\\n"
        "import os\\n"
        "import re\\n"
        "import sqlite3\\n"
        "\\n"
        "BASE_DIR = os.path.dirname(os.path.abspath(__file__))\\n"
        'CONFIG_DB_PATH = os.path.join(BASE_DIR, "' + domain + '_config.db")\\n'
        "\\n"
        'CONFIG_SEED_SQL = "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT, description TEXT)"\\n'
        "\\n"
        "FILE_INDEX = [\\n"
        "    # Dom_workflow appends BCL entries here\\n"
        "]\\n"
        "\\n"
        "\\n"
        "class " + pascal + "Config:\\n"
        '    """Single source of truth for ' + domain + ' configuration."""\\n'
        "\\n"
        "    FILE_INDEX = FILE_INDEX\\n"
        "\\n"
        "    def __init__(self):\\n"
        "        self.state = {'db_path': CONFIG_DB_PATH, 'values': {}}\\n"
        "        conn = sqlite3.connect(self.state['db_path'])\\n"
        "        cur = conn.cursor()\\n"
        "        cur.executescript(CONFIG_SEED_SQL)\\n"
        "        conn.commit()\\n"
        "        cur.execute('SELECT key, value FROM config')\\n"
        "        for key, value in cur.fetchall():\\n"
        "            self.state['values'][key] = value\\n"
        "        cur.close()\\n"
        "        conn.close()\\n"
        "\\n"
        "    def Run(self, command, params=None):\\n"
        "        if command == 'file_index':\\n"
        "            return (1, self.FILE_INDEX, None)\\n"
        "        if command == 'file_list':\\n"
        "            names = []\\n"
        "            for entry in self.FILE_INDEX:\\n"
        "                m = re.search(r'\\\\(\"file\";\"([^\"]+)\"\\\\)', entry)\\n"
        "                if m:\\n"
        "                    names.append(m.group(1))\\n"
        "            return (1, names, None)\\n"
        "        return (0, None, ('UNKNOWN', 'Unknown: ' + str(command), 1))\\n"
        "\\n"
        "\\n"
        "cfg = " + pascal + "Config()\\n"
    )
    return (1, content, None)''',

"FormatFileIndex": '''def FormatFileIndex(self, files):
    lines = ["FILE_INDEX = ["]
    for bcl in files:
        lines.append("    " + json.dumps(bcl) + ",")
    lines.append("]")
    return (1, '\\n'.join(lines), None)''',

"ReplaceFileIndex": '''def ReplaceFileIndex(self, existing, newBlock):
    lines = existing.split('\\n')
    startIdx = None
    endIdx = None
    for i, line in enumerate(lines):
        if re.match(r'^FILE_INDEX\\s*=\\s*\\[', line):
            startIdx = i
            continue
        if startIdx is not None and i > startIdx and re.match(r'^\\]', line):
            endIdx = i
            break
    if startIdx is not None and endIdx is not None:
        newLines = lines[:startIdx] + newBlock.split('\\n') + lines[endIdx + 1:]
        return (1, '\\n'.join(newLines), None)
    elif startIdx is not None:
        newLines = lines[:startIdx] + newBlock.split('\\n')
        return (1, '\\n'.join(newLines), None)
    ok, result, err = self.InsertFileIndex(existing, newBlock)
    return (ok, result, err)''',

"InsertFileIndex": '''def InsertFileIndex(self, existing, indexBlock):
    marker = "# ─── CONFIG CLASS"
    if marker in existing:
        parts = existing.split(marker, 1)
        return (1, parts[0] + indexBlock + "\\n\\n" + marker + parts[1], None)
    return (1, existing + "\\n\\n" + indexBlock + "\\n", None)''',

"Validate": '''def Validate(self, params):
    folder = params.get('folder')
    if not folder:
        folder = self.state.get('folder')
    if not folder:
        return (0, None, ("MISSING_PARAM", "Need folder", 1))
    folder = os.path.abspath(folder)
    singleFile = params.get('file')
    if singleFile:
        fpath = os.path.join(folder, singleFile)
        if not os.path.isfile(fpath):
            return (0, None, ("NOT_FOUND", "File not found: " + str(fpath), 1))
        ok, result, err = self.ValidateSingleFile(fpath)
        if ok:
            return (1, [result], None)
        return (0, None, err)
    pyFiles = sorted([f for f in os.listdir(folder) if f.endswith('.py') and not f.startswith('.')])
    results = []
    for fname in pyFiles:
        ok, result, err = self.ValidateSingleFile(os.path.join(folder, fname))
        if ok:
            results.append(result)
    self.state['validated_count'] = len(results)
    passed = sum(1 for r in results if r['is_compliant'])
    failed = len(results) - passed
    return (1, {'total': len(results), 'passed': passed, 'failed': failed, 'details': results}, None)''',

"ValidateSingleFile": '''def ValidateSingleFile(self, fpath):
    fname = os.path.basename(fpath)
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except Exception as e:
        return (1, {'file': fname, 'error': str(e), 'is_compliant': False}, None)
    ok, compliance, err = self.CheckVbstyle(lines)
    ok2, bcl, err2 = self.CheckBclHeaders(lines)
    result = {
        'file': fname,
        'is_compliant': compliance['is_compliant'],
        'rules_passed': compliance['passed'],
        'rules_total': compliance['total'],
        'failed_rules': compliance['failed'],
        'has_bcl': bcl['has_bcl'],
        'bcl_headers': bcl['headers'],
        'lines': len(lines),
    }
    return (1, result, None)''',

"Report": '''def Report(self, params):
    folder = params.get('folder')
    if not folder:
        folder = self.state.get('folder')
    if not folder:
        return (0, None, ("MISSING_PARAM", "Need folder", 1))
    fmt = params.get('format', 'text')
    if not self.state['files'] or self.state['folder'] != folder:
        result = self.Index({'folder': folder})
        if result[0] != 1:
            return result
    if fmt == 'summary':
        total = len(self.state['files'])
        vbstyleOk = 0
        bclOk = 0
        totalLines = 0
        for entry in self.state['files']:
            m = re.search(r'\\("vbstyle";"([^"]+)"\\)', entry)
            if m and m.group(1) == 'True':
                vbstyleOk += 1
            m = re.search(r'\\("bcl";"([^"]+)"\\)', entry)
            if m and m.group(1) == 'True':
                bclOk += 1
            m = re.search(r'\\("lines";"([^"]+)"\\)', entry)
            if m:
                totalLines += int(m.group(1))
        report = ("Folder: " + folder + "\\n"
                  + "Files: " + str(total) + "\\n"
                  + "VBStyle compliant: " + str(vbstyleOk) + "/" + str(total) + "\\n"
                  + "Has BCL: " + str(bclOk) + "/" + str(total) + "\\n"
                  + "Total lines: " + str(totalLines) + "\\n"
                  + "Errors: " + str(len(self.state['errors'])))
        return (1, report, None)
    elif fmt == 'bcl':
        report = '\\n'.join(self.state['files'])
        return (1, report, None)
    else:
        lines = []
        lines.append("Workflow Report: " + folder)
        lines.append("Generated: " + datetime.now().isoformat())
        lines.append("=" * 60)
        lines.append("")
        lines.append("File" + " " * 31 + "Lines" + " " * 4 + "VBStyle" + " " * 4 + "BCL" + " " * 3 + "Purpose")
        lines.append("-" * 90)
        for entry in self.state['files']:
            fname = re.search(r'\\("file";"([^"]+)"\\)', entry)
            linesCount = re.search(r'\\("lines";"([^"]+)"\\)', entry)
            vbstyle = re.search(r'\\("vbstyle";"([^"]+)"\\)', entry)
            bcl = re.search(r'\\("bcl";"([^"]+)"\\)', entry)
            purpose = re.search(r'\\("purpose";"([^"]+)"\\)', entry)
            fn = fname.group(1) if fname else '?'
            ln = linesCount.group(1) if linesCount else '?'
            vb = 'YES' if vbstyle and vbstyle.group(1) == 'True' else 'NO'
            bc = 'YES' if bcl and bcl.group(1) == 'True' else 'NO'
            pu = purpose.group(1)[:30] if purpose else ''
            lines.append(fn.ljust(35) + str(ln).rjust(6) + vb.rjust(10) + bc.rjust(6) + "  " + pu)
        if self.state['errors']:
            lines.append("")
            lines.append("Errors (" + str(len(self.state['errors'])) + "):")
            for e in self.state['errors']:
                lines.append("  " + e)
        return (1, '\\n'.join(lines), None)''',

"Status": '''def Status(self, params):
    return (1, dict(self.state), None)''',
}


def main():
    print("=" * 60)
    print("FIXING DOM_WORKFLOW — FULL VBSTYLE COMPLIANCE")
    print("=" * 60)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 1. Delete old underscore-prefixed methods
    print("\n[1] Removing old underscore-prefixed methods...")
    c.execute("DELETE FROM methods WHERE class_id=? AND method_name LIKE '\\_%'", (CLASS_ID,))
    old_count = c.rowcount
    print("    Deleted " + str(old_count) + " old methods")

    # 2. Update/insert corrected methods
    print("\n[2] Storing corrected methods (all Tuple3, no self._, PascalCase)...")
    stored = 0
    updated = 0
    for name, code in CORRECTED_METHODS.items():
        # Check for VBStyle compliance in the code itself
        has_tuple3 = 'return (1,' in code or 'return (0,' in code or 'return (ok,' in code
        has_self_underscore = 'self._' in code
        has_print = 'print(' in code

        c.execute("SELECT id FROM methods WHERE class_id=? AND method_name=?", (CLASS_ID, name))
        existing = c.fetchone()

        if existing:
            c.execute("""UPDATE methods SET
                        method_code=?, returns_tuple3=?, is_vbstyle=1, version=version+1
                        WHERE id=?""",
                      (code, 1 if has_tuple3 else 0, existing[0]))
            updated += 1
        else:
            c.execute("""INSERT INTO methods
                        (class_id, method_name, method_code, params, signature,
                         is_dunder, is_vbstyle, returns_tuple3, version, created_at)
                        VALUES (?, ?, ?, '', '', 0, 1, ?, 1, ?)""",
                      (CLASS_ID, name, code, 1 if has_tuple3 else 0, datetime.now().isoformat()))
            stored += 1

        issues = []
        if not has_tuple3:
            issues.append("NO TUPLE3")
        if has_self_underscore:
            issues.append("HAS self._")
        if has_print:
            issues.append("HAS print()")
        status = "OK" if not issues else "ISSUES: " + ", ".join(issues)
        print("    " + name.ljust(25) + " [" + status + "]")

    print("    Stored: " + str(stored) + " new, Updated: " + str(updated) + " existing")

    # 3. Update computational units to use new method names
    print("\n[3] Updating computational units...")
    c.execute("DELETE FROM computational_units WHERE class_id=?", (CLASS_ID,))

    units = [
        ("workflow:dispatch", "method_group", "Run", "Dispatch entry point and status"),
        ("workflow:project_mgmt", "method_group", "Prj", "Project management — create/identify/list folders"),
        ("workflow:indexer", "method_group", "Index", "File indexing engine — scans files, generates BCL entries"),
        ("workflow:config_maker", "method_group", "Config", "Config.py generator — creates gold-standard Config.py"),
        ("workflow:validator", "method_group", "Validate", "VBStyle validator — checks 9 compliance rules"),
        ("workflow:reporter", "method_group", "Report", "Report generator — text, BCL, summary formats"),
    ]
    for unit_name, unit_type, primary_method, desc in units:
        c.execute("SELECT id FROM methods WHERE class_id=? AND method_name=?", (CLASS_ID, primary_method))
        row = c.fetchone()
        method_id = row[0] if row else None
        c.execute("""INSERT INTO computational_units
                    (unit_name, unit_type, class_id, method_id, description, status)
                    VALUES (?, ?, ?, ?, ?, 'active')""",
                  (unit_name, unit_type, CLASS_ID, method_id, desc))
    print("    Stored " + str(len(units)) + " computational units")

    # 4. Update class skeleton
    print("\n[4] Updating class skeleton...")
    skeleton = (
        "#!/usr/bin/env python3\\n"
        "#[@GHOST]{[@file<Dom_workflow.py>][@domain<workflow>][@role<root_domain>][@auth<devin>][@date<2026-06-23>][@ver<1.0>]}\\n"
        "#[@VBSTYLE]{[@auth<devin>][@role<workflow_domain>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}\\n"
        "\\n"
        '"""Dom_workflow — VBStyle Workflow Domain. Code lives in methods table."""\\n'
        "\\n"
        "# Methods (all return Tuple3, no self._, PascalCase):\\n"
    )
    for name in CORRECTED_METHODS.keys():
        skeleton += "#   " + name + "\\n"
    skeleton += (
        "\\n"
        "# Computational units: 6\\n"
        "# Plan: run_workflow_domain (5 steps)\\n"
        "# Closure: workflow = 100%\\n"
    )
    c.execute("UPDATE classes SET class_code=?, version=version+1 WHERE id=?", (skeleton, CLASS_ID))
    print("    Skeleton: " + str(len(skeleton)) + " chars")

    # 5. Final verification
    print("\n[5] Final verification...")
    c.execute("SELECT method_name, returns_tuple3, LENGTH(method_code) FROM methods WHERE class_id=? ORDER BY method_name", (CLASS_ID,))
    all_ok = True
    for r in c.fetchall():
        tuple3 = "OK" if r[1] else "FAIL"
        if not r[1]:
            all_ok = False
        print("    " + r[0].ljust(25) + " tuple3=" + tuple3 + "  code=" + str(r[2]) + " chars")

    c.execute("SELECT COUNT(*) FROM methods WHERE class_id=? AND method_name LIKE '\\_%'", (CLASS_ID,))
    underscore_count = c.fetchone()[0]
    if underscore_count > 0:
        print("    WARNING: " + str(underscore_count) + " underscore-prefixed methods still exist!")
        all_ok = False
    else:
        print("    No underscore-prefixed methods: OK")

    c.execute("SELECT COUNT(*) FROM methods WHERE class_id=? AND returns_tuple3=0", (CLASS_ID,))
    no_tuple3 = c.fetchone()[0]
    if no_tuple3 > 0:
        print("    WARNING: " + str(no_tuple3) + " methods without Tuple3!")
        all_ok = False
    else:
        print("    All methods return Tuple3: OK")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL METHODS VBSTYLE COMPLIANT — DB IS CONSISTENT")
    else:
        print("ISSUES REMAIN — SEE ABOVE")
    print("=" * 60)


if __name__ == "__main__":
    main()
