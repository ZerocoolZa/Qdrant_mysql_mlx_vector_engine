class VBStyleAutoFix:

    RequiredHeaderTags = ("[@GHOST]", "[@SPEC]", "[@VBSTYLE]", "[@LAW]", "[@LIFECYCLE]", "[@PROOF]")

    DefaultLifecycle = '#[@LIFECYCLE]{("State";"Candidate");("Owner";"Wayne");("Reviewed";"2026-04-28")}'
    DefaultProof     = '#[@PROOF]{("Compile";"AstParse");("Tuple3";"Pending");("Schema";"Pending")}'
    DefaultLaw       = '#[@LAW]{("Pass";"Pending");("Fail";"Pending")}'
    DefaultGhost     = '#[@GHOST]{("File";"%s");("State";"Candidate");("Date";"%s");("Auth";"MemUnit");("Purpose";"AutoSeededHeaderRequiresHumanReview")}'
    DefaultSpec      = '#[@SPEC]{("Domain";"Unknown");("Class";"Unknown");("Authority";"MemUnit");("EntryPoint";"Run")}'
    DefaultVbstyle   = '#[@VBSTYLE]{("MemUnit";"Tuple3";"DBFirst";"NoJson";"NoDecorators";"NoEnums";"NoSysPath";"NoDirectImport";"OneClassOneWorld")}'

    BracketHeaderRe  = re.compile(r"^\s*#\s*\[@([A-Z_]+)\][\{\(]")

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = dict(param or {})
        self.dbPath = self.param.get(
            "db_path",
            "/Users/waynephilliplundall/testbed/AA_MEMORIES/2026_GuisMost_important/Db/master.db",
        )
        self.conn = None
        self.runId = None

    def Issue(self, kind, detail):
        return (str(kind), str(detail))

    def Now(self):
        return datetime.utcnow().isoformat(timespec="seconds")

    def Run(self, param=None):
        if param:
            self.param.update(param)
        action = str(self.param.get("action", "")).strip().lower()
        dispatch = {
            "bootstrap":        self.Bootstrap,
            "planheaderinject": self.PlanHeaderInject,
            "planall":          self.PlanAll,
            "apply":            self.Apply,
            "rollback":         self.Rollback,
            "status":           self.Status,
            "planreport":       self.PlanReport,
            "auditreport":      self.AuditReport,
        }
        fn = dispatch.get(action)
        if fn is None:
            return (False, None, (self.Issue("UnknownAction", action),))
        return fn(self.param)

    def Bootstrap(self, param):
        try:
            self.conn = sqlite3.connect(self.dbPath)
            self.conn.execute("PRAGMA foreign_keys=ON")
            return (True, {"db_path": self.dbPath, "bootstrapped": True}, ())
        except Exception as exc:
            return (False, None, (self.Issue("BootstrapFail", exc),))

    def Sha(self, text):
        return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()

    def Audit(self, planId, event, detail):
        if self.conn is None or self.runId is None:
            return
        self.conn.execute(
            "INSERT INTO autofix_audit(run_id, plan_id, event, detail, created_at)"
            " VALUES(?,?,?,?,?)",
            (self.runId, planId, event, str(detail)[:2000], self.Now()),
        )
        self.conn.commit()

    def OpenRun(self, fixClass, applyMode):
        now = self.Now()
        cur = self.conn.execute(
            "INSERT INTO autofix_run(started_at, apply_mode, fix_class, notes)"
            " VALUES(?,?,?,?)",
            (now, 1 if applyMode else 0, fixClass, "opened"),
        )
        self.conn.commit()
        self.runId = cur.lastrowid
        return self.runId

    def CloseRun(self, stats):
        if self.runId is None:
            return
        self.conn.execute(
            "UPDATE autofix_run SET finished_at=?, files_scanned=?, plans_created=?,"
            " snapshots_taken=?, patches_applied=?, blocked=?, notes=?"
            " WHERE run_id=?",
            (
                self.Now(),
                int(stats.get("files_scanned", 0)),
                int(stats.get("plans_created", 0)),
                int(stats.get("snapshots_taken", 0)),
                int(stats.get("patches_applied", 0)),
                int(stats.get("blocked", 0)),
                str(stats.get("notes", "ok"))[:1000],
                self.runId,
            ),
        )
        self.conn.commit()

    def CollectGovernedFiles(self, scope):
        if scope == "all":
            rows = self.conn.execute(
                "SELECT id, path, name, source FROM code_file"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, path, name, source FROM code_file"
                " WHERE stage IN ('extracted','harvested')"
            ).fetchall()
        out = []
        for fid, path, name, source in rows:
            if not name or not name.endswith(".py"):
                continue
            if not source:
                continue
            if "Unit_" not in (name or "") and "App_" not in (name or ""):
                continue
            out.append((fid, path, name, source))
        return out

    def MissingHeaderTags(self, source):
        head = "
