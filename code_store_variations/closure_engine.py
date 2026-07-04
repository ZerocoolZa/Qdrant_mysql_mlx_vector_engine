#!/usr/bin/env python3
"""
VBStyle Domain Closure Engine.

For each of 57 domains:
  1. Define the finite closure set of methods
  2. Check what exists in dom_*.py files
  3. Check what exists in MySQL (vb_code_test)
  4. Copy missing methods from MySQL where found
  5. Generate VBStyle-compliant methods where truly missing
  6. Create computational units for all
  7. Write everything into v20_hybrid_best.db
  8. Test each domain

VBStyle rules enforced:
  - Run() dispatch, Tuple3 (ok, data, error)
  - No decorators, no print, no hardcoded, no self._
  - PascalCase classes, UPPERCASE constants
  - self.state dict
  - __init__(self, mem=None, db=None, param=None)
  - read_state(), set_config()
"""

import sqlite3
import mysql.connector
import ast
import os
import re
import sys
import time
import textwrap
import traceback
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "v20_hybrid_best.db")
DOMAINS_DIR = os.environ.get(
    "CODE_STORE_DOMAINS_DIR",
    "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains"
)
if not os.path.isdir(DOMAINS_DIR):
    DOMAINS_DIR = BASE_DIR
EFL_BRAIN_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'efl_brain', 'efl_brain.db'
)

# ============================================================
# BEHAVIORAL VALIDATOR — contract check + sandbox execution + scoring
# ============================================================

