#!/usr/bin/env python3
"""
DbMethodProxy — method-level lazy loader.

Strip methods out of .py files. When a method is called and doesn't
exist on the object, intercept via __getattr__, pull source_code from
the methods SQLite DB, compile it, bind it to the instance, run it.

This is the complement to DbModuleLoader:
  - DbModuleLoader loads whole CLASSES from DB
  - DbMethodProxy loads individual METHODS from DB

Usage:
  # In your class, inherit from DbMethodProxy:
  class AgentBrain(DbMethodProxy):
      def __init__(self):
          super().__init__(class_name="AgentBrain")
          self.state = {}

      # Run() is NOT defined here — it's in the DB.
      # When someone calls agent.Run("scan"), __getattr__ fetches it.

  # Or: strip methods at import time using the stripper.
  # The file keeps the class shell, methods get loaded from DB on demand.
"""

import sqlite3
import ast
import types
import time
import threading
from typing import Dict, Optional, Tuple


class DbMethodProxy:
    """
    Base class that intercepts missing method calls and loads
    the method source from the methods SQLite DB on demand.

    First call:  DB query + compile + exec + cache  (~1ms)
    Next calls:  direct from cache                   (~0ms)
    """

    DB_PATH = "/tmp/methods.sqlite"

    _shared_conn = None
    _shared_lock = threading.RLock()
    _shared_cache: Dict[str, object] = {}

    def __init__(self, class_name: str = None, db_path: str = None):
        cls = type(self)
        if db_path:
            cls.DB_PATH = db_path
        self.__dict__["_proxy_class_name"] = class_name or type(self).__name__
        self.__dict__["_proxy_cache"] = {}

    @classmethod
    def _GetConn(cls) -> sqlite3.Connection:
        with cls._shared_lock:
            if cls._shared_conn is None:
                cls._shared_conn = sqlite3.connect(cls.DB_PATH)
                cls._shared_conn.row_factory = sqlite3.Row
            return cls._shared_conn

    @classmethod
    def _GetMethodSource(cls, class_name: str, method_name: str) -> Optional[str]:
        """Query the methods DB for source_code by class + method name."""
        cache_key = class_name + "." + method_name
        if cache_key in cls._shared_cache:
            return cls._shared_cache[cache_key]

        conn = cls._GetConn()
        row = conn.execute(
            "SELECT source_code, arg_names, returns FROM ci_methods "
            "WHERE class_name = ? AND name = ? "
            "ORDER BY def_id LIMIT 1",
            (class_name, method_name)
        ).fetchone()

        if row is None or not row["source_code"]:
            return None

        source = row["source_code"]
        cls._shared_cache[cache_key] = source
        return source

    def __getattr__(self, name: str):
        """
        Called when normal attribute lookup fails.
        This means the method was stripped from the class.
        Fetch it from DB, compile, bind, return as callable.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        class_name = self.__dict__.get("_proxy_class_name", type(self).__name__)

        source = self._GetMethodSource(class_name, name)
        if source is None:
            raise AttributeError(
                f"Method {class_name}.{name} not found in DB or file"
            )

        # Parse the source — it's a function def like: def name(self, ...): ...
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise AttributeError(f"Method {class_name}.{name} has syntax error: {e}")

        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    func_def = node
                    break

        if func_def is None:
            raise AttributeError(f"Method {class_name}.{name} not found in source")

        # Compile the function in an isolated namespace
        module_dict = {"__name__": f"db_method.{class_name}"}

        # Inject common imports the method might need
        self._InjectImports(module_dict)

        # Inject other loaded classes if available
        self._InjectClassRefs(module_dict, class_name)

        try:
            code_obj = compile(tree, f"<db://{class_name}.{name}>", "exec")
            exec(code_obj, module_dict)
        except Exception as e:
            raise AttributeError(f"Method {class_name}.{name} compile failed: {e}")

        func = module_dict.get(name)
        if func is None:
            raise AttributeError(f"Method {class_name}.{name} not created after exec")

        # Bind to this instance
        bound = types.MethodType(func, self)

        # Cache on instance so __getattr__ isn't called again
        self.__dict__[name] = bound

        return bound

    def _InjectImports(self, module_dict: dict):
        """Inject common imports the method body might reference."""
        import os, sys, time, json, re, sqlite3, hashlib
        import ast as _ast
        import collections
        import threading
        import typing
        import traceback
        import functools
        import itertools
        import copy
        import math
        import random
        import textwrap
        import io
        import uuid
        import logging
        import warnings
        import subprocess
        import pathlib
        import inspect
        import struct
        import base64
        import binascii
        import operator
        import string
        import pprint
        import argparse
        import configparser
        import csv
        import glob
        import fnmatch
        import pickle
        import socket
        import select
        import signal
        import mmap
        import ctypes
        import errno
        import fcntl
        import stat
        import shutil
        import tempfile
        import weakref
        import gc
        import contextlib
        import decimal
        import fractions
        import array
        import queue
        import dataclasses
        import enum
        import abc
        import bisect
        import heapq
        import numbers
        import statistics
        import types as _types
        import unittest
        import doctest

        std_imports = {
            "os": os, "sys": sys, "time": time, "json": json, "re": re,
            "sqlite3": sqlite3, "hashlib": hashlib, "ast": _ast,
            "collections": collections, "threading": threading,
            "typing": typing, "traceback": traceback, "functools": functools,
            "itertools": itertools, "copy": copy, "math": math,
            "random": random, "textwrap": textwrap, "io": io,
            "uuid": uuid, "logging": logging, "warnings": warnings,
            "subprocess": subprocess, "pathlib": pathlib,
            "inspect": inspect, "struct": struct, "base64": base64,
            "binascii": binascii, "operator": operator, "string": string,
            "pprint": pprint, "argparse": argparse, "configparser": configparser,
            "csv": csv, "glob": glob, "fnmatch": fnmatch, "pickle": pickle,
            "socket": socket, "select": select, "signal": signal,
            "mmap": mmap, "ctypes": ctypes, "errno": errno, "fcntl": fcntl,
            "stat": stat, "shutil": shutil, "tempfile": tempfile,
            "weakref": weakref, "gc": gc, "contextlib": contextlib,
            "decimal": decimal, "fractions": fractions, "array": array,
            "queue": queue, "dataclasses": dataclasses, "enum": enum,
            "abc": abc, "bisect": bisect, "heapq": heapq,
            "numbers": numbers, "statistics": statistics, "types": _types,
            "unittest": unittest, "doctest": doctest,
        }

        typing_names = {
            "Optional", "List", "Dict", "Tuple", "Any", "Union", "Set",
            "FrozenSet", "Callable", "Iterator", "Generator", "Sequence",
            "Mapping", "TypeVar", "Generic", "NoReturn", "ClassVar",
            "TYPE_CHECKING", "overload", "final", "Protocol", "runtime_checkable",
        }
        for tn in typing_names:
            if hasattr(typing, tn):
                std_imports[tn] = getattr(typing, tn)

        collections_names = {
            "defaultdict", "OrderedDict", "Counter", "deque", "namedtuple",
            "ChainMap",
        }
        for cn in collections_names:
            if hasattr(collections, cn):
                std_imports[cn] = getattr(collections, cn)

        functools_names = {"wraps", "lru_cache", "partial", "reduce", "singledispatch"}
        for fn in functools_names:
            if hasattr(functools, fn):
                std_imports[fn] = getattr(functools, fn)

        itertools_names = {
            "chain", "product", "combinations", "permutations",
            "cycle", "islice", "groupby", "accumulate", "count",
            "repeat", "starmap", "tee", "zip_longest",
        }
        for in_ in itertools_names:
            if hasattr(itertools, in_):
                std_imports[in_] = getattr(itertools, in_)

        dataclasses_names = {"dataclass", "field", "asdict", "astuple", "replace"}
        for dn in dataclasses_names:
            if hasattr(dataclasses, dn):
                std_imports[dn] = getattr(dataclasses, dn)

        contextlib_names = {"contextmanager", "suppress", "closing", "ExitStack"}
        for cn in contextlib_names:
            if hasattr(contextlib, cn):
                std_imports[cn] = getattr(contextlib, cn)

        pathlib_names = {"Path", "PurePath", "PurePosixPath", "PosixPath"}
        for pn in pathlib_names:
            if hasattr(pathlib, pn):
                std_imports[pn] = getattr(pathlib, pn)

        io_names = {"BytesIO", "StringIO", "TextIO", "BufferedReader", "TextIOWrapper"}
        for in_ in io_names:
            if hasattr(io, in_):
                std_imports[in_] = getattr(io, in_)

        threading_names = {"Lock", "RLock", "Event", "Condition", "Semaphore", "Thread"}
        for tn in threading_names:
            if hasattr(threading, tn):
                std_imports[tn] = getattr(threading, tn)

        queue_names = {"Queue", "LifoQueue", "PriorityQueue", "SimpleQueue"}
        for qn in queue_names:
            if hasattr(queue, qn):
                std_imports[qn] = getattr(queue, qn)

        enum_names = {"Enum", "IntEnum", "auto", "Flag", "IntFlag"}
        for en in enum_names:
            if hasattr(enum, en):
                std_imports[en] = getattr(enum, en)

        abc_names = {"ABC", "abstractmethod", "abstractproperty"}
        for an in abc_names:
            if hasattr(abc, an):
                std_imports[an] = getattr(abc, an)

        module_dict.update(std_imports)

    def _InjectClassRefs(self, module_dict: dict, current_class: str):
        """Inject references to other classes that are already loaded in sys.modules."""
        import sys
        for key, val in list(sys.modules.items()):
            if key.startswith("db_runtime."):
                short = key.split(".")[-1]
                if short != current_class:
                    module_dict[short] = val

    @classmethod
    def ClearCache(cls):
        """Clear the shared method cache."""
        with cls._shared_lock:
            cls._shared_cache.clear()

    @classmethod
    def CacheStats(cls) -> dict:
        """Return cache statistics."""
        with cls._shared_lock:
            return {
                "cached_methods": len(cls._shared_cache),
                "db_path": cls.DB_PATH,
            }

    @classmethod
    def PreloadClassMethods(cls, class_name: str) -> int:
        """Preload all methods for a class into cache."""
        conn = cls._GetConn()
        rows = conn.execute(
            "SELECT name, source_code FROM ci_methods WHERE class_name = ?",
            (class_name,)
        ).fetchall()
        count = 0
        for r in rows:
            key = class_name + "." + r["name"]
            if r["source_code"]:
                cls._shared_cache[key] = r["source_code"]
                count += 1
        return count


# ---------------------------------------------------------------------------
# METHOD STRIPPER — remove methods from .py files, keep class shells
# ---------------------------------------------------------------------------

class MethodStripper:
    """
    Strip methods from a Python file, leaving only the class shell.
    Methods are expected to be in the DB already.

    Usage:
        stripper = MethodStripper()
        stripped = stripper.strip_file("path/to/file.py", keep=["__init__"])
        # Write stripped code back to file
    """

    def __init__(self, db_path: str = "/tmp/methods.sqlite"):
        self.db_path = db_path

    def strip_file(self, file_path: str, keep: set = None) -> Tuple[str, list]:
        """
        Read a .py file, remove method bodies that exist in the DB.
        Keep methods in the 'keep' set (like __init__).
        Returns (stripped_source, list_of_stripped_methods).
        """
        if keep is None:
            keep = {"__init__"}

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, []

        stripped_methods = []

        class StripVisitor(ast.NodeTransformer):
            def visit_ClassDef(self, node):
                self.generic_visit(node)
                new_body = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name in keep:
                            new_body.append(item)
                        else:
                            stripped_methods.append(
                                f"{node.name}.{item.name}"
                            )
                    else:
                        new_body.append(item)
                node.body = new_body if new_body else [ast.Pass()]
                return node

        new_tree = StripVisitor().visit(tree)
        new_source = ast.unparse(new_tree)

        return new_source, stripped_methods

    def strip_class(self, source: str, class_name: str, keep: set = None) -> Tuple[str, list]:
        """Strip methods from a single class definition in source code."""
        if keep is None:
            keep = {"__init__"}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, []

        stripped_methods = []

        class StripOneClass(ast.NodeTransformer):
            def visit_ClassDef(self, node):
                if node.name == class_name:
                    self.generic_visit(node)
                    new_body = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name in keep:
                                new_body.append(item)
                            else:
                                stripped_methods.append(item.name)
                        else:
                            new_body.append(item)
                    node.body = new_body if new_body else [ast.Pass()]
                return node

        new_tree = StripOneClass().visit(tree)
        new_source = ast.unparse(new_tree)

        return new_source, stripped_methods


# ---------------------------------------------------------------------------
# TEST / DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== DB METHOD PROXY TEST ===")
    print()

    # Test 1: Load a method from DB and call it
    print("--- Test 1: Load method from DB on demand ---")

    class TestAgent(DbMethodProxy):
        def __init__(self):
            super().__init__(class_name="AgentBrain")
            self.state = {"calls": 0}

    agent = TestAgent()

    # AgentBrain.Run should be in the DB
    print(f"  Cache before: {DbMethodProxy.CacheStats()}")

    t0 = time.time()
    try:
        result = agent.Run("read_state", {})
        t1 = time.time()
        print(f"  agent.Run('read_state', {{}}) = {result}")
        print(f"  Time: {(t1-t0)*1000:.1f}ms (first call — DB + compile)")
    except AttributeError as e:
        t1 = time.time()
        print(f"  agent.Run not available: {e}")
        print(f"  Time: {(t1-t0)*1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        print(f"  agent.Run raised: {type(e).__name__}: {e}")
        print(f"  Time: {(t1-t0)*1000:.1f}ms")

    t2 = time.time()
    try:
        result2 = agent.Run("read_state", {})
        t3 = time.time()
        print(f"  agent.Run('read_state', {{}}) second call = {result2}")
        print(f"  Time: {(t3-t2)*1000:.1f}ms (cached — should be ~0ms)")
    except Exception as e:
        t3 = time.time()
        print(f"  Second call raised: {type(e).__name__}: {e}")

    print(f"  Cache after: {DbMethodProxy.CacheStats()}")

    # Test 2: Try a different class
    print()
    print("--- Test 2: Different class ---")

    class TestConfig(DbMethodProxy):
        def __init__(self):
            super().__init__(class_name="Config")
            self.state = {"version": "1.0", "loaded": True}

    cfg = TestConfig()
    try:
        result = cfg.read_state(None)
        print(f"  Config.read_state(None) = {result}")
    except Exception as e:
        print(f"  Config.read_state(None) raised: {type(e).__name__}: {e}")

    # Test 3: Preload all methods for a class
    print()
    print("--- Test 3: Preload class methods ---")
    count = DbMethodProxy.PreloadClassMethods("AgentBrain")
    print(f"  Preloaded {count} methods for AgentBrain")
    print(f"  Cache: {DbMethodProxy.CacheStats()}")

    # Test 4: Strip a file
    print()
    print("--- Test 4: Method stripper ---")
    stripper = MethodStripper()

    # Create a test file
    test_code = """
