"""
Fact Store Mock GUI
Shows the proposed fact_truths table with sample data.
Run: python3 fact_store_mock.py
"""

import sys
import sqlite3
import random
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QComboBox, QLineEdit, QGroupBox, QFormLayout,
    QTabWidget, QTextEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QAction


FACT_DB_PATH = "/tmp/fact_store_mock.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fact_truths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assertion       TEXT NOT NULL,
    classification  TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence      REAL NOT NULL DEFAULT 0.0,
    weight          INTEGER NOT NULL DEFAULT 50,
    provenance      TEXT NOT NULL DEFAULT 'qwen_1.5b',
    source_query    TEXT,
    evidence        TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    is_canonical    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'open',
    contradicts_id  INTEGER,
    created_at      TEXT NOT NULL,
    validated_at    TEXT,
    collapsed_at    TEXT
);

CREATE TABLE IF NOT EXISTS fact_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_fact_id    INTEGER NOT NULL,
    to_fact_id      INTEGER NOT NULL,
    relation        TEXT NOT NULL,
    weight          INTEGER DEFAULT 50,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (from_fact_id) REFERENCES fact_truths(id),
    FOREIGN KEY (to_fact_id) REFERENCES fact_truths(id)
);
"""

SAMPLE_FACTS = [
    ("System has persistent memory - check existing state before requesting changes",
     "TRUE", 1.00, 95, "cascade_llm", "What does the system do with state?", "Verified across 50+ sessions", "stabilized", 1),
    ("Full conversation ingestion with permanent storage and reuse",
     "TRUE", 1.00, 90, "cascade_llm", "How are conversations stored?", "Ingestion pipeline proven", "stabilized", 1),
    ("WHEN/WHEN NOT rules are executable conditions, not descriptions",
     "TRUE", 1.00, 85, "cascade_llm", "Are WHEN rules descriptive or executable?", "Code execution verified", "stabilized", 1),
    ("System ASSEMBLES GUIs from learned design rules conditioned on context",
     "TRUE", 0.95, 80, "cascade_llm", "Does the system generate or assemble GUIs?", "GuiSystem engine.py proven", "stabilized", 1),
    ("Learning is concrete: correction -> storage -> reuse",
     "TRUE", 1.00, 85, "cascade_llm", "How does learning work?", "learned_rules table has 10,540 entries", "stabilized", 1),
    ("Mode D (Qwen 1.5B) achieves 89% answer accuracy",
     "TRUE", 0.89, 75, "qwen_1.5b", "What is Mode D accuracy?", "28-question benchmark, 25/28 correct", "answered", 0),
    ("Mode B (BERT QA) achieves 57% answer accuracy",
     "TRUE", 0.57, 60, "bert_squad", "What is Mode B accuracy?", "28-question benchmark, 16/28 correct", "answered", 0),
    ("Mode C (BERT + LLM format) improves over Mode B",
     "FALSE", 0.93, 70, "qwen_1.5b", "Does LLM formatting improve BERT results?", "Mode C = Mode B, 0% gain, 12ms overhead", "answered", 0),
    ("Qwen never hallucinates on unknown questions",
     "TRUE", 1.00, 85, "qwen_1.5b", "Does Qwen hallucinate on unknowns?", "4/4 correct NOT FOUND, 0% false positive", "stabilized", 1),
    ("BERT extracts from wrong context on unknown questions",
     "TRUE", 0.75, 65, "bert_squad", "Does BERT hallucinate on unknowns?", "1/4 correct, 33% false positive rate", "answered", 0),
    ("JSON is acceptable for internal config storage",
     "FALSE", 1.00, 95, "cascade_llm", "Can we use JSON for config?", "Decision locked: No JSON. BCL only.", "stabilized", 1),
    ("print() statements are allowed in VBStyle code",
     "FALSE", 1.00, 90, "cascade_llm", "Are print statements allowed?", "Prohibition rule. No exceptions.", "stabilized", 1),
    ("Class inheritance is permitted in VBStyle",
     "FALSE", 1.00, 85, "cascade_llm", "Can we use inheritance?", "Prohibition rule. No ABCs.", "stabilized", 1),
    ("The system uses auto-routing for query mode selection",
     "UNKNOWN", 0.50, 40, "cascade_llm", "Is auto-routing implemented?", "Open question A.17 - pending decision", "open", 0),
    ("Fact Store should be a separate SQLite database",
     "UNKNOWN", 0.30, 35, "cascade_llm", "Where should Fact Store live?", "Resolved: already in vb_shared MySQL", "open", 0),
    ("Qwen 1.5B can replace BERT entirely for all QA tasks",
     "FALSE", 0.79, 70, "qwen_1.5b", "Can Qwen replace BERT?", "BERT wins near-miss disambiguation 100% vs 50%", "answered", 0),
    ("Context vectors determine which rules activate",
     "TRUE", 1.00, 80, "cascade_llm", "How are rules activated?", "Verified in rule_tokens and runtime_context", "stabilized", 1),
    ("The collapse algorithm requires categories_covered >= 3",
     "TRUE", 0.95, 75, "cascade_llm", "What triggers collapse?", "Coverage gate: Nut vs Plastic guardrail", "answered", 0),
    ("All existing know_nodes data should be discarded",
     "UNKNOWN", 0.20, 30, "cascade_llm", "Should we start fresh?", "Open question C.8 - pending decision", "open", 0),
    ("Stability score = coverage(30%) + confidence(30%) + depth(20%) + consistency(20%)",
     "TRUE", 0.95, 70, "cascade_llm", "What is the stability formula?", "6-phase collapse algorithm spec", "answered", 0),
]

SAMPLE_EDGES = [
    (1, 3, "supports", 80),
    (2, 1, "supports", 75),
    (6, 7, "contradicts", 60),
    (9, 10, "contradicts", 85),
    (6, 8, "supports", 70),
    (11, 12, "relatedTo", 50),
    (12, 13, "relatedTo", 50),
    (11, 13, "relatedTo", 50),
    (16, 6, "contradicts", 65),
    (17, 18, "supports", 60),
]


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


class FactStoreGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fact Store — Truth Classification System (Mock)")
        self.resize(1400, 850)
        self.conn = None
        self._init_db()
        self._build_ui()
        self._load_data()

    def _init_db(self):
        import os
        if os.path.exists(FACT_DB_PATH):
            os.remove(FACT_DB_PATH)
        self.conn = sqlite3.connect(FACT_DB_PATH)
        self.conn.executescript(SCHEMA_SQL)
        now = datetime.now().isoformat()
        for i, (assertion, cls, conf, weight, prov, query, evidence, status, canon) in enumerate(SAMPLE_FACTS):
            self.conn.execute(
                "INSERT INTO fact_truths (assertion, classification, confidence, weight, provenance, source_query, evidence, version, is_canonical, status, created_at, validated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (assertion, cls, conf, weight, prov, query, evidence, 1, canon, status, now, now if status != "open" else None)
            )
        for from_id, to_id, rel, w in SAMPLE_EDGES:
            self.conn.execute(
                "INSERT INTO fact_edges (from_fact_id, to_fact_id, relation, weight, created_at) VALUES (?,?,?,?,?)",
                (from_id, to_id, rel, w, now)
            )
        self.conn.commit()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QLabel("Fact Store — Truth Classification Table (Mock GUI)")
        header.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        stats = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        self.lbl_true = QLabel("TRUE: 0")
        self.lbl_false = QLabel("FALSE: 0")
        self.lbl_unknown = QLabel("UNKNOWN: 0")
        self.lbl_canonical = QLabel("Canonical: 0")
        self.lbl_stabilized = QLabel("Stabilized: 0")
        for lbl in [self.lbl_total, self.lbl_true, self.lbl_false, self.lbl_unknown, self.lbl_canonical, self.lbl_stabilized]:
            lbl.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.combo_class = QComboBox()
        self.combo_class.addItems(["ALL", "TRUE", "FALSE", "UNKNOWN"])
        self.combo_class.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_class)

        self.combo_status = QComboBox()
        self.combo_status.addItems(["ALL", "stabilized", "answered", "open", "collapsed"])
        self.combo_status.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_status)

        self.combo_prov = QComboBox()
        self.combo_prov.addItems(["ALL", "qwen_1.5b", "bert_squad", "cascade_llm"])
        self.combo_prov.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_prov)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search assertions...")
        self.txt_search.textChanged.connect(self._load_data)
        filter_row.addWidget(self.txt_search)
        layout.addLayout(filter_row)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        tab_facts = QWidget()
        tab_facts_layout = QVBoxLayout(tab_facts)
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID", "Assertion", "Classification", "Confidence", "Weight", "Provenance", "Status", "Canonical", "Version", "Validated"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._on_row_select)
        tab_facts_layout.addWidget(self.table)
        tabs.addTab(tab_facts, "Facts")

        tab_edges = QWidget()
        edges_layout = QVBoxLayout(tab_edges)
        self.edges_table = QTableWidget()
        self.edges_table.setColumnCount(5)
        self.edges_table.setHorizontalHeaderLabels(["Edge ID", "From Fact", "To Fact", "Relation", "Weight"])
        self.edges_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.edges_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        edges_layout.addWidget(self.edges_table)
        tabs.addTab(tab_edges, "Edges (Contradictions & Support)")

        tab_detail = QWidget()
        detail_layout = QVBoxLayout(tab_detail)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Menlo", 12))
        detail_layout.addWidget(self.detail_text)
        tabs.addTab(tab_detail, "Detail View")

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
        self.progress_true.setFormat("TRUE: %v%")
        self.progress_false = QProgressBar()
        self.progress_false.setFormat("FALSE: %v%")
        self.progress_unknown = QProgressBar()
        self.progress_unknown.setFormat("UNKNOWN: %v%")
        bottom.addWidget(self.progress_true)
        bottom.addWidget(self.progress_false)
        bottom.addWidget(self.progress_unknown)
        layout.addLayout(bottom)

    def _bcl_schema(self):
        return """[@table<fact_truths>]{
  (@field<id>;            @type<int>;          @primary_key; @auto_increment);
  (@field<assertion>;     @type<text>;         @required; @label<"Assertion">);
  (@field<classification>;@type<enum>;         @default<"UNKNOWN">; @options<("TRUE";"FALSE";"UNKNOWN")>;
                           @label<"Classification">);
  (@field<confidence>;    @type<real>;         @default<0.0>; @range<(0.0;1.0)>;
                           @label<"Confidence">);
  (@field<weight>;        @type<int>;          @default<50>; @range<(0;100)>;
                           @label<"Weight">);
  (@field<provenance>;    @type<varchar>;      @default<"qwen_1.5b">; @label<"Provenance">);
  (@field<source_query>;  @type<text>;         @label<"Source Query">);
  (@field<evidence>;      @type<text>;         @label<"Evidence">);
  (@field<version>;       @type<int>;          @default<1>; @label<"Version">);
  (@field<is_canonical>;  @type<bool>;         @default<false>; @label<"Canonical">);
  (@field<status>;        @type<enum>;         @default<"open">;
                           @options<("open";"answered";"stabilized";"collapsed")>;
                           @label<"Status">);
  (@field<contradicts_id>;@type<int>;          @nullable; @label<"Contradicts">);
  (@field<created_at>;    @type<timestamp>;    @required; @label<"Created">);
  (@field<validated_at>;  @type<timestamp>;    @nullable; @label<"Validated">);
  (@field<collapsed_at>;  @type<timestamp>;    @nullable; @label<"Collapsed">);
}

