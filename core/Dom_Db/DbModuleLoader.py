#!/usr/bin/env python3
# [@GHOST]{[@file<DbModuleLoader.py>][@domain<Dom_Db>][@role<loader>][@auth<cascade>][@date<2026-06-29>][@ver<3.2>][@session<db-runtime-loader>]}
# [@VBSTYLE]{[@return<Tuple3>][@orch<Config>][@model<runtime_db_loader>]}
# [@SUMMARY]{DbModuleLoader v3.2 — deterministic execution: validator-gated compile, import resolver in sys.meta_path, topo-ordered domain loads, structured failure tracking. DB is source of truth.}
# [@CLASS]{DbModuleLoader,DbImportResolver,DbValidator,DbDiagnostics,DbRuntimeManager,DbSystem}
# [@METHOD]{Run,LoadClass,LoadDomain,LoadAll,ReloadClass,ReloadDomain,ReloadAll,UnloadClass,UnloadDomain,LoadAndRun,ListClasses,ValidateGraph,RuntimeState,read_state,set_config,Close}
# [@FILEID]{core/Dom_Db/DbModuleLoader.py}

import ast
import hashlib
import importlib
import importlib.machinery
import os
import sqlite3
import sys
import threading
import time
import types

from core.Dom_Db.Config import Config


###############################################################################
#
# DbModuleLoader
#
###############################################################################

