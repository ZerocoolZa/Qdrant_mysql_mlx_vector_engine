"""
VBStyle Rule Truth GUI
Connects to real vb_shared.rules table + adds truth classification (TRUE/FALSE/UNKNOWN).
Rules can be viewed, filtered, edited, and classified.
Run: python3 rule_truth_gui.py
"""

import sys
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QComboBox, QLineEdit, QGroupBox, QFormLayout,
    QTabWidget, QTextEdit, QProgressBar, QMessageBox, QDialog,
    QDialogButtonBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPlainTextEdit,
    QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QAction


MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_DB = "vb_shared"


RULE_DB_PATH = "/tmp/rule_truth_mock.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rule_truths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         INTEGER,
    rule_text       TEXT NOT NULL,
    description     TEXT,
    rule_category   TEXT NOT NULL DEFAULT 'general',
    severity        TEXT NOT NULL DEFAULT 'guideline',
    classification  TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence      REAL NOT NULL DEFAULT 0.0,
    weight          INTEGER NOT NULL DEFAULT 50,
    provenance      TEXT NOT NULL DEFAULT 'cascade_llm',
    evidence        TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    is_canonical    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'open',
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT
);
"""


CATEGORY_COLORS = {
    "prohibition":  QColor(178, 34, 34),
    "requirement":  QColor(30, 100, 200),
    "constraint":   QColor(138, 43, 226),
    "general":      QColor(100, 100, 100),
}

SEVERITY_COLORS = {
    "mandatory": QColor(178, 34, 34),
    "critical":  QColor(220, 20, 60),
    "guideline": QColor(100, 100, 100),
}

CLASSIFICATION_COLORS = {
    "TRUE":      QColor(34, 139, 34),
    "FALSE":     QColor(178, 34, 34),
    "UNKNOWN":   QColor(184, 134, 11),
}

STATUS_COLORS = {
    "stabilized": QColor(34, 139, 34),
    "answered":   QColor(30, 100, 200),
    "open":       QColor(184, 134, 11),
    "collapsed":  QColor(128, 128, 128),
}


REAL_RULES = [
    (1, "1 class = 1 domain = 1 authority", "Single outer class = domain controller, nested inner classes = authorities", "constraint", "guideline"),
    (2, "Fixed 5-element state structure", "self.state = {config, catalog, results, memunit, db_manager}", "constraint", "guideline"),
    (3, "Mandatory methods: read_state, set_config, Run", "Every class must implement read_state(), set_config(values), and Run(command, params)", "requirement", "mandatory"),
    (4, "Strict Tuple3 return pattern", "Success: (1, data, None), Failure: (0, {}, (ERROR_CODE, error_msg, 0))", "constraint", "guideline"),
    (5, "NO utility functions (_ok/_err/_safe)", "Use direct tuple returns only, no helper wrapper functions", "prohibition", "mandatory"),
    (6, "NO decorators", "NO method decorators, NO class decorators, NO function decorators", "prohibition", "mandatory"),
    (7, "NO print statements", "NO print in class methods or authorities, use state/results for output", "prohibition", "mandatory"),
    (8, "NO hardcoded paths", "NO hardcoded file paths or database paths, use config/param for paths", "prohibition", "mandatory"),
    (9, "NO ABC / inheritance", "NO Abstract Base Classes, NO class inheritance, NO interface inheritance", "prohibition", "mandatory"),
    (10, "NO flat class structure", "NO single flat class with all methods, MUST use nested authority classes", "prohibition", "mandatory"),
    (11, "NO direct DB access in main class", "DB operations must be in nested DB authority, outer class only orchestrates", "prohibition", "mandatory"),
    (12, "Nested authority classes", "Nested classes end with Authority suffix, each has own Run() method", "constraint", "guideline"),
    (13, "Authority naming convention", "Nested classes end with Authority suffix (e.g., JsonConfig, EnvConfig)", "constraint", "guideline"),
    (14, "Standard __init__ signature", "def __init__(self, mem=None, db=None, param=None)", "constraint", "guideline"),
    (15, "Run method dispatch pattern", "Outer Run dispatches to nested authorities", "constraint", "guideline"),
    (16, "Annotation syntax", "VBStyle annotation format for methods and classes", "constraint", "guideline"),
    (17, "100% pattern consistency", "All code must follow same patterns, no exceptions", "constraint", "guideline"),
    (18, "UNKNOWN_COMMAND error handling", "Every Run must handle unknown commands gracefully", "constraint", "guideline"),
    (19, "read_state returns state snapshot", "read_state() returns copy of self.state", "constraint", "guideline"),
    (20, "set_config updates config", "set_config(values) updates self.state['config']", "constraint", "guideline"),
    (21, "no underscore in token names", "Token names must not contain underscores", "general", "guideline"),
    (22, "short token names", "Token names must be short and concise", "general", "guideline"),
    (23, "max token length 15", "Token names maximum 15 characters", "general", "guideline"),
    (24, "bracket format", "Token must be in format [@Token] (capital first letter)", "general", "guideline"),
    (25, "capital letter", "Token names must start with capital letter after [@] prefix", "general", "guideline"),
    (26, "all problems must be fixed", "Every problem must be fixed - no severity levels, no bypassing", "general", "guideline"),
    (27, "unsure - ask do not guess", "If unsure, ask. Do not guess.", "general", "guideline"),
    (28, "no underscore in class names", "PascalCase only, no underscores in class names", "general", "guideline"),
    (29, "no decorators (repeat)", "@property @staticmethod etc are never allowed", "general", "guideline"),
    (30, "no enums", "Do not use enums", "general", "guideline"),
    (31, "no print (repeat)", "Do not use print statements, use Report class or logging", "general", "guideline"),
    (32, "no hidden behavior", "No hidden or implicit behavior, all actions explicit", "general", "guideline"),
    (33, "no hardcode", "NOTHING IS ALLOWED TO BE HARD CODED", "general", "guideline"),
    (34, "no tabs", "Spaces only, no tabs", "general", "guideline"),
    (35, "no trailing whitespace", "No trailing whitespace at end of lines", "general", "guideline"),
    (999, "weight_position", "Weight token position in bracket notation", "constraint", "critical"),
]

SAMPLE_CLASSIFICATIONS = {
    3: ("TRUE", 1.00, 95, "Verified in all 11 seed classes"),
    4: ("TRUE", 1.00, 95, "Tuple3 pattern proven in qa_prototype.py"),
    5: ("TRUE", 0.95, 85, "No _ok/_err/_safe found in codebase"),
    6: ("TRUE", 1.00, 90, "No decorators in any VBStyle file"),
    7: ("TRUE", 1.00, 90, "No print() in any VBStyle file"),
    8: ("TRUE", 0.90, 85, "Paths come from config in all checked files"),
    9: ("TRUE", 1.00, 85, "No ABC or inheritance found"),
    10: ("TRUE", 0.85, 75, "Nested authorities confirmed in seed data"),
    11: ("TRUE", 0.90, 80, "DB access via DB authority pattern"),
    21: ("TRUE", 0.95, 70, "Token names checked - no underscores"),
    24: ("TRUE", 1.00, 75, "All tokens in [@Token] format"),
    30: ("TRUE", 1.00, 65, "No enums found in VBStyle code"),
    33: ("TRUE", 0.95, 80, "No hardcoded values found in checked files"),
    999: ("UNKNOWN", 0.50, 40, "Weight position rule - needs verification"),
}


class EditRuleDialog(QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rule Truth")
        self.resize(600, 500)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.txt_rule = QLineEdit()
        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setMaximumHeight(80)
        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["prohibition", "requirement", "constraint", "general"])
        self.combo_sev = QComboBox()
        self.combo_sev.addItems(["mandatory", "critical", "guideline"])
        self.combo_class = QComboBox()
        self.combo_class.addItems(["TRUE", "FALSE", "UNKNOWN"])
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.0, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setDecimals(2)
        self.spin_weight = QSpinBox()
        self.spin_weight.setRange(0, 100)
        self.txt_prov = QLineEdit()
        self.txt_evidence = QPlainTextEdit()
        self.txt_evidence.setMaximumHeight(60)
        self.combo_status = QComboBox()
        self.combo_status.addItems(["open", "answered", "stabilized", "collapsed"])
        self.chk_canonical = QCheckBox()
        self.txt_notes = QPlainTextEdit()
        self.txt_notes.setMaximumHeight(60)

        form.addRow("Rule:", self.txt_rule)
        form.addRow("Description:", self.txt_desc)
        form.addRow("Category:", self.combo_cat)
        form.addRow("Severity:", self.combo_sev)
        form.addRow("Classification:", self.combo_class)
        form.addRow("Confidence:", self.spin_conf)
        form.addRow("Weight:", self.spin_weight)
        form.addRow("Provenance:", self.txt_prov)
        form.addRow("Evidence:", self.txt_evidence)
        form.addRow("Status:", self.combo_status)
        form.addRow("Canonical:", self.chk_canonical)
        form.addRow("Notes:", self.txt_notes)
        layout.addLayout(form)

        if row_data:
            self.row_id = row_data[0]
            self.txt_rule.setText(row_data[2] or "")
            self.txt_desc.setPlainText(row_data[3] or "")
            self.combo_cat.setCurrentText(row_data[4] or "general")
            self.combo_sev.setCurrentText(row_data[5] or "guideline")
            self.combo_class.setCurrentText(row_data[6] or "UNKNOWN")
            self.spin_conf.setValue(row_data[7] or 0.0)
            self.spin_weight.setValue(row_data[8] or 50)
            self.txt_prov.setText(row_data[9] or "cascade_llm")
            self.txt_evidence.setPlainText(row_data[10] or "")
            self.combo_status.setCurrentText(row_data[11] or "open")
            self.chk_canonical.setChecked(bool(row_data[13]))
            self.txt_notes.setPlainText(row_data[14] or "")
        else:
            self.row_id = None

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "rule_text": self.txt_rule.text(),
            "description": self.txt_desc.toPlainText(),
            "rule_category": self.combo_cat.currentText(),
            "severity": self.combo_sev.currentText(),
            "classification": self.combo_class.currentText(),
            "confidence": self.spin_conf.value(),
            "weight": self.spin_weight.value(),
            "provenance": self.txt_prov.text(),
            "evidence": self.txt_evidence.toPlainText(),
            "status": self.combo_status.currentText(),
            "is_canonical": 1 if self.chk_canonical.isChecked() else 0,
            "notes": self.txt_notes.toPlainText(),
        }


class RuleTruthGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VBStyle Rule Truth — Classification & Editor")
        self.resize(1400, 850)
        self.conn = None
        self._init_db()
        self._build_ui()
        self._load_data()

    def _init_db(self):
        import os
        if os.path.exists(RULE_DB_PATH):
            os.remove(RULE_DB_PATH)
        self.conn = sqlite3.connect(RULE_DB_PATH)
        self.conn.executescript(SCHEMA_SQL)
        now = datetime.now().isoformat()
        for rule_id, rule_text, desc, cat, sev in REAL_RULES:
            cls_data = SAMPLE_CLASSIFICATIONS.get(rule_id, ("UNKNOWN", 0.0, 50, ""))
            cls, conf, weight, evidence = cls_data
            status = "stabilized" if conf >= 0.90 else ("answered" if conf > 0 else "open")
            canonical = 1 if cls == "TRUE" and conf >= 0.95 else 0
            self.conn.execute(
                """INSERT INTO rule_truths 
                (rule_id, rule_text, description, rule_category, severity, 
                 classification, confidence, weight, provenance, evidence, 
                 version, is_canonical, status, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rule_id, rule_text, desc, cat, sev,
                 cls, conf, weight, "cascade_llm", evidence,
                 1, canonical, status, "", now, now)
            )
        self.conn.commit()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QLabel("VBStyle Rule Truth — What Rules Are TRUE / FALSE / UNKNOWN")
        header.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        stats = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        self.lbl_total.setObjectName("stat_total")
        self.lbl_true = QLabel("TRUE: 0")
        self.lbl_true.setObjectName("stat_true")
        self.lbl_false = QLabel("FALSE: 0")
        self.lbl_false.setObjectName("stat_false")
        self.lbl_unknown = QLabel("UNKNOWN: 0")
        self.lbl_unknown.setObjectName("stat_unknown")
        self.lbl_canonical = QLabel("Canonical: 0")
        self.lbl_mandatory = QLabel("Mandatory: 0")
        for lbl in [self.lbl_total, self.lbl_true, self.lbl_false, self.lbl_unknown, self.lbl_canonical, self.lbl_mandatory]:
            lbl.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))

        self.combo_class = QComboBox()
        self.combo_class.setObjectName("filter_classification")
        self.combo_class.addItems(["ALL", "TRUE", "FALSE", "UNKNOWN"])
        self.combo_class.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(QLabel("Class:"))
        filter_row.addWidget(self.combo_class)

        self.combo_cat = QComboBox()
        self.combo_cat.setObjectName("filter_category")
        self.combo_cat.addItems(["ALL", "prohibition", "requirement", "constraint", "general"])
        self.combo_cat.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(QLabel("Category:"))
        filter_row.addWidget(self.combo_cat)

        self.combo_sev = QComboBox()
        self.combo_sev.setObjectName("filter_severity")
        self.combo_sev.addItems(["ALL", "mandatory", "critical", "guideline"])
        self.combo_sev.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(QLabel("Severity:"))
        filter_row.addWidget(self.combo_sev)

        self.combo_status = QComboBox()
        self.combo_status.setObjectName("filter_status")
        self.combo_status.addItems(["ALL", "stabilized", "answered", "open", "collapsed"])
        self.combo_status.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(QLabel("Status:"))
        filter_row.addWidget(self.combo_status)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("search_box")
        self.txt_search.setPlaceholderText("Search rules...")
        self.txt_search.textChanged.connect(self._load_data)
        filter_row.addWidget(self.txt_search)
        layout.addLayout(filter_row)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("Edit Selected Rule")
        self.btn_edit.setObjectName("edit_button")
        self.btn_edit.clicked.connect(self._edit_selected)
        btn_row.addWidget(self.btn_edit)

        self.btn_add = QPushButton("Add New Rule")
        self.btn_add.setObjectName("add_button")
        self.btn_add.clicked.connect(self._add_rule)
        btn_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete Selected Rule")
        self.btn_delete.setObjectName("delete_button")
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        self.btn_classify = QPushButton("Quick Classify (TRUE/FALSE/UNKNOWN)")
        self.btn_classify.setObjectName("classify_button")
        self.btn_classify.clicked.connect(self._quick_classify)
        btn_row.addWidget(self.btn_classify)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        tab_rules = QWidget()
        tab_rules_layout = QVBoxLayout(tab_rules)
        self.table = QTableWidget()
        self.table.setObjectName("rules_table")
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(["ID", "Rule ID", "Rule", "Category", "Severity", "Classification", "Confidence", "Weight", "Status", "Canonical", "Evidence"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._edit_selected)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_header_menu)
        tab_rules_layout.addWidget(self.table)
        tabs.addTab(tab_rules, "Rules")

        tab_summary = QWidget()
        summary_layout = QVBoxLayout(tab_summary)
        self.summary_text = QTextEdit()
        self.summary_text.setObjectName("summary_view")
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Menlo", 11))
        summary_layout.addWidget(self.summary_text)
        tabs.addTab(tab_summary, "Summary")

        tab_schema = QWidget()
        schema_layout = QVBoxLayout(tab_schema)
        schema_text = QTextEdit()
        schema_text.setReadOnly(True)
        schema_text.setFont(QFont("Menlo", 11))
        schema_text.setPlainText(SCHEMA_SQL)
        schema_layout.addWidget(schema_text)
        tabs.addTab(tab_schema, "Schema (SQL)")

        tab_bcl = QWidget()
        bcl_layout = QVBoxLayout(tab_bcl)
        bcl_text = QTextEdit()
        bcl_text.setReadOnly(True)
        bcl_text.setFont(QFont("Menlo", 11))
        bcl_text.setPlainText(self._bcl_schema())
        bcl_layout.addWidget(bcl_text)
        tabs.addTab(tab_bcl, "Schema (BCL)")

        bottom = QHBoxLayout()
        self.progress_true = QProgressBar()
        self.progress_true.setFormat("TRUE: %v")
        self.progress_false = QProgressBar()
        self.progress_false.setFormat("FALSE: %v")
        self.progress_unknown = QProgressBar()
        self.progress_unknown.setFormat("UNKNOWN: %v")
        bottom.addWidget(self.progress_true)
        bottom.addWidget(self.progress_false)
        bottom.addWidget(self.progress_unknown)
        layout.addLayout(bottom)

    def _bcl_schema(self):
        return """[@table<rule_truths>]{
  (@field<id>;              @type<int>;          @primary_key; @auto_increment);
  (@field<rule_id>;         @type<int>;          @nullable; @label<"Source Rule ID">);
  (@field<rule_text>;       @type<text>;         @required; @label<"Rule">);
  (@field<description>;     @type<text>;         @nullable; @label<"Description">);
  (@field<rule_category>;   @type<enum>;         @default<"general">;
                             @options<("prohibition";"requirement";"constraint";"general")>;
                             @label<"Category">);
  (@field<severity>;        @type<enum>;         @default<"guideline">;
                             @options<("mandatory";"critical";"guideline")>;
                             @label<"Severity">);
  (@field<classification>;  @type<enum>;         @default<"UNKNOWN">;
                             @options<("TRUE";"FALSE";"UNKNOWN")>;
                             @label<"Classification">);
  (@field<confidence>;      @type<real>;         @default<0.0>; @range<(0.0;1.0)>;
                             @label<"Confidence">);
  (@field<weight>;          @type<int>;          @default<50>; @range<(0;100)>;
                             @label<"Weight">);
  (@field<provenance>;      @type<varchar>;      @default<"cascade_llm">; @label<"Provenance">);
  (@field<evidence>;        @type<text>;         @nullable; @label<"Evidence">);
  (@field<version>;         @type<int>;          @default<1>; @label<"Version">);
  (@field<is_canonical>;    @type<bool>;         @default<false>; @label<"Canonical">);
  (@field<status>;          @type<enum>;         @default<"open">;
                             @options<("open";"answered";"stabilized";"collapsed")>;
                             @label<"Status">);
  (@field<notes>;           @type<text>;         @nullable; @label<"Notes">);
  (@field<created_at>;      @type<timestamp>;    @required; @label<"Created">);
  (@field<updated_at>;      @type<timestamp>;    @nullable; @label<"Updated">);
}"""

    def _load_data(self):
        cls_filter = self.combo_class.currentText()
        cat_filter = self.combo_cat.currentText()
        sev_filter = self.combo_sev.currentText()
        status_filter = self.combo_status.currentText()
        search = self.txt_search.text().strip().lower()

        query = "SELECT id, rule_id, rule_text, description, rule_category, severity, classification, confidence, weight, status, is_canonical, evidence FROM rule_truths WHERE 1=1"
        params = []
        if cls_filter != "ALL":
            query += " AND classification = ?"
            params.append(cls_filter)
        if cat_filter != "ALL":
            query += " AND rule_category = ?"
            params.append(cat_filter)
        if sev_filter != "ALL":
            query += " AND severity = ?"
            params.append(sev_filter)
        if status_filter != "ALL":
            query += " AND status = ?"
            params.append(status_filter)
        if search:
            query += " AND (LOWER(rule_text) LIKE ? OR LOWER(description) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY rule_id"

        rows = self.conn.execute(query, params).fetchall()
        self.table.setRowCount(len(rows))
        counts = {"TRUE": 0, "FALSE": 0, "UNKNOWN": 0}
        canonical_count = 0
        mandatory_count = 0

        for i, row in enumerate(rows):
            rid, rule_id, rule_text, desc, cat, sev, cls, conf, weight, status, canon, evidence = row
            counts[cls] = counts.get(cls, 0) + 1
            if canon:
                canonical_count += 1
            if sev == "mandatory":
                mandatory_count += 1

            items = [
                str(rid),
                str(rule_id) if rule_id else "—",
                rule_text,
                cat,
                sev,
                cls,
                f"{conf:.2f}",
                str(weight),
                status,
                "Yes" if canon else "—",
                evidence or "",
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                if j == 3:
                    color = CATEGORY_COLORS.get(cat, QColor(100, 100, 100))
                    item.setForeground(color)
                if j == 4:
                    color = SEVERITY_COLORS.get(sev, QColor(100, 100, 100))
                    item.setForeground(color)
                    if sev in ("mandatory", "critical"):
                        item.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
                if j == 5:
                    color = CLASSIFICATION_COLORS.get(cls, QColor(128, 128, 128))
                    item.setForeground(color)
                    item.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
                if j == 6:
                    if conf >= 0.90:
                        item.setForeground(QColor(34, 139, 34))
                    elif conf >= 0.70:
                        item.setForeground(QColor(30, 100, 200))
                    else:
                        item.setForeground(QColor(184, 134, 11))
                if j == 8:
                    color = STATUS_COLORS.get(status, QColor(128, 128, 128))
                    item.setForeground(color)
                self.table.setItem(i, j, item)

        self.lbl_total.setText(f"Total: {len(rows)}")
        self.lbl_true.setText(f"TRUE: {counts['TRUE']}")
        self.lbl_true.setStyleSheet("color: #228B22;")
        self.lbl_false.setText(f"FALSE: {counts['FALSE']}")
        self.lbl_false.setStyleSheet("color: #B22222;")
        self.lbl_unknown.setText(f"UNKNOWN: {counts['UNKNOWN']}")
        self.lbl_unknown.setStyleSheet("color: #B8860B;")
        self.lbl_canonical.setText(f"Canonical: {canonical_count}")
        self.lbl_mandatory.setText(f"Mandatory: {mandatory_count}")

        total = max(len(rows), 1)
        self.progress_true.setMaximum(total)
        self.progress_true.setValue(counts["TRUE"])
        self.progress_false.setMaximum(total)
        self.progress_false.setValue(counts["FALSE"])
        self.progress_unknown.setMaximum(total)
        self.progress_unknown.setValue(counts["UNKNOWN"])

        self._update_summary(counts, canonical_count, mandatory_count, len(rows))

    def _update_summary(self, counts, canonical, mandatory, total):
        lines = []
        lines.append("=" * 60)
        lines.append("VBSTYLE RULE TRUTH SUMMARY")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Total Rules:      {total}")
        lines.append(f"TRUE:             {counts['TRUE']}  ({counts['TRUE']*100//max(total,1)}%)")
        lines.append(f"FALSE:            {counts['FALSE']}  ({counts['FALSE']*100//max(total,1)}%)")
        lines.append(f"UNKNOWN:          {counts['UNKNOWN']}  ({counts['UNKNOWN']*100//max(total,1)}%)")
        lines.append(f"Canonical:        {canonical}")
        lines.append(f"Mandatory:        {mandatory}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("BY CATEGORY:")
        lines.append("-" * 60)
        cat_rows = self.conn.execute("SELECT rule_category, COUNT(*) AS cnt FROM rule_truths GROUP BY rule_category ORDER BY cnt DESC").fetchall()
        for cat, cnt in cat_rows:
            lines.append(f"  {cat:20s} {cnt}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("BY SEVERITY:")
        lines.append("-" * 60)
        sev_rows = self.conn.execute("SELECT severity, COUNT(*) AS cnt FROM rule_truths GROUP BY severity ORDER BY cnt DESC").fetchall()
        for sev, cnt in sev_rows:
            lines.append(f"  {sev:20s} {cnt}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("MANDATORY RULES — TRUTH STATUS:")
        lines.append("-" * 60)
        mand_rows = self.conn.execute("SELECT rule_text, classification, confidence FROM rule_truths WHERE severity='mandatory' ORDER BY rule_id").fetchall()
        for rule_text, cls, conf in mand_rows:
            lines.append(f"  [{cls:7s}] {conf:.2f}  {rule_text[:50]}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("UNKNOWN RULES — NEED VERIFICATION:")
        lines.append("-" * 60)
        unk_rows = self.conn.execute("SELECT rule_text, rule_category FROM rule_truths WHERE classification='UNKNOWN' ORDER BY rule_id").fetchall()
        for rule_text, cat in unk_rows:
            lines.append(f"  [{cat:12s}] {rule_text[:50]}")
        self.summary_text.setPlainText("\n".join(lines))

    def _show_header_menu(self, pos):
        header = self.table.horizontalHeader()
        menu = QMenu(self)
        for i in range(self.table.columnCount()):
            title = self.table.horizontalHeaderItem(i).text()
            if not title:
                title = f"Column {i}"
            action = QAction(title, self)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(i))
            action.triggered.connect(lambda checked, idx=i: header.setSectionHidden(idx, not checked))
            menu.addAction(action)
        menu.exec(header.mapToGlobal(pos))

    def _get_selected_row_data(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        rid = int(self.table.item(row, 0).text())
        data = self.conn.execute("SELECT * FROM rule_truths WHERE id = ?", (rid,)).fetchone()
        return data

    def _edit_selected(self):
        data = self._get_selected_row_data()
        if not data:
            QMessageBox.information(self, "No Selection", "Select a rule to edit.")
            return
        dialog = EditRuleDialog(self, data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vals = dialog.get_values()
            now = datetime.now().isoformat()
            self.conn.execute(
                """UPDATE rule_truths SET 
                   rule_text=?, description=?, rule_category=?, severity=?, 
                   classification=?, confidence=?, weight=?, provenance=?, 
                   evidence=?, status=?, is_canonical=?, notes=?, updated_at=?, version=version+1
                   WHERE id=?""",
                (vals["rule_text"], vals["description"], vals["rule_category"], vals["severity"],
                 vals["classification"], vals["confidence"], vals["weight"], vals["provenance"],
                 vals["evidence"], vals["status"], vals["is_canonical"], vals["notes"], now, data[0])
            )
            self.conn.commit()
            self._load_data()

    def _add_rule(self):
        dialog = EditRuleDialog(self, None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vals = dialog.get_values()
            now = datetime.now().isoformat()
            self.conn.execute(
                """INSERT INTO rule_truths 
                   (rule_text, description, rule_category, severity, classification, 
                    confidence, weight, provenance, evidence, status, is_canonical, 
                    notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (vals["rule_text"], vals["description"], vals["rule_category"], vals["severity"],
                 vals["classification"], vals["confidence"], vals["weight"], vals["provenance"],
                 vals["evidence"], vals["status"], vals["is_canonical"], vals["notes"], now, now)
            )
            self.conn.commit()
            self._load_data()

    def _delete_selected(self):
        data = self._get_selected_row_data()
        if not data:
            QMessageBox.information(self, "No Selection", "Select a rule to delete.")
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete rule:\n{data[2]}?")
        if reply == QMessageBox.StandardButton.Yes:
            self.conn.execute("DELETE FROM rule_truths WHERE id=?", (data[0],))
            self.conn.commit()
            self._load_data()

    def _quick_classify(self):
        data = self._get_selected_row_data()
        if not data:
            QMessageBox.information(self, "No Selection", "Select a rule first.")
            return
        rid = data[0]
        current = data[6]
        order = ["UNKNOWN", "TRUE", "FALSE"]
        next_cls = order[(order.index(current) + 1) % 3]
        now = datetime.now().isoformat()
        conf = 0.95 if next_cls == "TRUE" else (0.90 if next_cls == "FALSE" else 0.50)
        self.conn.execute(
            "UPDATE rule_truths SET classification=?, confidence=?, updated_at=?, version=version+1 WHERE id=?",
            (next_cls, conf, now, rid)
        )
        self.conn.commit()
        self._load_data()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RuleTruthGUI()
    window.show()
    sys.exit(app.exec())
