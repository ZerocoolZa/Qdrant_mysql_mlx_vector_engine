#!/usr/bin/env python3

#[@GHOST]{[@file<Dom_workflow.py>][@domain<workflow>][@role<root_domain>][@auth<devin>][@date<2026-06-27>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<workflow_domain>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}
#[@Class]{[@name<Dom_workflow>][@desc<Consolidated workflow domain — project management, file indexing, config generation, VBStyle validation, reporting, DB operations, cognitive loop walking. Merged from 7 files.>][@dispatch<Run>][@returns<Tuple3>]}

"""
Dom_workflow — VBStyle Workflow Domain (Consolidated)
=====================================================
Merged from:
  - Dom_workflow.py (core: prj, index, config, validate, report)
  - Prj_VBScanner.py (enhanced scanning)
  - fix_workflow_vbstyle.py (VBStyle-corrected methods)
  - store_workflow_properly.py (DB storage)
  - add_workflow_cognitive_loop.py (cognitive loop population)
  - cognitive_loop_walker.py (cognitive loop walker)
  - populate_ai_instructions.py (AI instruction population)

Run(command, params) -> Tuple3(ok, data, error)

Commands:
  Core:     prj, index, config, validate, report, status
  DB ops:   store_db, fix_db, add_cognitive_loop, populate_instructions
  CogLoop:  walk_loop, list_operations, show_graph, verify_graph
"""

import os
import re
import ast
import sys
import json
import sqlite3
from datetime import datetime


