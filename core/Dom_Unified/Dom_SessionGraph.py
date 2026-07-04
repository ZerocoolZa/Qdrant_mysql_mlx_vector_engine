# [@GHOST]{[@file<Dom_SessionGraph.py>][@domain<Dom_Unified>][@role<session_path_tracking>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<session_path_tracking>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{DomSessionGraph — compass for AI sessions. Tracks main thread, side paths, distractions, completions, and resume points. Prevents getting lost at sea.}
# [@CLASS]{DomSessionGraph}
# [@METHOD]{Run,open_session,add_path,update_path,add_resume_point,get_resume_point,render_graph,get_dashboard,close_session}

"""
DomSessionGraph — session path tracking and navigation.

WHAT IT DOES:
  1. OPEN      — start a new session graph with a main thread
  2. ADD_PATH  — record a path (MAIN, SIDE, DEAD_END, RESOLVED)
  3. UPDATE    — update path status and progress
  4. RESUME    — record where to resume a project
  5. RENDER    — generate ASCII graph showing the full session path
  6. DASHBOARD — show all projects with progress bars
  7. CLOSE     — finalize a session

WHY IT EXISTS:
  Without a compass, a ship is lost at sea.
  Without a session graph, an AI session gets distracted and forgets the main thread.
  This is the compass. This is the navigation system.

USAGE:
  from Dom_Unified.Dom_SessionGraph import DomSessionGraph

  sg = DomSessionGraph()

  # Open a session
  ok, data, err = sg.Run("open", {"session_id": "2026-06-28", "main_thread": "Dom_Mcp Migration"})

  # Add a side path (distraction)
  ok, data, err = sg.Run("add_path", {"session_id": "2026-06-28", "path_type": "SIDE", "path_name": "GPU Hashing Debate", "trigger": "User challenged CPU-only claim", "was_worth_it": "YES"})

  # Update progress
  ok, data, err = sg.Run("update_path", {"session_id": "2026-06-28", "path_name": "Dom_Mcp Migration", "path_status": "IN_PROGRESS", "progress": 25})

  # Set resume point
  ok, data, err = sg.Run("add_resume", {"session_id": "2026-06-28", "project_name": "Dom_Mcp Migration", "progress": 25, "state": "STALLED", "resume_action": "Dispatch indexing agents, consolidate, present move plan"})

  # Get resume point (for next session)
  ok, data, err = sg.Run("get_resume", {"project_name": "Dom_Mcp Migration"})

  # Render ASCII graph
  ok, graph, err = sg.Run("render", {"session_id": "2026-06-28"})

  # Get dashboard (all projects)
  ok, dashboard, err = sg.Run("dashboard", {})
"""

import datetime
import json
import mysql.connector

try:
    from .Config import SESSION_GRAPH_MYSQL_HOST, SESSION_GRAPH_MYSQL_USER, SESSION_GRAPH_MYSQL_PASS, SESSION_GRAPH_MYSQL_DB, SESSION_GRAPH_BAR_LENGTH
except ImportError:
    from Config import SESSION_GRAPH_MYSQL_HOST, SESSION_GRAPH_MYSQL_USER, SESSION_GRAPH_MYSQL_PASS, SESSION_GRAPH_MYSQL_DB, SESSION_GRAPH_BAR_LENGTH


