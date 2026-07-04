#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Bcl_C_ver/BclConfig.py" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Config class for BCL C engine — makes backend selectable (MySQL/SQLite), compile paths configurable, persists to JSON"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="BclConfig.py" domain="bcl_c_engine" authority="bcl_config"}
#[@SUMMARY]{summary="Config for BCL C engine. Backend selectable: mysql | sqlite. Compile/link paths auto-detected from Homebrew. Persists to bcl_config.json. Run() dispatch: get | set | save | load | list | read_state | set_config | build_db."}
#[@CLASS]{class="BclConfig" domain="bcl_c_engine" authority="single"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="Get" type="command"}
#[@METHOD]{method="Set" type="command"}
#[@METHOD]{method="Save" type="command"}
#[@METHOD]{method="Load" type="command"}
#[@METHOD]{method="List" type="command"}
#[@METHOD]{method="BuildDb" type="command"}
#[@METHOD]{method="DetectPaths" type="command"}
#[@METHOD]{method="_p" type="helper"}
#[@METHOD]{method="read_state" type="command"}
#[@METHOD]{method="set_config" type="command"}
#[@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Config for BCL C engine. Backend selectable, paths auto-detected, persists to JSON.>][@todos<none>]}

"""
BclConfig — Configuration for the BCL C engine.

Makes the backend selectable (MySQL or SQLite) and all compile/link
paths configurable. Auto-detects Homebrew paths on macOS. Persists
settings to bcl_config.json so they survive across sessions.

Usage:
    cfg = BclConfig()
    cfg.Run("load")                    # load from bcl_config.json
    cfg.Run("get", {"key": "backend"}) # get single value
    cfg.Run("set", {"backend": "sqlite"})  # switch backend
    cfg.Run("save")                    # persist to JSON

Backends:
    mysql  — vb_shared.c_classes (default, production)
    sqlite — local .db file (development, offline)

The loader (bcl_c_loader.py) reads this config to know:
    - Which DB backend to use
    - Connection params (host, user, db name, table)
    - Compile/link commands and library paths
    - Output directory and binary name
"""

import json
import os
import subprocess

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcl_config.json")

DEFAULT_CONFIG = {
    "backend": "mysql",
    "domain": "bcl_c_engine",
    "output_dir": os.path.dirname(os.path.abspath(__file__)),
    "binary_name": "dom_graph_engine",
    "mysql": {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "vb_shared",
        "table": "c_classes",
        "port": 3306,
    },
    "sqlite": {
        "path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcl_c_engine.db"),
        "table": "c_classes",
    },
    "compile": {
        "cc": "cc",
        "cflags": "-O2 -Wall -Wextra -Wno-unused-parameter -DCASCADE_USE_MYSQL",
        "tree_sitter_inc": "",
        "tree_sitter_lib": "",
        "tree_sitter_python_inc": "",
        "tree_sitter_python_lib": "",
        "tree_sitter_c_inc": "",
        "tree_sitter_c_lib": "",
        "json_c_inc": "",
        "json_c_lib": "",
        "sqlite_inc": "",
        "sqlite_lib": "",
        "mysql_inc": "",
        "mysql_lib": "",
        "ssl_lib": "",
        "extra_libs": "-lz -lresolv",
    },
    "link": {
        "rpaths": [],
        "extra_flags": "",
    },
}


