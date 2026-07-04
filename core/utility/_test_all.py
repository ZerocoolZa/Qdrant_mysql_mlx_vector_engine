#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/_test_all.py"
# date="2026-06-27" author="Cascade" session_id="utility-test"
# context="Generic test runner. Tests utilities + any registered target's domain classes."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="_test_all.py" domain="utility" authority="test"}
# [@SUMMARY]{summary="Tests all utilities and any target domain classes. Accepts target name via params."}
# [@CLASS]{class="TestAll" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Execute" type="command"}
# [@METHOD]{method="TestUtilities" type="helper"}
# [@METHOD]{method="TestTarget" type="helper"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config import ConfigReport, TARGETS


class TestAll:
    """Test all utilities and any target's domain classes. Globally reusable."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "report": None,
            "target": None,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "execute":
            return self.Execute(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state[key] = value
        return (1, dict(self.state), None)

    def Execute(self, params):
        report = ConfigReport()
        self.state["report"] = report

        def check(name, ok, detail=""):
            report.Run("add", {"name": name, "ok": ok, "detail": detail})

        # ── PART 1: Test utilities ─────────────────────────────────────────
        self.TestUtilities(check)

        # ── PART 2: Test target domain classes ─────────────────────────────
        target = self._p(params, "target", self.state.get("target"))
        if target and target in TARGETS:
            self.TestTarget(check, target)
        else:
            for tname in TARGETS:
                self.TestTarget(check, tname)

        summary_result = report.Run("summary", {})
        summary_text = summary_result[1] if summary_result[0] == 1 else ""
        return (1, {"passed": report.state["passed"], "failed": report.state["failed"], "summary": summary_text}, None)

    def TestUtilities(self, check):
        from _combine import CombineUtil
        from _fix_indent import FixIndent
        from _debug_strip import DebugStrip

        # ConfigReport
        cr = ConfigReport()
        cr.Run("add", {"name": "selftest", "ok": True})
        check("ConfigReport.add", cr.state["passed"] == 1)
        sr = cr.Run("summary", {})
        check("ConfigReport.summary", sr[0] == 1 and "selftest" in sr[1])

        # CombineUtil — generic, no target
        cu = CombineUtil()
        check("CombineUtil.construct", cu is not None)
        strip_result = cu.Run("strip_file", {"content": "# header\nimport os\n\nclass Test:\n    pass"})
        check("CombineUtil.strip_file", strip_result[0] == 1 and "class Test" in strip_result[1])
        rename_result = cu.Run("apply_renames", {"text": "class Foo: pass", "renames": {"Foo": "BarFoo"}})
        check("CombineUtil.apply_renames", rename_result[0] == 1 and "BarFoo" in rename_result[1])

        # FixIndent
        fi = FixIndent()
        check("FixIndent.construct", fi is not None)

        # DebugStrip
        ds = DebugStrip()
        check("DebugStrip.construct", ds is not None)
        verify_result = ds.Run("verify", {})
        check("DebugStrip.verify", verify_result[0] == 1)

    def TestTarget(self, check, target_name):
        t = TARGETS[target_name]
        source_dir = t["source_dir"]
        sys.path.insert(0, source_dir)

        module_name = os.path.basename(t["output_path"]).replace(".py", "")
        try:
            mod = __import__(module_name)
        except Exception as exc:
            check("%s.import" % target_name, False, str(exc))
            return

        classes = [getattr(mod, name) for name in dir(mod) if name[0].isupper() and isinstance(getattr(mod, name), type)]
        check("%s.import" % target_name, len(classes) > 0, "no classes found")

        for cls in classes:
            try:
                instance = cls()
                check("%s.%s.construct" % (target_name, cls.__name__), instance is not None)
                if hasattr(instance, "Run"):
                    check("%s.%s.run_exists" % (target_name, cls.__name__), True)
                if hasattr(instance, "state"):
                    check("%s.%s.state_dict" % (target_name, cls.__name__), isinstance(instance.state, dict))
            except Exception as exc:
                check("%s.%s.construct" % (target_name, cls.__name__), False, str(exc))


if __name__ == "__main__":
    test = TestAll()
    result = test.Run("execute", {})
    if result[0] == 1:
        info = result[1]
        sys.stdout.write(info["summary"] + "\n")
        if info["failed"] > 0:
            sys.exit(1)
    else:
        sys.stdout.write("ERROR: " + str(result[2]) + "\n")
        sys.exit(1)
