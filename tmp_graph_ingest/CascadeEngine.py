# [@GHOST]
# Ghost header — CascadeEngine
# Purpose: Pre-code validation compiler. 8-graph gating function.
# Layer: Sits ABOVE GraphEngine. Controls GraphEngine.
# Triangle: Cascade validates -> GraphEngine executes -> DEGS evolves
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import json
import time
import uuid
import sqlite3
from Config_graph_engine import cfg


class CascadeEngine:
    """Pre-code validation compiler. Validates structure before code exists."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "run_id": None,
            "current_stage": None,
            "stages": cfg.STAGES,
            "loop_count": 0,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        dispatch = {
            "start": self.Start,
            "stage": self.Stage,
            "validate": self.Validate,
            "status": self.Status,
            "rewrite": self.Rewrite,
            "commit": self.Commit,
            "rules": self.Rules,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Start(self, params):
        """Create cascade_run, write initial SPEC.md, return run_id."""
        idea = params.get("idea", "")
        if not idea:
            return (0, None, "missing_param: idea")
        run_id = "cascade_" + uuid.uuid4().hex[:12]
        spec_path = params.get("spec_path", cfg.SPEC_PATH)
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        cur.execute(
            "INSERT INTO cascade_runs (run_id, idea, spec_path, current_stage, status, loop_count) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, idea, spec_path, "plan", "running", 0),
        )
        db.commit()
        db.close()
        self.state["run_id"] = run_id
        self.state["current_stage"] = "plan"
        return (1, {"run_id": run_id, "spec_path": spec_path, "stage": "plan"}, None)

    def Stage(self, params):
        """Execute one graph projection. Returns verdict."""
        run_id = params.get("run_id")
        stage_name = params.get("stage")
        if not run_id or not stage_name:
            return (0, None, "missing_param: run_id and stage required")
        if stage_name not in cfg.STAGES:
            return (0, None, "invalid_stage: {name}".format(name=stage_name))
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT status, loop_count FROM cascade_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        run_status, loop_count = row
        if run_status == "blocked":
            db.close()
            return (0, None, cfg.GetError("cascade_blocked", stage=stage_name))
        rules = cur.execute(
            "SELECT rule_id, rule_text, violation_action, severity, query_template FROM cascade_rules WHERE stage=?",
            (stage_name,),
        ).fetchall()
        issues = []
        verdict = "pass"
        for rule_id, rule_text, action, severity, query_tmpl in rules:
            violated = False
            if query_tmpl:
                try:
                    result = cur.execute(query_tmpl).fetchall()
                    violated = len(result) > 0
                except Exception:
                    violated = False
            if violated:
                issue = {
                    "rule_id": rule_id,
                    "rule": rule_text,
                    "action": action,
                    "severity": severity,
                }
                issues.append(issue)
                if action == "block":
                    verdict = "fail"
                elif action == "rewrite" and verdict != "fail":
                    verdict = "rewrite"
        snapshot = json.dumps({"stage": stage_name, "issue_count": len(issues)})
        cur.execute(
            "INSERT INTO cascade_stage_results (run_id, stage, graph_snapshot, verdict, issues, issue_count) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, stage_name, snapshot, verdict, json.dumps(issues), len(issues)),
        )
        next_stage = self.NextStage(stage_name)
        cur.execute(
            "UPDATE cascade_runs SET current_stage=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (next_stage or stage_name, run_id),
        )
        if verdict == "fail":
            cur.execute(
                "UPDATE cascade_runs SET status='blocked', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                (run_id,),
            )
        db.commit()
        db.close()
        self.state["current_stage"] = next_stage
        return (1, {"stage": stage_name, "verdict": verdict, "issues": issues, "issue_count": len(issues)}, None)

    def Validate(self, params):
        """Run all 8 stages in sequence. Returns overall verdict."""
        run_id = params.get("run_id")
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT status, loop_count FROM cascade_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        run_status, loop_count = row
        if loop_count >= cfg.MAX_RETRY:
            cur.execute(
                "UPDATE cascade_runs SET status='failed', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                (run_id,),
            )
            db.commit()
            db.close()
            return (0, None, cfg.GetError("max_retry_exceeded"))
        cur.execute(
            "UPDATE cascade_runs SET loop_count=loop_count+1, updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (run_id,),
        )
        db.commit()
        db.close()
        all_verdicts = {}
        has_fail = False
        has_rewrite = False
        for stage_name in cfg.STAGES:
            ok, data, err = self.Stage({"run_id": run_id, "stage": stage_name})
            if not ok:
                return (0, None, err)
            verdict = data["verdict"]
            all_verdicts[stage_name] = {
                "verdict": verdict,
                "issue_count": data["issue_count"],
            }
            if verdict == "fail":
                has_fail = True
                break
            if verdict == "rewrite":
                has_rewrite = True
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        if has_fail:
            cur.execute(
                "UPDATE cascade_runs SET status='blocked', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                (run_id,),
            )
            db.commit()
            db.close()
            return (0, all_verdicts, cfg.GetError("cascade_blocked", stage=stage_name))
        if has_rewrite:
            ok, data, err = self.Rewrite({"run_id": run_id})
            if ok:
                db.close()
                return self.Validate({"run_id": run_id})
            db.close()
            return (0, all_verdicts, err)
        cur.execute(
            "UPDATE cascade_runs SET status='passed', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (run_id,),
        )
        db.commit()
        db.close()
        return (1, {"all_verdicts": all_verdicts, "status": "passed"}, None)

    def Status(self, params):
        """Return current stage + all verdicts."""
        run_id = params.get("run_id")
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT current_stage, status, loop_count FROM cascade_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        current_stage, status, loop_count = row
        results = cur.execute(
            "SELECT stage, verdict, issue_count FROM cascade_stage_results WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        db.close()
        stage_results = {}
        for stage, verdict, count in results:
            stage_results[stage] = {"verdict": verdict, "issue_count": count}
        return (
            1,
            {
                "run_id": run_id,
                "current_stage": current_stage,
                "status": status,
                "loop_count": loop_count,
                "stage_results": stage_results,
            },
            None,
        )

    def Rewrite(self, params):
        """Regenerate SPEC.md with fixes from failed stages."""
        run_id = params.get("run_id")
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT spec_path FROM cascade_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        spec_path = row[0]
        rewrite_stages = cur.execute(
            "SELECT stage, issues FROM cascade_stage_results WHERE run_id=? AND verdict='rewrite' ORDER BY id",
            (run_id,),
        ).fetchall()
        db.close()
        if not rewrite_stages:
            return (1, {"rewritten": False, "reason": "no rewrite stages"}, None)
        issues_summary = []
        for stage, issues_json in rewrite_stages:
            issues = json.loads(issues_json) if issues_json else []
            for issue in issues:
                issues_summary.append("[{stage}] {rule}".format(stage=stage, rule=issue.get("rule", "unknown")))
        if spec_path and os.path.exists(spec_path):
            with open(spec_path, "r") as f:
                content = f.read()
            rewrite_block = "\n\n## REWRITE NOTES (auto-generated)\n"
            for note in issues_summary:
                rewrite_block += "- {note}\n".format(note=note)
            rewrite_block += "\nGenerated by CascadeEngine.Rewrite()\n"
            with open(spec_path, "w") as f:
                f.write(content + rewrite_block)
        return (1, {"rewritten": True, "issues_addressed": len(issues_summary)}, None)

    def Commit(self, params):
        """Check all stages passed. Allows code generation."""
        run_id = params.get("run_id")
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT status FROM cascade_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        status = row[0]
        db.close()
        if status != "passed":
            return (0, None, cfg.GetError("cascade_not_passed"))
        return (1, {"run_id": run_id, "allowed": True, "status": status}, None)

    def Rules(self, params):
        """Return cascade_rules for a stage."""
        stage = params.get("stage")
        if not stage:
            return (0, None, "missing_param: stage")
        if stage not in cfg.STAGES:
            return (0, None, "invalid_stage: {name}".format(name=stage))
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        rules = cur.execute(
            "SELECT rule_id, rule_text, violation_action, severity FROM cascade_rules WHERE stage=?",
            (stage,),
        ).fetchall()
        db.close()
        rule_list = []
        for rule_id, text, action, severity in rules:
            rule_list.append({
                "rule_id": rule_id,
                "rule": text,
                "action": action,
                "severity": severity,
            })
        return (1, {"stage": stage, "rules": rule_list, "count": len(rule_list)}, None)

    def NextStage(self, current):
        """Return next stage in sequence, or None if last."""
        stages = cfg.STAGES
        if current in stages:
            idx = stages.index(current)
            if idx + 1 < len(stages):
                return stages[idx + 1]
        return None
