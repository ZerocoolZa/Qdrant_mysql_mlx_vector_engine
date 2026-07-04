class DomDbInv:
    """Database introspection domain: schema discovery for tables, columns, indexes, constraints, and relations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))
                schema = param.get("schema")
                if schema is not None:
                    self.state["catalog"] = list(schema)
            elif isinstance(param, list):
                self.state["catalog"] = list(param)

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "columns": self.columns,
            "constraints": self.constraints,
            "foreign_keys": self.foreign_keys,
            "functions": self.functions,
            "indexes": self.indexes,
            "introspect": self.introspect,
            "relationships": self.relationships,
            "report": self.report,
            "stored_procs": self.stored_procs,
            "tables": self.tables,
            "triggers": self.triggers,
            "views": self.views,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _schema(self, params):
        schema = params.get("schema")
        if schema is None:
            schema = self.state.get("catalog", [])
        return schema

    def columns(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    if table is None or t.get("name") == table:
                        for col in t.get("columns", []):
                            out.append(col)
            result = {"domain": "db_inv", "method": "columns", "data": {"columns": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COLUMNS_ERROR", str(e), 0))

    def constraints(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    if table is None or t.get("name") == table:
                        for c in t.get("constraints", []):
                            out.append(c)
            result = {"domain": "db_inv", "method": "constraints", "data": {"constraints": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONSTRAINTS_ERROR", str(e), 0))

    def foreign_keys(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    for c in t.get("constraints", []):
                        if isinstance(c, dict) and c.get("type") == "foreign_key":
                            out.append(c)
            result = {"domain": "db_inv", "method": "foreign_keys", "data": {"foreign_keys": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FOREIGN_KEYS_ERROR", str(e), 0))

    def functions(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    for fn in t.get("functions", []):
                        out.append(fn)
            result = {"domain": "db_inv", "method": "functions", "data": {"functions": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FUNCTIONS_ERROR", str(e), 0))

    def indexes(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    if table is None or t.get("name") == table:
                        for idx in t.get("indexes", []):
                            out.append(idx)
            result = {"domain": "db_inv", "method": "indexes", "data": {"indexes": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INDEXES_ERROR", str(e), 0))

    def introspect(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            table_count = 0
            column_count = 0
            index_count = 0
            view_count = 0
            for t in schema:
                if isinstance(t, dict):
                    ttype = t.get("type", "table")
                    if ttype == "view":
                        view_count += 1
                    else:
                        table_count += 1
                    column_count += len(t.get("columns", []))
                    index_count += len(t.get("indexes", []))
            summary = {"tables": table_count, "columns": column_count, "indexes": index_count, "views": view_count}
            self.state["results"] = summary
            result = {"domain": "db_inv", "method": "introspect", "data": summary}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INTROSPECT_ERROR", str(e), 0))

    def relationships(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            rels = []
            for t in schema:
                if isinstance(t, dict):
                    for c in t.get("constraints", []):
                        if isinstance(c, dict) and c.get("type") == "foreign_key":
                            rels.append({"from_table": t.get("name"), "from_column": c.get("column"), "to_table": c.get("ref_table"), "to_column": c.get("ref_column")})
            result = {"domain": "db_inv", "method": "relationships", "data": {"relationships": rels, "count": len(rels)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RELATIONSHIPS_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            tables = []
            for t in schema:
                if isinstance(t, dict):
                    tables.append({
                        "name": t.get("name"),
                        "type": t.get("type", "table"),
                        "columns": len(t.get("columns", [])),
                        "indexes": len(t.get("indexes", [])),
                        "constraints": len(t.get("constraints", [])),
                    })
            result = {"domain": "db_inv", "method": "report", "data": {"tables": tables, "total": len(tables)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def stored_procs(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    for sp in t.get("stored_procs", []):
                        out.append(sp)
            result = {"domain": "db_inv", "method": "stored_procs", "data": {"stored_procs": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STORED_PROCS_ERROR", str(e), 0))

    def tables(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    if t.get("type", "table") == "table":
                        out.append(t.get("name"))
            result = {"domain": "db_inv", "method": "tables", "data": {"tables": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TABLES_ERROR", str(e), 0))

    def triggers(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    for tr in t.get("triggers", []):
                        out.append(tr)
            result = {"domain": "db_inv", "method": "triggers", "data": {"triggers": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRIGGERS_ERROR", str(e), 0))

    def views(self, params=None):
        params = params or {}
        try:
            schema = self._schema(params)
            out = []
            for t in schema:
                if isinstance(t, dict):
                    if t.get("type") == "view":
                        out.append(t.get("name"))
            result = {"domain": "db_inv", "method": "views", "data": {"views": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VIEWS_ERROR", str(e), 0))