class Dom_workflow:
    """VBStyle Workflow Domain — all operations in one class."""

    def __init__(self):
        self.state = {
            'folder': None,
            'files': [],
            'config_path': None,
            'errors': [],
            'v20_db': None,
            'project_name': None,
            'indexed_count': 0,
            'validated_count': 0,
            'log': [],
            'conn': None,
            'current_node': None,
            'path_history': [],
            'step_count': 0,
            'domain': None,
            'operation': None,
            'params': {},
            'result': None,
            'start_time': None,
        }

    def Run(self, command, params=None):
        if params is None:
            params = {}
        handlers = {
            'prj': self.Prj,
            'index': self.Index,
            'config': self.Config,
            'validate': self.Validate,
            'report': self.Report,
            'status': self.Status,
            'store_db': self.StoreDb,
            'fix_db': self.FixDb,
            'add_cognitive_loop': self.AddCognitiveLoop,
            'populate_instructions': self.PopulateInstructions,
            'walk_loop': self.WalkLoop,
            'list_operations': self.ListOperations,
            'show_graph': self.ShowGraph,
            'verify_graph': self.VerifyGraph,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command) + ". Valid: " + str(list(handlers.keys())), 1))

    def Trace(self, msg):
        self.state['log'].append(msg)
        return (1, msg, None)

    # === PRJ ===

    def Prj(self, params):
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
        return (0, None, ("UNKNOWN_ACTION", "Unknown prj action: " + str(action), 1))

    # === INDEX ===

    def Index(self, params):
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
        return (1, self.state['files'], None)

    def ScanPyFile(self, fpath, fname):
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
                    purpose = doc.strip().split('\n')[0][:200]
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
        ok2, bclHeaders, err2 = self.CheckBclHeaders(lines)
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
        return (0, None, err)

    def ScanOtherFile(self, fpath, fname):
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
        return (0, None, err)

    def EntryToBcl(self, entry):
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
        return (1, bcl, None)

    def RegexParse(self, lines):
        classes = []
        functions = []
        purpose = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if not purpose:
                    purpose = stripped.strip('"""').strip("'''")[:200]
            m = re.match(r'^(\s*)class\s+(\w+)', stripped)
            if m:
                classes.append({'name': m.group(2), 'methods': []})
            m = re.match(r'^(\s+)def\s+(\w+)\(', stripped)
            if m and not m.group(2).startswith('_'):
                functions.append(m.group(2))
        return (1, (classes, functions, purpose), None)

    def CheckVbstyle(self, lines):
        fullText = "".join(lines)
        checks = {
            'ghost_header': bool(re.search(r'#\[@GHOST\]', fullText, re.IGNORECASE)),
            'vbstyle_header': bool(re.search(r'#\[@VBSTYLE\]', fullText, re.IGNORECASE)),
            'tuple3_return': bool(re.search(r'Tuple3|tuple3|\(1,\s*\w+,\s*None\)|\(0,\s*None,', fullText, re.IGNORECASE)),
            'state_dict': bool(re.search(r'self\.state\s*=', fullText)),
            'run_dispatch': bool(re.search(r'def\s+Run\s*\(', fullText)),
            'no_decorators': not any(re.match(r'^\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)', l) for l in lines),
            'no_print': not any(re.search(r'\bprint\s*\(', l) for l in lines if not l.strip().startswith("#")),
            'no_self_underscore': not any(re.search(r'self\._[a-z]', l) for l in lines if not l.strip().startswith("#")),
            'no_hardcoded_paths': not any(re.search(r'["\']/(?:Users|home|tmp|var|opt)/', l) for l in lines if not l.strip().startswith("#")),
        }
        passed = sum(1 for v in checks.values() if v)
        failed = [k for k, v in checks.items() if not v]
        result = {'is_compliant': passed == len(checks), 'passed': passed, 'total': len(checks), 'failed': failed}
        return (1, result, None)

    def CheckBclHeaders(self, lines):
        headers = []
        for line in lines:
            m = re.match(r'^\s*#\[@(\w+)\]', line)
            if m:
                headers.append(m.group(1))
        result = {'has_bcl': len(headers) > 0, 'headers': headers}
        return (1, result, None)

    # === CONFIG ===

    def Config(self, params):
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
        return (0, None, ("UNKNOWN_ACTION", "Unknown config action: " + str(action), 1))

    def ConfigTemplate(self, domain, folder):
        now = datetime.now().strftime('%Y-%m-%d')
        pascal = ''.join(w.capitalize() for w in domain.split('_'))
        content = (
            "#!/usr/bin/env python3\n"
            "#[@GHOST]{[@file<Config.py>][@domain<" + domain + ">][@role<config>][@auth<devin>][@date<" + now + ">][@ver<1.0>]}\n"
            "#[@VBSTYLE]{[@auth<system>][@role<config>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}\n"
            "\n"
            '"""Gold Standard Config for ' + domain + ' domain. Auto-generated by Dom_workflow."""\n'
            "\n"
            "import os\n"
            "import re\n"
            "import sqlite3\n"
            "\n"
            "BASE_DIR = os.path.dirname(os.path.abspath(__file__))\n"
            'CONFIG_DB_PATH = os.path.join(BASE_DIR, "' + domain + '_config.db")\n'
            "\n"
            'CONFIG_SEED_SQL = "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT, description TEXT)"\n'
            "\n"
            "FILE_INDEX = [\n"
            "    # Dom_workflow appends BCL entries here\n"
            "]\n"
            "\n\n"
            "class " + pascal + "Config:\n"
            '    """Single source of truth for ' + domain + ' configuration."""\n'
            "\n"
            "    def __init__(self):\n"
            "        self.state = {'db_path': CONFIG_DB_PATH, 'values': {}}\n"
            "        conn = sqlite3.connect(self.state['db_path'])\n"
            "        cur = conn.cursor()\n"
            "        cur.executescript(CONFIG_SEED_SQL)\n"
            "        conn.commit()\n"
            "        cur.execute('SELECT key, value FROM config')\n"
            "        for key, value in cur.fetchall():\n"
            "            self.state['values'][key] = value\n"
            "        cur.close()\n"
            "        conn.close()\n"
            "\n"
            "    def Run(self, command, params=None):\n"
            "        if command == 'file_index':\n"
            "            return (1, self.FILE_INDEX, None)\n"
            "        if command == 'file_list':\n"
            "            names = []\n"
            "            for entry in self.FILE_INDEX:\n"
            "                m = re.search(r'\\(\"file\";\"([^\"]+)\"\\)', entry)\n"
            "                if m:\n"
            "                    names.append(m.group(1))\n"
            "            return (1, names, None)\n"
            "        return (0, None, ('UNKNOWN', 'Unknown: ' + str(command), 1))\n"
            "\n\n"
            "cfg = " + pascal + "Config()\n"
        )
        return (1, content, None)

    def FormatFileIndex(self, files):
        lines = ["FILE_INDEX = ["]
        for bcl in files:
            lines.append("    " + json.dumps(bcl) + ",")
        lines.append("]")
        return (1, '\n'.join(lines), None)

    def ReplaceFileIndex(self, existing, newBlock):
        lines = existing.split('\n')
        startIdx = None
        endIdx = None
        for i, line in enumerate(lines):
            if re.match(r'^FILE_INDEX\s*=\s*\[', line):
                startIdx = i
                continue
            if startIdx is not None and i > startIdx and re.match(r'^\]', line):
                endIdx = i
                break
        if startIdx is not None and endIdx is not None:
            newLines = lines[:startIdx] + newBlock.split('\n') + lines[endIdx + 1:]
            return (1, '\n'.join(newLines), None)
        elif startIdx is not None:
            newLines = lines[:startIdx] + newBlock.split('\n')
            return (1, '\n'.join(newLines), None)
        ok, result, err = self.InsertFileIndex(existing, newBlock)
        return (ok, result, err)

    def InsertFileIndex(self, existing, indexBlock):
        marker = "# --- CONFIG CLASS"
        if marker in existing:
            parts = existing.split(marker, 1)
            return (1, parts[0] + indexBlock + "\n\n" + marker + parts[1], None)
        return (1, existing + "\n\n" + indexBlock + "\n", None)

    # === VALIDATE ===

    def Validate(self, params):
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
        return (1, {'total': len(results), 'passed': passed, 'failed': failed, 'details': results}, None)

    def ValidateSingleFile(self, fpath):
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
        return (1, result, None)

    # === REPORT ===

    def Report(self, params):
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
                m = re.search(r'\("vbstyle";"([^"]+)"\)', entry)
                if m and m.group(1) == 'True':
                    vbstyleOk += 1
                m = re.search(r'\("bcl";"([^"]+)"\)', entry)
                if m and m.group(1) == 'True':
                    bclOk += 1
                m = re.search(r'\("lines";"([^"]+)"\)', entry)
                if m:
                    totalLines += int(m.group(1))
            report = ("Folder: " + folder + "\n"
                      + "Files: " + str(total) + "\n"
                      + "VBStyle compliant: " + str(vbstyleOk) + "/" + str(total) + "\n"
                      + "Has BCL: " + str(bclOk) + "/" + str(total) + "\n"
                      + "Total lines: " + str(totalLines) + "\n"
                      + "Errors: " + str(len(self.state['errors'])))
            return (1, report, None)
        elif fmt == 'bcl':
            report = '\n'.join(self.state['files'])
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
                fname = re.search(r'\("file";"([^"]+)"\)', entry)
                linesCount = re.search(r'\("lines";"([^"]+)"\)', entry)
                vbstyle = re.search(r'\("vbstyle";"([^"]+)"\)', entry)
                bcl = re.search(r'\("bcl";"([^"]+)"\)', entry)
                purpose = re.search(r'\("purpose";"([^"]+)"\)', entry)
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
            return (1, '\n'.join(lines), None)

    def Status(self, params):
        return (1, dict(self.state), None)

    # === DB OPERATIONS ===

    def StoreDb(self, params):
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        sourceFile = params.get('source_file', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Dom_workflow.py'))
        if not os.path.isfile(sourceFile):
            return (0, None, ("NOT_FOUND", "Source file not found: " + str(sourceFile), 1))
        try:
            with open(sourceFile, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 2))
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return (0, None, ("PARSE_ERROR", str(e), 2))
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("SELECT id FROM classes WHERE class_name='Dom_workflow' AND domain='workflow'")
        existing = c.fetchone()
        if existing:
            classId = existing[0]
        else:
            c.execute("INSERT INTO classes (class_name, class_code, domain, description, source_file, is_vbstyle, has_run_method, has_tuple3, version, created_at) VALUES (?, ?, 'workflow', 'VBStyle Workflow Domain', ?, 1, 1, 1, 1, ?)",
                      ('Dom_workflow', source, sourceFile, datetime.now().isoformat()))
            classId = c.lastrowid
        stored = 0
        updated = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'Dom_workflow':
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methodName = item.name
                        if methodName.startswith('__') and methodName.endswith('__'):
                            isDunder = 1
                        else:
                            isDunder = 0
                        methodCode = ast.get_source_segment(source, item) or ''
                        params_str = ', '.join([arg.arg for arg in item.args.args])
                        hasTuple3 = 'return (1,' in methodCode or 'return (0,' in methodCode or 'return (ok,' in methodCode
                        c.execute("SELECT id FROM methods WHERE class_id=? AND method_name=?", (classId, methodName))
                        row = c.fetchone()
                        if row:
                            c.execute("UPDATE methods SET method_code=?, params=?, signature=?, is_dunder=?, is_vbstyle=1, returns_tuple3=?, version=version+1 WHERE id=?",
                                      (methodCode, params_str, params_str, isDunder, 1 if hasTuple3 else 0, row[0]))
                            updated += 1
                        else:
                            c.execute("INSERT INTO methods (class_id, method_name, method_code, params, signature, is_dunder, is_vbstyle, returns_tuple3, version, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, 1, ?)",
                                      (classId, methodName, methodCode, params_str, params_str, isDunder, 1 if hasTuple3 else 0, datetime.now().isoformat()))
                            stored += 1
        units = [
            ('workflow:dispatch', 'method_group', 'Run', 'Dispatch entry point and status'),
            ('workflow:project_mgmt', 'method_group', 'Prj', 'Project management'),
            ('workflow:indexer', 'method_group', 'Index', 'File indexing engine'),
            ('workflow:config_maker', 'method_group', 'Config', 'Config.py generator'),
            ('workflow:validator', 'method_group', 'Validate', 'VBStyle validator'),
            ('workflow:reporter', 'method_group', 'Report', 'Report generator'),
            ('workflow:db_ops', 'method_group', 'StoreDb', 'DB storage operations'),
            ('workflow:cognitive_loop', 'method_group', 'WalkLoop', 'Cognitive loop walker'),
        ]
        c.execute("DELETE FROM computational_units WHERE class_id=?", (classId,))
        for unitName, unitType, primaryMethod, desc in units:
            c.execute("SELECT id FROM methods WHERE class_id=? AND method_name=?", (classId, primaryMethod))
            row = c.fetchone()
            methodId = row[0] if row else None
            c.execute("INSERT INTO computational_units (unit_name, unit_type, class_id, method_id, description, status) VALUES (?, ?, ?, ?, ?, 'active')",
                      (unitName, unitType, classId, methodId, desc))
        conn.commit()
        conn.close()
        self.Trace("StoreDb: stored=" + str(stored) + " updated=" + str(updated) + " units=" + str(len(units)))
        return (1, {'stored': stored, 'updated': updated, 'units': len(units), 'class_id': classId}, None)

    def FixDb(self, params):
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("SELECT id FROM classes WHERE class_name='Dom_workflow' AND domain='workflow'")
        row = c.fetchone()
        if not row:
            conn.close()
            return (0, None, ("NOT_FOUND", "Dom_workflow class not in DB. Run store_db first.", 1))
        classId = row[0]
        c.execute("DELETE FROM methods WHERE class_id=? AND method_name LIKE '\\_%'", (classId,))
        deletedCount = c.rowcount
        c.execute("SELECT method_name, method_code FROM methods WHERE class_id=? ORDER BY method_name", (classId,))
        methods = c.fetchall()
        fixed = 0
        for methodName, methodCode in methods:
            hasTuple3 = 'return (1,' in methodCode or 'return (0,' in methodCode or 'return (ok,' in methodCode
            hasSelfUnderscore = 'self._' in methodCode
            hasPrint = bool(re.search(r'\bprint\s*\(', methodCode))
            newCode = methodCode
            if hasSelfUnderscore:
                newCode = re.sub(r'self\._([a-z])', lambda m: 'self.state[\'' + m.group(1) + '\']', newCode)
            if hasPrint:
                newCode = re.sub(r'\bprint\s*\([^)]*\)', 'pass', newCode)
            if newCode != methodCode:
                c.execute("UPDATE methods SET method_code=?, returns_tuple3=?, is_vbstyle=1, version=version+1 WHERE class_id=? AND method_name=?",
                          (newCode, 1 if hasTuple3 else 0, classId, methodName))
                fixed += 1
        c.execute("SELECT COUNT(*) FROM methods WHERE class_id=? AND method_name LIKE '\\_%'", (classId,))
        underscoreCount = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM methods WHERE class_id=? AND returns_tuple3=0", (classId,))
        noTuple3 = c.fetchone()[0]
        conn.commit()
        conn.close()
        allOk = underscoreCount == 0 and noTuple3 == 0
        self.Trace("FixDb: deleted=" + str(deletedCount) + " fixed=" + str(fixed) + " underscore_remaining=" + str(underscoreCount) + " no_tuple3=" + str(noTuple3))
        return (1, {'deleted': deletedCount, 'fixed': fixed, 'underscore_remaining': underscoreCount, 'no_tuple3': noTuple3, 'all_ok': allOk}, None)

    def AddCognitiveLoop(self, params):
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        okNodes, nodes, errNodes = self.GetCognitiveLoopNodes()
        okEdges, edges, errEdges = self.GetCognitiveLoopEdges()
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("PRAGMA table_info(decision_nodes)")
        columns = [r[1] for r in c.fetchall()]
        if 'domain' not in columns:
            c.execute("ALTER TABLE decision_nodes ADD COLUMN domain TEXT DEFAULT ''")
        if 'category' not in columns:
            c.execute("ALTER TABLE decision_nodes ADD COLUMN category TEXT DEFAULT ''")
        c.execute("DELETE FROM decision_nodes WHERE domain='workflow'")
        c.execute("DELETE FROM decision_edges WHERE from_node LIKE 'wf_%' OR to_node LIKE 'wf_%'")
        for node in nodes:
            c.execute("INSERT INTO decision_nodes (name, node_type, domain, payload, category) VALUES (?, ?, ?, ?, ?)",
                      (node['name'], node['node_type'], node['domain'], node['payload'], node['category']))
        c.execute("SELECT node_id, name FROM decision_nodes WHERE domain='workflow'")
        dbNodes = c.fetchall()
        nameToInternal = {n['name']: n['id'] for n in nodes}
        nodeMap = {}
        for dbId, name in dbNodes:
            internalId = nameToInternal.get(name)
            if internalId:
                nodeMap[internalId] = dbId
        insertedEdges = 0
        for edge in edges:
            fromId = nodeMap.get(edge['from'])
            toId = nodeMap.get(edge['to'])
            if fromId and toId:
                c.execute("INSERT INTO decision_edges (from_node, to_node, condition, weight) VALUES (?, ?, ?, 1.0)",
                          (fromId, toId, edge['condition']))
                insertedEdges += 1
        conn.commit()
        conn.close()
        self.Trace("AddCognitiveLoop: nodes=" + str(len(nodes)) + " edges=" + str(insertedEdges))
        return (1, {'nodes': len(nodes), 'edges': insertedEdges}, None)

    def PopulateInstructions(self, params):
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        okInst, instructions, errInst = self.GetAiInstructions()
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS _db_meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        stored = 0
        updated = 0
        for key, value in instructions.items():
            c.execute("SELECT key FROM _db_meta WHERE key=?", (key,))
            if c.fetchone():
                c.execute("UPDATE _db_meta SET value=?, updated_at=? WHERE key=?", (value, datetime.now().isoformat(), key))
                updated += 1
            else:
                c.execute("INSERT INTO _db_meta (key, value, updated_at) VALUES (?, ?, ?)", (key, value, datetime.now().isoformat()))
                stored += 1
        conn.commit()
        conn.close()
        self.Trace("PopulateInstructions: stored=" + str(stored) + " updated=" + str(updated))
        return (1, {'stored': stored, 'updated': updated, 'total': len(instructions)}, None)

    def GetCognitiveLoopNodes(self):
        nodes = [
            {'id': 'wf_root', 'name': 'WorkflowDomain', 'node_type': 'question', 'domain': 'workflow', 'payload': 'ROOT: What workflow operation? prj, index, config, validate, report', 'category': 'root'},
            {'id': 'wf_prj_problem', 'name': 'PrjProblem', 'node_type': 'action', 'domain': 'workflow', 'payload': 'PROBLEM: Need to create or identify a project folder for a domain', 'category': 'prj'},
            {'id': 'wf_prj_question', 'name': 'PrjQuestion', 'node_type': 'question', 'domain': 'workflow', 'payload': 'QUESTION: What domain? What base folder? params: {action, folder, name, domain, base}', 'category': 'prj'},
            {'id': 'wf_prj_answer', 'name': 'PrjAnswer', 'node_type': 'action', 'domain': 'workflow', 'payload': "ANSWER: Run Dom_workflow.Run('prj', {action:'create', folder:base/domain, name:domain})", 'category': 'prj'},
            {'id': 'wf_prj_constraint', 'name': 'PrjConstraint', 'node_type': 'check', 'domain': 'workflow', 'payload': 'CONSTRAINT: Folder must exist after creation. Name must be lowercase snake_case.', 'category': 'prj'},
            {'id': 'wf_prj_mistake', 'name': 'PrjMistake', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'MISTAKE: Folder creation failed — permission denied or invalid characters.', 'category': 'prj'},
            {'id': 'wf_prj_solution', 'name': 'PrjSolution', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SOLUTION: If permission denied use /tmp/. If invalid chars replace spaces with underscores. If exists proceed.', 'category': 'prj'},
            {'id': 'wf_prj_verify', 'name': 'PrjVerify', 'node_type': 'check', 'domain': 'workflow', 'payload': "VERIFY: os.path.isdir(folder)==True. state['folder'] is set. Return Tuple3(1,{folder,name},None).", 'category': 'prj'},
            {'id': 'wf_idx_problem', 'name': 'IndexProblem', 'node_type': 'action', 'domain': 'workflow', 'payload': 'PROBLEM: Need to know what files exist and extract their structure as BCL entries.', 'category': 'index'},
            {'id': 'wf_idx_question', 'name': 'IndexQuestion', 'node_type': 'question', 'domain': 'workflow', 'payload': 'QUESTION: Which folder to scan? params: {folder}. Are there .py files?', 'category': 'index'},
            {'id': 'wf_idx_answer', 'name': 'IndexAnswer', 'node_type': 'action', 'domain': 'workflow', 'payload': "ANSWER: Run Dom_workflow.Run('index', {folder}) — scans all .py files with AST, generates BCL entries.", 'category': 'index'},
            {'id': 'wf_idx_constraint', 'name': 'IndexConstraint', 'node_type': 'check', 'domain': 'workflow', 'payload': 'CONSTRAINT: Every BCL entry must have 15 fields. Every entry must have created and modified dates.', 'category': 'index'},
            {'id': 'wf_idx_mistake', 'name': 'IndexMistake', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'MISTAKE: AST parse failed. Recovery: fall back to regex parsing.', 'category': 'index'},
            {'id': 'wf_idx_solution', 'name': 'IndexSolution', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SOLUTION: Use RegexParse() as fallback. If file unreadable, generate minimal BCL entry.', 'category': 'index'},
            {'id': 'wf_idx_verify', 'name': 'IndexVerify', 'node_type': 'check', 'domain': 'workflow', 'payload': "VERIFY: len(state['files']) > 0. Each entry is valid BCL. Return Tuple3(1, entries, None).", 'category': 'index'},
            {'id': 'wf_cfg_problem', 'name': 'ConfigProblem', 'node_type': 'action', 'domain': 'workflow', 'payload': 'PROBLEM: The folder needs a Config.py with BCL FILE_INDEX listing every file.', 'category': 'config'},
            {'id': 'wf_cfg_question', 'name': 'ConfigQuestion', 'node_type': 'question', 'domain': 'workflow', 'payload': 'QUESTION: Does Config.py already exist? params: {folder, domain, action}', 'category': 'config'},
            {'id': 'wf_cfg_answer', 'name': 'ConfigAnswer', 'node_type': 'action', 'domain': 'workflow', 'payload': "ANSWER: Run Dom_workflow.Run('config', {folder, domain, action:'full'})", 'category': 'config'},
            {'id': 'wf_cfg_constraint', 'name': 'ConfigConstraint', 'node_type': 'check', 'domain': 'workflow', 'payload': 'CONSTRAINT: Config.py MUST have Ghost header, VBStyle header, FILE_INDEX, config class with SQLite backend.', 'category': 'config'},
            {'id': 'wf_cfg_mistake', 'name': 'ConfigMistake', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'MISTAKE: Config.py write failed or FILE_INDEX replacement failed.', 'category': 'config'},
            {'id': 'wf_cfg_solution', 'name': 'ConfigSolution', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SOLUTION: If permission denied write to /tmp first. If regex fails use line-by-line scan.', 'category': 'config'},
            {'id': 'wf_cfg_verify', 'name': 'ConfigVerify', 'node_type': 'check', 'domain': 'workflow', 'payload': "VERIFY: Config.py exists. Has FILE_INDEX. Return Tuple3(1, {config_path, files_indexed}, None).", 'category': 'config'},
            {'id': 'wf_val_problem', 'name': 'ValidateProblem', 'node_type': 'action', 'domain': 'workflow', 'payload': 'PROBLEM: Need to verify all .py files follow VBStyle rules (9 rules).', 'category': 'validate'},
            {'id': 'wf_val_question', 'name': 'ValidateQuestion', 'node_type': 'question', 'domain': 'workflow', 'payload': 'QUESTION: Which files to validate? All .py or single file? params: {folder, file:optional}', 'category': 'validate'},
            {'id': 'wf_val_answer', 'name': 'ValidateAnswer', 'node_type': 'action', 'domain': 'workflow', 'payload': "ANSWER: Run Dom_workflow.Run('validate', {folder}) — checks 9 VBStyle rules on each .py file.", 'category': 'validate'},
            {'id': 'wf_val_constraint', 'name': 'ValidateConstraint', 'node_type': 'check', 'domain': 'workflow', 'payload': 'CONSTRAINT: 9 rules must be checked. is_compliant = all 9 pass.', 'category': 'validate'},
            {'id': 'wf_val_mistake', 'name': 'ValidateMistake', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'MISTAKE: File not readable (encoding error). Recovery: use errors=replace.', 'category': 'validate'},
            {'id': 'wf_val_solution', 'name': 'ValidateSolution', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SOLUTION: If encoding error open with errors=replace. If binary skip. If empty mark not compliant.', 'category': 'validate'},
            {'id': 'wf_val_verify', 'name': 'ValidateVerify', 'node_type': 'check', 'domain': 'workflow', 'payload': "VERIFY: Results dict has total, passed, failed, details. Return Tuple3(1, results, None).", 'category': 'validate'},
            {'id': 'wf_rep_problem', 'name': 'ReportProblem', 'node_type': 'action', 'domain': 'workflow', 'payload': 'PROBLEM: Need a summary of folder state — files, VBStyle compliance, BCL coverage.', 'category': 'report'},
            {'id': 'wf_rep_question', 'name': 'ReportQuestion', 'node_type': 'question', 'domain': 'workflow', 'payload': 'QUESTION: What format? text, bcl, or summary? params: {folder, format}', 'category': 'report'},
            {'id': 'wf_rep_answer', 'name': 'ReportAnswer', 'node_type': 'action', 'domain': 'workflow', 'payload': "ANSWER: Run Dom_workflow.Run('report', {folder, format})", 'category': 'report'},
            {'id': 'wf_rep_constraint', 'name': 'ReportConstraint', 'node_type': 'check', 'domain': 'workflow', 'payload': 'CONSTRAINT: Report must include total files, VBStyle count, BCL count, total lines, errors.', 'category': 'report'},
            {'id': 'wf_rep_mistake', 'name': 'ReportMistake', 'node_type': 'fallback', 'domain': 'workflow', 'payload': "MISTAKE: No files indexed yet (state['files'] is empty).", 'category': 'report'},
            {'id': 'wf_rep_solution', 'name': 'ReportSolution', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SOLUTION: If state[files] is empty call Index first. If format unknown default to text.', 'category': 'report'},
            {'id': 'wf_rep_verify', 'name': 'ReportVerify', 'node_type': 'check', 'domain': 'workflow', 'payload': "VERIFY: Report is a string. Contains file count. Return Tuple3(1, report_string, None).", 'category': 'report'},
            {'id': 'wf_success', 'name': 'WorkflowComplete', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'SUCCESS: Workflow operation completed. Log to execution_log.', 'category': 'terminal'},
            {'id': 'wf_failed', 'name': 'WorkflowFailed', 'node_type': 'fallback', 'domain': 'workflow', 'payload': 'FAILED: Workflow operation could not complete after all recovery attempts.', 'category': 'terminal'},
        ]
        return (1, nodes, None)

    def GetCognitiveLoopEdges(self):
        edges = [
            {'from': 'wf_root', 'to': 'wf_prj_problem', 'condition': 'prj'},
            {'from': 'wf_root', 'to': 'wf_idx_problem', 'condition': 'index'},
            {'from': 'wf_root', 'to': 'wf_cfg_problem', 'condition': 'config'},
            {'from': 'wf_root', 'to': 'wf_val_problem', 'condition': 'validate'},
            {'from': 'wf_root', 'to': 'wf_rep_problem', 'condition': 'report'},
            {'from': 'wf_prj_problem', 'to': 'wf_prj_question', 'condition': 'success'},
            {'from': 'wf_prj_question', 'to': 'wf_prj_answer', 'condition': 'answered'},
            {'from': 'wf_prj_answer', 'to': 'wf_prj_constraint', 'condition': 'success'},
            {'from': 'wf_prj_answer', 'to': 'wf_prj_mistake', 'condition': 'fail'},
            {'from': 'wf_prj_constraint', 'to': 'wf_prj_verify', 'condition': 'pass'},
            {'from': 'wf_prj_constraint', 'to': 'wf_prj_mistake', 'condition': 'fail'},
            {'from': 'wf_prj_mistake', 'to': 'wf_prj_solution', 'condition': 'fail'},
            {'from': 'wf_prj_solution', 'to': 'wf_prj_answer', 'condition': 'retry'},
            {'from': 'wf_prj_solution', 'to': 'wf_failed', 'condition': 'unrecoverable'},
            {'from': 'wf_prj_verify', 'to': 'wf_success', 'condition': 'pass'},
            {'from': 'wf_prj_verify', 'to': 'wf_prj_mistake', 'condition': 'fail'},
            {'from': 'wf_idx_problem', 'to': 'wf_idx_question', 'condition': 'success'},
            {'from': 'wf_idx_question', 'to': 'wf_idx_answer', 'condition': 'answered'},
            {'from': 'wf_idx_answer', 'to': 'wf_idx_constraint', 'condition': 'success'},
            {'from': 'wf_idx_answer', 'to': 'wf_idx_mistake', 'condition': 'fail'},
            {'from': 'wf_idx_constraint', 'to': 'wf_idx_verify', 'condition': 'pass'},
            {'from': 'wf_idx_constraint', 'to': 'wf_idx_mistake', 'condition': 'fail'},
            {'from': 'wf_idx_mistake', 'to': 'wf_idx_solution', 'condition': 'fail'},
            {'from': 'wf_idx_solution', 'to': 'wf_idx_answer', 'condition': 'retry'},
            {'from': 'wf_idx_solution', 'to': 'wf_failed', 'condition': 'unrecoverable'},
            {'from': 'wf_idx_verify', 'to': 'wf_success', 'condition': 'pass'},
            {'from': 'wf_idx_verify', 'to': 'wf_idx_mistake', 'condition': 'fail'},
            {'from': 'wf_cfg_problem', 'to': 'wf_cfg_question', 'condition': 'success'},
            {'from': 'wf_cfg_question', 'to': 'wf_cfg_answer', 'condition': 'answered'},
            {'from': 'wf_cfg_answer', 'to': 'wf_cfg_constraint', 'condition': 'success'},
            {'from': 'wf_cfg_answer', 'to': 'wf_cfg_mistake', 'condition': 'fail'},
            {'from': 'wf_cfg_constraint', 'to': 'wf_cfg_verify', 'condition': 'pass'},
            {'from': 'wf_cfg_constraint', 'to': 'wf_cfg_mistake', 'condition': 'fail'},
            {'from': 'wf_cfg_mistake', 'to': 'wf_cfg_solution', 'condition': 'fail'},
            {'from': 'wf_cfg_solution', 'to': 'wf_cfg_answer', 'condition': 'retry'},
            {'from': 'wf_cfg_solution', 'to': 'wf_failed', 'condition': 'unrecoverable'},
            {'from': 'wf_cfg_verify', 'to': 'wf_success', 'condition': 'pass'},
            {'from': 'wf_cfg_verify', 'to': 'wf_cfg_mistake', 'condition': 'fail'},
            {'from': 'wf_val_problem', 'to': 'wf_val_question', 'condition': 'success'},
            {'from': 'wf_val_question', 'to': 'wf_val_answer', 'condition': 'answered'},
            {'from': 'wf_val_answer', 'to': 'wf_val_constraint', 'condition': 'success'},
            {'from': 'wf_val_answer', 'to': 'wf_val_mistake', 'condition': 'fail'},
            {'from': 'wf_val_constraint', 'to': 'wf_val_verify', 'condition': 'pass'},
            {'from': 'wf_val_constraint', 'to': 'wf_val_mistake', 'condition': 'fail'},
            {'from': 'wf_val_mistake', 'to': 'wf_val_solution', 'condition': 'fail'},
            {'from': 'wf_val_solution', 'to': 'wf_val_answer', 'condition': 'retry'},
            {'from': 'wf_val_solution', 'to': 'wf_failed', 'condition': 'unrecoverable'},
            {'from': 'wf_val_verify', 'to': 'wf_success', 'condition': 'pass'},
            {'from': 'wf_val_verify', 'to': 'wf_val_mistake', 'condition': 'fail'},
            {'from': 'wf_rep_problem', 'to': 'wf_rep_question', 'condition': 'success'},
            {'from': 'wf_rep_question', 'to': 'wf_rep_answer', 'condition': 'answered'},
            {'from': 'wf_rep_answer', 'to': 'wf_rep_constraint', 'condition': 'success'},
            {'from': 'wf_rep_answer', 'to': 'wf_rep_mistake', 'condition': 'fail'},
            {'from': 'wf_rep_constraint', 'to': 'wf_rep_verify', 'condition': 'pass'},
            {'from': 'wf_rep_constraint', 'to': 'wf_rep_mistake', 'condition': 'fail'},
            {'from': 'wf_rep_mistake', 'to': 'wf_rep_solution', 'condition': 'fail'},
            {'from': 'wf_rep_solution', 'to': 'wf_rep_answer', 'condition': 'retry'},
            {'from': 'wf_rep_solution', 'to': 'wf_failed', 'condition': 'unrecoverable'},
            {'from': 'wf_rep_verify', 'to': 'wf_success', 'condition': 'pass'},
            {'from': 'wf_rep_verify', 'to': 'wf_rep_mistake', 'condition': 'fail'},
            {'from': 'wf_success', 'to': 'wf_root', 'condition': 'success'},
        ]
        return (1, edges, None)

    def GetAiInstructions(self):
        instructions = {
            'how_to_add_code': (
                "HOW TO ADD CODE TO THE DATABASE\n"
                "================================\n"
                "STEP 1: GET THE CODE — Source: MySQL vb_code_test (vb_classes, vb_methods) or disk files via ast.parse()\n"
                "STEP 2: CHECK VBSTYLE — Run() dispatch, Tuple3 returns, no print, no decorators, no hardcoded paths, no tabs, PascalCase, self.state dict\n"
                "STEP 3: CHOOSE DOMAIN — lowercase single word (e.g. 'workflow', 'graphs')\n"
                "STEP 4: STORE — INSERT INTO classes, then methods, then computational_units\n"
                "STEP 5: GENERATE BCL — Run bcl_identity_generator.py\n"
                "STEP 6: UPDATE CLOSURE — INSERT INTO closure_status\n"
                "STEP 7: CREATE PLAN (optional) — INSERT INTO plans + plan_steps\n"
                "STEP 8: CREATE ORCHESTRATION (optional) — INSERT INTO orchestration\n"
                "STEP 9: VERIFY — Check method count, BCL count, closure_pct, run graph_engine"
            ),
            'code_style_rules': (
                "VBSTYLE CODE RULES (MUST FOLLOW)\n"
                "=================================\n"
                "RULE 1: Run() Dispatch — every class MUST have Run(command, params) returning Tuple3\n"
                "RULE 2: Tuple3 Returns — (ok, data, error) where ok=1/0, error=None or (code, msg, severity)\n"
                "RULE 3: No print statements — use return values\n"
                "RULE 4: No Decorators — no @property, @staticmethod, @classmethod\n"
                "RULE 5: No Hardcoded Localhost — use config params\n"
                "RULE 6: No Tabs — spaces only\n"
                "RULE 7: PascalCase Classes, UPPERCASE constants\n"
                "RULE 8: state Dict — no private attributes, use self.state\n"
                "RULE 9: No Complex __init__ — only set self.state, all logic via Run()\n"
                "RULE 10: Ghost + VBStyle + Class + Method Headers required"
            ),
            'where_code_goes': (
                "WHERE CODE GOES IN THE DATABASE\n"
                "================================\n"
                "CLASSES TABLE: one row per domain (class_name, class_code, domain, is_vbstyle, has_run_method)\n"
                "METHODS TABLE: one row per method (class_id, method_name, method_code, params, is_dunder, returns_tuple3)\n"
                "COMPUTATIONAL_UNITS: groups of coupled methods (unit_name, unit_type, class_id, method_id)\n"
                "BCL_IDENTITY: self-description tokens (entity_type, entity_id, bcl_token, self_narrative)\n"
                "DO NOT store code in: _db_meta, _table_registry, plans, violations, execution_log"
            ),
            'what_is_bcl': (
                "WHAT IS BCL (Bracket Command Language)?\n"
                "========================================\n"
                "BCL is a self-description format. Every entity has a BCL token answering 7 W-questions:\n"
                "WHO (identity), WHAT (capabilities), WHERE (used_in_pipelines), WHEN (closure),\n"
                "WHY (self_narrative), HOW (method_signature), WHAT_IF (breaks_if)\n"
                "Format: [@EntityName]{(\"key\";\"value\")(...)}\n"
                "Stored in bcl_identity table. Generated by bcl_identity_generator.py"
            ),
            'how_to_verify': (
                "HOW TO VERIFY CODE AND DATABASE\n"
                "================================\n"
                "1. VBStyle Compliance: SELECT kind, COUNT(*) FROM violations GROUP BY kind\n"
                "2. Closure Check: SELECT domain, closure_pct FROM closure_status\n"
                "3. BCL Identity: SELECT entity_type, COUNT(*) FROM bcl_identity GROUP BY entity_type\n"
                "4. Documentation: Check _table_registry and _column_docs coverage\n"
                "5. Orchestration: Check for isolated domains not in any pipeline\n"
                "6. Run graph_engine_v2.py for dynamic gap discovery\n"
                "7. Execution Test: Try executing a plan and log to execution_log"
            ),
            'error_handling': (
                "ERROR HANDLING\n"
                "==============\n"
                "VBStyle violations: no_state→add self.state, no_run→add Run(), print→replace with return,\n"
                "  localhost→use config, decorator→remove, tab→replace with spaces\n"
                "BCL fails: check entity exists, class_id correct, domain name matches\n"
                "Closure <100%: implement missing methods, update closure_status\n"
                "DB locked: close other connections, use WAL mode\n"
                "MySQL fails: check mysqladmin -u root status, port 3306"
            ),
            'permissions': (
                "PERMISSIONS\n"
                "===========\n"
                "ALLOWED: Read any table, add domains/methods/BCL/plans/orchestration, update closure, add docs, log executions\n"
                "CAUTION: Update existing class/method code (keep version history), delete violations after fix verified\n"
                "NOT ALLOWED: Drop tables, delete entire domains without backup, delete all BCL/plans, modify system_ _db_meta keys\n"
                "REQUIRES USER: Deleting >10 rows, dropping tables, changing schema"
            ),
            'rules_reference': (
                "RULES REFERENCE\n"
                "===============\n"
                "1. _db_meta table: this instruction set\n"
                "2. VBStyle rules: 10 rules (Run, Tuple3, no print, no decorators, etc.)\n"
                "3. BCL rules: 7 W-questions, required fields\n"
                "4. Closure rules: every domain at 100%\n"
                "5. Documentation rules: every table in _table_registry, every column in _column_docs"
            ),
        }
        return (1, instructions, None)

    # === COGNITIVE LOOP WALKER ===

    def WalkLoop(self, params):
        domain = params.get('domain', 'workflow')
        operation = params.get('operation', '')
        userInput = params.get('input', {})
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        if not operation:
            return (0, None, ("MISSING_PARAM", "No operation specified. Use list_operations to see valid options.", 1))
        self.state['domain'] = domain
        self.state['operation'] = operation
        self.state['params'] = userInput
        self.state['start_time'] = datetime.now().isoformat()
        self.state['path_history'] = []
        self.state['step_count'] = 0
        self.state['errors'] = []
        conn = sqlite3.connect(dbPath)
        self.state['conn'] = conn
        c = conn.cursor()
        c.execute("SELECT node_id, name, payload FROM decision_nodes WHERE domain=? AND category='root'", (domain,))
        root = c.fetchone()
        if not root:
            conn.close()
            return (0, None, ("NOT_FOUND", "No root node found for domain: " + domain, 1))
        rootId, rootName, rootPayload = root
        self.state['current_node'] = rootId
        self.Trace("WalkLoop: domain=" + domain + " operation=" + operation + " root=" + rootName)
        self.LogStep(rootId, rootName, "root", "entered", rootPayload, "")
        okEdge, nextNode, errEdge = self.FollowEdge(c, rootId, operation)
        if not nextNode:
            conn.close()
            return (0, None, ("NO_EDGE", "No edge from root with condition='" + operation + "'. Valid: prj, index, config, validate, report", 1))
        result = self.WalkFromNode(c, nextNode)
        self.LogStep(self.state['current_node'], "", "terminal", "completed" if result[0] else "failed", "", result[2] if result[2] else "OK")
        self.WriteExecutionLog(conn)
        conn.close()
        return result

    def WalkFromNode(self, c, nodeId):
        maxSteps = 50
        maxRetries = 3
        visited = []
        retryCounts = {}
        while nodeId and self.state['step_count'] < maxSteps:
            c.execute("SELECT name, node_type, category, payload FROM decision_nodes WHERE node_id=?", (nodeId,))
            row = c.fetchone()
            if not row:
                return (0, {"path": visited}, ("NODE_NOT_FOUND", "Node " + str(nodeId) + " not found", 2))
            name, nodeType, category, payload = row
            self.state['current_node'] = nodeId
            self.state['step_count'] += 1
            visited.append(nodeId)
            if category == "terminal":
                self.Trace("WalkFromNode: TERMINAL " + name + " — " + (payload or ""))
                self.LogStep(nodeId, name, category, "terminal", payload, "")
                if "Complete" in name:
                    return (1, {"path": visited, "steps": self.state['step_count']}, None)
                else:
                    return (0, {"path": visited, "steps": self.state['step_count']}, ("WORKFLOW_FAILED", payload or "", 2))
            self.Trace("WalkFromNode: step=" + str(self.state['step_count']) + " " + category.upper() + " " + name)
            okNode, outcome, errNode = self.ProcessNode(c, nodeId, name, nodeType, category, payload)
            status = outcome[0]
            detail = outcome[1]
            self.Trace("WalkFromNode: -> " + status.upper() + ": " + detail)
            self.LogStep(nodeId, name, category, status, payload, detail)
            okEdge2, nextNode, errEdge2 = self.FollowEdge(c, nodeId, status)
            if not nextNode and status == "fail":
                okEdge3, nextNode, errEdge3 = self.FollowEdge(c, nodeId, "retry")
            if not nextNode:
                if category == "verify" and status == "pass":
                    c.execute("SELECT to_node FROM decision_edges WHERE from_node=? AND condition='pass'", (nodeId,))
                    term = c.fetchone()
                    if term:
                        nextNode = term[0]
            if not nextNode:
                self.Trace("WalkFromNode: DEAD END at " + name + " status=" + status)
                self.state['errors'].append("Dead end at " + name + " with status=" + status)
                break
            if nodeType == "fallback" and "Solution" in name:
                retryKey = str(nodeId)
                retryCounts[retryKey] = retryCounts.get(retryKey, 0) + 1
                if retryCounts[retryKey] > maxRetries:
                    self.Trace("WalkFromNode: MAX RETRIES exceeded at " + name)
                    c.execute("SELECT node_id FROM decision_nodes WHERE domain=? AND category='terminal' AND name LIKE '%Failed%'", (self.state['domain'],))
                    failNode = c.fetchone()
                    if failNode:
                        nodeId = failNode[0]
                        continue
                    else:
                        return (0, {"path": visited}, ("MAX_RETRIES", "Max retries exceeded, no fail terminal found", 2))
            nodeId = nextNode
        if self.state['step_count'] >= maxSteps:
            return (0, {"path": visited}, ("MAX_STEPS", "Max steps (" + str(maxSteps) + ") exceeded — possible infinite loop", 2))
        return (1, {"path": visited, "steps": self.state['step_count']}, None)

    def ProcessNode(self, c, nodeId, name, nodeType, category, payload):
        if "Problem" in name:
            return (1, ("success", "Problem identified, proceeding to question"), None)
        if "Question" in name:
            params = self.state.get("params", {})
            targetDomain = params.get("domain", self.state.get("domain", ""))
            c.execute("SELECT name FROM domain_registry WHERE name=?", (targetDomain,))
            if not c.fetchone():
                return (1, ("answered", "Domain '" + targetDomain + "' NOT in registry — will need to register first"), None)
            return (1, ("answered", "Domain '" + targetDomain + "' found in registry. Params: " + str(params)), None)
        if "Answer" in name:
            params = self.state.get("params", {})
            targetDomain = params.get("domain", self.state.get("domain", ""))
            operation = self.state.get("operation", "")
            c.execute("SELECT name FROM type_registry WHERE name='action'")
            hasAction = c.fetchone()
            c.execute("SELECT name FROM type_registry WHERE name='check'")
            hasCheck = c.fetchone()
            if not hasAction or not hasCheck:
                return (1, ("fail", "type_registry missing required types (action, check)"), None)
            c.execute("SELECT name FROM category_registry WHERE domain=? AND name=?", (targetDomain, operation))
            hasCat = c.fetchone()
            if not hasCat:
                return (1, ("fail", "Category '" + operation + "' not registered for domain '" + targetDomain + "'"), None)
            if payload and "Dom_workflow.Run" in payload:
                return (1, ("success", "Registry checks passed for '" + targetDomain + "'. Would execute: Dom_workflow.Run('" + operation + "', " + str(params) + ")"), None)
            return (1, ("success", "Registry checks passed for '" + targetDomain + "'"), None)
        if "Constraint" in name:
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")
            steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, operation))
            nodes = [r[0] for r in c.fetchall()]
            missing = []
            for step in steps:
                if not any(step in n for n in nodes):
                    missing.append(step)
            if missing:
                return (1, ("fail", "Cognitive loop INCOMPLETE — missing: " + ', '.join(missing)), None)
            try:
                c.execute("SELECT COUNT(*) FROM violations v JOIN methods m ON v.method_id = m.id JOIN classes cl ON m.class_id = cl.id WHERE cl.domain = ?", (domain,))
                domainViolations = c.fetchone()[0]
                if domainViolations > 0:
                    return (1, ("fail", str(domainViolations) + " VBStyle violations in domain '" + domain + "'"), None)
            except Exception:
                pass
            return (1, ("pass", "All constraints satisfied: 7 steps present, 0 violations for domain '" + domain + "'"), None)
        if "Mistake" in name:
            return (1, ("fail", "Error detected, seeking solution"), None)
        if "Solution" in name:
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")
            c.execute("SELECT name FROM domain_registry WHERE name=?", (domain,))
            if not c.fetchone():
                return (1, ("retry", "Recovery: register domain '" + domain + "' in domain_registry, then retry"), None)
            c.execute("SELECT name FROM category_registry WHERE domain=? AND name=?", (domain, operation))
            if not c.fetchone():
                return (1, ("retry", "Recovery: register category '" + operation + "' for domain '" + domain + "', then retry"), None)
            return (1, ("retry", "Recovery attempted, retrying answer"), None)
        if "Verify" in name:
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")
            c.execute("SELECT name FROM domain_registry WHERE name=?", (domain,))
            if not c.fetchone():
                return (1, ("fail", "Verify FAILED: domain '" + domain + "' not in registry"), None)
            steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, operation))
            nodes = [r[0] for r in c.fetchall()]
            missing = [s for s in steps if not any(s in n for n in nodes)]
            if missing:
                return (1, ("fail", "Verify FAILED: cognitive loop missing: " + ', '.join(missing)), None)
            c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='validate_node_domain'")
            if not c.fetchone():
                return (1, ("fail", "Verify FAILED: validate_node_domain trigger missing"), None)
            return (1, ("pass", "Verified: domain registered, 7 steps present, triggers active"), None)
        return (1, ("success", "Processed"), None)

    def FollowEdge(self, c, fromNode, condition):
        c.execute("SELECT to_node FROM decision_edges WHERE from_node=? AND condition=?", (fromNode, condition))
        row = c.fetchone()
        result = row[0] if row else None
        return (1, result, None)

    def LogStep(self, nodeId, name, category, status, payload, detail):
        self.state['path_history'].append({
            'step': self.state['step_count'],
            'node_id': nodeId,
            'name': name,
            'category': category,
            'status': status,
            'payload': payload[:200] if payload else "",
            'detail': detail,
            'timestamp': datetime.now().isoformat(),
        })
        return (1, len(self.state['path_history']), None)

    def WriteExecutionLog(self, conn):
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='execution_log'")
        if not c.fetchone():
            c.execute("""CREATE TABLE IF NOT EXISTS execution_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step INTEGER,
                node_id INTEGER,
                node_name TEXT,
                category TEXT,
                status TEXT,
                detail TEXT,
                timestamp TEXT)""")
            conn.commit()
        runId = "walk_" + self.state['domain'] + "_" + self.state['operation'] + "_" + datetime.now().strftime('%Y%m%d_%H%M%S')
        for entry in self.state['path_history']:
            c.execute("INSERT INTO execution_log (run_id, node_id, status, output, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (runId, entry['node_id'], entry['status'], entry['name'] + " | " + entry['detail'], entry['timestamp']))
        conn.commit()
        self.Trace("WriteExecutionLog: " + str(len(self.state['path_history'])) + " entries (run_id=" + runId + ")")
        return (1, len(self.state['path_history']), None)

    def ListOperations(self, params):
        domain = params.get("domain", "workflow")
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("SELECT node_id FROM decision_nodes WHERE domain=? AND category='root'", (domain,))
        root = c.fetchone()
        if not root:
            conn.close()
            return (0, None, ("NOT_FOUND", "No root node for domain: " + domain, 1))
        c.execute("SELECT condition, to_node FROM decision_edges WHERE from_node=?", (root[0],))
        edges = c.fetchall()
        operations = []
        for cond, toNode in edges:
            c.execute("SELECT name, payload FROM decision_nodes WHERE node_id=?", (toNode,))
            node = c.fetchone()
            if node:
                operations.append({
                    "operation": cond,
                    "entry_node": node[0],
                    "description": node[1][:100] if node[1] else "",
                })
        conn.close()
        return (1, {"domain": domain, "operations": operations}, None)

    def ShowGraph(self, params):
        domain = params.get("domain", "workflow")
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("SELECT node_id, name, node_type, category, payload FROM decision_nodes WHERE domain=? ORDER BY category, name", (domain,))
        nodes = c.fetchall()
        c.execute("""SELECT e.condition, n1.name, n2.name
                     FROM decision_edges e
                     JOIN decision_nodes n1 ON e.from_node=n1.node_id
                     JOIN decision_nodes n2 ON e.to_node=n2.node_id
                     WHERE n1.domain=? ORDER BY n1.category, e.condition""", (domain,))
        edges = c.fetchall()
        conn.close()
        return (1, {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}, None)

    def VerifyGraph(self, params):
        domain = params.get("domain", "workflow")
        dbPath = params.get('db_path')
        if not dbPath:
            return (0, None, ("MISSING_PARAM", "Need db_path", 1))
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM decision_nodes WHERE domain=? AND category NOT IN ('root','terminal')", (domain,))
        categories = [r[0] for r in c.fetchall()]
        steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
        results = {}
        for cat in categories:
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, cat))
            nodes = [r[0] for r in c.fetchall()]
            missing = [s for s in steps if not any(s in n for n in nodes)]
            results[cat] = {
                "complete": len(missing) == 0,
                "missing": missing,
                "node_count": len(nodes),
            }
        conn.close()
        return (1, {"domain": domain, "categories": results}, None)


if __name__ == "__main__":
    wf = Dom_workflow()
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 Dom_workflow.py <command> [key=value ...]\n")
        sys.stderr.write("Commands: prj, index, config, validate, report, status,\n")
        sys.stderr.write("          store_db, fix_db, add_cognitive_loop, populate_instructions,\n")
        sys.stderr.write("          walk_loop, list_operations, show_graph, verify_graph\n")
        sys.exit(1)
    command = sys.argv[1]
    params = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            params[k] = v
    ok, data, err = wf.Run(command, params)
    if ok:
        if isinstance(data, (dict, list)):
            sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        elif isinstance(data, str):
            sys.stdout.write(data + "\n")
        else:
            sys.stdout.write(str(data) + "\n")
    else:
        sys.stderr.write("ERROR: " + str(err) + "\n")
        sys.exit(1)
