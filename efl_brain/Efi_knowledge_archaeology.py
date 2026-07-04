#!/usr/bin/env python3
"""MySQL Architecture Archaeology — streaming, row-capped, progress-printing."""
import mysql.connector, json, re, time, sys, os
from collections import Counter, defaultdict
import Config_efl_brain as Config

T0 = time.time()
mysql_cfg = Config.MYSQL_CONFIG
conn = mysql.connector.connect(
    user=mysql_cfg.get('user', 'root'),
    host=mysql_cfg.get('host', 'localhost'),
    password=mysql_cfg.get('password', ''),
    charset='utf8mb4', autocommit=True, connection_timeout=10
)
cur = conn.cursor(buffered=False)

# ── Databases ──────────────────────────────────────────────────────────────
cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema','mysql','performance_schema','sys')")
DBS = [r[0] for r in cur.fetchall()]

# ── Text columns per table ─────────────────────────────────────────────────
cur.execute("""SELECT table_schema, table_name, column_name, column_key, ordinal_position
FROM information_schema.columns
WHERE table_schema IN (%s) AND data_type IN ('text','varchar','longtext','mediumtext','char','tinytext')
ORDER BY table_schema, table_name, ordinal_position""" % ','.join(['%s']*len(DBS)), DBS)

TABLE_COLS = defaultdict(list)
PK_COL = {}
for db, tbl, col, ckey, pos in cur.fetchall():
    TABLE_COLS[(db, tbl)].append(col)
    if ckey == 'PRI' and (db, tbl) not in PK_COL:
        PK_COL[(db, tbl)] = col

# ── Known concepts regex ───────────────────────────────────────────────────
CONCEPTS = [
    'MAIN_UNIT','MainUnit','main_unit','REPORT_CLASS','ReportClass','report_class',
    'EVENT_HANDLER','EventHandler','event_handler','EventDispatcher','event_dispatcher',
    'IN_RAM','InRam','inram','in_ram_fixer','MemUnit','MemDB','MemBus','GuiDB','GuiBus',
    'magnetic','Magnetic','survivor','Survivor','champion','Champion',
    'candidate','Candidate','promotion','Promotion',
    'PROMOTION_QUEUE','CANDIDATE_GENERATOR','MUTATION_ENGINE','PROBLEM_CAPTURE',
    'BCL','bcl_config','bcl_command','bracket command',
    'evolution','Evolution','adversarial','challenger',
    'mutation','Mutation','sandbox','Sandbox',
    'repair','Repair','boot_chain','BootChain',
    'domain_owned','domain owned',
    'know_fixes','know_causes','know_problems','know_solutions','know_questions','know_answers','know_lessons',
    'pattern_db','PatternDB','execution_kernel','ExecutionKernel','traceable','Traceable',
    'replay','Replay','evidence','Evidence','diagnostic','Diagnostic','investigation','Investigation',
    'Open_Gates','open_gates','OpenGates','yin_yang','yin and yang',
    'web_search','WebSearch','closed_domain','closed domain',
    'truth_surface','truth surface','authority_surface','authority surface',
    'gatekeeper','Gatekeeper','causal_memory','causal memory',
    'black_box','black box','repair_organism','repair organism',
    'survival','Survival','knowledge_base','knowledge base',
    'state_legality','state legality','kernel','authority','orthogonal',
    'event_queue','event_history','state_current','state_history',
    'error_log','report_log','worker_registry','event_sourced','event sourced',
    'fixer','Fixer','promote','Promote',
    'know_memory_units','know_reasoning','know_plans','know_nodes','know_edges',
    'flow_tokens','know_tokens','decision_trees','decision_principles',
    'system_evolution','scoring_model','kernel_contracts','runtime_context',
    'GhostAuthority','KernelLegality','PromotionJudge',
    'Tuple3','tuple3','self.state','self.state',
    'VBStyle','vbstyle','Ghost','ghost_header',
    'domain','Domain','Boot','boot','Unit','unit',
    'orchestration','Orchestration','scanner','Scanner',
    'bracket','Bracket','signature','Signature',
    'config','Config','report','Report',
    'state','State','event','Event',
    'truth','Truth','memory','Memory',
    'worker','Worker','queue','Queue',
    'valigo fine dator','Validator','rule','Rule',
    'score','Score','rank','Rank','weight','Weight',
    'trust','Trust','hierarchy','Hierarchy',
    'layer','Layer','pipeline','Pipeline',
    'pass','Pass','fail','Fail',
    'attack','Attack','defend','Defend',
    'learn','Learn','teach','Teach',
    'question','Question','answer','Answer',
    'cause','Cause','fix','Fix','problem','Problem','solution','Solution',
    'observation','Observation','hypothesis','Hypothesis',
    'decision','Decision','principle','Principle',
    'graph','Graph','node','Node','edge','Edge',
    'token','Token','class','Class','method','Method',
    'file','File','path','Path',
    'index','Index','registry','Registry',
    'live','Live','dead','Dead','deprecated','Deprecated',
    'version','Version','history','History',
    'snapshot','Snapshot','checkpoint','Checkpoint',
    'context','Context','runtime','Runtime',
    'control','Control','plane','Plane',
    'bus','Bus','route','Route',
    'store','Store','cache','Cache',
    'load','Load','save','Save',
    'read','Read','write','Write',
    'scan','Scan','parse','Parse',
    'extract','Extract','mine','Mine',
    'embed','Embed','vector','Vector',
    'search','Search','find','Find',
    'match','Match','score','Score',
    'promote','Promote','demote','Demote',
    'lock','Lock','unlock','Unlock',
    'archive','Archive','restore','Restore',
    'migrate','Migrate','merge','Merge',
    'split','Split','join','Join',
    'clone','Clone','copy','Copy',
    'move','Move','delete','Delete',
    'create','Create','update','Update',
    'validate','Validate','normalize','Normalize',
    'transform','Transform','convert','Convert',
    'generate','Generate','build','Build',
    'assemble','Assemble','disassemble','Disassemble',
    'compile','Compile','decompile','Decompile',
    'run','Run','execute','Execute',
    'start','Start','stop','Stop',
    'pause','Pause','resume','Resume',
    'reset','Reset','clear','Clear',
    'flush','Flush','sync','Sync',
    'watch','Watch','monitor','Monitor',
    'alert','Alert','notify','Notify',
    'log','Log','trace','Trace',
    'debug','Debug','inspect','Inspect',
    'profile','Profile','benchmark','Benchmark',
    'test','Test','verify','Verify',
    'check','Check','assert','Assert',
    'expect','Expect','should','Should',
    'must','Must','shall','Shall',
    'will','Will','may','May',
    'can','Can','cannot','Cannot',
    'should_not','ShouldNot','must_not','MustNot',
]
CONCEPT_RE = re.compile('|'.join(re.escape(c) for c in CONCEPTS), re.IGNORECASE)

