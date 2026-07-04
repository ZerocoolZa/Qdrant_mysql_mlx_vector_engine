#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_BookSystem.py>][@domain<BookSystem>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for BookSystem domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- File Inventory --------------------------------------------
    # -- BgeSearch.py --
    # Purpose: BgeSearch.py — BGE semantic search over VBStyle document chunks.
    # Lines: 105 | Classes: 0 | Methods: 3
    #   Functions: Load, Search, Run
    #   VBStyle: Run | NO_init | NO_state | PRINT | no_decorator

    # -- Book.py --
    # Purpose: N/A
    # Lines: 4932 | Classes: 1 | Methods: 4
    #   Class: Book -- methods: __init__, _p, Run, dispatch, OpenDB, CloseDB, Init, Stats, AddPart, AddChapter
    #   Functions: parse_argv, write_about, write_help, main
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- BookViewer.py --
    # Purpose: N/A
    # Lines: 1616 | Classes: 2 | Methods: 1
    #   Class: BookBridge -- methods: __init__, saveAnnotation, getAllAnnotations, getSectionAnnotations, removeAnnotation
    #   Class: BookViewer -- methods: __init__, _p, Run, dispatch, OpenDB, BuildUI, LoadFlipbook, GenerateFlipbookHTML, PrevPage, NextPage
    #   Functions: main
    #   VBStyle: Run | init | state | no_print | DECOR

    # -- ExtractBook.py --
    # Purpose: ExtractBook.py — MySQL Evidence → VBStyle Book (v2)
    # Lines: 3299 | Classes: 1 | Methods: 1
    #   Class: BookExtractor -- methods: __init__, Connect, MineRules, MineViolations, MineClasses, MineMethods, MineBootStages, MineTablePurposes, MineObjectives, MineDocuments
    #   Functions: main
    #   VBStyle: Run | init | state | PRINT | no_decorator

    # -- config.py --
    # Purpose: N/A
    # Lines: 4393 | Classes: 1 | Methods: 0
    #   Class: Config -- methods: GetPath, GetAbout, GetHelp, GetReadme, GetTooltip, GetTheme, GetTurnJs, GetThemeCss, GetIcon, GetShortcut
    #   VBStyle: NO_Run | NO_init | state | no_print | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "BgeSearch.py": {
        "purpose": "BgeSearch.py — BGE semantic search over VBStyle document chunks.",
        "lines": 105,
        "classes": [],
        "methods": ["Load", "Search", "Run"],
    },
    "Book.py": {
        "purpose": "",
        "lines": 4932,
        "classes": ["Book"],
        "methods": ["parse_argv", "write_about", "write_help", "main"],
    },
    "BookViewer.py": {
        "purpose": "",
        "lines": 1616,
        "classes": ["BookBridge", "BookViewer"],
        "methods": ["main"],
    },
    "ExtractBook.py": {
        "purpose": "ExtractBook.py — MySQL Evidence → VBStyle Book (v2)",
        "lines": 3299,
        "classes": ["BookExtractor"],
        "methods": ["main"],
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
    "Book": {
        "file": "Book.py",
        "methods": ["__init__", "_p", "Run", "dispatch", "OpenDB", "CloseDB", "Init", "Stats", "AddPart", "AddChapter", "AddSection", "AddBlock", "AddRule", "LinkRule", "AddGlossary", "AddSummary", "AddXref", "AddTable", "UpdatePart", "UpdateChapter", "UpdateSection", "UpdateBlock", "UpdateGlossary", "UpdateRule", "RemoveSection", "RemoveBlock", "RemoveXref", "ImportMd", "ExportAll", "ExportFlipbook", "_md_to_flipbook_html", "_inline_flipbook", "Search", "Check", "AddAnnotation", "ListAnnotations", "RemoveAnnotation", "ExportChapter", "Outline", "ListRules", "ListGlossary", "ListXrefs", "Info", "ReadState", "Report", "MsearchJson", "SearchMysql", "SearchCode", "PopulateMysql", "SearchDocs", "CrossQuery", "LinkContent", "FixSummaries", "FixGlossary", "FixNames", "PopulateMilestones", "Promote", "ListAuthorities", "CheckContradictions", "ListMilestones", "WriteNarrative", "_CleanEvidence", "_GenerateNarrative", "DiscoverRelations", "Polish"],
    },
    "BookBridge": {
        "file": "BookViewer.py",
        "methods": ["__init__", "saveAnnotation", "getAllAnnotations", "getSectionAnnotations", "removeAnnotation"],
    },
    "BookViewer": {
        "file": "BookViewer.py",
        "methods": ["__init__", "_p", "Run", "dispatch", "OpenDB", "BuildUI", "LoadFlipbook", "GenerateFlipbookHTML", "PrevPage", "NextPage", "SearchInBook", "HighlightSelected", "AnnotateSelected", "OnClearSearch", "ExportHTML", "RefreshDB", "AddAnnotationDirect", "GetAllAnnotationsDirect", "GetSectionAnnotationsDirect", "RemoveAnnotationDirect", "_md_to_html", "_inline_md", "_show_error", "OnTtsToggle", "OnTtsStop", "ShowVoicePicker", "BuildDialogHeader", "BuildDialogCloseBar", "keyPressEvent", "ShowHelp", "ShowAbout"],
    },
    "BookExtractor": {
        "file": "ExtractBook.py",
        "methods": ["__init__", "Connect", "MineRules", "MineViolations", "MineClasses", "MineMethods", "MineBootStages", "MineTablePurposes", "MineObjectives", "MineDocuments", "ChunkDocuments", "_SplitByHeaders", "ExtractTruthsFromChunks", "BuildExtractedTruths", "ScanAllDocuments", "BuildMissingChapters", "BuildBook", "GapReport", "Report", "Close"],
    },
    "Config": {
        "file": "config.py",
        "methods": ["GetPath", "GetAbout", "GetHelp", "GetReadme", "GetTooltip", "GetTheme", "GetTurnJs", "GetThemeCss", "GetIcon", "GetShortcut", "GetButton", "GetMenu", "GetWindow", "GetSearch", "GetAnnotation", "GetFlipbook", "GetTts", "GetStatus", "GetError", "GetAllSettings"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 5,
    "files_with_Run": 4,
    "files_with_state": 4,
    "files_with_print": 2,
    "files_with_decorator": 1,
    "pass_rate": 80.0,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "BookSystem"
FILE_COUNT = 5
CLASS_COUNT = 5
