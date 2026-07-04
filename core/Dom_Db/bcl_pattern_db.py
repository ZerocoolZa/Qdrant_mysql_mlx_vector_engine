#!/usr/bin/env python3
#[@GHOST]{[@file<bcl_pattern_db.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<bcl_pattern_db>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
#[@SUMMARY]{MySQL integration for storing BCL pattern violations and repairs in vb_shared}


class BclPatternDb:
    """MySQL integration for storing BCL pattern violations and repairs.

    Stores non-canonical patterns in vb_shared.know_problems and repair
    rules in vb_shared.learned_rules. All access via Run() dispatch.
    """

    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DATABASE = "vb_shared"
    CATEGORY_VIOLATION = "bcl_violation"
    CATEGORY_REPAIR = "bcl_repair"
    DEFAULT_CONFIDENCE = 0.8

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "host": self.MYSQL_HOST,
                "port": self.MYSQL_PORT,
                "user": self.MYSQL_USER,
                "password": self.MYSQL_PASSWORD,
                "database": self.MYSQL_DATABASE,
            },
            "results": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "store_violations":
            return self.StoreViolations(params)
        elif command == "store_repair":
            return self.StoreRepair(params)
        elif command == "query_violations":
            return self.QueryViolations(params)
        elif command == "query_repairs":
            return self.QueryRepairs(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        elif command == "close":
            return self.Close()
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
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def Connect(self):
        """Open a new MySQL connection using config values."""
        try:
            import mysql.connector
        except ImportError:
            return (0, None, ("NO_MYSQL_MODULE", "mysql.connector not installed", 0))
        cfg = self.state["config"]
        try:
            conn = mysql.connector.connect(
                host=cfg.get("host", self.MYSQL_HOST),
                port=cfg.get("port", self.MYSQL_PORT),
                user=cfg.get("user", self.MYSQL_USER),
                password=cfg.get("password", self.MYSQL_PASSWORD),
                database=cfg.get("database", self.MYSQL_DATABASE),
            )
            return (1, conn, None)
        except Exception as exc:
            return (0, None, ("DB_CONNECT_FAILED", str(exc), 0))

    def ResolveCategoryId(self, conn, name):
        """Find or create a category row by name, return its id."""
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
            row = cur.fetchone()
            if row:
                cur.close()
                return (1, row[0], None)
            cur.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (name, name))
            conn.commit()
            cat_id = cur.lastrowid
            cur.close()
            return (1, cat_id, None)
        except Exception as exc:
            return (0, None, ("CATEGORY_RESOLVE_FAILED", str(exc), 0))

    def StoreViolations(self, params):
        """Store each non-canonical pattern as a row in know_problems."""
        patterns = self._p(params, "patterns", {})
        canonical = self._p(params, "canonical", "")
        if not patterns:
            return (0, None, ("NO_PATTERNS", "patterns param is required", 0))

        ok, conn, err = self.Connect()
        if not ok:
            return (0, None, err)

        try:
            ok_cat, cat_id, err_cat = self.ResolveCategoryId(conn, self.CATEGORY_VIOLATION)
            if not ok_cat:
                return (0, None, err_cat)

            cur = conn.cursor()
            stored = []
            for pattern_name, examples in patterns.items():
                if pattern_name == canonical:
                    continue
                desc_parts = []
                desc_parts.append("category=" + self.CATEGORY_VIOLATION)
                desc_parts.append("canonical=" + str(canonical))
                if isinstance(examples, list) and examples:
                    files = set()
                    for ex in examples:
                        if isinstance(ex, dict) and "file" in ex:
                            files.add(ex["file"])
                    desc_parts.append("files=" + ",".join(sorted(files)[:10]))
                    desc_parts.append("example_count=" + str(len(examples)))
                    first = examples[0]
                    if isinstance(first, dict) and "text" in first:
                        desc_parts.append("sample=" + str(first["text"])[:120])
                description = "; ".join(desc_parts)
                cur.execute(
                    "INSERT INTO know_problems (problem, description, category_id) VALUES (%s, %s, %s)",
                    (pattern_name, description, cat_id),
                )
                stored.append({"pattern": pattern_name, "row_id": cur.lastrowid})
            conn.commit()
            cur.close()
            self.state["results"]["stored_violations"] = stored
            return (1, {"stored": stored, "count": len(stored)}, None)
        except Exception as exc:
            return (0, None, ("STORE_VIOLATIONS_FAILED", str(exc), 0))
        finally:
            conn.close()

    def StoreRepair(self, params):
        """Store each repair as a learned_rule in learned_rules."""
        changes = self._p(params, "changes", [])
        if not changes:
            return (0, None, ("NO_CHANGES", "changes param is required", 0))

        ok, conn, err = self.Connect()
        if not ok:
            return (0, None, err)

        try:
            cur = conn.cursor()
            stored = []
            for change in changes:
                if not isinstance(change, dict):
                    continue
                pattern = change.get("pattern", "")
                fix_action = change.get("fix_action", change.get("fix", ""))
                confidence = change.get("confidence", self.DEFAULT_CONFIDENCE)
                if not pattern or not fix_action:
                    continue
                cur.execute(
                    "INSERT INTO learned_rules (pattern, fix_action, confidence, category) "
                    "VALUES (%s, %s, %s, %s)",
                    (pattern, fix_action, confidence, self.CATEGORY_REPAIR),
                )
                stored.append({"pattern": pattern, "row_id": cur.lastrowid})
            conn.commit()
            cur.close()
            self.state["results"]["stored_repairs"] = stored
            return (1, {"stored": stored, "count": len(stored)}, None)
        except Exception as exc:
            return (0, None, ("STORE_REPAIR_FAILED", str(exc), 0))
        finally:
            conn.close()

    def QueryViolations(self, params):
        """Query know_problems for bcl_violation entries, optionally filtered by pattern."""
        pattern_filter = self._p(params, "pattern", None)

        ok, conn, err = self.Connect()
        if not ok:
            return (0, None, err)

        try:
            cur = conn.cursor(dictionary=True)
            if pattern_filter:
                cur.execute(
                    "SELECT kp.id, kp.problem, kp.description, kp.created_at "
                    "FROM know_problems kp "
                    "JOIN categories c ON kp.category_id = c.id "
                    "WHERE c.name = %s AND kp.problem = %s "
                    "ORDER BY kp.id DESC",
                    (self.CATEGORY_VIOLATION, pattern_filter),
                )
            else:
                cur.execute(
                    "SELECT kp.id, kp.problem, kp.description, kp.created_at "
                    "FROM know_problems kp "
                    "JOIN categories c ON kp.category_id = c.id "
                    "WHERE c.name = %s "
                    "ORDER BY kp.id DESC",
                    (self.CATEGORY_VIOLATION,),
                )
            rows = cur.fetchall()
            cur.close()
            return (1, {"violations": rows, "count": len(rows)}, None)
        except Exception as exc:
            return (0, None, ("QUERY_VIOLATIONS_FAILED", str(exc), 0))
        finally:
            conn.close()

    def QueryRepairs(self, params):
        """Query learned_rules for bcl_repair entries, optionally filtered by pattern."""
        pattern_filter = self._p(params, "pattern", None)

        ok, conn, err = self.Connect()
        if not ok:
            return (0, None, err)

        try:
            cur = conn.cursor(dictionary=True)
            if pattern_filter:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, category, success_count, "
                    "failure_count, created_at, last_used "
                    "FROM learned_rules "
                    "WHERE category = %s AND pattern = %s "
                    "ORDER BY confidence DESC, id DESC",
                    (self.CATEGORY_REPAIR, pattern_filter),
                )
            else:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, category, success_count, "
                    "failure_count, created_at, last_used "
                    "FROM learned_rules "
                    "WHERE category = %s "
                    "ORDER BY confidence DESC, id DESC",
                    (self.CATEGORY_REPAIR,),
                )
            rows = cur.fetchall()
            cur.close()
            return (1, {"repairs": rows, "count": len(rows)}, None)
        except Exception as exc:
            return (0, None, ("QUERY_REPAIRS_FAILED", str(exc), 0))
        finally:
            conn.close()
