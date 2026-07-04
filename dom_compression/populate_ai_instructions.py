#!/usr/bin/env python3
"""
Populate v20 Database with Complete AI Instructions
====================================================
Makes the v20 database self-teaching — any AI that opens it
can answer ALL questions about how to work with it:

  - How do I add more domain code?
  - Where do I get code from?
  - What code style is required?
  - Where must code go (which tables)?
  - What rules must be followed?
  - How do I verify?
  - What is BCL? How do I make BCL?
  - What happens when an error occurs?
  - Am I allowed to do that?
  - Where are the rules? What are the rules?

Stores everything in _db_meta as a complete instruction set,
so the database itself teaches any AI how to use it.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "code_store_variations", "v20_hybrid_best.db"
)


# ════════════════════════════════════════════════════════════════════════
# INSTRUCTION SET — the complete "how to" for any AI
# ════════════════════════════════════════════════════════════════════════

INSTRUCTIONS = {

    # ─── THE BASICS: What is this database? ───
    "db_name": "v20_hybrid_best",
    "db_purpose": "A normalized, hierarchical knowledge graph storing VBStyle Python code as a 'parts bin'. Every entity (domain, class, method, computational unit) has a BCL identity token that lets it answer questions about itself. The database is self-documenting and self-describing.",
    "architecture": "Hierarchical: Domain → Class → Method → Computational Unit. Each level has BCL identity. Storage is normalized (PK/FK links). BCL tokens provide denormalized view for fast retrieval. Plans assemble ingredients into running systems. Orchestration defines execution order.",

    # ─── HOW TO ADD DOMAIN CODE ───
    "how_to_add_code": """
HOW TO ADD MORE DOMAIN CODE
============================

STEP 1: GET THE CODE
  Source: MySQL vb_code_test database
    - Table: vb_classes (contains class_code)
    - Table: vb_methods (contains method_code)
    - Query: SELECT class_name, class_code FROM vb_classes WHERE class_name LIKE '%YourDomain%'
    - Query: SELECT method_name, method_code FROM vb_methods WHERE class_id = (SELECT id FROM vb_classes WHERE class_name='YourClass')

  Alternative source: Python files on disk
    - Parse with: ast.parse(source) → extract ClassDef and FunctionDef nodes
    - See: ingest_graph_from_mysql.py for example

STEP 2: CHECK CODE STYLE (VBStyle RULES)
  Before storing, verify the code follows VBStyle:
    - Every class must have a Run(command, params) method
    - Every method must return Tuple3 (ok, data, error) where ok=1/0
    - No print() statements
    - No decorators (@property, @staticmethod, @classmethod)
    - No hardcoded localhost or 127.0.0.1
    - No tabs (spaces only)
    - PascalCase class names (e.g. DomGraph, not dom_graph)
    - UPPERCASE constants
    - self.state dict for state (no self._private)
    - No __init__ with complex logic (use Run for dispatch)

  Check violations:
    - See violations table for existing violations
    - Run VBStyle checker before storing new code

STEP 3: CHOOSE THE DOMAIN
  - If adding to existing domain: find class_id in classes table
  - If creating new domain: INSERT INTO classes with domain name
  - Domain naming: lowercase, single word (e.g. 'graphs', 'compression', 'cryptography')

STEP 4: STORE THE CODE
  Tables to populate (in order):

  4a. classes table (if new domain):
    INSERT INTO classes (class_name, class_code, domain, description, source_file,
                         is_vbstyle, has_run_method, has_tuple3, version, created_at)
    VALUES ('DomYourDomain', 'code_here', 'yourdomain', 'description',
            'mysql_vb_code_test', 1, 1, 0, 1, datetime);

  4b. methods table (for each method):
    INSERT INTO methods (class_id, method_name, method_code, params, signature,
                         is_dunder, is_vbstyle, returns_tuple3, version, created_at)
    VALUES (class_id, 'MethodName', 'code_here', 'self, params', 'self, params',
            0, 1, 1, 1, datetime);

  4c. computational_units table (for tightly coupled groups):
    INSERT INTO computational_units (unit_name, unit_type, class_id, method_id,
                                      description, status)
    VALUES ('YourDomain:Component', 'method_group', class_id, method_id, 'desc', 'active');

