#!/usr/bin/env python3
"""
memunit_gui.py — PyQt6 GUI for the MemUnit Architecture

Shows the full tree visually:
  MemUnit (base)
    ├── DOM_IO   (READ, WRITE)
    ├── GPU      (EXEC, OPT)
    └── DB       (QUERY, STORE)

Plus a live BCL console — type BCL, see it dispatched.

Run: python3 memunit_gui.py
"""

import sys
import sqlite3
import time

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTabWidget, QTextEdit, QLineEdit,
        QGroupBox, QFrame, QScrollArea, QSplitter, QTableWidget,
        QTableWidgetItem, QHeaderView, QComboBox
    )
    from PyQt6.QtGui import QFont, QColor, QPalette
    from PyQt6.QtCore import Qt, QTimer
except ImportError:
    print("PyQt6 not found. Install: pip install PyQt6")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# BCL PARSER — Python mirror of memunit.c Bcl_Parse
# ═══════════════════════════════════════════════════════════════

import re

def bcl_parse(text):
    """Parse [@Token]{(key;value)(key;value)...} → (token, {key: value})"""
    text = text.strip()
    m = re.match(r'\[@(\w+)\]\s*\{(.*)\}\s*$', text, re.DOTALL)
    if not m:
        return None, {}, "Not BCL format: missing [@Token]{...}"
    token = m.group(1)
    body = m.group(2)
    pairs = {}
    for pm in re.finditer(r'\(([^;)]*);([^)]*)\)', body):
        key = pm.group(1).strip().strip('"')
        val = pm.group(2).strip().strip('"')
        pairs[key] = val
    return token, pairs, ""


def bcl_emit_pass(data_json):
    return f'[@Pass]{{("data";"{data_json}")}}'

def bcl_emit_fail(error_msg, error_code):
    return f'[@Fail]{{("error";"{error_msg}");("code";"{error_code}")}}'


# ═══════════════════════════════════════════════════════════════
# RESULTS BUS — Python mirror of results_bus.c
# ═══════════════════════════════════════════════════════════════

class ResultsBus:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name  TEXT NOT NULL,
                action      TEXT NOT NULL,
                ok          INTEGER NOT NULL,
                data_json   TEXT,
                error_code  INTEGER,
                error_msg   TEXT,
                elapsed_ms  REAL,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        self.db.commit()
        self.row_count = 0

    def write(self, class_name, action, ok, data_json, error_code, error_msg, elapsed_ms):
        self.db.execute(
            "INSERT INTO results (class_name, action, ok, data_json, error_code, error_msg, elapsed_ms) VALUES (?,?,?,?,?,?,?)",
            (class_name, action, 1 if ok else 0, data_json or "", error_code, error_msg, elapsed_ms)
        )
        self.db.commit()
        self.row_count += 1

    def dump(self):
        rows = self.db.execute(
            "SELECT id, class_name, action, ok, error_msg, elapsed_ms FROM results ORDER BY id"
        ).fetchall()
        total = len(rows)
        ok_count = sum(1 for r in rows if r[3])
        fail_count = total - ok_count
        lines = [f"Results Bus: {total} total | {ok_count} ok | {fail_count} fail"]
        for r in rows:
            status = "OK" if r[3] else "FAIL"
            lines.append(f"  [{r[0]}] {r[1]}.{r[2]} -> {status} ({r[5]:.1f}ms)")
        return "\n".join(lines)

    def query(self, class_name):
        rows = self.db.execute(
            "SELECT id, class_name, action, ok, data_json, error_msg, elapsed_ms FROM results WHERE class_name=? ORDER BY id",
            (class_name,)
        ).fetchall()
        return rows

    def all_rows(self):
        return self.db.execute(
            "SELECT id, class_name, action, ok, data_json, error_msg, elapsed_ms FROM results ORDER BY id"
        ).fetchall()

    def close(self):
        self.db.close()


# ═══════════════════════════════════════════════════════════════
# DOMAIN SIMULATORS — Python mirrors of dom_io, dom_gpu, dom_db
# ═══════════════════════════════════════════════════════════════

