#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Vbs_Code_Verifiation.py>][@domain<Vbs_Code_Verifiation>][@role<config>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for Vbs_Code_Verifiation domain.
All constants, regexes, rules, and MySQL config for the VBStyle Domain Scanner.
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BCL_DIR = os.path.join(REPO_ROOT, "BCL")

DEFAULT_DOMAINS_DIR = os.path.join(REPO_ROOT, "code_store_variations")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "Vbstyle_Dom_Registry.md")

MYSQL_CONFIG = {
    "user": "root",
    "host": "localhost",
    "port": 3306,
    "database": "vb_shared",
}

BOILERPLATE_METHODS = {"__init__", "Run", "read_state", "set_config"}

HEADER_RE = re.compile(r'^\s*#\[@(\w+)\]\{(.+)\}')
CLASS_RE = re.compile(r'^(\s*)class\s+(\w+)')
DEF_RE = re.compile(r'^(\s+)def\s+(\w+)\((.*)\)')
BCL_HEADER_START_RE = re.compile(r'^\s*#\[@(\w+)\]')

PURPOSE_RE = re.compile(r'@purpose<([^>]+)>')
PARAMS_RE = re.compile(r'@params<<([^>]*)>')
RETURN_RE = re.compile(r'@return<([^>]+)>')

GHOST_RE = re.compile(r'#\[@GHOST\]', re.IGNORECASE)
VBSTYLE_RE = re.compile(r'#\[@VBSTYLE\]', re.IGNORECASE)
SUMMARY_RE = re.compile(r'#\[@SUMMARY\]', re.IGNORECASE)
CLASS_HEADER_RE = re.compile(r'#\[@CLASS\]', re.IGNORECASE)
METHOD_HEADER_RE = re.compile(r'#\[@METHOD\]', re.IGNORECASE)
TUPLE3_RE = re.compile(r'Tuple3|tuple3', re.IGNORECASE)
STATE_DICT_RE = re.compile(r'self\.state\s*=')
RUN_DISPATCH_RE = re.compile(r'def\s+Run\s*\(')
READ_STATE_RE = re.compile(r'def\s+read_state\s*\(')
SET_CONFIG_RE = re.compile(r'def\s+set_config\s*\(')
INIT_RE = re.compile(r'def\s+__init__\s*\(')
DECORATOR_RE = re.compile(r'^\s*@(?:staticmethod|classmethod|property|abstractmethod|functools)')
PRINT_RE = re.compile(r'\bprint\s*\(')
SELF_UNDERSCORE_RE = re.compile(r'self\._[a-z]')
HARDCODED_PATH_RE = re.compile(r'["\']/(?:Users|home|tmp|var|opt)/')
TAB_RE = re.compile(r'\t')

