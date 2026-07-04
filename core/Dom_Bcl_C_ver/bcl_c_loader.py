#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Bcl_C_ver/bcl_c_loader.py" date="2026-06-29" author="Devin" session_id="bcl-c-central-db" context="Materializer: pulls C source from MySQL c_classes, dependency sorts, writes .c files, compiles, verifies"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="bcl_c_loader.py" domain="bcl_c_engine" authority="BclCLoader"}
#[@SUMMARY]{summary="Materializer script — MySQL c_classes is source of truth, disk is build artifact. load_all/compile_all/build_changed/sync/verify/clean/status/manifest."}
#[@CLASS]{class="BclCLoader" domain="bcl_c_engine" authority="single"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="LoadAll" type="command"}
#[@METHOD]{method="LoadOne" type="command"}
#[@METHOD]{method="CompileAll" type="command"}
#[@METHOD]{method="CompileOne" type="command"}
#[@METHOD]{method="BuildAll" type="command"}
#[@METHOD]{method="BuildChanged" type="command"}
#[@METHOD]{method="Sync" type="command"}
#[@METHOD]{method="VerifyAll" type="command"}
#[@METHOD]{method="Clean" type="command"}
#[@METHOD]{method="Status" type="command"}
#[@METHOD]{method="Manifest" type="command"}
#[@METHOD]{method="_p" type="helper"}
#[@METHOD]{method="_Connect" type="helper"}
#[@METHOD]{method="_Close" type="helper"}
#[@METHOD]{method="_TopoSort" type="helper"}
#[@METHOD]{method="_ComputeHash" type="helper"}
#[@METHOD]{method="_WriteFile" type="helper"}
#[@METHOD]{method="_CompileFile" type="helper"}
#[@METHOD]{method="_ReadManifest" type="helper"}
#[@METHOD]{method="_WriteManifest" type="helper"}
#[@METHOD]{method="read_state" type="command"}
#[@METHOD]{method="set_config" type="command"}
#[@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Materializer for C central DB. MySQL source of truth, disk is build artifact. Topological sort, incremental rebuild, hash tracking.>][@todos<none>]}
"""
BclCLoader — Materializer for C central DB architecture.

MySQL c_classes is the source of truth. Disk (.c files) are disposable
build artifacts. This script:
  1. Pulls C source from MySQL c_classes (domain='bcl_c_engine')
  2. Resolves dependencies via topological sort (Kahn's algorithm)
  3. Writes .c files to disk in dependency order
  4. Compiles .c files to .o then links to binary
  5. Emits build_manifest.json
  6. Supports incremental rebuild (hash comparison)

Run() dispatch: load_all | load_one | compile_all | compile_one |
  build_all | build_one | build_changed | sync | verify_all |
  clean | status | manifest | read_state | set_config
"""

import hashlib
import json
import os
import subprocess
import sys
from collections import deque
from datetime import datetime

from BclConfig import BclConfig

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "build_manifest.json")