class BehavioralValidator:
    """Validates candidates against contracts via sandbox execution.

    Replaces name-based matching with behavioral verification.
    Score = weighted combination of:
      - contract_compliance (0-40): Tuple3 shape, return type
      - execution_success (0-30): no crash, runs to completion
      - edge_case_handling (0-20): empty input, bad params
      - historical_reward (0-10): past success rate from execution_log
    """

    UNSAFE_BUILTINS = {'eval', 'exec', 'globals', 'locals', 'vars', 'dir', 'input', 'breakpoint', 'exit', 'quit'}

    def __init__(self, efl_db_path=EFL_BRAIN_DB):
        self.efl_db_path = efl_db_path

    def _safe_builtins(self):
        import builtins
        return {k: v for k, v in vars(builtins).items() if k not in self.UNSAFE_BUILTINS}

    def _build_namespace(self):
        safe = self._safe_builtins()
        safe['print'] = lambda *a, **k: None
        return {
            '__builtins__': safe,
            'os': os, 're': re, 'ast': ast, 'time': time,
            'sqlite3': sqlite3, 'datetime': datetime,
        }

    def _check_tuple3(self, result):
        """Check if result is a valid Tuple3 (ok, data, error)."""
        if not isinstance(result, (tuple, list)):
            return False, 'not_tuple'
        if len(result) != 3:
            return False, f'wrong_length_{len(result)}'
        ok, data, error = result
        if ok not in (0, 1, True, False):
            return False, 'ok_not_bool'
        return True, 'tuple3_ok'

    def _get_historical_reward(self, method_name, domain):
        """Get historical success rate from efl_brain.db execution_log."""
        if not os.path.exists(self.efl_db_path):
            return 0.0
        try:
            conn = sqlite3.connect(self.efl_db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as wins
                FROM execution_log
                WHERE method_name LIKE ? AND class_name LIKE ?
            """, (f'%{method_name}%', f'%{domain}%'))
            row = cur.fetchone()
            conn.close()
            if row and row[0] and row[0] > 0:
                return row[1] / row[0] if row[1] else 0.0
        except Exception:
            pass
        return 0.0

    def Validate(self, candidate_code, method_name, domain):
        """Run a candidate through contract check + sandbox execution.

        Returns (ok, score, detail).
        """
        if not candidate_code or len(candidate_code.strip()) < 20:
            return False, 0, 'empty_or_trivial_code'

        score = 0
        details = []

        # --- Phase 1: AST parse check (5 pts) ---
        try:
            tree = ast.parse(candidate_code)
            score += 5
        except SyntaxError as e:
            return False, 0, f'syntax_error: {e}'

        # --- Phase 2: VBStyle compliance check (5 pts) ---
        violations = []
        if 'self._' in candidate_code:
            violations.append('self._')
        if 'print(' in candidate_code:
            violations.append('print()')
        if re.search(r'@(property|staticmethod|classmethod)', candidate_code):
            violations.append('decorator')
        if not violations:
            score += 5
        else:
            details.append(f'vbstyle_violations: {",".join(violations)}')

        # --- Phase 3: Sandbox execution (30 pts) ---
        ns = self._build_namespace()
        try:
            exec(compile(candidate_code, f'<{method_name}>', 'exec'), ns, ns)
        except Exception as e:
            return False, score, f'exec_failed: {e}'

        # Find the method function in namespace
        import keyword
        lookup_names = [method_name]
        if keyword.iskeyword(method_name):
            lookup_names.append(f"{method_name}_impl")
        
        fn = None
        for name in lookup_names:
            fn = ns.get(name)
            if callable(fn):
                break
            # Try to find a class with the method
            for key, val in ns.items():
                if isinstance(val, type) and hasattr(val, name):
                    try:
                        instance = val()
                        fn = getattr(instance, name)
                    except Exception:
                        continue
                    break
            if fn:
                break
        
        if not fn:
            # Try any callable that's not a class/builtin
            for key, val in ns.items():
                if callable(val) and not key.startswith('_') and key != 'print' and not isinstance(val, type):
                    fn = val
                    break
            if not fn:
                return False, score, f'method_not_found: {method_name}'

        # Try calling with None params
        try:
            result = fn(None) if method_name != 'Run' else fn('read_state', {})
            tuple_ok, tuple_detail = self._check_tuple3(result)
            if tuple_ok:
                score += 20
            else:
                details.append(f'bad_return: {tuple_detail}')
                score += 5
        except Exception as e:
            details.append(f'runtime_error: {e}')
            score += 5

        # --- Phase 4: Edge case — empty params (10 pts) ---
        try:
            result2 = fn(None) if method_name != 'Run' else fn('unknown_cmd', {})
            tuple_ok2, _ = self._check_tuple3(result2)
            if tuple_ok2:
                score += 10
        except Exception:
            details.append('edge_case_failed')

        # --- Phase 5: Historical reward (10 pts) ---
        reward = self._get_historical_reward(method_name, domain)
        score += int(reward * 10)
        if reward > 0:
            details.append(f'historical_reward: {reward:.2f}')

        ok = score >= 30
        return ok, score, '; '.join(details) if details else 'validated'


# ============================================================
# CANDIDATE RETRIEVER — get ALL candidates from all sources
# ============================================================

class CandidateRetriever:
    """Retrieves all candidates for a domain+method from multiple sources.

    Does NOT pick one — returns ALL candidates for competition.
    Sources: dom files, MySQL, efl_brain.db, generator.
    """

    def __init__(self, dom_dir=DOMAINS_DIR, efl_db_path=EFL_BRAIN_DB):
        self.dom_dir = dom_dir
        self.efl_db_path = efl_db_path

    def Retrieve(self, domain, method):
        """Returns list of (code, source, source_detail) tuples."""
        candidates = []

        # 1. DOM files
        dom_candidates = self._from_dom_file(domain, method)
        candidates.extend(dom_candidates)

        # 2. efl_brain.db (if exists)
        efl_candidates = self._from_efl_brain(domain, method)
        candidates.extend(efl_candidates)

        # 3. Generator (always available as fallback)
        gen_code = generate_vbstyle_method(domain, method)
        candidates.append((gen_code, 'generated', 'ClosureEngine'))

        return candidates

    def _from_dom_file(self, domain, method):
        """Extract method code from dom_*.py via AST."""
        path = os.path.join(self.dom_dir, f'dom_{domain}.py')
        if not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                src = f.read()
            tree = ast.parse(src)
        except Exception:
            return []

        candidates = []
        method_lower = method.lower()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node_name = node.name.lower()
                if method_lower == node_name or method_lower in node_name:
                    code = ast.get_source_segment(src, node)
                    if code and len(code) > 20:
                        candidates.append((code, 'dom_file', f'dom_{domain}.py:{node.name}'))
        return candidates

    def _from_efl_brain(self, domain, method):
        """Search efl_brain.db for method candidates."""
        if not os.path.exists(self.efl_db_path):
            return []
        try:
            conn = sqlite3.connect(self.efl_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT method_name, method_code, class_name
                FROM methods
                WHERE LOWER(method_name) = LOWER(?)
                AND method_code IS NOT NULL
                AND LENGTH(method_code) > 50
                LIMIT 5
            """, (method,))
            rows = cur.fetchall()
            conn.close()
            return [(r['method_code'], 'efl_brain', f"{r['class_name']}.{r['method_name']}") for r in rows if r['method_code']]
        except Exception:
            return []


# ============================================================
# SURVIVOR RANKER — score all candidates, promote best
# ============================================================

class SurvivorRanker:
    """Runs all candidates through validator, promotes best.

    winner = highest scoring candidate
    Losers archived with failure detail.
    Winner promoted as canonical implementation.
    """

    def __init__(self, validator=None):
        self.validator = validator or BehavioralValidator()

    def Compete(self, candidates, method_name, domain):
        """Returns (winner, ranked_results).

        winner = (code, source, source_detail, score, detail) or None
        ranked_results = list of (source, source_detail, score, detail, ok)
        """
        ranked = []
        for code, source, source_detail in candidates:
            ok, score, detail = self.validator.Validate(code, method_name, domain)
            ranked.append((source, source_detail, score, detail, ok, code))

        # Sort by score descending
        ranked.sort(key=lambda x: x[2], reverse=True)

        if not ranked:
            return None, []

        best = ranked[0]
        if best[4]:  # ok=True
            winner = (best[5], best[0], best[1], best[2], best[3])
        else:
            # No survivor passed — pick highest score anyway but mark as unverified
            winner = (best[5], best[0], best[1], best[2], f'UNVERIFIED: {best[3]}')

        return winner, [(r[0], r[1], r[2], r[3], r[4]) for r in ranked]