STEP 5: GENERATE BCL IDENTITY TOKENS
  Run: python3 bcl_identity_generator.py
  This generates BCL tokens for all new entities.
  See "what_is_bcl" instruction for details.

STEP 6: UPDATE CLOSURE
  INSERT INTO closure_status (domain, methods_needed, methods_have, methods_missing, closure_pct, status)
  VALUES ('yourdomain', N, N, 0, 100.0, 'closed');

STEP 7: CREATE PLAN (optional)
  If the new domain should be used in a pipeline:
    INSERT INTO plans (name, goal, expected_outcome, status, version)
    VALUES ('your_plan', 'goal', 'outcome', 'ready', 1);
    INSERT INTO plan_steps (plan_id, sequence, step_name, class_id, method_name, description, produces, consumes)
    VALUES (...);

STEP 8: CREATE ORCHESTRATION (optional)
  INSERT INTO orchestration (pipeline, sequence, class_id, role, description)
    VALUES ('your_pipeline', 1, class_id, 'role', 'description');

STEP 9: VERIFY
  - Check: SELECT COUNT(*) FROM methods WHERE class_id = new_id
  - Check: SELECT COUNT(*) FROM bcl_identity WHERE domain = 'yourdomain'
  - Check: SELECT closure_pct FROM closure_status WHERE domain = 'yourdomain'
  - Run: python3 graph_engine_v2.py (to check for new gaps)
""",

    # ─── WHERE TO GET CODE ───
    "where_to_get_code": """
WHERE TO GET CODE
=================

PRIMARY SOURCE: MySQL vb_code_test database
  Host: localhost, Port: 3306, User: root, Password: (empty)
  Database: vb_code_test
  Tables:
    - vb_classes: 1,394 VBStyle classes with full class_code
    - vb_methods: 13,818 methods with full method_code

  Query examples:
    -- Find classes by domain
    SELECT class_name, domain, LENGTH(class_code) FROM vb_classes WHERE domain = 'graph';

    -- Find methods of a class
    SELECT method_name, params, method_code FROM vb_methods
    WHERE class_id = (SELECT id FROM vb_classes WHERE class_name = 'DomGraph');

    -- Search by keyword
    SELECT class_name, domain FROM vb_classes WHERE class_code LIKE '%compress%';

SECONDARY SOURCE: MySQL CODEBASE database
  Database: CODEBASE
  Table: python_files (389K Python files with full source)
  Query: SELECT filename, line_count FROM python_files WHERE filename LIKE '%graph%';

TERTIARY SOURCE: Disk files
  Directory: /Users/wws/Qdrant_mysql_mlx_vector_engine/dom_compression/
  Parse with: ast.parse() → extract classes and methods
  See: ingest_graph_from_mysql.py for example code

PREFERRED: Always use MySQL first — it's faster than disk search.
""",

    # ─── CODE STYLE RULES ───
    "code_style_rules": """
VBSTYLE CODE RULES (MUST BE FOLLOWED)
======================================