VBSTYLE_RULES = [
    ("ghost_header", "Has #[@GHOST] header"),
    ("vbstyle_header", "Has #[@VBSTYLE] annotation"),
    ("summary_header", "Has #[@SUMMARY] header"),
    ("class_header", "Has #[@CLASS] header"),
    ("method_header", "Has #[@METHOD] header"),
    ("tuple3_return", "Returns Tuple3"),
    ("state_dict", "Uses self.state dict"),
    ("run_dispatch", "Has Run() dispatch"),
    ("init_method", "Has __init__(self, mem, db, param)"),
    ("read_state_method", "Has read_state() method"),
    ("set_config_method", "Has set_config() method"),
    ("no_decorators", "No decorators"),
    ("no_print", "No print statements"),
    ("no_self_underscore", "No self._ variables"),
    ("no_hardcoded_paths", "No hardcoded paths"),
    ("no_tabs", "No tab indentation"),
    # DomSystem rules (captured 2026-06-28)
    ("dom_system_authority", "DomSystem is sole service authority, no macOS launchd/brew"),
    ("dom_service_mode", "Service has mode: transient/batch/constant/pinned"),
    ("dom_acquire_release", "Code acquires before use, releases when done"),
    ("dom_adaptive_timeout", "Idle timeout auto-extends by acquire frequency"),
    ("dom_retire_plist", "retire_plist moves plists out of LaunchAgents"),
    ("dom_launch_modes", "direct/launchd/always/brew launch modes"),
    ("dom_package_gate", "Package install via DomSystem, not direct pip"),
    ("dom_config_override", "App overrides via param, not by editing Config.py"),
    ("dom_no_delegated_self_underscore", "Delegated objects in self.state, not self._pm"),
    ("dom_health_check_process", "Process-pattern health check for portless services"),
    ("dom_deps", "Services declare deps, acquire loads deps first"),
    ("dom_ram_budget", "acquire checks RAM budget before starting"),
    # Domain scanning rules (captured 2026-06-28)
    ("domain_must_be_scanned", "Every Dom_* folder must be scanned by VbsMain.Run('scan') to produce FILE_REGISTER, CLASS_INDEX, BOOT_SPINE, DEPENDENCY_GRAPH"),
    ("domain_config_must_have_file_register", "Every domain Config.py must contain a FILE_REGISTER dict mapping each .py file to its class, role, purpose, lines, methods, deps, imports, vbstyle, run_commands"),
    ("domain_config_must_have_class_index", "Every domain Config.py must contain a CLASS_INDEX dict mapping class names to their file and role"),
    ("domain_config_must_have_boot_spine", "Every domain Config.py must contain a BOOT_SPINE list defining the load order of files in the domain"),
    ("domain_config_must_have_dependency_graph", "Every domain Config.py must contain a DEPENDENCY_GRAPH dict mapping each file to the files it imports from the domain"),
    ("domain_must_have_pipeline_doc", "Every Dom_* folder must have a corresponding DOM_*_PIPELINE.md in core/Piplines/ with full breakdown: file map, classes, methods, boot spine, dependency graph, pipeline stages, entry points"),
    ("pipeline_doc_must_have_file_register", "Every pipeline .md must contain a file register section mapping each file to its class, role, purpose, lines, methods, run_commands"),
    ("pipeline_doc_must_have_class_index", "Every pipeline .md must contain a class index section mapping class names to their file and role"),
    ("pipeline_doc_must_have_boot_spine", "Every pipeline .md must contain a boot spine section defining the load order of files in the domain"),
    ("pipeline_doc_must_have_dependency_graph", "Every pipeline .md must contain a dependency graph section mapping each file to the files it imports from the domain"),
    ("pipeline_doc_must_have_pipeline_stages", "Every pipeline .md must contain a pipeline stages section defining what comes first, what goes second, and what each stage does"),
    ("pipeline_doc_must_have_entry_points", "Every pipeline .md must contain an entry points section with runnable commands for CLI, Python, GUI, and tests"),
]

COMPLIANCE_KEYS = [
    "ghost_header", "vbstyle_header", "summary_header", "class_header",
    "method_header", "tuple3_return", "state_dict", "run_dispatch",
    "init_method", "read_state_method", "set_config_method",
    "no_decorators", "no_print", "no_self_underscore",
    "no_hardcoded_paths", "no_tabs",
    "dom_system_authority", "dom_service_mode", "dom_acquire_release",
    "dom_adaptive_timeout", "dom_retire_plist", "dom_launch_modes",
    "dom_package_gate", "dom_config_override", "dom_no_delegated_self_underscore",
    "dom_health_check_process", "dom_deps", "dom_ram_budget",
    "domain_must_be_scanned", "domain_config_must_have_file_register",
    "domain_config_must_have_class_index", "domain_config_must_have_boot_spine",
    "domain_config_must_have_dependency_graph", "domain_must_have_pipeline_doc",
    "pipeline_doc_must_have_file_register", "pipeline_doc_must_have_class_index",
    "pipeline_doc_must_have_boot_spine", "pipeline_doc_must_have_dependency_graph",
    "pipeline_doc_must_have_pipeline_stages", "pipeline_doc_must_have_entry_points",
]

DOMAIN = "Vbs_Code_Verifiation"

# ── File Register ────────────────────────────────────────────
# Each .py file in the domain with full metadata.
# class = primary class, methods = count, lines = count, deps = imports