# ── Identifier miner ───────────────────────────────────────────────────────
IDENT_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]{4,}')
NOISE = {
    'select','from','where','table','column','create','insert','update','delete','default',
    'primary','foreign','index','value','values','null','true','false','text','varchar',
    'integer','int','autoincrement','timestamp','current','charset','engine','innodb',
    'content','length','size','status','error','message','source','path','file','name',
    'class','method','function','return','import','module','python','string','object',
    'none','type','self','this','that','with','have','been','which','their','there',
    'would','could','should','about','after','before','other','more','some','such',
    'than','then','them','they','were','what','when','where','will','into','only',
    'also','each','make','like','does','done','here','your','have','want','know',
    'just','very','much','many','most','both','same','such','tell','talk','said',
    'time','date','first','last','next','prev','true','false','none','null','empty',
    'content_hash','source_fingerprint','stored_fingerprint','rebuild_fingerprint',
    'verified_at','ingested_at','discovered_at','modified_time','disk_size',
    'extension','language','directory','filename','full_path','line_count',
    'file_size','created_at','archived_at','archive_path','error_message',
    'schema','tables','columns','rows','records','entries','items','fields',
    'query','result','output','input','params','args','kwargs','data','dict',
    'list','tuple','set','bool','str','float','bytes','bytearray',
    'print','open','close','read','write','seek','tell','flush',
    'encode','decode','split','join','strip','replace','format','lower','upper',
    'startswith','endswith','contains','find','index','count','append','extend',
    'insert','remove','pop','sort','reverse','copy','deepcopy','clear',
    'items','keys','values','get','setdefault','popitem','update','fromkeys',
    'isinstance','issubclass','hasattr','getattr','setattr','delattr',
    'property','staticmethod','classmethod','abstractmethod',
    'exception','error','warning','info','debug','critical','fatal',
    'traceback','stack','frame','locals','globals','builtin',
    'import','from','as','elif','else','except','finally','for','while',
    'try','with','yield','raise','break','continue','pass','return',
    'global','nonlocal','lambda','assert','del','in','not','and','or',
    'is','none','true','false','boolean','integer','float','complex',
    'string','bytes','bytearray','list','tuple','set','frozenset','dict',
    'range','zip','map','filter','sorted','reversed','enumerate','any','all',
    'sum','min','max','abs','round','pow','divmod','hex','oct','bin','chr','ord',
    'format','repr','str','int','float','bool','list','tuple','set','dict',
    'type','id','hash','dir','vars','help','input','print','open',
    'len','iter','next','slice','super','object','property','memoryview',
}

