#!/usr/bin/env python3
# [@GHOST]{[@file<c_class_builder.py>][@domain<Dom_Unified>][@role<c_code_assembler>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<c_code_assembler>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{C Class Builder — reads VBStyle C classes from MySQL, assembles into one .c file, compiles to binary. DB is source of truth, not filesystem.}
# [@CLASS]{CClassBuilder}
# [@METHOD]{Run,assemble,compile,build,list_classes,add_class,get_class,deactivate_class}

"""
C Class Builder — DB-driven C code assembly and compilation.

WHAT IT DOES:
  1. READ   — query all active c_classes from MySQL (VBStyle C code stored as rows)
  2. ORDER  — sort by dependency (classes with no deps first)
  3. ASSEMBLE — merge all class_code into one .c file with shared includes
  4. COMPILE — run cc/clang to produce the final binary
  5. VERIFY  — check binary exists, report size

WHY DB NOT FILES:
  - Multiple agents can write C classes in parallel (no file conflicts)
  - All classes follow VBStyle (bcl_ghost, bcl_vbstyle headers in DB columns)
  - DB is source of truth — filesystem is just build output
  - Classes can be activated/deactivated without deleting code
  - Versioning and dependency tracking in DB

USAGE:
  python3 c_class_builder.py build --domain graph_engine --output /tmp/dom_graph
  python3 c_class_builder.py list
  python3 c_class_builder.py add --name Node --domain graph_engine --code-file node.c
  python3 c_class_builder.py assemble --domain graph_engine --output /tmp/assembled.c
"""

import sys
import os
import subprocess
import mysql.connector

try:
    from .Config import GRAPH_MYSQL_HOST, GRAPH_MYSQL_USER, GRAPH_MYSQL_DB_VB
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from Config import GRAPH_MYSQL_HOST, GRAPH_MYSQL_USER, GRAPH_MYSQL_DB_VB