".join(source.splitlines()[:60])
        missing = []
        for tag in self.RequiredHeaderTags:
            if tag not in head:
                missing.append(tag)
        return missing

    def BuildHeaderInjection(self, fileName, missing):
        now = self.Now().split("T")[0]
        block = []
        for tag in missing:
            if tag == "[@GHOST]":
                block.append(self.DefaultGhost % (fileName, now))
            elif tag == "[@SPEC]":
                block.append(self.DefaultSpec)
            elif tag == "[@VBSTYLE]":
                block.append(self.DefaultVbstyle)
            elif tag == "[@LAW]":
                block.append(self.DefaultLaw)
            elif tag == "[@LIFECYCLE]":
                block.append(self.DefaultLifecycle)
            elif tag == "[@PROOF]":
                block.append(self.DefaultProof)
        return "
".join(block) + "
"

    def InsertPoint(self, lines):
        idx = 0
        if lines and lines[0].startswith("#!"):
            idx = 1
        if idx < len(lines) and "coding" in lines[idx][:40] and lines[idx].lstrip().startswith("#"):
            idx += 1
        last = idx
        for i in range(idx, min(len(lines), 80)):
            if self.BracketHeaderRe.match(lines[i]):
                last = i + 1
        return last

    def PlanHeaderInject(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        scope = str(param.get("scope", "extracted")).strip().lower()
        applyMode = bool(param.get("apply", False))
        runId = self.OpenRun("HeaderTagInjection", applyMode)
        files = self.CollectGovernedFiles(scope)
        scanned = 0
        plans = 0
        for fid, path, name, source in files:
            scanned += 1
            missing = self.MissingHeaderTags(source)
            if not missing:
                continue
            lines = source.splitlines(keepends=False)
            insertAt = self.InsertPoint(lines)
            injection = self.BuildHeaderInjection(name or os.path.basename(path or ""), missing)
            newLines = lines[:insertAt] + injection.rstrip("
").split("
") + lines[insertAt:]
            newSource = "
".join(newLines)
            if not source.endswith("
"):
                pass
            else:
                newSource += "
"
            shaAfter = self.Sha(newSource)
            diffSummary = "inject " + ",".join(missing) + " at line " + str(insertAt + 1)
            try:
                cur = self.conn.execute(
                    "INSERT OR REPLACE INTO autofix_plan"
                    "(run_id, file_path, fix_class, weakness_kind, question_id,"
                    " line_start, line_end, old_excerpt, new_excerpt, diff_summary,"
                    " sha256_after, bytes_after, risk_level, apply_state, created_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        runId, path, "HeaderTagInjection", "HeaderWeakness", "Q02",
                        insertAt + 1, insertAt + 1,
                        "
".join(lines[max(0, insertAt - 1):insertAt + 1])[:1000],
                        injection[:1500],
                        diffSummary,
                        shaAfter,
                        len(newSource.encode("utf-8", "replace")),
                        "low",
                        "PLANNED",
                        self.Now(),
                    ),
                )
                planId = cur.lastrowid
                plans += 1
                self.Audit(planId, "PLAN", diffSummary + " :: " + path)
            except sqlite3.IntegrityError as exc:
                self.Audit(None, "ERROR", "PlanInsertFail " + str(exc))
                continue
        self.conn.commit()
        self.CloseRun({
            "files_scanned": scanned,
            "plans_created": plans,
            "snapshots_taken": 0,
            "patches_applied": 0,
            "blocked": 0,
            "notes": "PlanHeaderInject dry-run" if not applyMode else "PlanHeaderInject planned (apply via Apply action)",
        })
        return (True, {
            "run_id": runId,
            "files_scanned": scanned,
            "plans_created": plans,
            "apply_mode": applyMode,
            "next_step": "Apply" if applyMode else "Inspect autofix_plan then call Apply with apply=true and run_id",
        }, ())

    def PlanAll(self, param):
        return self.PlanHeaderInject(param)

    def TakeSnapshot(self, runId, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as exc:
            return (False, self.Issue("SnapshotReadFail", str(path) + ": " + str(exc)))
        sha = self.Sha(content)
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO autofix_snapshot"
                "(run_id, file_path, sha256_before, bytes_before, content_before, taken_at)"
                " VALUES(?,?,?,?,?,?)",
                (runId, path, sha, len(content.encode("utf-8", "replace")), content, self.Now()),
            )
            self.conn.commit()
        except Exception as exc:
            return (False, self.Issue("SnapshotInsertFail", str(exc)))
        return (True, {"sha": sha, "bytes": len(content)})

    def HasSnapshot(self, runId, path):
        row = self.conn.execute(
            "SELECT snapshot_id FROM autofix_snapshot WHERE run_id=? AND file_path=?",
            (runId, path),
        ).fetchone()
        return bool(row)

    def ApplyPlan(self, runId, plan):
        planId, filePath, fixClass, lineStart, oldExcerpt, newExcerpt, diffSummary = plan
        if not self.HasSnapshot(runId, filePath):
            ok, info = self.TakeSnapshot(runId, filePath)
            if not ok:
                self.Audit(planId, "BLOCK", "snapshot_failed " + str(info))
                self.conn.execute(
                    "UPDATE autofix_plan SET apply_state='BLOCKED', apply_reason=? WHERE plan_id=?",
                    ("snapshot_failed: " + str(info), planId),
                )
                self.conn.commit()
                return ("BLOCK", info)
            self.Audit(planId, "SNAPSHOT", "sha=" + str(info.get("sha")))
        try:
            with open(filePath, "r", encoding="utf-8", errors="replace") as f:
                current = f.read()
        except Exception as exc:
            self.Audit(planId, "ERROR", "ReadFail " + str(exc))
            return ("ERROR", str(exc))
        if fixClass != "HeaderTagInjection":
            self.Audit(planId, "SKIP", "unsupported_fix_class " + fixClass)
            self.conn.execute(
                "UPDATE autofix_plan SET apply_state='SKIPPED', apply_reason='unsupported_fix_class' WHERE plan_id=?",
                (planId,),
            )
            self.conn.commit()
            return ("SKIP", fixClass)
        lines = current.splitlines(keepends=False)
        insertAt = max(0, int(lineStart) - 1)
        injection = newExcerpt or ""
        if injection.strip() == "":
            self.Audit(planId, "SKIP", "empty_injection")
            return ("SKIP", "empty")
        injectionLines = injection.rstrip("
").split("
")
        newLines = lines[:insertAt] + injectionLines + lines[insertAt:]
        newSource = "
".join(newLines)
        if current.endswith("
"):
            newSource += "
"
        try:
            ast.parse(newSource)
        except SyntaxError as exc:
            self.Audit(planId, "BLOCK", "post_patch_syntax_error " + str(exc))
            self.conn.execute(
                "UPDATE autofix_plan SET apply_state='BLOCKED', apply_reason=? WHERE plan_id=?",
                ("post_patch_syntax_error: " + str(exc), planId),
            )
            self.conn.commit()
            return ("BLOCK", "syntax")
        try:
            with open(filePath, "w", encoding="utf-8") as f:
                f.write(newSource)
        except Exception as exc:
            self.Audit(planId, "ERROR", "WriteFail " + str(exc))
            return ("ERROR", str(exc))
        self.conn.execute(
            "UPDATE autofix_plan SET apply_state='APPLIED', applied_at=? WHERE plan_id=?",
            (self.Now(), planId),
        )
        self.conn.commit()
        self.Audit(planId, "APPLY", diffSummary)
        return ("APPLIED", {"file": filePath})

    def Apply(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        if not bool(param.get("apply", False)):
            return (False, None, (self.Issue("ApplyGate", "apply=true required to actually patch files"),))
        runId = param.get("run_id")
        if runId is None:
            return (False, None, (self.Issue("RunIdRequired", "pass run_id from Plan output"),))
        try:
            runId = int(runId)
        except Exception:
            return (False, None, (self.Issue("RunIdInvalid", str(runId)),))
        self.runId = runId
        rows = self.conn.execute(
            "SELECT plan_id, file_path, fix_class, line_start, old_excerpt, new_excerpt, diff_summary"
            " FROM autofix_plan WHERE run_id=? AND apply_state='PLANNED'",
            (runId,),
        ).fetchall()
        applied = 0
        blocked = 0
        skipped = 0
        for plan in rows:
            state, _ = self.ApplyPlan(runId, plan)
            if state == "APPLIED":
                applied += 1
            elif state == "BLOCK":
                blocked += 1
            else:
                skipped += 1
        snapCount = self.conn.execute(
            "SELECT COUNT(*) FROM autofix_snapshot WHERE run_id=?", (runId,)
        ).fetchone()[0]
        self.conn.execute(
            "UPDATE autofix_run SET patches_applied=?, snapshots_taken=?, blocked=?, finished_at=?"
            " WHERE run_id=?",
            (applied, snapCount, blocked, self.Now(), runId),
        )
        self.conn.commit()
        return (True, {
            "run_id": runId,
            "planned": len(rows),
            "applied": applied,
            "blocked": blocked,
            "skipped": skipped,
            "snapshots": snapCount,
        }, ())

    def Rollback(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        runId = param.get("run_id")
        if runId is None:
            return (False, None, (self.Issue("RunIdRequired", "pass run_id"),))
        self.runId = int(runId)
        if not bool(param.get("confirm", False)):
            return (False, None, (self.Issue("ConfirmRequired", "pass confirm=true to rollback"),))
        snaps = self.conn.execute(
            "SELECT snapshot_id, file_path, content_before FROM autofix_snapshot WHERE run_id=?",
            (self.runId,),
        ).fetchall()
        restored = 0
        failed = 0
        for snapId, path, content in snaps:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                restored += 1
                self.Audit(None, "ROLLBACK", "snapshot=" + str(snapId) + " path=" + path)
            except Exception as exc:
                failed += 1
                self.Audit(None, "ERROR", "RollbackFail " + str(exc))
        self.conn.execute(
            "UPDATE autofix_plan SET apply_state='ROLLED_BACK' WHERE run_id=? AND apply_state='APPLIED'",
            (self.runId,),
        )
        self.conn.commit()
        return (True, {"run_id": self.runId, "restored": restored, "failed": failed}, ())

    def Status(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        runs = self.conn.execute(
            "SELECT run_id, started_at, finished_at, apply_mode, fix_class,"
            " files_scanned, plans_created, snapshots_taken, patches_applied, blocked"
            " FROM autofix_run ORDER BY run_id DESC LIMIT 10"
        ).fetchall()
        return (True, {"recent_runs": [list(r) for r in runs], "db_path": self.dbPath}, ())

    def PlanReport(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        runId = param.get("run_id")
        if runId is None:
            row = self.conn.execute(
                "SELECT run_id FROM autofix_run ORDER BY run_id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return (True, {"run_id": None, "plans": []}, ())
            runId = row[0]
        rows = self.conn.execute(
            "SELECT plan_id, file_path, fix_class, weakness_kind, question_id,"
            " line_start, diff_summary, risk_level, apply_state, applied_at"
            " FROM autofix_plan WHERE run_id=? ORDER BY plan_id",
            (int(runId),),
        ).fetchall()
        return (True, {
            "run_id": int(runId),
            "plan_count": len(rows),
            "plans": [list(r) for r in rows[:200]],
            "truncated": len(rows) > 200,
        }, ())

    def AuditReport(self, param):
        if self.conn is None:
            ok, _, iss = self.Bootstrap(param)
            if not ok:
                return (False, None, iss)
        runId = param.get("run_id")
        if runId is None:
            row = self.conn.execute(
                "SELECT run_id FROM autofix_run ORDER BY run_id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return (True, {"events": []}, ())
            runId = row[0]
        rows = self.conn.execute(
            "SELECT audit_id, plan_id, event, detail, created_at"
            " FROM autofix_audit WHERE run_id=? ORDER BY audit_id",
            (int(runId),),
        ).fetchall()
        return (True, {"run_id": int(runId), "event_count": len(rows), "events": [list(r) for r in rows[:500]]}, ())
