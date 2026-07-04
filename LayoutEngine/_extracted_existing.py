"""
_extracted_existing.py
Auto-extracted layout-engine Python code from two ChatGPT chat exports.

Sources:
  69cc0c1e = "Bracket Rule Manager GUI" (chat 69cc0c1e-e6ac-8326-a291-9d5b8c128084)
  6a101ee2 = "GUI Design Constraints"  (chat 6a101ee2-c300-83ea-b757-dc96f5c70d59)

Extraction rules:
  - Latest version of each class is kept (earlier versions noted in header).
  - Code blocks with id="..." fence attributes are included.
  - Each section: # === <classes> (from <tag> @ <create_time>) ===

Class inventory:
  Chat 6a101ee2 (layout/constraint engine):
    CascadeExecutionReplayEngine  - builds deterministic execution tree from DB
    DeterminismValidator          - validates DB integrity for layout pipeline
    CascadeDeterminismMaxValidator- extended determinism validator
    SpatialConstraintEngine       - deterministic geometry compiler (toolbar/sidebar/grid)
    ConstraintSolver              - resolves layout constraints (ratios, bounds)
    PixelRenderer                 - abstract canvas model from layout
    LayoutCritic                  - deterministic layout scoring
    LayoutFixer                   - deterministic layout correction
    DeterministicUIEngine         - closed-loop UI compiler (solve->render->critique->fix)
    DBConstraintAuditor           - audits DB constraints
    DBConstraintEngine            - DB-driven constraint engine (latest v6)
    RenderPipeline                - render pipeline stub
    RenderState                   - render state container
    CompiledRule                  - compiled constraint rule
    ConstraintNode                - node in constraint graph
    LayoutState                   - layout state container
    RuleGraph                     - rule graph structure
    ConstraintEngine              - constraint engine (graph-based)
    GraphNode                     - graph node
    MainWindow                    - Qt main window for constraint GUI
    SVGRenderer                   - SVG output renderer
    IncrementalConstraintEngine   - incremental constraint solver
    IncrementalRepairEngine       - incremental repair
    IncrementalSVG                - incremental SVG renderer
    PatchRenderer                 - patch-based renderer
    DependencyGraph               - dependency graph
    IRStateCache                  - IR state cache
    RepairEngine                  - repair engine
    IRRebuilder                   - IR rebuilder from events
    ProjectionLayer               - projection layer
    TimeMachine                   - temporal state rebuild
    Event                         - event record
    EventStore                    - event store
    Branch                        - branch record
    BranchMerger                  - merges branches
    BranchingRepairEngine         - branching repair
    Snapshot                      - state snapshot
    SnapshotPolicy                - snapshot policy
    StateCache                    - state cache
    DAGEvent                      - DAG event
    DAGRebuilder                  - DAG rebuilder
    CompressedEvent               - compressed event

  Chat 69cc0c1e (block/tree/renderer/editor):
    DataclassBlock                - dataclass block representation
    MethodBlock                   - method block representation
    StorageSplitter               - storage splitter
    ChatCompressorStore           - chat compressor store
    CoreDB                        - core DB
    EditorSurface                 - editor surface (Qt)
    HybridEditor                  - hybrid editor
    EditorHighlighter             - syntax highlighter
    EditorToolBar                 - editor toolbar
    AppState                      - app state
    DocumentModel                 - document model
    HeaderParser                  - VBStyle header parser
    SectionNavigator              - section navigator
    SectionRecord                 - section record
    StatusPanel                   - status panel
    StructurePanel                - structure panel
    FileService                   - file service
    VBStyleTreeNode               - VBStyle tree node
    VBStyleClassAspectTree        - class aspect tree
    VBStyleTreeViewer             - tree viewer
    VBStyleClassAspectLawTree     - class aspect law tree
    VBStyleClassTreeBuilder       - class tree builder
    VBStyleDecisionNode           - decision tree node
    VBStyleDecisionTreeEngine     - decision tree engine
    UL_WarpRenderer               - warp renderer
    UL_WarpAtomExtractor          - warp atom extractor
    UL_WarpMerger                 - warp merger
    UL_WarpStore                  - warp store
    UL_WarpVocabulary             - warp vocabulary
    UL_ChatTurnParser             - chat turn parser
    App_GhostStenoV1              - ghost steno app
    PatchBlockApplier             - patch block applier
    Core_ChatExtractConfig        - chat extract config
    Core_ChatNoiseReducer         - chat noise reducer
    Core_ChatStructureExtractor   - chat structure extractor
    MetricsWindow                 - metrics window
    ChatMetrics                   - chat metrics
    AuditMainWindow               - audit main window
    CodeRenamer                   - code renamer
    ProjectScanner                - project scanner
    ResultFormatter               - result formatter
    VBRuleConfig                  - VB rule config
"""


# === Core_ChatExtractConfig, Core_ChatNoiseReducer, Core_ChatStructureExtractor (from 69cc0c1e @ 1775007524.779274) ===
# Ghost{[File[UC_ChatExtractCore.py]][Role[core_chat_extraction]][Status[active]][Version[1.0]][Law[config_driven|no_decorators|no_dataclass|direct_methods_only]]}
# Ghost{[Purpose[Normalize chat markdown, extract QA pairs, extract code blocks, reduce noise, build chat packets]]}
# Ghost{[Authority[utility_core]][Flow[read_state|normalize|validate|perform_owned_action|update_state|return_direct_value]]}

import re
import json
import hashlib
from pathlib import Path


class Core_ChatExtractConfig:
    """
    Ghost{[Class[Core_ChatExtractConfig]][Domain[config_loading]][Owns[external_config_truth]][Returns[tuple2]]}
    """

    def __init__(self, config_path):
        self.mem = None
        self.db = None
        self.state = {
            "config_path": str(config_path),
            "config": {},
            "errors": [],
        }

    def load_config(self):
        path = Path(self.state["config_path"])
        if not path.exists():
            return (
                0,
                {
                    "error": "config_not_found",
                    "config_path": str(path),
                },
            )

        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return (
                0,
                {
                    "error": "config_read_failed",
                    "config_path": str(path),
                    "reason": str(exc),
                },
            )

        self.state["config"] = config
        return (
            1,
            {
                "config": config,
                "config_path": str(path),
            },
        )


class Core_ChatNoiseReducer:
    """
    Ghost{[Class[Core_ChatNoiseReducer]][Domain[chat_noise_reduction]][Owns[markdown_cleanup]][Returns[tuple2]]}
    """

    def __init__(self, config):
        self.mem = None
        self.db = None
        self.state = {
            "config": config,
            "input_text": "",
            "clean_text": "",
            "removed_lines": 0,
            "removed_patterns": [],
        }

    def reduce_noise(self, text):
        self.state["input_text"] = text or ""
        clean_text = self.state["input_text"]

        patterns = self.state["config"].get("noise_line_patterns", [])
        removed_patterns = []
        removed_lines = 0

        source_lines = clean_text.splitlines()
        kept_lines = []

        for line in source_lines:
            stripped = line.strip()
            matched = 0
            for pattern in patterns:
                if re.match(pattern, stripped):
                    matched = 1
                    removed_lines += 1
                    removed_patterns.append(pattern)
                    break
            if matched == 0:
                kept_lines.append(line)

        clean_text = "\n".join(kept_lines)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip() + "\n"

        self.state["clean_text"] = clean_text
        self.state["removed_lines"] = removed_lines
        self.state["removed_patterns"] = removed_patterns

        return (
            1,
            {
                "clean_text": clean_text,
                "removed_lines": removed_lines,
                "removed_pattern_count": len(set(removed_patterns)),
            },
        )


class Core_ChatStructureExtractor:
    """
    Ghost{[Class[Core_ChatStructureExtractor]][Domain[chat_structure_extraction]][Owns[qa_code_packet_extraction]][Returns[tuple2]]}
    """

    def __init__(self, config):
        self.mem = None
        self.db = None
        self.state = {
            "config": config,
            "text": "",
            "qa_pairs": [],
            "code_blocks": [],
            "packets": [],
            "headings": [],
            "stats": {},
        }

    def extract_all(self, text):
        self.state["text"] = text or ""

        qa_pairs = self._extract_qa_pairs(self.state["text"])
        code_blocks = self._extract_code_blocks(self.state["text"])
        headings = self._extract_headings(self.state["text"])
        packets = self._build_packets(qa_pairs, code_blocks, headings)

        self.state["qa_pairs"] = qa_pairs
        self.state["code_blocks"] = code_blocks
        self.state["headings"] = headings
        self.state["packets"] = packets
        self.state["stats"] = {
            "qa_count": len(qa_pairs),
            "code_count": len(code_blocks),
            "heading_count": len(headings),
            "packet_count": len(packets),
        }

        return (
            1,
            {
                "qa_pairs": qa_pairs,
                "code_blocks": code_blocks,
                "headings": headings,
                "packets": packets,
                "stats": self.state["stats"],
            },
        )

    def _extract_qa_pairs(self, text):
        lines = text.splitlines()
        qa_pairs = []
        current_question = None
        current_answer_lines = []

        user_markers = self.state["config"].get("user_markers", [])
        assistant_markers = self.state["config"].get("assistant_markers", [])

        def is_user_line(line):
            stripped = line.strip()
            for marker in user_markers:
                if stripped.startswith(marker):
                    return 1
            return 0

        def is_assistant_line(line):
            stripped = line.strip()
            for marker in assistant_markers:
                if stripped.startswith(marker):
                    return 1
            return 0

        def normalize_role_line(line):
            stripped = line.strip()
            for marker in user_markers + assistant_markers:
                if stripped.startswith(marker):
                    return stripped[len(marker):].strip()
            return stripped

        current_role = ""

        for line in lines:
            if is_user_line(line):
                if current_question is not None:
                    qa_pairs.append(
                        {
                            "question": current_question,
                            "answer": "\n".join(current_answer_lines).strip(),
                            "qa_id": self._stable_id(current_question + "||" + "\n".join(current_answer_lines)),
                        }
                    )
                current_question = normalize_role_line(line)
                current_answer_lines = []
                current_role = "user"
                continue

            if is_assistant_line(line):
                current_role = "assistant"
                content = normalize_role_line(line)
                if content:
                    current_answer_lines.append(content)
                continue

            if current_role == "assistant":
                current_answer_lines.append(line)

        if current_question is not None:
            qa_pairs.append(
                {
                    "question": current_question,
                    "answer": "\n".join(current_answer_lines).strip(),
                    "qa_id": self._stable_id(current_question + "||" + "\n".join(current_answer_lines)),
                }
            )

        return qa_pairs

    def _extract_code_blocks(self, text):
        matches = re.findall(r"


# === AuditMainWindow, CodeRenamer, ProjectScanner, ResultFormatter, VBRuleConfig (from 69cc0c1e @ 1775009902.727951) ===
# Ghost{
# [Purpose:VBSTYLE_Naming_And_File_Audit_GUI]
# [Pattern:param_validate_execute_cleanup]
# [MagneticSignature:VBSTYLEAudit]
# }

import ast
import json
import os
import re
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QAbstractItemView,
)


class VBRuleConfig:
    def __init__(self):
        self.mem = None
        self.db = None
        self.state = {
            "config": {
                "disallowed_class_prefixes": ["Core_", "UL_", "Lib_"],
                "warn_token_count_over": 3,
                "allowed_file_prefixes": ["Core_", "UL_", "Lib_", "UC_", "App_"],
                "python_extensions": [".py"],
                "backup_suffix": ".bak_vbstyle",
            }
        }

    def get_config(self):
        return (1, {"config": self.state["config"]})


class ProjectScanner:
    def __init__(self, config):
        self.mem = None
        self.db = None
        self.state = {
            "config": config,
            "root_path": "",
            "files": [],
            "violations": [],
        }

    def scan_project(self, root_path):
        path = Path(root_path)
        self.state["root_path"] = str(path)

        if not path.exists():
            return (0, {"error": "root_not_found", "root_path": str(path)})

        files = []
        violations = []

        for file_path in path.rglob("*.py"):
            if any(part.startswith(".") for part in file_path.parts):
                continue

            ok_file, file_result = self._scan_file(file_path)
            if ok_file != 1:
                violations.append(file_result)
                continue

            files.append(file_result["file"])
            violations.extend(file_result["violations"])

        self.state["files"] = files
        self.state["violations"] = violations

        return (
            1,
            {
                "root_path": str(path),
                "files": files,
                "violations": violations,
                "file_count": len(files),
                "violation_count": len(violations),
            },
        )

    def _scan_file(self, file_path):
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return (
                0,
                {
                    "type": "file_read_failed",
                    "severity": "error",
                    "file_path": str(file_path),
                    "message": str(exc),
                    "fix_type": "none",
                },
            )

        try:
            tree = ast.parse(source)
        except Exception as exc:
            return (
                1,
                {
                    "file": {
                        "file_path": str(file_path),
                        "class_count": 0,
                    },
                    "violations": [
                        {
                            "type": "syntax_error",
                            "severity": "error",
                            "file_path": str(file_path),
                            "class_name": "",
                            "line": 1,
                            "message": f"Syntax parse failed: {exc}",
                            "fix_type": "none",
                        }
                    ],
                },
            )

        class_nodes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        violations = []

        file_name = file_path.name
        file_stem = file_path.stem
        class_names = [node.name for node in class_nodes]

        for node in class_nodes:
            violations.extend(self._scan_class(file_path, file_name, file_stem, node, class_names))

        file_prefix_kind = self._file_prefix_kind(file_name)
        ul_like_classes = [name for name in class_names if name.startswith("UL_") or name.startswith("Lib_")]
        if len(ul_like_classes) > 1:
            violations.append(
                {
                    "type": "lib_multi_class_file",
                    "severity": "warning",
                    "file_path": str(file_path),
                    "class_name": ", ".join(ul_like_classes),
                    "line": 1,
                    "message": "UL_/Lib_ file surface appears to contain multiple utility classes.",
                    "fix_type": "manual_split",
                }
            )

        if file_prefix_kind == "Core":
            foreign_utility = [name for name in class_names if name.startswith("UL_") or name.startswith("Lib_")]
            if foreign_utility:
                violations.append(
                    {
                        "type": "utility_inside_core_file",
                        "severity": "warning",
                        "file_path": str(file_path),
                        "class_name": ", ".join(foreign_utility),
                        "line": 1,
                        "message": "Utility-style class found inside Core_ file surface.",
                        "fix_type": "manual_move",
                    }
                )

        return (
            1,
            {
                "file": {
                    "file_path": str(file_path),
                    "class_count": len(class_nodes),
                },
                "violations": violations,
            },
        )

    def _scan_class(self, file_path, file_name, file_stem, node, class_names):
        violations = []
        class_name = node.name
        line = getattr(node, "lineno", 1)

        if self._has_disallowed_class_prefix(class_name):
            violations.append(
                {
                    "type": "class_layer_prefix",
                    "severity": "error",
                    "file_path": str(file_path),
                    "class_name": class_name,
                    "line": line,
                    "message": "Class name includes layer prefix such as Core_/UL_/Lib_.",
                    "fix_type": "rename_class",
                    "suggested_name": self._suggest_class_name(class_name),
                }
            )

        token_count = self._camel_token_count(class_name)
        warn_limit = self.state["config"]["warn_token_count_over"]
        if token_count > warn_limit:
            violations.append(
                {
                    "type": "class_name_too_descriptive",
                    "severity": "warning",
                    "file_path": str(file_path),
                    "class_name": class_name,
                    "line": line,
                    "message": f"Class name appears long or padded. Token count: {token_count}.",
                    "fix_type": "rename_class",
                    "suggested_name": self._suggest_class_name(class_name),
                }
            )

        if len(class_names) == 1:
            only_name = class_names[0]
            suggested_file = self._suggest_file_name(only_name)
            if file_stem != Path(suggested_file).stem:
                violations.append(
                    {
                        "type": "file_name_mismatch",
                        "severity": "warning",
                        "file_path": str(file_path),
                        "class_name": only_name,
                        "line": line,
                        "message": "Single-class file name does not match canonical class-derived file name.",
                        "fix_type": "rename_file",
                        "suggested_file_name": suggested_file,
                    }
                )

        return violations

    def _has_disallowed_class_prefix(self, class_name):
        for prefix in self.state["config"]["disallowed_class_prefixes"]:
            if class_name.startswith(prefix):
                return True
        return False

    def _camel_token_count(self, class_name):
        clean_name = re.sub(r"^(Core_|UL_|Lib_|UC_|App_)", "", class_name)
        if "_" in clean_name:
            parts = [part for part in clean_name.split("_") if part]
            return len(parts)
        parts = re.findall(r"[A-Z][a-z0-9]*", clean_name)
        return len(parts) if parts else 1

    def _suggest_class_name(self, class_name):
        name = re.sub(r"^(Core_|UL_|Lib_|UC_|App_)", "", class_name)
        name = re.sub(r"^(Chat|Markdown)", "", name)
        name = re.sub(r"(Reducer|Builder|Processor|Handler|Manager)$", "", name)
        name = name.strip("_")
        if not name:
            name = "RenameMe"
        return name

    def _suggest_file_name(self, class_name):
        return f"{class_name}.py"

    def _file_prefix_kind(self, file_name):
        for prefix in ["Core_", "UL_", "Lib_", "UC_", "App_"]:
            if file_name.startswith(prefix):
                return prefix.replace("_", "")
        return "Other"


class CodeRenamer:
    def __init__(self, config):
        self.mem = None
        self.db = None
        self.state = {
            "config": config,
            "last_action": {},
        }

    def rename_class_in_file(self, file_path, old_name, new_name):
        path = Path(file_path)
        if not path.exists():
            return (0, {"error": "file_not_found", "file_path": str(path)})

        if not old_name or not new_name:
            return (0, {"error": "missing_name", "old_name": old_name, "new_name": new_name})

        if old_name == new_name:
            return (0, {"error": "same_name", "name": old_name})

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return (0, {"error": "read_failed", "reason": str(exc)})

        pattern = r"\b" + re.escape(old_name) + r"\b"
        updated_source, count = re.subn(pattern, new_name, source)

        if count == 0:
            return (
                0,
                {
                    "error": "class_name_not_found",
                    "file_path": str(path),
                    "old_name": old_name,
                },
            )

        ok_backup, backup_result = self._backup_file(path)
        if ok_backup != 1:
            return (0, backup_result)

        try:
            path.write_text(updated_source, encoding="utf-8")
        except Exception as exc:
            return (0, {"error": "write_failed", "reason": str(exc)})

        self.state["last_action"] = {
            "action": "rename_class",
            "file_path": str(path),
            "old_name": old_name,
            "new_name": new_name,
            "replacement_count": count,
        }

        return (
            1,
            {
                "file_path": str(path),
                "old_name": old_name,
                "new_name": new_name,
                "replacement_count": count,
            },
        )

    def rename_file(self, file_path, new_file_name):
        path = Path(file_path)
        if not path.exists():
            return (0, {"error": "file_not_found", "file_path": str(path)})

        target = path.parent / new_file_name
        if target.exists():
            return (0, {"error": "target_exists", "target_path": str(target)})

        ok_backup, backup_result = self._backup_file(path)
        if ok_backup != 1:
            return (0, backup_result)

        try:
            path.rename(target)
        except Exception as exc:
            return (0, {"error": "rename_failed", "reason": str(exc)})

        self.state["last_action"] = {
            "action": "rename_file",
            "old_path": str(path),
            "new_path": str(target),
        }

        return (
            1,
            {
                "old_path": str(path),
                "new_path": str(target),
            },
        )

    def _backup_file(self, path):
        suffix = self.state["config"]["backup_suffix"]
        backup_path = path.with_name(path.name + suffix)
        try:
            shutil.copy2(path, backup_path)
        except Exception as exc:
            return (0, {"error": "backup_failed", "reason": str(exc), "backup_path": str(backup_path)})
        return (1, {"backup_path": str(backup_path)})


class ResultFormatter:
    def __init__(self):
        self.mem = None
        self.db = None
        self.state = {
            "last_summary": "",
        }

    def build_summary(self, scan_result):
        lines = []
        lines.append(f"Root: {scan_result.get('root_path', '')}")
        lines.append(f"Files scanned: {scan_result.get('file_count', 0)}")
        lines.append(f"Violations: {scan_result.get('violation_count', 0)}")
        lines.append("")

        groups = {}
        for item in scan_result.get("violations", []):
            groups[item["type"]] = groups.get(item["type"], 0) + 1

        lines.append("Violation groups:")
        if not groups:
            lines.append("- none")
        else:
            for key in sorted(groups.keys()):
                lines.append(f"- {key}: {groups[key]}")

        summary = "\n".join(lines)
        self.state["last_summary"] = summary
        return (1, {"summary": summary})


class AuditMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ok_cfg, cfg_result = VBRuleConfig().get_config()
        self.config = cfg_result["config"] if ok_cfg == 1 else {}
        self.scanner = ProjectScanner(self.config)
        self.renamer = CodeRenamer(self.config)
        self.formatter = ResultFormatter()
        self.current_root = ""
        self.current_scan = {"violations": []}
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("VBSTYLE Audit GUI")
        self.resize(1440, 860)

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Project root path")
        browse_btn = QPushButton("Browse")
        scan_btn = QPushButton("Scan")
        export_btn = QPushButton("Export JSON")

        browse_btn.clicked.connect(self._choose_root)
        scan_btn.clicked.connect(self._scan_now)
        export_btn.clicked.connect(self._export_json)

        top_bar.addWidget(QLabel("Root"))
        top_bar.addWidget(self.path_edit, 1)
        top_bar.addWidget(browse_btn)
        top_bar.addWidget(scan_btn)
        top_bar.addWidget(export_btn)

        filter_box = QGroupBox("Filters")
        filter_layout = QHBoxLayout(filter_box)
        self.show_errors = QCheckBox("Errors")
        self.show_warnings = QCheckBox("Warnings")
        self.show_errors.setChecked(True)
        self.show_warnings.setChecked(True)
        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("Filter by class, file, message")
        apply_filter_btn = QPushButton("Apply Filter")
        apply_filter_btn.clicked.connect(self._refresh_table)
        self.show_errors.stateChanged.connect(self._refresh_table)
        self.show_warnings.stateChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.show_errors)
        filter_layout.addWidget(self.show_warnings)
        filter_layout.addWidget(self.filter_text, 1)
        filter_layout.addWidget(apply_filter_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Severity", "Type", "Class", "File", "Line", "Suggested", "Message"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._load_selected_violation)
        left_layout.addWidget(self.table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_box = QGroupBox("Violation Details")
        details_layout = QFormLayout(details_box)

        self.detail_type = QLineEdit()
        self.detail_type.setReadOnly(True)
        self.detail_class = QLineEdit()
        self.detail_class.setReadOnly(True)
        self.detail_file = QLineEdit()
        self.detail_file.setReadOnly(True)
        self.detail_fix = QLineEdit()
        self.detail_fix.setReadOnly(True)
        self.rename_input = QLineEdit()
        self.rename_input.setPlaceholderText("New class name or file name")

        details_layout.addRow("Type", self.detail_type)
        details_layout.addRow("Class", self.detail_class)
        details_layout.addRow("File", self.detail_file)
        details_layout.addRow("Fix Type", self.detail_fix)
        details_layout.addRow("New Name", self.rename_input)

        action_row = QHBoxLayout()
        self.apply_fix_btn = QPushButton("Apply Selected Fix")
        self.open_file_btn = QPushButton("Open Folder")
        self.rescan_btn = QPushButton("Rescan")
        action_row.addWidget(self.apply_fix_btn)
        action_row.addWidget(self.open_file_btn)
        action_row.addWidget(self.rescan_btn)

        self.apply_fix_btn.clicked.connect(self._apply_fix)
        self.open_file_btn.clicked.connect(self._open_folder)
        self.rescan_btn.clicked.connect(self._scan_now)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Menlo", 11))

        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(180)
        self.summary.setFont(QFont("Menlo", 11))

        right_layout.addWidget(details_box)
        right_layout.addLayout(action_row)
        right_layout.addWidget(QLabel("File Preview"))
        right_layout.addWidget(self.preview, 1)
        right_layout.addWidget(QLabel("Scan Summary"))
        right_layout.addWidget(self.summary)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([900, 540])

        root_layout.addLayout(top_bar)
        root_layout.addWidget(filter_box)
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        choose_action = QAction("Choose Root", self)
        choose_action.triggered.connect(self._choose_root)
        scan_action = QAction("Scan", self)
        scan_action.triggered.connect(self._scan_now)
        file_menu.addAction(choose_action)
        file_menu.addAction(scan_action)

        self._set_styles()

    def _set_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                font-size: 13px;
            }
            QGroupBox {
                font-weight: 600;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }
            QPushButton {
                min-height: 30px;
                padding: 6px 12px;
            }
            QLineEdit, QPlainTextEdit, QTableWidget {
                border: 1px solid #4a4a4a;
                border-radius: 6px;
            }
            """
        )

    def _choose_root(self):
        path = QFileDialog.getExistingDirectory(self, "Choose project root")
        if path:
            self.current_root = path
            self.path_edit.setText(path)

    def _scan_now(self):
        root = self.path_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "Missing root", "Choose a root folder first.")
            return

        ok_scan, scan_result = self.scanner.scan_project(root)
        if ok_scan != 1:
            QMessageBox.critical(self, "Scan failed", json.dumps(scan_result, indent=2))
            return

        self.current_root = root
        self.current_scan = scan_result
        ok_summary, summary_result = self.formatter.build_summary(scan_result)
        if ok_summary == 1:
            self.summary.setPlainText(summary_result["summary"])
        self._refresh_table()
        self.statusBar().showMessage(
            f"Scanned {scan_result['file_count']} files, found {scan_result['violation_count']} violations."
        )

    def _refresh_table(self):
        rows = self._filtered_violations()
        self.table.setRowCount(len(rows))

        for row_index, item in enumerate(rows):
            values = [
                item.get("severity", ""),
                item.get("type", ""),
                item.get("class_name", ""),
                item.get("file_path", ""),
                str(item.get("line", "")),
                item.get("suggested_name", item.get("suggested_file_name", "")),
                item.get("message", ""),
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))

        self.table.resizeColumnsToContents()

    def _filtered_violations(self):
        search = self.filter_text.text().strip().lower()
        show_errors = self.show_errors.isChecked()
        show_warnings = self.show_warnings.isChecked()

        rows = []
        for item in self.current_scan.get("violations", []):
            if item.get("severity") == "error" and not show_errors:
                continue
            if item.get("severity") == "warning" and not show_warnings:
                continue

            hay = " | ".join(
                [
                    item.get("type", ""),
                    item.get("class_name", ""),
                    item.get("file_path", ""),
                    item.get("message", ""),
                ]
            ).lower()

            if search and search not in hay:
                continue

            rows.append(item)

        return rows

    def _load_selected_violation(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return

        index = rows[0].row()
        item = self._filtered_violations()[index]

        self.detail_type.setText(item.get("type", ""))
        self.detail_class.setText(item.get("class_name", ""))
        self.detail_file.setText(item.get("file_path", ""))
        self.detail_fix.setText(item.get("fix_type", ""))

        suggested = item.get("suggested_name", item.get("suggested_file_name", ""))
        self.rename_input.setText(suggested)

        self._load_preview(item.get("file_path", ""))

    def _load_preview(self, file_path):
        if not file_path or not Path(file_path).exists():
            self.preview.clear()
            return

        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            self.preview.setPlainText(str(exc))
            return

        self.preview.setPlainText(text[:22000])

    def _selected_violation(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        filtered = self._filtered_violations()
        if index >= len(filtered):
            return None
        return filtered[index]

    def _apply_fix(self):
        item = self._selected_violation()
        if item is None:
            QMessageBox.warning(self, "Nothing selected", "Select a violation first.")
            return

        new_name = self.rename_input.text().strip()
        fix_type = item.get("fix_type", "")

        if fix_type == "rename_class":
            old_name = item.get("class_name", "")
            ok_fix, fix_result = self.renamer.rename_class_in_file(item["file_path"], old_name, new_name)
        elif fix_type == "rename_file":
            ok_fix, fix_result = self.renamer.rename_file(item["file_path"], new_name)
        else:
            QMessageBox.information(self, "Manual fix", "This violation requires manual move/split/fix.")
            return

        if ok_fix != 1:
            QMessageBox.critical(self, "Fix failed", json.dumps(fix_result, indent=2))
            return

        QMessageBox.information(self, "Fix applied", json.dumps(fix_result, indent=2))
        self._scan_now()

    def _open_folder(self):
        item = self._selected_violation()
        if item is None:
            return
        folder = str(Path(item["file_path"]).parent)
        if os.name == "posix":
            os.system(f'open "{folder}"')

    def _export_json(self):
        if not self.current_scan:
            QMessageBox.warning(self, "Nothing to export", "Run a scan first.")
            return

        target, _ = QFileDialog.getSaveFileName(self, "Export JSON", "vbstyle_audit.json", "JSON Files (*.json)")
        if not target:
            return

        try:
            Path(target).write_text(json.dumps(self.current_scan, indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        QMessageBox.information(self, "Exported", target)


def main():
    app = QApplication([])
    window = AuditMainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()


# === App_GhostStenoV1, UL_ChatTurnParser, UL_WarpMerger, UL_WarpRenderer, UL_WarpStore, UL_WarpVocabulary (from 69cc0c1e @ 1775131304.087449) ===
import argparse
import json
import os
import re
import sqlite3
from typing import List, Dict, Tuple, Optional


class UL_WarpVocabulary:
    def __init__(self):
        self.allowed_atoms = {
            "request", "concern", "issue", "find", "solution", "decision",
            "approve", "reject", "reason", "status", "action", "test",
            "verify", "fix", "plan", "impl", "deploy", "rollback",
            "scope", "timeline", "priority", "metric", "result", "risk",
            "block", "unblock", "refactor", "optimize", "document",
            "review", "trigger", "env", "location", "cause", "target",
            "format", "use_case", "event", "type", "strategy", "step",
            "check", "ready", "resolve", "monitor", "schedule", "add",
            "accuracy", "motivation", "stakeholder", "feasibility", "design",
            "spec"
        }
        self.partition_names = ["W", "A", "R", "P"]

    def is_allowed_atom(self, atom_name: str) -> bool:
        return atom_name in self.allowed_atoms

    def sanitize_token(self, raw_text: str) -> str:
        text = raw_text.strip().lower()
        text = text.replace("&", " and ")
        text = re.sub(r"[^a-z0-9\s_]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "unknown"

        parts = text.split()
        if len(parts) == 1:
            return parts[0]

        if len(parts) >= 2:
            # one underscore max
            return f"{parts[0]}_{parts[1]}"

        return "unknown"

    def sanitize_arg_list(self, values: List[str]) -> List[str]:
        seen = set()
        out = []
        for item in values:
            tok = self.sanitize_token(item)
            if tok and tok not in seen:
                out.append(tok)
                seen.add(tok)
        return out


class UL_ChatTurnParser:
    def __init__(self):
        self.speaker_pattern = re.compile(
            r"^\s*(user|assistant|cascade|chatgpt|system|developer)\s*:\s*(.*)$",
            re.IGNORECASE,
        )

    def parse_turns(self, text: str) -> Tuple[bool, List[Dict[str, str]]]:
        lines = text.splitlines()
        turns = []
        current_speaker = None
        current_text_parts = []

        for raw_line in lines:
            line = raw_line.rstrip()
            match = self.speaker_pattern.match(line)
            if match:
                if current_speaker is not None:
                    turns.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text_parts).strip()
                    })
                current_speaker = match.group(1).lower()
                current_text_parts = [match.group(2).strip()]
            else:
                stripped = line.strip()
                if not stripped:
                    if current_speaker is not None and current_text_parts:
                        current_text_parts.append("")
                    continue
                if current_speaker is None:
                    current_speaker = "unknown"
                    current_text_parts = [stripped]
                else:
                    current_text_parts.append(stripped)

        if current_speaker is not None:
            turns.append({
                "speaker": current_speaker,
                "text": " ".join(current_text_parts).strip()
            })

        return True, turns


class UL_WarpAtomExtractor:
    def __init__(self, vocab: UL_WarpVocabulary):
        self.vocab = vocab

        self.request_words = [
            "request", "need", "want", "please", "can you", "could you", "asks for", "asked for"
        ]
        self.concern_words = [
            "concern", "worried", "worry", "issue with", "problem with", "eye strain", "risk"
        ]
        self.issue_words = [
            "error", "bug", "crash", "syntax error", "issue", "problem", "fault", "overflow"
        ]
        self.find_words = [
            "found", "identified", "detected", "noticed", "located", "discovered"
        ]
        self.solution_words = [
            "solution", "propose", "proposed", "suggest", "suggested", "approach"
        ]
        self.fix_words = [
            "fix", "fixed", "corrected", "patched", "resolved"
        ]
        self.verify_words = [
            "confirmed", "works", "working", "verified", "passes", "pass", "green"
        ]
        self.reject_words = [
            "reject", "rejected", "ruled out", "not doing", "no", "declined"
        ]
        self.approve_words = [
            "approved", "accepted", "agree", "agreed", "sign off", "signed off"
        ]
        self.plan_words = [
            "pending", "next", "todo", "later", "plan", "planning", "review", "needs", "need to"
        ]
        self.impl_words = [
            "implemented", "created", "added", "built", "wrote", "extracted", "deployed"
        ]
        self.test_words = [
            "test", "tested", "benchmark", "benchmarked", "check", "checking", "validate", "validation"
        ]

    def extract_partitions_from_turns(
        self,
        turns: List[Dict[str, str]],
        block_name: str
    ) -> Tuple[bool, Dict[str, List[str]]]:
        partitions = {
            "W": [],
            "A": [],
            "R": [],
            "P": []
        }

        for turn in turns:
            speaker = turn["speaker"]
            text = turn["text"]
            line_atoms = self.extract_atoms_from_line(text, speaker)
            for part_name, atoms in line_atoms.items():
                for atom in atoms:
                    if atom not in partitions[part_name]:
                        partitions[part_name].append(atom)

        return True, {
            "name": block_name,
            "W": partitions["W"],
            "A": partitions["A"],
            "R": partitions["R"],
            "P": partitions["P"]
        }

    def extract_atoms_from_line(self, text: str, speaker: str) -> Dict[str, List[str]]:
        lower = text.lower()
        out = {"W": [], "A": [], "R": [], "P": []}

        # W = event frame
        if self.contains_any(lower, self.request_words):
            arg = self.extract_primary_subject(lower, fallback="request")
            out["W"].append(self.make_atom("request", [arg]))

        if self.contains_any(lower, self.concern_words):
            arg = self.extract_primary_subject(lower, fallback="concern")
            out["W"].append(self.make_atom("concern", [arg]))

        if self.contains_any(lower, self.issue_words):
            arg = self.extract_issue_subject(lower)
            out["W"].append(self.make_atom("issue", [arg]))

        if self.contains_any(lower, self.find_words):
            arg = self.extract_find_subject(lower)
            out["W"].append(self.make_atom("find", [arg]))

        if "review" in lower or "analy" in lower:
            arg = self.extract_primary_subject(lower, fallback="review")
            out["W"].append(self.make_atom("review", [arg]))

        if "scope" in lower:
            arg = self.extract_primary_subject(lower, fallback="scope")
            out["W"].append(self.make_atom("scope", [arg]))

        if "trigger" in lower or "happens only" in lower:
            arg = self.extract_trigger_subject(lower)
            out["W"].append(self.make_atom("trigger", [arg]))

        if "env" in lower or "intermittent" in lower or "night usage" in lower:
            arg = self.extract_primary_subject(lower, fallback="env")
            out["W"].append(self.make_atom("env", [arg]))

        if "location" in lower or "line " in lower:
            arg = self.extract_location_subject(lower)
            out["W"].append(self.make_atom("location", [arg]))

        # A = accepted / true now
        if self.contains_any(lower, self.solution_words):
            arg = self.extract_solution_subject(lower)
            out["A"].append(self.make_atom("solution", [arg]))

        if self.contains_any(lower, self.fix_words):
            arg = self.extract_fix_subject(lower)
            out["A"].append(self.make_atom("fix", [arg]))

        if self.contains_any(lower, self.verify_words):
            arg = self.extract_verify_subject(lower)
            out["A"].append(self.make_atom("verify", [arg]))

        if self.contains_any(lower, self.approve_words):
            arg = self.extract_primary_subject(lower, fallback="approved")
            out["A"].append(self.make_atom("approve", [arg]))

        if self.contains_any(lower, self.impl_words):
            arg = self.extract_impl_subject(lower)
            out["A"].append(self.make_atom("impl", [arg]))

        if self.contains_any(lower, self.test_words):
            arg = self.extract_test_subject(lower)
            out["A"].append(self.make_atom("test", [arg]))

        if "status" in lower or "ready" in lower or "green" in lower:
            arg = self.extract_status_subject(lower)
            out["A"].append(self.make_atom("status", [arg]))

        if "accuracy" in lower or "%" in lower or "percent" in lower:
            arg = self.extract_metric_subject(lower)
            out["A"].append(self.make_atom("metric", [arg]))

        if "target" in lower or "postgres" in lower or "pdf" in lower:
            arg = self.extract_primary_subject(lower, fallback="target")
            out["A"].append(self.make_atom("target", [arg]))

        # R = rejected / wrong / ruled out
        if self.contains_any(lower, self.reject_words):
            arg = self.extract_reject_subject(lower)
            out["R"].append(self.make_atom("reject", [arg]))

        if "reason" in lower or "because" in lower or "overkill" in lower or "waste" in lower:
            arg = self.extract_reason_subject(lower)
            out["R"].append(self.make_atom("reason", [arg]))

        # P = pending / unresolved / outstanding
        if self.contains_any(lower, self.plan_words):
            arg = self.extract_plan_subject(lower)
            out["P"].append(self.make_atom("plan", [arg]))

        if "timeline" in lower or "schedule" in lower:
            arg = self.extract_primary_subject(lower, fallback="timeline")
            out["P"].append(self.make_atom("timeline", [arg]))

        if "priority" in lower or "backlog" in lower:
            arg = self.extract_primary_subject(lower, fallback="priority")
            out["P"].append(self.make_atom("priority", [arg]))

        if "document" in lower or "docs" in lower or "guide" in lower:
            arg = self.extract_primary_subject(lower, fallback="document")
            out["P"].append(self.make_atom("document", [arg]))

        if "deploy" in lower or "production" in lower or "push" in lower:
            arg = self.extract_primary_subject(lower, fallback="deploy")
            out["P"].append(self.make_atom("deploy", [arg]))

        if "monitor" in lower or "monitoring" in lower:
            arg = self.extract_primary_subject(lower, fallback="monitor")
            out["P"].append(self.make_atom("action", [arg]))

        if "review needed" in lower or "approval pending" in lower or "decision pending" in lower:
            arg = self.extract_primary_subject(lower, fallback="review")
            out["P"].append(self.make_atom("review", [arg]))

        for part_name in ["W", "A", "R", "P"]:
            out[part_name] = self.dedupe_atoms(out[part_name])

        return out

    def contains_any(self, lower_text: str, words: List[str]) -> bool:
        for word in words:
            if word in lower_text:
                return True
        return False

    def dedupe_atoms(self, atoms: List[str]) -> List[str]:
        seen = set()
        out = []
        for atom in atoms:
            if atom not in seen:
                out.append(atom)
                seen.add(atom)
        return out

    def make_atom(self, atom_name: str, args: List[str]) -> str:
        if not self.vocab.is_allowed_atom(atom_name):
            atom_name = "status"
        clean_args = self.vocab.sanitize_arg_list(args)
        if not clean_args:
            clean_args = ["unknown"]
        return f"{atom_name}({','.join(clean_args)})"

    def extract_primary_subject(self, lower_text: str, fallback: str) -> str:
        # tiny deterministic noun-ish extractor
        candidates = [
            "python file", "database architecture", "large datasets", "dark mode",
            "pdf export", "slack webhook", "migration plan", "async io",
            "connection pooling", "syntax error", "save crash", "buffer overflow",
            "circular dependency", "monolithic parser", "fuzzy search",
            "postgres", "mysql", "backup strategy", "zero downtime",
            "500mb file", "100mb file", "night usage"
        ]
        for item in candidates:
            if item in lower_text:
                return item
        words = re.findall(r"[a-z0-9]+", lower_text)
        if not words:
            return fallback
        return " ".join(words[:2])

    def extract_issue_subject(self, lower_text: str) -> str:
        if "syntax error" in lower_text:
            return "syntax_error"
        if "save crash" in lower_text or "crash" in lower_text:
            return "save_crash"
        if "overflow" in lower_text:
            return "buffer_overflow"
        if "circular dependency" in lower_text:
            return "circular_dependency"
        if "indent" in lower_text:
            return "indent_issue"
        return self.extract_primary_subject(lower_text, "issue")

    def extract_find_subject(self, lower_text: str) -> str:
        if "missing colon" in lower_text:
            return "missing_colon"
        if "indent" in lower_text and "42" in lower_text:
            return "indent_issue_42"
        if "overflow" in lower_text:
            return "buffer_overflow"
        if "three bottleneck" in lower_text:
            return "three_bottlenecks"
        return self.extract_primary_subject(lower_text, "find")

    def extract_solution_subject(self, lower_text: str) -> str:
        if "async" in lower_text:
            return "async_io"
        if "index" in lower_text:
            return "add_indexes"
        if "pool" in lower_text:
            return "pooling"
        if "abstraction" in lower_text:
            return "interface_abstraction"
        return self.extract_primary_subject(lower_text, "solution")

    def extract_fix_subject(self, lower_text: str) -> str:
        if "colon" in lower_text:
            return "add_colon"
        if "indent" in lower_text:
            return "indent_correction"
        if "dynamic buffer" in lower_text:
            return "dynamic_buffer"
        return self.extract_primary_subject(lower_text, "fix")

    def extract_verify_subject(self, lower_text: str) -> str:
        if "user" in lower_text and ("confirmed" in lower_text or "thanks" in lower_text):
            return "user_confirm"
        if "500mb" in lower_text:
            return "500mb_pass"
        if "all tests" in lower_text or "tests passing" in lower_text:
            return "all_tests"
        return self.extract_primary_subject(lower_text, "verify")

    def extract_impl_subject(self, lower_text: str) -> str:
        if "levenshtein" in lower_text:
            return "levenshtein"
        if "dynamic buffer" in lower_text:
            return "dynamic_sizing"
        if "abstraction" in lower_text:
            return "abstraction"
        if "tokenizer" in lower_text:
            return "tokenizer"
        return self.extract_primary_subject(lower_text, "impl")

    def extract_test_subject(self, lower_text: str) -> str:
        if "500mb" in lower_text:
            return "500mb"
        if "100mb" in lower_text:
            return "100mb"
        if "edge case" in lower_text:
            return "edge_cases"
        if "user approved" in lower_text:
            return "user_approve"
        return self.extract_primary_subject(lower_text, "test")

    def extract_status_subject(self, lower_text: str) -> str:
        if "green" in lower_text:
            return "build_green"
        if "ready" in lower_text:
            return "ready"
        if "working" in lower_text:
            return "working"
        return self.extract_primary_subject(lower_text, "status")

    def extract_metric_subject(self, lower_text: str) -> str:
        if "95" in lower_text and "percent" in lower_text:
            return "95_percent"
        return self.extract_primary_subject(lower_text, "metric")

    def extract_reject_subject(self, lower_text: str) -> str:
        if "pool" in lower_text:
            return "pooling"
        if "mysql" in lower_text:
            return "mysql"
        if "html" in lower_text:
            return "html"
        if "full rewrite" in lower_text:
            return "full_rewrite"
        if "soundex" in lower_text:
            return "soundex"
        if "fixed buffer" in lower_text:
            return "fixed_buffer"
        if "race condition" in lower_text:
            return "race_condition"
        if "disk full" in lower_text:
            return "disk_full"
        return self.extract_primary_subject(lower_text, "reject")

    def extract_reason_subject(self, lower_text: str) -> str:
        if "overkill" in lower_text:
            return "overkill"
        if "expertise" in lower_text:
            return "expertise"
        if "risk" in lower_text:
            return "risk_high"
        if "debt" in lower_text:
            return "debt_concern"
        if "memory waste" in lower_text or "waste" in lower_text:
            return "memory_waste"
        if "accuracy" in lower_text:
            return "low_accuracy"
        return self.extract_primary_subject(lower_text, "reason")

    def extract_plan_subject(self, lower_text: str) -> str:
        if "analysis" in lower_text:
            return "analysis_pending"
        if "migration" in lower_text:
            return "migration_plan"
        if "async" in lower_text:
            return "async_setup"
        if "edge case" in lower_text:
            return "edge_cases"
        if "dual write" in lower_text:
            return "dual_write"
        if "algorithm" in lower_text:
            return "algorithm"
        if "palette" in lower_text:
            return "palette"
        if "backlog" in lower_text:
            return "backlog"
        return self.extract_primary_subject(lower_text, "plan")

    def extract_trigger_subject(self, lower_text: str) -> str:
        if "100mb" in lower_text:
            return "100mb"
        if "large file" in lower_text:
            return "large_file"
        return self.extract_primary_subject(lower_text, "trigger")

    def extract_location_subject(self, lower_text: str) -> str:
        if "284" in lower_text:
            return "save_handler_284"
        if "42" in lower_text:
            return "line_42"
        return self.extract_primary_subject(lower_text, "location")


class UL_WarpRenderer:
    def render_block(self, block: Dict[str, List[str]]) -> Tuple[bool, str]:
        name = block["name"]
        text = []
        text.append(f"#{name}" + "{")
        text.append(self.render_partition("W", block["W"]))
        text.append(self.render_partition("A", block["A"]))
        text.append(self.render_partition("R", block["R"]))
        text.append(self.render_partition("P", block["P"]))
        text.append("}")
        return True, "\n".join(text)

    def render_partition(self, name: str, items: List[str]) -> str:
        if not items:
            return f"{name}[]"
        return f"{name}[{','.join(items)}]"


class UL_WarpMerger:
    def __init__(self):
        pass

    def merge_blocks(self, blocks: List[Dict[str, List[str]]], merged_name: str) -> Tuple[bool, Dict[str, List[str]]]:
        merged = {
            "name": merged_name,
            "W": [],
            "A": [],
            "R": [],
            "P": []
        }
        seen = {
            "W": set(),
            "A": set(),
            "R": set(),
            "P": set()
        }

        for block in blocks:
            for part_name in ["W", "A", "R", "P"]:
                for atom in block.get(part_name, []):
                    if atom not in seen[part_name]:
                        merged[part_name].append(atom)
                        seen[part_name].add(atom)

        return True, merged


class UL_WarpStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self) -> Tuple[bool, str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS warp_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_name TEXT NOT NULL,
                partition_w TEXT NOT NULL,
                partition_a TEXT NOT NULL,
                partition_r TEXT NOT NULL,
                partition_p TEXT NOT NULL,
                rendered TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        return True, "ok"

    def save_block(self, block: Dict[str, List[str]], rendered: str) -> Tuple[bool, str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO warp_blocks (
                block_name, partition_w, partition_a, partition_r, partition_p, rendered
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            block["name"],
            json.dumps(block["W"]),
            json.dumps(block["A"]),
            json.dumps(block["R"]),
            json.dumps(block["P"]),
            rendered,
        ))
        conn.commit()
        conn.close()
        return True, "ok"


class App_GhostStenoV1:
    def __init__(self, db_path: str):
        self.vocab = UL_WarpVocabulary()
        self.parser = UL_ChatTurnParser()
        self.extractor = UL_WarpAtomExtractor(self.vocab)
        self.renderer = UL_WarpRenderer()
        self.merger = UL_WarpMerger()
        self.store = UL_WarpStore(db_path)

    def process_text(
        self,
        raw_text: str,
        block_prefix: str = "Chat",
        chunk_size: int = 4
    ) -> Tuple[bool, Dict[str, object]]:
        ok, _ = self.store.init_db()
        if not ok:
            return False, {"error": "db_init_failed"}

        ok, turns = self.parser.parse_turns(raw_text)
        if not ok:
            return False, {"error": "turn_parse_failed"}

        if not turns:
            return False, {"error": "no_turns_found"}

        chunks = self.chunk_turns(turns, chunk_size)
        blocks = []
        rendered_blocks = []

        for idx, chunk in enumerate(chunks, start=1):
            block_name = f"{block_prefix}_{idx:03d}"
            ok, block = self.extractor.extract_partitions_from_turns(chunk, block_name)
            if not ok:
                return False, {"error": "extract_failed", "block_name": block_name}
            ok, rendered = self.renderer.render_block(block)
            if not ok:
                return False, {"error": "render_failed", "block_name": block_name}
            self.store.save_block(block, rendered)
            blocks.append(block)
            rendered_blocks.append(rendered)

        ok, merged = self.merger.merge_blocks(blocks, f"Memory_{block_prefix}")
        if not ok:
            return False, {"error": "merge_failed"}

        ok, merged_rendered = self.renderer.render_block(merged)
        if not ok:
            return False, {"error": "merged_render_failed"}

        self.store.save_block(merged, merged_rendered)

        return True, {
            "turn_count": len(turns),
            "chunk_count": len(chunks),
            "blocks": blocks,
            "rendered_blocks": rendered_blocks,
            "merged_block": merged,
            "merged_rendered": merged_rendered
        }

    def chunk_turns(self, turns: List[Dict[str, str]], chunk_size: int) -> List[List[Dict[str, str]]]:
        out = []
        current = []
        for turn in turns:
            current.append(turn)
            if len(current) >= chunk_size:
                out.append(current)
                current = []
        if current:
            out.append(current)
        return out


def read_text_file(file_path: str) -> Tuple[bool, str]:
    if not os.path.exists(file_path):
        return False, ""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
        return True, handle.read()


def write_text_file(file_path: str, text: str) -> Tuple[bool, str]:
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True, "ok"


def build_output_text(result: Dict[str, object]) -> Tuple[bool, str]:
    lines = []
    for rendered in result["rendered_blocks"]:
        lines.append(rendered)
        lines.append("")
    lines.append(result["merged_rendered"])
    return True, "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input chat transcript text file")
    parser.add_argument("--output", required=True, help="Output .warp file")
    parser.add_argument("--db", default="ghost_steno_v1.db", help="SQLite output store")
    parser.add_argument("--prefix", default="Chat", help="Block prefix")
    parser.add_argument("--chunk-size", type=int, default=4, help="Turns per extraction block")
    args = parser.parse_args()

    ok, raw_text = read_text_file(args.input)
    if not ok:
        raise SystemExit(1)

    app = App_GhostStenoV1(args.db)
    ok, result = app.process_text(
        raw_text=raw_text,
        block_prefix=args.prefix,
        chunk_size=args.chunk_size
    )
    if not ok:
        raise SystemExit(2)

    ok, output_text = build_output_text(result)
    if not ok:
        raise SystemExit(3)

    ok, _ = write_text_file(args.output, output_text)
    if not ok:
        raise SystemExit(4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# === UL_WarpAtomExtractor (from 69cc0c1e @ 1775131829.404981) ===
# (earlier:   UL_WarpAtomExtractor earlier versions: [('69cc0c1e', 1775131304.087449)])
import re
from typing import List, Dict


class UL_WarpAtomExtractor:
    def __init__(self, vocab):
        self.vocab = vocab

        self.stop_phrases = {
            "found_the", "also_found", "but_now", "fixed_and", "thanks_that",
            "let_me", "great_working", "user_thanks", "the_error", "the_issue",
            "this_is", "that_is", "it_is", "we_are", "i_have", "you_can",
            "can_you", "could_you", "please_do"
        }

        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "now", "then", "also",
            "that", "this", "those", "these", "with", "from", "into", "onto",
            "have", "has", "had", "was", "were", "is", "are", "be", "been",
            "being", "let", "me", "great", "work", "working", "thanks"
        }

        self.patterns = {
            "syntax_error": re.compile(r"\bsyntax error\b", re.I),
            "indent_issue": re.compile(r"\bindent(?:ation)? issue\b", re.I),
            "missing_colon": re.compile(r"\bmissing colon\b", re.I),
            "line_num": re.compile(r"\bline\s+(\d+)\b", re.I),
            "build_green": re.compile(r"\bbuild\s+green\b", re.I),
            "tests_pass": re.compile(r"\b(all tests|tests?)\s+(pass|passing|passed)\b", re.I),
            "user_confirm": re.compile(r"\b(thanks[, ]|that fixed it|fixed it|works now|working now|confirmed)\b", re.I),
            "reject_named": re.compile(
                r"\b(?:reject|rejected|ruled out)\s+([a-z0-9_ \-]{2,40})", re.I
            ),
            "reason_named": re.compile(
                r"\b(?:because|reason)\b[: ]+([a-z0-9_ \-]{2,60})", re.I
            ),
            "request_named": re.compile(
                r"\b(?:need|want|please|request|requested|asks for|asked for)\b[: ]+([a-z0-9_ \-]{2,60})", re.I
            ),
            "fix_named": re.compile(
                r"\b(?:fix|fixed|corrected|patched|resolved)\b[: \-]+([a-z0-9_ \-]{2,60})", re.I
            ),
            "find_named": re.compile(
                r"\b(?:found|identified|detected|noticed|located|discovered)\b[: \-]+([a-z0-9_ \-]{2,60})", re.I
            ),
        }

    def extract_partitions_from_turns(
        self,
        turns: List[Dict[str, str]],
        block_name: str
    ):
        partitions = {"W": [], "A": [], "R": [], "P": []}

        for turn in turns:
            line_atoms = self.extract_atoms_from_line(turn["text"], turn["speaker"])
            for part_name, atoms in line_atoms.items():
                for atom in atoms:
                    if atom not in partitions[part_name]:
                        partitions[part_name].append(atom)

        return True, {
            "name": block_name,
            "W": partitions["W"],
            "A": partitions["A"],
            "R": partitions["R"],
            "P": partitions["P"],
        }

    def extract_atoms_from_line(self, text: str, speaker: str) -> Dict[str, List[str]]:
        lower = text.lower()
        out = {"W": [], "A": [], "R": [], "P": []}

        # W
        if self.patterns["syntax_error"].search(lower):
            self._add(out["W"], "issue", "syntax_error")

        if self.patterns["indent_issue"].search(lower):
            self._add(out["W"], "issue", "indent_issue")

        if self.patterns["missing_colon"].search(lower):
            self._add(out["W"], "find", "missing_colon")

        line_match = self.patterns["line_num"].search(lower)
        if line_match:
            self._add(out["W"], "location", f"line_{line_match.group(1)}")

        request_payload = self._extract_payload(lower, "request_named")
        if request_payload:
            self._add(out["W"], "request", request_payload)

        # A
        fix_payload = self._extract_payload(lower, "fix_named")
        if fix_payload:
            self._add(out["A"], "fix", fix_payload)

        if self.patterns["build_green"].search(lower):
            self._add(out["A"], "status", "build_green")

        if self.patterns["tests_pass"].search(lower):
            self._add(out["A"], "verify", "tests_pass")

        if self.patterns["user_confirm"].search(lower):
            self._add(out["A"], "verify", "user_confirm")

        # R
        reject_payload = self._extract_payload(lower, "reject_named")
        if reject_payload:
            self._add(out["R"], "reject", reject_payload)

        reason_payload = self._extract_payload(lower, "reason_named")
        if reason_payload:
            self._add(out["R"], "reason", reason_payload)

        # P
        if self._contains_pending(lower):
            pending_payload = self._extract_pending_payload(lower)
            if pending_payload:
                self._add(out["P"], "plan", pending_payload)

        for part_name in out:
            out[part_name] = self._dedupe(out[part_name])

        return out

    def _contains_pending(self, lower: str) -> bool:
        pending_markers = (
            "pending", "need to", "needs ", "later", "next step",
            "next", "todo", "to do", "review needed", "approval pending"
        )
        return any(marker in lower for marker in pending_markers)

    def _extract_pending_payload(self, lower: str) -> str:
        candidates = [
            "analysis", "review", "approval", "migration_plan", "timeline",
            "deploy", "test", "documentation", "cleanup", "edge_cases"
        ]
        for item in candidates:
            if item.replace("_", " ") in lower or item in lower:
                return item
        return "pending"

    def _extract_payload(self, lower: str, pattern_name: str) -> str:
        match = self.patterns[pattern_name].search(lower)
        if not match:
            return ""

        raw = match.group(1).strip()
        token = self.vocab.sanitize_token(raw)

        if not self._is_valid_payload(token):
            return ""

        return token

    def _is_valid_payload(self, token: str) -> bool:
        if not token:
            return False
        if token in self.stop_phrases:
            return False

        parts = token.split("_")
        if any(part in self.stop_words for part in parts):
            return False

        if len(parts) == 1 and parts[0] in self.stop_words:
            return False

        if len(token) < 3:
            return False

        return True

    def _add(self, bucket: List[str], atom_name: str, payload: str) -> None:
        if not payload:
            return
        if not self.vocab.is_allowed_atom(atom_name):
            return
        clean = self.vocab.sanitize_token(payload)
        if not self._is_valid_payload(clean):
            return
        bucket.append(f"{atom_name}({clean})")

    def _dedupe(self, atoms: List[str]) -> List[str]:
        seen = set()
        out = []
        for atom in atoms:
            if atom not in seen:
                out.append(atom)
                seen.add(atom)
        return out


# === ChatMetrics, MetricsWindow (from 69cc0c1e @ 1775166157.334866) ===
import sys
import math
from pathlib import Path
from typing import Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class ChatMetrics:
    def __init__(self, text: str):
        self.text = text

    def get_character_count(self) -> int:
        return len(self.text)

    def get_line_count(self) -> int:
        if not self.text:
            return 0
        return self.text.count("\n") + 1

    def get_word_count(self) -> int:
        return len(self.text.split())

    def get_paragraph_count(self) -> int:
        if not self.text.strip():
            return 0
        blocks = [part for part in self.text.split("\n\n") if part.strip()]
        return len(blocks)

    def get_average_chars_per_line(self) -> float:
        lines = self.get_line_count()
        if lines == 0:
            return 0.0
        return self.get_character_count() / lines

    def get_average_words_per_line(self) -> float:
        lines = self.get_line_count()
        if lines == 0:
            return 0.0
        return self.get_word_count() / lines

    def get_message_count(self) -> Tuple[int, int, int, int, int, int]:
        user_count = 0
        assistant_count = 0
        cascade_count = 0
        chatgpt_count = 0
        system_count = 0
        other_count = 0

        for raw_line in self.text.splitlines():
            line = raw_line.strip()
            lower = line.lower()

            if lower.startswith("user:"):
                user_count += 1
            elif lower.startswith("assistant:"):
                assistant_count += 1
            elif lower.startswith("cascade:"):
                cascade_count += 1
            elif lower.startswith("chatgpt:"):
                chatgpt_count += 1
            elif lower.startswith("system:"):
                system_count += 1
            elif ":" in line:
                head = line.split(":", 1)[0].strip()
                if head and len(head) < 40 and " " not in head:
                    other_count += 1

        return (
            user_count,
            assistant_count,
            cascade_count,
            chatgpt_count,
            system_count,
            other_count,
        )

    def get_total_detected_messages(self) -> int:
        counts = self.get_message_count()
        return sum(counts)

    def get_estimated_pages(self) -> float:
        chars = self.get_character_count()
        if chars == 0:
            return 0.0
        return chars / 1800.0

    def get_estimated_gpt_tokens(self) -> int:
        chars = self.get_character_count()
        if chars == 0:
            return 0
        return math.ceil(chars / 4.0)

    def get_estimated_claude_style_tokens(self) -> int:
        words = self.get_word_count()
        if words == 0:
            return 0
        return math.ceil(words * 1.3)


class MetricsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = ""
        self.setWindowTitle("Chat Metrics Tool")
        self.resize(1200, 800)
        self._build_ui()
        self._build_menu()
        self.update_metrics()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout()
        central.setLayout(root_layout)

        top_bar = QHBoxLayout()

        self.load_button = QPushButton("Load Text File")
        self.load_button.clicked.connect(self.load_text_file)

        self.save_button = QPushButton("Save Text")
        self.save_button.clicked.connect(self.save_text_file)

        self.copy_button = QPushButton("Copy Metrics")
        self.copy_button.clicked.connect(self.copy_metrics_to_clipboard)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_text)

        top_bar.addWidget(self.load_button)
        top_bar.addWidget(self.save_button)
        top_bar.addWidget(self.copy_button)
        top_bar.addWidget(self.clear_button)
        top_bar.addStretch()

        root_layout.addLayout(top_bar)

        content_layout = QHBoxLayout()

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Paste the full chat transcript here...")
        self.text_edit.textChanged.connect(self.update_metrics)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        content_layout.addWidget(self.text_edit, 3)

        side_panel = QVBoxLayout()

        metrics_box = QGroupBox("Metrics")
        metrics_grid = QGridLayout()
        metrics_box.setLayout(metrics_grid)

        self.labels = {}

        metric_names = [
            "Characters",
            "Lines",
            "Words",
            "Paragraphs",
            "Pages",
            "GPT Tokens",
            "Claude Tokens",
            "Avg Chars/Line",
            "Avg Words/Line",
            "Detected Messages",
            "User Messages",
            "Assistant Messages",
            "Cascade Messages",
            "ChatGPT Messages",
            "System Messages",
            "Other Label Messages",
        ]

        for row, name in enumerate(metric_names):
            title = QLabel(name + ":")
            value = QLabel("0")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            metrics_grid.addWidget(title, row, 0)
            metrics_grid.addWidget(value, row, 1)
            self.labels[name] = value

        side_panel.addWidget(metrics_box)

        info_box = QGroupBox("Info")
        info_layout = QVBoxLayout()
        info_box.setLayout(info_layout)

        self.file_label = QLabel("File: none")
        self.status_label = QLabel("Status: ready")
        self.formula_label = QLabel(
            "Token estimates: GPT ≈ chars/4, Claude-ish ≈ words×1.3"
        )
        self.file_label.setWordWrap(True)
        self.status_label.setWordWrap(True)
        self.formula_label.setWordWrap(True)

        info_layout.addWidget(self.file_label)
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.formula_label)

        side_panel.addWidget(info_box)
        side_panel.addStretch()

        content_layout.addLayout(side_panel, 2)
        root_layout.addLayout(content_layout)

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        load_action = QAction("Load", self)
        save_action = QAction("Save", self)
        clear_action = QAction("Clear", self)
        exit_action = QAction("Exit", self)

        load_action.triggered.connect(self.load_text_file)
        save_action.triggered.connect(self.save_text_file)
        clear_action.triggered.connect(self.clear_text)
        exit_action.triggered.connect(self.close)

        file_menu.addAction(load_action)
        file_menu.addAction(save_action)
        file_menu.addAction(clear_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def update_metrics(self) -> None:
        text = self.get_text()
        metrics = ChatMetrics(text)

        user_count, assistant_count, cascade_count, chatgpt_count, system_count, other_count = metrics.get_message_count()

        values = {
            "Characters": str(metrics.get_character_count()),
            "Lines": str(metrics.get_line_count()),
            "Words": str(metrics.get_word_count()),
            "Paragraphs": str(metrics.get_paragraph_count()),
            "Pages": f"{metrics.get_estimated_pages():.2f}",
            "GPT Tokens": str(metrics.get_estimated_gpt_tokens()),
            "Claude Tokens": str(metrics.get_estimated_claude_style_tokens()),
            "Avg Chars/Line": f"{metrics.get_average_chars_per_line():.2f}",
            "Avg Words/Line": f"{metrics.get_average_words_per_line():.2f}",
            "Detected Messages": str(metrics.get_total_detected_messages()),
            "User Messages": str(user_count),
            "Assistant Messages": str(assistant_count),
            "Cascade Messages": str(cascade_count),
            "ChatGPT Messages": str(chatgpt_count),
            "System Messages": str(system_count),
            "Other Label Messages": str(other_count),
        }

        for name, value in values.items():
            self.labels[name].setText(value)

        size_hint = metrics.get_character_count()
        if size_hint == 0:
            self.status_label.setText("Status: ready")
        elif size_hint < 10000:
            self.status_label.setText("Status: small text loaded")
        elif size_hint < 100000:
            self.status_label.setText("Status: medium text loaded")
        else:
            self.status_label.setText("Status: large text loaded")

    def load_text_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Text File",
            "",
            "Text Files (*.txt *.md *.log *.csv *.json *.yaml *.yml);;All Files (*)",
        )
        if not file_path:
            return

        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            self.text_edit.setPlainText(text)
            self.current_file_path = file_path
            self.file_label.setText(f"File: {file_path}")
            self.status_label.setText("Status: file loaded")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Could not load file.\n\n{exc}")

    def save_text_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Text File",
            self.current_file_path or "chat_export.txt",
            "Text Files (*.txt *.md *.log);;All Files (*)",
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(self.get_text(), encoding="utf-8")
            self.current_file_path = file_path
            self.file_label.setText(f"File: {file_path}")
            self.status_label.setText("Status: text saved")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Could not save file.\n\n{exc}")

    def copy_metrics_to_clipboard(self) -> None:
        report = self.build_metrics_report()
        QApplication.clipboard().setText(report)
        self.status_label.setText("Status: metrics copied")

    def build_metrics_report(self) -> str:
        ordered_names = [
            "Characters",
            "Lines",
            "Words",
            "Paragraphs",
            "Pages",
            "GPT Tokens",
            "Claude Tokens",
            "Avg Chars/Line",
            "Avg Words/Line",
            "Detected Messages",
            "User Messages",
            "Assistant Messages",
            "Cascade Messages",
            "ChatGPT Messages",
            "System Messages",
            "Other Label Messages",
        ]
        lines = []
        for name in ordered_names:
            lines.append(f"{name}: {self.labels[name].text()}")
        return "\n".join(lines)

    def clear_text(self) -> None:
        self.text_edit.clear()
        self.current_file_path = ""
        self.file_label.setText("File: none")
        self.status_label.setText("Status: cleared")


def main() -> int:
    app = QApplication(sys.argv)
    window = MetricsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


# === PatchBlockApplier (from 69cc0c1e @ 1775166860.320658) ===
class PatchBlockApplier:
    def apply_block(self, patch_block_text): ...


# === AppState, DocumentModel, EditorHighlighter, EditorSurface, EditorToolBar, FileService, HeaderParser, HybridEditor, SectionNavigator, SectionRecord, StatusPanel, StructurePanel (from 69cc0c1e @ 1775263361.565535) ===
# Ghost{World:App_Hybrid_Record_Editor|Authority:presentation|Kind:app}
# #[Role:window|Behavior:edit|Domain:hybrid_document|Intent:structured_authoring]

import sys

from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QTextCharFormat, QTextCursor, QFont, QColor, QSyntaxHighlighter
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTextEdit,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QSpinBox,
    QListWidget,
    QListWidgetItem,
    QFrame,
)


class AppState:
    """
    Holds live editor state only.
    No heavy behavior.
    """
    def __init__(self):
        self.file_path = ""
        self.is_dirty = False
        self.current_section_id = ""
        self.current_header = ""
        self.zoom_value = 100
        self.mode = "hybrid"


class SectionRecord:
    """
    One document section.
    Header + body + kind + order.
    """
    def __init__(self, section_id="", header="", kind="", body=""):
        self.section_id = section_id
        self.header = header
        self.kind = kind
        self.body = body


class DocumentModel:
    """
    In-memory representation of the full document.
    """
    def __init__(self):
        self.sections = []

    def clear(self):
        pass

    def add_section(self, section_record):
        pass

    def get_section_by_id(self, section_id):
        pass

    def get_all_headers(self):
        pass

    def load_from_text(self, text):
        pass

    def render_to_text(self):
        pass


class HeaderParser:
    """
    Header detection and section splitting rules.
    This is the first protection against document massacre.
    """
    def __init__(self):
        pass

    def detect_header_line(self, line_text):
        pass

    def split_into_sections(self, full_text):
        pass

    def normalize_header(self, header_text):
        pass


class EditorHighlighter(QSyntaxHighlighter):
    """
    Highlighting only.
    Kept contained inside editor family.
    """
    def __init__(self, document):
        super().__init__(document)

    def highlightBlock(self, text):
        pass


class EditorSurface(QTextEdit):
    """
    Base editor surface.
    Main editable text area.
    """
    sectionCursorChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighter = EditorHighlighter(self.document())

    def set_editor_font(self, family, size):
        pass

    def set_zoom_percent(self, value):
        pass

    def insert_section_header(self, header_text):
        pass

    def get_full_text(self):
        pass

    def set_full_text(self, text):
        pass

    def get_current_section_id(self):
        pass


class HybridEditor(EditorSurface):
    """
    Subclassed editor with contained abilities.
    This is where the editor-specific powers live.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def apply_header_format(self):
        pass

    def apply_code_block_format(self):
        pass

    def apply_record_block_format(self):
        pass

    def insert_template_section(self, kind_name):
        pass

    def jump_to_header(self, header_text):
        pass


class SectionNavigator(QTreeWidget):
    """
    Left-side section tree.
    Human-readable navigation.
    """
    sectionSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def rebuild_from_model(self, document_model):
        pass

    def select_section(self, section_id):
        pass


class StructurePanel(QWidget):
    """
    Wrapper around navigator and section tools.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.navigator = SectionNavigator()


class EditorToolBar(QToolBar):
    """
    Top editing actions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def build_actions(self):
        pass


class StatusPanel(QStatusBar):
    """
    Bottom status only.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def show_file_state(self, file_path, is_dirty):
        pass

    def show_section_state(self, header_text):
        pass


class FileService:
    """
    File read/write only.
    No GUI ownership.
    """
    def read_text_file(self, file_path):
        pass

    def write_text_file(self, file_path, text):
        pass


class MainWindow(QMainWindow):
    """
    First real top-level class.
    Owns layout and wires the contained parts.
    """
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.model = DocumentModel()
        self.parser = HeaderParser()
        self.file_service = FileService()

        self.editor = HybridEditor()
        self.structure_panel = StructurePanel()
        self.toolbar = EditorToolBar()
        self.status_panel = StatusPanel()

        self.central = QWidget()
        self.main_splitter = QSplitter()

        self.build_window()
        self.build_layout()
        self.build_toolbar()
        self.bind_events()
        self.load_empty_document()

    def build_window(self):
        pass

    def build_layout(self):
        pass

    def build_toolbar(self):
        pass

    def bind_events(self):
        pass

    def load_empty_document(self):
        pass

    def new_file(self):
        pass

    def open_file(self):
        pass

    def save_file(self):
        pass

    def save_file_as(self):
        pass

    def refresh_model_from_editor(self):
        pass

    def refresh_editor_from_model(self):
        pass

    def refresh_structure_panel(self):
        pass

    def on_section_selected(self, section_id):
        pass

    def on_editor_text_changed(self):
        pass

    def on_insert_header(self):
        pass

    def on_insert_code_block(self):
        pass

    def on_insert_record_block(self):
        pass


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# === VBStyleClassAspectLawTree, VBStyleClassTreeBuilder (from 69cc0c1e @ 1775288542.387348) ===
class VBStyleClassTreeBuilder:
    def __init__(self):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["lines"] = []
        self.state["indent_unit"] = "    "

    def build_tree(self):
        self.state["lines"] = []
        self.add_line("VBSTYLE_CLASS_ASPECT")
        self.add_branch("START", 1)
        self.add_branch("IDENTIFY_ACTION", 2)
        self.add_branch("SEARCH_WORKSPACE", 3)
        self.add_branch("DUPLICATE_FOUND?", 4)

        self.add_branch("YES", 5)
        self.add_branch("CHECK_OWNER_CLASS", 6)
        self.add_branch("OWNER_MATCH?", 7)

        self.add_branch("YES", 8)
        self.add_branch("EXPAND_EXISTING_CLASS", 9)
        self.add_branch("RUN_COMPLETENESS_CHECK", 10)
        self.add_branch("RUN_CONTRACT_CHECK", 11)
        self.add_branch("RUN_TESTS", 12)
        self.add_branch("VERIFY", 13)
        self.add_branch("PASS?", 14)
        self.add_branch("YES -> ACCEPT_CHANGE", 15)
        self.add_branch("NO  -> REJECT_CHANGE", 15)

        self.add_branch("NO", 8)
        self.add_branch("OVERLAP_ONLY?", 9)
        self.add_branch("YES -> RESOLVE_BOUNDARY_FIRST", 10)
        self.add_branch("NO  -> CREATE_NEW_CLASS_FOR_TRUE_NEW_AUTHORITY", 10)
        self.add_branch("RUN_COMPLETENESS_CHECK", 11)
        self.add_branch("RUN_CONTRACT_CHECK", 12)
        self.add_branch("RUN_TESTS", 13)
        self.add_branch("VERIFY", 14)
        self.add_branch("PASS?", 15)
        self.add_branch("YES -> ACCEPT_CHANGE", 16)
        self.add_branch("NO  -> REJECT_CHANGE", 16)

        self.add_branch("NO", 5)
        self.add_branch("CREATE_NEW_CLASS_CANDIDATE", 6)
        self.add_branch("RUN_COMPLETENESS_CHECK", 7)
        self.add_branch("RUN_CONTRACT_CHECK", 8)
        self.add_branch("RUN_TESTS", 9)
        self.add_branch("VERIFY", 10)
        self.add_branch("PASS?", 11)
        self.add_branch("YES -> ACCEPT_CHANGE", 12)
        self.add_branch("NO  -> REJECT_CHANGE", 12)

        return self.render_tree()

    def add_line(self, value):
        self.state["lines"].append(value)

    def add_branch(self, value, depth):
        indent = self.state["indent_unit"] * depth
        line = indent + "|-- " + value
        self.state["lines"].append(line)

    def render_tree(self):
        return "\n".join(self.state["lines"])


class VBStyleClassAspectLawTree:
    def __init__(self):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["builder"] = VBStyleClassTreeBuilder()

    def create_tree_text(self):
        return self.state["builder"].build_tree()


def main():
    tree = VBStyleClassAspectLawTree()
    output = tree.create_tree_text()
    print(output)


if __name__ == "__main__":
    main()


# === VBStyleDecisionNode, VBStyleDecisionTreeEngine (from 69cc0c1e @ 1775288542.387348) ===
class VBStyleDecisionNode:
    def __init__(self, name):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["name"] = name
        self.state["children"] = []

    def add_child(self, child_node):
        self.state["children"].append(child_node)
        return child_node

    def read_name(self):
        return self.state["name"]

    def read_children(self):
        return self.state["children"]


class VBStyleDecisionTreeEngine:
    def __init__(self):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["root"] = None
        self.state["lines"] = []

    def build_default_tree(self):
        root = VBStyleDecisionNode("VBSTYLE_CLASS_ASPECT")
        self.state["root"] = root

        start = root.add_child(VBStyleDecisionNode("START"))
        identify = start.add_child(VBStyleDecisionNode("IDENTIFY_ACTION"))
        search = identify.add_child(VBStyleDecisionNode("SEARCH_WORKSPACE"))
        duplicate = search.add_child(VBStyleDecisionNode("DUPLICATE_FOUND?"))

        yes_dup = duplicate.add_child(VBStyleDecisionNode("YES"))
        owner = yes_dup.add_child(VBStyleDecisionNode("CHECK_OWNER_CLASS"))
        owner_match = owner.add_child(VBStyleDecisionNode("OWNER_MATCH?"))

        owner_yes = owner_match.add_child(VBStyleDecisionNode("YES"))
        expand = owner_yes.add_child(VBStyleDecisionNode("EXPAND_EXISTING_CLASS"))
        complete_1 = expand.add_child(VBStyleDecisionNode("RUN_COMPLETENESS_CHECK"))
        contract_1 = complete_1.add_child(VBStyleDecisionNode("RUN_CONTRACT_CHECK"))
        tests_1 = contract_1.add_child(VBStyleDecisionNode("RUN_TESTS"))
        verify_1 = tests_1.add_child(VBStyleDecisionNode("VERIFY"))
        pass_1 = verify_1.add_child(VBStyleDecisionNode("PASS?"))
        pass_1.add_child(VBStyleDecisionNode("YES -> ACCEPT_CHANGE"))
        pass_1.add_child(VBStyleDecisionNode("NO  -> REJECT_CHANGE"))

        owner_no = owner_match.add_child(VBStyleDecisionNode("NO"))
        overlap = owner_no.add_child(VBStyleDecisionNode("OVERLAP_ONLY?"))
        overlap.add_child(VBStyleDecisionNode("YES -> RESOLVE_BOUNDARY_FIRST"))
        new_auth = overlap.add_child(VBStyleDecisionNode("NO  -> CREATE_NEW_CLASS_FOR_TRUE_NEW_AUTHORITY"))
        complete_2 = new_auth.add_child(VBStyleDecisionNode("RUN_COMPLETENESS_CHECK"))
        contract_2 = complete_2.add_child(VBStyleDecisionNode("RUN_CONTRACT_CHECK"))
        tests_2 = contract_2.add_child(VBStyleDecisionNode("RUN_TESTS"))
        verify_2 = tests_2.add_child(VBStyleDecisionNode("VERIFY"))
        pass_2 = verify_2.add_child(VBStyleDecisionNode("PASS?"))
        pass_2.add_child(VBStyleDecisionNode("YES -> ACCEPT_CHANGE"))
        pass_2.add_child(VBStyleDecisionNode("NO  -> REJECT_CHANGE"))

        no_dup = duplicate.add_child(VBStyleDecisionNode("NO"))
        create = no_dup.add_child(VBStyleDecisionNode("CREATE_NEW_CLASS_CANDIDATE"))
        complete_3 = create.add_child(VBStyleDecisionNode("RUN_COMPLETENESS_CHECK"))
        contract_3 = complete_3.add_child(VBStyleDecisionNode("RUN_CONTRACT_CHECK"))
        tests_3 = contract_3.add_child(VBStyleDecisionNode("RUN_TESTS"))
        verify_3 = tests_3.add_child(VBStyleDecisionNode("VERIFY"))
        pass_3 = verify_3.add_child(VBStyleDecisionNode("PASS?"))
        pass_3.add_child(VBStyleDecisionNode("YES -> ACCEPT_CHANGE"))
        pass_3.add_child(VBStyleDecisionNode("NO  -> REJECT_CHANGE"))

        return root

    def render_ascii_tree(self):
        self.state["lines"] = []
        root = self.state["root"]
        if root is None:
            return ""

        self.render_node(root, 0)
        return "\n".join(self.state["lines"])

    def render_node(self, node, depth):
        name = node.read_name()
        children = node.read_children()

        if depth == 0:
            self.state["lines"].append(name)
        else:
            indent = "    " * depth
            self.state["lines"].append(indent + "|-- " + name)

        index = 0
        total = len(children)
        while index < total:
            child = children[index]
            self.render_node(child, depth + 1)
            index = index + 1


def main():
    engine = VBStyleDecisionTreeEngine()
    engine.build_default_tree()
    print(engine.render_ascii_tree())


if __name__ == "__main__":
    main()


# === VBStyleClassAspectTree, VBStyleTreeNode, VBStyleTreeViewer (from 69cc0c1e @ 1775288655.179883) ===
#!/usr/bin/env python3

import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class VBStyleTreeNode:
    def __init__(self, name):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["name"] = name
        self.state["children"] = []

    def read_name(self):
        return self.state["name"]

    def read_children(self):
        return self.state["children"]

    def add_child(self, name):
        child = VBStyleTreeNode(name)
        self.state["children"].append(child)
        return child


class VBStyleClassAspectTree:
    def __init__(self):
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["root"] = None

    def build_default_tree(self):
        root = VBStyleTreeNode("VBSTYLE_CLASS_ASPECT")
        self.state["root"] = root

        start = root.add_child("START")
        identify = start.add_child("IDENTIFY_ACTION")
        search = identify.add_child("SEARCH_WORKSPACE")
        duplicate = search.add_child("DUPLICATE_FOUND?")

        yes_dup = duplicate.add_child("YES")
        owner = yes_dup.add_child("CHECK_OWNER_CLASS")
        owner_match = owner.add_child("OWNER_MATCH?")

        owner_yes = owner_match.add_child("YES")
        expand = owner_yes.add_child("EXPAND_EXISTING_CLASS")
        complete_1 = expand.add_child("RUN_COMPLETENESS_CHECK")
        contract_1 = complete_1.add_child("RUN_CONTRACT_CHECK")
        tests_1 = contract_1.add_child("RUN_TESTS")
        verify_1 = tests_1.add_child("VERIFY")
        pass_1 = verify_1.add_child("PASS?")
        pass_1.add_child("YES -> ACCEPT_CHANGE")
        pass_1.add_child("NO -> REJECT_CHANGE")

        owner_no = owner_match.add_child("NO")
        overlap = owner_no.add_child("OVERLAP_ONLY?")
        overlap.add_child("YES -> RESOLVE_BOUNDARY_FIRST")
        new_auth = overlap.add_child("NO -> CREATE_NEW_CLASS_FOR_TRUE_NEW_AUTHORITY")
        complete_2 = new_auth.add_child("RUN_COMPLETENESS_CHECK")
        contract_2 = complete_2.add_child("RUN_CONTRACT_CHECK")
        tests_2 = contract_2.add_child("RUN_TESTS")
        verify_2 = tests_2.add_child("VERIFY")
        pass_2 = verify_2.add_child("PASS?")
        pass_2.add_child("YES -> ACCEPT_CHANGE")
        pass_2.add_child("NO -> REJECT_CHANGE")

        no_dup = duplicate.add_child("NO")
        create = no_dup.add_child("CREATE_NEW_CLASS_CANDIDATE")
        complete_3 = create.add_child("RUN_COMPLETENESS_CHECK")
        contract_3 = complete_3.add_child("RUN_CONTRACT_CHECK")
        tests_3 = contract_3.add_child("RUN_TESTS")
        verify_3 = tests_3.add_child("VERIFY")
        pass_3 = verify_3.add_child("PASS?")
        pass_3.add_child("YES -> ACCEPT_CHANGE")
        pass_3.add_child("NO -> REJECT_CHANGE")

        edit = identify.add_child("EDIT_EXISTING")
        edit_owner = edit.add_child("LOCATE_OWNER_CLASS")
        edit_belongs = edit_owner.add_child("CHANGE_BELONGS_TO_OWNER?")
        edit_yes = edit_belongs.add_child("YES")
        edit_apply = edit_yes.add_child("APPLY_CHANGE_INSIDE_OWNER")
        edit_check = edit_apply.add_child("RUN_COMPLETENESS_CHECK")
        edit_test = edit_check.add_child("RUN_REGRESSION_TEST")
        edit_verify = edit_test.add_child("VERIFY")
        edit_pass = edit_verify.add_child("PASS?")
        edit_pass.add_child("YES -> ACCEPT_CHANGE")
        edit_pass.add_child("NO -> REJECT_CHANGE")
        edit_belongs.add_child("NO -> ROUTE_TO_CORRECT_OWNER")

        refactor = identify.add_child("REFACTOR_INTERNAL")
        refactor_shape = refactor.add_child("KEEP_SAME_AUTHORITY")
        refactor_clean = refactor_shape.add_child("REMOVE_INTERNAL_CONFUSION")
        refactor_eq = refactor_clean.add_child("RUN_BEHAVIOR_EQUIVALENCE_TEST")
        refactor_pass = refactor_eq.add_child("PASS?")
        refactor_pass.add_child("YES -> ACCEPT_REFACTOR")
        refactor_pass.add_child("NO -> REJECT_REFACTOR")

        split = identify.add_child("SPLIT_DOMAIN")
        split_proof = split.add_child("PROVE_NEW_INDEPENDENT_AUTHORITY")
        split_ok = split_proof.add_child("PROOF_PASS?")
        split_yes = split_ok.add_child("YES")
        split_make = split_yes.add_child("CREATE_NEW_OWNER_CLASS")
        split_verify = split_make.add_child("VERIFY_NON_OVERLAPPING_BOUNDARIES")
        split_verify.add_child("PASS -> ACCEPT_SPLIT")
        split_ok.add_child("NO -> SPLIT_FORBIDDEN")

        merge = identify.add_child("MERGE_DOMAINS")
        merge_find = merge.add_child("IDENTIFY_ILLEGAL_SHARED_AUTHORITY")
        merge_owner = merge_find.add_child("MOVE_BEHAVIOR_TO_SINGLE_OWNER")
        merge_verify = merge_owner.add_child("VERIFY_ONE_COMPLETE_OWNER")
        merge_verify.add_child("PASS -> ACCEPT_MERGE")
        merge_verify.add_child("FAIL -> REJECT_MERGE")

        delete = identify.add_child("DELETE_CLASS")
        delete_refs = delete.add_child("SEARCH_ALL_REFERENCES")
        delete_needed = delete_refs.add_child("OWNER_STILL_NEEDED?")
        delete_needed.add_child("YES -> DELETE_FORBIDDEN")
        delete_no = delete_needed.add_child("NO")
        delete_loss = delete_no.add_child("UNIQUE_AUTHORITY_LOST?")
        delete_loss.add_child("YES -> DELETE_FORBIDDEN")
        delete_safe = delete_loss.add_child("NO -> VERIFY_REPLACEMENT_AND_CALLERS")
        delete_safe.add_child("PASS -> DELETE_ALLOWED")
        delete_safe.add_child("FAIL -> REJECT_DELETE")

        verify_only = identify.add_child("VERIFY_ONLY")
        v1 = verify_only.add_child("VERIFY_WORKSPACE_SEARCH_WAS_DONE")
        v2 = v1.add_child("VERIFY_ACTION_TYPE_WAS_CORRECT")
        v3 = v2.add_child("VERIFY_NO_DUPLICATE_AUTHORITY_EXISTS")
        v4 = v3.add_child("VERIFY_OWNER_MORE_COMPLETE_THAN_BEFORE")
        v5 = v4.add_child("VERIFY_CONTRACT_IS_EXPLICIT")
        v6 = v5.add_child("VERIFY_CONFIG_IS_EXTERNALIZED")
        v7 = v6.add_child("VERIFY_ERROR_SURFACE_IS_EXPLICIT")
        v8 = v7.add_child("VERIFY_TESTS_PASS")
        v9 = v8.add_child("VERIFY_NO_LAW_BROKEN")
        v9.add_child("PASS -> ACCEPT_CHANGE")
        v9.add_child("FAIL -> REJECT_CHANGE")

        return root

    def read_root(self):
        return self.state["root"]

    def render_ascii(self):
        root = self.read_root()
        if root is None:
            return ""

        lines = []
        self.render_ascii_node(root, 0, lines)
        return "\n".join(lines)

    def render_ascii_node(self, node, depth, lines):
        name = node.read_name()
        children = node.read_children()

        if depth == 0:
            lines.append(name)
        else:
            indent = "    " * depth
            lines.append(indent + "|-- " + name)

        index = 0
        total = len(children)
        while index < total:
            child = children[index]
            self.render_ascii_node(child, depth + 1, lines)
            index = index + 1


class VBStyleTreeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mem = {}
        self.db = {}
        self.state = {}
        self.state["tree_engine"] = VBStyleClassAspectTree()
        self.state["root_node"] = None
        self.state["all_items"] = []

        self.setup_window()
        self.setup_actions()
        self.setup_toolbar()
        self.setup_central()
        self.load_tree()

    def setup_window(self):
        self.setWindowTitle("VBSTYLE Class Aspect Tree")
        self.resize(1500, 900)

    def setup_actions(self):
        self.state["action_expand"] = QAction("Expand All", self)
        self.state["action_expand"].triggered.connect(self.expand_all_nodes)

        self.state["action_collapse"] = QAction("Collapse All", self)
        self.state["action_collapse"].triggered.connect(self.collapse_all_nodes)

        self.state["action_reload"] = QAction("Reload", self)
        self.state["action_reload"].triggered.connect(self.load_tree)

        self.state["action_export_ascii"] = QAction("Export ASCII", self)
        self.state["action_export_ascii"].triggered.connect(self.export_ascii_to_right_panel)

        self.state["action_about"] = QAction("About", self)
        self.state["action_about"].triggered.connect(self.show_about)

    def setup_toolbar(self):
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addAction(self.state["action_expand"])
        toolbar.addAction(self.state["action_collapse"])
        toolbar.addAction(self.state["action_reload"])
        toolbar.addAction(self.state["action_export_ascii"])

        toolbar.addSeparator()

        self.state["search_label"] = QLabel("Search")
        toolbar.addWidget(self.state["search_label"])

        self.state["search_input"] = QLineEdit()
        self.state["search_input"].setPlaceholderText("Find node text...")
        self.state["search_input"].textChanged.connect(self.filter_tree_items)
        toolbar.addWidget(self.state["search_input"])

        self.state["clear_button"] = QPushButton("Clear")
        self.state["clear_button"].clicked.connect(self.clear_search)
        toolbar.addWidget(self.state["clear_button"])

        toolbar.addSeparator()
        toolbar.addAction(self.state["action_about"])

    def setup_central(self):
        wrapper = QWidget()
        layout = QVBoxLayout()
        wrapper.setLayout(layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.state["tree_widget"] = QTreeWidget()
        self.state["tree_widget"].setHeaderLabels(["VBSTYLE Decision Tree"])
        self.state["tree_widget"].itemSelectionChanged.connect(self.on_item_selected)
        self.state["tree_widget"].setAlternatingRowColors(True)
        self.state["tree_widget"].setUniformRowHeights(False)

        self.state["detail_panel"] = QPlainTextEdit()
        self.state["detail_panel"].setReadOnly(True)
        self.state["detail_panel"].setPlaceholderText("Node detail appears here.")

        font = QFont("Menlo")
        font.setPointSize(11)
        self.state["detail_panel"].setFont(font)

        splitter.addWidget(self.state["tree_widget"])
        splitter.addWidget(self.state["detail_panel"])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([900, 600])

        layout.addWidget(splitter)
        self.setCentralWidget(wrapper)

    def load_tree(self):
        engine = self.state["tree_engine"]
        engine.build_default_tree()
        root = engine.read_root()
        self.state["root_node"] = root
        self.populate_tree_widget()
        self.export_ascii_to_right_panel()

    def populate_tree_widget(self):
        tree_widget = self.state["tree_widget"]
        tree_widget.clear()
        self.state["all_items"] = []

        root_node = self.state["root_node"]
        if root_node is None:
            return

        root_item = QTreeWidgetItem([root_node.read_name()])
        tree_widget.addTopLevelItem(root_item)
        self.state["all_items"].append(root_item)

        self.populate_tree_children(root_item, root_node)
        tree_widget.expandToDepth(2)
        tree_widget.setCurrentItem(root_item)

    def populate_tree_children(self, parent_item, parent_node):
        children = parent_node.read_children()
        index = 0
        total = len(children)

        while index < total:
            child_node = children[index]
            child_item = QTreeWidgetItem([child_node.read_name()])
            parent_item.addChild(child_item)
            self.state["all_items"].append(child_item)
            self.populate_tree_children(child_item, child_node)
            index = index + 1

    def expand_all_nodes(self):
        self.state["tree_widget"].expandAll()

    def collapse_all_nodes(self):
        self.state["tree_widget"].collapseAll()

    def clear_search(self):
        self.state["search_input"].clear()

    def filter_tree_items(self):
        query = self.state["search_input"].text().strip().lower()
        tree_widget = self.state["tree_widget"]

        if query == "":
            self.show_all_items()
            return

        self.hide_all_items()
        self.show_matching_paths(query)
        tree_widget.expandAll()

    def hide_all_items(self):
        items = self.state["all_items"]
        index = 0
        total = len(items)

        while index < total:
            item = items[index]
            item.setHidden(True)
            index = index + 1

    def show_all_items(self):
        items = self.state["all_items"]
        index = 0
        total = len(items)

        while index < total:
            item = items[index]
            item.setHidden(False)
            index = index + 1

    def show_matching_paths(self, query):
        items = self.state["all_items"]
        index = 0
        total = len(items)

        while index < total:
            item = items[index]
            text = item.text(0).lower()
            if query in text:
                self.show_item_and_parents(item)
                self.show_children_recursive(item)
            index = index + 1

    def show_item_and_parents(self, item):
        current = item
        while current is not None:
            current.setHidden(False)
            current = current.parent()

    def show_children_recursive(self, item):
        item.setHidden(False)
        count = item.childCount()
        index = 0

        while index < count:
            child = item.child(index)
            self.show_children_recursive(child)
            index = index + 1

    def on_item_selected(self):
        selected_items = self.state["tree_widget"].selectedItems()
        if len(selected_items) == 0:
            return

        item = selected_items[0]
        path_text = self.build_item_path(item)
        child_count = item.childCount()
        detail_lines = []
        detail_lines.append("NODE")
        detail_lines.append(path_text)
        detail_lines.append("")
        detail_lines.append("CHILD_COUNT")
        detail_lines.append(str(child_count))
        detail_lines.append("")
        detail_lines.append("TEXT")
        detail_lines.append(item.text(0))

        self.state["detail_panel"].setPlainText("\n".join(detail_lines))

    def build_item_path(self, item):
        parts = []
        current = item

        while current is not None:
            parts.insert(0, current.text(0))
            current = current.parent()

        return " -> ".join(parts)

    def export_ascii_to_right_panel(self):
        engine = self.state["tree_engine"]
        ascii_text = engine.render_ascii()
        self.state["detail_panel"].setPlainText(ascii_text)

    def show_about(self):
        QMessageBox.information(
            self,
            "About",
            "VBSTYLE tree viewer shell.\n\n"
            "Left: interactive tree\n"
            "Right: node detail or ASCII export\n\n"
            "Humanity keeps inventing complexity, so the least we can do is draw the damn tree clearly."
        )


def main():
    app = QApplication(sys.argv)
    window = VBStyleTreeViewer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# === ChatCompressorStore, CoreDB, DataclassBlock, MethodBlock, StorageSplitter (from 69cc0c1e @ 1775302885.140082) ===
#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


# ============================================================
# CONFIG
# ============================================================

AUTHORITY_FILES = {
    "core": "Core_DB.py",
    "schema_chat": "DB_Schema_Chat.py",
    "schema_ui_legacy": "DB_Schema_UI_Legacy.py",
    "schema_gui_law": "DB_Schema_GUI_Law.py",
    "schema_gui_layout": "DB_Schema_GUI_Layout.py",
    "schema_gui_runtime": "DB_Schema_GUI_Runtime.py",
    "seed_ui_legacy": "DB_Seed_UI_Legacy.py",
    "seed_gui_law": "DB_Seed_GUI_Law.py",
    "seed_gui_layout": "DB_Seed_GUI_Layout.py",
    "seed_gui_runtime": "DB_Seed_GUI_Runtime.py",
    "query_chat": "DB_Query_Chat.py",
    "query_embeddings": "DB_Query_Embeddings.py",
    "query_imports": "DB_Query_Imports.py",
    "query_settings": "DB_Query_Settings.py",
    "query_ui_legacy": "DB_Query_UI_Legacy.py",
    "query_gui_law": "DB_Query_GUI_Law.py",
    "query_gui_layout": "DB_Query_GUI_Layout.py",
    "query_gui_runtime": "DB_Query_GUI_Runtime.py",
    "report_chat": "DB_Report_Chat.py",
    "report_threads": "DB_Report_Threads.py",
}

QUERY_CLASS_NAMES = {
    "query_chat": "DBQueryChat",
    "query_embeddings": "DBQueryEmbeddings",
    "query_imports": "DBQueryImports",
    "query_settings": "DBQuerySettings",
    "query_ui_legacy": "DBQueryUILegacy",
    "query_gui_law": "DBQueryGUILaw",
    "query_gui_layout": "DBQueryGUILayout",
    "query_gui_runtime": "DBQueryGUIRuntime",
    "report_chat": "DBReportChat",
    "report_threads": "DBReportThreads",
}

SEED_CLASS_NAMES = {
    "seed_ui_legacy": "DBSeedUILegacy",
    "seed_gui_law": "DBSeedGUILaw",
    "seed_gui_layout": "DBSeedGUILayout",
    "seed_gui_runtime": "DBSeedGUIRuntime",
}

SCHEMA_CLASS_NAMES = {
    "schema_chat": "DBSchemaChat",
    "schema_ui_legacy": "DBSchemaUILegacy",
    "schema_gui_law": "DBSchemaGUILaw",
    "schema_gui_layout": "DBSchemaGUILayout",
    "schema_gui_runtime": "DBSchemaGUIRuntime",
}

ROOT_README = "README_Codex.md"
FACADE_FILE = "storage.py"


# ============================================================
# DATA
# ============================================================

@dataclass
class MethodBlock:
    name: str
    source: str
    authority: str


@dataclass
class DataclassBlock:
    name: str
    source: str
    authority: str


# ============================================================
# SMALL HELPERS
# ============================================================

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def unparse_node(node: ast.AST, source_text: str) -> str:
    segment = ast.get_source_segment(source_text, node)
    if segment is None:
        return ast.unparse(node)
    return segment


def collect_import_block(module: ast.Module, source_text: str) -> str:
    lines: List[str] = []
    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            lines.append(unparse_node(node, source_text))
    imports = "\n".join(lines).strip()
    return imports


def normalize_code_block(text: str) -> str:
    return textwrap.dedent(text).strip("\n")


def split_sql_statements(sql_text: str) -> List[str]:
    parts = []
    current = []
    for line in sql_text.splitlines():
        current.append(line)
        if line.strip().endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                parts.append(statement)
            current = []
    tail = "\n".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def detect_sql_authority(statement: str) -> str:
    lower = statement.lower()

    if " chat_" in lower or "chat_" in lower:
        return "schema_chat"

    if " ui_" in lower or "ui_" in lower:
        return "schema_ui_legacy"

    if " gui_surface_zone" in lower or " gui_layout_" in lower or "gui_widget_hierarchy_rule" in lower:
        return "schema_gui_layout"

    if " gui_widget_instance" in lower or " gui_widget_value" in lower or " gui_event_binding" in lower or " gui_widget_style" in lower or " gui_runtime_boot_phase" in lower:
        return "schema_gui_runtime"

    if " gui_" in lower:
        return "schema_gui_law"

    return "core"


def detect_dataclass_authority(name: str) -> str:
    if name.startswith("StoredChat") or name.startswith("StoredPacket") or name.startswith("StoredTopic") or name.startswith("StoredImported") or name.startswith("StoredEmbedding"):
        return "query_chat"
    if name.startswith("StoredProvider") or name.startswith("StoredUITheme") or name.startswith("StoredUIAction") or name.startswith("StoredUIComponent") or name.startswith("StoredUIEvent") or name.startswith("StoredUICall") or name.startswith("StoredUIEventBinding"):
        return "query_ui_legacy"
    if name.startswith("StoredGUIProperty") or name.startswith("StoredGUIWidgetType") or name.startswith("StoredGUIEventDef") or name.startswith("StoredGUIActionTarget") or name.startswith("StoredGUITargetCompatibility") or name.startswith("StoredGUIThemeDef") or name.startswith("StoredGUIFontDef") or name.startswith("StoredGUIAsset") or name.startswith("StoredGUIStyleDef"):
        return "query_gui_law"
    if name.startswith("StoredGUISurface") or name.startswith("StoredGUILayout") or name.startswith("StoredGUIWidgetHierarchyRule"):
        return "query_gui_layout"
    if name.startswith("StoredGUIRuntime") or name.startswith("StoredGUIWidgetInstance") or name.startswith("StoredGUIWidgetValue") or name.startswith("StoredGUIWidgetStyle"):
        return "query_gui_runtime"
    return "core"


def detect_method_authority(name: str) -> str:
    if name in {"__init__", "_connect", "_initialize"}:
        return "core"

    if name == "_seed_ui_defaults":
        return "seed_ui_legacy"

    if name == "_seed_gui_runtime_defaults":
        return "seed_gui_law"

    if name.startswith("set_setting") or name.startswith("get_setting") or name.startswith("list_settings") or "provider_credentials" in name:
        return "query_settings"

    if "embedding" in name or name.startswith("embed_") or name.startswith("flush_embeddings") or name.startswith("count_embeddings"):
        return "query_embeddings"

    if "import" in name or "_record_imported_source" == name or "_read_text_file" == name:
        return "query_imports"

    if name.startswith("list_ui_") or name.startswith("get_ui_") or name.startswith("resolve_ui_"):
        return "query_ui_legacy"

    if name.startswith("list_gui_property") or name.startswith("list_gui_widget_types") or name.startswith("list_gui_widget_type_properties") or name.startswith("list_gui_event_definitions") or name.startswith("list_gui_widget_type_events") or name.startswith("list_gui_action_targets") or name.startswith("list_gui_target_compatibility") or name.startswith("list_gui_themes") or name.startswith("list_gui_font_definitions") or name.startswith("list_gui_assets") or name.startswith("list_gui_style_definitions"):
        return "query_gui_law"

    if name.startswith("list_gui_surfaces") or name.startswith("list_gui_surface_zones") or name.startswith("list_gui_layout_definitions") or name.startswith("list_gui_layout_items") or name.startswith("list_gui_widget_hierarchy_rules"):
        return "query_gui_layout"

    if name.startswith("list_gui_widget_instances") or name.startswith("list_gui_widget_values") or name.startswith("list_gui_event_bindings") or name.startswith("list_gui_widget_styles") or name.startswith("list_gui_runtime_boot_phases") or name.startswith("get_gui_surface_assembly_summary"):
        return "query_gui_runtime"

    if name.startswith("build_memory_report") or name.startswith("export_memory_report"):
        return "report_chat"

    if "thread" in name and ("topic" in name or "dossier" in name):
        return "report_threads"

    if name.startswith("save_compression") or name.startswith("load_latest_session") or name.startswith("list_recent_sessions") or name.startswith("search_session") or name.startswith("search_sessions") or name.startswith("find_sessions_by_tag") or name.startswith("find_packets_by_tag") or name.startswith("find_related_packets") or name.startswith("find_session_memory_hits") or name.startswith("load_session") or name.startswith("_load_packets") or name.startswith("_build_session") or name.startswith("_build_summary") or name.startswith("_load_packet_types") or name.startswith("_load_tags") or name.startswith("_load_packet_tags") or name.startswith("_load_tags_for_session_id") or name.startswith("_row_to_packet") or name.startswith("_row_to_packet_link") or name.startswith("_create_packet_links") or name.startswith("_find_packet_link_candidates") or name.startswith("_shared_link_tags") or name.startswith("_derive_session_tags") or name.startswith("_derive_packet_tags") or name.startswith("_tag_candidates_from_atom") or name.startswith("_normalize_tag") or name.startswith("_normalize_tag_query") or name.startswith("list_top_tags") or name.startswith("count_packet_links"):
        return "query_chat"

    return "core"


def extract_executescript_sql(method_src: str) -> str:
    match = re.search(r'connection\.executescript\(\s*("""|\'\'\')(.+?)\1\s*\)', method_src, re.S)
    if not match:
        return ""
    return match.group(2)


