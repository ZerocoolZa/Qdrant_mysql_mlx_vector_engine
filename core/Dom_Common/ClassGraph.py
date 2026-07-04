#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/ClassGraph.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="Reports v4 C unit wrapper. Calls bcl_tool binary via subprocess for execution_graph, code_structure, code_flow, table, overview, profile. Queries MySQL vb_shared for knowledge_graph."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ClassGraph.py" domain="dom_common" authority="ClassGraph"}
#[@SUMMARY]{summary="ClassGraph — Reports v4 C unit wrapper. Calls bcl_tool via subprocess for execution graph, code structure, code flow, table, overview, profile. Queries MySQL vb_shared know_nodes/know_edges for knowledge graph."}
#[@CLASS]{class="ClassGraph" domain="dom_common" authority="wrapper"}
#[@METHOD]{method="execution_graph" type="parser"}
#[@METHOD]{method="code_structure" type="parser"}
#[@METHOD]{method="code_flow" type="parser"}
#[@METHOD]{method="table" type="parser"}
#[@METHOD]{method="overview" type="parser"}
#[@METHOD]{method="profile" type="parser"}
#[@METHOD]{method="knowledge_graph" type="query"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}

"""ClassGraph — Reports v4 C unit wrapper.

Wraps the Reports v4 C unit's execution graph, code structure,
code flow, table, overview, and profile capabilities. Calls the
bcl_tool binary via subprocess and parses the BCL output. Also
queries MySQL vb_shared (know_nodes, know_edges) for knowledge
graph data.
"""

import re
import subprocess

try:
    from Config import BCL_TOOL_PATH
    from Config import MYSQL_HOST
    from Config import MYSQL_USER
    from Config import MYSQL_PASS
    from Config import MYSQL_DB
except ImportError:
    from .Config import BCL_TOOL_PATH
    from .Config import MYSQL_HOST
    from .Config import MYSQL_USER
    from .Config import MYSQL_PASS
    from .Config import MYSQL_DB

# ── Error Codes ──
ERR_SUBPROCESS = "GRAPH_SUBPROCESS_ERROR"
ERR_PARSE = "GRAPH_PARSE_ERROR"
ERR_UNKNOWN_CMD = "GRAPH_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "GRAPH_BAD_PARAMS"
ERR_MYSQL = "GRAPH_MYSQL_ERROR"
ERR_TOOL_MISSING = "GRAPH_TOOL_MISSING"

# ── BCL Report Subcommands ──
CMD_EXECUTION_GRAPH = "execution_graph"
CMD_CODE_STRUCTURE = "code_structure"
CMD_CODE_FLOW = "replay"
CMD_TABLE = "table"
CMD_OVERVIEW = "overview"
CMD_PROFILE = "profile"

# ── Regex for flat BCL tag extraction ──
TAG_RE = re.compile(r'\[@TAG\]\{([^}]*)\}')

# ── Knowledge graph SQL ──
SQL_KNOW_NODES = "SELECT id, label, kind FROM know_nodes LIMIT 500"
SQL_KNOW_EDGES = "SELECT src, dst, rel FROM know_edges LIMIT 500"