# ── Accumulators ───────────────────────────────────────────────────────────
KNOWN_HITS = []          # [{db, table, row_id, concepts, snippet}]
IDENT_FREQ = Counter()   # token_lower -> count
IDENT_DBS = defaultdict(set)
IDENT_TABLES = defaultdict(set)
IDENT_LOC = defaultdict(list)  # token -> [(db, table, row_id)]  (max 3)
CO_OCCUR = defaultdict(Counter)  # token -> Counter of co-occurring tokens

TABLES_SCANNED = 0
ROWS_SCANNED = 0
MAX_ROWS_PER_TABLE = 2000
MAX_FIELD_SCAN = 1000
# Skip tables with huge blob content that cause hangs
SKIP_TABLES = {
    ('CODEBASE', 'python_files'), ('CODEBASE', 'markdown_files'), ('CODEBASE', 'json_files'),
    ('CODEBASE', 'yaml_files'), ('CODEBASE', 'c_files'), ('CODEBASE', 'swift_files'),
    ('CODEBASE', 'csharp_files'), ('CODEBASE', 'file_archive'),
    ('vbstyle_documents', 'markdown_files'), ('vbstyle_documents', 'json_files'),
    ('vbstyle_documents', 'yaml_files'), ('vbstyle_documents', 'brk_files'),
}

# ── Stream ─────────────────────────────────────────────────────────────────
total_tables = len(TABLE_COLS)
for idx, ((db, tbl), cols) in enumerate(TABLE_COLS.items()):
    if (db, tbl) in SKIP_TABLES:
        continue
    if idx % 10 == 0:
        elapsed = time.time() - T0
        print(f"[{elapsed:.0f}s] Table {idx+1}/{total_tables}: {db}.{tbl}...", flush=True)

    pk = PK_COL.get((db, tbl), cols[0])
    col_list = ', '.join('`%s`' % c for c in cols)
    try:
        cur.execute(f"SELECT `{pk}`, {col_list} FROM `{db}`.`{tbl}` LIMIT {MAX_ROWS_PER_TABLE}")
    except Exception:
        continue

    TABLES_SCANNED += 1

    while True:
        rows = cur.fetchmany(500)
        if not rows:
            break
        for row in rows:
            ROWS_SCANNED += 1
            row_id = str(row[0])[:80]
            row_idents = []

            for val in row[1:]:
                if val is None:
                    continue
                s = str(val)[:MAX_FIELD_SCAN]

                # Known concept — search() first, finditer() only on hit
                m = CONCEPT_RE.search(s)
                if m:
                    found = set()
                    for fm in CONCEPT_RE.finditer(s):
                        found.add(fm.group().lower())
                    start = max(0, m.start() - 40)
                    end = min(len(s), m.end() + 80)
                    snippet = s[start:end].replace('\n', ' ')[:200]
                    KNOWN_HITS.append({
                        'db': db, 'table': tbl, 'row_id': row_id,
                        'concepts': sorted(found), 'snippet': snippet
                    })

                # Identifier mining — search directly on field, no concat
                for im in IDENT_RE.finditer(s):
                    token = im.group()
                    tl = token.lower()
                    if tl in NOISE or len(tl) < 5:
                        continue
                    IDENT_FREQ[tl] += 1
                    IDENT_DBS[tl].add(db)
                    IDENT_TABLES[tl].add(tbl)
                    if len(IDENT_LOC[tl]) < 3:
                        IDENT_LOC[tl].append((db, tbl, row_id))
                    row_idents.append(tl)

            # Co-occurrence within row
            unique_row = list(set(row_idents))
            if len(unique_row) > 1:
                for i, t1 in enumerate(unique_row):
                    for t2 in unique_row[i+1:]:
                        if t1 != t2:
                            CO_OCCUR[t1][t2] += 1
                            CO_OCCUR[t2][t1] += 1