# ============================================================
# BUILDERS
# ============================================================

def build_schema_module(import_block: str, class_name: str, sql_statements: List[str]) -> str:
    sql_text = "\n\n".join(sql_statements).strip()
    return f'''from __future__ import annotations

{import_block}


class {class_name}:
    def sql_text(self) -> str:
        return r"""
{sql_text}
        """.strip()
'''


def build_seed_module(import_block: str, class_name: str, method_source: str) -> str:
    cleaned = normalize_code_block(method_source)
    lines = cleaned.splitlines()
    if not lines:
        body = "def apply(self, connection):\n        return None"
    else:
        lines[0] = "def apply(self, connection):"
        body = "\n".join("    " + line if index > 0 else line for index, line in enumerate(lines))
    return f'''from __future__ import annotations

{import_block}


class {class_name}:
{textwrap.indent(body, "    ")}
'''


def build_query_module(import_block: str, class_name: str, dataclasses_src: List[str], methods_src: List[str]) -> str:
    dataclasses_text = "\n\n".join(normalize_code_block(x) for x in dataclasses_src).strip()
    method_blocks = []
    for source in methods_src:
        method_blocks.append(textwrap.indent(normalize_code_block(source), "    "))
    methods_text = "\n\n".join(method_blocks).strip()

    if not methods_text:
        methods_text = "    def __init__(self, core):\n        self.core = core"

    elif "def __init__(" not in methods_text:
        methods_text = "    def __init__(self, core):\n        self.core = core\n\n" + methods_text

    return f'''from __future__ import annotations

{import_block}

{dataclasses_text}


class {class_name}:
{methods_text}
'''