class DomIo:
    """DOM_IO — READ, WRITE"""
    name = "DOM_IO"
    actions = {"READ": "Read a file", "WRITE": "Write a file"}

    def __init__(self):
        self.files_read = 0
        self.files_written = 0

    def run(self, action, params):
        if action == "READ":
            path = params.get("path", "?")
            try:
                with open(path, "r") as f:
                    content = f.read(4096)
                self.files_read += 1
                return True, f'{{"path":"{path}","bytes":{len(content)}}}', 0, ""
            except Exception as e:
                return False, "", 6, str(e)
        elif action == "WRITE":
            path = params.get("path", "?")
            content = params.get("content", "")
            try:
                with open(path, "w") as f:
                    f.write(content)
                self.files_written += 1
                return True, f'{{"path":"{path}","bytes":{len(content)}}}', 0, ""
            except Exception as e:
                return False, "", 6, str(e)
        return False, "", 1, f"unknown action: {action}"


class DomGpu:
    """GPU — EXEC, OPT"""
    name = "GPU"
    actions = {"EXEC": "Launch a GPU kernel", "OPT": "Run optimization pass"}

    def __init__(self):
        self.kernels_executed = 0
        self.optimizations_run = 0
        self.gpu_available = False

    def run(self, action, params):
        if action == "EXEC":
            kernel = params.get("kernel", "?")
            blocks = int(params.get("blocks", "256"))
            self.kernels_executed += 1
            gpu = "available" if self.gpu_available else "simulated"
            return True, f'{{"kernel":"{kernel}","blocks":{blocks},"status":"launched","gpu":"{gpu}"}}', 0, ""
        elif action == "OPT":
            level = int(params.get("level", "1"))
            target = params.get("target", "auto")
            self.optimizations_run += 1
            return True, f'{{"level":{level},"target":"{target}","improvement":"{level*15}%"}}', 0, ""
        return False, "", 1, f"unknown action: {action}"


class DomDb:
    """DB — QUERY, STORE"""
    name = "DB"
    actions = {"QUERY": "Run a SQL query", "STORE": "Store data in a table"}

    def __init__(self):
        self.local_db = sqlite3.connect(":memory:")
        self.local_db.execute("CREATE TABLE IF NOT EXISTS results (data TEXT)")
        self.local_db.commit()
        self.queries_run = 0
        self.stores_executed = 0

    def run(self, action, params):
        if action == "QUERY":
            sql = params.get("sql", "")
            limit = int(params.get("limit", "50"))
            self.queries_run += 1
            try:
                cur = self.local_db.execute(sql)
                rows = cur.fetchall()
                return True, f'{{"sql":"{sql}","limit":{limit},"rows":{len(rows)}}}', 0, ""
            except Exception as e:
                return True, f'{{"sql":"{sql}","limit":{limit},"rows":0,"error":"{e}"}}', 0, ""
        elif action == "STORE":
            table = params.get("table", "?")
            data = params.get("data", "")
            self.stores_executed += 1
            try:
                self.local_db.execute(f"INSERT INTO {table} (data) VALUES (?)", (data,))
                self.local_db.commit()
                return True, f'{{"table":"{table}","stored":true,"bytes":{len(data)}}}', 0, ""
            except Exception as e:
                return False, "", 4, str(e)
        return False, "", 1, f"unknown action: {action}"

    def close(self):
        self.local_db.close()


# ═══════════════════════════════════════════════════════════════
# MEMUNIT — Base class dispatcher (Python mirror of memunit.c)
# ═══════════════════════════════════════════════════════════════

class MemUnit:
    """Base class — parses BCL, dispatches to domain, writes to ResultsBus, emits BCL"""
    def __init__(self, domain, bus):
        self.domain = domain
        self.bus = bus
        self.call_count = 0
        self.last_action = ""
        self.last_bcl_out = ""

    def run_bcl(self, bcl_input):
        """BCL in → parse → dispatch → write result → emit BCL out"""
        t0 = time.time()

        # 1. Parse BCL
        token, pairs, err = bcl_parse(bcl_input)
        if err:
            elapsed = (time.time() - t0) * 1000
            self.bus.write(self.domain.name, "PARSE_ERROR", False, "", 1, err, elapsed)
            self.last_bcl_out = bcl_emit_fail(err, 1)
            return False, "", 1, err, self.last_bcl_out

        # 2. Extract command
        command = pairs.get("command", pairs.get("action", ""))
        if not command:
            elapsed = (time.time() - t0) * 1000
            msg = "no_command_in_bcl"
            self.bus.write(self.domain.name, "NO_COMMAND", False, "", 2, msg, elapsed)
            self.last_bcl_out = bcl_emit_fail(msg, 2)
            return False, "", 2, msg, self.last_bcl_out

        # 3. Dispatch
        ok, data_json, error_code, error_msg = self.domain.run(command, pairs)

        elapsed = (time.time() - t0) * 1000
        self.call_count += 1
        self.last_action = command

        # 4. Write to ResultsBus
        self.bus.write(self.domain.name, command, ok, data_json, error_code, error_msg, elapsed)

        # 5. Emit BCL output
        if ok:
            self.last_bcl_out = bcl_emit_pass(data_json)
        else:
            self.last_bcl_out = bcl_emit_fail(error_msg, error_code)

        return ok, data_json, error_code, error_msg, self.last_bcl_out


