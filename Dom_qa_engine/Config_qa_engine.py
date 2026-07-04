#!/usr/bin/env python3

#[@GHOST]{[@file<Config_Config_qa_engine.py>][@domain<qa_engine>][@role<config>][@auth<cascade>][@date<2026-06-22>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<config>][@return<dict>][@no<decorators|print|hardcoded_paths>]}

"""
Config for qa_engine domain.

Auto-generated file inventory, class/method index, and VBStyle compliance check.
DO NOT EDIT MANUALLY -- regenerate with _generate_configs.py.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -- Runtime Config Constants -----------------------------------
# These constants are imported by GhostQAEngine.py, six_mode_runner.py,
# pinnacle_harness.py, and other harness scripts. They provide the
# canonical config dict, paths, and model references.

CONFIG_JSON_PATH = os.path.join(BASE_DIR, "qa_engine_config.json")

PINNACLE_DB_PATH = os.path.join(BASE_DIR, "pinnacle_harness.db")

TEST_COLLECTION = "pinnacle_test_chat"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

EMBEDDING_BGE_SMALL = {
    "name": "BAAI/bge-small-en-v1.5",
    "dim": 384,
    "max_seq": 512,
}

RETRIEVAL_CHUNK_SIZE = 400
RETRIEVAL_CHUNK_OVERLAP = 80

RETRIEVAL_THRESHOLD = 0.30
QA_CONFIDENCE_THRESHOLD = 0.0
LLM_CONFIDENCE_THRESHOLD = 1.0
QA_MAX_LENGTH = 384
LLM_MAX_TOKENS = 200

QDRANT_COLLECTIONS = [
    "dim_semantic", "dim_structural", "dim_capability",
    "dim_lifecycle", "dim_bracket",
]


def _LoadConfigDict():
    """Load the JSON config file, falling back to a built-in default."""
    try:
        with open(CONFIG_JSON_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "version": 2,
            "engine_name": "GhostQA",
            "models": {},
            "storage": {
                "vector_backend": "qdrant",
                "backends": {
                    "qdrant": {
                        "url": QDRANT_URL,
                        "default_collection": "dim_semantic",
                    },
                },
            },
            "pipeline": {"mode": "B", "stages": ["embed", "search", "qa_extract", "classify"]},
            "classification": {"true_threshold": 5.0, "unknown_threshold": 0.0},
        }


CONFIG_DICT = _LoadConfigDict()

# -- File Inventory --------------------------------------------
    # -- Config_qa_engine.py --
    # Purpose: Gold Standard Config for GhostQAEngine.
    # Lines: 341 | Classes: 0 | Methods: 0
    #   VBStyle: NO_Run | NO_init | NO_state | no_print | no_decorator

    # -- GhostQAEngine.py --
    # Purpose: N/A
    # Lines: 1657 | Classes: 6 | Methods: 0
    #   Class: HardwareDetector -- methods: Run, __init__, Detect
    #   Class: ModelRegistry -- methods: __init__, Run, LoadModel, GetModel, ListModels, UnloadModel
    #   Class: VectorBackend -- methods: __init__, Run, Connect, CreateCollection, Upsert, Search, DeleteCollection, Count
    #   Class: QueryInterpreter -- methods: __init__, Run, Classify, Rewrite, Interpret
    #   Class: ModeRouter -- methods: __init__, Run, Route
    #   Class: GhostQAEngine -- methods: __init__, Run, _LoadConfig, InitEngine, ReloadConfig, SetConfig, DetectHardware, _GetEmbedder, _GetQAModel, _GetLLM
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- Rule_Gui.py --
    # Purpose: VBStyle Rule Truth GUI
    # Lines: 679 | Classes: 2 | Methods: 0
    #   Class: EditRuleDialog -- methods: __init__, get_values
    #   Class: RuleTruthGUI -- methods: __init__, _init_db, _build_ui, _bcl_schema, _load_data, _update_summary, _show_header_menu, _get_selected_row_data, _edit_selected, _add_rule
    #   VBStyle: NO_Run | init | state | PRINT | DECOR

    # -- fact_store_mock.py --
    # Purpose: Fact Store Mock GUI
    # Lines: 426 | Classes: 1 | Methods: 0
    #   Class: FactStoreGUI -- methods: __init__, _init_db, _build_ui, _bcl_schema, _load_data, _on_row_select
    #   VBStyle: NO_Run | init | NO_state | PRINT | DECOR

    # -- five_mode_runner.py --
    # Purpose: 5-Mode Experiment Runner
    # Lines: 280 | Classes: 0 | Methods: 4
    #   Functions: load_base_config, run_mode, compare_all_modes, main
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- pinnacle_harness.py --
    # Purpose: PinnacleHarness — Full Pipeline QA Test Harness
    # Lines: 827 | Classes: 0 | Methods: 10
    #   Functions: chunk_text, find_expected_chunks, qdrant_request, create_qdrant_collection, embed_and_upsert, setup_database, run_tests, report, clean, main
    #   VBStyle: NO_Run | init | state | PRINT | no_decorator

    # -- qa_prototype.py --
    # Purpose: N/A
    # Lines: 399 | Classes: 1 | Methods: 0
    #   Class: GhostQA -- methods: __init__, Run, LoadModels, EmbedText, SearchQdrant, ExtractAnswer, AskQuestion, ExplainAnswer, RunTests, ReadState
    #   VBStyle: Run | init | state | no_print | no_decorator

    # -- qa_test_harness.py --
    # Purpose: QA Test Harness — Curated Chat + 3-Mode Result Storage
    # Lines: 457 | Classes: 0 | Methods: 4
    #   Functions: setup_database, run_tests, report, main
    #   VBStyle: NO_Run | init | state | PRINT | no_decorator

    # -- qa_test_harness_v2.py --
    # Purpose: QA Test Harness v2 — Full Pipeline Test
    # Lines: 689 | Classes: 0 | Methods: 9
    #   Functions: chunk_text, qdrant_request, create_qdrant_collection, embed_and_upsert, setup_database, run_tests, report, clean, main
    #   VBStyle: NO_Run | init | state | PRINT | no_decorator

    # -- six_mode_runner.py --
    # Purpose: 6-Mode Experiment Runner
    # Lines: 350 | Classes: 0 | Methods: 4
    #   Functions: load_base_config, run_mode, compare_all_modes, main
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

    # -- three_experiment_harness.py --
    # Purpose: 3-Experiment Comparison Harness
    # Lines: 403 | Classes: 0 | Methods: 9
    #   Functions: qdrant_search, bert_qa_extract, qwen_qa_extract, classify_mode, run_experiment, bert_qa_wrapper, qwen_qa_wrapper, compare_results, main
    #   VBStyle: NO_Run | NO_init | NO_state | PRINT | no_decorator

# -- Files Dict ------------------------------------------------
FILES = {
    "Config_qa_engine.py": {
        "purpose": "Gold Standard Config for GhostQAEngine.",
        "lines": 341,
        "classes": [],
        "methods": [],
    },
    "GhostQAEngine.py": {
        "purpose": "",
        "lines": 1657,
        "classes": ["HardwareDetector", "ModelRegistry", "VectorBackend", "QueryInterpreter", "ModeRouter", "GhostQAEngine"],
        "methods": [],
    },
    "Rule_Gui.py": {
        "purpose": "VBStyle Rule Truth GUI",
        "lines": 679,
        "classes": ["EditRuleDialog", "RuleTruthGUI"],
        "methods": [],
    },
    "fact_store_mock.py": {
        "purpose": "Fact Store Mock GUI",
        "lines": 426,
        "classes": ["FactStoreGUI"],
        "methods": [],
    },
    "five_mode_runner.py": {
        "purpose": "5-Mode Experiment Runner",
        "lines": 280,
        "classes": [],
        "methods": ["load_base_config", "run_mode", "compare_all_modes", "main"],
    },
    "pinnacle_harness.py": {
        "purpose": "PinnacleHarness — Full Pipeline QA Test Harness",
        "lines": 827,
        "classes": [],
        "methods": ["chunk_text", "find_expected_chunks", "qdrant_request", "create_qdrant_collection", "embed_and_upsert", "setup_database", "run_tests", "report", "clean", "main"],
    },
    "qa_prototype.py": {
        "purpose": "",
        "lines": 399,
        "classes": ["GhostQA"],
        "methods": [],
    },
    "qa_test_harness.py": {
        "purpose": "QA Test Harness — Curated Chat + 3-Mode Result Storage",
        "lines": 457,
        "classes": [],
        "methods": ["setup_database", "run_tests", "report", "main"],
    },
    "qa_test_harness_v2.py": {
        "purpose": "QA Test Harness v2 — Full Pipeline Test",
        "lines": 689,
        "classes": [],
        "methods": ["chunk_text", "qdrant_request", "create_qdrant_collection", "embed_and_upsert", "setup_database", "run_tests", "report", "clean", "main"],
    },
    "six_mode_runner.py": {
        "purpose": "6-Mode Experiment Runner",
        "lines": 350,
        "classes": [],
        "methods": ["load_base_config", "run_mode", "compare_all_modes", "main"],
    },
    "three_experiment_harness.py": {
        "purpose": "3-Experiment Comparison Harness",
        "lines": 403,
        "classes": [],
        "methods": ["qdrant_search", "bert_qa_extract", "qwen_qa_extract", "classify_mode", "run_experiment", "bert_qa_wrapper", "qwen_qa_wrapper", "compare_results", "main"],
    },
}
# -- Classes Dict ----------------------------------------------
CLASSES = {
    "HardwareDetector": {
        "file": "GhostQAEngine.py",
        "methods": ["Run", "__init__", "Detect"],
    },
    "ModelRegistry": {
        "file": "GhostQAEngine.py",
        "methods": ["__init__", "Run", "LoadModel", "GetModel", "ListModels", "UnloadModel"],
    },
    "VectorBackend": {
        "file": "GhostQAEngine.py",
        "methods": ["__init__", "Run", "Connect", "CreateCollection", "Upsert", "Search", "DeleteCollection", "Count"],
    },
    "QueryInterpreter": {
        "file": "GhostQAEngine.py",
        "methods": ["__init__", "Run", "Classify", "Rewrite", "Interpret"],
    },
    "ModeRouter": {
        "file": "GhostQAEngine.py",
        "methods": ["__init__", "Run", "Route"],
    },
    "GhostQAEngine": {
        "file": "GhostQAEngine.py",
        "methods": ["__init__", "Run", "_LoadConfig", "InitEngine", "ReloadConfig", "SetConfig", "DetectHardware", "_GetEmbedder", "_GetQAModel", "_GetLLM", "EmbedText", "_EmbedCoreML", "SearchChunks", "ExtractAnswer", "LLMExtract", "AskQuestion", "_Classify", "_ExecuteRoutedMode", "_ExecuteBERT", "_ExecuteQwen", "ExplainAnswer", "IngestDocument", "_RecordFailure", "ReadState"],
    },
    "EditRuleDialog": {
        "file": "Rule_Gui.py",
        "methods": ["__init__", "get_values"],
    },
    "RuleTruthGUI": {
        "file": "Rule_Gui.py",
        "methods": ["__init__", "_init_db", "_build_ui", "_bcl_schema", "_load_data", "_update_summary", "_show_header_menu", "_get_selected_row_data", "_edit_selected", "_add_rule", "_delete_selected", "_quick_classify"],
    },
    "FactStoreGUI": {
        "file": "fact_store_mock.py",
        "methods": ["__init__", "_init_db", "_build_ui", "_bcl_schema", "_load_data", "_on_row_select"],
    },
    "GhostQA": {
        "file": "qa_prototype.py",
        "methods": ["__init__", "Run", "LoadModels", "EmbedText", "SearchQdrant", "ExtractAnswer", "AskQuestion", "ExplainAnswer", "RunTests", "ReadState", "SetConfig"],
    },
}
# -- VBStyle Compliance ----------------------------------------
VBSTYLE_COMPLIANCE = {
    "total_files": 11,
    "files_with_Run": 2,
    "files_with_state": 6,
    "files_with_print": 8,
    "files_with_decorator": 2,
    "pass_rate": 18.2,
}
# -- Domain Summary --------------------------------------------
DOMAIN = "qa_engine"
FILE_COUNT = 11
CLASS_COUNT = 10