def build_core_module(import_block: str, top_level_helpers: List[str]) -> str:
    helpers_text = "\n\n".join(normalize_code_block(x) for x in top_level_helpers).strip()
    return f'''from __future__ import annotations

{import_block}

{helpers_text}


class CoreDB:
    def __init__(self, db_path):
        self.db_path = db_path

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
'''


def build_readme() -> str:
    return """# Storage Refactor Authority Map

## Non-negotiable law
- one domain = one authority
- do not mix schema + seed + query + report + runtime when the domain can be separated
- `ui_*` is legacy / bridge
- `gui_*` is long-term truth

## File ownership
- `Core_DB.py` = db path, connect, core transaction/setup helpers only
- `DB_Schema_Chat.py` = chat/session schema
- `DB_Schema_UI_Legacy.py` = legacy `ui_*` schema
- `DB_Schema_GUI_Law.py` = stable `gui_*` law schema
- `DB_Schema_GUI_Layout.py` = surface/layout/hierarchy schema
- `DB_Schema_GUI_Runtime.py` = widget instance/runtime schema
- `DB_Seed_UI_Legacy.py` = `ui_*` seed rows
- `DB_Seed_GUI_Law.py` = stable `gui_*` law seed rows
- `DB_Seed_GUI_Layout.py` = layout/hierarchy seed rows
- `DB_Seed_GUI_Runtime.py` = runtime widget/value/binding seed rows
- `DB_Query_Chat.py` = chat/session/tag/link/search load/save
- `DB_Query_Embeddings.py` = embedding persistence and counts
- `DB_Query_Imports.py` = import/source tracking
- `DB_Query_Settings.py` = app settings and credentials
- `DB_Query_UI_Legacy.py` = legacy `ui_*` query surface
- `DB_Query_GUI_Law.py` = stable `gui_*` law query surface
- `DB_Query_GUI_Layout.py` = surface/layout/hierarchy query surface
- `DB_Query_GUI_Runtime.py` = widget/value/binding/runtime query surface
- `DB_Report_Chat.py` = report/export for chat/session views
- `DB_Report_Threads.py` = thread/dossier/report surfaces

## Migration order
1. split DDL by authority
2. split seed surfaces by authority
3. split query/report methods by authority
4. leave top facade thin only
5. keep compatibility methods delegating internally
6. keep tests passing

## Do not do
- no `storage_helpers.py`
- no `storage_part1.py`
- no `storage_misc.py`
- no new tables added directly to facade
- no mixing `ui_*` and `gui_*` in one module unless bridge is explicitly marked
"""