FILE_REGISTER = {
    "Config_Vbs_Code_Verifiation.py": {
        "class": "Config",
        "role": "config",
        "purpose": "Constants, regexes, rules, MySQL config, file register, rule engine config, domain metadata",
        "lines": 277,
        "methods": 0,
        "deps": ["os", "re"],
        "imports": [],
        "vbstyle": True,
    },
    "vbs_parser.py": {
        "class": "Parser",
        "role": "analysis",
        "purpose": "Parse Python files, BCL headers, markdown documents. Read, edit, update parsed structures.",
        "lines": 476,
        "methods": 13,
        "deps": ["os", "re", "sys", "Config_Vbs_Code_Verifiation", "bcl_lexer", "bcl_parser", "bcl_validator"],
        "imports": ["Config_Vbs_Code_Verifiation as Config"],
        "vbstyle": True,
        "run_commands": "parse_file, parse_header, parse_document, extract_header, extract_fields, clean_params, read_parsed, update_parsed, edit_header, read_state, set_config",
    },
    "vbs_compliance.py": {
        "class": "Compliance",
        "role": "validation",
        "purpose": "Check, create, edit, update VBStyle compliance rules and results. Full CRUD on rules.",
        "lines": 194,
        "methods": 13,
        "deps": ["Config_Vbs_Code_Verifiation"],
        "imports": ["Config_Vbs_Code_Verifiation as Config"],
        "vbstyle": True,
        "run_commands": "check, check_lines, compliance_icon, create_rule, edit_rule, update_rule, read_rules, read_result, update_result, read_state, set_config",
    },
    "vbs_code_index.py": {
        "class": "CodeIndex",
        "role": "storage",
        "purpose": "Read, write, edit, update MySQL code_index entries. Full CRUD on facts, classes, methods, authorities.",
        "lines": 380,
        "methods": 16,
        "deps": ["json", "math", "collections", "mysql.connector", "Config_Vbs_Code_Verifiation"],
        "imports": ["Config_Vbs_Code_Verifiation as Config"],
        "vbstyle": True,
        "run_commands": "open, close, write_fact, read_fact, update_fact, edit_fact, write_co_occurrence, flush_co_occurrence, flush_identifier_frequency, write_class, write_method, write_authority, read_state, set_config",
    },
    "vbs_registry.py": {
        "class": "Registry",
        "role": "reporting",
        "purpose": "Read, write, edit, update registry output. Format trees, index domains to MySQL.",
        "lines": 406,
        "methods": 12,
        "deps": ["os", "Config_Vbs_Code_Verifiation"],
        "imports": ["Config_Vbs_Code_Verifiation as Config"],
        "vbstyle": True,
        "run_commands": "write, read, edit, update, format_tree, index_domain, read_state, set_config",
    },
    "vbs_rule_engine.py": {
        "class": "RuleEngine",
        "role": "rules_authority",
        "purpose": "Authority over VBStyle rules. Extract rules from .md sources, load canonical rule_tokens, analyse gap/duplicate/conflict, search, propose, create, edit, fix. Writes are dry_run by default and dedup-gated per [@MetaOneConcept].",
        "lines": 513,
        "methods": 18,
        "deps": ["re", "mysql.connector", "Config_Vbs_Code_Verifiation"],
        "imports": ["Config_Vbs_Code_Verifiation as Config"],
        "vbstyle": True,
        "run_commands": "open, close, signature, score_match, extract, extract_all, load_tokens, best_match, analyze, detect_duplicates, detect_conflicts, search, propose, create, edit, fix, read_state, set_config",
    },
    "vbs_main.py": {
        "class": "VbsMain",
        "role": "orchestration",
        "purpose": "Entry point. Wires Parser, Compliance, CodeIndex, Registry. Run(scan) dispatch.",
        "lines": 150,
        "methods": 5,
        "deps": ["os", "sys", "Config_Vbs_Code_Verifiation", "vbs_parser", "vbs_compliance", "vbs_code_index", "vbs_registry"],
        "imports": [
            "Config_Vbs_Code_Verifiation as Config",
            "vbs_parser.Parser",
            "vbs_compliance.Compliance",
            "vbs_code_index.CodeIndex",
            "vbs_registry.Registry",
        ],
        "vbstyle": True,
        "run_commands": "scan, read_state, set_config",
    },
}

# ── Class Index ──────────────────────────────────────────────
# Maps class names to their file and role for quick lookup.

CLASS_INDEX = {
    "Config": {"file": "Config_Vbs_Code_Verifiation.py", "role": "config"},
    "Parser": {"file": "vbs_parser.py", "role": "analysis"},
    "Compliance": {"file": "vbs_compliance.py", "role": "validation"},
    "CodeIndex": {"file": "vbs_code_index.py", "role": "storage"},
    "Registry": {"file": "vbs_registry.py", "role": "reporting"},
    "RuleEngine": {"file": "vbs_rule_engine.py", "role": "rules_authority"},
    "VbsMain": {"file": "vbs_main.py", "role": "orchestration"},
}

# ── Domain Summary ───────────────────────────────────────────
CLASS_COUNT = 7
FILE_COUNT = 7
TOTAL_LINES = 2290
TOTAL_METHODS = 77

# ── Boot Spine ───────────────────────────────────────────────
# Config -> Parser -> Compliance -> CodeIndex -> Registry -> VbsMain
BOOT_SPINE = [
    "Config_Vbs_Code_Verifiation.py",
    "vbs_parser.py",
    "vbs_compliance.py",
    "vbs_code_index.py",
    "vbs_registry.py",
    "vbs_rule_engine.py",
    "vbs_main.py",
]