RULE 1: Run() Dispatch
  Every VBStyle class MUST have a Run(command, params) method.
  Run dispatches to internal methods based on command string.
  Returns Tuple3 (ok, data, error).

  Example:
    def Run(self, command, params):
        handlers = {
            "add": self.add,
            "remove": self.remove,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

RULE 2: Tuple3 Returns
  Every VBStyle method MUST return (ok, data, error) where:
    - ok: 1 (success) or 0 (failure)
    - data: the result data (or None on failure)
    - error: None (success) or (error_code, message, severity) tuple

  Example:
    return (1, result_data, None)          # success
    return (0, None, ("NOT_FOUND", "item not found", 1))  # failure

RULE 3: No print()
  NEVER use print() in VBStyle code.
  Use return values to communicate results.
  Violations are tracked in the violations table.

RULE 4: No Decorators
  NEVER use @property, @staticmethod, @classmethod.
  All methods are regular instance methods.

RULE 5: No Hardcoded Localhost
  NEVER hardcode 'localhost' or '127.0.0.1'.
  Use config parameters or environment variables.

RULE 6: No Tabs
  Use spaces for indentation. Never tabs.

RULE 7: PascalCase Classes
  Class names: PascalCase (DomGraph, not dom_graph)
  Method names: PascalCase or snake_case (both accepted, be consistent)
  Constants: UPPERCASE_WITH_UNDERSCORES

RULE 8: self.state Dict
  Use self.state = {} for instance state.
  NEVER use self._private attributes.
  State is a dict that can be inspected and serialized.

RULE 9: No Complex __init__
  __init__ should only set up self.state and basic references.
  All logic goes through Run() dispatch.

RULE 10: Ghost + VBStyle + Class + Method Headers
  Every file should have appropriate headers documenting purpose.

VIOLATIONS:
  Check violations table for existing violations.
  Violation kinds: no_state, no_run, print, no_init, localhost, decorator, tab
""",

    # ─── WHERE CODE GOES ───
    "where_code_goes": """
WHERE CODE GOES IN THE DATABASE
================================

The v20 database has 18+ tables. Code goes into these:

CLASSES TABLE (domain-level code):
  - One row per domain (e.g. DomGraph, DomCompression, DomCryptography)
  - class_name: PascalCase domain class name (e.g. 'DomGraph')
  - class_code: full Python class source code
  - domain: lowercase domain name (e.g. 'graphs')
  - is_vbstyle: 1 (must be VBStyle compliant)
  - has_run_method: 1 (must have Run() dispatch)
  - has_tuple3: 1 if all methods return Tuple3

METHODS TABLE (method-level code):
  - One row per method
  - class_id: FK to classes.id
  - method_name: name of the method
  - method_code: full Python method source code
  - params: parameter list (e.g. 'self, params')
  - signature: same as params (for quick lookup)
  - is_dunder: 1 if __dunder__ method
  - is_vbstyle: 1 if VBStyle compliant
  - returns_tuple3: 1 if returns (ok, data, error)

COMPUTATIONAL_UNITS TABLE (tightly coupled groups):
  - Groups methods that work together
  - unit_name: descriptive name (e.g. 'GraphEngine:CuriosityController')
  - unit_type: 'method_group' or 'class_group'
  - class_id: FK to classes
  - method_id: FK to methods (primary method of the group)
  - status: 'active' or 'deprecated'

BCL_IDENTITY TABLE (self-description tokens):
  - One row per entity (domain, class, method)
  - entity_type: 'domain', 'class', or 'method'
  - entity_id: FK to the entity
  - entity_name: name of the entity
  - domain: which domain it belongs to
  - bcl_token: the BCL self-description token (see what_is_bcl)
  - self_narrative: plain-text description
  - parent_id: FK to parent entity (for hierarchy)

DO NOT STORE CODE IN:
  - _db_meta (metadata only, not code)
  - _table_registry (table documentation, not code)
  - _column_docs (column documentation, not code)
  - plans (plan definitions, not code)
  - plan_steps (plan step definitions, not code)
  - orchestration (pipeline definitions, not code)
  - closure_status (closure tracking, not code)
  - violations (violation records, not code)
  - execution_log (execution records, not code)
""",

    # ─── WHAT IS BCL ───
    "what_is_bcl": """
WHAT IS BCL (Bracket Command Language)?
========================================

BCL is a self-description format. Every entity in the database
(domain, class, method) has a BCL token that lets it answer
questions about ITSELF — without needing external documentation.

BCL TOKEN STRUCTURE:
  A BCL token is a text string with labeled fields:

  [@EntityName]{
    ("identity";"who this entity is")
    ("capabilities";"what it can do")
    ("used_in_pipelines";"where it's used")
    ("depends_on";"what it needs")
    ("depended_by";"what needs it")
    ("closure";"is it complete")
    ("self_narrative";"plain text description")
    ("extends";"parent entity for inheritance")
    ("method_signature";"how to call it")
    ("breaks_if";"what breaks if this changes")
  }

THE 7 W-QUESTIONS EVERY BCL TOKEN ANSWERS:
  WHO:     identity field — who is this entity?
  WHAT:    capabilities field — what can it do?
  WHERE:   used_in_pipelines field — where is it used?
  WHEN:    closure field — when is it ready?
  WHY:     self_narrative field — why does it exist?
  HOW:     method_signature field — how do you call it?
  WHAT_IF: breaks_if field — what happens if it changes?

HOW TO MAKE BCL TOKENS:
  Use: bcl_identity_generator.py

  The generator reads the database and creates BCL tokens for:
    - Domain level: summarizes the whole domain
    - Class level: summarizes the class and its methods
    - Method level: summarizes individual methods

  Run:
    python3 bcl_identity_generator.py

  This generates BCL tokens for ALL entities and stores them
  in the bcl_identity table.

  To generate BCL for a single new domain:
    from bcl_identity_generator import generate_domain_bcl, generate_class_bcl, generate_method_bcl, store_bcl_identity

    # Domain BCL
    bcl = generate_domain_bcl(conn, 'yourdomain')
    store_bcl_identity(conn, 'domain', class_id, 'DomYourDomain', 'yourdomain', bcl, narrative)

    # Class BCL
    bcl = generate_class_bcl(conn, class_id, 'DomYourDomain', 'yourdomain', description)
    store_bcl_identity(conn, 'class', class_id, 'DomYourDomain', 'yourdomain', bcl, narrative)

    # Method BCL (for each method)
    bcl = generate_method_bcl(conn, method_id, class_id, method_name, params, returns_tuple3)
    store_bcl_identity(conn, 'method', method_id, method_name, 'yourdomain', bcl, narrative)

BCL STORAGE:
  BCL tokens are stored in the bcl_identity table.
  - Normalized: parent_id links child to parent (method → class → domain)
  - Denormalized: bcl_token field contains the full self-contained token
  - This means: one query gets the full answer, no joins needed

QUERYING BCL:
  -- Get BCL for a domain
  SELECT bcl_token FROM bcl_identity WHERE entity_type='domain' AND entity_name='DomGraphs';

  -- Search BCL for keyword
  SELECT entity_name, bcl_token FROM bcl_identity WHERE bcl_token LIKE '%compress%';

  -- Get BCL for all methods in a domain
  SELECT entity_name, bcl_token FROM bcl_identity WHERE domain='graphs' AND entity_type='method';
""",

    # ─── HOW TO VERIFY ───
    "how_to_verify": """
HOW TO VERIFY CODE AND DATABASE
================================

VERIFICATION 1: VBStyle Compliance
  Check that code follows VBStyle rules:
    SELECT kind, COUNT(*) FROM violations GROUP BY kind;
  Kinds: no_state, no_run, print, no_init, localhost, decorator, tab
  If violations exist for your code, fix them before proceeding.

VERIFICATION 2: Closure Check
  Every domain must be at 100% closure:
    SELECT domain, closure_pct, methods_missing, status FROM closure_status;
  If closure_pct < 100, implement missing methods.

VERIFICATION 3: BCL Identity Check
  Every entity must have a BCL token:
    SELECT entity_type, COUNT(*) FROM bcl_identity GROUP BY entity_type;
  Compare with:
    SELECT COUNT(*) FROM classes WHERE is_vbstyle=1;  -- should match class BCL count
    SELECT COUNT(*) FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.is_vbstyle=1;  -- should match method BCL count

VERIFICATION 4: Documentation Check
  Every table must be in _table_registry:
    SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
    EXCEPT SELECT table_name FROM _table_registry;
  Every column must be in _column_docs:
    -- Run graph_engine_v2.py to check this automatically

VERIFICATION 5: Orchestration Check
  Check which domains are used in pipelines:
    SELECT DISTINCT cl.domain FROM classes cl WHERE cl.is_vbstyle=1
    AND cl.id NOT IN (SELECT class_id FROM orchestration);
  Domains not in any pipeline are 'isolated' — not necessarily wrong, but unused.

VERIFICATION 6: Run the Graph Engine
  The ultimate verification — run the cognitive loop:
    python3 graph_engine_v2.py
  This discovers all gaps dynamically and reports them.

VERIFICATION 7: Execution Test
  If you have a plan, try executing it:
    -- Check plan steps
    SELECT sequence, step_name, method_name FROM plan_steps WHERE plan_id=? ORDER BY sequence;
    -- Log execution
    INSERT INTO execution_log (plan_id, step_sequence, status, result, executed_at)
    VALUES (plan_id, step_seq, 'OK', 'result', datetime);
""",

    # ─── ERROR HANDLING ───
    "error_handling": """
ERROR HANDLING — WHAT TO DO WHEN THINGS GO WRONG
=================================================

ERROR 1: Code fails VBStyle check
  Symptom: violations table has entries for your code
  Fix:
    - no_state: Add self.state = {} to __init__
    - no_run: Add Run(self, command, params) method with dispatch
    - print: Replace print() with return values
    - no_init: Add __init__ that sets self.state
    - localhost: Replace 'localhost'/'127.0.0.1' with config parameter
    - decorator: Remove @property, @staticmethod, @classmethod
    - tab: Replace tabs with spaces
  After fix: DELETE FROM violations WHERE class_id = your_class_id
  Re-run: VBStyle checker to confirm no new violations

ERROR 2: BCL generation fails
  Symptom: bcl_identity_generator.py throws error
  Fix:
    - Check that the entity exists in classes/methods table
    - Check that class_id is correct
    - Check that domain name matches
  Alternative: Generate BCL manually (see what_is_bcl instruction)

ERROR 3: Closure not 100%
  Symptom: closure_pct < 100 in closure_status
  Fix:
    - Check closure_methods table for what's missing
    - Implement the missing methods
    - Update closure_status: UPDATE closure_status SET methods_have=N, methods_missing=0, closure_pct=100.0 WHERE domain='yourdomain'

ERROR 4: Domain not in orchestration
  Symptom: Domain shows as 'isolated' in gap report
  Fix:
    - Create a plan that uses the domain
    - Add orchestration steps: INSERT INTO orchestration (pipeline, sequence, class_id, role, description) VALUES (...)

ERROR 5: Database is locked
  Symptom: sqlite3.OperationalError: database is locked
  Fix:
    - Close other connections to the database
    - Use WAL mode: PRAGMA journal_mode=WAL
    - Retry the operation

ERROR 6: MySQL connection fails
  Symptom: Can't connect to MySQL
  Fix:
    - Check MySQL is running: mysqladmin -u root status
    - Check credentials: root with empty password
    - Check port: 3306 (default)

ALTERNATIVE STEPS:
  If primary approach fails, try alternatives:
  1. If MySQL is down → use disk files as source
  2. If BCL generator fails → write BCL tokens manually
  3. If closure can't reach 100% → document why in closure_status.status
  4. If plan can't execute → log the error in execution_log and continue
""",

    # ─── PERMISSIONS: AM I ALLOWED? ───
    "permissions": """
PERMISSIONS — AM I ALLOWED TO DO THAT?
=======================================

ALLOWED:
  ✅ Read any table in the database
  ✅ Add new domains (INSERT INTO classes)
  ✅ Add new methods (INSERT INTO methods)
  ✅ Generate BCL tokens (INSERT INTO bcl_identity)
  ✅ Create new plans (INSERT INTO plans)
  ✅ Create orchestration recipes (INSERT INTO orchestration)
  ✅ Update closure status (UPDATE closure_status)
  ✅ Add documentation (INSERT INTO _db_meta, _table_registry, _column_docs)
  ✅ Log executions (INSERT INTO execution_log)
  ✅ Run the graph engine (python3 graph_engine_v2.py)

ALLOWED WITH CAUTION:
  ⚠️  Update existing class code (UPDATE classes SET class_code=...) — keep version history
  ⚠️  Update existing method code (UPDATE methods SET method_code=...) — keep version history
  ⚠️  Delete violations after fixing (DELETE FROM violations WHERE...) — only after fix verified

NOT ALLOWED:
  ❌ Drop tables (DROP TABLE)
  ❌ Delete entire domains without backup (DELETE FROM classes WHERE domain=...)
  ❌ Delete all BCL tokens (DELETE FROM bcl_identity)
  ❌ Delete all plans (DELETE FROM plans)
  ❌ Modify _db_meta keys that start with 'system_'
  ❌ Change database schema (ALTER TABLE) without documenting in _table_registry

REQUIRES USER CONFIRMATION:
  🔒 Deleting more than 10 rows from any table
  🔒 Dropping any table
  🔒 Changing database schema
  🔒 Modifying the architecture field in _db_meta
""",

    # ─── RULES REFERENCE ───
    "rules_reference": """
RULES REFERENCE — WHERE ARE THE RULES?
=======================================

RULES ARE STORED IN THESE LOCATIONS:

1. DATABASE META (_db_meta table):
   - This table (you are reading it now)
   - Keys: how_to_add_code, code_style_rules, where_code_goes, etc.
   - Query: SELECT key, value FROM _db_meta WHERE key LIKE '%rule%'

2. VBSTYLE RULES (this instruction set):
   - See 'code_style_rules' key in _db_meta
   - 10 rules: Run dispatch, Tuple3, no print, no decorators, etc.

3. BCL RULES:
   - See 'what_is_bcl' key in _db_meta
   - 7 W-questions: WHO, WHAT, WHERE, WHEN, WHY, HOW, WHAT_IF
   - Required fields: identity, capabilities, used_in_pipelines, depends_on, depended_by, closure, self_narrative

4. CLOSURE RULES:
   - Every domain must be at 100% closure
   - closure_pct = methods_have / methods_needed * 100
   - Check: SELECT * FROM closure_status WHERE closure_pct < 100

5. DOCUMENTATION RULES:
   - Every table must be in _table_registry
   - Every column must be in _column_docs
   - _db_meta must have: db_name, db_purpose, architecture

6. VIOLATION RULES (tracked in violations table):
   - no_state: class must have self.state dict
   - no_run: class must have Run() method
   - print: no print() statements
   - no_init: class must have __init__
   - localhost: no hardcoded localhost
   - decorator: no @property/@staticmethod/@classmethod
   - tab: no tabs in code

7. MYSQL LEARNED RULES (vb_shared.learned_rules):
   - 10,540 learned rules from past experience
   - Search: SELECT pattern, fix_action, confidence FROM learned_rules WHERE pattern LIKE '%keyword%'
   - These are rules the system has learned from fixing problems

8. GRAPH ENGINE (dynamic rule discovery):
   - Run: python3 graph_engine_v2.py
   - Discovers gaps and checks against all rules above
   - Reports violations, missing docs, broken chains, etc.
""",

    # ─── STEP-BY-STEP: COMPLETE WORKFLOW ───
    "complete_workflow": """
COMPLETE WORKFLOW — EVERY STEP, EVERY ALTERNATIVE
==================================================

SCENARIO: Adding a new domain called 'validation' to the database

STEP 1: SEARCH FOR CODE
  Primary: Search MySQL
    mysql -u root vb_code_test -e "SELECT class_name, domain FROM vb_classes WHERE class_name LIKE '%Valid%' OR domain LIKE '%valid%'"
  Alternative: Search disk
    find /path -name "*.py" | xargs grep -l "class.*Valid"
  Alternative: Search CODEBASE
    mysql -u root CODEBASE -e "SELECT filename FROM python_files WHERE filename LIKE '%valid%'"

STEP 2: VERIFY CODE IS VBSTYLE
  Check: Does it have Run()? Does it return Tuple3? No print()? No decorators?
  If not VBStyle: Convert it (add Run dispatch, wrap returns in Tuple3)
  If already VBStyle: Proceed to step 3

STEP 3: STORE IN DATABASE
  INSERT INTO classes (class_name, class_code, domain, description, source_file, is_vbstyle, has_run_method, has_tuple3, version, created_at)
  VALUES ('DomValidation', code, 'validation', 'Validation domain', 'mysql_vb_code_test', 1, 1, 1, 1, datetime);
  Get class_id = last_insert_rowid()

  For each method:
  INSERT INTO methods (class_id, method_name, method_code, params, signature, is_dunder, is_vbstyle, returns_tuple3, version, created_at)
  VALUES (class_id, 'MethodName', code, 'self, params', 'self, params', 0, 1, 1, 1, datetime);

STEP 4: CREATE COMPUTATIONAL UNITS
  Group tightly coupled methods:
  INSERT INTO computational_units (unit_name, unit_type, class_id, method_id, description, status)
  VALUES ('Validation:Checker', 'method_group', class_id, method_id, 'Validation checker', 'active');

STEP 5: GENERATE BCL IDENTITY
  Run: python3 bcl_identity_generator.py
  Or manually:
    from bcl_identity_generator import generate_domain_bcl, store_bcl_identity
    bcl = generate_domain_bcl(conn, 'validation')
    store_bcl_identity(conn, 'domain', class_id, 'DomValidation', 'validation', bcl, narrative)

  ALTERNATIVE if generator fails:
    Write BCL token manually with all 7 W-question fields
    INSERT INTO bcl_identity (entity_type, entity_id, entity_name, domain, bcl_token, self_narrative, parent_id)
    VALUES ('domain', class_id, 'DomValidation', 'validation', '[@DomValidation]{...}', 'narrative', NULL);

STEP 6: UPDATE CLOSURE
  INSERT INTO closure_status (domain, methods_needed, methods_have, methods_missing, closure_pct, status)
  VALUES ('validation', N, N, 0, 100.0, 'closed');

  ALTERNATIVE if not all methods implemented:
  Set closure_pct = (have/needed)*100, status = 'partial'

STEP 7: DOCUMENT
  Add to _table_registry if you created new tables
  Add to _column_docs for new columns
  Update _db_meta if architecture changed

STEP 8: CREATE PLAN (if domain should be used in a pipeline)
  INSERT INTO plans (name, goal, expected_outcome, status, version)
  VALUES ('run_validation', 'Validate data', 'Validation report', 'ready', 1);
  INSERT INTO plan_steps (plan_id, sequence, step_name, class_id, method_name, description, produces, consumes)
  VALUES (plan_id, 1, 'validate', class_id, 'Validate', 'Validate input data', 'validation_result', 'input_data');

STEP 9: CREATE ORCHESTRATION
  INSERT INTO orchestration (pipeline, sequence, class_id, role, description)
  VALUES ('validation_pipeline', 1, class_id, 'validate', 'Validate input data');

STEP 10: VERIFY
  Run: python3 graph_engine_v2.py
  Check: No new gaps introduced
  Check: BCL tokens generated
  Check: Closure at 100%
  Check: No VBStyle violations

STEP 11: LOG
  If you executed anything:
  INSERT INTO execution_log (plan_id, step_sequence, status, result, executed_at)
  VALUES (plan_id, 1, 'OK', 'success', datetime);

ERROR RECOVERY AT EACH STEP:
  Step 1 fails → try alternative source (disk, CODEBASE)
  Step 2 fails → convert code to VBStyle before proceeding
  Step 3 fails → check for duplicate class_name, use UPDATE if exists
  Step 4 fails → skip (CUs are optional)
  Step 5 fails → write BCL manually
  Step 6 fails → set partial closure, document why
  Step 7 fails → skip (documentation can be added later)
  Step 8 fails → skip (plan is optional)
  Step 9 fails → skip (orchestration is optional)
  Step 10 fails → fix gaps before proceeding
  Step 11 fails → log the error and continue
""",
}


# ════════════════════════════════════════════════════════════════════════
# STORE INSTRUCTIONS IN DATABASE
# ════════════════════════════════════════════════════════════════════════

def populate_instructions(conn):
    """Store all instructions in _db_meta table."""
    c = conn.cursor()

    stored = 0
    updated = 0

    for key, value in INSTRUCTIONS.items():
        # Check if key already exists
        c.execute("SELECT value FROM _db_meta WHERE key=?", (key,))
        existing = c.fetchone()

        if existing:
            # Update
            c.execute("UPDATE _db_meta SET value=? WHERE key=?", (value, key))
            updated += 1
        else:
            # Insert
            c.execute("INSERT INTO _db_meta (key, value) VALUES (?, ?)", (key, value))
            stored += 1

    conn.commit()
    return stored, updated


def verify_instructions(conn):
    """Verify all instruction keys are present."""
    c = conn.cursor()
    c.execute("SELECT key FROM _db_meta")
    existing = set(r[0] for r in c.fetchall())

    required = set(INSTRUCTIONS.keys())
    missing = required - existing
    extra = existing - required

    return missing, extra


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("POPULATING v20 DATABASE WITH AI INSTRUCTIONS")
    print("=" * 70)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Instructions to store: {len(INSTRUCTIONS)}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Store instructions
    print("[1] Storing instructions in _db_meta...")
    stored, updated = populate_instructions(conn)
    print(f"    Stored: {stored} new keys")
    print(f"    Updated: {updated} existing keys")

    # Verify
    print("\n[2] Verifying all instructions present...")
    missing, extra = verify_instructions(conn)
    if missing:
        print(f"    ⚠️  Missing: {missing}")
    else:
        print(f"    ✅ All {len(INSTRUCTIONS)} instruction keys present")
    if extra:
        print(f"    Extra keys in _db_meta: {extra}")

    # Show what's available
    print("\n[3] Instruction set now available in _db_meta:")
    c = conn.cursor()
    c.execute("SELECT key, LENGTH(value) as len FROM _db_meta ORDER BY key")
    for row in c.fetchall():
        print(f"    {row['key']:30} {row['len']:>6} chars")

    # Show how any AI can query this
    print("\n[4] How any AI can query the instructions:")
    print("    -- Get all instructions")
    print("    SELECT key, value FROM _db_meta;")
    print("")
    print("    -- Get specific instruction")
    print("    SELECT value FROM _db_meta WHERE key='how_to_add_code';")
    print("")
    print("    -- Search for keyword")
    print("    SELECT key, value FROM _db_meta WHERE value LIKE '%VBStyle%';")
    print("")
    print("    -- Get BCL instructions")
    print("    SELECT value FROM _db_meta WHERE key='what_is_bcl';")

    # Count total
    c.execute("SELECT COUNT(*) FROM _db_meta")
    total = c.fetchone()[0]
    c.execute("SELECT SUM(LENGTH(value)) FROM _db_meta")
    total_chars = c.fetchone()[0]

    print(f"\n[5] Summary:")
    print(f"    Total _db_meta entries: {total}")
    print(f"    Total instruction text: {total_chars:,} chars")
    print(f"    Any AI can now learn how to use this database by reading _db_meta")

    print("\n" + "=" * 70)
    print("DATABASE IS NOW SELF-TEACHING")
    print("=" * 70)
    print("""
  Any AI that opens this database can now answer:

  ✅ How do I add more domain code?     → key: how_to_add_code
  ✅ Where do I get code from?          → key: where_to_get_code
  ✅ What code style is required?       → key: code_style_rules
  ✅ Where must code go?                → key: where_code_goes
  ✅ What rules must be followed?       → key: rules_reference
  ✅ How do I verify?                   → key: how_to_verify
  ✅ What is BCL? How do I make it?     → key: what_is_bcl
  ✅ What happens on error?             → key: error_handling
  ✅ Am I allowed to do that?           → key: permissions
  ✅ Complete step-by-step workflow?    → key: complete_workflow

  Query: SELECT value FROM _db_meta WHERE key='<instruction_name>';
""")

    conn.close()


if __name__ == "__main__":
    main()