# ═══════════════════════════════════════════════════════════════
# GUI — PyQt6 MainWindow
# ═══════════════════════════════════════════════════════════════

# Colors (dark theme)
BG          = "#0d1117"
BG_CARD     = "#161b22"
BG_INPUT    = "#1c2128"
BORDER      = "#30363d"
TEXT        = "#c9d1d9"
TEXT_DIM    = "#8b949e"
BLUE        = "#58a6ff"
GREEN       = "#7ee787"
PURPLE      = "#bc8cff"
ORANGE      = "#f0883e"
RED         = "#f85149"
YELLOW      = "#d29922"

def styled_label(text, color=TEXT, size=11, bold=False):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {'bold' if bold else 'normal'}; font-family: monospace;")
    return lbl


def domain_card(name, actions, color, desc, bcl_in, bcl_out):
    """Create a domain card widget"""
    card = QFrame()
    card.setFixedWidth(300)
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {BG_CARD};
            border: 2px solid {color};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(15, 15, 15, 15)
    layout.setSpacing(8)

    # Header
    header = QLabel(name)
    header.setStyleSheet(f"color: white; background-color: {color}; font-size: 14px; font-weight: bold; font-family: monospace; padding: 6px; border-radius: 5px;")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    # Description
    desc_lbl = styled_label(desc, TEXT_DIM, 9)
    desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(desc_lbl)

    # Actions
    for act_name, act_desc in actions.items():
        act_frame = QFrame()
        act_frame.setStyleSheet(f"background-color: {BG}; border: 1px solid {color}; border-radius: 5px; padding: 4px;")
        act_layout = QHBoxLayout(act_frame)
        act_layout.setContentsMargins(8, 4, 8, 4)
        act_lbl = styled_label(act_name, color, 13, bold=True)
        act_layout.addWidget(act_lbl)
        act_desc_lbl = styled_label(act_desc, TEXT_DIM, 9)
        act_desc_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        act_layout.addWidget(act_desc_lbl)
        layout.addWidget(act_frame)

    # BCL example
    bcl_frame = QFrame()
    bcl_frame.setStyleSheet(f"background-color: {BG}; border: 1px solid {BORDER}; border-radius: 5px;")
    bcl_layout = QVBoxLayout(bcl_frame)
    bcl_layout.setContentsMargins(8, 6, 8, 6)
    bcl_layout.setSpacing(2)
    bcl_layout.addWidget(styled_label("BCL in:", TEXT_DIM, 9))
    bcl_layout.addWidget(styled_label(bcl_in, YELLOW, 9))
    bcl_layout.addWidget(styled_label("BCL out:", TEXT_DIM, 9))
    bcl_layout.addWidget(styled_label(bcl_out, color, 9))
    layout.addWidget(bcl_frame)

    layout.addStretch()
    return card


