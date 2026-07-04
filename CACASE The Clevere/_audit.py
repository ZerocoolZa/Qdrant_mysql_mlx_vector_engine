import glob
import re

SPEC = {
    1: ("backup_engine.py", ["create_primary", "verify_integrity", "create_secondary", "store_offline", "hash_both", "record_metadata", "make_readonly", "restore_test", "log_session"]),
    2: ("sandbox_engine.py", ["load_ram", "verify_schema", "verify_counts", "verify_foreign_keys", "verify_indexes", "verify_constraints", "enable_rollback", "snapshot_before", "auto_restore"]),
    3: ("error_db_engine.py", ["create_error_table", "create_fix_table", "create_failed_table", "create_success_table", "store_stack_trace", "store_exception_type", "store_file", "store_class", "store_method", "store_line_number", "store_variables", "store_inputs", "store_outputs", "store_root_cause", "store_human_fix", "store_ai_fix", "store_confidence", "store_similar_errors", "store_resolution_time", "learn_from_previous"]),
    4: ("graph_builder.py", ["parse_project", "build_file_graph", "build_folder_graph", "build_import_graph", "build_dependency_graph", "build_class_graph", "build_method_graph", "build_function_graph", "build_call_graph", "build_variable_graph", "build_object_graph", "build_event_graph", "build_runtime_flow", "build_execution_flow", "build_database_flow", "build_gui_flow", "build_thread_graph", "build_memory_graph", "detect_cycles", "detect_dead_code", "detect_duplicate_code", "detect_orphans", "detect_hotspots", "store_graph"]),
    5: ("ingestion_engine.py", ["scan_files", "compute_file_hash", "compute_bcl_hash", "detect_duplicates", "detect_version", "detect_language", "detect_encoding", "detect_dependencies", "record_metadata", "store_raw_source"]),
    6: ("file_split_engine.py", ["store_file", "query_file", "update_file", "delete_file", "list_files", "count_files", "files_by_extension", "files_by_status", "files_by_hash", "files_by_dependency"]),
    7: ("class_split_engine.py", ["store_class", "query_class", "update_class", "delete_class", "list_classes", "count_classes", "classes_by_parent", "classes_by_file", "classes_by_dependency", "split_all"]),
    8: ("method_split_engine.py", ["store_method", "query_method", "update_method", "delete_method", "list_methods", "count_methods", "methods_by_class", "methods_by_file", "methods_by_complexity", "split_all"]),
    9: ("bcl_engine.py", ["normalize_file", "normalize_class", "normalize_method", "normalize_function", "store_as_text", "never_reformat", "never_wrap", "never_tokenize", "preserve_original", "hash_protect"]),
    10: ("static_analysis_engine.py", ["ast_parse", "symbol_table", "import_resolution", "type_analysis", "scope_analysis", "constant_detection", "global_detection", "dead_code_detection", "duplicate_detection", "complexity_analysis"]),
    11: ("relationship_engine.py", ["file_to_file", "file_to_class", "class_to_class", "class_to_method", "method_to_method", "method_to_variable", "method_to_database", "method_to_gui", "method_to_api", "method_to_thread"]),
    12: ("fix_engine.py", ["find_error", "search_similar", "rank_fixes", "apply_candidate", "compile_fix", "run_tests", "compare_output", "rollback_if_failed", "record_outcome", "learn_result"]),
    13: ("validation_engine.py", ["validate_syntax", "validate_imports", "validate_references", "validate_runtime", "validate_unit_tests", "validate_integration_tests", "validate_memory", "validate_database", "validate_performance", "validate_regression"]),
    14: ("knowledge_storage_engine.py", ["store_error", "store_fix", "store_patch", "store_explanation", "store_graph_changes", "store_before_after", "store_confidence", "store_evidence", "store_learning", "update_search_index"]),
    15: ("reporting_engine.py", ["error_timeline", "fix_timeline", "dependency_report", "duplicate_report", "complexity_report", "bcl_coverage", "graph_coverage", "method_coverage", "test_coverage", "health_score"]),
    16: ("continuous_loop_engine.py", ["scan", "ingest", "index", "graph", "detect", "search", "repair", "validate", "learn", "repeat"]),
    17: ("fingerprint_engine.py", ["project_hash", "file_hashes", "class_hashes", "method_hashes", "bcl_hashes", "dependency_hashes", "graph_hash", "snapshot_id", "change_signature", "integrity_verification"]),
    18: ("version_snapshot_engine.py", ["snapshot_before", "snapshot_after", "auto_restore_point", "branch_experiment", "compare_snapshots", "restore_snapshot", "snapshot_notes", "snapshot_timeline"]),
    19: ("comparison_engine.py", ["file_diff", "class_diff", "method_diff", "ast_diff", "graph_diff", "dependency_diff", "bcl_diff", "database_diff", "runtime_diff"]),
    20: ("semantic_search_engine.py", ["search_by_name", "search_by_bcl", "search_by_signature", "search_by_error", "search_by_fix", "search_by_dependency", "search_by_call_chain", "search_by_variable", "search_by_comment", "search_by_behavior"]),
    21: ("execution_tracing_engine.py", ["entry_point", "call_order", "stack_trace", "memory_usage", "object_lifetime", "sql_calls", "api_calls", "file_io", "thread_activity", "exit_path"]),
    22: ("impact_analysis_engine.py", ["what_uses_this", "what_breaks", "what_depends_on_it", "reverse_call_graph", "forward_call_graph", "ripple_radius", "risk_score", "confidence_score"]),
    23: ("deduplication_engine.py", ["duplicate_files", "duplicate_classes", "duplicate_methods", "duplicate_logic", "duplicate_sql", "duplicate_constants", "duplicate_imports", "duplicate_bcl", "duplicate_algorithms"]),
    24: ("pattern_detection_engine.py", ["detect_design_patterns", "detect_anti_patterns", "detect_code_smells", "detect_naming_patterns", "detect_architecture_rules", "detect_user_rules", "detect_violations", "suggest_improvements"]),
    25: ("architecture_validator_engine.py", ["circular_dependencies", "layer_violations", "invalid_imports", "missing_interfaces", "missing_classes", "missing_methods", "missing_files", "broken_references"]),
    26: ("database_validator_engine.py", ["missing_tables", "missing_indexes", "missing_foreign_keys", "broken_constraints", "duplicate_rows", "orphan_rows", "integrity_check", "optimization_check"]),
    27: ("bcl_validator_engine.py", ["exists", "valid_format", "complete", "hash_valid", "matches_code", "matches_database", "references_valid", "parent_exists"]),
    28: ("knowledge_graph_engine.py", ["files", "classes", "methods", "variables", "databases", "apis", "gui", "threads", "errors", "fixes"]),
    29: ("ai_memory_engine.py", ["previous_errors", "previous_fixes", "previous_successes", "previous_failures", "user_rules", "coding_rules", "architecture_rules", "learned_patterns"]),
    30: ("confidence_engine.py", ["parse_confidence", "match_confidence", "graph_confidence", "repair_confidence", "runtime_confidence", "test_confidence", "overall_confidence"]),
    31: ("safety_engine.py", ["never_touch_original", "always_rollback", "verify_before_save", "verify_after_save", "verify_graph", "verify_database", "verify_runtime", "verify_output"]),
    32: ("build_pipeline_engine.py", ["scan", "parse", "index", "bcl_extract", "graph_build", "validate", "learn", "store", "test", "report"]),
    33: ("root_cause_engine.py", ["surface_error", "walk_backward", "dependency_analysis", "data_flow_analysis", "control_flow_analysis", "origin_detection", "first_cause", "secondary_causes", "cascading_effects"]),
    34: ("self_check_engine.py", ["did_anything_change", "was_it_expected", "did_tests_pass", "did_graph_change", "did_database_change", "did_bcl_change", "did_runtime_change", "is_confidence_higher"]),
    35: ("digital_twin_engine.py", ["entire_codebase", "entire_dependency_graph", "entire_runtime_model", "entire_bcl_model", "entire_error_history", "entire_fix_history", "entire_architecture_model", "entire_evolution_timeline", "queryable_knowledge_base", "safe_simulation"]),
    36: ("compiler_knowledge_engine.py", ["compiler_errors", "compiler_warnings", "linker_errors", "build_logs", "build_time", "build_history", "build_environment", "compiler_version"]),
    37: ("runtime_knowledge_engine.py", ["live_objects", "memory_map", "heap", "stack", "open_files", "open_sockets", "threads", "timers", "handles", "resource_usage"]),
    38: ("memory_forensics_engine.py", ["leak_detection", "object_lifetime", "allocation_history", "deallocation_history", "fragmentation", "peak_usage", "growth_trend", "leak_history"]),
    39: ("sql_analyzer_engine.py", ["query_history", "query_plan", "slow_queries", "missing_indexes", "table_usage", "transaction_history", "lock_analysis", "deadlock_analysis"]),
    40: ("file_forensics_engine.py", ["creation_date", "modification_history", "rename_history", "move_history", "ownership", "permissions", "encoding", "file_signature", "hash_timeline"]),
    41: ("evolution_engine.py", ["class_timeline", "method_timeline", "variable_timeline", "dependency_timeline", "architecture_timeline", "error_timeline", "fix_timeline", "refactor_timeline"]),
    42: ("call_path_engine.py", ["incoming_calls", "outgoing_calls", "recursive_calls", "event_calls", "async_calls", "callback_chains", "signal_chains", "complete_execution_paths"]),
    43: ("data_flow_engine.py", ["variable_origin", "variable_mutation", "variable_lifetime", "parameter_flow", "return_flow", "database_flow", "file_flow", "network_flow"]),
    44: ("control_flow_engine.py", ["branches", "loops", "switches", "exceptions", "early_returns", "exit_paths", "unreachable_code", "infinite_loops"]),
    45: ("symbol_database_engine.py", ["classes", "methods", "variables", "constants", "enums", "structs", "interfaces", "typedefs"]),
    46: ("type_system_engine.py", ["type_definitions", "inference", "casts", "conversions", "nullable_analysis", "generic_analysis", "compatibility", "violations"]),
    47: ("naming_engine.py", ["naming_rules", "duplicate_names", "similar_names", "reserved_words", "user_standards", "consistency", "violations", "suggestions"]),
    48: ("code_quality_engine.py", ["complexity", "readability", "maintainability", "cohesion", "coupling", "reuse", "documentation", "stability"]),
    49: ("refactor_engine.py", ["safe_rename", "safe_move", "safe_extract", "safe_inline", "safe_split", "safe_merge", "safe_delete", "safe_replace"]),
    50: ("test_knowledge_engine.py", ["unit_tests", "integration_tests", "regression_tests", "coverage", "failed_tests", "passed_tests", "missing_tests", "test_history"]),
}