[@table<fact_edges>]{
  (@field<id>;            @type<int>;          @primary_key; @auto_increment);
  (@field<from_fact_id>;  @type<int>;          @required; @fk<"fact_truths.id">);
  (@field<to_fact_id>;    @type<int>;          @required; @fk<"fact_truths.id">);
  (@field<relation>;      @type<enum>;         @required;
                           @options<("supports";"contradicts";"refines";"supersedes";"relatedTo")>);
  (@field<weight>;        @type<int>;          @default<50>; @range<(0;100)>);
  (@field<created_at>;    @type<timestamp>;    @required);
}"""

    def _load_data(self):
        cls_filter = self.combo_class.currentText()
        status_filter = self.combo_status.currentText()
        prov_filter = self.combo_prov.currentText()
        search = self.txt_search.text().strip().lower()

        query = "SELECT id, assertion, classification, confidence, weight, provenance, status, is_canonical, version, validated_at FROM fact_truths WHERE 1=1"
        params = []
        if cls_filter != "ALL":
            query += " AND classification = ?"
            params.append(cls_filter)
        if status_filter != "ALL":
            query += " AND status = ?"
            params.append(status_filter)
        if prov_filter != "ALL":
            query += " AND provenance = ?"
            params.append(prov_filter)
        if search:
            query += " AND LOWER(assertion) LIKE ?"
            params.append(f"%{search}%")
        query += " ORDER BY id"

        rows = self.conn.execute(query, params).fetchall()
        self.table.setRowCount(len(rows))
        counts = {"TRUE": 0, "FALSE": 0, "UNKNOWN": 0}
        canonical_count = 0
        stabilized_count = 0

        for i, row in enumerate(rows):
            fid, assertion, cls, conf, weight, prov, status, canon, version, validated = row
            counts[cls] = counts.get(cls, 0) + 1
            if canon:
                canonical_count += 1
            if status == "stabilized":
                stabilized_count += 1

            items = [
                str(fid),
                assertion,
                cls,
                f"{conf:.2f}",
                str(weight),
                prov,
                status,
                "Yes" if canon else "—",
                str(version),
                validated[:10] if validated else "—",
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                if j == 2:
                    color = CLASSIFICATION_COLORS.get(cls, QColor(128, 128, 128))
                    item.setForeground(color)
                    item.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
                if j == 6:
                    color = STATUS_COLORS.get(status, QColor(128, 128, 128))
                    item.setForeground(color)
                if j == 3:
                    if conf >= 0.90:
                        item.setForeground(QColor(34, 139, 34))
                    elif conf >= 0.70:
                        item.setForeground(QColor(30, 100, 200))
                    else:
                        item.setForeground(QColor(184, 134, 11))
                self.table.setItem(i, j, item)

        self.lbl_total.setText(f"Total: {len(rows)}")
        self.lbl_true.setText(f"TRUE: {counts['TRUE']}")
        self.lbl_true.setStyleSheet("color: #228B22;")
        self.lbl_false.setText(f"FALSE: {counts['FALSE']}")
        self.lbl_false.setStyleSheet("color: #B22222;")
        self.lbl_unknown.setText(f"UNKNOWN: {counts['UNKNOWN']}")
        self.lbl_unknown.setStyleSheet("color: #B8860B;")
        self.lbl_canonical.setText(f"Canonical: {canonical_count}")
        self.lbl_stabilized.setText(f"Stabilized: {stabilized_count}")

        total = max(len(rows), 1)
        self.progress_true.setMaximum(total)
        self.progress_true.setValue(counts["TRUE"])
        self.progress_false.setMaximum(total)
        self.progress_false.setValue(counts["FALSE"])
        self.progress_unknown.setMaximum(total)
        self.progress_unknown.setValue(counts["UNKNOWN"])

        edge_rows = self.conn.execute(
            "SELECT fe.id, ft1.assertion, ft2.assertion, fe.relation, fe.weight FROM fact_edges fe JOIN fact_truths ft1 ON fe.from_fact_id = ft1.id JOIN fact_truths ft2 ON fe.to_fact_id = ft2.id ORDER BY fe.id"
        ).fetchall()
        self.edges_table.setRowCount(len(edge_rows))
        for i, (eid, from_a, to_a, rel, w) in enumerate(edge_rows):
            items = [str(eid), from_a[:60], to_a[:60], rel, str(w)]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                if j == 3:
                    if rel == "contradicts":
                        item.setForeground(QColor(178, 34, 34))
                        item.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
                    elif rel == "supports":
                        item.setForeground(QColor(34, 139, 34))
                self.edges_table.setItem(i, j, item)

    def _on_row_select(self, row, col):
        fid_item = self.table.item(row, 0)
        if not fid_item:
            return
        fid = int(fid_item.text())
        data = self.conn.execute("SELECT * FROM fact_truths WHERE id = ?", (fid,)).fetchone()
        if not data:
            return
        cols = ["id", "assertion", "classification", "confidence", "weight", "provenance",
                "source_query", "evidence", "version", "is_canonical", "status",
                "contradicts_id", "created_at", "validated_at", "collapsed_at"]
        lines = []
        for i, col_name in enumerate(cols):
            val = data[i]
            if val is None:
                val = "—"
            lines.append(f"  {col_name:20s} = {val}")
        self.detail_text.setPlainText("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FactStoreGUI()
    window.show()
    sys.exit(app.exec())