class BclConfig:
    """Config for BCL C engine — backend selectable, paths configurable."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": dict(DEFAULT_CONFIG),
            "config_path": CONFIG_PATH,
            "loaded": False,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        if os.path.exists(self.state["config_path"]):
            self.Load({})
        self.DetectPaths({})

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "get": self.Get,
            "set": self.Set,
            "save": self.Save,
            "load": self.Load,
            "list": self.List,
            "build_db": self.BuildDb,
            "detect_paths": self.DetectPaths,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def DetectPaths(self, params):
        """Auto-detect Homebrew paths for tree-sitter, mysql, openssl."""
        cfg = self.state["config"]
        compile_cfg = cfg["compile"]
        link_cfg = cfg["link"]

        def brew_prefix(formula):
            try:
                r = subprocess.run(
                    ["brew", "--prefix", formula],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    return r.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            return None

        def brew_cellar(formula):
            try:
                r = subprocess.run(
                    ["brew", "--cellar", formula],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    return r.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            return None

        def list_versions(cellar):
            if not cellar or not os.path.isdir(cellar):
                return None
            versions = sorted(os.listdir(cellar))
            return versions[-1] if versions else None

        ts_prefix = brew_prefix("tree-sitter")
        ts_cellar = brew_cellar("tree-sitter")
        ts_ver = list_versions(ts_cellar) if ts_cellar else None
        if ts_prefix and ts_ver:
            compile_cfg["tree_sitter_inc"] = os.path.join(ts_cellar, ts_ver, "include")
            compile_cfg["tree_sitter_lib"] = os.path.join(ts_cellar, ts_ver, "lib")

        tsp_prefix = brew_prefix("tree-sitter-python")
        tsp_cellar = brew_cellar("tree-sitter-python")
        tsp_ver = list_versions(tsp_cellar) if tsp_cellar else None
        if tsp_prefix and tsp_ver:
            compile_cfg["tree_sitter_python_inc"] = os.path.join(tsp_cellar, tsp_ver, "include")
            compile_cfg["tree_sitter_python_lib"] = os.path.join(tsp_cellar, tsp_ver, "lib")

        tsc_prefix = brew_prefix("tree-sitter-c")
        tsc_cellar = brew_cellar("tree-sitter-c")
        tsc_ver = list_versions(tsc_cellar) if tsc_cellar else None
        if tsc_prefix and tsc_ver:
            compile_cfg["tree_sitter_c_inc"] = os.path.join(tsc_cellar, tsc_ver, "include")
            compile_cfg["tree_sitter_c_lib"] = os.path.join(tsc_cellar, tsc_ver, "lib")

        jsonc_prefix = brew_prefix("json-c")
        if jsonc_prefix:
            compile_cfg["json_c_inc"] = os.path.join(jsonc_prefix, "include")
            compile_cfg["json_c_lib"] = os.path.join(jsonc_prefix, "lib")

        sqlite_prefix = brew_prefix("sqlite")
        if sqlite_prefix:
            compile_cfg["sqlite_inc"] = os.path.join(sqlite_prefix, "include")
            compile_cfg["sqlite_lib"] = os.path.join(sqlite_prefix, "lib")

        mysql_prefix = brew_prefix("mysql@8.0")
        if mysql_prefix:
            compile_cfg["mysql_inc"] = os.path.join(mysql_prefix, "include", "mysql")
            compile_cfg["mysql_lib"] = os.path.join(mysql_prefix, "lib")

        ssl_prefix = brew_prefix("openssl@3")
        if ssl_prefix:
            compile_cfg["ssl_lib"] = os.path.join(ssl_prefix, "lib")

        rpaths = []
        if compile_cfg.get("tree_sitter_lib"):
            rpaths.append(compile_cfg["tree_sitter_lib"])
        if compile_cfg.get("tree_sitter_python_lib"):
            rpaths.append(compile_cfg["tree_sitter_python_lib"])
        if compile_cfg.get("tree_sitter_c_lib"):
            rpaths.append(compile_cfg["tree_sitter_c_lib"])
        if compile_cfg.get("json_c_lib"):
            rpaths.append(compile_cfg["json_c_lib"])
        if compile_cfg.get("sqlite_lib"):
            rpaths.append(compile_cfg["sqlite_lib"])
        if compile_cfg.get("mysql_lib"):
            rpaths.append(compile_cfg["mysql_lib"])
        if compile_cfg.get("ssl_lib"):
            rpaths.append(compile_cfg["ssl_lib"])
        link_cfg["rpaths"] = rpaths

        return (1, {"detected": {
            "tree_sitter_inc": compile_cfg.get("tree_sitter_inc", ""),
            "tree_sitter_lib": compile_cfg.get("tree_sitter_lib", ""),
            "tree_sitter_python_inc": compile_cfg.get("tree_sitter_python_inc", ""),
            "tree_sitter_python_lib": compile_cfg.get("tree_sitter_python_lib", ""),
            "mysql_inc": compile_cfg.get("mysql_inc", ""),
            "mysql_lib": compile_cfg.get("mysql_lib", ""),
            "ssl_lib": compile_cfg.get("ssl_lib", ""),
            "rpaths": rpaths,
        }}, None)

    def Get(self, params):
        key = self._p(params, "key", "")
        cfg = self.state["config"]
        if not key:
            return (1, dict(cfg), None)
        keys = key.split(".")
        val = cfg
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return (0, None, ("KEY_NOT_FOUND", "Config key not found: " + str(key), 0))
        return (1, val, None)

    def Set(self, params):
        key = self._p(params, "key", "")
        value = self._p(params, "value", None)
        if not key:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        cfg = self.state["config"]
        keys = key.split(".")
        target = cfg
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.Save({})
        return (1, {key: value, "saved": True}, None)

    def Save(self, params):
        path = self._p(params, "path", self.state["config_path"])
        cfg = self.state["config"]
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        self.state["config_path"] = path
        return (1, {"saved": path, "keys": len(json.dumps(cfg))}, None)

    def Load(self, params):
        path = self._p(params, "path", self.state["config_path"])
        if not os.path.exists(path):
            self.DetectPaths({})
            self.Save({"path": path})
            return (1, {"loaded": False, "created_default": path}, None)
        with open(path) as f:
            loaded = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        for k, v in loaded.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v
        self.state["config"] = merged
        self.state["loaded"] = True
        self.DetectPaths({})
        return (1, {"loaded": True, "path": path, "backend": merged.get("backend")}, None)

    def List(self, params):
        cfg = self.state["config"]
        flat = {}
        def flatten(prefix, d):
            for k, v in d.items():
                full = prefix + "." + k if prefix else k
                if isinstance(v, dict):
                    flatten(full, v)
                else:
                    flat[full] = v
        flatten("", cfg)
        return (1, flat, None)

    def BuildDb(self, params):
        backend = self._p(params, "backend", self.state["config"].get("backend", "mysql"))
        if backend == "mysql":
            return self._BuildMysqlDb(params)
        elif backend == "sqlite":
            return self._BuildSqliteDb(params)
        return (0, None, ("UNKNOWN_BACKEND", "Unknown backend: " + str(backend), 0))

    def _BuildMysqlDb(self, params):
        cfg = self.state["config"]["mysql"]
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=cfg["host"], user=cfg["user"],
                password=cfg.get("password", ""), database=cfg["database"],
                port=cfg.get("port", 3306),
            )
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM " + cfg["table"])
            count = cur.fetchone()[0]
            conn.close()
            return (1, {"backend": "mysql", "table": cfg["table"], "rows": count}, None)
        except Exception as e:
            return (0, None, ("MYSQL_ERROR", str(e), 0))

    def _BuildSqliteDb(self, params):
        cfg = self.state["config"]["sqlite"]
        import sqlite3
        path = cfg["path"]
        if not os.path.exists(path):
            conn = sqlite3.connect(path)
            conn.execute('''CREATE TABLE IF NOT EXISTS c_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT UNIQUE NOT NULL,
                class_code TEXT NOT NULL,
                description TEXT,
                domain TEXT DEFAULT 'bcl_c_engine',
                authority TEXT DEFAULT 'unassigned',
                bcl_ghost TEXT, bcl_vbstyle TEXT, bcl_fileid TEXT,
                bcl_summary TEXT, bcl_methods TEXT, bcl_includes TEXT,
                dependencies TEXT, status TEXT DEFAULT 'active',
                version INTEGER DEFAULT 1,
                hash TEXT, build_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
            conn.close()
            return (1, {"backend": "sqlite", "path": path, "created": True}, None)
        conn = sqlite3.connect(path)
        count = conn.execute("SELECT COUNT(*) FROM " + cfg["table"]).fetchone()[0]
        conn.close()
        return (1, {"backend": "sqlite", "path": path, "rows": count}, None)

    def GetCompileCmd(self):
        """Build the compile command string from config."""
        c = self.state["config"]["compile"]
        inc_flags = " ".join(filter(None, [
            "-I" + c["tree_sitter_inc"] if c.get("tree_sitter_inc") else "",
            "-I" + c["tree_sitter_python_inc"] if c.get("tree_sitter_python_inc") else "",
            "-I" + c["tree_sitter_c_inc"] if c.get("tree_sitter_c_inc") else "",
            "-I" + c["json_c_inc"] if c.get("json_c_inc") else "",
            "-I" + c["sqlite_inc"] if c.get("sqlite_inc") else "",
            "-I" + c["mysql_inc"] if c.get("mysql_inc") else "",
        ]))
        return "{cc} {cflags} -c {{file}} -o {{obj}} -I{{incdir}} {inc}".format(
            cc=c["cc"], cflags=c["cflags"], inc=inc_flags
        )

    def GetLinkCmd(self):
        """Build the link command string from config."""
        c = self.state["config"]["compile"]
        l = self.state["config"]["link"]
        lib_flags = " ".join(filter(None, [
            "-L" + c["tree_sitter_lib"] if c.get("tree_sitter_lib") else "",
            "-ltree-sitter" if c.get("tree_sitter_lib") else "",
            "-L" + c["tree_sitter_python_lib"] if c.get("tree_sitter_python_lib") else "",
            "-ltree-sitter-python" if c.get("tree_sitter_python_lib") else "",
            "-L" + c["tree_sitter_c_lib"] if c.get("tree_sitter_c_lib") else "",
            "-ltree-sitter-c" if c.get("tree_sitter_c_lib") else "",
            "-L" + c["json_c_lib"] if c.get("json_c_lib") else "",
            "-ljson-c" if c.get("json_c_lib") else "",
            "-L" + c["sqlite_lib"] if c.get("sqlite_lib") else "",
            "-lsqlite3" if c.get("sqlite_lib") else "",
            "-L" + c["mysql_lib"] if c.get("mysql_lib") else "",
            "-lmysqlclient" if c.get("mysql_lib") else "",
            "-L" + c["ssl_lib"] if c.get("ssl_lib") else "",
            "-lssl -lcrypto" if c.get("ssl_lib") else "",
            c.get("extra_libs", ""),
        ]))
        rpath_flags = " ".join("-Wl,-rpath," + r for r in l.get("rpaths", []))
        return "{cc} {{objs}} -o {{binary}} {libs} {rpaths} {extra}".format(
            cc=c["cc"], libs=lib_flags, rpaths=rpath_flags,
            extra=l.get("extra_flags", "")
        )

    def GetDbConfig(self):
        """Return the active backend's connection config."""
        backend = self.state["config"].get("backend", "mysql")
        if backend == "mysql":
            return (1, {"backend": "mysql", **self.state["config"]["mysql"]}, None)
        elif backend == "sqlite":
            return (1, {"backend": "sqlite", **self.state["config"]["sqlite"]}, None)
        return (0, None, ("UNKNOWN_BACKEND", "Unknown backend: " + str(backend), 0))

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        params = params or {}
        for key in ["backend", "domain", "output_dir", "binary_name"]:
            if key in params:
                self.state["config"][key] = params[key]
        if "config_path" in params:
            self.state["config_path"] = params["config_path"]
        return (1, dict(self.state["config"]), None)


if __name__ == "__main__":
    import sys
    cfg = BclConfig()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    p = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            p[k] = v
    if cmd == "compile_cmd":
        print(cfg.GetCompileCmd())
    elif cmd == "link_cmd":
        print(cfg.GetLinkCmd())
    elif cmd == "db_config":
        code, data, err = cfg.GetDbConfig()
        if code:
            print(json.dumps(data, indent=2))
        else:
            print("ERROR:", err)
    else:
        code, data, err = cfg.Run(cmd, p)
        if code:
            print(json.dumps(data, indent=2, default=str))
        else:
            print("ERROR:", err)
            sys.exit(1)