def build_init_file() -> str:
    return """from .Core_DB import CoreDB
from .DB_Schema_Chat import DBSchemaChat
from .DB_Schema_UI_Legacy import DBSchemaUILegacy
from .DB_Schema_GUI_Law import DBSchemaGUILaw
from .DB_Schema_GUI_Layout import DBSchemaGUILayout
from .DB_Schema_GUI_Runtime import DBSchemaGUIRuntime
from .DB_Seed_UI_Legacy import DBSeedUILegacy
from .DB_Seed_GUI_Law import DBSeedGUILaw
from .DB_Seed_GUI_Layout import DBSeedGUILayout
from .DB_Seed_GUI_Runtime import DBSeedGUIRuntime
from .DB_Query_Chat import DBQueryChat
from .DB_Query_Embeddings import DBQueryEmbeddings
from .DB_Query_Imports import DBQueryImports
from .DB_Query_Settings import DBQuerySettings
from .DB_Query_UI_Legacy import DBQueryUILegacy
from .DB_Query_GUI_Law import DBQueryGUILaw
from .DB_Query_GUI_Layout import DBQueryGUILayout
from .DB_Query_GUI_Runtime import DBQueryGUIRuntime
from .DB_Report_Chat import DBReportChat
from .DB_Report_Threads import DBReportThreads
"""