class ResultsTableWidget(QTableWidget):
    """Table showing ResultsBus contents"""
    def __init__(self):
        super().__init__()
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["id", "class", "action", "ok", "data_json", "error", "ms"])
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BG};
                color: {TEXT};
                gridline-color: {BORDER};
                font-family: monospace;
                font-size: 10px;
            }}
            QHeaderView::section {{
                background-color: {BG_CARD};
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)
        self.horizontalHeader().setStyleSheet(f"background-color: {BG_CARD};")
        self.setAlternatingRowColors(True)
        self.setStyleSheet(self.styleSheet() + f"QTableWidget::item:alternate {{ background-color: {BG_CARD}; }}")
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def update_rows(self, rows):
        self.setRowCount(len(rows))
        for i, r in enumerate(rows):
            color = GREEN if r[3] else RED
            items = [
                str(r[0]), r[1], r[2], "OK" if r[3] else "FAIL",
                r[4] or "", r[5] or "", f"{r[6]:.1f}"
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color if j == 3 else TEXT))
                self.setItem(i, j, item)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MemUnit Architecture — VBStyle-for-C")
        self.setMinimumSize(1200, 850)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG}; }}")

        # ── Backend ──
        self.bus = ResultsBus()
        self.io = DomIo()
        self.gpu = DomGpu()
        self.db = DomDb()
        self.mu_io = MemUnit(self.io, self.bus)
        self.mu_gpu = MemUnit(self.gpu, self.bus)
        self.mu_db = MemUnit(self.db, self.bus)

        # ── Central widget with tabs ──
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
            QTabBar::tab {{
                background: {BG_CARD}; color: {TEXT_DIM};
                padding: 8px 20px; border: 1px solid {BORDER};
                border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-family: monospace; font-size: 12px;
            }}
            QTabBar::tab:selected {{ background: {BG}; color: {BLUE}; font-weight: bold; }}
        """)

        tabs.addTab(self._tab_architecture(), "Architecture")
        tabs.addTab(self._tab_console(), "BCL Console")
        tabs.addTab(self._tab_results(), "Results Table")

        self.setCentralWidget(tabs)

    # ═══════════════════════════════════════════════════════════════
    # TAB 1: Architecture diagram
    # ═══════════════════════════════════════════════════════════════

    def _tab_architecture(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG}; border: none; }}")

        central = QWidget()
        central.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = styled_label("MemUnit Architecture — VBStyle-for-C", BLUE, 20, bold=True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = styled_label("ONE parser · ONE dispatch · ONE results table · BCL in → BCL out", TEXT_DIM, 12)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # BCL Input box
        in_frame = QFrame()
        in_frame.setStyleSheet(f"background-color: {BG_INPUT}; border: 2px solid {ORANGE}; border-radius: 8px;")
        in_layout = QVBoxLayout(in_frame)
        in_layout.setContentsMargins(15, 8, 15, 8)
        in_layout.addWidget(styled_label("BCL INPUT", ORANGE, 13, bold=True))
        in_example = styled_label('[@Run]{("command";"EXEC");("kernel";"matmul");("blocks";"1024")}', YELLOW, 11)
        in_layout.addWidget(in_example)
        layout.addWidget(in_frame)

        # Arrow
        arrow = styled_label("↓", TEXT_DIM, 18, bold=True)
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow)

        # MemUnit box
        mu_frame = QFrame()
        mu_frame.setStyleSheet(f"background-color: {BG_CARD}; border: 3px solid {BLUE}; border-radius: 10px;")
        mu_layout = QVBoxLayout(mu_frame)
        mu_layout.setContentsMargins(15, 10, 15, 10)
        mu_layout.setSpacing(6)

        mu_header = styled_label("MemUnit  (memunit.c — THE BASE CLASS)", BLUE, 15, bold=True)
        mu_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mu_layout.addWidget(mu_header)

        # 4 internal boxes
        boxes_layout = QHBoxLayout()
        boxes_layout.setSpacing(8)

        for name, desc_lines, color in [
            ("BCL PARSER", ["ONE copy", "[@Token]{(k;v)...}", "→ token + pairs"], GREEN),
            ("AUTO-DISPATCH", ["ActionBinding[]", "table lookup", "command → fn()"], PURPLE),
            ("RESULTSBUS", ["in-RAM SQLite", "every result", "→ central table"], RED),
            ("BCL EMITTER", ["wrap result", "back into BCL", "[@Pass] / [@Fail]"], YELLOW),
        ]:
            box = QFrame()
            box.setFixedHeight(90)
            box.setStyleSheet(f"background-color: {BG}; border: 2px solid {color}; border-radius: 6px;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 6, 8, 6)
            box_layout.setSpacing(2)
            box_layout.addWidget(styled_label(name, color, 11, bold=True))
            for line in desc_lines:
                box_layout.addWidget(styled_label(line, TEXT_DIM, 9))
            boxes_layout.addWidget(box)

        mu_layout.addLayout(boxes_layout)

        # Flow text
        flow = styled_label("parse → extract command → find in ACTIONS[] → call fn(state, params) → write result → emit BCL", TEXT_DIM, 10)
        flow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mu_layout.addWidget(flow)

        # API
        api = styled_label("MemUnit_Init()  ·  MemUnit_Run()  ·  MemUnit_RunAction()  ·  MemUnit_Status()", BLUE, 10, bold=True)
        api.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mu_layout.addWidget(api)

        note = styled_label("Subclass embeds MemUnit as FIRST field → composition = inheritance in C", TEXT_DIM, 9)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mu_layout.addWidget(note)

        layout.addWidget(mu_frame)

        # Arrow
        arrow2 = styled_label("↓  dispatches to  ↓", TEXT_DIM, 12)
        arrow2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow2)

        # 3 domain cards
        domains_layout = QHBoxLayout()
        domains_layout.setSpacing(15)

        domains_layout.addWidget(domain_card(
            "DOM_IO (dom_io.c)", {"READ": "Read a file", "WRITE": "Write a file"},
            GREEN, "File I/O domain",
            '[@Run]{("command";"READ");("path";"/etc/hosts")}',
            '[@Pass]{("data";"{"bytes":256}")}'
        ))
        domains_layout.addWidget(domain_card(
            "GPU (dom_gpu.c)", {"EXEC": "Launch kernel", "OPT": "Optimize"},
            PURPLE, "GPU compute domain",
            '[@Run]{("command";"EXEC");("kernel";"matmul")}',
            '[@Pass]{("data";"{"status":"launched"}")}'
        ))
        domains_layout.addWidget(domain_card(
            "DB (dom_db.c)", {"QUERY": "Run SQL query", "STORE": "Store data"},
            ORANGE, "Database domain",
            '[@Run]{("command";"QUERY");("sql";"SELECT * FROM t")}',
            '[@Pass]{("data";"{"rows":42}")}'
        ))
        layout.addLayout(domains_layout)

        # Arrow
        arrow3 = styled_label("↓  all results write to  ↓", RED, 12)
        arrow3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow3)

        # ResultsBus box
        rb_frame = QFrame()
        rb_frame.setStyleSheet(f"background-color: {BG_CARD}; border: 2px solid {RED}; border-radius: 10px;")
        rb_layout = QVBoxLayout(rb_frame)
        rb_layout.setContentsMargins(15, 8, 15, 8)
        rb_header = styled_label("RESULTSBUS — Central In-RAM SQLite Table  (results_bus.c)", RED, 14, bold=True)
        rb_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb_layout.addWidget(rb_header)

        self.rb_summary = styled_label("0 total · 0 ok · 0 fail · ALL domains share this ONE table", TEXT_DIM, 10)
        self.rb_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb_layout.addWidget(self.rb_summary)

        layout.addWidget(rb_frame)

        # BCL Output
        arrow4 = styled_label("↓", TEXT_DIM, 18, bold=True)
        arrow4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(arrow4)

        out_frame = QFrame()
        out_frame.setStyleSheet(f"background-color: {BG_INPUT}; border: 2px solid {YELLOW}; border-radius: 8px;")
        out_layout = QVBoxLayout(out_frame)
        out_layout.setContentsMargins(15, 8, 15, 8)
        out_layout.addWidget(styled_label("BCL OUTPUT", YELLOW, 13, bold=True))
        self.out_example = styled_label('[@Pass]{("data";"...")}', GREEN, 11)
        out_layout.addWidget(self.out_example)
        layout.addWidget(out_frame)

        # File map
        layout.addSpacing(10)
        file_title = styled_label("FILE MAP — What lives where", BLUE, 13, bold=True)
        file_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(file_title)

        files = [
            ("cascade_toolstack.h", BLUE, "ONE header — Tuple3, MemUnit, BCL types, domain structs"),
            ("memunit.c", GREEN, "Base class — BCL parser + emitter + auto-dispatch + ResultsBus (290 lines)"),
            ("results_bus.c", RED, "Central in-RAM SQLite table — Init, Write, Query, Dump, Close (230 lines)"),
            ("dom_io.c", GREEN, "DOM_IO — READ, WRITE only. No parser, no dispatch, no results writing (130 lines)"),
            ("dom_gpu.c", PURPLE, "GPU — EXEC, OPT only. No parser, no dispatch, no results writing (125 lines)"),
            ("dom_db.c", ORANGE, "DB — QUERY, STORE only. No parser, no dispatch, no results writing (196 lines)"),
        ]
        for fname, color, desc in files:
            row = QHBoxLayout()
            row.addWidget(styled_label(fname, color, 11, bold=True))
            row.addWidget(styled_label(desc, TEXT_DIM, 10))
            layout.addLayout(row)

        # Key insight
        layout.addSpacing(10)
        insight = QFrame()
        insight.setStyleSheet(f"background-color: {BG_CARD}; border: 1px solid {BLUE}; border-radius: 6px;")
        ins_layout = QVBoxLayout(insight)
        ins_layout.setContentsMargins(15, 10, 15, 10)
        ins_layout.addWidget(styled_label("THE KEY INSIGHT", BLUE, 12, bold=True))
        ins_layout.addWidget(styled_label("Each domain file has ONLY:", TEXT, 10))
        ins_layout.addWidget(styled_label("  · Act_*() functions (the actual work)", GREEN, 10))
        ins_layout.addWidget(styled_label("  · ACTIONS[] table (name → function map)", PURPLE, 10))
        ins_layout.addWidget(styled_label("  · DomXxx_Init() (calls MemUnit_Init)", ORANGE, 10))
        ins_layout.addWidget(styled_label("NO parser. NO dispatch. NO results writing. MemUnit = all of that.", YELLOW, 10, bold=True))
        layout.addWidget(insight)

        layout.addStretch()
        scroll.setWidget(central)
        return scroll

    # ═══════════════════════════════════════════════════════════════
    # TAB 2: BCL Console — live interaction
    # ═══════════════════════════════════════════════════════════════

    def _tab_console(self):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        layout.addWidget(styled_label("BCL Console — Type BCL, see it dispatched live", BLUE, 16, bold=True))

        # Domain selector
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(styled_label("Target domain:", TEXT, 11))
        self.domain_combo = QComboBox()
        self.domain_combo.addItems(["DOM_IO", "GPU", "DB"])
        self.domain_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {BG_INPUT}; color: {TEXT};
                border: 1px solid {BORDER}; padding: 5px 10px;
                font-family: monospace; font-size: 12px; border-radius: 4px;
            }}
        """)
        sel_layout.addWidget(self.domain_combo)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # Input field
        layout.addWidget(styled_label("BCL Input:", YELLOW, 12, bold=True))
        self.bcl_input = QLineEdit()
        self.bcl_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_INPUT}; color: {YELLOW};
                border: 2px solid {ORANGE}; border-radius: 6px;
                padding: 10px; font-family: monospace; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {BLUE}; }}
        """)
        self.bcl_input.returnPressed.connect(self._dispatch_bcl)
        layout.addWidget(self.bcl_input)

        # Run button
        run_btn = QPushButton("▶  Dispatch BCL")
        run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #238636; color: white;
                border: none; border-radius: 6px;
                padding: 10px 20px; font-family: monospace;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2ea043; }}
        """)
        run_btn.clicked.connect(self._dispatch_bcl)
        layout.addWidget(run_btn)

        # Quick examples
        layout.addWidget(styled_label("Quick examples (click to load):", TEXT_DIM, 10))
        examples_layout = QHBoxLayout()
        examples = [
            ("DOM_IO READ", '[@Run]{("command";"READ");("path";"/etc/hosts")}', "DOM_IO"),
            ("DOM_IO WRITE", '[@Run]{("command";"WRITE");("path";"/tmp/gui_test.txt");("content";"hello from GUI")}', "DOM_IO"),
            ("GPU EXEC", '[@Run]{("command";"EXEC");("kernel";"matmul");("blocks";"1024")}', "GPU"),
            ("GPU OPT", '[@Run]{("command";"OPT");("level";"3");("target";"memory")}', "GPU"),
            ("DB STORE", '[@Run]{("command";"STORE");("table";"results");("data";"{\\"id\\":1}")}', "DB"),
            ("DB QUERY", '[@Run]{("command";"QUERY");("sql";"SELECT * FROM results");("limit";"10")}', "DB"),
        ]
        for label_text, bcl, domain in examples:
            btn = QPushButton(label_text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BG_CARD}; color: {TEXT};
                    border: 1px solid {BORDER}; border-radius: 4px;
                    padding: 6px 10px; font-family: monospace; font-size: 10px;
                }}
                QPushButton:hover {{ border-color: {BLUE}; color: {BLUE}; }}
            """)
            btn.clicked.connect(lambda checked, b=bcl, d=domain: self._load_example(b, d))
            examples_layout.addWidget(btn)
        layout.addLayout(examples_layout)

        # Output
        layout.addWidget(styled_label("Output:", GREEN, 12, bold=True))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_INPUT}; color: {TEXT};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 10px; font-family: monospace; font-size: 12px;
            }}
        """)
        layout.addWidget(self.output)

        # Results summary
        self.console_summary = styled_label("", TEXT_DIM, 10)
        layout.addWidget(self.console_summary)

        return widget

    def _load_example(self, bcl, domain):
        self.bcl_input.setText(bcl)
        # Set domain combo
        idx = self.domain_combo.findText(domain)
        if idx >= 0:
            self.domain_combo.setCurrentIndex(idx)

    def _dispatch_bcl(self):
        bcl = self.bcl_input.text().strip()
        if not bcl:
            self.output.append(f'<span style="color:{RED}">Error: empty input</span>')
            return

        domain_name = self.domain_combo.currentText()
        if domain_name == "DOM_IO":
            mu = self.mu_io
        elif domain_name == "GPU":
            mu = self.mu_gpu
        else:
            mu = self.mu_db

        ok, data_json, error_code, error_msg, bcl_out = mu.run_bcl(bcl)

        color = GREEN if ok else RED
        status = "OK" if ok else "FAIL"
        self.output.append(f'<span style="color:{YELLOW}">IN:</span>  <span style="color:{TEXT}">{bcl}</span>')
        self.output.append(f'<span style="color:{BLUE}">→ {domain_name}.{mu.last_action}</span>')
        self.output.append(f'<span style="color:{color}">OUT: {bcl_out}</span>')
        if not ok:
            self.output.append(f'<span style="color:{RED}">ERROR: {error_msg} (code={error_code})</span>')
        self.output.append("")

        self.out_example.setText(bcl_out)
        self._update_summary()

    def _update_summary(self):
        rows = self.bus.all_rows()
        total = len(rows)
        ok_count = sum(1 for r in rows if r[3])
        fail_count = total - ok_count
        self.rb_summary.setText(f"{total} total · {ok_count} ok · {fail_count} fail · ALL domains share this ONE table")
        self.console_summary.setText(f"ResultsBus: {total} total | {ok_count} ok | {fail_count} fail")
        if hasattr(self, 'results_table'):
            self.results_table.update_rows(rows)

    # ═══════════════════════════════════════════════════════════════
    # TAB 3: Results Table
    # ═══════════════════════════════════════════════════════════════

    def _tab_results(self):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(styled_label("Central Results Table — In-RAM SQLite", RED, 16, bold=True))

        # Filter buttons
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(styled_label("Filter:", TEXT, 11))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "DOM_IO", "GPU", "DB"])
        self.filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {BG_INPUT}; color: {TEXT};
                border: 1px solid {BORDER}; padding: 5px 10px;
                font-family: monospace; font-size: 12px; border-radius: 4px;
            }}
        """)
        self.filter_combo.currentTextChanged.connect(self._filter_results)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()

        clear_btn = QPushButton("Clear Table")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_CARD}; color: {RED};
                border: 1px solid {RED}; border-radius: 4px;
                padding: 6px 15px; font-family: monospace; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {RED}; color: white; }}
        """)
        clear_btn.clicked.connect(self._clear_results)
        filter_layout.addWidget(clear_btn)
        layout.addLayout(filter_layout)

        # Table
        self.results_table = ResultsTableWidget()
        layout.addWidget(self.results_table)

        # Dump text
        layout.addWidget(styled_label("Text dump:", TEXT_DIM, 10))
        self.dump_text = QTextEdit()
        self.dump_text.setReadOnly(True)
        self.dump_text.setMaximumHeight(150)
        self.dump_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_INPUT}; color: {TEXT};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 8px; font-family: monospace; font-size: 11px;
            }}
        """)
        layout.addWidget(self.dump_text)

        return widget

    def _filter_results(self, filter_text):
        if filter_text == "ALL":
            rows = self.bus.all_rows()
        else:
            rows = self.bus.query(filter_text)
        self.results_table.update_rows(rows)
        self.dump_text.setText(self.bus.dump())

    def _clear_results(self):
        self.bus.db.execute("DELETE FROM results")
        self.bus.db.commit()
        self.bus.row_count = 0
        self._filter_results(self.filter_combo.currentText())
        self._update_summary()

    def closeEvent(self, event):
        self.bus.close()
        self.db.close()
        event.accept()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