class DbModuleLoader:

    def __init__(self, mem=None, db=None, param=None):

        self.config = Config()

        self.state = {

            "db_path": self.config.state["db_path"],
            "classes_table": self.config.state["classes_table"],
            "class_code_column": self.config.state["class_code_column"],
            "class_name_column": self.config.state["class_name_column"],
            "domain_column": self.config.state["domain_column"],
            "version_column": "version",
            "checksum_column": "checksum",
            "dependency_column": "dependencies",
            "domain_filter": "",
            "conn": None,
            "runtime": {},
            "modules": {},
            "classes": {},
            "instances": {},
            "versions": {},
            "checksums": {},
            "dependencies": {},
            "reverse_dependencies": {},
            "loading": set(),
            "loaded": set(),
            "failed": {},
            "compile_cache": {},
            "reload_queue": [],
            "graph_validated": False,
            "topo_order": [],
            "cascade_reloads": 0,
            "errors": [],
            "warnings": [],
            "stats": {
                "loaded": 0,
                "compiled": 0,
                "executed": 0,
                "reloads": 0,
                "failures": 0,
                "db_queries": 0,
                "graph_validations": 0,
                "cascade_reloads": 0
            }
        }

        self.lock = threading.RLock()

        if isinstance(param, dict):
            self.state.update(param)

    #######################################################################
    #
    # Dispatcher
    #
    #######################################################################

    def Run(self, command, params=None):

        if params is None:
            params = {}

        dispatch = {
            "load_class": self.LoadClass,
            "load_domain": self.LoadDomain,
            "load_all": self.LoadAll,
            "reload_class": self.ReloadClass,
            "reload_domain": self.ReloadDomain,
            "reload_all": self.ReloadAll,
            "unload_class": self.UnloadClass,
            "unload_domain": self.UnloadDomain,
            "load_and_run": self.LoadAndRun,
            "list_classes": self.ListClasses,
            "validate_graph": self.ValidateGraph,
            "runtime": self.RuntimeState,
            "close": self.Close,
            "state": self.read_state,
            "config": self.set_config
        }

        fn = dispatch.get(command)

        if fn is None:
            return (
                0,
                None,
                ("UNKNOWN_COMMAND", "Unknown command " + str(command), 0)
            )

        return fn(params)

    #######################################################################
    #
    # Utilities
    #
    #######################################################################

    def _p(self, params, key, default=None):

        if params is None:
            return default

        return params.get(key, default)

    def _err(self, code, msg):

        err = (code, msg, 0)

        self.state["errors"].append(err)

        self.state["stats"]["failures"] += 1

        return (0, None, err)

    #######################################################################
    #
    # SQL safety
    #
    #######################################################################

    def _ValidateIdentifier(self, name):

        if not isinstance(name, str):
            return False

        if not name:
            return False

        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

        for c in name:
            if c not in allowed:
                return False

        return True

    def _ValidateSchema(self):

        keys = [
            "classes_table",
            "class_name_column",
            "class_code_column",
            "domain_column",
            "version_column",
            "checksum_column",
            "dependency_column"
        ]

        for k in keys:
            if not self._ValidateIdentifier(self.state[k]):
                return self._err(
                    "INVALID_IDENTIFIER",
                    self.state[k]
                )

        return (1, None, None)

    #######################################################################
    #
    # Database
    #
    #######################################################################

    def _Connect(self):

        if self.state["conn"] is not None:
            return (1, self.state["conn"], None)

        ok, _, err = self._ValidateSchema()

        if not ok:
            return (0, None, err)

        db = self.state["db_path"]

        if not os.path.exists(db):
            return self._err(
                "DB_NOT_FOUND",
                db
            )

        conn = sqlite3.connect(db)

        conn.row_factory = sqlite3.Row

        self.state["conn"] = conn

        return (1, conn, None)

    def _Cursor(self):

        ok, conn, err = self._Connect()

        if not ok:
            return (0, None, err)

        self.state["stats"]["db_queries"] += 1

        return (1, conn.cursor(), None)

    def Close(self, params=None):

        with self.lock:
            if self.state["conn"] is not None:
                self.state["conn"].close()
                self.state["conn"] = None

        return (1, {"closed": True}, None)

    def __del__(self):

        try:
            if self.state.get("conn") is not None:
                self.state["conn"].close()
                self.state["conn"] = None
        except Exception:
            pass

    #######################################################################
    #
    # Metadata
    #
    #######################################################################

    def _Checksum(self, code):

        return hashlib.sha256(
            code.encode("utf8")
        ).hexdigest()

    def _ParseDependencies(self, code):

        deps = []

        try:
            tree = ast.parse(code)
        except Exception:
            return deps

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    deps.append(n.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.append(node.module)

        return sorted(set(deps))

    def _ExtractNames(self, code):

        names = set()

        try:
            tree = ast.parse(code)
        except Exception:
            return names

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    names.add(node.value.id)

        builtins_set = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))

        names -= builtins_set

        skip = {"self", "cls", "True", "False", "None", "__name__", "__module__", "__qualname__", "__dict__", "__class__", "__doc__", "__annotations__", "__slots__", "__init__", "__del__", "__str__", "__repr__", "__enter__", "__exit__", "__iter__", "__next__", "__len__", "__getitem__", "__setitem__", "__contains__"}

        names -= skip

        return names

    COMMON_IMPORTS = {
        "Path": "pathlib", "Optional": "typing", "List": "typing",
        "Dict": "typing", "Tuple": "typing", "Any": "typing",
        "Union": "typing", "Set": "typing", "FrozenSet": "typing",
        "Callable": "typing", "Iterator": "typing", "Generator": "typing",
        "Sequence": "typing", "Mapping": "typing", "TypeVar": "typing",
        "Generic": "typing", "dataclass": "dataclasses", "field": "dataclasses",
        "asdict": "dataclasses", "Enum": "enum", "IntEnum": "enum",
        "auto": "enum", "abstractmethod": "abc", "ABC": "abc",
        "wraps": "functools", "lru_cache": "functools", "partial": "functools",
        "reduce": "functools", "namedtuple": "collections",
        "defaultdict": "collections", "OrderedDict": "collections",
        "Counter": "collections", "deque": "collections",
        "ChainMap": "collections", "copy": "copy", "deepcopy": "copy",
        "datetime": "datetime", "date": "datetime", "time": "time",
        "timedelta": "datetime", "timezone": "datetime",
        "Decimal": "decimal", "Fraction": "fractions",
        "uuid": "uuid", "UUID": "uuid", "json": "json",
        "re": "re", "os": "os", "sys": "sys", "math": "math",
        "random": "random", "hashlib": "hashlib", "base64": "base64",
        "struct": "struct", "array": "array", "io": "io",
        "BytesIO": "io", "StringIO": "io", "TextIO": "io",
        "BufferedReader": "io", "TextIOWrapper": "io",
        "threading": "threading", "Lock": "threading", "RLock": "threading",
        "Event": "threading", "Condition": "threading",
        "Semaphore": "threading", "Queue": "queue",
        "LifoQueue": "queue", "PriorityQueue": "queue",
        "SimpleQueue": "queue", "ast": "ast", "types": "types",
        "ModuleType": "types", "FunctionType": "types",
        "MethodType": "types", "sqlite3": "sqlite3",
        "Connection": "sqlite3", "Cursor": "sqlite3", "Row": "sqlite3",
        "tempfile": "tempfile", "NamedTemporaryFile": "tempfile",
        "TemporaryDirectory": "tempfile", "gettempdir": "tempfile",
        "shutil": "shutil", "copyfile": "shutil", "copytree": "shutil",
        "rmtree": "shutil", "move": "shutil", "subprocess": "subprocess",
        "Popen": "subprocess", "PIPE": "subprocess",
        "logging": "logging", "getLogger": "logging",
        "StreamHandler": "logging", "FileHandler": "logging",
        "Formatter": "logging", "warnings": "warnings",
        "traceback": "traceback", "format_exc": "traceback",
        "print_exc": "traceback", "itertools": "itertools",
        "chain": "itertools", "product": "itertools",
        "combinations": "itertools", "permutations": "itertools",
        "cycle": "itertools", "islice": "itertools",
        "groupby": "itertools", "accumulate": "itertools",
        "functools": "functools", "collections": "collections",
        "operator": "operator", "itemgetter": "operator",
        "attrgetter": "operator", "methodcaller": "operator",
        "pathlib": "pathlib", "PurePath": "pathlib",
        "PurePosixPath": "pathlib", "PureWindowsPath": "pathlib",
        "PosixPath": "pathlib", "WindowsPath": "pathlib",
        "contextlib": "contextlib", "contextmanager": "contextlib",
        "suppress": "contextlib", "closing": "contextlib",
        "ExitStack": "contextlib", "weakref": "weakref",
        "WeakValueDictionary": "weakref", "WeakKeyDictionary": "weakref",
        "ref": "weakref", "proxy": "weakref", "gc": "gc",
        "inspect": "inspect", "signature": "inspect",
        "Parameter": "inspect", "textwrap": "textwrap",
        "dedent": "textwrap", "indent": "textwrap",
        "string": "string", "Template": "string",
        "pprint": "pprint", "configparser": "configparser",
        "ConfigParser": "configparser", "argparse": "argparse",
        "ArgumentParser": "argparse", "csv": "csv",
        "glob": "glob", "fnmatch": "fnmatch",
        "pickle": "pickle", "socket": "socket",
        "select": "select", "signal": "signal",
        "mmap": "mmap", "ctypes": "ctypes",
        "errno": "errno", "fcntl": "fcntl", "stat": "stat",
    }

    def _InjectMissing(self, code, module_dict, deps):

        names = self._ExtractNames(code)

        injected = []

        for name in names:
            if name in module_dict:
                continue

            if name in self.state["classes"]:
                module_dict[name] = self.state["classes"][name]
                injected.append(name)
                continue

            ok, row, _ = self._ReadClass(name)
            if ok:
                ok2, runtime, err2 = self._LoadRecursive(name)
                if ok2 and runtime:
                    module_dict[name] = runtime["class"]
                    injected.append(name)
                continue

            if name in sys.modules:
                module_dict[name] = sys.modules[name]
                injected.append(name)
                continue

            if name in self.COMMON_IMPORTS:
                mod_name = self.COMMON_IMPORTS[name]
                if mod_name in sys.modules:
                    mod = sys.modules[mod_name]
                else:
                    try:
                        mod = importlib.import_module(mod_name)
                    except Exception:
                        continue
                if hasattr(mod, name):
                    module_dict[name] = getattr(mod, name)
                    injected.append(name)
                elif mod_name == name:
                    module_dict[name] = mod
                    injected.append(name)
                continue

            try:
                mod = importlib.import_module(name)
                module_dict[name] = mod
                injected.append(name)
            except Exception:
                pass

        return injected

    #######################################################################
    #
    # Dependency Graph — full DB scan + topological sort
    #
    #######################################################################

    def _GetAllDbClassNames(self):

        ok, cur, err = self._Cursor()

        if not ok:
            return []

        sql = """
        SELECT
            %s
        FROM
            %s
        """ % (
            self.state["class_name_column"],
            self.state["classes_table"]
        )

        cur.execute(sql)

        return [r[0] for r in cur.fetchall()]

    def _BuildDependencyGraph(self):

        all_names = self._GetAllDbClassNames()

        all_set = set(all_names)

        graph = {}

        unresolved = {}

        for cn in all_names:
            ok, row, err = self._ReadClass(cn)
            if not ok:
                continue
            code = row[self.state["class_code_column"]]
            if isinstance(code, bytes):
                code = code.decode("utf8", "replace")
            deps = self._ParseDependencies(code)
            db_deps = []
            missing = []
            for dep in deps:
                short = dep.split(".")[-1]
                if short == cn:
                    continue
                if short in all_set:
                    db_deps.append(short)
                else:
                    if short not in sys.modules and dep not in sys.modules:
                        missing.append(dep)
            graph[cn] = db_deps
            if missing:
                unresolved[cn] = missing

        return (graph, unresolved)

    def _TopologicalSort(self, graph):

        visited = set()

        temp_mark = set()

        order = []

        cycles = []

        def visit(node, path):

            if node in visited:
                return True
            if node in temp_mark:
                cycles.append(" -> ".join(path + [node]))
                return False
            temp_mark.add(node)
            for dep in graph.get(node, []):
                if dep in graph:
                    visit(dep, path + [node])
            temp_mark.discard(node)
            visited.add(node)
            order.append(node)
            return True

        for node in sorted(graph.keys()):
            if node not in visited:
                visit(node, [])

        return (order, cycles)

    def ValidateGraph(self, params=None):

        with self.lock:
            self.state["stats"]["graph_validations"] += 1
            graph, unresolved = self._BuildDependencyGraph()
            order, cycles = self._TopologicalSort(graph)
            self.state["topo_order"] = order
            if cycles:
                self.state["graph_validated"] = False
                return (
                    0,
                    None,
                    ("GRAPH_HAS_CYCLES", str(cycles), 0)
                )
            if unresolved:
                self.state["graph_validated"] = False
                self.state["warnings"].append(
                    ("UNRESOLVED_DEPS", str(unresolved), 0)
                )
            self.state["graph_validated"] = True
            return (
                1,
                {
                    "total_classes": len(graph),
                    "topo_order": order,
                    "unresolved": unresolved,
                    "cycles": cycles,
                    "validated": True
                },
                None
            )

    #######################################################################
    #
    # Runtime Registry
    #
    #######################################################################

    def _RegisterRuntime(
        self,
        class_name,
        module_name,
        cls,
        module,
        version,
        checksum,
        dependencies
    ):

        now = time.time()

        self.state["runtime"][class_name] = {
            "class": cls,
            "module": module,
            "module_name": module_name,
            "version": version,
            "checksum": checksum,
            "dependencies": list(dependencies),
            "loaded_at": now,
            "compile_time": now,
            "reload_count": 0,
            "state": "loaded"
        }

        self.state["modules"][module_name] = module

        self.state["classes"][class_name] = cls

        self.state["versions"][class_name] = version

        self.state["checksums"][class_name] = checksum

        self.state["dependencies"][class_name] = list(dependencies)

        for dep in dependencies:
            self.state["reverse_dependencies"].setdefault(dep, set()).add(class_name)

        self.state["loaded"].add(class_name)

        self.state["stats"]["loaded"] += 1

    #######################################################################
    #
    # Read class row
    #
    #######################################################################

    def _ReadClass(self, class_name):

        ok, cur, err = self._Cursor()

        if not ok:
            return (0, None, err)

        sql = """
        SELECT
            *
        FROM
            %s
        WHERE
            %s=?
        """ % (
            self.state["classes_table"],
            self.state["class_name_column"]
        )

        cur.execute(
            sql,
            (class_name,)
        )

        row = cur.fetchone()

        if row is None:
            return self._err(
                "CLASS_NOT_FOUND",
                class_name
            )

        return (1, row, None)

    #######################################################################
    #
    # Recursive loader
    #
    #######################################################################

    def _LoadRecursive(
        self,
        class_name,
        stack=None
    ):

        if stack is None:
            stack = []

        if class_name in self.state["loaded"]:
            runtime = self.state["runtime"][class_name]
            return (1, runtime, None)

        if class_name in stack:
            return self._err(
                "CIRCULAR_DEPENDENCY",
                " -> ".join(stack + [class_name])
            )

        stack.append(class_name)

        ok, row, err = self._ReadClass(class_name)

        if not ok:
            return (0, None, err)

        code = row[self.state["class_code_column"]]

        if isinstance(code, bytes):
            code = code.decode("utf8", "replace")

        checksum = self._Checksum(code)

        version_col = self.state["version_column"]

        if version_col in row.keys():
            version = row[version_col]
        else:
            version = 1

        deps = self._ParseDependencies(code)

        for dep in deps:
            short = dep.split(".")[-1]

            if short == class_name:
                continue

            ok2, _, _ = self._ReadClass(short)

            if ok2:
                ok3, _, err3 = self._LoadRecursive(
                    short,
                    stack[:]
                )

                if not ok3:
                    return self._err(
                        "DEP_LOAD_FAILED",
                        class_name + " depends on " + short + " which failed: " + str(err3)
                    )

        return self._CompileRuntime(
            row,
            code,
            checksum,
            deps,
            version
        )

    #######################################################################
    #
    # Compiler
    #
    #######################################################################

    def _CompileRuntime(
        self,
        row,
        code,
        checksum,
        deps,
        version
    ):

        class_name = row[
            self.state["class_name_column"]
        ]

        domain = row[
            self.state["domain_column"]
        ]

        module_name = "db_runtime." + str(domain) + "." + str(class_name)

        if checksum in self.state["compile_cache"]:
            compiled = self.state["compile_cache"][checksum]
        else:
            from core.Dom_Db.DbModuleLoader import DbValidator
            validator = DbValidator()
            vok, _, verr = validator.validate(code)
            if not vok:
                return self._err(
                    "VALIDATION_FAILED",
                    str(verr)
                )

            try:
                compiled = compile(
                    code,
                    "sqlite://" + str(class_name),
                    "exec"
                )
            except Exception as e:
                return self._err(
                    "COMPILE_ERROR",
                    str(e)
                )

            self.state["compile_cache"][checksum] = compiled

            self.state["stats"]["compiled"] += 1

        module = types.ModuleType(module_name)

        module.__dict__["__db_runtime__"] = True

        module.__dict__["__loader__"] = self

        module.__dict__["__checksum__"] = checksum

        module.__dict__["__domain__"] = domain

        module.__dict__["__runtime__"] = self.state["runtime"]

        for dep in deps:
            short = dep.split(".")[-1]

            if short in self.state["classes"]:
                module.__dict__[short] = self.state["classes"][short]

        self._InjectMissing(code, module.__dict__, deps)

        try:
            exec(
                compiled,
                module.__dict__
            )
        except Exception as e:
            return self._err(
                "EXEC_ERROR",
                str(e)
            )

        cls = getattr(
            module,
            class_name,
            None
        )

        if cls is None:
            return self._err(
                "CLASS_NOT_CREATED",
                class_name
            )

        sys.modules[module_name] = module

        self._RegisterRuntime(
            class_name,
            module_name,
            cls,
            module,
            version,
            checksum,
            deps
        )

        self.state["stats"]["executed"] += 1

        return (
            1,
            self.state["runtime"][class_name],
            None
        )

    #######################################################################
    #
    # Public Loader
    #
    #######################################################################

    def LoadClass(self, params):

        class_name = self._p(params, "class_name")

        if not class_name:
            return self._err(
                "NO_CLASS_NAME",
                "class_name required"
            )

        with self.lock:
            return self._LoadRecursive(class_name)

    #######################################################################
    #
    # Domain Loader
    #
    #######################################################################

    def LoadDomain(self, params):

        domain = self._p(params, "domain")

        if not domain:
            return self._err(
                "NO_DOMAIN",
                "domain required"
            )

        ok, cur, err = self._Cursor()

        if not ok:
            return (0, None, err)

        sql = """
        SELECT
            %s
        FROM
            %s
        WHERE
            %s=?
        ORDER BY
            %s
        """ % (
            self.state["class_name_column"],
            self.state["classes_table"],
            self.state["domain_column"],
            self.state["class_name_column"]
        )

        cur.execute(sql, (domain,))

        rows = cur.fetchall()

        loaded = []

        failed = []

        names = [row[0] for row in rows]

        if self.state["topo_order"]:
            topo = self.state["topo_order"]
            topo_set = set(topo)
            ordered = [n for n in topo if n in names]
            unordered = [n for n in names if n not in topo_set]
            names = ordered + unordered

        for name in names:

            ok2, _, err2 = self._LoadRecursive(name)

            if ok2:
                loaded.append(name)
            else:
                failed.append(
                    {"class": name, "error": err2}
                )
                self.state["failed"][name] = err2

        return (
            1,
            {
                "domain": domain,
                "loaded": loaded,
                "failed": failed,
                "count": len(loaded)
            },
            None
        )

    #######################################################################
    #
    # Load Everything
    #
    #######################################################################

    def LoadAll(self, params):

        if self.state["topo_order"]:
            names = list(self.state["topo_order"])
        else:
            ok, cur, err = self._Cursor()
            if not ok:
                return (0, None, err)
            sql = """
            SELECT
                %s
            FROM
                %s
            ORDER BY
                %s,
                %s
            """ % (
                self.state["class_name_column"],
                self.state["classes_table"],
                self.state["domain_column"],
                self.state["class_name_column"]
            )
            cur.execute(sql)
            names = [r[0] for r in cur.fetchall()]

        loaded = []

        failed = []

        for name in names:

            ok2, _, err2 = self._LoadRecursive(name)

            if ok2:
                loaded.append(name)
            else:
                failed.append(
                    {"class": name, "error": err2}
                )
                self.state["failed"][name] = err2

        return (
            1,
            {
                "loaded": loaded,
                "failed": failed,
                "count": len(loaded)
            },
            None
        )

    #######################################################################
    #
    # Unload
    #
    #######################################################################

    def UnloadClass(self, params):

        class_name = self._p(params, "class_name")

        if class_name not in self.state["runtime"]:
            return self._err("NOT_LOADED", class_name)

        runtime = self.state["runtime"][class_name]

        module_name = runtime["module_name"]

        with self.lock:
            if module_name in sys.modules:
                del sys.modules[module_name]

            self.state["runtime"].pop(class_name, None)
            self.state["classes"].pop(class_name, None)
            self.state["versions"].pop(class_name, None)
            self.state["checksums"].pop(class_name, None)
            self.state["dependencies"].pop(class_name, None)
            self.state["loaded"].discard(class_name)
            self.state["modules"].pop(module_name, None)

        return (1, {"unloaded": class_name}, None)

    #######################################################################
    #
    # Recursive unload
    #
    #######################################################################

    def UnloadDomain(self, params):

        domain = self._p(params, "domain")

        unload = []

        for name in list(self.state["runtime"].keys()):
            runtime = self.state["runtime"][name]
            if runtime["module"].__dict__.get("__domain__") == domain:
                self.UnloadClass({"class_name": name})
                unload.append(name)

        return (
            1,
            {
                "domain": domain,
                "count": len(unload),
                "classes": unload
            },
            None
        )

    #######################################################################
    #
    # Reload
    #
    #######################################################################

    def ReloadClass(self, params):

        class_name = self._p(params, "class_name")

        cascade = self._p(params, "cascade", True)

        cascaded = []

        with self.lock:
            if class_name in self.state["runtime"]:
                self.UnloadClass({"class_name": class_name})

            self.state["stats"]["reloads"] += 1

            ok, data, err = self.LoadClass({"class_name": class_name})

            if not ok:
                return (0, None, err)

            if cascade:
                rev_deps = self.state["reverse_dependencies"].get(class_name, set())

                for dependent in list(rev_deps):
                    if dependent in self.state["loaded"]:
                        self.UnloadClass({"class_name": dependent})
                        ok2, _, err2 = self.LoadClass({"class_name": dependent})
                        if ok2:
                            cascaded.append(dependent)
                        else:
                            self.state["warnings"].append(
                                ("CASCADE_RELOAD_FAILED", dependent + " -> " + str(err2), 0)
                            )

                if cascaded:
                    self.state["stats"]["cascade_reloads"] += len(cascaded)

            return (
                1,
                {
                    "class": class_name,
                    "state": "loaded",
                    "cascaded": cascaded,
                    "cascade_count": len(cascaded)
                },
                None
            )

    def ReloadDomain(self, params):

        self.UnloadDomain(params)

        return self.LoadDomain(params)

    def ReloadAll(self, params):

        names = list(self.state["runtime"].keys())

        for name in names:
            self.UnloadClass({"class_name": name})

        self.state["stats"]["reloads"] += 1

        return self.LoadAll({})

    #######################################################################
    #
    # Load and Run
    #
    #######################################################################

    def LoadAndRun(self, params):

        class_name = self._p(params, "class_name")

        if not class_name:
            return self._err(
                "NO_CLASS_NAME",
                "class_name required"
            )

        command = self._p(params, "command", "Run")

        run_params = self._p(params, "params", {})

        ok, runtime, err = self.LoadClass(
            {"class_name": class_name}
        )

        if not ok:
            return (0, None, err)

        cls = runtime["class"]

        try:
            instance = cls()
        except Exception as e:
            return self._err(
                "INSTANTIATE_ERROR",
                str(e)
            )

        if hasattr(instance, "Run"):
            try:
                return instance.Run(command, run_params)
            except TypeError:
                if hasattr(instance, command):
                    method = getattr(instance, command)
                    try:
                        return method()
                    except TypeError:
                        return method(run_params)

        if hasattr(instance, command):
            method = getattr(instance, command)
            try:
                if run_params:
                    return method(run_params)
                return method()
            except Exception as e:
                return self._err(
                    "EXEC_ERROR",
                    str(e)
                )

        return self._err(
            "NO_METHOD",
            "No Run() or method " + str(command)
        )

    #######################################################################
    #
    # List Classes
    #
    #######################################################################

    def ListClasses(self, params):

        domain_filter = self._p(params, "domain")

        ok, cur, err = self._Cursor()

        if not ok:
            return (0, None, err)

        if domain_filter:

            sql = """
            SELECT
                %s,
                %s
            FROM
                %s
            WHERE
                %s=?
            ORDER BY
                %s
            """ % (
                self.state["class_name_column"],
                self.state["domain_column"],
                self.state["classes_table"],
                self.state["domain_column"],
                self.state["class_name_column"]
            )

            cur.execute(sql, (domain_filter,))

        else:

            sql = """
            SELECT
                %s,
                %s
            FROM
                %s
            ORDER BY
                %s,
                %s
            """ % (
                self.state["class_name_column"],
                self.state["domain_column"],
                self.state["classes_table"],
                self.state["domain_column"],
                self.state["class_name_column"]
            )

            cur.execute(sql)

        rows = cur.fetchall()

        classes = []

        for r in rows:
            classes.append(
                {
                    "class_name": r[self.state["class_name_column"]],
                    "domain": r[self.state["domain_column"]]
                }
            )

        return (
            1,
            {
                "classes": classes,
                "count": len(classes)
            },
            None
        )

    #######################################################################
    #
    # Runtime state
    #
    #######################################################################

    def RuntimeState(self, params=None):

        return (
            1,
            {
                "runtime": self.state["runtime"],
                "loaded": list(self.state["loaded"]),
                "failed": self.state["failed"],
                "stats": self.state["stats"],
                "cache_size": len(self.state["compile_cache"])
            },
            None
        )

    #######################################################################
    #
    # Read state
    #
    #######################################################################

    def read_state(self, params=None):

        safe = dict(self.state)

        safe.pop("conn", None)

        return (
            1,
            safe,
            None
        )

    #######################################################################
    #
    # Config
    #
    #######################################################################

    def set_config(self, params=None):

        if not params:
            return self._err(
                "NO_PARAMS",
                "missing config"
            )

        cfg = params.get("config", params)

        if isinstance(cfg, dict):
            self.state.update(cfg)

        return (
            1,
            dict(self.state),
            None
        )


