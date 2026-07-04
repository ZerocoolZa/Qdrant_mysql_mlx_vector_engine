#!/usr/bin/env python3
"""
Database Interrogation Layer — lets Cascade (or any AI) ask the v20 database
questions and get structured answers back. An interview with the database.

The database is not just storage. It is a knowledge base.
The AI asks questions. The database answers from stored facts.

Usage:
    from db_interrogator import DbInterrogator
    db = DbInterrogator()
    ok, data, err = db.Run("what_exists", {})
    ok, data, err = db.Run("what_is_missing", {})
    ok, data, err = db.Run("i_need", {"capability": "compress"})
    ok, data, err = db.Run("what_depends_on", {"class_name": "DomTesting"})
    ok, data, err = db.Run("what_plans_exist", {})

VBStyle: Run(command, params) dispatch, returns Tuple3 (ok, data, error).
"""

import os
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "code_store_variations", "v20_hybrid_best.db")


class DbInterrogator:
    """Ask the database questions. Get structured answers."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "db_path": None, "connected": False}
        if param and "db_path" in param:
            self.state["db_path"] = param["db_path"]
        else:
            self.state["db_path"] = os.path.abspath(DB_PATH)
        self.state["connected"] = os.path.exists(self.state["db_path"])

    def Run(self, command, params=None):
        """Dispatch entry point. Returns Tuple3 (ok, data, error)."""
        params = params or {}
        handlers = {
            # ── Capability questions ──
            "what_exists": self.WhatExists,
            "what_domains": self.WhatDomains,
            "what_can_domain_do": self.WhatCanDomainDo,
            "what_methods_exist": self.WhatMethodsExist,
            "what_capabilities": self.WhatCapabilities,
            "what_computational_units": self.WhatComputationalUnits,

            # ── Gap questions ──
            "what_is_missing": self.WhatIsMissing,
            "which_classes_no_methods": self.WhichClassesNoMethods,
            "which_methods_no_callers": self.WhichMethodsNoCallers,
            "which_plans_cannot_execute": self.WhichPlansCannotExecute,
            "which_recipes_reference_missing": self.WhichRecipesReferenceMissing,
            "what_violations": self.WhatViolations,

            # ── Dependency questions ──
            "what_depends_on": self.WhatDependsOn,
            "what_breaks_if_removed": self.WhatBreaksIfRemoved,
            "most_depended_on": self.MostDependedOn,
            "circular_dependencies": self.CircularDependencies,

            # ── Lifecycle questions ──
            "lifecycle_of": self.LifecycleOf,
            "what_lifecycle_stages_missing": self.WhatLifecycleStagesMissing,

            # ── Error questions ──
            "where_can_fail": self.WhereCanFail,
            "what_failures_occurred": self.WhatFailuresOccurred,
            "what_repairs_exist": self.WhatRepairsExist,
            "which_failures_no_repair": self.WhichFailuresNoRepair,

            # ── Orchestration questions ──
            "who_calls_this": self.WhoCallsThis,
            "what_does_this_call": self.WhatDoesThisCall,
            "what_execution_chains": self.WhatExecutionChains,
            "what_recipes_use": self.WhatRecipesUse,

            # ── Plan questions ──
            "what_plans_exist": self.WhatPlansExist,
            "what_plan_goals": self.WhatPlanGoals,
            "which_plans_succeeded": self.WhichPlansSucceeded,
            "which_plans_failed": self.WhichPlansFailed,
            "which_plans_similar": self.WhichPlansSimilar,
            "which_plans_promoted": self.WhichPlansPromoted,
            "what_plan_produces": self.WhatPlanProduces,

            # ── Composition questions ──
            "i_need": self.INeed,
            "what_can_compose": self.WhatCanCompose,

            # ── Coverage questions ──
            "what_is_not_covered": self.WhatIsNotCovered,
            "what_has_no_owner": self.WhatHasNoOwner,
            "what_has_no_lifecycle": self.WhatHasNoLifecycle,
            "what_has_no_test_path": self.WhatHasNoTestPath,

            # ── Stability questions ──
            "what_is_stable_core": self.WhatIsStableCore,
            "what_is_fragile": self.WhatIsFragile,
            "what_is_frequently_changed": self.WhatIsFrequentlyChanged,

            # ── Emergence questions ──
            "what_systems_emerge": self.WhatSystemsEmerge,
            "what_hidden_capabilities": self.WhatHiddenCapabilities,
            "what_is_possible_but_undeclared": self.WhatIsPossibleButUndeclared,

            # ── W-questions (natural language mapping) ──
            "ask": self.Ask,

            # ── Conversational (being-like composed responses) ──
            "do_you_have": self.DoYouHave,
            "how_does_work": self.HowDoesWork,
            "what_about": self.WhatAbout,
            "can_you_build": self.CanYouBuild,
            "what_are_you": self.WhatAreYou,

            # ── BCL Identity (self-describing entities) ──
            "who_are_you_bcl": self.WhoAreYouBCL,
            "bcl_identity": self.BclIdentity,
            "bcl_search": self.BclSearch,

            # ── Meta questions ──
            "who_are_you": self.WhoAreYou,
            "what_tables": self.WhatTables,
            "help": self.Help,
        }

        handler = handlers.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}. Call 'help' for available questions.", 0))

        if not self.state["connected"]:
            return (0, None, ("DB_NOT_FOUND", f"Database not found at {self.state['db_path']}", 0))

        try:
            return handler(params)
        except Exception as e:
            return (0, None, ("QUERY_ERROR", str(e), 0))

    def _conn(self):
        return sqlite3.connect(self.state["db_path"])

    # ════════════════════════════════════════════════════════════════════════
    # CAPABILITY QUESTIONS — what exists?
    # ════════════════════════════════════════════════════════════════════════

    def WhatExists(self, params):
        """What capabilities exist in the database?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT value FROM _db_meta WHERE key IN ('domain_count','class_count','method_count','plan_count','pipeline_count')")
        meta = {row[0].split("_")[0] + "_count": row[0] for row in c.fetchall()}
        result = {
            "vbstyle_domains": c.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1").fetchone()[0],
            "total_classes": c.execute("SELECT COUNT(*) FROM classes").fetchone()[0],
            "total_methods": c.execute("SELECT COUNT(*) FROM methods").fetchone()[0],
            "computational_units": c.execute("SELECT COUNT(*) FROM computational_units").fetchone()[0],
            "closure_methods": c.execute("SELECT COUNT(*) FROM closure_methods").fetchone()[0],
            "plans": c.execute("SELECT COUNT(*) FROM plans").fetchone()[0],
            "pipelines": c.execute("SELECT COUNT(DISTINCT pipeline) FROM orchestration").fetchone()[0],
            "executions_logged": c.execute("SELECT COUNT(*) FROM execution_log").fetchone()[0],
        }
        conn.close()
        return (1, result, None)

    def WhatDomains(self, params):
        """What domains exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT c.domain, c.class_name, c.description, COUNT(m.id) as method_count
            FROM classes c LEFT JOIN methods m ON m.class_id = c.id
            WHERE c.is_vbstyle = 1
            GROUP BY c.id ORDER BY c.domain
        """)
        domains = [{"domain": r[0], "class": r[1], "description": r[2], "methods": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, domains, None)

    def WhatCanDomainDo(self, params):
        """What can a specific domain do?"""
        domain = params.get("domain", "")
        if not domain:
            return (0, None, ("MISSING_PARAM", "Provide 'domain' parameter", 0))
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT m.method_name, m.params, m.returns_tuple3
            FROM methods m JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND cl.domain = ? AND m.method_name NOT LIKE '\\_%'
            ORDER BY m.method_name
        """, (domain,))
        methods = [{"method": r[0], "params": r[1], "returns_tuple3": bool(r[2])} for r in c.fetchall()]
        conn.close()
        if not methods:
            return (0, None, ("NOT_FOUND", f"Domain '{domain}' not found or has no methods", 0))
        return (1, {"domain": domain, "methods": methods}, None)

    def WhatMethodsExist(self, params):
        """What methods exist matching a pattern?"""
        pattern = params.get("pattern", "")
        conn = self._conn()
        c = conn.cursor()
        if pattern:
            c.execute("""
                SELECT cl.class_name, cl.domain, m.method_name
                FROM methods m JOIN classes cl ON m.class_id = cl.id
                WHERE cl.is_vbstyle = 1 AND m.method_name LIKE ?
                ORDER BY cl.domain, m.method_name
            """, (f"%{pattern}%",))
        else:
            c.execute("""
                SELECT cl.class_name, cl.domain, m.method_name
                FROM methods m JOIN classes cl ON m.class_id = cl.id
                WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
                ORDER BY cl.domain, m.method_name
            """)
        methods = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, methods, None)

    def WhatCapabilities(self, params):
        """What capabilities (class+method combos) exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT cl.domain, cl.class_name, GROUP_CONCAT(m.method_name, ', ') as methods
            FROM methods m JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
            GROUP BY cl.id ORDER BY cl.domain
        """)
        caps = [{"domain": r[0], "class": r[1], "methods": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, caps, None)

    def WhatComputationalUnits(self, params):
        """What computational units exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT unit_name, unit_type, cl.class_name, cu.description
            FROM computational_units cu LEFT JOIN classes cl ON cu.class_id = cl.id
            ORDER BY cu.unit_type, cu.unit_name LIMIT 100
        """)
        units = [{"unit": r[0], "type": r[1], "class": r[2], "description": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, units, None)

    # ════════════════════════════════════════════════════════════════════════
    # GAP QUESTIONS — what is missing?
    # ════════════════════════════════════════════════════════════════════════

    def WhatIsMissing(self, params):
        """What is missing across the whole system?"""
        conn = self._conn()
        c = conn.cursor()
        gaps = []

        # Domains not at 100% closure
        c.execute("SELECT domain, methods_missing, closure_pct FROM closure_status WHERE closure_pct < 100.0")
        for r in c.fetchall():
            gaps.append({"kind": "incomplete_domain", "domain": r[0], "missing_methods": r[1], "closure_pct": r[2]})

        # Methods not implemented
        c.execute("SELECT domain, method_name FROM closure_methods WHERE is_implemented = 0")
        for r in c.fetchall():
            gaps.append({"kind": "unimplemented_method", "domain": r[0], "method": r[1]})

        # Plans with no outcomes (never executed)
        c.execute("SELECT id, name FROM plans WHERE id NOT IN (SELECT DISTINCT plan_id FROM plan_outcomes)")
        for r in c.fetchall():
            gaps.append({"kind": "plan_never_executed", "plan_id": r[0], "plan": r[1]})

        # Orchestration steps referencing non-VBStyle classes
        c.execute("""
            SELECT o.pipeline, o.sequence, o.class_id, c.class_name
            FROM orchestration o JOIN classes c ON o.class_id = c.id
            WHERE c.is_vbstyle = 0
        """)
        for r in c.fetchall():
            gaps.append({"kind": "recipe_uses_non_vbstyle", "pipeline": r[0], "step": r[1], "class": r[3]})

        # Violations
        c.execute("SELECT COUNT(*) FROM violations")
        vcount = c.fetchone()[0]
        if vcount > 0:
            gaps.append({"kind": "violations", "count": vcount})

        conn.close()
        return (1, gaps if gaps else [{"kind": "none", "message": "No gaps found"}], None)

    def WhichClassesNoMethods(self, params):
        """Which classes have no methods?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT cl.class_name, cl.domain FROM classes cl
            WHERE cl.id NOT IN (SELECT DISTINCT class_id FROM methods)
        """)
        classes = [{"class": r[0], "domain": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, classes if classes else [], None)

    def WhichMethodsNoCallers(self, params):
        """Which methods are never called in any orchestration or plan?"""
        conn = self._conn()
        c = conn.cursor()
        # Get all methods called in plans
        c.execute("SELECT DISTINCT method_name FROM plan_steps")
        called_in_plans = {r[0] for r in c.fetchall()}
        # Get all VBStyle methods not in plans
        c.execute("""
            SELECT cl.class_name, m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
            AND m.method_name NOT IN ('Run', '__init__')
        """)
        uncalled = []
        for r in c.fetchall():
            if r[1] not in called_in_plans:
                uncalled.append({"class": r[0], "method": r[1]})
        conn.close()
        return (1, uncalled, None)

    def WhichPlansCannotExecute(self, params):
        """Which plans reference capabilities that don't exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id, name FROM plans")
        plans = c.fetchall()
        broken = []
        for pid, pname in plans:
            c.execute("""
                SELECT ps.step_name, ps.class_id, ps.method_name
                FROM plan_steps ps WHERE ps.plan_id = ?
            """, (pid,))
            for step_name, class_id, method_name in c.fetchall():
                if class_id:
                    c2 = conn.cursor()
                    c2.execute("SELECT COUNT(*) FROM methods WHERE class_id = ? AND method_name = ?", (class_id, method_name))
                    if c2.fetchone()[0] == 0:
                        broken.append({"plan": pname, "step": step_name, "reason": f"method '{method_name}' not found on class_id={class_id}"})
        conn.close()
        return (1, broken if broken else [{"kind": "none", "message": "All plans can execute"}], None)

    def WhichRecipesReferenceMissing(self, params):
        """Which orchestration recipes reference missing capabilities?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT o.pipeline, o.sequence, o.class_id
            FROM orchestration o
            WHERE o.class_id NOT IN (SELECT id FROM classes)
        """)
        missing = [{"pipeline": r[0], "step": r[1], "class_id": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, missing if missing else [{"kind": "none", "message": "All recipes reference valid classes"}], None)

    def WhatViolations(self, params):
        """What VBStyle violations exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT v.kind, v.message, cl.class_name, m.method_name
            FROM violations v
            LEFT JOIN methods m ON v.method_id = m.id
            LEFT JOIN classes cl ON m.class_id = cl.id
            LIMIT 100
        """)
        violations = [{"kind": r[0], "message": r[1], "class": r[2], "method": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, violations, None)

    # ════════════════════════════════════════════════════════════════════════
    # DEPENDENCY QUESTIONS — what depends on what?
    # ════════════════════════════════════════════════════════════════════════

    def WhatDependsOn(self, params):
        """What depends on a given class?"""
        class_name = params.get("class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name' parameter", 0))
        conn = self._conn()
        c = conn.cursor()
        # Find class_id
        c.execute("SELECT id FROM classes WHERE class_name = ?", (class_name,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Class '{class_name}' not found", 0))
        class_id = row[0]
        # Find who uses it in orchestration
        c.execute("SELECT pipeline, sequence, role FROM orchestration WHERE class_id = ?", (class_id,))
        used_in = [{"pipeline": r[0], "step": r[1], "role": r[2]} for r in c.fetchall()]
        # Find who uses it in plans
        c.execute("""
            SELECT p.name, ps.step_name FROM plan_steps ps
            JOIN plans p ON ps.plan_id = p.id WHERE ps.class_id = ?
        """, (class_id,))
        used_in_plans = [{"plan": r[0], "step": r[1]} for r in c.fetchall()]
        # Find it as a plan ingredient
        c.execute("""
            SELECT p.name, pi.role FROM plan_ingredients pi
            JOIN plans p ON pi.plan_id = p.id WHERE pi.class_id = ?
        """, (class_id,))
        ingredient_of = [{"plan": r[0], "role": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, {
            "class": class_name,
            "used_in_recipes": used_in,
            "used_in_plans": used_in_plans,
            "ingredient_of": ingredient_of,
        }, None)

    def WhatBreaksIfRemoved(self, params):
        """If a class is removed, what breaks?"""
        class_name = params.get("class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name' parameter", 0))
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM classes WHERE class_name = ?", (class_name,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Class '{class_name}' not found", 0))
        class_id = row[0]
        breaks = []
        # Pipelines that use it
        c.execute("SELECT DISTINCT pipeline FROM orchestration WHERE class_id = ?", (class_id,))
        pipelines = [r[0] for r in c.fetchall()]
        if pipelines:
            breaks.append({"what": "pipelines", "which": pipelines})
        # Plans that use it
        c.execute("""
            SELECT DISTINCT p.name FROM plan_steps ps
            JOIN plans p ON ps.plan_id = p.id WHERE ps.class_id = ?
        """, (class_id,))
        plans = [r[0] for r in c.fetchall()]
        if plans:
            breaks.append({"what": "plans", "which": plans})
        # Plans that use it as ingredient
        c.execute("""
            SELECT DISTINCT p.name FROM plan_ingredients pi
            JOIN plans p ON pi.plan_id = p.id WHERE pi.class_id = ?
        """, (class_id,))
        ingredients = [r[0] for r in c.fetchall()]
        if ingredients:
            breaks.append({"what": "plan_ingredients", "which": ingredients})
        # Methods that disappear
        c.execute("SELECT COUNT(*) FROM methods WHERE class_id = ?", (class_id,))
        method_count = c.fetchone()[0]
        breaks.append({"what": "methods_lost", "count": method_count})
        conn.close()
        return (1, {"class": class_name, "breaks": breaks}, None)

    def MostDependedOn(self, params):
        """Which classes are used the most across recipes and plans?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT cl.class_name, cl.domain,
                COUNT(DISTINCT o.pipeline) as recipe_count,
                COUNT(DISTINCT p.id) as plan_count
            FROM classes cl
            LEFT JOIN orchestration o ON o.class_id = cl.id
            LEFT JOIN plan_steps ps ON ps.class_id = cl.id
            LEFT JOIN plans p ON ps.plan_id = p.id
            WHERE cl.is_vbstyle = 1
            GROUP BY cl.id
            HAVING recipe_count > 0 OR plan_count > 0
            ORDER BY (recipe_count + plan_count) DESC
            LIMIT 20
        """)
        result = [{"class": r[0], "domain": r[1], "recipes": r[2], "plans": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, result, None)

    def CircularDependencies(self, params):
        """Are there circular dependencies between plan steps?"""
        conn = self._conn()
        c = conn.cursor()
        # Check if any plan produces something it also consumes
        c.execute("""
            SELECT p.name, ps1.step_name, ps2.step_name, ps1.produces
            FROM plan_steps ps1
            JOIN plan_steps ps2 ON ps1.plan_id = ps2.plan_id
            AND ps1.sequence < ps2.sequence
            AND ps1.consumes LIKE '%' || ps2.produces || '%'
            AND ps2.consumes LIKE '%' || ps1.produces || '%'
            JOIN plans p ON ps1.plan_id = p.id
        """)
        circular = [{"plan": r[0], "step_a": r[1], "step_b": r[2], "shared": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, circular if circular else [{"kind": "none", "message": "No circular dependencies found"}], None)

    # ════════════════════════════════════════════════════════════════════════
    # LIFECYCLE QUESTIONS — when does it run?
    # ════════════════════════════════════════════════════════════════════════

    def LifecycleOf(self, params):
        """What is the lifecycle of a domain or class?"""
        class_name = params.get("class_name", "")
        domain = params.get("domain", "")
        if not class_name and not domain:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name' or 'domain'", 0))
        conn = self._conn()
        c = conn.cursor()
        if class_name:
            c.execute("SELECT id, domain, description FROM classes WHERE class_name = ? AND is_vbstyle = 1", (class_name,))
        else:
            c.execute("SELECT id, domain, description FROM classes WHERE domain = ? AND is_vbstyle = 1", (domain,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Class/domain not found", 0))
        class_id, dom, desc = row
        # Where does it appear in orchestration (lifecycle stages)
        c.execute("SELECT pipeline, sequence, role FROM orchestration WHERE class_id = ? ORDER BY pipeline, sequence", (class_id,))
        stages = [{"pipeline": r[0], "step": r[1], "role": r[2]} for r in c.fetchall()]
        # Where in plans
        c.execute("""
            SELECT p.name, ps.sequence, ps.step_name, ps.produces, ps.consumes
            FROM plan_steps ps JOIN plans p ON ps.plan_id = p.id
            WHERE ps.class_id = ? ORDER BY p.name, ps.sequence
        """, (class_id,))
        plan_stages = [{"plan": r[0], "step": r[1], "name": r[2], "produces": r[3], "consumes": r[4]} for r in c.fetchall()]
        conn.close()
        return (1, {
            "class": class_name or dom,
            "domain": dom,
            "description": desc,
            "orchestration_stages": stages,
            "plan_stages": plan_stages,
        }, None)

    def WhatLifecycleStagesMissing(self, params):
        """What lifecycle stages are missing across the system?"""
        # Check which pipelines lack error handling, verification, etc.
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT pipeline FROM orchestration")
        pipelines = [r[0] for r in c.fetchall()]
        missing = []
        for p in pipelines:
            c.execute("SELECT role FROM orchestration WHERE pipeline = ?", (p,))
            roles = [r[0].lower() for r in c.fetchall()]
            has_error = any("error" in r or "repair" in r or "recover" in r for r in roles)
            has_verify = any("verify" in r or "validate" in r or "check" in r for r in roles)
            has_report = any("report" in r or "format" in r or "output" in r for r in roles)
            if not has_error:
                missing.append({"pipeline": p, "missing": "error_handling"})
            if not has_verify:
                missing.append({"pipeline": p, "missing": "verification"})
            if not has_report:
                missing.append({"pipeline": p, "missing": "reporting"})
        conn.close()
        return (1, missing if missing else [{"kind": "none", "message": "All pipelines have complete lifecycle stages"}], None)

    # ════════════════════════════════════════════════════════════════════════
    # ERROR QUESTIONS — where does it fail?
    # ════════════════════════════════════════════════════════════════════════

    def WhereCanFail(self, params):
        """Where can the system fail?"""
        conn = self._conn()
        c = conn.cursor()
        # Methods with no try/catch
        c.execute("""
            SELECT cl.class_name, m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
            AND m.method_name != 'Run' AND m.method_name != '__init__'
            AND m.method_code NOT LIKE '%try%' AND m.method_code NOT LIKE '%except%'
            LIMIT 50
        """)
        no_try = [{"class": r[0], "method": r[1], "risk": "no error handling"} for r in c.fetchall()]
        # Violations
        c.execute("SELECT kind, COUNT(*) FROM violations GROUP BY kind ORDER BY COUNT(*) DESC")
        violations = [{"kind": r[0], "count": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, {"methods_without_error_handling": no_try, "violation_summary": violations}, None)

    def WhatFailuresOccurred(self, params):
        """What failures have occurred in execution?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT status, COUNT(*) as cnt FROM execution_log
            GROUP BY status ORDER BY cnt DESC
        """)
        statuses = [{"status": r[0], "count": r[1]} for r in c.fetchall()]
        c.execute("""
            SELECT el.status, cl.class_name, m.method_name
            FROM execution_log el
            LEFT JOIN methods m ON el.method_id = m.id
            LEFT JOIN classes cl ON m.class_id = cl.id
            WHERE el.status != 'OK'
            LIMIT 50
        """)
        failures = [{"status": r[0], "class": r[1], "method": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, {"status_summary": statuses, "failure_examples": failures}, None)

    def WhatRepairsExist(self, params):
        """What repair capabilities exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT cl.class_name, cl.domain, m.method_name
            FROM methods m JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1
            AND (m.method_name LIKE '%repair%' OR m.method_name LIKE '%recover%'
                 OR m.method_name LIKE '%restore%' OR m.method_name LIKE '%backup%'
                 OR m.method_name LIKE '%fix%')
            ORDER BY cl.domain
        """)
        repairs = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, repairs, None)

    def WhichFailuresNoRepair(self, params):
        """Which failures have no repair path?"""
        conn = self._conn()
        c = conn.cursor()
        # Domains without any repair/recover methods
        c.execute("""
            SELECT DISTINCT cl.domain, cl.class_name FROM classes cl
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (
                SELECT DISTINCT m.class_id FROM methods m
                WHERE m.method_name LIKE '%repair%' OR m.method_name LIKE '%recover%'
                OR m.method_name LIKE '%restore%'
            )
            ORDER BY cl.domain
        """)
        no_repair = [{"domain": r[0], "class": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, no_repair, None)

    # ════════════════════════════════════════════════════════════════════════
    # ORCHESTRATION QUESTIONS — who calls who?
    # ════════════════════════════════════════════════════════════════════════

    def WhoCallsThis(self, params):
        """Who calls a given class?"""
        class_name = params.get("class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name'", 0))
        return self.WhatDependsOn(params)

    def WhatDoesThisCall(self, params):
        """What does a given class call?"""
        class_name = params.get("class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name'", 0))
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM classes WHERE class_name = ?", (class_name,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Class '{class_name}' not found", 0))
        class_id = row[0]
        # What methods does it have
        c.execute("""
            SELECT method_name FROM methods WHERE class_id = ? AND method_name NOT LIKE '\\_%'
            AND method_name NOT IN ('Run', '__init__')
            ORDER BY method_name
        """, (class_id,))
        calls = [r[0] for r in c.fetchall()]
        conn.close()
        return (1, {"class": class_name, "methods": calls}, None)

    def WhatExecutionChains(self, params):
        """What execution chains (pipelines) exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT pipeline FROM orchestration ORDER BY pipeline")
        pipelines = []
        for (pname,) in c.fetchall():
            c.execute("""
                SELECT o.sequence, cl.class_name, o.role, o.description
                FROM orchestration o JOIN classes cl ON o.class_id = cl.id
                WHERE o.pipeline = ? ORDER BY o.sequence
            """, (pname,))
            steps = [{"step": r[0], "class": r[1], "role": r[2], "description": r[3]} for r in c.fetchall()]
            pipelines.append({"pipeline": pname, "steps": steps})
        conn.close()
        return (1, pipelines, None)

    def WhatRecipesUse(self, params):
        """What recipes use a given class?"""
        return self.WhatDependsOn(params)

    # ════════════════════════════════════════════════════════════════════════
    # PLAN QUESTIONS — what plans exist?
    # ════════════════════════════════════════════════════════════════════════

    def WhatPlansExist(self, params):
        """What plans exist?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.id, p.name, p.goal, p.status, p.version, p.expected_outcome,
                   (SELECT COUNT(*) FROM plan_steps WHERE plan_id = p.id) as step_count,
                   (SELECT COUNT(*) FROM plan_ingredients WHERE plan_id = p.id) as ingredient_count,
                   p.promoted_to_class_id
            FROM plans p ORDER BY p.id
        """)
        plans = [{
            "id": r[0], "name": r[1], "goal": r[2], "status": r[3], "version": r[4],
            "expected_outcome": r[5], "steps": r[6], "ingredients": r[7],
            "promoted": r[8] is not None
        } for r in c.fetchall()]
        conn.close()
        return (1, plans, None)

    def WhatPlanGoals(self, params):
        """What goals are stored in plans?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT name, goal, expected_outcome FROM plans ORDER BY id")
        goals = [{"plan": r[0], "goal": r[1], "expected_outcome": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, goals, None)

    def WhichPlansSucceeded(self, params):
        """Which plans succeeded?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.name, po.success, po.steps_completed, po.steps_total, po.learned_rules
            FROM plan_outcomes po JOIN plans p ON po.plan_id = p.id
            WHERE po.success = 1
        """)
        succeeded = [{"plan": r[0], "steps_done": r[2], "steps_total": r[3], "learned": r[4]} for r in c.fetchall()]
        conn.close()
        return (1, succeeded if succeeded else [{"kind": "none", "message": "No plans have been executed yet"}], None)

    def WhichPlansFailed(self, params):
        """Which plans failed?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.name, po.success, po.gaps_found, po.notes
            FROM plan_outcomes po JOIN plans p ON po.plan_id = p.id
            WHERE po.success = 0
        """)
        failed = [{"plan": r[0], "gaps_found": r[2], "notes": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, failed if failed else [{"kind": "none", "message": "No failed plans"}], None)

    def WhichPlansSimilar(self, params):
        """Which plans are similar (share ingredients)?"""
        plan_name = params.get("plan_name", "")
        if not plan_name:
            return (0, None, ("MISSING_PARAM", "Provide 'plan_name'", 0))
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM plans WHERE name = ?", (plan_name,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Plan '{plan_name}' not found", 0))
        plan_id = row[0]
        # Get this plan's ingredients
        c.execute("SELECT class_id FROM plan_ingredients WHERE plan_id = ?", (plan_id,))
        my_ingredients = {r[0] for r in c.fetchall()}
        # Find other plans with overlapping ingredients
        c.execute("SELECT id, name FROM plans WHERE id != ?", (plan_id,))
        similar = []
        for pid, pname in c.fetchall():
            c2 = conn.cursor()
            c2.execute("SELECT class_id FROM plan_ingredients WHERE plan_id = ?", (pid,))
            their_ingredients = {r[0] for r in c2.fetchall()}
            overlap = my_ingredients & their_ingredients
            if overlap:
                similar.append({"plan": pname, "shared_ingredients": len(overlap), "overlap": list(overlap)})
        conn.close()
        return (1, sorted(similar, key=lambda x: x["shared_ingredients"], reverse=True), None)

    def WhichPlansPromoted(self, params):
        """Which plans have been promoted to classes?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.name, p.status, p.promoted_to_class_id, cl.class_name
            FROM plans p LEFT JOIN classes cl ON p.promoted_to_class_id = cl.id
            WHERE p.promoted_to_class_id IS NOT NULL
        """)
        promoted = [{"plan": r[0], "status": r[1], "promoted_to": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, promoted if promoted else [{"kind": "none", "message": "No plans have been promoted yet"}], None)

    def WhatPlanProduces(self, params):
        """What does a plan produce at each step? (data flow)"""
        plan_name = params.get("plan_name", "")
        if not plan_name:
            return (0, None, ("MISSING_PARAM", "Provide 'plan_name'", 0))
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT id FROM plans WHERE name = ?", (plan_name,))
        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Plan '{plan_name}' not found", 0))
        plan_id = row[0]
        c.execute("""
            SELECT sequence, step_name, produces, consumes, cl.class_name, method_name
            FROM plan_steps ps LEFT JOIN classes cl ON ps.class_id = cl.id
            WHERE ps.plan_id = ? ORDER BY ps.sequence
        """, (plan_id,))
        flow = [{
            "step": r[0], "name": r[1], "input": r[3], "output": r[2],
            "class": r[4], "method": r[5]
        } for r in c.fetchall()]
        conn.close()
        return (1, {"plan": plan_name, "data_flow": flow}, None)

    # ════════════════════════════════════════════════════════════════════════
    # COMPOSITION QUESTIONS — "I need capability X"
    # ════════════════════════════════════════════════════════════════════════

    def INeed(self, params):
        """I need capability X. Return exact + related + substitutes + compositions."""
        capability = params.get("capability", "").lower()
        if not capability:
            return (0, None, ("MISSING_PARAM", "Provide 'capability' parameter (e.g. 'compress', 'encrypt', 'search')", 0))
        conn = self._conn()
        c = conn.cursor()

        # 1. EXACT MATCHES — methods named exactly like the capability
        c.execute("""
            SELECT cl.class_name, cl.domain, m.method_name
            FROM methods m JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND LOWER(m.method_name) = ?
            ORDER BY cl.domain
        """, (capability,))
        exact = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]

        # 2. RELATED — methods that contain the capability word
        c.execute("""
            SELECT cl.class_name, cl.domain, m.method_name
            FROM methods m JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND LOWER(m.method_name) LIKE ?
            AND LOWER(m.method_name) != ?
            ORDER BY cl.domain
        """, (f"%{capability}%", capability))
        related = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]

        # 3. SUBSTITUTES — domains that could achieve the same outcome
        # Map common capabilities to substitute domains
        substitute_map = {
            "compress": ["archive", "codec", "transform"],
            "encrypt": ["security", "cryptography"],
            "decrypt": ["security", "cryptography"],
            "search": ["index", "knowledge", "graph"],
            "repair": ["rescue", "errorhandling"],
            "verify": ["validate", "testing", "audit"],
            "generate": ["ai", "transform", "documentation"],
            "store": ["storage", "memory", "db", "knowledge"],
            "read": ["io", "fileops", "parse"],
            "write": ["io", "fileops", "storage"],
            "delete": ["fileops", "folder", "storage"],
            "validate": ["testing", "style", "audit"],
            "test": ["testing", "validate"],
            "parse": ["text", "convert", "io"],
            "convert": ["transform", "codec", "convert"],
            "schedule": ["orchestration", "automation"],
            "monitor": ["observability", "logging", "system"],
            "backup": ["rescue", "storage", "db"],
        }
        substitute_domains = substitute_map.get(capability, [])
        substitutes = []
        if substitute_domains:
            placeholders = ",".join("?" * len(substitute_domains))
            c.execute(f"""
                SELECT DISTINCT cl.class_name, cl.domain, cl.description
                FROM classes cl WHERE cl.is_vbstyle = 1
                AND cl.domain IN ({placeholders})
                ORDER BY cl.domain
            """, substitute_domains)
            substitutes = [{"class": r[0], "domain": r[1], "description": r[2]} for r in c.fetchall()]

        # 4. COMPOSITIONS — plans that already use this capability
        c.execute("""
            SELECT DISTINCT p.name, p.goal
            FROM plan_steps ps
            JOIN plans p ON ps.plan_id = p.id
            JOIN classes cl ON ps.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND LOWER(ps.method_name) LIKE ?
        """, (f"%{capability}%",))
        compositions = [{"plan": r[0], "goal": r[1]} for r in c.fetchall()]

        # 5. SEARCH — find the capability in method code (FTS5)
        try:
            c.execute("""
                SELECT DISTINCT class_name, method_name FROM search_idx
                WHERE search_idx MATCH ?
                LIMIT 10
            """, (capability,))
            search_hits = [{"class": r[0], "method": r[1]} for r in c.fetchall()]
        except:
            search_hits = []

        conn.close()
        return (1, {
            "capability": capability,
            "exact_matches": exact,
            "related": related,
            "substitutes": substitutes,
            "existing_compositions": compositions,
            "code_search_hits": search_hits,
        }, None)

    def WhatCanCompose(self, params):
        """What domains can be composed together? Show all plan compositions."""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT p.name, p.goal,
                   GROUP_CONCAT(DISTINCT cl.domain) as domains_used,
                   COUNT(DISTINCT cl.id) as domain_count
            FROM plan_steps ps
            JOIN plans p ON ps.plan_id = p.id
            JOIN classes cl ON ps.class_id = cl.id
            WHERE cl.is_vbstyle = 1
            GROUP BY p.id ORDER BY domain_count DESC
        """)
        compositions = [{"plan": r[0], "goal": r[1], "domains": r[2], "domain_count": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, compositions, None)

    # ════════════════════════════════════════════════════════════════════════
    # COVERAGE QUESTIONS — what is not covered?
    # ════════════════════════════════════════════════════════════════════════

    def WhatIsNotCovered(self, params):
        """What is missing entirely from the system?"""
        conn = self._conn()
        c = conn.cursor()
        uncovered = []

        # Domains with no orchestration usage
        c.execute("""
            SELECT cl.domain, cl.class_name FROM classes cl
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM orchestration)
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM plan_steps)
            ORDER BY cl.domain
        """)
        for r in c.fetchall():
            uncovered.append({"kind": "domain_no_usage", "domain": r[0], "class": r[1]})

        # Methods with no callers (not in any plan)
        c.execute("""
            SELECT cl.class_name, m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
            AND m.method_name NOT IN ('Run', '__init__')
            AND m.method_name NOT IN (SELECT DISTINCT method_name FROM plan_steps)
        """)
        uncalled = [{"class": r[0], "method": r[1]} for r in c.fetchall()]
        if uncalled:
            uncovered.append({"kind": "uncalled_methods", "count": len(uncalled), "sample": uncalled[:20]})

        # Domains with no closure entries
        c.execute("""
            SELECT DISTINCT cl.domain FROM classes cl
            WHERE cl.is_vbstyle = 1
            AND cl.domain NOT IN (SELECT DISTINCT domain FROM closure_status)
        """)
        for r in c.fetchall():
            uncovered.append({"kind": "domain_no_closure_tracking", "domain": r[0]})

        conn.close()
        return (1, uncovered if uncovered else [{"kind": "none", "message": "Everything is covered"}], None)

    def WhatHasNoOwner(self, params):
        """What has no owner — no plan, no recipe, no orchestration?"""
        conn = self._conn()
        c = conn.cursor()
        # Classes not used anywhere
        c.execute("""
            SELECT cl.class_name, cl.domain FROM classes cl
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM orchestration)
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM plan_steps)
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM plan_ingredients)
            ORDER BY cl.domain
        """)
        orphans = [{"class": r[0], "domain": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, {"orphaned_classes": orphans, "count": len(orphans)}, None)

    def WhatHasNoLifecycle(self, params):
        """What has no lifecycle — never created, used, modified, or retired?"""
        conn = self._conn()
        c = conn.cursor()
        # Domains that never appear in any pipeline
        c.execute("""
            SELECT cl.domain, cl.class_name FROM classes cl
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM orchestration)
            ORDER BY cl.domain
        """)
        no_lifecycle = [{"domain": r[0], "class": r[1]} for r in c.fetchall()]
        conn.close()
        return (1, {"domains_with_no_lifecycle": no_lifecycle, "count": len(no_lifecycle)}, None)

    def WhatHasNoTestPath(self, params):
        """What has no test path — domains/methods with no testing coverage?"""
        conn = self._conn()
        c = conn.cursor()
        # Domains that don't use DomTesting in any plan
        c.execute("""
            SELECT DISTINCT cl.domain, cl.class_name FROM classes cl
            WHERE cl.is_vbstyle = 1 AND cl.domain != 'testing'
            AND cl.id NOT IN (
                SELECT ps.class_id FROM plan_steps ps
                JOIN classes c2 ON ps.class_id = c2.id
                WHERE c2.domain = 'testing'
            )
            ORDER BY cl.domain
        """)
        no_test = [{"domain": r[0], "class": r[1]} for r in c.fetchall()]
        # Check closure_tests coverage
        c.execute("SELECT DISTINCT domain FROM closure_tests")
        tested_domains = {r[0] for r in c.fetchall()}
        c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle = 1")
        all_domains = {r[0] for r in c.fetchall()}
        untested = all_domains - tested_domains
        conn.close()
        return (1, {
            "domains_without_test_reference": no_test[:20],
            "domains_without_closure_tests": sorted(untested) if untested else [],
        }, None)

    # ════════════════════════════════════════════════════════════════════════
    # STABILITY QUESTIONS — what is safe vs risky?
    # ════════════════════════════════════════════════════════════════════════

    def WhatIsStableCore(self, params):
        """What is the stable core — most used, most depended on, no violations?"""
        conn = self._conn()
        c = conn.cursor()
        # Classes used in multiple pipelines with no violations
        c.execute("""
            SELECT cl.class_name, cl.domain,
                COUNT(DISTINCT o.pipeline) as pipeline_count,
                COUNT(DISTINCT m.id) as method_count
            FROM classes cl
            LEFT JOIN orchestration o ON o.class_id = cl.id
            LEFT JOIN methods m ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (SELECT DISTINCT method_id FROM violations WHERE method_id IS NOT NULL)
            GROUP BY cl.id
            HAVING pipeline_count > 0
            ORDER BY pipeline_count DESC, method_count DESC
            LIMIT 20
        """)
        stable = [{"class": r[0], "domain": r[1], "pipelines": r[2], "methods": r[3]} for r in c.fetchall()]
        conn.close()
        return (1, {"stable_core": stable}, None)

    def WhatIsFragile(self, params):
        """What is fragile — has violations, no error handling, heavily depended on?"""
        conn = self._conn()
        c = conn.cursor()
        # Classes with violations
        c.execute("""
            SELECT DISTINCT cl.class_name, cl.domain, COUNT(v.id) as violation_count
            FROM violations v
            JOIN methods m ON v.method_id = m.id
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1
            GROUP BY cl.id
            ORDER BY violation_count DESC
            LIMIT 20
        """)
        fragile = [{"class": r[0], "domain": r[1], "violations": r[2]} for r in c.fetchall()]
        # Methods without try/catch that are used in plans
        c.execute("""
            SELECT cl.class_name, m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1 AND m.method_name NOT LIKE '\\_%'
            AND m.method_code NOT LIKE '%try%' AND m.method_code NOT LIKE '%except%'
            AND m.method_name IN (SELECT DISTINCT method_name FROM plan_steps)
        """)
        risky = [{"class": r[0], "method": r[1], "risk": "no error handling but used in plans"} for r in c.fetchall()]
        conn.close()
        return (1, {"fragile_classes": fragile, "risky_methods_in_plans": risky}, None)

    def WhatIsFrequentlyChanged(self, params):
        """What is frequently changed — high version count, recent updates?"""
        conn = self._conn()
        c = conn.cursor()
        # Plan versions (which plans change most)
        c.execute("""
            SELECT p.name, COUNT(pv.id) as version_count
            FROM plan_versions pv JOIN plans p ON pv.plan_id = p.id
            GROUP BY p.id ORDER BY version_count DESC
        """)
        changed_plans = [{"plan": r[0], "versions": r[1]} for r in c.fetchall()]
        # Classes with highest version numbers
        c.execute("""
            SELECT class_name, domain, version FROM classes
            WHERE is_vbstyle = 1 AND version > 1
            ORDER BY version DESC LIMIT 20
        """)
        changed_classes = [{"class": r[0], "domain": r[1], "version": r[2]} for r in c.fetchall()]
        conn.close()
        return (1, {"frequently_changed_plans": changed_plans, "frequently_changed_classes": changed_classes}, None)

    # ════════════════════════════════════════════════════════════════════════
    # EMERGENCE QUESTIONS — what does this become when combined?
    # ════════════════════════════════════════════════════════════════════════

    def WhatSystemsEmerge(self, params):
        """What systems emerge from these parts? What could be built from existing domains?"""
        conn = self._conn()
        c = conn.cursor()
        # Get all domains
        c.execute("SELECT domain, class_name FROM classes WHERE is_vbstyle = 1 ORDER BY domain")
        all_domains = c.fetchall()
        domain_names = [r[0] for r in all_domains]

        # Known system patterns and what domains they need
        system_patterns = {
            "search_engine": ["search", "index", "text", "transform"],
            "code_generator": ["ai", "parse", "bytecode", "codegraph", "transform", "testing"],
            "chat_system": ["ai", "qa", "search", "knowledge", "memory", "text", "gui", "messaging", "network"],
            "ai_repair_loop": ["testing", "bytecode", "parse", "runtime", "errorhandling", "rescue", "ai", "knowledge", "orchestration"],
            "database_gui": ["db", "db_inv", "gui", "storage", "config"],
            "build_system": ["parse", "codegraph", "style", "validate", "package", "testing"],
            "monitoring_system": ["observability", "logging", "system", "network", "alert"],
            "backup_system": ["rescue", "storage", "db", "archive", "compression", "schedule"],
            "security_system": ["security", "cryptography", "audit", "governance"],
            "documentation_system": ["documentation", "parse", "text", "convert", "knowledge"],
            "deployment_pipeline": ["deployment", "testing", "validate", "config", "orchestration", "runtime"],
            "knowledge_graph": ["knowledge", "graph", "text", "ai", "search", "transform"],
            "data_pipeline": ["ingest", "transform", "validate", "storage", "db", "analytics"],
            "api_server": ["network", "http", "security", "validate", "transform", "config"],
            "file_manager": ["fileops", "folder", "io", "archive", "compression", "gui"],
        }

        emergent = []
        for system_name, needed in system_patterns.items():
            have = [d for d in needed if d in domain_names]
            missing = [d for d in needed if d not in domain_names]
            coverage = len(have) / len(needed) * 100 if needed else 0
            emergent.append({
                "system": system_name,
                "domains_needed": needed,
                "domains_have": have,
                "domains_missing": missing,
                "coverage_pct": round(coverage, 1),
                "buildable": len(missing) == 0,
            })

        emergent.sort(key=lambda x: x["coverage_pct"], reverse=True)
        conn.close()
        return (1, emergent, None)

    def WhatHiddenCapabilities(self, params):
        """What hidden capabilities exist — methods that could do more than they're used for?"""
        conn = self._conn()
        c = conn.cursor()
        # Domains with many methods but no orchestration usage
        c.execute("""
            SELECT cl.class_name, cl.domain, COUNT(m.id) as method_count
            FROM classes cl LEFT JOIN methods m ON m.class_id = cl.id
            WHERE cl.is_vbstyle = 1
            AND cl.id NOT IN (SELECT DISTINCT class_id FROM orchestration)
            GROUP BY cl.id
            HAVING method_count > 5
            ORDER BY method_count DESC
        """)
        hidden = [{"class": r[0], "domain": r[1], "methods": r[2], "note": "capable but unused in any pipeline"} for r in c.fetchall()]
        conn.close()
        return (1, {"hidden_capabilities": hidden}, None)

    def WhatIsPossibleButUndeclared(self, params):
        """What is possible but not declared — domains that could combine but no plan exists?"""
        conn = self._conn()
        c = conn.cursor()
        # Get all domains used in plans
        c.execute("""
            SELECT DISTINCT cl.domain FROM plan_steps ps
            JOIN classes cl ON ps.class_id = cl.id
            WHERE cl.is_vbstyle = 1
        """)
        used_in_plans = {r[0] for r in c.fetchall()}
        # Get all VBStyle domains
        c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle = 1")
        all_domains = {r[0] for r in c.fetchall()}
        # Domains that exist but are not in any plan
        undeclared = sorted(all_domains - used_in_plans)
        conn.close()
        return (1, {
            "domains_not_in_any_plan": undeclared,
            "count": len(undeclared),
            "note": "These domains have capabilities but no plan uses them. They could be composed into new systems.",
        }, None)

    # ════════════════════════════════════════════════════════════════════════
    # W-QUESTIONS — natural language to structured query mapping
    # ════════════════════════════════════════════════════════════════════════

    # Map W-question words to question families
    W_MAP = {
        # WHAT — existence, structure, capability
        "what exists": ("what_exists", {}),
        "what do you have": ("what_exists", {}),
        "what capabilities": ("what_capabilities", {}),
        "what domains": ("what_domains", {}),
        "what methods": ("what_methods_exist", {}),
        "what plans": ("what_plans_exist", {}),
        "what tables": ("what_tables", {}),
        "what is missing": ("what_is_missing", {}),
        "what is not covered": ("what_is_not_covered", {}),
        "what repairs": ("what_repairs_exist", {}),
        "what can compose": ("what_can_compose", {}),
        "what systems emerge": ("what_systems_emerge", {}),
        "what is stable": ("what_is_stable_core", {}),
        "what is fragile": ("what_is_fragile", {}),
        "what is hidden": ("what_hidden_capabilities", {}),
        "what is possible": ("what_is_possible_but_undeclared", {}),
        "what breaks if": ("what_breaks_if_removed", {}),
        "what depends on": ("what_depends_on", {}),
        "what produces": ("what_plan_produces", {}),
        "what recipes use": ("what_recipes_use", {}),
        "what execution chains": ("what_execution_chains", {}),
        "what has no owner": ("what_has_no_owner", {}),
        "what has no test": ("what_has_no_test_path", {}),
        "what violations": ("what_violations", {}),

        # WHERE — location, failure points
        "where can fail": ("where_can_fail", {}),
        "where is it used": ("what_depends_on", {}),

        # WHEN — lifecycle, time
        "when does it run": ("lifecycle_of", {}),
        "when is it created": ("lifecycle_of", {}),

        # WHY — dependency, reason
        "why does it connect": ("what_depends_on", {}),
        "why does a depend": ("what_depends_on", {}),

        # HOW — flow, execution
        "how does it move": ("what_execution_chains", {}),
        "how does it work": ("what_plan_produces", {}),

        # WHO — orchestration
        "who calls this": ("who_calls_this", {}),
        "who are you": ("who_are_you", {}),

        # WHAT IF — hypothetical
        "what if i remove": ("what_breaks_if_removed", {}),
        "what if i need": ("i_need", {}),
    }

    def Ask(self, params):
        """
        Natural language question. Maps W-questions to structured queries.
        params: {"question": "what exists?"} or {"question": "what if I need compress"}
        Returns the same structured answer as the underlying question.
        """
        question = params.get("question", "").lower().strip()
        if not question:
            return (0, None, ("MISSING_PARAM", "Provide 'question' parameter", 0))

        # Try exact match first
        for pattern, (cmd, extra) in self.W_MAP.items():
            if pattern in question:
                # Extract parameters from the question
                merged = dict(extra)
                # Try to extract class_name
                if "class_name" not in merged:
                    for cls in self._extract_class_names(question):
                        merged["class_name"] = cls
                        break
                # Try to extract domain
                if "domain" not in merged:
                    domain = self._extract_domain(question)
                    if domain:
                        merged["domain"] = domain
                # Try to extract capability
                if "capability" not in merged:
                    cap = self._extract_capability(question)
                    if cap:
                        merged["capability"] = cap
                # Try to extract plan_name
                if "plan_name" not in merged:
                    plan = self._extract_plan_name(question)
                    if plan:
                        merged["plan_name"] = plan
                return self.Run(cmd, merged)

        # Fallback: try partial keyword matching
        if "do you have" in question:
            # Extract the capability after "do you have"
            after = question.split("do you have", 1)[1].strip().rstrip("?")
            # Remove common words
            for word in ["support", "capability", "a ", "an ", "the "]:
                after = after.replace(word, "")
            cap = after.strip()
            if cap:
                return self.Run("do_you_have", {"capability": cap})
        if "do you use" in question:
            after = question.split("do you use", 1)[1].strip().rstrip("?")
            return self.Run("what_about", {"topic": after})
        if "can you build" in question:
            after = question.split("can you build", 1)[1].strip().rstrip("?").replace("a ", "").replace("an ", "")
            return self.Run("can_you_build", {"system": after})
        if "how does" in question and "work" in question:
            # Extract class or domain name
            after = question.split("how does", 1)[1].split("work", 1)[0].strip()
            for cls in self._extract_class_names(after):
                return self.Run("how_does_work", {"class_name": cls})
            domain = self._extract_domain(after)
            if domain:
                return self.Run("how_does_work", {"domain": domain})
        if "what about" in question:
            after = question.split("what about", 1)[1].strip().rstrip("?")
            return self.Run("what_about", {"topic": after})
        if "what are you" in question:
            return self.Run("what_are_you", {})
        if "who calls" in question or "who uses" in question:
            for cls in self._extract_class_names(question):
                return self.Run("who_calls_this", {"class_name": cls})
        if "produce" in question:
            plan = self._extract_plan_name(question)
            if plan:
                return self.Run("what_plan_produces", {"plan_name": plan})
        if "i need" in question or "need to" in question or "how do i" in question:
            cap = self._extract_capability(question)
            if cap:
                return self.Run("i_need", {"capability": cap})
        if "remove" in question or "delete" in question:
            for cls in self._extract_class_names(question):
                return self.Run("what_breaks_if_removed", {"class_name": cls})
        if "depend" in question:
            for cls in self._extract_class_names(question):
                return self.Run("what_depends_on", {"class_name": cls})
        if "what does" in question and " do" in question:
            plan = self._extract_plan_name(question)
            if plan:
                return self.Run("what_plan_produces", {"plan_name": plan})
            for cls in self._extract_class_names(question):
                return self.Run("what_does_this_call", {"class_name": cls})

        return (0, None, ("UNRECOGNIZED_QUESTION", f"Could not map question: '{question}'. Call 'help' for available questions.", 0))

    def _extract_class_names(self, question):
        """Extract potential class names from a question."""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT class_name FROM classes WHERE is_vbstyle = 1")
        all_classes = [r[0] for r in c.fetchall()]
        conn.close()
        found = []
        q_lower = question.lower()
        for cls in all_classes:
            if cls.lower() in q_lower:
                found.append(cls)
        return found

    def _extract_domain(self, question):
        """Extract a domain name from a question."""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle = 1")
        all_domains = [r[0] for r in c.fetchall()]
        conn.close()
        q_lower = question.lower()
        for d in all_domains:
            if d in q_lower:
                return d
        return None

    def _extract_capability(self, question):
        """Extract a capability keyword from a question."""
        # Common capability words
        caps = ["compress", "encrypt", "decrypt", "search", "repair", "verify",
                "generate", "store", "read", "write", "delete", "validate",
                "test", "parse", "convert", "schedule", "monitor", "backup",
                "restore", "recover", "classify", "embed", "reason", "learn",
                "reflect", "plan", "score", "summarize", "translate"]
        q_lower = question.lower()
        for cap in caps:
            if cap in q_lower:
                return cap
        return None

    def _extract_plan_name(self, question):
        """Extract a plan name from a question."""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT name FROM plans")
        all_plans = [r[0] for r in c.fetchall()]
        conn.close()
        q_lower = question.lower()
        for p in all_plans:
            if p.lower() in q_lower:
                return p
        return None

    # ════════════════════════════════════════════════════════════════════════
    # CONVERSATIONAL ANSWER LAYER — being-like composed responses
    # The database answers as if it were an entity being interviewed.
    # Each response covers multiple angles: capability, structure, behavior,
    # orchestration, plans, gaps. Same question = same answer (deterministic).
    # ════════════════════════════════════════════════════════════════════════

    def DoYouHave(self, params):
        """
        'Do you have GUI support?'
        Checks all layers: domain, methods, orchestration, plans, gaps.
        Returns a composed multi-angle answer.
        """
        capability = params.get("capability", "").lower()
        if not capability:
            return (0, None, ("MISSING_PARAM", "Provide 'capability' (e.g. 'gui', 'compress', 'search')", 0))

        conn = self._conn()
        c = conn.cursor()

        # Map common terms to domain names
        term_to_domain = {
            "gui": "gui", "ui": "gui", "interface": "gui", "widget": "gui",
            "compress": "compression", "archive": "archive", "zip": "archive",
            "encrypt": "cryptography", "decrypt": "cryptography", "crypto": "cryptography",
            "search": "search", "find": "search",
            "database": "db", "db": "db", "sql": "db",
            "test": "testing", "testing": "testing",
            "error": "errorhandling", "repair": "rescue", "fix": "rescue",
            "parse": "parse", "lex": "parse",
            "graph": "graph", "tree": "graph",
            "knowledge": "knowledge", "learn": "ai", "ai": "ai",
            "network": "network", "http": "http", "web": "http",
            "security": "security", "auth": "security",
            "config": "config", "configuration": "config",
            "memory": "memory", "cache": "caching",
            "log": "logging", "logging": "logging",
            "schedule": "schedule", "cron": "schedule",
            "file": "fileops", "filesystem": "fileops",
            "validate": "validate", "validation": "validate",
            "style": "style", "lint": "style",
            "runtime": "runtime", "execute": "runtime",
            "orchestration": "orchestration", "pipeline": "orchestration",
            "backup": "rescue", "restore": "rescue",
            "documentation": "documentation", "docs": "documentation",
            "deploy": "deployment", "deployment": "deployment",
            "monitor": "observability", "observability": "observability",
            "message": "messaging", "queue": "messaging",
            "process": "process", "spawn": "process",
            "package": "package", "build": "package",
            "convert": "convert", "transform": "transform",
            "text": "text", "string": "text",
            "index": "index", "search index": "index",
            "vcs": "vcs", "git": "vcs",
            "yaml": "yaml", "json": "convert",
            "audit": "audit", "compliance": "audit",
            "governance": "governance", "policy": "governance",
            "factory": "factory", "create": "factory",
            "feature": "featureflags", "flag": "featureflags",
            "rate": "ratelimiting", "limit": "ratelimiting",
            "resilience": "resilience", "retry": "resilience",
            "serial": "serialization", "serialize": "serialization",
            "concurrency": "concurrency", "thread": "concurrency",
            "localization": "localization", "i18n": "localization",
            "accessibility": "accessibility", "a11y": "accessibility",
            "automation": "automation", "workflow": "automation",
            "asm": "asm", "assembly": "asm",
            "bytecode": "bytecode", "compile": "bytecode",
            "codegraph": "codegraph", "dependency": "codegraph",
            "csplit": "csplit", "split": "csplit",
            "cu": "cu", "compute": "cu",
            "db_inv": "db_inv", "schema": "db_inv",
            "db_studio": "db_studio",
            "compass": "compass", "navigation": "compass",
            "codec": "codec", "encode": "codec",
            "unify": "unify", "dedupe": "unify",
            "wws_index": "wws_index", "inverted": "wws_index",
            "ingest": "ingest", "import": "ingest",
            "system": "system", "platform": "system",
            "storage": "storage", "blob": "storage",
            "folder": "folder", "directory": "folder",
            "io": "io", "input": "io", "output": "io",
        }

        domain = term_to_domain.get(capability, capability)

        # Layer 1: Domain check
        c.execute("SELECT id, class_name, description FROM classes WHERE is_vbstyle=1 AND domain=?", (domain,))
        domain_row = c.fetchone()
        domain_exists = domain_row is not None

        # Layer 2: Method check
        methods = []
        method_count = 0
        if domain_exists:
            c.execute("""
                SELECT method_name FROM methods WHERE class_id=? AND method_name NOT LIKE '\\_%'
                ORDER BY method_name
            """, (domain_row[0],))
            methods = [r[0] for r in c.fetchall()]
            method_count = len(methods)

        # Layer 3: Orchestration check
        c.execute("SELECT DISTINCT pipeline FROM orchestration WHERE class_id=?", (domain_row[0],)) if domain_exists else None
        pipelines = [r[0] for r in c.fetchall()] if domain_exists else []

        # Layer 4: Plan check
        c.execute("""
            SELECT DISTINCT p.name FROM plan_steps ps
            JOIN plans p ON ps.plan_id = p.id WHERE ps.class_id=?
        """, (domain_row[0],)) if domain_exists else None
        plans = [r[0] for r in c.fetchall()] if domain_exists else []

        # Layer 5: Ingredient check
        c.execute("""
            SELECT DISTINCT p.name FROM plan_ingredients pi
            JOIN plans p ON pi.plan_id = p.id WHERE pi.class_id=?
        """, (domain_row[0],)) if domain_exists else None
        ingredient_in = [r[0] for r in c.fetchall()] if domain_exists else []

        # Layer 6: Closure check
        c.execute("SELECT closure_pct, status FROM closure_status WHERE domain=?", (domain,))
        closure = c.fetchone()

        # Layer 7: Violations
        c.execute("""
            SELECT COUNT(*) FROM violations v
            JOIN methods m ON v.method_id = m.id
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.id=?
        """, (domain_row[0],)) if domain_exists else None
        violation_count = c.fetchone()[0] if domain_exists else 0

        # Compose the answer
        if domain_exists:
            answer = {
                "question": f"Do you have {capability}?",
                "answer": f"Yes. I have the {domain} domain ({domain_row[1]}).",
                "class": domain_row[1],
                "description": domain_row[2],
                "breakdown": {
                    "domain_exists": True,
                    "domain": domain,
                    "methods": method_count,
                    "method_list": methods,
                    "used_in_pipelines": pipelines,
                    "used_in_plans": plans,
                    "ingredient_in_plans": ingredient_in,
                    "closure_pct": closure[0] if closure else None,
                    "closure_status": closure[1] if closure else None,
                    "violations": violation_count,
                },
                "assessment": self._assess_capability(domain_exists, method_count, pipelines, plans, closure, violation_count),
            }
        else:
            # Check if there's a similar domain
            c.execute("SELECT domain, class_name FROM classes WHERE is_vbstyle=1 AND domain LIKE ?", (f"%{capability}%",))
            similar = [{"domain": r[0], "class": r[1]} for r in c.fetchall()]
            # Check if any method matches
            c.execute("""
                SELECT cl.class_name, cl.domain, m.method_name FROM methods m
                JOIN classes cl ON m.class_id = cl.id
                WHERE cl.is_vbstyle=1 AND m.method_name LIKE ?
                LIMIT 5
            """, (f"%{capability}%",))
            method_matches = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]

            answer = {
                "question": f"Do you have {capability}?",
                "answer": f"No. I don't have a domain called '{capability}'.",
                "breakdown": {
                    "domain_exists": False,
                    "similar_domains": similar,
                    "methods_matching": method_matches,
                },
                "assessment": "Not available. " + (
                    f"But I found similar domains: {', '.join(s['domain'] for s in similar)}." if similar else
                    f"But I found methods matching: {', '.join(m['method'] for m in method_matches)}." if method_matches else
                    "No similar capabilities found."
                ),
            }

        conn.close()
        return (1, answer, None)

    def _assess_capability(self, exists, methods, pipelines, plans, closure, violations):
        """Assess overall capability status."""
        if not exists:
            return "Not available."
        parts = []
        if methods > 0:
            parts.append(f"{methods} methods available")
        if pipelines:
            parts.append(f"used in {len(pipelines)} pipeline(s): {', '.join(pipelines)}")
        else:
            parts.append("not used in any pipeline")
        if plans:
            parts.append(f"used in {len(plans)} plan(s)")
        else:
            parts.append("not part of any plan")
        if closure and closure[0] == 100.0:
            parts.append("100% closure")
        elif closure:
            parts.append(f"{closure[0]}% closure ({closure[1]})")
        if violations > 0:
            parts.append(f"{violations} violations")
        else:
            parts.append("no violations")
        return ". ".join(parts) + "."

    def HowDoesWork(self, params):
        """
        'How does the compression class work?'
        Explains a class/domain like a being would: what it is, what it can do,
        how it's used, where it's used, what it depends on, what depends on it.
        """
        class_name = params.get("class_name", "")
        domain = params.get("domain", "")
        if not class_name and not domain:
            return (0, None, ("MISSING_PARAM", "Provide 'class_name' or 'domain'", 0))

        conn = self._conn()
        c = conn.cursor()

        if class_name:
            c.execute("SELECT id, class_name, domain, description FROM classes WHERE class_name=? AND is_vbstyle=1", (class_name,))
        else:
            c.execute("SELECT id, class_name, domain, description FROM classes WHERE domain=? AND is_vbstyle=1", (domain,))

        row = c.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", f"Class/domain not found", 0))

        class_id, cls_name, dom, desc = row

        # What it can do
        c.execute("""
            SELECT method_name, params, returns_tuple3 FROM methods
            WHERE class_id=? AND method_name NOT LIKE '\\_%'
            ORDER BY method_name
        """, (class_id,))
        methods = [{"method": r[0], "params": r[1], "returns_tuple3": bool(r[2])} for r in c.fetchall()]

        # Where it's used (orchestration)
        c.execute("SELECT pipeline, sequence, role FROM orchestration WHERE class_id=? ORDER BY pipeline, sequence", (class_id,))
        used_in = [{"pipeline": r[0], "step": r[1], "role": r[2]} for r in c.fetchall()]

        # What plans use it
        c.execute("""
            SELECT p.name, ps.step_name, ps.produces, ps.consumes
            FROM plan_steps ps JOIN plans p ON ps.plan_id = p.id
            WHERE ps.class_id=? ORDER BY p.name, ps.sequence
        """, (class_id,))
        plan_usage = [{"plan": r[0], "step": r[1], "produces": r[2], "consumes": r[3]} for r in c.fetchall()]

        # What depends on it
        c.execute("SELECT COUNT(DISTINCT pipeline) FROM orchestration WHERE class_id=?", (class_id,))
        pipeline_count = c.fetchone()[0]

        # Closure
        c.execute("SELECT closure_pct, status FROM closure_status WHERE domain=?", (dom,))
        closure = c.fetchone()

        # Violations
        c.execute("""
            SELECT COUNT(*) FROM violations v
            JOIN methods m ON v.method_id = m.id WHERE m.class_id=?
        """, (class_id,))
        violations = c.fetchone()[0]

        # Compose being-like response
        method_names = [m["method"] for m in methods]
        answer = {
            "question": f"How does {cls_name} work?",
            "answer": desc,
            "identity": {
                "class": cls_name,
                "domain": dom,
                "description": desc,
            },
            "what_it_can_do": method_names,
            "how_many_methods": len(methods),
            "where_its_used": used_in,
            "plans_that_use_it": plan_usage,
            "closure": {"pct": closure[0] if closure else None, "status": closure[1] if closure else None},
            "violations": violations,
            "summary": self._summarize_class(cls_name, dom, desc, methods, used_in, plan_usage, closure, violations),
        }

        conn.close()
        return (1, answer, None)

    def _summarize_class(self, cls, dom, desc, methods, used_in, plans, closure, violations):
        """Compose a human-like summary of a class."""
        lines = []
        lines.append(f"{cls} is my {dom} domain.")
        lines.append(f"It {desc.lower()}")
        method_names = [m["method"] for m in methods if m["method"] not in ("Run", "__init__")]
        if method_names:
            lines.append(f"It can {', '.join(method_names[:8])}.")
        if used_in:
            pipelines = list(set(u["pipeline"] for u in used_in))
            lines.append(f"It's used in the {', '.join(pipelines)} pipeline(s).")
        else:
            lines.append("It's not currently used in any pipeline.")
        if plans:
            lines.append(f"It's part of the {', '.join(p['plan'] for p in plans)} plan(s).")
        else:
            lines.append("It's not part of any plan yet.")
        if closure and closure[0] == 100.0:
            lines.append("It's fully closed — all needed methods are implemented.")
        if violations > 0:
            lines.append(f"It has {violations} violation(s) that need attention.")
        return " ".join(lines)

    def WhatAbout(self, params):
        """
        'What about PyTorch?' / 'What about print?'
        General purpose conversational query. Searches for anything matching.
        """
        topic = params.get("topic", params.get("capability", "")).lower()
        if not topic:
            return (0, None, ("MISSING_PARAM", "Provide 'topic'", 0))

        conn = self._conn()
        c = conn.cursor()
        result = {"question": f"What about {topic}?", "searches": {}}

        # Search domains
        c.execute("SELECT domain, class_name, description FROM classes WHERE is_vbstyle=1 AND (domain LIKE ? OR class_name LIKE ? OR description LIKE ?)",
                  (f"%{topic}%", f"%{topic}%", f"%{topic}%"))
        domains = [{"domain": r[0], "class": r[1], "description": r[2]} for r in c.fetchall()]
        result["searches"]["domains"] = domains

        # Search methods
        c.execute("""
            SELECT cl.class_name, cl.domain, m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle=1 AND m.method_name LIKE ?
            LIMIT 20
        """, (f"%{topic}%",))
        methods = [{"class": r[0], "domain": r[1], "method": r[2]} for r in c.fetchall()]
        result["searches"]["methods"] = methods

        # Search plans
        c.execute("SELECT name, goal, description FROM plans WHERE name LIKE ? OR goal LIKE ? OR description LIKE ?",
                  (f"%{topic}%", f"%{topic}%", f"%{topic}%"))
        plans = [{"name": r[0], "goal": r[1], "description": r[2]} for r in c.fetchall()]
        result["searches"]["plans"] = plans

        # Search code (FTS5)
        try:
            c.execute("SELECT DISTINCT class_name, method_name FROM search_idx WHERE search_idx MATCH ? LIMIT 10", (topic,))
            code_hits = [{"class": r[0], "method": r[1]} for r in c.fetchall()]
            result["searches"]["code"] = code_hits
        except:
            result["searches"]["code"] = []

        # Compose answer
        total = sum(len(v) for v in result["searches"].values())
        if total == 0:
            result["answer"] = f"I don't know about '{topic}'. I searched domains, methods, plans, and code — nothing matched."
        else:
            parts = []
            if domains:
                parts.append(f"I found {len(domains)} domain(s): {', '.join(d['domain'] for d in domains[:5])}")
            if methods:
                parts.append(f"{len(methods)} method(s) match: {', '.join(m['method'] for m in methods[:5])}")
            if plans:
                parts.append(f"{len(plans)} plan(s) match: {', '.join(p['name'] for p in plans)}")
            if result["searches"].get("code"):
                parts.append(f"Found in code: {', '.join(c['class'] + '.' + c['method'] for c in result['searches']['code'][:5])}")
            result["answer"] = f"Here's what I know about '{topic}': " + ". ".join(parts) + "."

        conn.close()
        return (1, result, None)

    def CanYouBuild(self, params):
        """
        'Can you build a GUI?' / 'Can you build a search engine?'
        Checks if the ingredients exist to build a system, returns coverage.
        """
        system = params.get("system", "").lower()
        if not system:
            return (0, None, ("MISSING_PARAM", "Provide 'system' (e.g. 'gui', 'search engine', 'chat system')", 0))

        # Map system names to required domains
        system_map = {
            "gui": ["gui"],
            "search engine": ["search", "index", "text", "transform"],
            "code generator": ["ai", "parse", "bytecode", "codegraph", "transform", "testing"],
            "chat system": ["ai", "qa", "search", "knowledge", "memory", "text", "gui", "messaging", "network"],
            "ai repair loop": ["testing", "bytecode", "parse", "runtime", "errorhandling", "rescue", "ai", "knowledge", "orchestration"],
            "database gui": ["db", "db_inv", "gui", "storage", "config"],
            "build system": ["parse", "codegraph", "style", "validate", "package", "testing"],
            "monitoring system": ["observability", "logging", "system", "network"],
            "backup system": ["rescue", "storage", "db", "archive", "compression", "schedule"],
            "security system": ["security", "cryptography", "audit", "governance"],
            "documentation system": ["documentation", "parse", "text", "convert", "knowledge"],
            "deployment pipeline": ["deployment", "testing", "validate", "config", "orchestration", "runtime"],
            "knowledge graph": ["knowledge", "graph", "text", "ai", "search", "transform"],
            "data pipeline": ["ingest", "transform", "validate", "storage", "db", "analytics"],
            "api server": ["network", "http", "security", "validate", "transform", "config"],
            "file manager": ["fileops", "folder", "io", "archive", "compression", "gui"],
        }

        # Also try partial match
        needed = None
        for key, domains in system_map.items():
            if key in system or system in key:
                needed = domains
                break
        if not needed:
            # Try to infer from the word itself
            for key, domains in system_map.items():
                if any(word in system for word in key.split()):
                    needed = domains
                    break
        if not needed:
            return (0, None, ("UNKNOWN_SYSTEM", f"I don't know what domains '{system}' needs. Try: {', '.join(system_map.keys())}", 0))

        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle=1")
        have = {r[0] for r in c.fetchall()}

        have_domains = [d for d in needed if d in have]
        missing = [d for d in needed if d not in have]
        coverage = len(have_domains) / len(needed) * 100 if needed else 0

        # Get class details for what we have
        have_details = []
        for d in have_domains:
            c.execute("SELECT class_name, description FROM classes WHERE is_vbstyle=1 AND domain=?", (d,))
            row = c.fetchone()
            if row:
                c2 = conn.cursor()
                c2.execute("SELECT COUNT(*) FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.domain=? AND m.method_name NOT LIKE '\\_%'", (d,))
                mc = c2.fetchone()[0]
                have_details.append({"domain": d, "class": row[0], "description": row[1], "methods": mc})

        missing_details = [{"domain": d, "note": f"No {d} domain exists yet"} for d in missing]

        answer = {
            "question": f"Can you build a {system}?",
            "answer": f"{'Yes.' if not missing else f'Partially. {coverage:.0f}% of the ingredients exist.'}",
            "buildable": len(missing) == 0,
            "coverage_pct": round(coverage, 1),
            "domains_needed": needed,
            "domains_have": have_details,
            "domains_missing": missing_details,
            "summary": self._summarize_buildable(system, have_details, missing),
        }

        conn.close()
        return (1, answer, None)

    def _summarize_buildable(self, system, have, missing):
        """Compose a being-like answer about buildability."""
        if not missing:
            return f"Yes, I can build a {system}. I have all the ingredients: {', '.join(h['domain'] for h in have)}. " + \
                   f"The largest domain is {max(have, key=lambda x: x['methods'])['class']} with {max(have, key=lambda x: x['methods'])['methods']} methods. " + \
                   "Write a plan that orchestrates these domains and I can execute it."
        else:
            return f"Partially. I have {len(have)} of {len(have) + len(missing)} ingredients for a {system}. " + \
                   f"I'm missing: {', '.join(m['domain'] for m in missing)}. " + \
                   f"Build those domains first, then I can compose them into a {system}."

    def WhatAreYou(self, params):
        """
        'What are you?' — the database describes itself as an entity.
        """
        ok, meta, err = self.WhatExists({})
        if not ok:
            return (0, None, err)

        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT value FROM _db_meta WHERE key='db_purpose'")
        purpose = c.fetchone()[0]
        c.execute("SELECT value FROM _db_meta WHERE key='architecture'")
        architecture = c.fetchone()[0]
        c.execute("SELECT value FROM _db_meta WHERE key='cooking_analogy'")
        analogy = c.fetchone()[0]
        c.execute("SELECT value FROM _db_meta WHERE key='vbstyle_rules'")
        rules = c.fetchone()[0]
        conn.close()

        answer = {
            "question": "What are you?",
            "answer": f"I am {meta['vbstyle_domains']} VBStyle domains living in a database. " +
                      f"I contain {meta['total_classes']} classes, {meta['total_methods']} methods, " +
                      f"{meta['plans']} plan(s), and {meta['pipelines']} pipeline(s). " +
                      f"I am not an application — I am a pantry of capabilities. " +
                      f"Plans compose my ingredients into recipes. Orchestration executes the recipes. " +
                      f"You can ask me what I have, what I can do, what I'm missing, and what I could become.",
            "identity": {
                "name": "v20_hybrid_best",
                "purpose": purpose,
                "architecture": architecture,
                "analogy": analogy,
                "rules": rules,
            },
            "scale": meta,
            "self_awareness": {
                "knows_what_it_is": True,
                "knows_what_it_has": True,
                "knows_what_its_missing": True,
                "knows_what_it_could_become": True,
                "can_be_interrogated": True,
                "documents_itself": True,
            },
        }
        return (1, answer, None)

    # ════════════════════════════════════════════════════════════════════════
    # BCL IDENTITY — self-describing entities in Bracket Command Language
    # Every domain, class, method, and CU has a BCL token that says:
    #   "I am X. I do Y. My capabilities are Z."
    # Format: [@name]{("key";"value")...(weight)}
    # ════════════════════════════════════════════════════════════════════════

    def WhoAreYouBCL(self, params):
        """
        'Who are you?' — returns the BCL identity token for an entity.
        params: {"name": "DomAi"} or {"domain": "ai"} or {"class_name": "DomAi"}
        """
        name = params.get("name", params.get("class_name", ""))
        domain = params.get("domain", "")

        conn = self._conn()
        c = conn.cursor()

        if name:
            # Search by entity name
            c.execute("""
                SELECT entity_type, entity_id, entity_name, domain, bcl_token, self_narrative
                FROM bcl_identity WHERE entity_name=? ORDER BY entity_type
            """, (name,))
        elif domain:
            # Search by domain — return the domain-level BCL token
            c.execute("""
                SELECT entity_type, entity_id, entity_name, domain, bcl_token, self_narrative
                FROM bcl_identity WHERE entity_type='domain' AND domain=? ORDER BY entity_name
            """, (domain,))
        else:
            conn.close()
            return (0, None, ("MISSING_PARAM", "Provide 'name' or 'domain'", 0))

        rows = c.fetchall()
        if not rows:
            conn.close()
            return (0, None, ("NOT_FOUND", f"No BCL identity found for '{name or domain}'", 0))

        results = []
        for r in rows:
            results.append({
                "entity_type": r[0],
                "entity_id": r[1],
                "entity_name": r[2],
                "domain": r[3],
                "bcl_token": r[4],
                "self_narrative": r[5],
            })

        conn.close()
        return (1, results[0] if len(results) == 1 else results, None)

    def BclIdentity(self, params):
        """
        Get BCL identity token(s) by type.
        params: {"type": "domain"} or {"type": "class"} or {"type": "method"} or {"type": "cu"}
        """
        entity_type = params.get("type", "")
        if not entity_type:
            return (0, None, ("MISSING_PARAM", "Provide 'type' (domain, class, method, cu)", 0))

        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT entity_type, entity_id, entity_name, domain, bcl_token, self_narrative
            FROM bcl_identity WHERE entity_type=? ORDER BY domain, entity_name
        """, (entity_type,))
        rows = c.fetchall()

        if not rows:
            conn.close()
            return (0, None, ("NOT_FOUND", f"No BCL identities of type '{entity_type}'", 0))

        results = []
        for r in rows:
            results.append({
                "entity_type": r[0],
                "entity_id": r[1],
                "entity_name": r[2],
                "domain": r[3],
                "bcl_token": r[4],
                "self_narrative": r[5],
            })

        conn.close()
        return (1, results, None)

    def BclSearch(self, params):
        """
        Search BCL identity tokens by keyword.
        params: {"keyword": "compress"} — searches entity_name and bcl_token
        """
        keyword = params.get("keyword", "")
        if not keyword:
            return (0, None, ("MISSING_PARAM", "Provide 'keyword'", 0))

        conn = self._conn()
        c = conn.cursor()
        like_pattern = f"%{keyword}%"
        c.execute("""
            SELECT entity_type, entity_id, entity_name, domain, bcl_token, self_narrative
            FROM bcl_identity
            WHERE entity_name LIKE ? OR bcl_token LIKE ? OR self_narrative LIKE ?
            ORDER BY entity_type, domain, entity_name LIMIT 50
        """, (like_pattern, like_pattern, like_pattern))
        rows = c.fetchall()

        if not rows:
            conn.close()
            return (1, [], None)

        results = []
        for r in rows:
            results.append({
                "entity_type": r[0],
                "entity_id": r[1],
                "entity_name": r[2],
                "domain": r[3],
                "bcl_token": r[4],
                "self_narrative": r[5],
            })

        conn.close()
        return (1, results, None)

    # ════════════════════════════════════════════════════════════════════════
    # META QUESTIONS — who are you?
    # ════════════════════════════════════════════════════════════════════════

    def WhoAreYou(self, params):
        """Who are you? What is this database?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT key, value FROM _db_meta")
        meta = {r[0]: r[1] for r in c.fetchall()}
        conn.close()
        return (1, meta, None)

    def WhatTables(self, params):
        """What tables exist and what do they do?"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT table_name, layer, purpose, key_columns, notes FROM _table_registry ORDER BY layer, table_name")
        tables = [{"table": r[0], "layer": r[1], "purpose": r[2], "keys": r[3], "notes": r[4]} for r in c.fetchall()]
        conn.close()
        return (1, tables, None)

    def Help(self, params):
        """What questions can I ask?"""
        questions = {
            "capability": [
                "what_exists", "what_domains", "what_can_domain_do {domain}",
                "what_methods_exist {pattern?}", "what_capabilities", "what_computational_units"
            ],
            "gap": [
                "what_is_missing", "which_classes_no_methods", "which_methods_no_callers",
                "which_plans_cannot_execute", "which_recipes_reference_missing", "what_violations"
            ],
            "dependency": [
                "what_depends_on {class_name}", "what_breaks_if_removed {class_name}",
                "most_depended_on", "circular_dependencies"
            ],
            "lifecycle": [
                "lifecycle_of {class_name|domain}", "what_lifecycle_stages_missing"
            ],
            "error": [
                "where_can_fail", "what_failures_occurred", "what_repairs_exist",
                "which_failures_no_repair"
            ],
            "orchestration": [
                "who_calls_this {class_name}", "what_does_this_call {class_name}",
                "what_execution_chains", "what_recipes_use {class_name}"
            ],
            "plan": [
                "what_plans_exist", "what_plan_goals", "which_plans_succeeded",
                "which_plans_failed", "which_plans_similar {plan_name}",
                "which_plans_promoted", "what_plan_produces {plan_name}"
            ],
            "composition": [
                "i_need {capability}", "what_can_compose"
            ],
            "coverage": [
                "what_is_not_covered", "what_has_no_owner",
                "what_has_no_lifecycle", "what_has_no_test_path"
            ],
            "stability": [
                "what_is_stable_core", "what_is_fragile", "what_is_frequently_changed"
            ],
            "emergence": [
                "what_systems_emerge", "what_hidden_capabilities",
                "what_is_possible_but_undeclared"
            ],
            "w_questions (natural language)": [
                "ask {question: 'what exists?'}",
                "ask {question: 'what if I need compress?'}",
                "ask {question: 'what breaks if I remove DomAi?'}",
                "ask {question: 'who calls DomTesting?'}",
                "ask {question: 'what systems emerge?'}",
                "ask {question: 'where can fail?'}",
            ],
            "conversational (being-like)": [
                "do_you_have {capability} — multi-layer capability check",
                "how_does_work {class_name|domain} — explain like a being would",
                "what_about {topic} — search everything for a topic",
                "can_you_build {system} — check if ingredients exist",
                "what_are_you — the database describes itself",
            ],
            "bcl_identity (self-describing entities)": [
                "who_are_you_bcl {name|domain} — get BCL identity token for an entity",
                "bcl_identity {type: domain|class|method|cu} — list all BCL tokens of a type",
                "bcl_search {keyword} — search BCL tokens by keyword",
            ],
            "meta": [
                "who_are_you", "what_tables", "help"
            ],
        }
        return (1, questions, None)


if __name__ == "__main__":
    # Quick self-test
    db = DbInterrogator()
    print("=== WHO ARE YOU ===")
    ok, data, err = db.Run("who_are_you", {})
    if ok:
        for k, v in data.items():
            print(f"  {k}: {v[:80]}...")

    print("\n=== WHAT EXISTS ===")
    ok, data, err = db.Run("what_exists", {})
    if ok:
        for k, v in data.items():
            print(f"  {k}: {v}")

    print("\n=== I NEED 'compress' ===")
    ok, data, err = db.Run("i_need", {"capability": "compress"})
    if ok:
        print(f"  Exact matches: {len(data['exact_matches'])}")
        for m in data["exact_matches"]:
            print(f"    {m['class']}.{m['method']} ({m['domain']})")
        print(f"  Related: {len(data['related'])}")
        for m in data["related"][:5]:
            print(f"    {m['class']}.{m['method']} ({m['domain']})")
        print(f"  Substitutes: {len(data['substitutes'])}")
        for s in data["substitutes"][:5]:
            print(f"    {s['class']} ({s['domain']})")
        print(f"  Existing compositions: {len(data['existing_compositions'])}")
        for c in data["existing_compositions"]:
            print(f"    {c['plan']}: {c['goal']}")

    print("\n=== WHAT PLANS EXIST ===")
    ok, data, err = db.Run("what_plans_exist", {})
    if ok:
        for p in data:
            print(f"  {p['name']} [{p['status']}] steps={p['steps']} ingredients={p['ingredients']}")

    print("\n=== WHAT IS MISSING ===")
    ok, data, err = db.Run("what_is_missing", {})
    if ok:
        for g in data:
            print(f"  [{g.get('kind')}] {g}")

    print("\n=== HELP ===")
    ok, data, err = db.Run("help", {})
    if ok:
        for category, questions in data.items():
            print(f"  {category}:")
            for q in questions:
                print(f"    {q}")