# Check which files exist
existing = set(f for f in glob.glob("*.py") if not f.startswith("_"))

import sys
sys.stdout = open("_audit_results.txt", "w")
print("=== MISSING FILES ===")
for section, (fname, commands) in sorted(SPEC.items()):
    if fname not in existing:
        print(f"  Section {section}: {fname} MISSING")

print()
print("=== METHOD COUNT CHECK ===")
for section, (fname, commands) in sorted(SPEC.items()):
    if fname not in existing:
        continue
    with open(fname) as fh:
        content = fh.read()
    # Extract Run dispatch commands
    run_match = re.search(r'def Run\(self, command, params=None\):(.*?)(?=\n    def |\nclass |\Z)', content, re.DOTALL)
    if not run_match:
        print(f"  {fname}: NO Run method found")
        continue
    run_body = run_match.group(1)
    dispatched = re.findall(r'== "(\w+)"', run_body)
    spec_cmds = set(commands)
    dispatched_set = set(dispatched)
    missing = spec_cmds - dispatched_set
    extra = dispatched_set - spec_cmds - {"read_state", "set_config"}
    if missing:
        print(f"  {fname} (Section {section}): MISSING {len(missing)} commands: {sorted(missing)}")
    if extra:
        print(f"  {fname} (Section {section}): EXTRA commands: {sorted(extra)}")
    if not missing and not extra:
        cmd_count = len(dispatched_set - {"read_state", "set_config"})
        print(f"  {fname} (Section {section}): OK ({cmd_count} commands)")