###############################################################################
#
# DbImportResolver
#
###############################################################################

class DbImportResolver:

    def __init__(self, loader):

        self.loader = loader

        self.state = {
            "import_cache": {},
            "module_map": {},
            "reverse_map": {},
            "resolution_stack": set()
        }

    ###########################################################################
    #
    # Public hook
    #
    ###########################################################################

    def find_spec(self, fullname, path=None, target=None):

        if fullname in self.state["import_cache"]:
            return self.state["import_cache"][fullname]

        if self._exists_in_db(fullname):
            spec = self._build_spec(fullname)
            self.state["import_cache"][fullname] = spec
            return spec

        return None

    ###########################################################################
    #
    # Loader entry
    #
    ###########################################################################

    def exec_module(self, module):

        name = module.__name__

        if name in self.state["resolution_stack"]:
            raise ImportError("Circular import detected: " + name)

        self.state["resolution_stack"].add(name)

        try:
            ok, row, err = self._fetch(name)

            if not ok:
                raise ImportError(str(err))

            code = row[self.loader.state["class_code_column"]]

            if isinstance(code, bytes):
                code = code.decode("utf8", "replace")

            compiled = compile(code, name, "exec")

            exec(compiled, module.__dict__)

            self.state["module_map"][name] = module

        finally:
            self.state["resolution_stack"].discard(name)

        return module

    ###########################################################################
    #
    # DB access
    #
    ###########################################################################

    def _fetch(self, fullname):

        ok, cur, err = self.loader._Cursor()

        if not ok:
            return (0, None, err)

        sql = """
        SELECT
            *
        FROM
            %s
        WHERE
            %s=?
        """ % (
            self.loader.state["classes_table"],
            self.loader.state["class_name_column"]
        )

        cur.execute(sql, (fullname.split(".")[-1],))

        row = cur.fetchone()

        if row is None:
            return (0, None, ("NOT_FOUND", fullname, 0))

        return (1, row, None)

    ###########################################################################
    #
    # Existence check
    #
    ###########################################################################

    def _exists_in_db(self, fullname):

        ok, row, _ = self._fetch(fullname)

        return bool(ok)

    ###########################################################################
    #
    # Spec builder
    #
    ###########################################################################

    def _build_spec(self, fullname):

        return importlib.machinery.ModuleSpec(
            name=fullname,
            loader=self
        )