def build_facade_file() -> str:
    return '''from __future__ import annotations

from pathlib import Path

from .storage import (
    CoreDB,
    DBSchemaChat,
    DBSchemaUILegacy,
    DBSchemaGUILaw,
    DBSchemaGUILayout,
    DBSchemaGUIRuntime,
    DBSeedUILegacy,
    DBSeedGUILaw,
    DBSeedGUILayout,
    DBSeedGUIRuntime,
    DBQueryChat,
    DBQueryEmbeddings,
    DBQueryImports,
    DBQuerySettings,
    DBQueryUILegacy,
    DBQueryGUILaw,
    DBQueryGUILayout,
    DBQueryGUIRuntime,
    DBReportChat,
    DBReportThreads,
)


class ChatCompressorStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else self._default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.core = CoreDB(self.db_path)

        self.query_chat = DBQueryChat(self.core)
        self.query_embeddings = DBQueryEmbeddings(self.core)
        self.query_imports = DBQueryImports(self.core)
        self.query_settings = DBQuerySettings(self.core)
        self.query_ui_legacy = DBQueryUILegacy(self.core)
        self.query_gui_law = DBQueryGUILaw(self.core)
        self.query_gui_layout = DBQueryGUILayout(self.core)
        self.query_gui_runtime = DBQueryGUIRuntime(self.core)
        self.report_chat = DBReportChat(self.core)
        self.report_threads = DBReportThreads(self.core)

        self.schema_chat = DBSchemaChat()
        self.schema_ui_legacy = DBSchemaUILegacy()
        self.schema_gui_law = DBSchemaGUILaw()
        self.schema_gui_layout = DBSchemaGUILayout()
        self.schema_gui_runtime = DBSchemaGUIRuntime()

        self.seed_ui_legacy = DBSeedUILegacy()
        self.seed_gui_law = DBSeedGUILaw()
        self.seed_gui_layout = DBSeedGUILayout()
        self.seed_gui_runtime = DBSeedGUIRuntime()

        self._initialize()

    def _default_db_path(self) -> Path:
        root = Path(__file__).resolve().parents[1]
        return root / "data" / "chat_compressor.db"

    def _initialize(self) -> None:
        with self.core.connect() as connection:
            connection.executescript("PRAGMA foreign_keys = ON;")
            connection.executescript(self.schema_chat.sql_text())
            connection.executescript(self.schema_ui_legacy.sql_text())
            connection.executescript(self.schema_gui_law.sql_text())
            connection.executescript(self.schema_gui_layout.sql_text())
            connection.executescript(self.schema_gui_runtime.sql_text())
            self.seed_ui_legacy.apply(connection)
            self.seed_gui_law.apply(connection)
            self.seed_gui_layout.apply(connection)
            self.seed_gui_runtime.apply(connection)

    def __getattr__(self, name):
        for unit in (
            self.query_chat,
            self.query_embeddings,
            self.query_imports,
            self.query_settings,
            self.query_ui_legacy,
            self.query_gui_law,
            self.query_gui_layout,
            self.query_gui_runtime,
            self.report_chat,
            self.report_threads,
        ):
            if hasattr(unit, name):
                return getattr(unit, name)
        raise AttributeError(name)
'''


# ============================================================
# MAIN SPLITTER
# ============================================================