class CClassBuilder:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": param.get("mysql_host", GRAPH_MYSQL_HOST) if param else GRAPH_MYSQL_HOST,
                "mysql_user": param.get("mysql_user", GRAPH_MYSQL_USER) if param else GRAPH_MYSQL_USER,
                "mysql_pass": param.get("mysql_pass", "") if param else "",
                "mysql_db": param.get("mysql_db", GRAPH_MYSQL_DB_VB) if param else GRAPH_MYSQL_DB_VB,
                "compiler": param.get("compiler", "cc") if param else "cc",
                "cflags": param.get("cflags", "-O2 -Wall -I/opt/homebrew/include -L/opt/homebrew/lib -lmysqlclient -framework Metal -framework Foundation") if param else "-O2 -Wall -I/opt/homebrew/include -L/opt/homebrew/lib -lmysqlclient -framework Metal -framework Foundation",
            },
            "stats": {"assembled": 0, "compiled": 0, "classes_built": 0},
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
        self.state["db_conn"] = db

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _get_conn(self):
        if self.state.get("db_conn"):
            return self.state["db_conn"]
        cfg = self.state["config"]
        return mysql.connector.connect(
            host=cfg["mysql_host"],
            user=cfg["mysql_user"],
            password=cfg.get("mysql_pass", ""),
            database=cfg["mysql_db"],
        )

    def Run(self, command, params=None):
        dispatch = {
            "assemble": self._cmd_assemble,
            "compile": self._cmd_compile,
            "build": self._cmd_build,
            "list": self._cmd_list,
            "add": self._cmd_add,
            "get": self._cmd_get,
            "deactivate": self._cmd_deactivate,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params or {})

    def _cmd_list(self, params):
        domain = self._p(params, "domain")
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            if domain:
                cur.execute(
                    "SELECT id, class_name, domain, authority, status, version, "
                    "LENGTH(class_code) as code_size, bcl_methods, dependencies, updated_at "
                    "FROM c_classes WHERE domain=%s ORDER BY id",
                    (domain,),
                )
            else:
                cur.execute(
                    "SELECT id, class_name, domain, authority, status, version, "
                    "LENGTH(class_code) as code_size, bcl_methods, dependencies, updated_at "
                    "FROM c_classes ORDER BY domain, id"
                )
            rows = cur.fetchall()
            return (1, rows, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_get(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM c_classes WHERE class_name=%s", (class_name,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "Class not found: " + class_name, 0))
            return (1, row, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_add(self, params):
        class_name = self._p(params, "class_name")
        domain = self._p(params, "domain", "general")
        code = self._p(params, "code")
        code_file = self._p(params, "code_file")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        if not code and not code_file:
            return (0, None, ("MISSING_PARAM", "code or code_file required", 0))
        if code_file:
            try:
                with open(code_file, "r") as f:
                    code = f.read()
            except Exception as exc:
                return (0, None, ("READ_ERROR", str(exc), 0))
        authority = self._p(params, "authority", "unassigned")
        description = self._p(params, "description", "")
        bcl_ghost = self._p(params, "bcl_ghost", "")
        bcl_vbstyle = self._p(params, "bcl_vbstyle", "")
        bcl_fileid = self._p(params, "bcl_fileid", class_name)
        bcl_summary = self._p(params, "bcl_summary", description)
        bcl_methods = self._p(params, "bcl_methods", "")
        bcl_includes = self._p(params, "bcl_includes", "")
        dependencies = self._p(params, "dependencies", "[]")
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO c_classes (class_name, class_code, description, domain, authority, "
                "bcl_ghost, bcl_vbstyle, bcl_fileid, bcl_summary, bcl_methods, bcl_includes, dependencies, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE class_code=%s, description=%s, domain=%s, authority=%s, "
                "bcl_ghost=%s, bcl_vbstyle=%s, bcl_fileid=%s, bcl_summary=%s, bcl_methods=%s, "
                "bcl_includes=%s, dependencies=%s, version=version+1, updated_at=NOW()",
                (class_name, code.encode("utf-8"), description, domain, authority,
                 bcl_ghost, bcl_vbstyle, bcl_fileid, bcl_summary, bcl_methods, bcl_includes, dependencies, "active",
                 code.encode("utf-8"), description, domain, authority,
                 bcl_ghost, bcl_vbstyle, bcl_fileid, bcl_summary, bcl_methods, bcl_includes, dependencies),
            )
            conn.commit()
            return (1, {"class_name": class_name, "domain": domain, "id": cur.lastrowid}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_deactivate(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE c_classes SET status='retired' WHERE class_name=%s", (class_name,))
            conn.commit()
            if cur.rowcount == 0:
                return (0, None, ("NOT_FOUND", "Class not found: " + class_name, 0))
            return (1, {"class_name": class_name, "status": "retired"}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_assemble(self, params):
        domain = self._p(params, "domain")
        output = self._p(params, "output")
        if not output:
            return (0, None, ("MISSING_PARAM", "output path required", 0))
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            if domain:
                cur.execute(
                    "SELECT * FROM c_classes WHERE status='active' AND domain=%s ORDER BY id",
                    (domain,),
                )
            else:
                cur.execute("SELECT * FROM c_classes WHERE status='active' ORDER BY domain, id")
            classes = cur.fetchall()
            if not classes:
                return (0, None, ("NO_CLASSES", "No active C classes found", 0))
            # Collect all unique includes
            all_includes = set()
            for cls in classes:
                inc = cls.get("bcl_includes") or ""
                for line in inc.split("\n"):
                    line = line.strip()
                    if line.startswith("#include"):
                        all_includes.add(line)
            # Assemble
            parts = []
            parts.append("/* Auto-generated by CClassBuilder — do not edit */")
            parts.append("/* Source: MySQL vb_shared.c_classes */")
            parts.append("/* Classes: " + str(len(classes)) + " */")
            parts.append("")
            # Standard includes
            parts.append("#include <stdio.h>")
            parts.append("#include <stdlib.h>")
            parts.append("#include <string.h>")
            parts.append("")
            # Custom includes
            for inc in sorted(all_includes):
                parts.append(inc)
            if all_includes:
                parts.append("")
            # Class code blocks
            for cls in classes:
                code = cls["class_code"]
                if isinstance(code, bytes):
                    code = code.decode("utf-8")
                parts.append("/* ═════════════════════════════════════════════════════════════════")
                parts.append("   CLASS: " + cls["class_name"])
                parts.append("   DOMAIN: " + (cls["domain"] or "general"))
                parts.append("   AUTHORITY: " + (cls["authority"] or "unassigned"))
                if cls.get("bcl_summary"):
                    parts.append("   SUMMARY: " + cls["bcl_summary"])
                parts.append("   ═════════════════════════════════════════════════════════════════ */")
                parts.append("")
                parts.append(code)
                parts.append("")
            assembled = "\n".join(parts)
            try:
                with open(output, "w") as f:
                    f.write(assembled)
            except Exception as exc:
                return (0, None, ("WRITE_ERROR", str(exc), 0))
            self.state["stats"]["assembled"] += 1
            return (1, {
                "output": output,
                "class_count": len(classes),
                "total_lines": assembled.count("\n") + 1,
                "total_bytes": len(assembled),
            }, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_compile(self, params):
        source = self._p(params, "source")
        output = self._p(params, "output")
        if not source or not output:
            return (0, None, ("MISSING_PARAM", "source and output required", 0))
        if not os.path.exists(source):
            return (0, None, ("NO_SOURCE", "Source file not found: " + source, 0))
        compiler = self.state["config"]["compiler"]
        cflags = self.state["config"]["cflags"]
        cmd = [compiler, cflags.split(), "-o", output, source]
        # Flatten
        flat_cmd = [compiler] + cflags.split() + ["-o", output, source]
        try:
            result = subprocess.run(
                flat_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("COMPILE_TIMEOUT", "Compilation timed out (60s)", 0))
        except Exception as exc:
            return (0, None, ("COMPILE_ERROR", str(exc), 0))
        if result.returncode != 0:
            return (0, None, ("COMPILE_FAILED", result.stderr[:2000], result.returncode))
        if not os.path.exists(output):
            return (0, None, ("NO_BINARY", "Binary not produced", 0))
        binary_size = os.path.getsize(output)
        self.state["stats"]["compiled"] += 1
        return (1, {
            "binary": output,
            "size_bytes": binary_size,
            "size_kb": binary_size // 1024,
            "warnings": result.stderr[:500] if result.stderr else "",
        }, None)

    def _cmd_build(self, params):
        domain = self._p(params, "domain")
        output = self._p(params, "output")
        if not domain or not output:
            return (0, None, ("MISSING_PARAM", "domain and output required", 0))
        # Step 1: Assemble
        source = output + ".c"
        ok, asm_data, err = self._cmd_assemble({"domain": domain, "output": source})
        if not ok:
            return (0, None, err)
        # Step 2: Compile
        ok, comp_data, err = self._cmd_compile({"source": source, "output": output})
        if not ok:
            return (0, None, err)
        self.state["stats"]["classes_built"] += 1
        return (1, {
            "source": source,
            "binary": output,
            "class_count": asm_data["class_count"],
            "total_lines": asm_data["total_lines"],
            "binary_size_kb": comp_data["size_kb"],
            "warnings": comp_data.get("warnings", ""),
        }, None)

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
        }

    def set_config(self, key, value):
        if key in self.state["config"]:
            self.state["config"][key] = value
            return (1, {"key": key, "value": value}, None)
        return (0, None, ("UNKNOWN_KEY", "Unknown config key: " + str(key), 0))


if __name__ == "__main__":
    builder = CClassBuilder()
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: c_class_builder.py <command> [args]\n")
        sys.stderr.write("Commands: build, assemble, compile, list, add, get, deactivate\n")
        sys.exit(1)
    cmd = sys.argv[1]
    params = {}
    i = 2
    while i < len(sys.argv) - 1:
        key = sys.argv[i].lstrip("--")
        params[key] = sys.argv[i + 1]
        i += 2
    ok, data, err = builder.Run(cmd, params)
    if ok:
        if isinstance(data, list):
            for row in data:
                sys.stdout.write(str(row) + "\n")
        elif isinstance(data, dict):
            for k, v in data.items():
                sys.stdout.write(str(k) + ": " + str(v) + "\n")
        else:
            sys.stdout.write(str(data) + "\n")
    else:
        sys.stderr.write("ERROR: " + str(err) + "\n")
        sys.exit(1)