# ── Dependency Graph ─────────────────────────────────────────
# file -> files it imports from this domain
DEPENDENCY_GRAPH = {
    "Config_Vbs_Code_Verifiation.py": [],
    "vbs_parser.py": ["Config_Vbs_Code_Verifiation.py"],
    "vbs_compliance.py": ["Config_Vbs_Code_Verifiation.py"],
    "vbs_code_index.py": ["Config_Vbs_Code_Verifiation.py"],
    "vbs_registry.py": ["Config_Vbs_Code_Verifiation.py"],
    "vbs_rule_engine.py": ["Config_Vbs_Code_Verifiation.py"],
    "vbs_main.py": ["Config_Vbs_Code_Verifiation.py", "vbs_parser.py", "vbs_compliance.py", "vbs_code_index.py", "vbs_registry.py"],
}

# ═════════════════════════════════════════════════════════════
# RULE ENGINE — config for vbs_rule_engine.RuleEngine
# Canonical store for ALL VBStyle rules is vb_shared.rule_tokens.
# ═════════════════════════════════════════════════════════════

# Canonical token store (the ONE place all rules live)
RULE_TOKENS_TABLE = "rule_tokens"

# Default weight appended to every BCL token body (per [@WeightPosition])
RULE_TOKEN_WEIGHT = 92

# .md rule source files to extract rules from
RULE_SOURCE_FILES = {
    "obey.md": "/Users/wws/contestsystem/.devin/rules/obey.md",
    "vbstyle_rules.md": os.path.join(REPO_ROOT, ".devin", "rules", "vbstyle_rules.md"),
    "config_file_rule.md": os.path.join(REPO_ROOT, ".devin", "rules", "config_file_rule.md"),
}

# Regex to extract obey.md tagged rules:  - [@tag] ("body";"body")
OBEY_TAG_RE = re.compile(r'^\s*-\s*\[@(\w+)\]\s*\((.+)\)\s*$')

# Regex to extract sectioned rules:  ### R1 — text  /  ### H2 — text
SECTION_RULE_RE = re.compile(r'^\s*###\s+([A-Z]{1,4}\d+)\s*[\u2014\-]?\s*(.*)')

# Valid rule_tokens categories (existing taxonomy — do NOT invent new ones)
RULE_CATEGORIES = [
    "Architecture", "State", "Method", "Forbidden", "Format", "Naming",
    "Paths", "Database", "FileOps", "Workflow", "Meta", "Other", "GUI",
]

# Words ignored when computing a rule's concept signature for dedup matching.
# Includes generic rule-prose words that otherwise cause false concept matches
# (e.g. "without"/"explicit" matching unrelated tokens).
RULE_STOPWORDS = {
    "the", "a", "an", "and", "or", "no", "not", "must", "use", "all", "any",
    "be", "is", "are", "of", "to", "in", "on", "for", "with", "this", "that",
    "each", "every", "from", "by", "if", "then", "do", "does", "it", "its",
    "as", "at", "per", "via", "into", "may", "can", "has", "have", "rule",
    "rules", "file", "files", "code", "class", "classes", "method", "methods",
    "value", "values", "name", "names",
    # generic rule-prose words (high frequency, low concept signal)
    "without", "explicit", "explicitly", "user", "ever", "before", "after",
    "should", "never", "only", "always", "when", "which", "what", "where",
    "other", "another", "their", "they", "them", "must", "needs", "need",
    "using", "used", "make", "made", "real", "own", "owns", "owner", "new",
    "old", "same", "more", "less", "than", "between", "within", "across",
    "unless", "until", "while", "about", "based", "shape", "shapes", "thing",
}

# Concept-overlap thresholds for gap classification (report)
RULE_MATCH_COVERED = 0.50
RULE_MATCH_WEAK = 0.25

# Dedup BLOCK threshold (create refusal). Higher than COVERED on purpose:
# blocking a new token requires a strong, precise concept match, not a
# loose lexical overlap. False blocks are worse than a manual review.
RULE_DEDUP_BLOCK = 0.85

# Minimum distinctive (len>=RULE_DISTINCTIVE_LEN) shared words required
# before a create is blocked as a duplicate.
RULE_DEDUP_MIN_DISTINCTIVE = 2

# Minimum word length to count as a distinctive concept word
RULE_DISTINCTIVE_LEN = 5

# Known conflicting concepts that share a keyword but mean opposite things.
# The engine flags these so a new token is never confused with an existing one.
RULE_CONFLICT_PAIRS = [
    ("[@BulkInserts]", "@nobulk", "bulk",
     "[@BulkInserts] = SQL executemany performance. @nobulk = no multi-target code-mod scripts. Different domains."),
]

# Meta-governance token names that define the anti-duplication law
RULE_META_TOKENS = [
    "[@MetaOneConcept]", "[@MetaCheckFirst]", "[@MetaNoDupBody]",
    "[@MetaGroupDomain]", "[@MetaNameIsConcept]", "[@MetaNoPrefix]",
]