T1 = time.time()
ELAPSED = round(T1 - T0, 1)

# ── Output ─────────────────────────────────────────────────────────────────
print(f"Scanned {TABLES_SCANNED} tables, {ROWS_SCANNED} rows in {ELAPSED}s")
print(f"Known hits: {len(KNOWN_HITS)}, Unique identifiers: {len(IDENT_FREQ)}")

# By database
print("\n=== KNOWN HITS BY DATABASE ===")
for db, cnt in Counter(r['db'] for r in KNOWN_HITS).most_common():
    print(f"  {db}: {cnt}")

# By concept
print("\n=== KNOWN HITS BY CONCEPT ===")
concept_hits = Counter()
for r in KNOWN_HITS:
    for c in r['concepts']:
        concept_hits[c] += 1
for c, cnt in concept_hits.most_common(60):
    print(f"  {c}: {cnt}")

# By table
print("\n=== KNOWN HITS BY TABLE (top 30) ===")
for (db, tbl), cnt in Counter((r['db'], r['table']) for r in KNOWN_HITS).most_common(30):
    print(f"  {db}.{tbl}: {cnt}")

# Top identifiers — architecture archaeology
print("\n=== TOP IDENTIFIERS (forgotten architecture terms) ===")
print(f"{'token':<45} {'freq':>6} {'dbs':>4} {'tbls':>5}")
for token, cnt in IDENT_FREQ.most_common(150):
    print(f"  {token:<45} {cnt:>6} {len(IDENT_DBS[token]):>4} {len(IDENT_TABLES[token]):>5}")

# Co-occurrence for key terms
print("\n=== CO-OCCURRENCE GRAPH ===")
KEY = ['main_unit','memunit','memdb','membus','guidb','guibus','report_class',
       'event_handler','survivor','champion','promotion','candidate','repair',
       'mutation','sandbox','evolution','evidence','diagnostic','replay',
       'kernel','authority','magnetic','bcl','fixer','survival','ghost',
       'vbstyle','tuple3','state','event','truth','memory','worker',
       'orchestration','scanner','bracket','signature','domain','boot','unit',
       'validator','rule','score','rank','weight','trust','hierarchy',
       'layer','pipeline','pass','fail','attack','learn','question','cause',
       'fix','problem','solution','observation','decision','principle',
       'graph','node','edge','token','runtime','context','control','plane',
       'bus','route','store','cache','index','registry','live','dead',
       'version','history','snapshot','checkpoint']
for term in KEY:
    if term in CO_OCCUR:
        top = CO_OCCUR[term].most_common(8)
        if top:
            print(f"  {term} -> {', '.join(f'{t}({c})' for t,c in top)}")

# ── Save JSON ──────────────────────────────────────────────────────────────
OUTPUT = {
    'stats': {
        'tables_scanned': TABLES_SCANNED, 'rows_scanned': ROWS_SCANNED,
        'time_seconds': ELAPSED, 'known_hits': len(KNOWN_HITS),
        'unique_identifiers': len(IDENT_FREQ)
    },
    'known_hits': KNOWN_HITS,
    'identifiers': [
        {'token': t, 'freq': c, 'dbs': sorted(IDENT_DBS[t]),
         'tables': sorted(IDENT_TABLES[t]), 'locations': IDENT_LOC[t],
         'co_occurs': CO_OCCUR[t].most_common(10) if t in CO_OCCUR else []}
        for t, c in IDENT_FREQ.most_common(500)
    ],
    'co_occurrence': {t: dict(c.most_common(15)) for t, c in CO_OCCUR.items()
                      if c.most_common(1) and c.most_common(1)[0][1] > 2},
}

OUT_PATH = os.path.join(Config.BASE_DIR, 'mysql_concept_search.json')
with open(OUT_PATH, 'w') as f:
    json.dump(OUTPUT, f, indent=2, ensure_ascii=False)
print(f"\nSaved to {OUT_PATH}")
conn.close()