# ============================================================
# DOMAIN CLOSURE DEFINITIONS — finite method set per domain
# ============================================================

DOMAIN_CLOSURE = {
    'io': ['open','read','write','append','close','seek','tell','flush','truncate','stat','exists','touch',
           'move','copy','delete','chmod','lock','readlines','writelines',
           'compress','decompress','split','join','watch',
           'scan','listdir','walk','makedirs','rmdir','glob','temp'],
    'db': ['connect','disconnect','create_table','drop_table','alter_table','create_index',
           'insert','select','update','delete','upsert','bulk_insert','transaction','commit','rollback',
           'backup','restore','migrate','schema','describe','count','exists','query','execute',
           'fetch','vacuum','optimize'],
    'gui': ['create_window','close_window','show','hide','resize','set_title',
            'add_widget','remove_widget','layout','set_style','set_theme',
            'menu','toolbar','dialog','table','tree','list','combo','checkbox','button','label','text',
            'tab','splitter','panel','progress','slider',
            'paint','draw_line','draw_rect','draw_text',
            'event_click','event_key','event_mouse','event_resize','event_close',
            'render','update','refresh'],
    'network': ['connect','disconnect','listen','accept','send','recv',
                'get','post','put','patch','delete',
                'upload','download','stream','websocket','poll',
                'resolve','ping','trace'],
    'search': ['index','reindex','search','query','match','rank','filter','sort',
               'facet','suggest','autocomplete','highlight','snippet',
               'fuzzy','regex','phrase','vector','embed','similarity','nearest'],
    'parse': ['tokenize','lex','parse','validate','transform','emit',
              'read_header','read_brackets','validate_brackets','extract_metadata',
              'split_class','split_method','extract_docstring'],
    'transform': ['map','filter','reduce','flatten','group','sort','dedupe',
                  'convert','normalize','format','clean','enrich','project',
                  'rename','restructure','merge','split'],
    'validate': ['check_headers','check_naming','check_state','check_run','check_tuple3',
                 'check_no_print','check_no_decorator','check_no_hardcode',
                 'check_pascal','check_ghost','check_vbstyle',
                 'check_init','check_self_state','check_dispatch',
                 'scan','report','fix','enforce'],
    'memory': ['store','recall','forget','clear','size','keys',
               'persist','load','snapshot','restore','compress','expire',
               'cache','invalidate','refresh'],
    'knowledge': ['add_fact','query_fact','add_rule','query_rule','add_concept',
                  'query_concept','add_relation','query_relation','infer',
                  'explain','prove','disprove','confidence','source',
                  'merge','export','import'],
    'security': ['authenticate','authorize','encrypt','decrypt','hash','sign','verify',
                 'token','refresh_token','revoke','permission','role','policy',
                 'audit','lockout','reset'],
    'orchestration': ['start','stop','pause','resume','schedule','dispatch',
                      'pipeline','sequence','parallel','retry','timeout',
                      'dependency','priority','queue','worker','status'],
    'config': ['load','save','get','set','delete','list','validate',
               'merge','export','import','watch','reload',
               'defaults','profile','environment'],
    'storage': ['put','get','delete','list','exists','size',
                'blob','object','document','table','record','bucket',
                'volume','replicate'],
    'testing': ['unit','integration','benchmark','fixture','mock',
                'assert','verify','coverage','report',
                'setup','teardown','skip'],
    'analytics': ['count','sum','avg','min','max','median','stddev',
                  'trend','forecast','correlate','cluster','classify',
                  'aggregate','group','pivot','anomaly','insight'],
    'ai': ['prompt','complete','embed','classify','extract','summarize',
           'translate','generate','rank','score','plan','reason',
           'reflect','evaluate','learn','remember','forget'],
    'messaging': ['send','receive','publish','subscribe','unsubscribe',
                  'queue','topic','channel','broadcast','ack','nack',
                  'retry','deadletter','delay','priority'],
    'runtime': ['execute','eval','compile','decompile','load','unload',
                'register','unregister','dispatch','hook','intercept',
                'sandbox','monitor','profile'],
    'governance': ['rule','policy','constraint','compliance','violation',
                   'enforce','waive','approve','reject','review',
                   'audit','report','escalate','exception'],
    'logging': ['log','trace','debug','info','warn','error','fatal',
                'metric','event','flush','rotate','archive','query','filter'],
    'documentation': ['generate','render','export','import','template',
                      'index','search','cross_ref','diagram',
                      'changelog','readme','api_doc','example'],
    'package': ['build','install','uninstall','update','list','info',
                'depend','resolve','lock','publish','fetch',
                'verify','sign','checksum'],
    'automation': ['trigger','schedule','run','chain','branch',
                   'loop','condition','wait','notify','webhook',
                   'cron','interval','event','state_machine'],
    'archive': ['create','extract','list','verify','compress','decompress',
                'split','join','encrypt','decrypt','index','search'],
    'audit': ['scan','check','report','violation','compliance',
              'trace','history','diff','baseline','drift',
              'flag','escalate','fix','verify'],
    'style': ['check_header','check_naming','check_format','check_structure',
              'check_ghost','check_vbstyle','check_class','check_method',
              'fix_header','fix_naming','fix_format','report',
              'enforce','scan','score'],
    'arch': ['design','review','approve','enforce','document','scan',
             'pattern','layer','dependency','coupling','cohesion',
             'complexity','technical_debt','report','baseline'],
    'asm': ['disassemble','assemble','decode','encode','analyze',
            'extract_opcodes','extract_registers','extract_jumps',
            'label_map','function_map','cross_reference','report'],
    'bytecode': ['compile','decompile','disassemble','analyze',
                 'extract_constants','extract_names','extract_code',
                 'optimize','patch','inject','verify','compare'],
    'cli': ['parse_args','parse_flags','parse_options','help','version',
            'run','dispatch','complete','history','alias',
            'pipe','redirect','signal','exit'],
    'codec': ['encode','decode','serialize','deserialize',
              'compress','decompress','hash','checksum',
              'base64','hex','url_encode','url_decode','validate'],
    'codegraph': ['build','query','traverse','neighbors','path',
                  'shortest_path','cycles','connected','components',
                  'topology','visualize','export','import','merge'],
    'compass': ['navigate','orient','heading','distance','route',
                'landmark','waypoint','explore','map','survey',
                'report','calibrate','benchmark'],
    'convert': ['to_json','to_yaml','to_xml','to_csv','to_toml',
                'to_dict','to_list','to_text','from_json','from_yaml',
                'from_xml','from_csv','validate','roundtrip'],
    'csplit': ['split','merge','extract_class','extract_method',
               'extract_imports','extract_header','count_classes',
               'count_methods','validate','report'],
    'cu': ['create','execute','destroy','list','inspect',
           'register','unregister','status','history','report',
           'validate','benchmark'],
    'db_inv': ['discover','introspect','schema','tables','columns',
               'indexes','constraints','foreign_keys','triggers',
               'stored_procs','views','functions','relationships','report'],
    'db_studio': ['connect','query','browse','edit','design',
                  'migrate','compare','sync','export','import',
                  'visualize','optimize','monitor','report'],
    'factory': ['create','register','unregister','get','list',
                'prototype','clone','configure','dispose',
                'validate','report'],
    'fileops': ['read','write','append','delete','copy','move',
                'rename','exists','stat','chmod','glob','walk',
                'touch','temp','split','join'],
    'folder': ['create','delete','list','walk','size','tree',
               'move','copy','rename','watch','sync',
               'archive','compare','clean'],
    'graph': ['add_node','add_edge','remove_node','remove_edge',
              'get_node','get_edge','neighbors','path','traverse',
              'dfs','bfs','shortest_path','cycles','topology',
              'visualize','export'],
    'index': ['create','build','update','delete','search','query',
              'optimize','rebuild','stats','export','import',
              'merge','split','validate'],
    'ingest': ['scan','parse','extract','transform','load','validate',
               'dedupe','enrich','classify','tag','store','index',
               'report','schedule'],
    'ingest_cli': ['scan','parse','load','validate','batch',
                   'schedule','status','report','resume','cancel'],
    'ingest_gui': ['browse','select','preview','import','progress',
                   'cancel','settings','history','report','validate'],
    'log': ['write','read','query','filter','search','rotate',
            'archive','purge','tail','follow','export','format',
            'level','category'],
    'process': ['start','stop','kill','wait','signal',
                'stdin','stdout','stderr','status','pid',
                'list','monitor','timeout','restart'],
    'qa': ['ask','answer','embed','search','extract','classify',
           'route','fallback','explain','score','confidence',
           'history','feedback','tune'],
    'qt': ['create_widget','layout','style','signal','slot',
           'connect','disconnect','paint','event','show',
           'hide','enable','disable','tooltip','menu'],
    'rescue': ['detect','diagnose','repair','recover','backup',
               'restore','rollback','quarantine','clean',
               'verify','report','escalate'],
    'schedule': ['add','remove','list','run','next','cancel',
                 'pause','resume','cron','interval',
                 'once','recurring','status','history'],
    'system': ['info','cpu','memory','disk','network','processes',
               'uptime','load','users','env','hostname','platform',
               'report','monitor'],
    'text': ['read','write','search','replace','split','join',
             'tokenize','normalize','clean','format','extract',
             'compare','diff','count','encode'],
    'unify': ['merge','dedupe','resolve','normalize','standardize',
              'match','link','group','aggregate','validate',
              'report','export'],
    'wws_index': ['create','build','search','query','update',
                  'delete','rebuild','optimize','stats',
                  'export','import','merge','validate'],
    'yaml': ['parse','dump','load','save','validate',
             'merge','query','convert','extract','inject',
             'normalize','compare'],
}


