#!/usr/bin/env python3

#[@GHOST]{[@file<core_class_extractor.py>][@state<active>][@date<2026-06-26>][@ver<1.0>][@auth<system>]}
#[@VBSTYLE]{[@auth<system>][@role<core_class_extraction>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
CoreClassExtractor: Queries ALL sources for VBStyle core classes.
Sources: (1) SQLite v20_hybrid_best.db (2) vb_shared.code_classes
         (3) vb_shared.code_registry (4) vb_shared.designrationale
         (5) vb_shared.learned_rules (6) vb_code_test.vb_classes+vb_methods
         (7) on-disk VBSTYLE_*.py files (8) MD files mentioning core classes
Generates BCL bracket format entries with source tracking. Each BCL entry
records WHERE the class was found so core.md gives the entire picture.

Usage:
    python3 core_class_extractor.py
    python3 core_class_extractor.py --no-mysql     # SQLite only
    python3 core_class_extractor.py --output PATH   # custom output
    python3 core_class_extractor.py --scan-disk DIR # scan disk for VBSTYLE_*.py
    python3 core_class_extractor.py --scan-md DIR   # scan MD files for refs
"""

import sqlite3
import json
import os
import re
import sys
import subprocess
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "code_store_variations", "v20_hybrid_best.db")
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "core_class_registry.md")

CORE_CLASS_NAMES = [
    "MemUnit", "MemDb", "MemBus", "Executor", "Orchestration",
    "AST", "ClassAST", "VBAnnotate", "VBStyle_AST", "VBStyle_Brackets",
    "Report", "ErrorHandler", "ErrorReport",
    "Hardware", "OSLayer", "ClassOS",
    "ClassIndexer", "IndexAuthority",
    "BootstrapLoader", "RuntimeGuard", "UnitBase", "VerificationSuite",
    "CoreBootV3", "CoreUnit", "CoreState",
    "CASOSNode", "CASOSVerification",
    "GuiBus", "GuiDB", "GuiDBActions", "GuiDbWriter",
    "GuiDomainRegistry", "GuiDecisionEngine", "GuiLayoutLaw",
    "EventBus", "CommandBus", "MessageBus",
    "DomOrchestration", "DomErrorHandling", "DomMemory", "DomGui",
    "DomIndex", "DomWwsIndex", "WwsIndexAuthority",
    "UnifyDomain", "SystemDomain",
    "RuntimeGuard", "Runtime",
]

DOMAIN_REGISTRY = [
    "Dom_Vector", "accessibility", "ai", "analysis", "analytics", "arch",
    "archive", "asm", "audit", "automation", "bytecode", "caching", "cli",
    "codec", "codegraph", "compass", "compression", "concurrency", "config",
    "convert", "cryptography", "csplit", "cu", "db", "db_inv", "db_studio",
    "deployment", "documentation", "errorhandling", "factory", "featureflags",
    "fileops", "folder", "general", "governance", "graph", "graph_engine",
    "graphs", "gui", "http", "index", "ingest", "ingest_cli", "ingest_gui",
    "io", "knowledge", "localization", "log", "logging", "memory",
    "messaging", "network", "observability", "orchestration", "package",
    "parse", "process", "project_indexer", "qa", "qt", "ratelimiting",
    "reporting", "rescue", "resilience", "runtime", "schedule", "search",
    "security", "serialization", "storage", "style", "system", "testing",
    "text", "transform", "unify", "validate", "validation", "vcs",
    "workflow", "wws_index", "yaml",
]

HUMAN_DESCRIPTIONS = {
    "MemUnit": "THE execution authority. Bus + Authority + Dispatcher + Coordinator + Runtime Context + Graph Owner. Only place where execution runs. Dispatches to Executor, routes through MemBus, queues through MemDB. No class executes itself.",
    "Executor": "Performs execution. Distinct from MemUnit — MemUnit dispatches, Executor performs. Holds core_instances and lib_instances dicts. Finds target by name and calls its Run() method.",
    "MemBus": "Message routing bus. Routes communication between classes. Subscribe callbacks to action patterns, publish actions to matching subscribers. Pattern matching with wildcard support.",
    "MemDb": "Runtime Truth Substrate. In-RAM SQLite database with command_queue, state_cache, and routing_map tables. NOT just SQLite — includes Runtime Registry, Shared State, Execution Context, Class Registry Cache, Config Cache.",
    "Orchestration": "Dependency resolver. Builds execution graph, reduces to one active execution target. Applies ordering rules: boot_priority, stage, dependency graph.",
    "AST": "Structural truth extraction. Syntax gate — validates structure, checks if code is well-formed. Parses Python files using ast module. Validates one-class-per-file rule. No execution role, no selection role.",
    "ClassAST": "Class-level AST analysis. Detects classes in source files, finds classes with Run() methods, parses source code into class structures, extracts parameters from function nodes.",
    "VBAnnotate": "Semantic truth. Safe contract annotation authority. Parses Python safely using AST, injects missing VBSTYLE method annotations. Creates backups, supports dry-run, validates syntax before overwrite.",
    "VBStyle_AST": "Structural truth extraction (alias of AST). Parses Python source, validates one-class-per-domain rule.",
    "VBStyle_Brackets": "Semantic truth (alias of VBAnnotate). Reads/validates BCL bracket syntax, extracts metadata contracts, builds execution intent.",
    "Report": "Structured reporting. Builds reports from multiple layers, attaches data layers (OS, hardware), takes system snapshots, builds semantic clusters from keywords, extracts tags from objects.",
    "ErrorHandler": "Error capture, classification, recovery, suppression. Captures errors with system state, classifies error types, executes recovery strategies, correlates related errors, tracks frequency and trends, manages suppression rules.",
    "ErrorReport": "Captures exceptions into know_problems/know_causes tables. Bridges error handling and knowledge base.",
    "Hardware": "Hardware detection and resource limits. Detects CPU, RAM, cores. Calculates optimal thread counts and safe memory limits. Adapts to available hardware.",
    "OSLayer": "OS detection, paths, safe file operations. Detects operating system, provides safe file operations, manages OS-specific paths, takes system snapshots.",
    "ClassOS": "Foundation OS class for DOM operations. Detects OS capabilities, checks if features are supported, provides OS state for domain modules.",
    "ClassIndexer": "Indexes classes from source files. Extracts classes from Python files, parses class names from source lines, parses VBStyle annotations, indexes by name and role.",
    "IndexAuthority": "Inverted index generation and validation. Generates inverted index for a directory, creates file bracket entries, validates index integrity.",
    "BootstrapLoader": "System bootstrap — every model runs this first. Loads system architecture, finds correct table for a token, gets instructions by name, explains architecture to new models.",
    "RuntimeGuard": "Runtime limits — max RAM, max time, abort on breach. Checks memory usage, runs processes/threads with guardrails, safe execution with mode selection, tracks crashes.",
    "UnitBase": "Base class for all units. Provides Dispatch and Run methods, handles bad actions and bad params, tracks unit name, authority, params.",
    "VerificationSuite": "System verification. Cold boot tests, circular dependency checks, class discovery, Claude bridge, component registry, duplicate public classes, memory centrality, QA engine, runtime integrity, shard compression, shutdown integrity, VBStyle audit.",
    "CoreBootV3": "Boot initialization. Default stages, action run, declaration text. Core boot sequence controller.",
    "CoreUnit": "Core unit definition. Base unit for the core system.",
    "CoreState": "Core state management. Centralized state tracking for core modules.",
    "CASOSNode": "A single code entity in the registry — method, CU, class, domain, or application. Part of MemUnit core CASOS verification system. Status: discovered -> documented -> understood -> tested -> verified -> approved -> canonical.",
    "CASOSVerification": "CASOS Verification Core — trust-gated promotion pipeline. Lives inside MemUnit. 4 parallel truth streams: Structural, Semantic, Execution, Authority. 6 verification engines: SE -> SSE -> MemUnit -> SpecMatcher -> Authority -> Stability.",
    "GuiBus": "GUI event bus — pub/sub scoped to GUI events. Publishes GUI events (click, key, mouse, resize, close), subscribes to GUI event channels.",
    "GuiDB": "GUI truth source. Dynamic GUI loads from GuiDB truth, not hardcoded PyQt code. CAR principle: Critical, Available, Reliable.",
    "GuiDBActions": "GUI database actions. Backup, Check, Deduplicate, Export, ImportSQL, Initialize, SQLiteIntegrity, SaveState, Status, Verify. Bridges GUI operations to SQLite.",
    "GuiDbWriter": "Writes GUI definitions to database. Creates schema, writes app data, classes, layout law, properties, signals, slots. Summarizes and writes domain packets.",
    "GuiDomainRegistry": "GUI domain registry. Resets, groups by module/role, groups signals/slots, absorbs domain packets. Organizes GUI classes into domains.",
    "GuiDecisionEngine": "GUI decision engine. Makes rendering and layout decisions for the GUI layer.",
    "GuiLayoutLaw": "GUI layout constraint laws. Enforces layout rules and constraints for GUI widgets.",
    "EventBus": "Event bus for pub/sub messaging. Routes events between subscribers. VBStyle domain: dom_messaging.",
    "CommandBus": "Command bus for command routing. Routes commands to handlers. VBStyle domain: dom_messaging.",
    "MessageBus": "Message bus for process-level messaging. VBStyle domain: dom_process.",
    "DomOrchestration": "Full orchestration domain. Task dispatch, queue, schedule, parallel, retry, worker, priority, timeout, sequence, dependency, pause, resume, status.",
    "DomErrorHandling": "Full error handling domain. Classify, recover, translate, cause_chain, suppress, wrap, is_retryable, log_once, create_context, get_hierarchy.",
    "DomMemory": "Full memory domain. In-memory key-value store with TTL, compression, and persistence hooks. Store, recall, cache, compress, persist, restore, expire, forget, invalidate, refresh, clear, keys, size.",
    "DomGui": "Full GUI domain. Widget tree management, layout, drawing, and event handling. 40+ methods: create_window, add_widget, button, label, render, event_click, etc.",
    "DomIndex": "Full index domain. Build, merge, split, create, update, delete, optimize, rebuild, stats, import. Searchable index management.",
    "DomWwsIndex": "Wws inverted index domain. Build, create, update, delete, merge, optimize, rebuild, stats, import. Tokenized inverted index with doc management.",
    "WwsIndexAuthority": "File packet builder. Extracts symbols, dependencies, classifies buckets, detects language, builds file packets, reads fingerprints and excerpts.",
    "UnifyDomain": "Unify domain. Unifies domain access across the system. VBStyle domain: dom_unify.",
    "SystemDomain": "System domain. System-level domain management. VBStyle domain: dom_system.",
    "Runtime": "Execution, scheduling, dispatching, task and pipeline management. VBStyle domain: dom_runtime.",
}


def query_sqlite_classes(db_path, class_names):
    results = {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    placeholders = ",".join("?" * len(class_names))
    rows = cur.execute(
        "SELECT class_name, domain, description, source_file, "
        "is_vbstyle, has_run_method, has_tuple3 FROM classes "
        "WHERE class_name IN ({})".format(placeholders),
        class_names
    ).fetchall()

    for row in rows:
        cn = row["class_name"]
        results[cn] = {
            "class_name": cn,
            "domain": row["domain"] or "",
            "description": row["description"] or "",
            "source_file": row["source_file"] or "",
            "is_vbstyle": row["is_vbstyle"],
            "has_run_method": row["has_run_method"],
            "has_tuple3": row["has_tuple3"],
            "methods": [],
        }

    class_ids = {}
    for row in rows:
        cid = cur.execute(
            "SELECT id FROM classes WHERE class_name = ?", (row["class_name"],)
        ).fetchone()
        if cid:
            class_ids[row["class_name"]] = cid["id"]

    for cn, cid in class_ids.items():
        mrows = cur.execute(
            "SELECT method_name, params, signature, is_dunder, "
            "is_vbstyle, returns_tuple3, line_start FROM methods "
            "WHERE class_id = ? ORDER BY method_name", (cid,)
        ).fetchall()
        for m in mrows:
            results[cn]["methods"].append({
                "method_name": m["method_name"],
                "params": m["params"] or "",
                "signature": m["signature"] or "",
                "is_dunder": m["is_dunder"],
                "is_vbstyle": m["is_vbstyle"],
                "returns_tuple3": m["returns_tuple3"],
                "line_start": m["line_start"],
            })

    conn.close()
    return results


def query_mysql_classes(class_names):
    results = {}
    try:
        cmd = (
            "mysql -u root vb_shared -e \"SELECT class_name, description "
            "FROM code_classes WHERE class_name IN ({})\"".format(
                ",".join("'{}'".format(c) for c in class_names)
            )
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                cn = parts[0].strip()
                desc = parts[1].strip()
                results[cn] = {"mysql_description": desc, "source": "vb_shared.code_classes"}
    except Exception:
        pass
    return results


def query_mysql_code_classes_all():
    """Query vb_shared.code_classes for ALL VBStyle core classes (not just hardcoded list)."""
    results = {}
    try:
        cmd = (
            "mysql -u root vb_shared -e \"SELECT class_name, description "
            "FROM code_classes WHERE description LIKE 'VBStyle core%' "
            "OR description LIKE 'VBStyle Core%' "
            "OR description LIKE 'From ChatGPT export: Core%' "
            "OR class_name LIKE 'VBStyle%' ORDER BY class_name\""
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                cn = parts[0].strip()
                desc = parts[1].strip()
                results[cn] = {"mysql_description": desc, "source": "vb_shared.code_classes"}
    except Exception:
        pass
    return results


def query_mysql_code_registry(class_names):
    """Query vb_shared.code_registry for core class source files."""
    results = {}
    try:
        name_list = ",".join("'{}'".format(c) for c in class_names)
        cmd = (
            "mysql -u root vb_shared -e \"SELECT token_name, description "
            "FROM code_registry WHERE token_name IN ({}) "
            "OR token_name LIKE '%VBSTYLE%' "
            "OR token_name LIKE '%Core%' ORDER BY token_name\"".format(name_list)
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                cn = parts[0].strip()
                desc = parts[1].strip()
                results[cn] = {"registry_description": desc, "source": "vb_shared.code_registry"}
    except Exception:
        pass
    return results


def query_mysql_design_rationale():
    """Query vb_shared.designrationale for architecture decisions about core classes."""
    results = []
    try:
        cmd = (
            "mysql -u root vb_shared -e \"SELECT subject, rationale, category "
            "FROM designrationale WHERE subject LIKE '%MemUnit%' "
            "OR subject LIKE '%MemDb%' "
            "OR subject LIKE '%Executor%' "
            "OR subject LIKE '%MemBus%' "
            "OR subject LIKE '%execution%' "
            "OR category = 'execution_surface' "
            "OR subject LIKE '%Core%' ORDER BY subject\""
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                results.append({
                    "subject": parts[0].strip(),
                    "rationale": parts[1].strip(),
                    "category": parts[2].strip(),
                    "source": "vb_shared.designrationale",
                })
    except Exception:
        pass
    return results


def query_mysql_learned_rules():
    """Query vb_shared.learned_rules for rules about core/MemUnit/VBStyle patterns."""
    results = []
    try:
        cmd = (
            "mysql -u root vb_shared -e \"SELECT pattern, fix_action, confidence "
            "FROM learned_rules WHERE pattern LIKE '%MemUnit%' "
            "OR pattern LIKE '%MemDb%' "
            "OR pattern LIKE '%core%' "
            "OR pattern LIKE '%vbstyle%' "
            "OR pattern LIKE '%scanner%' ORDER BY confidence DESC LIMIT 30\""
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                results.append({
                    "pattern": parts[0].strip(),
                    "fix_action": parts[1].strip(),
                    "confidence": parts[2].strip(),
                    "source": "vb_shared.learned_rules",
                })
    except Exception:
        pass
    return results


def query_mysql_vb_code_test(class_names):
    """Query vb_code_test.vb_classes + vb_methods for method signatures."""
    results = {}
    try:
        name_list = ",".join("'{}'".format(c) for c in class_names)
        cmd = (
            "mysql -u root vb_code_test -e \"SELECT c.class_name, c.domain, c.role, "
            "c.description, GROUP_CONCAT(CONCAT(m.method_name, '|', m.params) "
            "ORDER BY m.method_name SEPARATOR ';') AS methods "
            "FROM vb_classes c LEFT JOIN vb_methods m ON c.id = m.class_id "
            "WHERE c.class_name IN ({}) "
            "OR c.class_name LIKE '%Mem%' "
            "OR c.class_name LIKE '%Core%' "
            "OR c.class_name LIKE 'VBStyle%' "
            "GROUP BY c.class_name ORDER BY c.class_name\"".format(name_list)
        )
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return results
        lines = proc.stdout.strip().split("\n")[1:]
        for line in lines:
            parts = line.split("\t", 4)
            if len(parts) >= 4:
                cn = parts[0].strip()
                domain = parts[1].strip()
                role = parts[2].strip()
                desc = parts[3].strip()
                methods_str = parts[4].strip() if len(parts) > 4 else ""
                methods = []
                for mpair in methods_str.split(";"):
                    if "|" in mpair:
                        mname, mparams = mpair.split("|", 1)
                        methods.append({"method_name": mname.strip(), "params": mparams.strip()})
                results[cn] = {
                    "domain": domain,
                    "role": role,
                    "description": desc,
                    "methods": methods,
                    "source": "vb_code_test.vb_classes+vb_methods",
                }
    except Exception:
        pass
    return results


def scan_disk_vbstyle_files(search_root):
    """Find VBSTYLE_*.py files on disk and extract class/method signatures."""
    results = {}
    if not search_root or not os.path.isdir(search_root):
        return results
    for dirpath, dirnames, filenames in os.walk(search_root):
        for fname in filenames:
            if not fname.startswith("VBSTYLE") or not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            current_class = None
            for line in lines:
                m = re.match(r"^class\s+(\w+)", line)
                if m:
                    current_class = m.group(1)
                    if current_class not in results:
                        results[current_class] = {
                            "source_file": fpath,
                            "methods": [],
                            "source": "disk:{}".format(fname),
                        }
                    continue
                if current_class:
                    dm = re.match(r"^\s+def\s+(\w+)\((.*)\)", line)
                    if dm:
                        results[current_class]["methods"].append({
                            "method_name": dm.group(1),
                            "params": dm.group(2),
                        })
    return results


def scan_md_files(search_root, class_names):
    """Scan MD files for references to core class names."""
    results = {}
    if not search_root or not os.path.isdir(search_root):
        return results
    for dirpath, dirnames, filenames in os.walk(search_root):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            for cn in class_names:
                if cn in content:
                    if cn not in results:
                        results[cn] = []
                    rel_path = os.path.relpath(fpath, search_root)
                    results[cn].append({
                        "md_file": fpath,
                        "rel_path": rel_path,
                        "source": "md:{}".format(fname),
                    })
    return results


def generate_bcl_block(class_info, mysql_info=None, all_sources=None):
    cn = class_info["class_name"]
    domain = class_info["domain"]
    desc = class_info["description"]
    source = class_info["source_file"]
    is_vb = class_info["is_vbstyle"]
    has_run = class_info["has_run_method"]
    has_t3 = class_info["has_tuple3"]
    methods = class_info["methods"]

    mysql_desc = ""
    if mysql_info and "mysql_description" in mysql_info:
        mysql_desc = mysql_info["mysql_description"]

    sources_list = ["sqlite:v20_hybrid_best.db"]
    if mysql_info and "source" in mysql_info:
        sources_list.append(mysql_info["source"])
    if all_sources:
        for s in all_sources:
            if s not in sources_list:
                sources_list.append(s)

    run_cmds = []
    has_read_state = False
    has_set_config = False
    for m in methods:
        if m["method_name"] == "Run":
            pass
        if m["method_name"] == "read_state":
            has_read_state = True
        if m["method_name"] == "set_config":
            has_set_config = True
        if not m["is_dunder"] and m["method_name"] not in ("Run", "read_state", "set_config"):
            run_cmds.append(m["method_name"])

    init_params = ""
    for m in methods:
        if m["method_name"] == "__init__":
            init_params = m["params"]
            break

    lines = []
    lines.append('[@{}]{{'.format(cn))
    lines.append('("class_name";"{}")'.format(cn))
    lines.append('("domain";"{}")'.format(domain))
    lines.append('("source";"{}")'.format(source))
    lines.append('("sources";"{}")'.format(";".join(sources_list)))
    lines.append('("description";"{}")'.format(desc.replace('"', "'")))
    if mysql_desc:
        lines.append('("mysql_description";"{}")'.format(mysql_desc.replace('"', "'")[:200]))
    lines.append('("init";"{}")'.format(init_params))
    lines.append('("is_vbstyle";"{}")'.format("yes" if is_vb else "no"))
    lines.append('("has_run";"{}")'.format("yes" if has_run else "no"))
    lines.append('("has_tuple3";"{}")'.format("yes" if has_t3 else "no"))
    lines.append('("has_read_state";"{}")'.format("yes" if has_read_state else "no"))
    lines.append('("has_set_config";"{}")'.format("yes" if has_set_config else "no"))
    lines.append('("run_commands";"{}")'.format(";".join(run_cmds)))
    lines.append('("method_count";"{}")'.format(len(methods)))
    lines.append('("weight";"100")')

    if methods:
        lines.append('[@methods]{')
        for m in methods:
            mn = m["method_name"]
            mp = m["params"]
            dunder = "yes" if m["is_dunder"] else "no"
            mvb = "yes" if m["is_vbstyle"] else "no"
            mt3 = "yes" if m["returns_tuple3"] else "no"
            lines.append('("method";"{}";"params";"{}";"dunder";"{}";"vbstyle";"{}";"tuple3";"{}")'.format(
                mn, mp, dunder, mvb, mt3))
        lines.append('}')

    lines.append('}')
    return "\n".join(lines)


def generate_markdown(sqlite_data, mysql_data, all_mysql_classes=None,
                      code_registry_data=None, vb_code_test_data=None,
                      disk_files=None, md_refs=None, design_rationale=None,
                      learned_rules=None):
    out = []
    out.append("# Core VBStyle Class Registry")
    out.append("")
    out.append("> **Generated**: {} by core_class_extractor.py".format(
        datetime.now().isoformat(timespec="seconds")))
    out.append("> **Sources**: (1) SQLite v20_hybrid_best.db (2) vb_shared.code_classes "
               "(3) vb_shared.code_registry (4) vb_shared.designrationale "
               "(5) vb_shared.learned_rules (6) vb_code_test.vb_classes+vb_methods "
               "(7) on-disk VBSTYLE_*.py (8) MD files")
    out.append("> **Location**: `/Core/`")
    out.append("")
    out.append("---")
    out.append("")

    source_counts = {
        "sqlite": len(sqlite_data),
        "code_classes": len(all_mysql_classes) if all_mysql_classes else len(mysql_data),
        "code_registry": len(code_registry_data) if code_registry_data else 0,
        "vb_code_test": len(vb_code_test_data) if vb_code_test_data else 0,
        "disk_vbstyle": len(disk_files) if disk_files else 0,
        "md_refs": sum(len(v) for v in md_refs.values()) if md_refs else 0,
        "design_rationale": len(design_rationale) if design_rationale else 0,
        "learned_rules": len(learned_rules) if learned_rules else 0,
    }
    out.append("## Source Summary")
    out.append("")
    out.append("| Source | Entries Found |")
    out.append("|--------|--------------|")
    out.append("| SQLite v20_hybrid_best.db | {} |".format(source_counts["sqlite"]))
    out.append("| vb_shared.code_classes | {} |".format(source_counts["code_classes"]))
    out.append("| vb_shared.code_registry | {} |".format(source_counts["code_registry"]))
    out.append("| vb_code_test.vb_classes | {} |".format(source_counts["vb_code_test"]))
    out.append("| on-disk VBSTYLE_*.py | {} |".format(source_counts["disk_vbstyle"]))
    out.append("| MD file references | {} |".format(source_counts["md_refs"]))
    out.append("| designrationale | {} |".format(source_counts["design_rationale"]))
    out.append("| learned_rules | {} |".format(source_counts["learned_rules"]))
    out.append("")
    out.append("---")
    out.append("")

    out.append("## Domain Registry")
    out.append("")
    out.append("```")
    out.append(", ".join(DOMAIN_REGISTRY))
    out.append("```")
    out.append("")
    out.append("---")
    out.append("")

    out.append("## Boot Spine")
    out.append("")
    out.append("```")
    out.append("Bootstrap -> Config -> MemDB -> AST -> Brackets -> ClassDB -> Orchestration -> MemUnit -> Report -> Output")
    out.append("                                                              |")
    out.append("                                                         +----+----+")
    out.append("                                                         | MemBus  |")
    out.append("                                                         |Executor |")
    out.append("                                                         | Runtime |")
    out.append("                                                         +---------+")
    out.append("```")
    out.append("")
    out.append("---")
    out.append("")

    out.append("## Truth Separation")
    out.append("")
    out.append("| Layer | Truth Type | Role |")
    out.append("|-------|-----------|------|")
    out.append("| **AST** | Structural Truth | Validates code structure |")
    out.append("| **Brackets** | Semantic Truth | Extracts contracts, metadata from bracket syntax |")
    out.append("| **ClassDB** | Capability Truth | Maps class names to domains and capabilities |")
    out.append("| **Orchestration** | Dependency Truth | Resolves dependencies, builds execution graph |")
    out.append("| **MemUnit** | Execution Truth | The only place where execution runs |")
    out.append("| **MemDB** | Runtime Truth | In-RAM state substrate, registry, shared state |")
    out.append("")
    out.append("---")
    out.append("")

    out.append("## Class Entries")
    out.append("")

    all_class_names = set(sqlite_data.keys())
    if all_mysql_classes:
        all_class_names.update(all_mysql_classes.keys())
    if vb_code_test_data:
        all_class_names.update(vb_code_test_data.keys())
    if disk_files:
        all_class_names.update(disk_files.keys())

    ordered = []
    for name in CORE_CLASS_NAMES:
        if name in all_class_names and name not in ordered:
            ordered.append(name)
    remaining = sorted(all_class_names - set(ordered))
    ordered.extend(remaining)

    for i, cn in enumerate(ordered):
        ci = sqlite_data.get(cn, {
            "class_name": cn, "domain": "", "description": "",
            "source_file": "", "is_vbstyle": False,
            "has_run_method": False, "has_tuple3": False, "methods": [],
        })
        mi = mysql_data.get(cn) or (all_mysql_classes.get(cn) if all_mysql_classes else None)

        class_sources = []
        if cn in sqlite_data:
            class_sources.append("sqlite:v20_hybrid_best.db")
        if all_mysql_classes and cn in all_mysql_classes:
            class_sources.append("vb_shared.code_classes")
        if code_registry_data and cn in code_registry_data:
            class_sources.append("vb_shared.code_registry")
        if vb_code_test_data and cn in vb_code_test_data:
            class_sources.append("vb_code_test.vb_classes")
        if disk_files and cn in disk_files:
            class_sources.append(disk_files[cn]["source"])
        if md_refs and cn in md_refs:
            for ref in md_refs[cn]:
                class_sources.append(ref["source"])

        if vb_code_test_data and cn in vb_code_test_data:
            vbt = vb_code_test_data[cn]
            if vbt["methods"] and not ci["methods"]:
                ci["methods"] = [{"method_name": m["method_name"], "params": m["params"],
                                  "is_dunder": m["method_name"].startswith("__"),
                                  "is_vbstyle": False, "returns_tuple3": False,
                                  "signature": "", "line_start": 0}
                                 for m in vbt["methods"]]
            if vbt["domain"] and not ci["domain"]:
                ci["domain"] = vbt["domain"]
            if vbt["description"] and not ci["description"]:
                ci["description"] = vbt["description"]

        if disk_files and cn in disk_files:
            df = disk_files[cn]
            if df["methods"] and not ci["methods"]:
                ci["methods"] = [{"method_name": m["method_name"], "params": m["params"],
                                  "is_dunder": m["method_name"].startswith("__"),
                                  "is_vbstyle": False, "returns_tuple3": False,
                                  "signature": "", "line_start": 0}
                                 for m in df["methods"]]
            if not ci["source_file"]:
                ci["source_file"] = df["source_file"]

        human_desc = HUMAN_DESCRIPTIONS.get(cn, ci["description"])
        out.append("### {} ({}/{})".format(i + 1, cn, ci["domain"] or "?"))
        out.append("")
        out.append(human_desc)
        out.append("")
        if class_sources:
            out.append("**Sources**: `{}`".format("` `".join(class_sources)))
            out.append("")
        out.append("```")
        out.append(generate_bcl_block(ci, mi, class_sources))
        out.append("```")
        out.append("")
        out.append("---")
        out.append("")

    out.append("## Design Rationale (from vb_shared.designrationale)")
    out.append("")
    if design_rationale:
        for dr in design_rationale:
            out.append("### {}".format(dr["subject"]))
            out.append("")
            out.append("> {}".format(dr["rationale"][:300]))
            out.append("")
            out.append("*Category: {} | Source: {}*".format(dr["category"], dr["source"]))
            out.append("")
            out.append("---")
            out.append("")
    else:
        out.append("*(no design rationale entries found)*")
        out.append("")
        out.append("---")
        out.append("")

    out.append("## Learned Rules (from vb_shared.learned_rules)")
    out.append("")
    if learned_rules:
        out.append("| Pattern | Fix Action | Confidence |")
        out.append("|---------|-----------|------------|")
        for lr in learned_rules:
            out.append("| {} | {} | {} |".format(
                lr["pattern"][:80], lr["fix_action"][:80], lr["confidence"]))
        out.append("")
    else:
        out.append("*(no learned rules entries found)*")
        out.append("")
    out.append("---")
    out.append("")

    out.append("## MD File References")
    out.append("")
    if md_refs:
        out.append("| Class | MD Files |")
        out.append("|-------|----------|")
        for cn, refs in sorted(md_refs.items()):
            files = ", ".join(r["rel_path"] for r in refs[:5])
            extra = " +{} more".format(len(refs) - 5) if len(refs) > 5 else ""
            out.append("| {} | {}{} |".format(cn, files, extra))
        out.append("")
    else:
        out.append("*(no MD file references found)*")
        out.append("")
    out.append("---")
    out.append("")

    out.append("## Summary")
    out.append("")
    out.append("| Metric | Value |")
    out.append("|--------|-------|")
    out.append("| Total classes (all sources) | {} |".format(len(ordered)))
    out.append("| SQLite classes | {} |".format(len(sqlite_data)))
    out.append("| MySQL code_classes | {} |".format(
        len(all_mysql_classes) if all_mysql_classes else len(mysql_data)))
    out.append("| MySQL code_registry | {} |".format(
        len(code_registry_data) if code_registry_data else 0))
    out.append("| vb_code_test classes | {} |".format(
        len(vb_code_test_data) if vb_code_test_data else 0))
    out.append("| on-disk VBSTYLE files | {} |".format(
        len(disk_files) if disk_files else 0))
    out.append("| MD file references | {} |".format(
        sum(len(v) for v in md_refs.values()) if md_refs else 0))
    out.append("| design rationale entries | {} |".format(
        len(design_rationale) if design_rationale else 0))
    out.append("| learned rules | {} |".format(
        len(learned_rules) if learned_rules else 0))
    total_methods = sum(len(ci["methods"]) for ci in sqlite_data.values())
    out.append("| Total methods (SQLite) | {} |".format(total_methods))
    vbstyle_count = sum(1 for ci in sqlite_data.values() if ci["is_vbstyle"])
    out.append("| VBStyle compliant | {} |".format(vbstyle_count))
    has_run_count = sum(1 for ci in sqlite_data.values() if ci["has_run_method"])
    out.append("| Has Run() method | {} |".format(has_run_count))
    has_t3_count = sum(1 for ci in sqlite_data.values() if ci["has_tuple3"])
    out.append("| Has Tuple3 returns | {} |".format(has_t3_count))
    out.append("")
    out.append("### Classes Needing VBStyle Conversion")
    out.append("")
    out.append("| Class | Issue |")
    out.append("|-------|-------|")
    for cn in ordered:
        ci = sqlite_data.get(cn)
        if not ci:
            continue
        issues = []
        if not ci["has_run_method"]:
            issues.append("No Run() method")
        if not ci["has_tuple3"]:
            issues.append("No Tuple3 returns")
        has_read = any(m["method_name"] == "read_state" for m in ci["methods"])
        has_set = any(m["method_name"] == "set_config" for m in ci["methods"])
        if not has_read:
            issues.append("No read_state()")
        if not has_set:
            issues.append("No set_config()")
        if issues:
            out.append("| **{}** | {} |".format(cn, ", ".join(issues)))
    out.append("")

    return "\n".join(out)


def Run(command, params=None):
    if params is None:
        params = {}

    if command == "extract":
        use_mysql = params.get("use_mysql", True)
        output_path = params.get("output", DEFAULT_OUTPUT)
        scan_disk_dir = params.get("scan_disk", "")
        scan_md_dir = params.get("scan_md", "")

        sqlite_data = query_sqlite_classes(DB_PATH, CORE_CLASS_NAMES)

        mysql_data = {}
        all_mysql_classes = {}
        code_registry_data = {}
        design_rationale = []
        learned_rules = []
        vb_code_test_data = {}

        if use_mysql:
            mysql_data = query_mysql_classes(CORE_CLASS_NAMES)
            all_mysql_classes = query_mysql_code_classes_all()
            code_registry_data = query_mysql_code_registry(CORE_CLASS_NAMES)
            design_rationale = query_mysql_design_rationale()
            learned_rules = query_mysql_learned_rules()
            vb_code_test_data = query_mysql_vb_code_test(CORE_CLASS_NAMES)

        disk_files = scan_disk_vbstyle_files(scan_disk_dir) if scan_disk_dir else {}
        md_refs = scan_md_files(scan_md_dir, CORE_CLASS_NAMES) if scan_md_dir else {}

        markdown = generate_markdown(
            sqlite_data, mysql_data,
            all_mysql_classes=all_mysql_classes,
            code_registry_data=code_registry_data,
            vb_code_test_data=vb_code_test_data,
            disk_files=disk_files,
            md_refs=md_refs,
            design_rationale=design_rationale,
            learned_rules=learned_rules)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        return (1, {
            "output": output_path,
            "classes_found": len(sqlite_data),
            "mysql_classes": len(mysql_data),
            "all_mysql_classes": len(all_mysql_classes),
            "code_registry": len(code_registry_data),
            "vb_code_test": len(vb_code_test_data),
            "disk_files": len(disk_files),
            "md_refs": sum(len(v) for v in md_refs.values()) if md_refs else 0,
            "design_rationale": len(design_rationale),
            "learned_rules": len(learned_rules),
            "total_methods": sum(len(ci["methods"]) for ci in sqlite_data.values()),
        }, None)

    elif command == "list_domains":
        return (1, {"domains": DOMAIN_REGISTRY}, None)

    elif command == "read_state":
        return (1, {"db_path": DB_PATH, "output": DEFAULT_OUTPUT}, None)

    else:
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


if __name__ == "__main__":
    use_mysql = "--no-mysql" not in sys.argv
    args = [a for a in sys.argv[1:] if a != "--no-mysql"]

    scan_disk = ""
    scan_md = ""
    output = DEFAULT_OUTPUT

    i = 0
    while i < len(args):
        if args[i] == "--scan-disk" and i + 1 < len(args):
            scan_disk = args[i + 1]
            i += 2
        elif args[i] == "--scan-md" and i + 1 < len(args):
            scan_md = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            output = args[i]
            i += 1
        else:
            i += 1

    result = Run("extract", {
        "use_mysql": use_mysql,
        "output": output,
        "scan_disk": scan_disk,
        "scan_md": scan_md,
    })
    if result[0]:
        data = result[1]
        sys.stderr.write("Done: {} sqlite classes, {} mysql, {} code_registry, "
                         "{} vb_code_test, {} disk, {} md_refs, {} rationale, {} rules\n".format(
            data["classes_found"], data["mysql_classes"], data["code_registry"],
            data["vb_code_test"], data["disk_files"], data["md_refs"],
            data["design_rationale"], data["learned_rules"]))
        sys.stderr.write("Written to: {}\n".format(data["output"]))
    else:
        sys.stderr.write("Error: {}\n".format(result[2]))
        sys.exit(1)
                                    tt  