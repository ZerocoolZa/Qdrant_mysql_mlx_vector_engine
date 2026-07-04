#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_main.py>][@domain<Vbs_Code_Verifiation>][@role<orchestration>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<orchestration>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
VbsMain: Entry point for the VBStyle Domain Scanner.
Wires all scanner components together and dispatches scan commands.
Replaces the old procedural vbstyle_dom_scanner.py main block.

Usage:
    python3 vbs_main.py [domains_dir] [output_file] [--no-mysql]
"""

import os
import sys

from . import Config_Vbs_Code_Verifiation as Config
from .vbs_parser import Parser
from .vbs_compliance import Compliance
from .vbs_code_index import CodeIndex
from .vbs_registry import Registry


class VbsMain:
    """VBStyle Domain Scanner entry point and orchestrator."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
        }
        self.parser = Parser(mem=mem, db=db, param=param)
        self.compliance = Compliance(mem=mem, db=db, param=param)
        self.code_index = CodeIndex(mem=mem, db=db, param=param)
        self.registry = Registry(mem=mem, db=db, param=param)

    #[@scan]{[@params<<params>][@return<Tuple3>][@purpose<scan all dom_*.py files and generate registry>]}
    def scan(self, params):
        try:
            domains_dir = params.get("domains_dir", Config.DEFAULT_DOMAINS_DIR)
            output_path = params.get("output_path", Config.DEFAULT_OUTPUT)
            use_mysql = params.get("use_mysql", True)

            if not os.path.exists(domains_dir):
                return (0, None, ("DIR_NOT_FOUND", domains_dir, 0))

            files = sorted([
                f for f in os.listdir(domains_dir)
                if f.endswith(".py") and (f.startswith("dom_") or f.startswith("impl_"))
            ])

            if not files:
                return (0, None, ("NO_FILES", "No dom_*.py or impl_*.py files found", 0))

            index = None
            if use_mysql:
                r = self.code_index.open({})
                if r[0]:
                    index = self.code_index

            domains = []
            for fname in files:
                fpath = os.path.join(domains_dir, fname)
                r = self.parser.parse_file({"filepath": fpath})
                if r[0] and r[1]:
                    domain = r[1]

                    comp_r = self.compliance.check({
                        "lines_list": open(fpath, "r", encoding="utf-8", errors="replace").readlines(),
                        "class_ranges": domain.get("class_ranges"),
                        "filepath": fpath,
                    })
                    if comp_r[0]:
                        domain["file_compliance"] = comp_r[1]["file"]
                        domain["class_compliance"] = comp_r[1]["classes"]

                    domains.append(domain)

            gen_r = self.registry.write({
                "domains": domains,
                "output_path": output_path,
                "index": index,
            })

            if index:
                self.code_index.close({})

            if gen_r[0]:
                return (1, gen_r[1], None)
            else:
                return gen_r
        except Exception as e:
            return (0, None, ("SCAN_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read VbsMain state>]}
    def read_state(self, params=None):
        return (1, self.state, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set VbsMain config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch VbsMain commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "scan": self.scan,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


if __name__ == "__main__":
    use_mysql = "--no-mysql" not in sys.argv
    args = [a for a in sys.argv[1:] if a != "--no-mysql"]

    domains_dir = args[0] if len(args) > 0 else Config.DEFAULT_DOMAINS_DIR
    output_path = args[1] if len(args) > 1 else Config.DEFAULT_OUTPUT

    scanner = VbsMain()
    result = scanner.Run("scan", {
        "domains_dir": domains_dir,
        "output_path": output_path,
        "use_mysql": use_mysql,
    })

    if result[0]:
        data = result[1]
        sys.stderr.write("Done: {} files, {} classes, {} methods, {} lines\n".format(
            data["domains"], data["classes"], data["methods"], data["lines"]))
        sys.stderr.write("Written to: {}\n".format(data["output_path"]))
    else:
        err = result[2]
        sys.stderr.write("Error: {} - {}\n".format(err[0], err[1]))
        sys.exit(1)