class StorageSplitter:
    def __init__(self, source_file: Path):
        self.source_file = source_file
        self.source_text = read_text(source_file)
        self.module = ast.parse(self.source_text)

        self.import_block = collect_import_block(self.module, self.source_text)

        self.top_level_helpers: List[str] = []
        self.dataclasses_by_authority: Dict[str, List[str]] = {}
        self.methods_by_authority: Dict[str, List[str]] = {}
        self.schema_sql_by_authority: Dict[str, List[str]] = {}

    def run(self) -> None:
        self._collect_top_level_items()
        self._extract_store_class()
        self._write_files()

    def _collect_top_level_items(self) -> None:
        for node in self.module.body:
            if isinstance(node, ast.FunctionDef):
                self.top_level_helpers.append(unparse_node(node, self.source_text))
            elif isinstance(node, ast.Assign):
                self.top_level_helpers.append(unparse_node(node, self.source_text))
            elif isinstance(node, ast.AnnAssign):
                self.top_level_helpers.append(unparse_node(node, self.source_text))
            elif isinstance(node, ast.ClassDef):
                if any(self._is_dataclass_decorator(dec) for dec in node.decorator_list):
                    authority = detect_dataclass_authority(node.name)
                    self.dataclasses_by_authority.setdefault(authority, []).append(unparse_node(node, self.source_text))

    def _extract_store_class(self) -> None:
        for node in self.module.body:
            if isinstance(node, ast.ClassDef) and node.name == "ChatCompressorStore":
                self._extract_store_methods(node)
                return
        raise RuntimeError("ChatCompressorStore not found")

    def _extract_store_methods(self, class_node: ast.ClassDef) -> None:
        for item in class_node.body:
            if not isinstance(item, ast.FunctionDef):
                continue

            method_source = unparse_node(item, self.source_text)
            authority = detect_method_authority(item.name)
            self.methods_by_authority.setdefault(authority, []).append(method_source)

            if item.name == "_initialize":
                sql_text = extract_executescript_sql(method_source)
                if sql_text:
                    for statement in split_sql_statements(sql_text):
                        schema_authority = detect_sql_authority(statement)
                        if schema_authority != "core":
                            self.schema_sql_by_authority.setdefault(schema_authority, []).append(statement)

    def _write_files(self) -> None:
        storage_dir = self.source_file.parent / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        write_text(storage_dir / ROOT_README, build_readme())
        write_text(storage_dir / "__init__.py", build_init_file())
        write_text(self.source_file.parent / FACADE_FILE, build_facade_file())

        core_code = build_core_module(self.import_block, self.top_level_helpers)
        write_text(storage_dir / AUTHORITY_FILES["core"], core_code)

        for authority, class_name in SCHEMA_CLASS_NAMES.items():
            sql_list = self.schema_sql_by_authority.get(authority, [])
            module_code = build_schema_module(self.import_block, class_name, sql_list)
            write_text(storage_dir / AUTHORITY_FILES[authority], module_code)

        for authority, class_name in SEED_CLASS_NAMES.items():
            method_list = self.methods_by_authority.get(authority, [])
            seed_method = method_list[0] if method_list else "def apply(self, connection):\n    return None"
            module_code = build_seed_module(self.import_block, class_name, seed_method)
            write_text(storage_dir / AUTHORITY_FILES[authority], module_code)

        for authority, class_name in QUERY_CLASS_NAMES.items():
            dataclasses_src = self.dataclasses_by_authority.get(authority, [])
            methods_src = self.methods_by_authority.get(authority, [])
            module_code = build_query_module(self.import_block, class_name, dataclasses_src, methods_src)
            write_text(storage_dir / AUTHORITY_FILES[authority], module_code)

    def _is_dataclass_decorator(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == "dataclass"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id == "dataclass"
        return False


# ============================================================
# CLI
# ============================================================

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Split a giant storage.py into VBSTYLE authority-owned modules."
    )
    parser.add_argument(
        "source_file",
        help="Path to the current storage.py file",
    )
    args = parser.parse_args()

    source_file = Path(args.source_file).resolve()
    if not source_file.exists():
        raise FileNotFoundError(source_file)

    splitter = StorageSplitter(source_file)
    splitter.run()
    print(f"done: split output written beside {source_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# === DeterminismValidator (from 6a101ee2 @ 1779449440.959133) ===
import sqlite3
from collections import defaultdict

DB_PATH = "token_registry.db"


class DeterminismValidator:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.errors = []
        self.warnings = []

    # ----------------------------
    # MAIN ENTRY
    # ----------------------------
    def run(self):
        self.check_domain_uniqueness()
        self.check_fk_integrity()
        self.check_brackets_complete()
        self.check_rule_conflicts()
        self.check_orchestration_determinism()

        return self.report()

    # ----------------------------
    # 1. DOMAIN UNIQUENESS
    # ----------------------------
    def check_domain_uniqueness(self):
        self.cursor.execute("""
            SELECT domain_id, COUNT(*)
            FROM classes
            GROUP BY domain_id
            HAVING COUNT(*) > 1
        """)
        rows = self.cursor.fetchall()

        if rows:
            self.errors.append({
                "type": "DOMAIN_NOT_UNIQUE",
                "details": rows
            })

    # ----------------------------
    # 2. FK INTEGRITY (METHOD → CLASS)
    # ----------------------------
    def check_fk_integrity(self):
        self.cursor.execute("""
            SELECT m.method_id
            FROM methods m
            LEFT JOIN classes c ON m.class_id = c.class_id
            WHERE c.class_id IS NULL
        """)
        rows = self.cursor.fetchall()

        if rows:
            self.errors.append({
                "type": "ORPHAN_METHODS",
                "details": rows
            })

    # ----------------------------
    # 3. BRACKET COMPLETENESS
    # ----------------------------
    def check_brackets_complete(self):
        self.cursor.execute("""
            SELECT method_id
            FROM methods
            WHERE brackets IS NULL OR brackets = ''
        """)
        rows = self.cursor.fetchall()

        if rows:
            self.errors.append({
                "type": "MISSING_BRACKETS",
                "details": rows
            })

    # ----------------------------
    # 4. RULE CONFLICT CHECK
    # (detects multiple valid candidates per domain execution)
    # ----------------------------
    def check_rule_conflicts(self):
        self.cursor.execute("""
            SELECT class_id, domain_id, COUNT(*)
            FROM classes
            GROUP BY domain_id
        """)
        rows = self.cursor.fetchall()

        for class_id, domain_id, count in rows:
            if count > 1:
                self.errors.append({
                    "type": "DOMAIN_AMBIGUITY",
                    "domain": domain_id,
                    "count": count
                })

        # extra rule check (optional extension layer)
        self.cursor.execute("""
            SELECT class_id, COUNT(*)
            FROM rules
            GROUP BY class_id
            HAVING COUNT(*) = 0
        """)
        # no-op placeholder for future strict rule binding

    # ----------------------------
    # 5. ORCHESTRATION DETERMINISM
    # ----------------------------
    def check_orchestration_determinism(self):
        self.cursor.execute("""
            SELECT domain_id, MIN(boot_priority), MAX(boot_priority)
            FROM orchestration
            GROUP BY domain_id
        """)
        rows = self.cursor.fetchall()

        for domain_id, min_p, max_p in rows:
            if min_p != max_p:
                self.errors.append({
                    "type": "NON_DETERMINISTIC_BOOT_ORDER",
                    "domain": domain_id,
                    "min": min_p,
                    "max": max_p
                })

    # ----------------------------
    # FINAL REPORT
    # ----------------------------
    def report(self):
        return {
            "status": "PASS" if not self.errors else "FAIL",
            "errors": self.errors,
            "warnings": self.warnings
        }


if __name__ == "__main__":
    validator = DeterminismValidator(DB_PATH)
    result = validator.run()

    import json
    print(json.dumps(result, indent=2))


# === CascadeDeterminismMaxValidator (from 6a101ee2 @ 1779449499.779633) ===
import sqlite3
import hashlib
from collections import defaultdict

DB_PATH = "token_registry.db"


class CascadeDeterminismMaxValidator:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

        self.errors = []
        self.warnings = []
        self.graph_cache = {}

    # =========================
    # ENTRY POINT
    # =========================
    def run_full(self):
        self.level1_schema_integrity()
        self.level2_domain_closure()
        self.level3_method_resolution_uniqueness()
        self.level4_rule_conflict_detection()
        self.level5_execution_graph_simulation()

        return self.report()

    # =========================
    # LEVEL 1 — SCHEMA INTEGRITY
    # =========================
    def level1_schema_integrity(self):
        # orphan methods
        self.cur.execute("""
            SELECT m.method_id
            FROM methods m
            LEFT JOIN classes c ON m.class_id = c.class_id
            WHERE c.class_id IS NULL
        """)
        orphans = self.cur.fetchall()

        if orphans:
            self.errors.append(("ORPHAN_METHODS", orphans))

        # missing brackets
        self.cur.execute("""
            SELECT method_id
            FROM methods
            WHERE brackets IS NULL OR brackets = ''
        """)
        missing = self.cur.fetchall()

        if missing:
            self.errors.append(("MISSING_BRACKETS", missing))

    # =========================
    # LEVEL 2 — DOMAIN CLOSURE
    # =========================
    def level2_domain_closure(self):
        """
        Each domain must:
        - map to exactly one class
        - have at least one method
        """

        self.cur.execute("""
            SELECT domain_id, COUNT(*)
            FROM classes
            GROUP BY domain_id
        """)
        domain_counts = self.cur.fetchall()

        for domain, count in domain_counts:
            if count != 1:
                self.errors.append(("DOMAIN_NOT_UNIQUE", domain, count))

        # check methods exist per class
        self.cur.execute("""
            SELECT c.class_id, COUNT(m.method_id)
            FROM classes c
            LEFT JOIN methods m ON m.class_id = c.class_id
            GROUP BY c.class_id
        """)
        for cid, count in self.cur.fetchall():
            if count == 0:
                self.errors.append(("CLASS_HAS_NO_METHODS", cid))

    # =========================
    # LEVEL 3 — METHOD RESOLUTION UNIQUENESS
    # =========================
    def level3_method_resolution_uniqueness(self):
        """
        Simulates bracket-based resolution per class.
        Ensures deterministic single-result selection.
        """

        self.cur.execute("""
            SELECT class_id, brackets
            FROM methods
        """)
        rows = self.cur.fetchall()

        resolution_map = defaultdict(list)

        for class_id, brackets in rows:
            key = (class_id, brackets)
            resolution_map[key].append(class_id)

        for key, matches in resolution_map.items():
            if len(matches) > 1:
                self.errors.append(("AMBIGUOUS_METHOD_RESOLUTION", key, len(matches)))

    # =========================
    # LEVEL 4 — RULE CONFLICT DETECTION
    # =========================
    def level4_rule_conflict_detection(self):
        """
        Detect contradictory or overlapping rules.
        """

        self.cur.execute("""
            SELECT rule_id, class_id, rule_type, severity
            FROM rules
        """)
        rules = self.cur.fetchall()

        rule_index = defaultdict(list)

        for r in rules:
            _, class_id, rule_type, severity = r
            rule_index[class_id].append((rule_type, severity))

        for class_id, rule_set in rule_index.items():
            seen = set()
            for rule_type, severity in rule_set:
                if rule_type in seen:
                    self.errors.append(("RULE_CONFLICT", class_id, rule_type))
                seen.add(rule_type)

    # =========================
    # LEVEL 5 — EXECUTION GRAPH SIMULATION
    # =========================
    def level5_execution_graph_simulation(self):
        """
        Builds deterministic execution graph per domain.
        Ensures no cycles and stable ordering.
        """

        self.cur.execute("""
            SELECT c.class_id, c.domain_id, c.boot_priority
            FROM classes c
        """)
        classes = self.cur.fetchall()

        graph = defaultdict(list)

        for class_id, domain_id, priority in classes:
            graph[domain_id].append((priority, class_id))

        for domain, nodes in graph.items():
            nodes.sort(key=lambda x: x[0])

            # deterministic hash of execution order
            signature = hashlib.sha256(
                str(nodes).encode()
            ).hexdigest()

            if domain in self.graph_cache:
                if self.graph_cache[domain] != signature:
                    self.errors.append(("GRAPH_NON_DETERMINISTIC", domain))
            else:
                self.graph_cache[domain] = signature

    # =========================
    # FINAL REPORT
    # =========================
    def report(self):
        return {
            "status": "PASS" if not self.errors else "FAIL",
            "error_count": len(self.errors),
            "errors": self.errors,
            "warnings": self.warnings,
            "graph_signatures": self.graph_cache
        }


if __name__ == "__main__":
    v = CascadeDeterminismMaxValidator(DB_PATH)
    result = v.run_full()

    import json
    print(json.dumps(result, indent=2))


# === CascadeExecutionReplayEngine (from 6a101ee2 @ 1779449519.344034) ===
import sqlite3
import hashlib
import json
from collections import defaultdict

DB_PATH = "token_registry.db"


class CascadeExecutionReplayEngine:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

        self.execution_tree = {}
        self.graph = defaultdict(list)
        self.hashes = {}

    # =========================
    # ENTRY POINT
    # =========================
    def run_replay(self, intent="DEFAULT"):
        domains = self.load_domains()

        for domain in domains:
            self.execution_tree[domain] = self.build_domain_tree(domain, intent)

        final_hash = self.compute_global_hash(self.execution_tree)

        return {
            "intent": intent,
            "execution_tree": self.execution_tree,
            "deterministic_hash": final_hash
        }

    # =========================
    # LOAD DOMAINS
    # =========================
    def load_domains(self):
        self.cur.execute("SELECT DISTINCT domain_id FROM classes")
        return [d[0] for d in self.cur.fetchall()]

    # =========================
    # BUILD DOMAIN TREE
    # =========================
    def build_domain_tree(self, domain, intent):
        self.cur.execute("""
            SELECT class_id, boot_priority
            FROM classes
            WHERE domain_id = ?
        """, (domain,))
        classes = self.cur.fetchall()

        # deterministic ordering
        classes.sort(key=lambda x: x[1])

        tree = {
            "domain": domain,
            "execution_order": []
        }

        for class_id, priority in classes:
            node = self.build_class_node(class_id)
            tree["execution_order"].append(node)

        return tree

    # =========================
    # BUILD CLASS NODE
    # =========================
    def build_class_node(self, class_id):
        self.cur.execute("""
            SELECT method_id, brackets, domain_id
            FROM methods
            WHERE class_id = ?
        """, (class_id,))
        methods = self.cur.fetchall()

        resolved_methods = []

        for mid, brackets, domain_id in methods:
            resolved_methods.append({
                "method_id": mid,
                "brackets": brackets,
                "domain": domain_id
            })

        # deterministic ordering (by method_id for stability)
        resolved_methods.sort(key=lambda x: x["method_id"])

        node = {
            "class_id": class_id,
            "methods": resolved_methods,
            "method_count": len(resolved_methods)
        }

        return node

    # =========================
    # GLOBAL HASH (DETERMINISM PROOF)
    # =========================
    def compute_global_hash(self, tree):
        encoded = json.dumps(tree, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


# =========================
# RUN
# =========================
if __name__ == "__main__":
    engine = CascadeExecutionReplayEngine(DB_PATH)
    result = engine.run_replay(intent="GUI_BUILD")

    print(json.dumps(result, indent=2))


# === SpatialConstraintEngine (from 6a101ee2 @ 1779449647.452078) ===
import json
import hashlib


class SpatialConstraintEngine:
    def __init__(self):
        self.layout_tree = {}
        self.constraints = {
            "toolbar_height_ratio": 0.08,
            "sidebar_width_ratio": 0.2,
            "content_weight": 1.0,
            "min_button_width": 80,
            "min_button_height": 28,
            "padding": 10
        }

    # =========================
    # ENTRY POINT
    # =========================
    def build_layout(self, execution_tree, screen=(1200, 800)):
        width, height = screen

        layout = {
            "screen": {"width": width, "height": height},
            "domains": []
        }

        for domain_name, domain_data in execution_tree.items():
            layout["domains"].append(
                self.build_domain_layout(domain_name, domain_data, width, height)
            )

        layout["hash"] = self.hash_layout(layout)
        return layout

    # =========================
    # DOMAIN LAYOUT
    # =========================
    def build_domain_layout(self, domain, data, width, height):
        toolbar_h = int(height * self.constraints["toolbar_height_ratio"])
        sidebar_w = int(width * self.constraints["sidebar_width_ratio"])
        content_w = width - sidebar_w
        content_h = height - toolbar_h

        return {
            "domain": domain,
            "toolbar": self.build_toolbar(domain, width, toolbar_h),
            "sidebar": self.build_sidebar(domain, sidebar_w, content_h, toolbar_h),
            "content": self.build_content(data, content_w, content_h, sidebar_w, toolbar_h)
        }

    # =========================
    # TOOLBAR
    # =========================
    def build_toolbar(self, domain, width, height):
        buttons = [
            "File", "Edit", "View", "Run", "Debug"
        ]

        button_width = max(
            self.constraints["min_button_width"],
            width // len(buttons)
        )

        layout = []
        x = 0

        for b in buttons:
            layout.append({
                "label": b,
                "x": x,
                "y": 0,
                "width": button_width,
                "height": height
            })
            x += button_width

        return {
            "height": height,
            "buttons": layout
        }

    # =========================
    # SIDEBAR
    # =========================
    def build_sidebar(self, domain, width, height, y_offset):
        items = ["Domain", "Classes", "Methods", "Rules"]

        item_height = max(
            self.constraints["min_button_height"],
            height // len(items)
        )

        layout = []
        y = y_offset

        for item in items:
            layout.append({
                "label": item,
                "x": 0,
                "y": y,
                "width": width,
                "height": item_height
            })
            y += item_height

        return layout

    # =========================
    # CONTENT AREA
    # =========================
    def build_content(self, execution_data, width, height, x_offset, y_offset):
        classes = execution_data.get("execution_order", [])

        grid = []
        cols = 3
        cell_w = width // cols
        cell_h = 120

        x = x_offset
        y = y_offset

        col = 0

        for c in classes:
            grid.append({
                "class_id": c["class_id"],
                "x": x,
                "y": y,
                "width": cell_w,
                "height": cell_h,
                "methods": c["methods"]
            })

            col += 1
            x += cell_w

            if col >= cols:
                col = 0
                x = x_offset
                y += cell_h

        return grid

    # =========================
    # HASH (DETERMINISTIC PROOF)
    # =========================
    def hash_layout(self, layout):
        return hashlib.sha256(
            json.dumps(layout, sort_keys=True).encode()
        ).hexdigest()


# =========================
# RUN EXAMPLE
# =========================
if __name__ == "__main__":
    engine = SpatialConstraintEngine()

    dummy_execution_tree = {
        "IO": {
            "execution_order": [
                {"class_id": 1, "methods": [{"method_id": 10}, {"method_id": 11}]},
                {"class_id": 2, "methods": [{"method_id": 20}]}
            ]
        }
    }

    layout = engine.build_layout(dummy_execution_tree)

    import json
    print(json.dumps(layout, indent=2))


# === ConstraintSolver, DeterministicUIEngine, LayoutCritic, LayoutFixer, PixelRenderer (from 6a101ee2 @ 1779449783.483109) ===
import hashlib
import json
from copy import deepcopy


class ConstraintSolver:
    def solve(self, layout, constraints):
        """
        Deterministic constraint resolution:
        - no randomness
        - fixed priority rules
        """

        width = layout["screen"]["width"]
        height = layout["screen"]["height"]

        # enforce toolbar
        layout["toolbar"]["height"] = int(height * constraints["toolbar_ratio"])

        # enforce sidebar
        layout["sidebar"]["width"] = int(width * constraints["sidebar_ratio"])

        # enforce content bounds
        layout["content"]["width"] = width - layout["sidebar"]["width"]
        layout["content"]["height"] = height - layout["toolbar"]["height"]

        return layout


class PixelRenderer:
    def render(self, layout):
        """
        Converts layout → pixel model (abstract simulation)
        """
        canvas = []

        # toolbar pixels
        canvas.append(("toolbar", layout["toolbar"]))

        # sidebar pixels
        canvas.append(("sidebar", layout["sidebar"]))

        # content grid
        for cell in layout["content"]:
            canvas.append(("cell", cell))

        return canvas


class LayoutCritic:
    def evaluate(self, canvas):
        """
        Deterministic scoring:
        - no randomness
        - fixed heuristics
        """

        score = 100

        for item_type, item in canvas:
            # rule 1: minimum size enforcement
            if item.get("width", 0) < 80:
                score -= 10
            if item.get("height", 0) < 28:
                score -= 10

            # rule 2: missing geometry
            if "x" not in item or "y" not in item:
                score -= 15

        return score


class LayoutFixer:
    def fix(self, layout, score):
        """
        Deterministic corrections only
        """

        if score >= 90:
            return layout  # stable

        # enforce stricter minimums
        for cell in layout["content"]:
            cell["width"] = max(cell.get("width", 100), 120)
            cell["height"] = max(cell.get("height", 60), 40)

        return layout


class DeterministicUIEngine:
    def __init__(self):
        self.solver = ConstraintSolver()
        self.renderer = PixelRenderer()
        self.critic = LayoutCritic()
        self.fixer = LayoutFixer()

        self.constraints = {
            "toolbar_ratio": 0.08,
            "sidebar_ratio": 0.2
        }

    def run(self, execution_tree, screen=(1200, 800), max_iters=5):
        layout = self.build_initial_layout(execution_tree, screen)

        last_hash = None

        for i in range(max_iters):
            layout = self.solver.solve(layout, self.constraints)

            canvas = self.renderer.render(layout)

            score = self.critic.evaluate(canvas)

            layout = self.fixer.fix(layout, score)

            current_hash = self.hash(layout)

            # deterministic convergence check
            if current_hash == last_hash:
                break

            last_hash = current_hash

        return {
            "final_layout": layout,
            "canvas": canvas,
            "score": score,
            "hash": last_hash,
            "iterations": i + 1
        }

    def build_initial_layout(self, execution_tree, screen):
        width, height = screen

        content = []

        for domain, data in execution_tree.items():
            for node in data["execution_order"]:
                content.append({
                    "class_id": node["class_id"],
                    "width": 100,
                    "height": 60,
                    "x": 0,
                    "y": 0
                })

        return {
            "screen": {"width": width, "height": height},
            "toolbar": {},
            "sidebar": {},
            "content": content
        }

    def hash(self, layout):
        return hashlib.sha256(
            json.dumps(layout, sort_keys=True).encode()
        ).hexdigest()


# =========================
# RUN DEMO
# =========================
if __name__ == "__main__":
    engine = DeterministicUIEngine()

    dummy_execution_tree = {
        "IO": {
            "execution_order": [
                {"class_id": 1},
                {"class_id": 2},
                {"class_id": 3}
            ]
        }
    }

    result = engine.run(dummy_execution_tree)

    import json
    print(json.dumps(result, indent=2))


# === DBConstraintAuditor (from 6a101ee2 @ 1779454286.962721) ===
import sqlite3
from collections import defaultdict


class DBConstraintAuditor:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

        self.issues = []
        self.warnings = []

    # =========================
    # ENTRY POINT
    # =========================
    def run_audit(self):
        self.check_foreign_keys()
        self.check_orphaned_records()
        self.check_unlinked_reference_fields()
        self.check_soft_constraints()

        return self.report()

    # =========================
    # 1. FOREIGN KEY CHECKS
    # =========================
    def check_foreign_keys(self):
        self.cur.execute("PRAGMA foreign_key_check;")
        fk_violations = self.cur.fetchall()

        for v in fk_violations:
            self.issues.append({
                "type": "FOREIGN_KEY_BROKEN",
                "details": v
            })

    # =========================
    # 2. ORPHAN RECORD DETECTION
    # =========================
    def check_orphaned_records(self):
        """
        Generic orphan scan for known relations:
        classes -> methods
        methods -> rules (optional assumption)
        """

        # methods without valid class
        self.cur.execute("""
            SELECT m.method_id
            FROM methods m
            LEFT JOIN classes c ON m.class_id = c.class_id
            WHERE c.class_id IS NULL
        """)
        orphans = self.cur.fetchall()

        for o in orphans:
            self.issues.append({
                "type": "ORPHAN_METHOD",
                "method_id": o[0]
            })

    # =========================
    # 3. UNLINKED REFERENCE FIELD CHECK
    # =========================
    def check_unlinked_reference_fields(self):
        """
        Detect fields that look like references but are not enforced.
        Example patterns: *_id columns without real FK enforcement
        """

        self.cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = self.cur.fetchall()

        for table_name, sql in tables:
            if not sql:
                continue

            self.cur.execute(f"PRAGMA table_info({table_name})")
            cols = self.cur.fetchall()

            for col in cols:
                col_name = col[1]

                if col_name.endswith("_id"):
                    # heuristic: check if FK exists in schema definition
                    if "FOREIGN KEY" not in sql.upper():
                        self.warnings.append({
                            "type": "POSSIBLE_SOFT_REFERENCE",
                            "table": table_name,
                            "column": col_name,
                            "note": "appears to be reference but no FK constraint found"
                        })

    # =========================
    # 4. SOFT CONSTRAINT DRIFT CHECK
    # =========================
    def check_soft_constraints(self):
        """
        Detect nullable or unconstrained critical fields
        """

        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in self.cur.fetchall()]

        for table in tables:
            self.cur.execute(f"PRAGMA table_info({table})")
            cols = self.cur.fetchall()

            for col in cols:
                name = col[1]
                notnull = col[3]

                # heuristic: critical ID fields should not be nullable
                if name.endswith("_id") and not notnull:
                    self.warnings.append({
                        "type": "NULLABLE_REFERENCE_FIELD",
                        "table": table,
                        "column": name
                    })

    # =========================
    # REPORT
    # =========================
    def report(self):
        return {
            "status": "FAIL" if self.issues else "PASS",
            "issue_count": len(self.issues),
            "warning_count": len(self.warnings),
            "issues": self.issues,
            "warnings": self.warnings
        }


# =========================
# RUN
# =========================
if __name__ == "__main__":
    auditor = DBConstraintAuditor("token_registry.db")
    result = auditor.run_audit()

    import json
    print(json.dumps(result, indent=2))


# === App, DBConstraintEngine (from 6a101ee2 @ 1779456102.027991) ===
# (earlier:   App earlier versions: [('6a101ee2', 1779456001.052005)])
# (earlier:   DBConstraintEngine earlier versions: [('6a101ee2', 1779454943.687732), ('6a101ee2', 1779455212.290239), ('6a101ee2', 1779455814.92072), ('6a101ee2', 1779455914.726036), ('6a101ee2', 1779456001.052005)])
#!/usr/bin/env python3
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton, QLabel, QListWidget
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QByteArray


# ======================================================
# ENGINE (DETERMINISTIC CORE)
# ======================================================
class DBConstraintEngine:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA foreign_keys = ON;")

        self.state = {"issues": [], "warnings": [], "repairs": []}

        self.rules = {
            "ORPHAN_METHOD": self._repair_orphan,
            "FK_VIOLATION": self._repair_fk
        }

    # --------------------------
    def run(self):
        self.state = {"issues": [], "warnings": [], "repairs": []}
        self.audit()
        return self.state

    # --------------------------
    def audit(self):
        self._orphans()
        self._fk()

    def _orphans(self):
        cur = self.db.cursor()
        for (mid,) in cur.execute("""
            SELECT m.id FROM methods m
            LEFT JOIN classes c ON m.class_id = c.id
            WHERE c.id IS NULL
        """):
            self.state["issues"].append({
                "type": "ORPHAN_METHOD",
                "id": mid
            })

    def _fk(self):
        cur = self.db.cursor()
        for row in cur.execute("PRAGMA foreign_key_check;"):
            self.state["issues"].append({
                "type": "FK_VIOLATION",
                "table": row[0],
                "rowid": row[1]
            })

    # --------------------------
    def repair(self):
        for i in self.state["issues"]:
            fn = self.rules.get(i["type"], self._noop)
            fn(i)
        self.db.commit()

    def _repair_orphan(self, i):
        cur = self.db.cursor()
        cur.execute("""
            DELETE FROM methods
            WHERE class_id NOT IN (SELECT id FROM classes)
        """)
        self.state["repairs"].append({"type": "ORPHAN_FIX"})

    def _repair_fk(self, i):
        cur = self.db.cursor()
        cur.execute(f"DELETE FROM {i['table']} WHERE rowid = ?", (i["rowid"],))
        self.state["repairs"].append({"type": "FK_FIX"})

    def _noop(self, i):
        self.state["repairs"].append({"type": "NOOP"})


    # ======================================================
    # GRAPH MODEL (STRUCTURED, NOT STRING SVG)
    # ======================================================
    def graph(self):
        return {
            "nodes": [
                {"id": "db", "label": "DATABASE"},
                {"id": "issues", "label": f"ISSUES {len(self.state['issues'])}"},
                {"id": "warnings", "label": f"WARNINGS {len(self.state['warnings'])}"},
                {"id": "repairs", "label": f"REPAIRS {len(self.state['repairs'])}"}
            ],
            "edges": [
                ("db", "issues"),
                ("db", "warnings"),
                ("issues", "repairs")
            ]
        }

    # ======================================================
    # SVG RENDER (FROM GRAPH)
    # ======================================================
    def svg(self):
        g = self.graph()

        def node(x, y, label, color):
            return f"""
            <rect x="{x}" y="{y}" width="180" height="60" fill="{color}" rx="10"/>
            <text x="{x+90}" y="{y+35}" text-anchor="middle" fill="black">{label}</text>
            """

        svg = []
        svg.append('<svg width="900" height="500" xmlns="http://www.w3.org/2000/svg">')
        svg.append('<rect width="100%" height="100%" fill="#111"/>')

        svg.append('<text x="300" y="40" fill="white" font-size="18">DB CONSTRAINT GRAPH</text>')

        # static layout (deterministic)
        svg.append(node(80, 120, g["nodes"][0]["label"], "#4fc3f7"))
        svg.append(node(320, 120, g["nodes"][1]["label"], "#ff5252"))
        svg.append(node(320, 240, g["nodes"][2]["label"], "#ffd54f"))
        svg.append(node(560, 180, g["nodes"][3]["label"], "#69f0ae"))

        svg.append("</svg>")
        return "\n".join(svg)


# ======================================================
# GUI (LIVE + INTERACTIVE STATE VIEW)
# ======================================================
class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.engine = DBConstraintEngine("token_registry.db")

        self.setWindowTitle("DB Constraint MAX ENGINE")
        self.resize(1000, 650)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.svg_view = QSvgWidget()
        layout.addWidget(self.svg_view)

        self.info = QListWidget()
        layout.addWidget(self.info)

        btn_run = QPushButton("RUN AUDIT")
        btn_fix = QPushButton("RUN REPAIR")

        layout.addWidget(btn_run)
        layout.addWidget(btn_fix)

        btn_run.clicked.connect(self.audit)
        btn_fix.clicked.connect(self.repair)

        self.refresh()

    def audit(self):
        self.engine.run()
        self.refresh()

    def repair(self):
        self.engine.repair()
        self.refresh()

    def refresh(self):
        svg = self.engine.svg().encode()
        self.svg_view.load(QByteArray(svg))

        self.info.clear()
        self.info.addItem(f"Issues: {len(self.engine.state['issues'])}")
        self.info.addItem(f"Warnings: {len(self.engine.state['warnings'])}")
        self.info.addItem(f"Repairs: {len(self.engine.state['repairs'])}")


# ======================================================
# START
# ======================================================
if __name__ == "__main__":
    app = QApplication([])
    w = App()
    w.show()
    app.exec()


# === RenderPipeline (from 6a101ee2 @ 1779457205.816915) ===
class RenderPipeline:
    def __init__(self, layout_state):
        self.layout = layout_state

    def to_svg(self, graph):
        # deterministic rendering
        ...


# === RenderState (from 6a101ee2 @ 1779457332.364413) ===
@dataclass
class RenderState:
    nodes: Dict[str, Dict[str, Any]]   # position, color, label
    edges: list


# === ConstraintEngine, GraphNode, MainWindow (from 6a101ee2 @ 1779457375.730032) ===
# (earlier:   ConstraintEngine earlier versions: [('6a101ee2', 1779457332.364413)])
# (earlier:   MainWindow earlier versions: [('69cc0c1e', 1775263361.565535)])
import sys
import uuid
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem
)
from PyQt6.QtGui import QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QPointF


# ==========================================================
# 5. AUDIT ENGINE → PRODUCES IR ONLY
# ==========================================================

class ConstraintEngine:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def audit(self) -> List[ConstraintNode]:
        issues = []

        cur = self.db.cursor()

        # ORPHANS
        cur.execute("""
            SELECT m.id
            FROM methods m
            LEFT JOIN classes c ON m.class_id = c.id
            WHERE c.id IS NULL
        """)
        for (mid,) in cur.fetchall():
            issues.append(
                ConstraintNode(
                    id=str(uuid.uuid4()),
                    type="ORPHAN_METHOD",
                    table="methods",
                    column="class_id",
                    rowid=mid,
                    severity=2,
                    metadata={"method_id": mid}
                )
            )

        # FK VIOLATIONS
        for row in cur.execute("PRAGMA foreign_key_check;"):
            issues.append(
                ConstraintNode(
                    id=str(uuid.uuid4()),
                    type="FK_VIOLATION",
                    table=row[0],
                    column=None,
                    rowid=row[1],
                    severity=3,
                    metadata={"parent": row[2]}
                )
            )

        return issues