class DomSessionGraph:
    """
    Session path tracking and navigation authority.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": param.get("db_host", SESSION_GRAPH_MYSQL_HOST) if param else SESSION_GRAPH_MYSQL_HOST,
                "db_user": param.get("db_user", SESSION_GRAPH_MYSQL_USER) if param else SESSION_GRAPH_MYSQL_USER,
                "db_pass": param.get("db_pass", SESSION_GRAPH_MYSQL_PASS) if param else SESSION_GRAPH_MYSQL_PASS,
                "db_name": param.get("db_name", SESSION_GRAPH_MYSQL_DB) if param else SESSION_GRAPH_MYSQL_DB,
                "bar_length": param.get("bar_length", SESSION_GRAPH_BAR_LENGTH) if param else SESSION_GRAPH_BAR_LENGTH,
            },
            "current_session": None,
            "stats": {"sessions_opened": 0, "paths_added": 0, "resume_points": 0, "renders": 0},
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
            host=cfg["db_host"],
            user=cfg["db_user"],
            password=cfg.get("db_pass", ""),
            database=cfg["db_name"],
        )

    def Run(self, command, params=None):
        dispatch = {
            "open": self._cmd_open,
            "add_path": self._cmd_add_path,
            "update_path": self._cmd_update_path,
            "add_resume": self._cmd_add_resume,
            "get_resume": self._cmd_get_resume,
            "render": self._cmd_render,
            "dashboard": self._cmd_dashboard,
            "close": self._cmd_close,
            "list_sessions": self._cmd_list_sessions,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
        return handler(params or {})

    def _cmd_open(self, params):
        session_id = self._p(params, "session_id")
        main_thread = self._p(params, "main_thread")
        if not session_id or not main_thread:
            return (0, None, ("MISSING_PARAM", "session_id and main_thread required", 0))
        session_date = self._p(params, "session_date", datetime.date.today().isoformat())
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO session_graphs (session_id, session_date, main_thread, main_status, main_progress) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE main_thread=%s, updated_at=NOW()",
                (session_id, session_date, main_thread, "IN_PROGRESS", 0, main_thread),
            )
            conn.commit()
            cur.execute(
                "INSERT INTO session_paths (session_id, path_type, path_name, path_status, progress, sort_order) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE path_status=%s",
                (session_id, "MAIN", main_thread, "IN_PROGRESS", 0, 0, "IN_PROGRESS"),
            )
            conn.commit()
            self.state["current_session"] = session_id
            self.state["stats"]["sessions_opened"] += 1
            return (1, {"session_id": session_id, "main_thread": main_thread, "status": "IN_PROGRESS"}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_add_path(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        path_type = self._p(params, "path_type")
        path_name = self._p(params, "path_name")
        if not session_id or not path_type or not path_name:
            return (0, None, ("MISSING_PARAM", "session_id, path_type, path_name required", 0))
        path_status = self._p(params, "path_status", "IN_PROGRESS")
        progress = self._p(params, "progress", 0)
        trigger = self._p(params, "trigger")
        time_cost = self._p(params, "time_cost_min", 0)
        worth_it = self._p(params, "was_worth_it", "UNKNOWN")
        parent = self._p(params, "parent_path")
        sort_order = self._p(params, "sort_order", 99)
        notes = self._p(params, "notes")
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO session_paths (session_id, path_type, path_name, path_status, progress, trigger_reason, time_cost_min, was_worth_it, parent_path, sort_order, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (session_id, path_type, path_name, path_status, progress, trigger, time_cost, worth_it, parent, sort_order, notes),
            )
            conn.commit()
            self.state["stats"]["paths_added"] += 1
            return (1, {"path_id": cur.lastrowid, "path_name": path_name, "path_type": path_type, "path_status": path_status}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_update_path(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        path_name = self._p(params, "path_name")
        if not session_id or not path_name:
            return (0, None, ("MISSING_PARAM", "session_id and path_name required", 0))
        path_status = self._p(params, "path_status")
        progress = self._p(params, "progress")
        worth_it = self._p(params, "was_worth_it")
        notes = self._p(params, "notes")
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            sets = []
            vals = []
            if path_status:
                sets.append("path_status=%s")
                vals.append(path_status)
            if progress is not None:
                sets.append("progress=%s")
                vals.append(progress)
            if worth_it:
                sets.append("was_worth_it=%s")
                vals.append(worth_it)
            if notes:
                sets.append("notes=%s")
                vals.append(notes)
            if not sets:
                return (0, None, ("NO_UPDATE", "No fields to update", 0))
            vals.append(session_id)
            vals.append(path_name)
            cur.execute(
                f"UPDATE session_paths SET {', '.join(sets)} WHERE session_id=%s AND path_name=%s",
                vals,
            )
            conn.commit()
            if cur.rowcount == 0:
                return (0, None, ("NOT_FOUND", f"Path not found: {path_name}", 0))
            return (1, {"path_name": path_name, "updated": True}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_add_resume(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        project_name = self._p(params, "project_name")
        resume_action = self._p(params, "resume_action")
        if not session_id or not project_name or not resume_action:
            return (0, None, ("MISSING_PARAM", "session_id, project_name, resume_action required", 0))
        progress = self._p(params, "progress", 0)
        state_val = self._p(params, "state", "STALLED")
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO session_resume_points (session_id, project_name, progress, state, resume_action, is_active) VALUES (%s, %s, %s, %s, %s, 1) ON DUPLICATE KEY UPDATE progress=%s, state=%s, resume_action=%s, is_active=1, updated_at=NOW()",
                (session_id, project_name, progress, state_val, resume_action, progress, state_val, resume_action),
            )
            conn.commit()
            self.state["stats"]["resume_points"] += 1
            return (1, {"project_name": project_name, "progress": progress, "state": state_val, "resume_action": resume_action}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_get_resume(self, params):
        project_name = self._p(params, "project_name")
        if not project_name:
            return (0, None, ("MISSING_PARAM", "project_name required", 0))
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT * FROM session_resume_points WHERE project_name=%s AND is_active=1 ORDER BY updated_at DESC LIMIT 1",
                (project_name,),
            )
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", f"No resume point for: {project_name}", 0))
            return (1, row, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_render(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        if not session_id:
            return (0, None, ("MISSING_PARAM", "session_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM session_graphs WHERE session_id=%s", (session_id,))
            graph = cur.fetchone()
            if not graph:
                return (0, None, ("NOT_FOUND", f"Session not found: {session_id}", 0))
            cur.execute(
                "SELECT * FROM session_paths WHERE session_id=%s ORDER BY sort_order, id",
                (session_id,),
            )
            paths = cur.fetchall()
            cur.execute(
                "SELECT * FROM session_resume_points WHERE session_id=%s AND is_active=1 ORDER BY project_name",
                (session_id,),
            )
            resumes = cur.fetchall()
            lines = []
            lines.append(f"SESSION: {session_id} — {graph['main_thread']}")
            lines.append("")
            for path in paths:
                ptype = path["path_type"]
                pname = path["path_name"]
                pstatus = path["path_status"]
                progress = path["progress"] or 0
                bar_len = self.state["config"].get("bar_length", 40)
                filled = int(progress / 100 * bar_len)
                bar = "#" * filled + "." * (bar_len - filled)
                pct = f"{progress}%"
                lines.append(f"  [{ptype}] {pname}")
                lines.append(f"    [{bar}] {pct} {pstatus}")
                if path["trigger_reason"]:
                    lines.append(f"    trigger: {path['trigger_reason']}")
                if path["was_worth_it"] and path["was_worth_it"] != "UNKNOWN":
                    lines.append(f"    worth it: {path['was_worth_it']}")
                if path["notes"]:
                    lines.append(f"    notes: {path['notes']}")
                lines.append("")
            if resumes:
                lines.append("RESUME POINTS:")
                for r in resumes:
                    lines.append(f"  {r['project_name']} ({r['progress']}%, {r['state']})")
                    lines.append(f"    -> {r['resume_action']}")
                    lines.append("")
            self.state["stats"]["renders"] += 1
            return (1, "\n".join(lines), None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_dashboard(self, params):
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT project_name, progress, state, resume_action, updated_at FROM session_resume_points WHERE is_active=1 ORDER BY project_name"
            )
            rows = cur.fetchall()
            if not rows:
                return (1, "No active projects tracked.", None)
            lines = []
            lines.append("PROJECT DASHBOARD")
            lines.append("=" * 60)
            for row in rows:
                progress = row["progress"] or 0
                bar_len = self.state["config"].get("bar_length", 40)
                filled = int(progress / 100 * bar_len)
                bar = "#" * filled + "." * (bar_len - filled)
                lines.append(f"  {row['project_name']}")
                lines.append(f"    [{bar}] {progress}% {row['state']}")
                lines.append(f"    resume: {row['resume_action']}")
                lines.append("")
            return (1, "\n".join(lines), None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_close(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        if not session_id:
            return (0, None, ("MISSING_PARAM", "session_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE session_graphs SET main_status='CLOSED', updated_at=NOW() WHERE session_id=%s",
                (session_id,),
            )
            conn.commit()
            self.state["current_session"] = None
            return (1, {"session_id": session_id, "status": "CLOSED"}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def _cmd_list_sessions(self, params):
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT session_id, session_date, main_thread, main_status, main_progress FROM session_graphs ORDER BY session_date DESC LIMIT 20"
            )
            rows = cur.fetchall()
            return (1, rows, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        finally:
            cur.close()
            if not self.state.get("db_conn"):
                conn.close()

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "current_session": self.state.get("current_session"),
            "stats": dict(self.state["stats"]),
        }

    def set_config(self, key, value):
        if key in self.state["config"]:
            self.state["config"][key] = value
            return (1, {"key": key, "value": value}, None)
        return (0, None, ("UNKNOWN_KEY", f"Unknown config key: {key}", 0))