###############################################################################
#
# DbValidator
#
###############################################################################

class DbValidator:

    def __init__(self):

        self.state = {
            "errors": []
        }

    ###########################################################################
    #
    # Validate code safety
    #
    ###########################################################################

    def validate(self, code):

        try:
            tree = ast.parse(code)
        except Exception as e:
            return (0, None, ("SYNTAX_ERROR", str(e), 0))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = getattr(node.func, "id", None)
                if func_name == "exec":
                    return (0, None, ("EXEC_FORBIDDEN", "exec not allowed", 0))
                if func_name == "eval":
                    return (0, None, ("EVAL_FORBIDDEN", "eval not allowed", 0))

        return (1, True, None)


###############################################################################
#
# DbDiagnostics
#
###############################################################################

class DbDiagnostics:

    def __init__(self, loader):

        self.loader = loader

    ###########################################################################
    #
    # Dump runtime graph
    #
    ###########################################################################

    def dump_graph(self):

        graph = {}

        for k, v in self.loader.state["dependencies"].items():
            graph[k] = list(v)

        return (1, graph, None)

    ###########################################################################
    #
    # Find broken classes
    #
    ###########################################################################

    def find_failures(self):

        return (
            1,
            self.loader.state["failed"],
            None
        )

    ###########################################################################
    #
    # Dependency reverse lookup
    #
    ###########################################################################

    def reverse_dependencies(self, class_name):

        return (
            1,
            list(self.loader.state["reverse_dependencies"].get(class_name, [])),
            None
        )