class Foo:
    def __init__(self):
        self.x = 1

    def bar(self):
        return self.x + 1

    def baz(self, n):
        return self.x * n

    def qux(self):
        return str(self.x)
"""

    stripped, removed = stripper.strip_class(test_code, "Foo", keep={"__init__"})
    print(f"  Stripped methods: {removed}")
    print(f"  Stripped code:")
    for line in stripped.strip().split("\n"):
        print(f"    {line}")

    # Test 5: Verify stripped + proxy works
    print()
    print("--- Test 5: Stripped class + proxy = methods from DB ---")

    # The stripped class only has __init__, but inherits DbMethodProxy
    # Methods like read_state, Run, set_config will come from DB
    test_code_with_proxy = """
class FooProxy(DbMethodProxy):
    def __init__(self):
        super().__init__(class_name="Config")
        self.x = 42
        self.state = {"x": 42, "source": "db_proxy"}
"""
    # Execute it
    ns = {"DbMethodProxy": DbMethodProxy}
    exec(test_code_with_proxy, ns)
    FooProxy = ns["FooProxy"]
    fp = FooProxy()
    print(f"  fp.x = {fp.x}")
    try:
        r = fp.read_state(None)
        print(f"  fp.read_state(None) = {r}  (loaded from DB)")
    except Exception as e:
        print(f"  fp.read_state(None) raised: {type(e).__name__}: {e}")

    print()
    print("=== ALL TESTS DONE ===")
    print(f"  Final cache: {DbMethodProxy.CacheStats()}")