class BclCLoader:
    """Materializer: DB -> disk -> compile -> verify. Backend selectable via BclConfig."""

    def __init__(self, mem=None, db=None, param=None):
        self.config = BclConfig()
        self.config.Run("load")
        cfg = self.config.state["config"]
        db_cfg = cfg.get(cfg.get("backend", "mysql"), {})
        self.state = {
            "backend": cfg.get("backend", "mysql"),
            "db_host": db_cfg.get("host", "localhost") if cfg.get("backend") == "mysql" else "",
            "db_user": db_cfg.get("user", "root") if cfg.get("backend") == "mysql" else "",
            "db_name": db_cfg.get("database", "vb_shared") if cfg.get("backend") == "mysql" else db_cfg.get("path", ""),
            "db_table": db_cfg.get("table", "c_classes"),
            "domain": cfg.get("domain", "bcl_c_engine"),
            "output_dir": cfg.get("output_dir", OUTPUT_DIR),
            "manifest_path": MANIFEST_PATH,
            "compile_cmd": self.config.GetCompileCmd(),
            "link_cmd": self.config.GetLinkCmd(),
            "binary_name": cfg.get("binary_name", "dom_graph_engine"),
            "units": [],
            "errors": [],
            "compiled": 0,
            "failed": 0,
        }
        if param:
            for key, value in param.items():
                if key in self.state:
                    self.state[key] = value
        self.conn = None
        self.cur = None

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "load_all": self.LoadAll,
            "load_one": self.LoadOne,
            "compile_all": self.CompileAll,
            "compile_one": self.CompileOne,
            "build_all": self.BuildAll,
            "build_one": lambda p: self.BuildAll(p),
            "build_changed": self.BuildChanged,
            "sync": self.Sync,
            "verify_all": self.VerifyAll,
            "clean": self.Clean,
            "status": self.Status,
            "manifest": self.Manifest,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        return params.get(key, default) if params else default

    def _Connect(self):
        if self.conn is None:
            if self.state.get("backend", "mysql") == "sqlite":
                import sqlite3
                db_path = self.state["db_name"]
                self.conn = sqlite3.connect(db_path)
                self.conn.row_factory = sqlite3.Row
                self.cur = self.conn.cursor()
            else:
                import mysql.connector
                self.conn = mysql.connector.connect(
                    host=self.state["db_host"],
                    user=self.state["db_user"],
                    database=self.state["db_name"],
                )
                self.cur = self.conn.cursor(dictionary=True)
        return self.cur

    def _Close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            self.cur = None

    def _ComputeHash(self, code):
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _TopoSort(self, units):
        """Topological sort using Kahn's algorithm. units = list of dicts/Rows with class_name + dependencies."""
        normalized = [dict(u) if not isinstance(u, dict) else u for u in units]
        name_to_unit = {u["class_name"]: u for u in normalized}
        graph = {}
        in_degree = {}
        for u in normalized:
            name = u["class_name"]
            deps = []
            raw_deps = u.get("dependencies", "[]")
            if raw_deps:
                try:
                    dep_list = json.loads(raw_deps) if isinstance(raw_deps, str) else raw_deps
                    for d in dep_list:
                        dep_type = d.get("type", "call")
                        target = d.get("target", d.get("call", d.get("include", d.get("link", ""))))
                        if dep_type in ("call", "include") and target and target != "all":
                            deps.append(target)
                except (json.JSONDecodeError, TypeError):
                    pass
            graph[name] = deps
            in_degree[name] = len(deps)

        queue = deque([n for n in name_to_unit if in_degree[n] == 0])
        result = []
        while queue:
            node = queue.popleft()
            result.append(name_to_unit[node])
            for dependent in graph:
                if node in graph[dependent]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(units):
            remaining = [n for n in name_to_unit if n not in [r["class_name"] for r in result]]
            return None, remaining
        return result, None

    def _WriteFile(self, filename, content):
        fpath = os.path.join(self.state["output_dir"], filename)
        with open(fpath, "w") as f:
            f.write(content)
        return fpath

    def _CompileFile(self, c_file):
        if c_file.endswith(".h"):
            return (1, {"obj": None, "cmd": "skip (header)"}, None)
        obj_file = c_file.replace(".c", ".o")
        incdir = self.state["output_dir"]
        cmd = self.state["compile_cmd"].format(
            file=os.path.join(self.state["output_dir"], c_file),
            obj=os.path.join(self.state["output_dir"], obj_file),
            incdir=incdir,
        )
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return (0, None, ("COMPILE_ERROR", result.stderr.strip()[:500], 0))
            return (1, {"obj": obj_file, "cmd": cmd}, None)
        except subprocess.TimeoutExpired:
            return (0, None, ("COMPILE_TIMEOUT", "Compilation timed out", 0))

    def _ReadManifest(self):
        path = self.state["manifest_path"]
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def _WriteManifest(self, units_data):
        manifest = {
            "built_at": datetime.utcnow().isoformat() + "Z",
            "domain": self.state["domain"],
            "units": units_data,
            "total": len(units_data),
            "compiled": sum(1 for u in units_data if u.get("compiled")),
            "failed": sum(1 for u in units_data if not u.get("compiled")),
        }
        with open(self.state["manifest_path"], "w") as f:
            json.dump(manifest, f, indent=2)
        return manifest

    def _FetchUnits(self, class_name=None):
        cur = self._Connect()
        ph = "?" if self.state.get("backend", "mysql") == "sqlite" else "%s"
        if class_name:
            cur.execute(
                "SELECT * FROM {table} WHERE domain={ph} AND status='active' AND class_name={ph}".format(
                    table=self.state["db_table"], ph=ph
                ),
                (self.state["domain"], class_name),
            )
            rows = cur.fetchall()
            dep_names = []
            for r in rows:
                r_dict = dict(r) if not isinstance(r, dict) else r
                try:
                    deps = json.loads(r_dict.get("dependencies", "[]")) if r_dict.get("dependencies") else []
                    dep_names = [d.get("target", "") for d in deps if d.get("type") in ("call", "include")]
                except (json.JSONDecodeError, TypeError):
                    pass
            if dep_names:
                placeholders = ",".join([ph] * len(dep_names))
                cur.execute(
                    "SELECT * FROM {table} WHERE domain={ph} AND status='active' AND class_name IN ({pl})".format(
                        table=self.state["db_table"], ph=ph, pl=placeholders
                    ),
                    [self.state["domain"]] + dep_names,
                )
                extra = cur.fetchall()
                existing = {(dict(r) if not isinstance(r, dict) else r)["class_name"] for r in rows}
                for r in extra:
                    r_dict = dict(r) if not isinstance(r, dict) else r
                    if r_dict["class_name"] not in existing:
                        rows.append(r)
        else:
            cur.execute(
                "SELECT * FROM {table} WHERE domain={ph} AND status='active' ORDER BY class_name".format(
                    table=self.state["db_table"], ph=ph
                ),
                (self.state["domain"],),
            )
            rows = cur.fetchall()
        return rows

    def LoadAll(self, params):
        class_name = self._p(params, "class_name")
        rows = self._FetchUnits(class_name)
        if not rows:
            return (0, None, ("NO_UNITS", "No units found in DB for domain: " + self.state["domain"], 0))

        sorted_units, cycle = self._TopoSort(rows)
        if cycle:
            return (0, None, ("CIRCULAR_DEP", "Circular dependency among: " + ", ".join(cycle), 0))

        written = []
        for u in sorted_units:
            u = dict(u) if not isinstance(u, dict) else u
            code = u["class_code"]
            if isinstance(code, bytes):
                code = code.decode("utf-8", errors="replace")
            fname = u.get("bcl_fileid") or (u["class_name"] + ".c")
            self._WriteFile(fname, code)
            file_hash = self._ComputeHash(code)
            cur = self._Connect()
            ph = "?" if self.state.get("backend", "mysql") == "sqlite" else "%s"
            cur.execute(
                "UPDATE {table} SET hash={ph} WHERE class_name={ph}".format(table=self.state["db_table"], ph=ph),
                (file_hash, u["class_name"]),
            )
            written.append({
                "class_name": u["class_name"],
                "file": fname,
                "hash": file_hash,
                "order": len(written) + 1,
            })
        self._Close()
        return (1, {"loaded": len(written), "units": written}, None)

    def LoadOne(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        return self.LoadAll({"class_name": class_name})

    def CompileAll(self, params):
        manifest = self._ReadManifest()
        if not manifest:
            r = self.LoadAll({})
            if r[0] == 0:
                return r
            manifest_units = r[1]["units"]
        else:
            manifest_units = manifest.get("units", [])

        results = []
        compiled = 0
        failed = 0
        for u in manifest_units:
            c_file = u["file"]
            r = self._CompileFile(c_file)
            if r[0] == 1:
                compiled += 1
                results.append({**u, "compiled": True, "obj": r[1]["obj"]})
            else:
                failed += 1
                results.append({**u, "compiled": False, "error": r[2][1]})

        if compiled > 0 and failed == 0:
            obj_files = [r["obj"] for r in results if r.get("compiled") and r.get("obj")]
            if not obj_files:
                self._WriteManifest(results)
                self.state["compiled"] = compiled
                self.state["failed"] = failed
                return (1, {"compiled": compiled, "failed": failed, "results": results, "linked": False}, None)
            binary_path = os.path.join(self.state["output_dir"], "bin", self.state["binary_name"])
            os.makedirs(os.path.dirname(binary_path), exist_ok=True)
            link_cmd = self.state["link_cmd"].format(
                objs=" ".join(obj_files),
                binary=binary_path,
            )
            try:
                link_result = subprocess.run(link_cmd, shell=True, capture_output=True, text=True, timeout=30)
                if link_result.returncode != 0:
                    failed += 1
                    return (0, None, ("LINK_ERROR", link_result.stderr.strip()[:500], 0))
            except subprocess.TimeoutExpired:
                return (0, None, ("LINK_TIMEOUT", "Link timed out", 0))

        self._WriteManifest(results)
        self.state["compiled"] = compiled
        self.state["failed"] = failed
        return (1, {"compiled": compiled, "failed": failed, "results": results}, None)

    def CompileOne(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        c_file = class_name + ".c"
        return self._CompileFile(c_file)

    def BuildAll(self, params):
        r1 = self.LoadAll(params)
        if r1[0] == 0:
            return r1
        r2 = self.CompileAll(params)
        return r2

    def BuildChanged(self, params):
        rows = self._FetchUnits()
        if not rows:
            return (0, None, ("NO_UNITS", "No units found", 0))

        old_manifest = self._ReadManifest()
        old_hashes = {}
        if old_manifest:
            for u in old_manifest.get("units", []):
                old_hashes[u["class_name"]] = u.get("hash", "")

        changed = []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            code = r["class_code"]
            if isinstance(code, bytes):
                code = code.decode("utf-8", errors="replace")
            new_hash = self._ComputeHash(code)
            if new_hash != old_hashes.get(r["class_name"], ""):
                changed.append(r["class_name"])

        if not changed:
            return (1, {"changed": 0, "message": "No changes detected"}, None)

        return self.BuildAll(params)

    def Sync(self, params):
        rows = self._FetchUnits()
        if not rows:
            return (0, None, ("NO_UNITS", "No units found", 0))

        differences = []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            code = r["class_code"]
            if isinstance(code, bytes):
                code = code.decode("utf-8", errors="replace")
            db_hash = self._ComputeHash(code)
            fname = r.get("bcl_fileid") or (r["class_name"] + ".c")
            fpath = os.path.join(self.state["output_dir"], fname)
            if not os.path.exists(fpath):
                differences.append({"class_name": r["class_name"], "status": "missing_on_disk", "db_hash": db_hash})
            else:
                with open(fpath) as f:
                    disk_hash = self._ComputeHash(f.read())
                if disk_hash != db_hash:
                    differences.append({"class_name": r["class_name"], "status": "hash_mismatch", "db_hash": db_hash, "disk_hash": disk_hash})

        orphans = []
        c_files = [f for f in os.listdir(self.state["output_dir"]) if f.endswith(".c") or f.endswith(".h")]
        db_names = {(dict(r) if not isinstance(r, dict) else r).get("bcl_fileid") or (dict(r) if not isinstance(r, dict) else r)["class_name"] + ".c" for r in rows}
        for f in c_files:
            if f not in db_names:
                orphans.append(f)

        return (1, {"differences": differences, "orphans": orphans, "synced": len(rows) - len(differences)}, None)

    def VerifyAll(self, params):
        r = self.BuildAll(params)
        if r[0] == 0:
            return r
        results = r[1]
        return (1, {"verified": results.get("compiled", 0), "failed": results.get("failed", 0)}, None)

    def Clean(self, params):
        confirm = self._p(params, "confirm", False)
        if not confirm:
            return (0, None, ("NEED_CONFIRM", "Pass confirm=True to clean", 0))

        deleted = []
        for f in os.listdir(self.state["output_dir"]):
            if f.endswith(".c") or f.endswith(".o") or f.endswith(".h"):
                os.remove(os.path.join(self.state["output_dir"], f))
                deleted.append(f)
        bin_dir = os.path.join(self.state["output_dir"], "bin")
        if os.path.exists(bin_dir):
            for f in os.listdir(bin_dir):
                os.remove(os.path.join(bin_dir, f))
                deleted.append("bin/" + f)
        if os.path.exists(self.state["manifest_path"]):
            os.remove(self.state["manifest_path"])
            deleted.append("build_manifest.json")
        return (1, {"deleted": deleted, "count": len(deleted)}, None)

    def Status(self, params):
        rows = self._FetchUnits()
        if not rows:
            return (1, {"units": [], "total": 0}, None)

        status_list = []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            fname = r.get("bcl_fileid") or (r["class_name"] + ".c")
            fpath = os.path.join(self.state["output_dir"], fname)
            on_disk = os.path.exists(fpath)
            obj_path = fpath.replace(".c", ".o")
            compiled = os.path.exists(obj_path) if fname.endswith(".c") else True
            status_list.append({
                "class_name": r["class_name"],
                "status": r.get("status", "unknown"),
                "on_disk": on_disk,
                "compiled": compiled,
                "hash": r.get("hash", ""),
            })
        return (1, {"units": status_list, "total": len(status_list)}, None)

    def Manifest(self, params):
        manifest = self._ReadManifest()
        if not manifest:
            return (0, None, ("NO_MANIFEST", "No manifest found. Run build_all first.", 0))
        return (1, manifest, None)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        params = params or {}
        for key in ["db_host", "db_user", "db_name", "db_table", "domain",
                     "output_dir", "compile_cmd", "link_cmd", "binary_name"]:
            if key in params:
                self.state[key] = params[key]
        return (1, dict(self.state), None)


if __name__ == "__main__":
    import json as json_mod
    engine = BclCLoader()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    p = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            p[k] = v
    if "--confirm" in sys.argv:
        p["confirm"] = True
    code, data, err = engine.Run(cmd, p)
    if code == 1:
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        print("ERROR:", err)
        sys.exit(1)
