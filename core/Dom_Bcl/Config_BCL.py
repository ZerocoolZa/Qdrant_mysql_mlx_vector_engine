#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_BCL.py>][@domain<BCL>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for BCL domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- File Inventory --------------------------------------------
    # -- bcl_config.py --
    # Purpose: BCL Config — Rules for Bracket Command Language validation.
    # Lines: 261 | Classes: 0 | Methods: 6
    #   Functions: validate_container_name, validate_weight, validate_tuple, validate_node, validate_bcl_text, validate_all
    #   VBStyle: NO_Run | NO_init | NO_state | no_print | no_decorator

    # -- bcl_crud.py --
    # Purpose: BCL CRUD — Thin CLI wrapper for the BCL Engine.
    # Lines: 511 | Classes: 0 | Methods: 2
    #   Functions: cli, demo
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- bcl_engine.py --
    # Purpose: BCL Engine — Stage 5: Orchestrator
    # Lines: 461 | Classes: 2 | Methods: 2
    #   Class: EngineResult -- methods: __init__, ok, summary, _count_nodes
    #   Class: BCLEngine -- methods: __init__, _enter_stage, run, load_file, save_file, _serialize, create, update, delete, read
    #   Functions: clone_ast, ast_hash
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- bcl_fixer.py --
    # Purpose: BCL Fixer — Stage 4: Controlled Mutation Engine
    # Lines: 277 | Classes: 2 | Methods: 0
    #   Class: FixAction -- methods: __init__, __repr__
    #   Class: BCLFixer -- methods: fix, restore, _get_handler, _fix_container_name, _fix_weight, _find_by_path, cleanup_empty
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- bcl_lexer.py --
    # Purpose: BCL Lexer — Stage 1: Tokenizer
    # Lines: 180 | Classes: 3 | Methods: 0
    #   Class: TokenType -- methods: 
    #   Class: Token -- methods: __init__, __repr__
    #   Class: BCLTokenizer -- methods: __init__, _error, _peek, _advance, _skip_whitespace, tokenize, _lex_container_name, _lex_string, _lex_number, _lex_bareword
    #   VBStyle: NO_Run | init | NO_state | no_print | no_decorator

    # -- bcl_parser.py --
    # Purpose: BCL Parser — Stage 2: AST Builder
    # Lines: 238 | Classes: 2 | Methods: 1
    #   Class: BCLNode -- methods: __init__, path, get, get_weight, set, to_bcl, __repr__
    #   Class: BCLParser -- methods: __init__, _peek, _advance, _expect, parse, _parse_container, _parse_container_body, _parse_tuple
    #   Functions: parse_text
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- bcl_validator.py --
    # Purpose: BCL Validator — Stage 3: Check Layer
    # Lines: 326 | Classes: 3 | Methods: 0
    #   Class: Violation -- methods: __init__, __repr__
    #   Class: ValidationReport -- methods: __init__, add, ok, summary
    #   Class: BCLValidator -- methods: validate, validate_text, _validate_node, _check_container_name, _check_weights, _check_duplicate_siblings, _check_branch_pairs, _check_circular_ref
    #   VBStyle: NO_Run | init | NO_state | no_print | DECOR

    # -- config.py --
    # Purpose: N/A
    # Lines: 4393 | Classes: 1 | Methods: 0
    #   Class: Config -- methods: GetPath, GetAbout, GetHelp, GetReadme, GetTooltip, GetTheme, GetTurnJs, GetThemeCss, GetIcon, GetShortcut
    #   VBStyle: NO_Run | NO_init | state | no_print | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "bcl_config.py": {
        "purpose": "BCL Config — Rules for Bracket Command Language validation.",
        "lines": 261,
        "classes": [],
        "methods": ["validate_container_name", "validate_weight", "validate_tuple", "validate_node", "validate_bcl_text", "validate_all"],
    },
    "bcl_crud.py": {
        "purpose": "BCL CRUD — Thin CLI wrapper for the BCL Engine.",
        "lines": 511,
        "classes": [],
        "methods": ["cli", "demo"],
    },
    "bcl_engine.py": {
        "purpose": "BCL Engine — Stage 5: Orchestrator",
        "lines": 461,
        "classes": ["EngineResult", "BCLEngine"],
        "methods": ["clone_ast", "ast_hash"],
    },
    "bcl_fixer.py": {
        "purpose": "BCL Fixer — Stage 4: Controlled Mutation Engine",
        "lines": 277,
        "classes": ["FixAction", "BCLFixer"],
        "methods": [],
    },
    "bcl_lexer.py": {
        "purpose": "BCL Lexer — Stage 1: Tokenizer",
        "lines": 180,
        "classes": ["TokenType", "Token", "BCLTokenizer"],
        "methods": [],
    },
    "bcl_parser.py": {
        "purpose": "BCL Parser — Stage 2: AST Builder",
        "lines": 238,
        "classes": ["BCLNode", "BCLParser"],
        "methods": ["parse_text"],
    },
    "bcl_validator.py": {
        "purpose": "BCL Validator — Stage 3: Check Layer",
        "lines": 326,
        "classes": ["Violation", "ValidationReport", "BCLValidator"],
        "methods": [],
    },
    "config.py": {
        "purpose": "",
        "lines": 4393,
        "classes": ["Config"],
        "methods": [],
    },
}
# -- Classes Dict ----------------------------------------------
CLASSES = {
    "EngineResult": {
        "file": "bcl_engine.py",
        "methods": ["__init__", "ok", "summary", "_count_nodes"],
    },
    "BCLEngine": {
        "file": "bcl_engine.py",
        "methods": ["__init__", "_enter_stage", "run", "load_file", "save_file", "_serialize", "create", "update", "delete", "read", "list_all", "_find_by_name"],
    },
    "FixAction": {
        "file": "bcl_fixer.py",
        "methods": ["__init__", "__repr__"],
    },
    "BCLFixer": {
        "file": "bcl_fixer.py",
        "methods": ["fix", "restore", "_get_handler", "_fix_container_name", "_fix_weight", "_find_by_path", "cleanup_empty"],
    },
    "TokenType": {
        "file": "bcl_lexer.py",
        "methods": [],
    },
    "Token": {
        "file": "bcl_lexer.py",
        "methods": ["__init__", "__repr__"],
    },
    "BCLTokenizer": {
        "file": "bcl_lexer.py",
        "methods": ["__init__", "_error", "_peek", "_advance", "_skip_whitespace", "tokenize", "_lex_container_name", "_lex_string", "_lex_number", "_lex_bareword"],
    },
    "BCLNode": {
        "file": "bcl_parser.py",
        "methods": ["__init__", "path", "get", "get_weight", "set", "to_bcl", "__repr__"],
    },
    "BCLParser": {
        "file": "bcl_parser.py",
        "methods": ["__init__", "_peek", "_advance", "_expect", "parse", "_parse_container", "_parse_container_body", "_parse_tuple"],
    },
    "Violation": {
        "file": "bcl_validator.py",
        "methods": ["__init__", "__repr__"],
    },
    "ValidationReport": {
        "file": "bcl_validator.py",
        "methods": ["__init__", "add", "ok", "summary"],
    },
    "BCLValidator": {
        "file": "bcl_validator.py",
        "methods": ["validate", "validate_text", "_validate_node", "_check_container_name", "_check_weights", "_check_duplicate_siblings", "_check_branch_pairs", "_check_circular_ref"],
    },
    "Config": {
        "file": "config.py",
        "methods": ["GetPath", "GetAbout", "GetHelp", "GetReadme", "GetTooltip", "GetTheme", "GetTurnJs", "GetThemeCss", "GetIcon", "GetShortcut", "GetButton", "GetMenu", "GetWindow", "GetSearch", "GetAnnotation", "GetFlipbook", "GetTts", "GetStatus", "GetError", "GetAllSettings"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 8,
    "files_with_Run": 0,
    "files_with_state": 1,
    "files_with_print": 1,
    "files_with_decorator": 3,
    "pass_rate": 0.0,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "BCL"
FILE_COUNT = 8
CLASS_COUNT = 13
