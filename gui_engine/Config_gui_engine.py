#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_gui_engine.py>][@domain<gui_engine>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for gui_engine domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- File Inventory --------------------------------------------
    # -- Config.py --
    # Purpose: N/A
    # Lines: 0 | Classes: 0 | Methods: 0
    #   VBStyle: NO_Run | NO_init | NO_state | no_print | no_decorator

    # -- config_extractor.py --
    # Purpose: ConfigExtractor — regex-based, no AST needed.
    # Lines: 275 | Classes: 0 | Methods: 7
    #   Functions: extract_from_file, parse_literal, is_config_string, is_config_number, safe_name, safe_name_num, generate_config
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- edge_case_test.py --
    # Purpose: Edge case test file for config_extractor.py
    # Lines: 121 | Classes: 3 | Methods: 0
    #   Class: TestWidget -- methods: __init__, configure, render, _get_style, load_config
    #   Class: OuterClass -- methods: __init__
    #   Class: InnerAuthority -- methods: Run, read_state
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- gui_engine.py --
    # Purpose: N/A
    # Lines: 0 | Classes: 0 | Methods: 0
    #   VBStyle: NO_Run | init | NO_state | PRINT | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "Config.py": {
        "purpose": "",
        "lines": 0,
        "classes": [],
        "methods": [],
    },
    "config_extractor.py": {
        "purpose": "ConfigExtractor — regex-based, no AST needed.",
        "lines": 275,
        "classes": [],
        "methods": ["extract_from_file", "parse_literal", "is_config_string", "is_config_number", "safe_name", "safe_name_num", "generate_config"],
    },
    "edge_case_test.py": {
        "purpose": "Edge case test file for config_extractor.py",
        "lines": 121,
        "classes": ["TestWidget", "OuterClass", "InnerAuthority"],
        "methods": [],
    },
    "gui_engine.py": {
        "purpose": "",
        "lines": 0,
        "classes": [],
        "methods": [],
    },
}
# -- Classes Dict ----------------------------------------------
CLASSES = {
    "TestWidget": {
        "file": "edge_case_test.py",
        "methods": ["__init__", "configure", "render", "_get_style", "load_config"],
    },
    "OuterClass": {
        "file": "edge_case_test.py",
        "methods": ["__init__"],
    },
    "InnerAuthority": {
        "file": "edge_case_test.py",
        "methods": ["Run", "read_state"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 4,
    "files_with_Run": 1,
    "files_with_state": 1,
    "files_with_print": 2,
    "files_with_decorator": 0,
    "pass_rate": 25.0,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "gui_engine"
FILE_COUNT = 4
CLASS_COUNT = 3