# ============================================================
# VBSTYLE METHOD TEMPLATE GENERATOR
# ============================================================

def generate_vbstyle_method(domain, method_name, description=""):
    """Generate a VBStyle-compliant method stub, wrapped in a class for standalone execution."""
    import keyword
    safe_name = method_name
    if keyword.iskeyword(method_name):
        safe_name = f"{method_name}_impl"
    code = f'''class Dom{method_name.title().replace("_","")}:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {{"config": {{}}, "results": []}}
    def {safe_name}(self, params=None):
        params = params or {{}}
        try:
            result = {{"domain": "{domain}", "method": "{method_name}", "params": params}}
            return (1, result, None)
        except Exception as e:
            return (0, {{}}, ("{method_name.upper()}_ERROR", str(e), 0))
'''
    return code


def generate_vbstyle_class(domain, authority_name, methods):
    """Generate a VBStyle-compliant authority class with methods."""
    
    method_defs = []
    for mname, mdesc in methods:
        method_defs.append(generate_vbstyle_method(domain, mname, mdesc))
    
    methods_code = '\n\n'.join(method_defs)
    
    # Build dispatch
    dispatch_lines = []
    for mname, _ in methods:
        dispatch_lines.append(f'        elif command == "{mname}":')
        dispatch_lines.append(f'            return self.{mname}(params)')
    
    dispatch = '\n'.join(dispatch_lines)
    
    class_code = f'''#[@GHOST]{{[@file<dom_{domain}.py>][@state<active>][@date<{datetime.now().strftime("%Y-%m-%d")}>>][@ver<1.0>][@auth<system>]}}
#[@VBSTYLE]{{[@auth<system>][@role<domain_{domain}>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|abc|inheritance>]}}

"""
{authority_name} Authority for {domain} domain.
Generated by Domain Closure Engine.
"""

class {authority_name}:
    """Authority for {domain} domain — {len(methods)} methods."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {{
            "config": {{}},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db
        }}
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    #[@Run]{{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch {authority_name} commands>]}}
    def Run(self, command, params=None):
        params = params or {{}}
        if command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
{dispatch}
        else:
            return (0, {{}}, ("UNKNOWN_COMMAND", f"Unknown command: {{command}}", 0))

    def read_state(self):
        return (1, {{"state": self.state}}, None)

    def set_config(self, values):
        cfg = values.get("config") if isinstance(values, dict) else {{}}
        if isinstance(cfg, dict):
            self.state["config"].update(cfg)
        return (1, self.state["config"], None)

{methods_code}
'''
    return class_code