class ClassGraph:
    """Reports v4 C unit wrapper. Calls bcl_tool via subprocess."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.state = {
            "initialized": True,
            "total_graphs": 0,
            "last_path": None,
            "last_error": None,
            "bcl_tool_path": BCL_TOOL_PATH,
            "config": {},
        }

    def _p(self, label, value):
        """Helper to log state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "execution_graph": self.cmd_execution_graph,
            "code_structure": self.cmd_code_structure,
            "code_flow": self.cmd_code_flow,
            "table": self.cmd_table,
            "overview": self.cmd_overview,
            "profile": self.cmd_profile,
            "knowledge_graph": self.cmd_knowledge_graph,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    # ── Command handlers ──

    def cmd_execution_graph(self, params):
        """Run bcl_tool reports execution_graph. Parse tree + edges."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_EXECUTION_GRAPH, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        tree = self._parse_tree(out)
        edges = self._parse_edges(out)
        self.state["total_graphs"] = self.state.get("total_graphs", 0) + 1
        self._p("path", path)
        result = {"tree": tree, "edges": edges, "raw": out}
        return (1, result, None)

    def cmd_code_structure(self, params):
        """Run bcl_tool reports code_structure. Parse imports + classes."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_CODE_STRUCTURE, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        imports = self._parse_imports(out)
        classes = self._parse_classes(out)
        self._p("path", path)
        result = {"imports": imports, "classes": classes, "raw": out}
        return (1, result, None)

    def cmd_code_flow(self, params):
        """Run bcl_tool reports replay. Parse event sequence."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_CODE_FLOW, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        events = self._parse_events(out)
        self._p("path", path)
        result = {"events": events, "raw": out}
        return (1, result, None)

    def cmd_table(self, params):
        """Run bcl_tool reports table. Parse all events in table form."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_TABLE, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        rows = self._parse_table_rows(out)
        summary = self._parse_summary(out)
        self._p("path", path)
        result = {"rows": rows, "summary": summary, "raw": out}
        return (1, result, None)

    def cmd_overview(self, params):
        """Run bcl_tool reports overview. Extract counts + what went wrong."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_OVERVIEW, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        total_events = self._extract_int(out, "TOTAL_EVENTS")
        errors = self._extract_int(out, "ERRORS")
        results = self._extract_int(out, "RESULTS")
        what_went_wrong = self._parse_what_went_wrong(out)
        self._p("path", path)
        result = {
            "total_events": total_events,
            "errors": errors,
            "results": results,
            "what_went_wrong": what_went_wrong,
            "raw": out,
        }
        return (1, result, None)

    def cmd_profile(self, params):
        """Run bcl_tool reports profile. Parse timings."""
        path = self._extract_path(params)
        if path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'path'", 0))
        rc, out, err = self._run_bcl(CMD_PROFILE, path)
        if rc != 0:
            self.state["last_error"] = err
            return (0, None, (ERR_SUBPROCESS, err[1], err[0]))
        timings = self._parse_timings(out)
        self._p("path", path)
        result = {"timings": timings, "raw": out}
        return (1, result, None)

    def cmd_knowledge_graph(self, params):
        """Query MySQL vb_shared know_nodes/know_edges for graph data."""
        query = None
        if params is not None and isinstance(params, dict):
            query = params.get("query")
        nodes = []
        edges = []
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASS,
                database=MYSQL_DB,
            )
            cursor = conn.cursor()
            cursor.execute(SQL_KNOW_NODES)
            for row in cursor.fetchall():
                nodes.append({"id": row[0], "label": row[1], "kind": row[2]})
            cursor.execute(SQL_KNOW_EDGES)
            for row in cursor.fetchall():
                edges.append({"src": row[0], "dst": row[1], "rel": row[2]})
            cursor.close()
            conn.close()
        except Exception as exc:
            self.state["last_error"] = str(exc)
            return (0, None, (ERR_MYSQL, str(exc), 0))
        self._p("query", query)
        result = {"nodes": nodes, "edges": edges}
        return (1, result, None)

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        self.state["config"] = params
        if "bcl_tool_path" in params:
            self.state["bcl_tool_path"] = params["bcl_tool_path"]
        self._p("config", list(params.keys()))
        return (1, None, None)

    # ── Subprocess runner ──

    def _run_bcl(self, subcommand, path):
        """Run bcl_tool reports <subcommand> "[@PATH]{path}".
        Returns (rc, stdout_str, (code, desc, rc)).
        On success rc=0 and err is None placeholder.
        """
        tool = self.state.get("bcl_tool_path", BCL_TOOL_PATH)
        bcl_arg = "[@PATH]{" + str(path) + "}"
        cmd = [tool, "reports", subcommand, bcl_arg]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except FileNotFoundError:
            return (-1, "", (1, "bcl_tool not found at " + str(tool), -1))
        except subprocess.TimeoutExpired:
            return (-1, "", (2, "bcl_tool timed out", -1))
        except Exception as exc:
            return (-1, "", (3, str(exc), -1))
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            desc = stderr.strip() if stderr.strip() else "bcl_tool exit " + str(proc.returncode)
            return (proc.returncode, stdout, (proc.returncode, desc, proc.returncode))
        return (0, stdout, None)

    # ── BCL output parsers ──

    def _extract_path(self, params):
        """Extract path string from params (dict or string)."""
        if params is None:
            return None
        if isinstance(params, str):
            return params
        if isinstance(params, dict):
            return params.get("path")
        return None

    def _extract_tag_values(self, text, tag):
        """Extract all values for [@TAG]{value} from text using regex."""
        pattern = r'\[@' + re.escape(tag) + r'\]\{([^}]*)\}'
        return re.findall(pattern, text)

    def _extract_nested(self, text, tag):
        """Extract values for [@TAG]{...} allowing nested braces.
        Uses a state machine to track brace depth.
        """
        values = []
        marker = "[@" + tag + "]"
        idx = 0
        length = len(text)
        while idx < length:
            pos = text.find(marker, idx)
            if pos == -1:
                break
            j = pos + len(marker)
            # skip optional whitespace
            while j < length and text[j] in (" ", "\t", "\n", "\r"):
                j = j + 1
            if j >= length or text[j] != "{":
                idx = pos + len(marker)
                continue
            j = j + 1
            start = j
            depth = 1
            while j < length and depth > 0:
                if text[j] == "{":
                    depth = depth + 1
                elif text[j] == "}":
                    depth = depth - 1
                    if depth == 0:
                        break
                j = j + 1
            if depth == 0:
                values.append(text[start:j])
                idx = j + 1
            else:
                values.append(text[start:])
                idx = length
        return values

    def _parse_tree(self, text):
        """Parse tree nodes from execution_graph BCL output."""
        nodes = []
        raw_nodes = self._extract_nested(text, "NODE")
        for raw in raw_nodes:
            node = {}
            label = self._extract_tag_values(raw, "LABEL")
            if label:
                node["label"] = label[0]
            kind = self._extract_tag_values(raw, "KIND")
            if kind:
                node["kind"] = kind[0]
            nid = self._extract_tag_values(raw, "ID")
            if nid:
                node["id"] = nid[0]
            if not node:
                node["raw"] = raw
            nodes.append(node)
        if not nodes:
            for val in self._extract_tag_values(text, "NODE"):
                nodes.append({"label": val})
        return nodes

    def _parse_edges(self, text):
        """Parse call edges from execution_graph BCL output."""
        edges = []
        raw_edges = self._extract_nested(text, "EDGE")
        for raw in raw_edges:
            edge = {}
            src = self._extract_tag_values(raw, "SRC")
            if src:
                edge["src"] = src[0]
            dst = self._extract_tag_values(raw, "DST")
            if dst:
                edge["dst"] = dst[0]
            label = self._extract_tag_values(raw, "LABEL")
            if label:
                edge["label"] = label[0]
            if not edge:
                edge["raw"] = raw
            edges.append(edge)
        if not edges:
            for val in self._extract_tag_values(text, "EDGE"):
                edges.append({"raw": val})
        return edges

    def _parse_imports(self, text):
        """Parse imports from code_structure BCL output."""
        imports = []
        raw_imports = self._extract_nested(text, "IMPORT")
        for raw in raw_imports:
            name = self._extract_tag_values(raw, "NAME")
            if name:
                imports.append(name[0])
            else:
                imports.append(raw.strip())
        if not imports:
            imports = self._extract_tag_values(text, "IMPORT")
        return imports

    def _parse_classes(self, text):
        """Parse classes/methods from code_structure BCL output."""
        classes = []
        raw_classes = self._extract_nested(text, "CLASS")
        for raw in raw_classes:
            cls = {}
            name = self._extract_tag_values(raw, "NAME")
            if name:
                cls["name"] = name[0]
            methods = []
            raw_methods = self._extract_nested(raw, "METHOD")
            for mraw in raw_methods:
                mname = self._extract_tag_values(mraw, "NAME")
                if mname:
                    methods.append(mname[0])
                else:
                    methods.append(mraw.strip())
            if methods:
                cls["methods"] = methods
            if not cls:
                cls["raw"] = raw
            classes.append(cls)
        if not classes:
            for val in self._extract_tag_values(text, "CLASS"):
                classes.append({"name": val})
        return classes

    def _parse_events(self, text):
        """Parse event sequence from code_flow BCL output."""
        events = []
        raw_events = self._extract_nested(text, "EVENT")
        for raw in raw_events:
            evt = {}
            seq = self._extract_tag_values(raw, "SEQ")
            if seq:
                evt["seq"] = seq[0]
            name = self._extract_tag_values(raw, "NAME")
            if name:
                evt["name"] = name[0]
            kind = self._extract_tag_values(raw, "KIND")
            if kind:
                evt["kind"] = kind[0]
            if not evt:
                evt["raw"] = raw
            events.append(evt)
        if not events:
            events = self._extract_tag_values(text, "EVENT")
        return events

    def _parse_table_rows(self, text):
        """Parse table rows from table BCL output."""
        rows = []
        raw_rows = self._extract_nested(text, "ROW")
        for raw in raw_rows:
            row = {}
            cells = self._extract_tag_values(raw, "CELL")
            if cells:
                row["cells"] = cells
            seq = self._extract_tag_values(raw, "SEQ")
            if seq:
                row["seq"] = seq[0]
            event = self._extract_tag_values(raw, "EVENT")
            if event:
                row["event"] = event[0]
            if not row:
                row["raw"] = raw
            rows.append(row)
        if not rows:
            rows = self._extract_tag_values(text, "ROW")
        return rows

    def _parse_summary(self, text):
        """Parse summary block from table BCL output."""
        summary = {}
        raw_summaries = self._extract_nested(text, "SUMMARY")
        for raw in raw_summaries:
            for tag in ("TOTAL", "ERRORS", "RESULTS", "DURATION"):
                vals = self._extract_tag_values(raw, tag)
                if vals:
                    summary[tag.lower()] = vals[0]
        if not summary:
            for tag in ("TOTAL", "ERRORS", "RESULTS", "DURATION"):
                vals = self._extract_tag_values(text, tag)
                if vals:
                    summary[tag.lower()] = vals[0]
        return summary

    def _parse_timings(self, text):
        """Parse timing entries from profile BCL output."""
        timings = []
        raw_timings = self._extract_nested(text, "TIMING")
        for raw in raw_timings:
            entry = {}
            name = self._extract_tag_values(raw, "NAME")
            if name:
                entry["name"] = name[0]
            elapsed = self._extract_tag_values(raw, "ELAPSED")
            if elapsed:
                entry["elapsed"] = elapsed[0]
            calls = self._extract_tag_values(raw, "CALLS")
            if calls:
                entry["calls"] = calls[0]
            if not entry:
                entry["raw"] = raw
            timings.append(entry)
        if not timings:
            timings = self._extract_tag_values(text, "TIMING")
        return timings

    def _parse_what_went_wrong(self, text):
        """Parse what_went_wrong list from overview BCL output."""
        wrong = []
        raw_wrong = self._extract_nested(text, "WHAT_WENT_WRONG")
        for raw in raw_wrong:
            items = self._extract_tag_values(raw, "ITEM")
            if items:
                wrong.extend(items)
            else:
                wrong.append(raw.strip())
        if not wrong:
            wrong = self._extract_tag_values(text, "WHAT_WENT_WRONG")
        return wrong

    def _extract_int(self, text, tag):
        """Extract an integer value for [@TAG]{value} from text."""
        vals = self._extract_tag_values(text, tag)
        if not vals:
            return 0
        try:
            return int(vals[0])
        except (ValueError, IndexError):
            return 0
