# [@GHOST]{[@file<__init__.py>][@domain<Dom_Unified>][@role<package>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<package>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Dom_Unified package — centralized AST parsing with SQLite cache + error knowledge}
# [@CLASS]{Dom_Unified}
# [@METHOD]{parse,get_classes,get_methods,get_edges,check_vbstyle,store,prevent,top_errors}

"""
Dom_Unified — Centralized AST parsing via vbast C binary + SQLite cache + error knowledge.

USAGE:
    from Dom_Unified import *

    # Parse (uses cache automatically)
    classes = get_classes("file.py")
    methods = get_methods("file.py")
    edges   = get_edges("file.py")
    violations = check_vbstyle("file.py")
    stamps  = get_bcl_stamps("file.py")
    data    = parse("file.py")           # full structured data
    results = parse_dir("./folder/")     # all .py files in dir

    # Error prevention (errors become reusable knowledge)
    hints = prevent("file.py")           # what errors has this file hit before?
    top   = top_errors(10)               # most common errors across codebase

    # MySQL storage
    ok = store("file.py", "bcl_ir")      # write to MySQL bcl_ir

    # Cache management
    stats = cache_stats()                # cache hit/miss stats
    invalidate("file.py")                # force re-parse next time

    # Stateful class API
    ua = UnifiedAst()
    ok, data, err = ua.Run("parse", {"file": "file.py"})
"""

from .UnifiedAst import (
    parse, parse_dir, get_classes, get_methods, get_edges,
    check_vbstyle, get_bcl_stamps, to_json, store,
    prevent, top_errors, cache_stats, invalidate,
    UnifiedAst,
)
from .CacheDb import CacheDb
from .ErrorCapture import ErrorCapture
from .Config import UnifiedConfig
from .DatabaseManager import DatabaseManager, db_query, db_execute, db_insert
from .ConfigCascade import ConfigCascade
from .Dom_Report import DomReport
from .Dom_Indexer import DomIndexer
from .Dom_Reuse import DomReuse
from .Dom_System import DomSystem
from .Dom_Resource import DomResource
from .MagneticGraph import MagneticGraph
from .MemoryObject import MemoryObject
from .Neo4jGraph import Neo4jGraph
from .LocalAgent import LocalAgent
from .Dom_ExecutionEngine import ExecutionEngine

__all__ = [
    "parse", "parse_dir", "get_classes", "get_methods", "get_edges",
    "check_vbstyle", "get_bcl_stamps", "to_json", "store",
    "prevent", "top_errors", "cache_stats", "invalidate",
    "UnifiedAst", "CacheDb", "ErrorCapture", "UnifiedConfig",
    "DatabaseManager", "db_query", "db_execute", "db_insert",
    "ConfigCascade", "DomReport", "DomIndexer", "DomReuse", "DomSystem",
    "DomResource",
    "MagneticGraph", "MemoryObject", "Neo4jGraph", "LocalAgent",
    "ExecutionEngine",
]