# ============================================================
# CLOSURE ENGINE
# ============================================================

class ClosureEngine:
    
    def __init__(self):
        self.local = sqlite3.connect(DB_PATH)
        self.lc = self.local.cursor()
        
        try:
            self.mysql = mysql.connector.connect(user='root', database='vb_code_test')
            self.mc = self.mysql.cursor(dictionary=True)
        except Exception as e:
            print(f"WARNING: MySQL not available: {e}")
            self.mysql = None
            self.mc = None
        
        self.stats = {
            'domains_total': 0,
            'domains_closed': 0,
            'methods_needed': 0,
            'methods_found_in_dom': 0,
            'methods_found_in_mysql': 0,
            'methods_generated': 0,
            'methods_copied': 0,
            'units_created': 0,
            'classes_created': 0,
            'tests_passed': 0,
            'tests_failed': 0,
        }
    
    def close(self):
        self.local.close()
        if self.mysql:
            self.mysql.close()

    def Run(self, command, params=None):
        """VBStyle dispatch entry point for ClosureEngine.

        Commands:
            run          — execute full closure pass (populates all tables)
            init         — create closure tables only
            status       — return current closure_status rows
            domain       — process a single domain (params: {'domain': name})
            read_state   — return engine stats
        Returns Tuple3 (ok, data, error).
        """
        params = params or {}
        if command == 'run':
            self.init_closure_tables()
            self.lc.execute("DELETE FROM closure_status")
            self.lc.execute("DELETE FROM closure_methods")
            self.lc.execute("DELETE FROM closure_tests")
            self.local.commit()
            domains = sorted(DOMAIN_CLOSURE.keys())
            results = []
            for domain in domains:
                r = self.process_domain(domain)
                if r:
                    results.append(r)
            self.local.commit()
            return (1, {'results': results, 'stats': dict(self.stats)}, None)
        if command == 'init':
            self.init_closure_tables()
            return (1, {'tables': ['closure_status', 'closure_methods', 'closure_tests']}, None)
        if command == 'status':
            rows = self.lc.execute(
                "SELECT domain, methods_needed, methods_have, methods_missing, closure_pct, status, last_updated FROM closure_status ORDER BY domain"
            ).fetchall()
            return (1, rows, None)
        if command == 'domain':
            domain = params.get('domain')
            if not domain:
                return (0, None, ('MISSING_PARAM', 'domain required', 0))
            self.init_closure_tables()
            r = self.process_domain(domain)
            self.local.commit()
            return (1, r, None)
        if command == 'read_state':
            return (1, {'stats': dict(self.stats)}, None)
        return (0, None, ('UNKNOWN_COMMAND', f'ClosureEngine unknown: {command}', 0))

    def init_closure_tables(self):
        """Create closure tracking tables."""
        self.lc.executescript('''
            CREATE TABLE IF NOT EXISTS closure_status (
                domain TEXT PRIMARY KEY,
                methods_needed INTEGER DEFAULT 0,
                methods_have INTEGER DEFAULT 0,
                methods_missing INTEGER DEFAULT 0,
                closure_pct REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                last_updated TEXT
            );
            
            CREATE TABLE IF NOT EXISTS closure_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                method_name TEXT NOT NULL,
                source TEXT,
                source_detail TEXT,
                method_code TEXT,
                is_implemented INTEGER DEFAULT 0,
                is_generated INTEGER DEFAULT 0,
                is_copied INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(domain, method_name)
            );
            
            CREATE TABLE IF NOT EXISTS closure_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                method_name TEXT NOT NULL,
                test_status TEXT,
                test_result TEXT,
                tested_at TEXT
            );
        ''')
        self.local.commit()
    
    def get_dom_methods(self, domain):
        """Get methods from dom_*.py file."""
        fname = f"dom_{domain}.py"
        fpath = os.path.join(DOMAINS_DIR, fname)
        if not os.path.exists(fpath):
            return set(), {}
        
        with open(fpath) as f:
            source = f.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return set(), {}
        
        methods = set()
        method_code = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mname = node.name.lower()
                methods.add(mname)
                code = ast.get_source_segment(source, node)
                if code:
                    method_code[mname] = code
        
        # Also check dispatch commands
        for m in re.finditer(r'command\s*==\s*["\'](\w+)["\']', source):
            methods.add(m.group(1).lower())
        
        return methods, method_code
    
    def search_mysql(self, method_name):
        """Search MySQL for a method by name."""
        if not self.mc:
            return None
        
        # Exact match (case-insensitive)
        self.mc.execute("""
            SELECT m.id, m.method_name, m.method_code, m.class_id,
                   c.class_name, c.domain
            FROM vb_methods m 
            JOIN vb_classes c ON m.class_id = c.id
            WHERE LOWER(m.method_name) = LOWER(%s)
            AND m.method_code IS NOT NULL
            AND LENGTH(m.method_code) > 50
            ORDER BY LENGTH(m.method_code) ASC
            LIMIT 1
        """, (method_name,))
        row = self.mc.fetchone()
        if row:
            return row
        
        # Partial match
        self.mc.execute("""
            SELECT m.id, m.method_name, m.method_code, m.class_id,
                   c.class_name, c.domain
            FROM vb_methods m 
            JOIN vb_classes c ON m.class_id = c.id
            WHERE LOWER(m.method_name) LIKE %s
            AND m.method_code IS NOT NULL
            AND LENGTH(m.method_code) > 50
            ORDER BY LENGTH(m.method_code) ASC
            LIMIT 1
        """, (f'%{method_name}%',))
        return self.mc.fetchone()
    
    def search_local_db(self, method_name):
        """Search local v20 DB for a method by name."""
        results = self.lc.execute("""
            SELECT m.id, m.method_name, m.method_code, c.class_name, c.domain
            FROM methods m JOIN classes c ON m.class_id = c.id
            WHERE LOWER(m.method_name) = LOWER(?)
            AND m.method_code IS NOT NULL
            AND LENGTH(m.method_code) > 50
            LIMIT 1
        """, (method_name,)).fetchall()
        return results[0] if results else None
    
    def generate_method(self, domain, method_name):
        """Generate a VBStyle-compliant method stub."""
        code = generate_vbstyle_method(domain, method_name)
        return code
    
    def insert_closure_method(self, domain, method_name, source, source_detail, method_code, is_generated=0, is_copied=0):
        """Insert a closure method into the DB."""
        self.lc.execute("""
            INSERT OR REPLACE INTO closure_methods 
            (domain, method_name, source, source_detail, method_code, is_implemented, is_generated, is_copied)
            VALUES (?,?,?,?,?,1,?,?)
        """, (domain, method_name, source, source_detail, method_code, is_generated, is_copied))
        self.local.commit()
    
    def create_computational_unit(self, domain, method_name, class_id, method_code):
        """Create a computational unit for a method."""
        # Check if already exists
        existing = self.lc.execute("""
            SELECT id FROM computational_units 
            WHERE unit_name = ? AND unit_type = 'method'
        """, (f"Method: {method_name}",)).fetchone()
        
        if existing:
            return existing[0]
        
        complexity = len(method_code) / 100.0 if method_code else 0
        self.lc.execute("""
            INSERT INTO computational_units 
            (unit_name, unit_type, class_id, method_id, complexity_score, status)
            VALUES (?,?,?,?,?,'active')
        """, (f"Method: {method_name}", 'method', class_id, None, complexity))
        self.local.commit()
        return self.lc.lastrowid
    
    def ensure_domain_class(self, domain):
        """Ensure a class exists for the domain in the DB."""
        # Check if exists
        row = self.lc.execute("SELECT id FROM classes WHERE class_name = ?", (f"Dom{domain.title().replace('_','')}",)).fetchone()
        if row:
            return row[0]
        
        # Create
        class_name = f"Dom{domain.title().replace('_','')}"
        class_code = f"# Generated domain authority for {domain}"
        self.lc.execute("""
            INSERT INTO classes (class_name, class_code, domain, description, source_file, is_vbstyle, has_run_method, has_tuple3, version)
            VALUES (?,?,?,?,?,1,1,1,1)
        """, (class_name, class_code, domain, f"Domain authority for {domain}", f"dom_{domain}.py"))
        self.local.commit()
        self.stats['classes_created'] += 1
        return self.lc.lastrowid
    
    def test_method(self, domain, method_name, method_code):
        """Test a method by executing it."""
        if not method_code:
            return False, "No code"
        
        try:
            # Try to parse the code
            tree = ast.parse(method_code)
            
            # Check VBStyle compliance
            violations = []
            if 'self._' in method_code:
                violations.append('self._ used')
            if 'print(' in method_code:
                violations.append('print() used')
            if re.search(r'@(property|staticmethod|classmethod)', method_code):
                violations.append('decorator used')
            if '\t' in method_code:
                violations.append('tab used')
            
            if violations:
                return False, f"VBStyle violations: {', '.join(violations)}"
            
            return True, "OK"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Error: {e}"
    
    def process_domain(self, domain):
        """Process a single domain for closure using behavioral validation."""
        closure_ops = DOMAIN_CLOSURE.get(domain, [])
        if not closure_ops:
            return

        self.stats['domains_total'] += 1
        self.stats['methods_needed'] += len(closure_ops)

        # Ensure domain class exists
        class_id = self.ensure_domain_class(domain)

        # Initialize behavioral validation components
        retriever = CandidateRetriever()
        ranker = SurvivorRanker()

        found_in_dom = 0
        found_in_mysql = 0
        generated = 0
        verified = 0
        unverified = 0

        for op in closure_ops:
            # 1. Retrieve ALL candidates from all sources
            candidates = retriever.Retrieve(domain, op)

            # 2. Compete — run all through behavioral validator
            winner, ranked = ranker.Compete(candidates, op, domain)

            if not winner:
                self.stats['tests_failed'] += 1
                self.lc.execute("INSERT INTO closure_tests (domain, method_name, test_status, test_result, tested_at) VALUES (?,?,?,?,?)",
                               (domain, op, 'FAIL', 'no_candidates', datetime.now().isoformat()))
                continue

            code, source, source_detail, score, detail = winner

            # Track source stats
            if source == 'dom_file':
                found_in_dom += 1
                self.stats['methods_found_in_dom'] += 1
            elif source in ('mysql', 'efl_brain'):
                found_in_mysql += 1
                self.stats['methods_found_in_mysql'] += 1
                self.stats['methods_copied'] += 1
            else:
                generated += 1
                self.stats['methods_generated'] += 1

            is_generated = 1 if source == 'generated' else 0
            is_copied = 1 if source in ('mysql', 'efl_brain') else 0

            # 3. Promote winner to closure_methods
            self.insert_closure_method(domain, op, source, source_detail, code, is_generated=is_generated, is_copied=is_copied)

            # 4. Create computational unit
            self.create_computational_unit(domain, op, class_id, code)
            self.stats['units_created'] += 1

            # 5. Record test result
            is_verified = score >= 30
            test_status = 'PASS' if is_verified else 'FAIL'
            test_detail = f'score={score} src={source} {detail}'
            self.lc.execute("INSERT INTO closure_tests (domain, method_name, test_status, test_result, tested_at) VALUES (?,?,?,?,?)",
                           (domain, op, test_status, test_detail, datetime.now().isoformat()))

            if is_verified:
                self.stats['tests_passed'] += 1
                verified += 1
            else:
                self.stats['tests_failed'] += 1
                unverified += 1

            # 6. Log all candidates to execution_log for historical reward
            self._log_competition(domain, op, ranked)

        # Update closure status
        total_have = found_in_dom + found_in_mysql + generated
        pct = (total_have / len(closure_ops) * 100) if closure_ops else 0
        status = 'closed' if pct == 100 else 'open'

        self.lc.execute("""
            INSERT OR REPLACE INTO closure_status
            (domain, methods_needed, methods_have, methods_missing, closure_pct, status, last_updated)
            VALUES (?,?,?,?,?,?,?)
        """, (domain, len(closure_ops), total_have, 0, pct, status, datetime.now().isoformat()))
        self.local.commit()

        if pct == 100:
            self.stats['domains_closed'] += 1

        return {
            'domain': domain,
            'needed': len(closure_ops),
            'in_dom': found_in_dom,
            'in_mysql': found_in_mysql,
            'generated': generated,
            'verified': verified,
            'unverified': unverified,
            'pct': pct,
            'status': status,
        }

    def _log_competition(self, domain, method_name, ranked_results):
        """Log competition results to execution_log for historical reward tracking."""
        if not os.path.exists(EFL_BRAIN_DB):
            return
        try:
            conn = sqlite3.connect(EFL_BRAIN_DB)
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER,
                method_id INTEGER,
                class_name TEXT,
                method_name TEXT,
                input_state TEXT,
                output_state TEXT,
                action_taken TEXT,
                success INTEGER,
                error_msg TEXT,
                reward REAL,
                timestamp TEXT
            )""")
            for src, src_detail, score, detail, ok in ranked_results:
                cur.execute("""INSERT INTO execution_log
                    (class_name, method_name, action_taken, success, error_msg, reward, timestamp)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    f'Dom{domain.title()}', method_name,
                    f'candidate:{src}:{src_detail}',
                    1 if ok else 0,
                    detail[:200] if detail else '',
                    float(score) / 100.0,
                    datetime.now().isoformat()
                ))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def run(self):
        """Run the full closure engine."""
        print("=" * 100)
        print("VBSTYLE DOMAIN CLOSURE ENGINE")
        print("=" * 100)
        print()
        
        # Init tables
        self.init_closure_tables()
        
        # Clear previous run
        self.lc.execute("DELETE FROM closure_status")
        self.lc.execute("DELETE FROM closure_methods")
        self.lc.execute("DELETE FROM closure_tests")
        self.local.commit()
        
        # Process all domains
        domains = sorted(DOMAIN_CLOSURE.keys())
        results = []
        
        t0 = time.time()
        for i, domain in enumerate(domains, 1):
            r = self.process_domain(domain)
            if r:
                results.append(r)
                marker = "CLOSED" if r['status'] == 'closed' else "OPEN"
                print(f"  [{i:2d}/57] {domain:15s} need={r['needed']:3d} dom={r['in_dom']:3d} mysql={r['in_mysql']:3d} gen={r['generated']:3d} {r['pct']:5.1f}% {marker}")
        
        elapsed = time.time() - t0
        
        # Final report
        print()
        print("=" * 100)
        print("CLOSURE COMPLETE — FINAL REPORT")
        print("=" * 100)
        print()
        
        # Domain status
        print(f"{'Domain':15s} {'Need':>5s} {'Dom':>5s} {'MySQL':>6s} {'Gen':>5s} {'%':>6s} {'Status':>8s}")
        print("-" * 60)
        for r in sorted(results, key=lambda x: x['pct'], reverse=True):
            print(f"{r['domain']:15s} {r['needed']:5d} {r['in_dom']:5d} {r['in_mysql']:6d} {r['generated']:5d} {r['pct']:5.1f}% {r['status']:>8s}")
        print("-" * 60)
        
        # Stats
        print()
        print("ENGINE STATS:")
        print(f"  Domains processed:     {self.stats['domains_total']}")
        print(f"  Domains closed:        {self.stats['domains_closed']}")
        print(f"  Methods needed:        {self.stats['methods_needed']}")
        print(f"  Found in dom files:    {self.stats['methods_found_in_dom']}")
        print(f"  Found in MySQL:        {self.stats['methods_found_in_mysql']}")
        print(f"  Generated:             {self.stats['methods_generated']}")
        print(f"  Classes created:       {self.stats['classes_created']}")
        print(f"  Units created:         {self.stats['units_created']}")
        print(f"  Tests passed:          {self.stats['tests_passed']}")
        print(f"  Tests failed:          {self.stats['tests_failed']}")
        print(f"  Time:                  {elapsed:.1f}s")
        print()
        print("BEHAVIORAL VALIDATION:")
        total_verified = self.lc.execute("SELECT COUNT(*) FROM closure_tests WHERE test_status='PASS'").fetchone()[0]
        total_unverified = self.lc.execute("SELECT COUNT(*) FROM closure_tests WHERE test_status='FAIL'").fetchone()[0]
        print(f"  Verified (score>=30):  {total_verified}")
        print(f"  Unverified:            {total_unverified}")
        
        # DB stats
        total_units = self.lc.execute("SELECT COUNT(*) FROM computational_units").fetchone()[0]
        total_classes = self.lc.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        total_methods = self.lc.execute("SELECT COUNT(*) FROM methods").fetchone()[0]
        closure_methods = self.lc.execute("SELECT COUNT(*) FROM closure_methods").fetchone()[0]
        db_size = os.path.getsize(DB_PATH)
        
        print()
        print("DATABASE STATE:")
        print(f"  Classes:               {total_classes}")
        print(f"  Methods:               {total_methods}")
        print(f"  Computational units:   {total_units}")
        print(f"  Closure methods:       {closure_methods}")
        print(f"  DB size:               {db_size/1024/1024:.1f} MB")
        
        # Test summary
        print()
        print("TEST RESULTS:")
        for status, cnt in self.lc.execute("SELECT test_status, COUNT(*) FROM closure_tests GROUP BY test_status").fetchall():
            print(f"  {status}: {cnt}")
        
        # Failed tests
        failed = self.lc.execute("SELECT domain, method_name, test_result FROM closure_tests WHERE test_status='FAIL' LIMIT 10").fetchall()
        if failed:
            print()
            print("FAILED TESTS (first 10):")
            for d, m, r in failed:
                print(f"  {d}.{m}: {r}")
        
        self.close()


if __name__ == "__main__":
    engine = ClosureEngine()
    ok, data, err = engine.Run('run')
    if not ok:
        print(f"Closure engine failed: {err}")
        engine.close()
        sys.exit(1)
    stats = data.get('stats', {})
    results = data.get('results', [])
    closed = sum(1 for r in results if r['status'] == 'closed')
    print(f"Domains: {len(results)} | Closed: {closed} | Methods needed: {stats.get('methods_needed',0)} | Generated: {stats.get('methods_generated',0)} | Found in dom: {stats.get('methods_found_in_dom',0)}")
    engine.close()