# ==========================================================
# 6. GRAPH NODE (BOUND TO LAYOUT STATE, NOT REBUILD LOGIC)
# ==========================================================

class GraphNode(QGraphicsRectItem):
    def __init__(self, node_id, label, layout: LayoutState):
        super().__init__(0, 0, 180, 70)
        self.node_id = node_id
        self.label = label
        self.layout = layout

        self.setBrush(QBrush(QColor("#2d3436")))
        self.setPen(QPen(QColor("#636e72")))
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)

        self.text = QGraphicsTextItem(label, self)
        self.text.setDefaultTextColor(Qt.GlobalColor.white)
        self.text.setPos(10, 10)

        x, y = self.layout.get(node_id)
        self.setPos(x, y)

    def mouseReleaseEvent(self, event):
        pos = self.scenePos()
        self.layout.set(self.node_id, (pos.x(), pos.y()))
        super().mouseReleaseEvent(event)


# ==========================================================
# 7. SVG RENDER (SAME LAYOUT STATE — NO DUPLICATION)
# ==========================================================

class SVGRenderer:
    def __init__(self, layout: LayoutState):
        self.layout = layout

    def render(self, nodes: dict):
        parts = []
        parts.append('<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">')

        for node_id, node in nodes.items():
            x, y = self.layout.get(node_id)
            parts.append(f"""
            <rect x="{x}" y="{y}" width="180" height="70" fill="#2d3436"/>
            <text x="{x+10}" y="{y+30}" fill="white">{node.label}</text>
            """)

        parts.append("</svg>")
        return "\n".join(parts)


# ==========================================================
# 8. MAIN WINDOW (NO REBUILD LOOP, ONLY UPDATE LOOP)
# ==========================================================

class MainWindow(QMainWindow):
    def __init__(self, engine, repair_engine, layout):
        super().__init__()

        self.engine = engine
        self.repair_engine = repair_engine
        self.layout = layout

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.nodes = {}

        self.refresh()

    def refresh(self):
        self.scene.clear()

        issues = self.engine.audit()

        # convert IR → visual nodes
        grouped = {}
        for i in issues:
            grouped.setdefault(i.type, []).append(i)

        y = 50
        for t, items in grouped.items():
            node_id = t
            self.layout.ensure(node_id, (100, y))

            node = GraphNode(node_id, f"{t}: {len(items)}", self.layout)
            node.setPos(*self.layout.get(node_id))

            self.scene.addItem(node)
            self.nodes[node_id] = node

            y += 120

    def run_repairs(self):
        issues = self.engine.audit()
        self.repair_engine.run_all(issues)
        self.refresh()


# === CompiledRule, ConstraintNode, LayoutState, RuleGraph (from 6a101ee2 @ 1779457375.730032) ===
# (earlier:   CompiledRule earlier versions: [('6a101ee2', 1779457205.816915), ('6a101ee2', 1779457332.364413)])
# (earlier:   ConstraintNode earlier versions: [('6a101ee2', 1779457205.816915), ('6a101ee2', 1779457332.364413)])
# (earlier:   LayoutState earlier versions: [('6a101ee2', 1779457205.816915), ('6a101ee2', 1779457332.364413)])
#!/usr/bin/env python3
# ==========================================================
# CONSTRAINT IR + RULE GRAPH + LAYOUT STATE
# SINGLE SOURCE OF TRUTH CORE
# ==========================================================

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Callable, List, Optional, Any


# ==========================================================
# 1. CONSTRAINT IR (INTERMEDIATE REPRESENTATION)
# ==========================================================

@dataclass(frozen=True)
class ConstraintNode:
    id: str
    type: str                  # ORPHAN_METHOD / FK_VIOLATION / etc
    table: str
    column: Optional[str]
    rowid: Optional[int]
    severity: int
    metadata: dict = field(default_factory=dict)


# ==========================================================
# 2. COMPILED RULE GRAPH (IMMUTABLE DISPATCH TABLE)
# ==========================================================

@dataclass(frozen=True)
class CompiledRule:
    name: str
    handler: Callable[[ConstraintNode, sqlite3.Connection], dict]


class RuleGraph:
    def __init__(self):
        self.rules: Dict[str, CompiledRule] = {}

    def register(self, rule: CompiledRule):
        self.rules[rule.name] = rule

    def resolve(self, constraint: ConstraintNode):
        rule = self.rules.get(constraint.type)
        if not rule:
            return None
        return rule.handler


# ==========================================================
# 3. LAYOUT STATE (THE VISUAL SOURCE OF TRUTH)
# ==========================================================

class LayoutState:
    def __init__(self):
        self.positions: Dict[str, tuple] = {}

    def get(self, node_id: str):
        return self.positions.get(node_id, (0, 0))

    def set(self, node_id: str, pos):
        self.positions[node_id] = (pos[0], pos[1])

    def ensure(self, node_id: str, fallback):
        if node_id not in self.positions:
            self.positions[node_id] = fallback


# ==========================================================
# 4. REPAIR ENGINE (NO SQL LOOKUPS IN RULE SELECTION)
# ==========================================================

class RepairEngine:
    def __init__(self, db: sqlite3.Connection, rule_graph: RuleGraph):
        self.db = db
        self.rule_graph = rule_graph
        self.repairs = []

    def execute(self, constraint: ConstraintNode):
        handler = self.rule_graph.resolve(constraint)
        if not handler:
            return {"status": "NO_RULE", "id": constraint.id}

        result = handler(constraint, self.db)
        self.repairs.append(result)
        return result

    def run_all(self, constraints: List[ConstraintNode]):
        self.repairs.clear()
        for c in constraints:
            self.execute(c)
        self.db.commit()
        return self.repairs


# === IRStateCache (from 6a101ee2 @ 1779457640.742178) ===
from typing import Dict, List

class IRStateCache:
    def __init__(self):
        self.previous: Dict[str, ConstraintNode] = {}
        self.current: Dict[str, ConstraintNode] = {}

    def commit(self):
        self.previous = self.current
        self.current = {}

    def diff(self):
        added = []
        removed = []
        changed = []

        prev_keys = set(self.previous.keys())
        curr_keys = set(self.current.keys())

        for k in curr_keys - prev_keys:
            added.append(self.current[k])

        for k in prev_keys - curr_keys:
            removed.append(self.previous[k])

        for k in curr_keys & prev_keys:
            if self.previous[k] != self.current[k]:
                changed.append((self.previous[k], self.current[k]))

        return added, removed, changed


# === IncrementalConstraintEngine (from 6a101ee2 @ 1779457640.742178) ===
class IncrementalConstraintEngine:
    def __init__(self, db, cache: IRStateCache):
        self.db = db
        self.cache = cache

    def audit(self):
        new_state = {}

        cur = self.db.cursor()

        # ORPHANS
        cur.execute("""
            SELECT m.id
            FROM methods m
            LEFT JOIN classes c ON m.class_id = c.id
            WHERE c.id IS NULL
        """)

        for (mid,) in cur.fetchall():
            node = ConstraintNode(
                id=f"orphan_{mid}",
                type="ORPHAN_METHOD",
                table="methods",
                column="class_id",
                rowid=mid,
                severity=2,
                metadata={"method_id": mid}
            )
            new_state[node.id] = node

        # FK
        for row in cur.execute("PRAGMA foreign_key_check;"):
            node = ConstraintNode(
                id=f"fk_{row[0]}_{row[1]}",
                type="FK_VIOLATION",
                table=row[0],
                column=None,
                rowid=row[1],
                severity=3,
                metadata={"parent": row[2]}
            )
            new_state[node.id] = node

        self.cache.current = new_state
        return self.cache.diff()


# === DependencyGraph (from 6a101ee2 @ 1779457640.742178) ===
class DependencyGraph:
    def __init__(self):
        self.edges = {}  # node_id -> set(depends_on)

    def add(self, node: ConstraintNode):
        deps = set()

        if node.type == "ORPHAN_METHOD":
            deps.add("classes")

        if node.type == "FK_VIOLATION":
            deps.add(node.table)

        self.edges[node.id] = deps

    def resolve_order(self, nodes: List[ConstraintNode]):
        # simple topological-ish ordering (deterministic fallback)
        scored = []
        for n in nodes:
            score = len(self.edges.get(n.id, []))
            scored.append((score, n))

        return [n for _, n in sorted(scored, key=lambda x: x[0])]


# === IncrementalRepairEngine (from 6a101ee2 @ 1779457640.742178) ===
class IncrementalRepairEngine:
    def __init__(self, db, rule_graph):
        self.db = db
        self.rules = rule_graph

    def apply_patch(self, added, removed, changed):
        results = []

        # only act on NEW + CHANGED
        targets = added + [c[1] for c in changed]

        for node in targets:
            handler = self.rules.resolve(node)
            if handler:
                results.append(handler(node, self.db))

        self.db.commit()
        return results


# === PatchRenderer (from 6a101ee2 @ 1779457640.742178) ===
class PatchRenderer:
    def __init__(self, scene, layout):
        self.scene = scene
        self.layout = layout
        self.nodes = {}

    def apply(self, added, removed, changed):
        # REMOVE ONLY WHAT DISAPPEARED
        for node in removed:
            if node.id in self.nodes:
                self.scene.removeItem(self.nodes[node.id])
                del self.nodes[node.id]

        # ADD ONLY NEW NODES
        for node in added:
            if node.id not in self.nodes:
                g = GraphNode(node.id, node.type, self.layout)
                x, y = self.layout.get(node.type)
                g.setPos(x, y)
                self.scene.addItem(g)
                self.nodes[node.id] = g

        # UPDATE ONLY CHANGED
        for old, new in changed:
            if new.id in self.nodes:
                item = self.nodes[new.id]
                item.text.setPlainText(new.type)


# === IncrementalSVG (from 6a101ee2 @ 1779457640.742178) ===
class IncrementalSVG:
    def __init__(self, layout):
        self.layout = layout

    def patch_render(self, added, removed, changed):
        ops = []

        for n in added:
            x, y = self.layout.get(n.type)
            ops.append(f"<rect x='{x}' y='{y}' width='180' height='70'/>")

        for n in removed:
            ops.append(f"<!-- remove {n.id} -->")

        for _, new in changed:
            x, y = self.layout.get(new.type)
            ops.append(f"<text x='{x}' y='{y}'>{new.type}</text>")

        return "\n".join(ops)


# === RepairEngine (from 6a101ee2 @ 1779457717.169153) ===
# (earlier:   RepairEngine earlier versions: [('6a101ee2', 1779457205.816915), ('6a101ee2', 1779457375.730032)])
class RepairEngine:
    def __init__(self, event_store: EventStore):
        self.store = event_store

    def fix_orphan(self, node):
        return self.store.append(
            "REMOVE_CONSTRAINT",
            {
                "id": node.id,
                "reason": "orphan_repair"
            }
        )

    def fix_fk(self, node):
        return self.store.append(
            "UPDATE_CONSTRAINT",
            {
                "id": node.id,
                "node": {
                    "type": "FK_FIXED",
                    "table": node.table
                }
            }
        )


# === IRRebuilder (from 6a101ee2 @ 1779457717.169153) ===
class IRRebuilder:
    def __init__(self):
        self.state = {}

    def apply(self, event: Event):
        t = event.type
        p = event.payload

        if t == "ADD_CONSTRAINT":
            self.state[p["id"]] = p["node"]

        elif t == "REMOVE_CONSTRAINT":
            self.state.pop(p["id"], None)

        elif t == "UPDATE_CONSTRAINT":
            self.state[p["id"]] = p["node"]

    def rebuild(self, events: List[Event]):
        self.state = {}
        for e in events:
            self.apply(e)
        return self.state


# === TimeMachine (from 6a101ee2 @ 1779457717.169153) ===
class TimeMachine:
    def __init__(self, store: EventStore):
        self.store = store

    def at_time(self, t: float):
        return [e for e in self.store.all() if e.timestamp <= t]

    def rebuild_at(self, t: float, rebuilder: IRRebuilder):
        events = self.at_time(t)
        return rebuilder.rebuild(events)


# === ProjectionLayer (from 6a101ee2 @ 1779457717.169153) ===
class ProjectionLayer:
    def __init__(self, layout):
        self.layout = layout

    def render(self, ir_state, scene):
        scene.clear()

        for node_id, node in ir_state.items():
            x, y = self.layout.get(node_id)

            item = GraphNode(node_id, node["type"], self.layout)
            item.setPos(x, y)
            scene.addItem(item)


# === SVGRenderer (from 6a101ee2 @ 1779457832.493312) ===
# (earlier:   SVGRenderer earlier versions: [('6a101ee2', 1779457375.730032)])
class SVGRenderer:
    def render(self, state):
        svg = ["<svg>"]

        for node, pos in state.get("layout", {}).items():
            svg.append(
                f'<rect x="{pos[0]}" y="{pos[1]}" width="120" height="50"/>'
            )

        svg.append("</svg>")
        return "\n".join(svg)


# === Event (from 6a101ee2 @ 1779457832.493312) ===
# (earlier:   Event earlier versions: [('6a101ee2', 1779457717.169153)])
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import uuid

@dataclass(frozen=True)
class Event:
    id: str
    timestamp: float
    branch_id: str
    parent_event_id: Optional[str]

    event_type: str   # AUDIT | ISSUE_DETECTED | REPAIR_APPLIED | UI_MOVE
    payload: Dict[str, Any]


# === EventStore (from 6a101ee2 @ 1779457832.493312) ===
# (earlier:   EventStore earlier versions: [('6a101ee2', 1779457717.169153)])
class EventStore:
    def __init__(self):
        self.events: List[Event] = []

    def append(self, event: Event):
        self.events.append(event)

    def get_branch(self, branch_id: str):
        return [e for e in self.events if e.branch_id == branch_id]

    def replay(self, branch_id: str):
        state = {}
        for e in self.get_branch(branch_id):
            state = self.apply(state, e)
        return state

    def apply(self, state, event):
        # deterministic reducer
        if event.event_type == "UI_MOVE":
            state.setdefault("layout", {})[event.payload["node"]] = event.payload["pos"]

        if event.event_type == "ISSUE_DETECTED":
            state.setdefault("issues", []).append(event.payload)

        if event.event_type == "REPAIR_APPLIED":
            state.setdefault("repairs", []).append(event.payload)

        return state


# === Branch (from 6a101ee2 @ 1779457832.493312) ===
@dataclass
class Branch:
    id: str
    parent_id: Optional[str]
    head_event_id: Optional[str]
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# === BranchingRepairEngine (from 6a101ee2 @ 1779457832.493312) ===
class BranchingRepairEngine:
    def __init__(self, store: EventStore):
        self.store = store

    def apply_repair(self, branch_id, issue, strategy):
        new_branch = str(uuid.uuid4())

        event = Event(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            branch_id=new_branch,
            parent_event_id=None,
            event_type="REPAIR_APPLIED",
            payload={
                "issue": issue,
                "strategy": strategy
            }
        )

        self.store.append(event)
        return new_branch


# === BranchMerger (from 6a101ee2 @ 1779457832.493312) ===
class BranchMerger:
    def merge(self, store: EventStore, branch_ids: List[str]):
        canonical = {}

        for bid in branch_ids:
            state = store.replay(bid)

            for k, v in state.items():
                if k not in canonical:
                    canonical[k] = v
                else:
                    # deterministic merge rule
                    canonical[k] = self.resolve(canonical[k], v)

        return canonical

    def resolve(self, a, b):
        # deterministic rule (NO randomness allowed)
        if isinstance(a, list):
            return sorted(set(a + b))
        if isinstance(a, dict):
            return {**a, **b}
        return a if len(str(a)) > len(str(b)) else b


# === DAGEvent (from 6a101ee2 @ 1779457880.007397) ===
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass(frozen=True)
class DAGEvent:
    id: str
    parents: List[str]   # multiple allowed (branch merge support)

    event_type: str
    payload: Dict[str, Any]

    version: int


# === Snapshot (from 6a101ee2 @ 1779457880.007397) ===
@dataclass
class Snapshot:
    event_id: str
    state: Dict[str, Any]


# === StateCache (from 6a101ee2 @ 1779457880.007397) ===
class StateCache:
    def __init__(self):
        self.snapshots: Dict[str, Snapshot] = {}

    def get(self, event_id):
        return self.snapshots.get(event_id)

    def put(self, event_id, state):
        self.snapshots[event_id] = Snapshot(event_id, state)


# === DAGRebuilder (from 6a101ee2 @ 1779457880.007397) ===
class DAGRebuilder:
    def __init__(self, store, cache):
        self.store = store
        self.cache = cache

    def rebuild(self, target_event_id):

        snapshot = self._find_closest_snapshot(target_event_id)

        state = snapshot.state if snapshot else {}

        path = self._trace_path(snapshot.event_id if snapshot else None,
                                target_event_id)

        for event in path:
            state = self.apply(state, event)
            self.cache.put(event.id, state)

        return state


# === CompressedEvent (from 6a101ee2 @ 1779457880.007397) ===
@dataclass
class CompressedEvent:
    id: str
    parents: List[str]
    delta_type: str
    delta: Dict[str, Any]


# === SnapshotPolicy (from 6a101ee2 @ 1779457880.007397) ===
class SnapshotPolicy:
    def should_snapshot(self, event_count, is_merge, is_heavy):
        return (
            event_count % 30 == 0 or
            is_merge or
            is_heavy
        )


# #####################################################################
# === STANDALONE HELPER FUNCTIONS AND CONSTANTS (no class container) ===
# #####################################################################

# === RULE_GRAPH constant (earlier version) (from 6a101ee2 @ 1779457205.816915) ===
RULE_GRAPH = {
    "ORPHAN_METHOD": lambda ctx: repair_orphan(ctx),
    "FK_VIOLATION": lambda ctx: repair_fk(ctx),
    "NULLABLE_REFERENCE": lambda ctx: no_op(ctx),
}


# === cycle() main loop (earlier version) (from 6a101ee2 @ 1779457205.816915) ===
def cycle():
    issues = engine.audit()
    repairs = repair_engine.execute_all(issues)
    engine.commit(repairs)
    layout.update()
    render.refresh()


# === RULE_GRAPH constant (latest, with CompiledRule) (from 6a101ee2 @ 1779457332.364413) ===
RULE_GRAPH: Dict[str, CompiledRule] = {
    "ORPHAN": CompiledRule(
        name="ORPHAN",
        handler=lambda ctx: repair_orphan(ctx),
    ),

    "FK_VIOLATION": CompiledRule(
        name="FK_VIOLATION",
        handler=lambda ctx: repair_fk(ctx),
    ),

    "NULL_REF": CompiledRule(
        name="NULL_REF",
        handler=lambda ctx: no_op(ctx),
    ),
}


# === repair_orphan / repair_fk helpers (from 6a101ee2 @ 1779457332.364413) ===
def repair_orphan(ctx: ConstraintNode):
    return {
        "action": "QUARANTINE",
        "target": ctx.source_table,
        "id": ctx.row_id
    }


def repair_fk(ctx: ConstraintNode):
    return {
        "action": "DELETE",
        "target": ctx.source_table,
        "id": ctx.row_id
    }


def no_op(ctx: ConstraintNode):
    return {
        "action": "IGNORE",
        "id": ctx.id
    }


# === cycle() main loop helper (from 6a101ee2 @ 1779457332.364413) ===
def cycle(engine):
    engine.extract()     # DB → IR
    engine.resolve()     # IR → Repairs
    engine.commit()      # Apply changes

    return {
        "constraints": engine.state["constraints"],
        "repairs": engine.state["repairs"]
    }


# === build_state helper (from 6a101ee2 @ 1779457832.493312) ===
def build_state(store, branch_id):
    return store.replay(branch_id)


# === render() alternative renderer (from 6a101ee2 @ 1779457832.493312) ===
def render(self, state):
    for node_id, pos in state["layout"].items():
        node = self.nodes.get(node_id)

        if not node:
            node = create_node(node_id)
            self.scene.addItem(node)
            self.nodes[node_id] = node

        node.setPos(*pos)


# === _trace_path DAG helper (from 6a101ee2 @ 1779457880.007397) ===
def _trace_path(self, from_id, to_id):
    # DAG shortest path or dependency linearization
    visited = set()
    path = []

    def dfs(node):
        if node.id in visited:
            return
        visited.add(node.id)

        for p in node.parents:
            dfs(self.store.get(p))

        path.append(node)

    dfs(self.store.get(to_id))
    return path


# === apply() event helper (from 6a101ee2 @ 1779457880.007397) ===
def apply(self, state, event):
    if event.event_type == "DELTA":
        for k, v in event.payload.items():
            state[k] = v

    elif event.event_type == "REPAIR":
        state.setdefault("repairs", []).append(event.payload)

    elif event.event_type == "ISSUE":
        state.setdefault("issues", []).append(event.payload)

    return state