###############################################################################
#
# DbRuntimeManager
#
###############################################################################

class DbRuntimeManager:

    def __init__(self, loader):

        self.loader = loader

        self.state = {
            "watchers": {},
            "events": [],
            "reload_queue": set(),
            "lock": loader.lock
        }

    ###########################################################################
    #
    # Event emit
    #
    ###########################################################################

    def emit(self, event, payload):

        self.state["events"].append(
            {
                "event": event,
                "payload": payload,
                "time": time.time()
            }
        )

        watchers = self.state["watchers"].get(event, [])

        for w in watchers:
            try:
                w(payload)
            except Exception:
                pass

        return (1, True, None)

    ###########################################################################
    #
    # Watch registration
    #
    ###########################################################################

    def watch(self, event, callback):

        self.state["watchers"].setdefault(event, []).append(callback)

        return (1, True, None)

    ###########################################################################
    #
    # Hot reload trigger
    #
    ###########################################################################

    def mark_reload(self, class_name):

        self.state["reload_queue"].add(class_name)

        return (1, True, None)

    ###########################################################################
    #
    # Process reload queue
    #
    ###########################################################################

    def process_reload(self):

        results = []

        for name in list(self.state["reload_queue"]):
            ok, data, err = self.loader.ReloadClass(
                {"class_name": name}
            )
            results.append(
                {
                    "class": name,
                    "result": (ok, data, err)
                }
            )
            self.state["reload_queue"].discard(name)

        return (1, results, None)

    ###########################################################################
    #
    # Runtime stats snapshot
    #
    ###########################################################################

    def snapshot(self):

        return (
            1,
            {
                "events": len(self.state["events"]),
                "watchers": {
                    k: len(v) for k, v in self.state["watchers"].items()
                },
                "reload_queue": list(self.state["reload_queue"])
            },
            None
        )


###############################################################################
#
# DbSystem — unified entry point
#
###############################################################################

class DbSystem:

    def __init__(self):

        self.loader = DbModuleLoader()

        self.resolver = DbImportResolver(self.loader)

        self.validator = DbValidator()

        self.diagnostics = DbDiagnostics(self.loader)

        self.runtime = DbRuntimeManager(self.loader)

        if self.resolver not in sys.meta_path:
            sys.meta_path.insert(0, self.resolver)

    def Close(self):

        if self.resolver in sys.meta_path:
            sys.meta_path.remove(self.resolver)

        return self.loader.Close()

    def Run(self, cmd, params=None):

        if cmd == "load":
            return self.loader.LoadClass(params)

        if cmd == "domain":
            return self.loader.LoadDomain(params)

        if cmd == "all":
            return self.loader.LoadAll(params)

        if cmd == "run":
            return self.loader.LoadAndRun(params)

        if cmd == "graph":
            return self.diagnostics.dump_graph()

        if cmd == "failures":
            return self.diagnostics.find_failures()

        if cmd == "snapshot":
            return self.runtime.snapshot()

        if cmd == "list":
            return self.loader.ListClasses(params)

        if cmd == "validate_graph":
            return self.loader.ValidateGraph(params)

        if cmd == "unload":
            return self.loader.UnloadClass(params)

        if cmd == "reload":
            return self.loader.ReloadClass(params)

        if cmd == "close":
            return self.loader.Close(params)

        return (
            0,
            None,
            ("UNKNOWN_CMD", cmd, 0)
        )
