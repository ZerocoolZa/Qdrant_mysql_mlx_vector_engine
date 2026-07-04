#!/usr/bin/env python3
# [@GHOST]{file_path="core/Dom_Gui/AuthorityErdGui.py" date="2026-07-04" author="Devin" context="GPU-accelerated ERD visualization using QGraphicsView + OpenGL"}
# [@VBSTYLE]{auth="system" role="erd_gui" return="Tuple3" orch="none" no="decorators|print|hardcoded|tabs|self_underscore"}
# [@FILEID]{id="AuthorityErdGui.py" domain="gui" authority="erd_gui"}
# [@SUMMARY]{PyQt6 GPU-accelerated ERD: QGraphicsView + QOpenGLWidget viewport. Drag tables, zoom, pan, FK lines.}

"""
AuthorityErdGui — GPU-accelerated ERD visualization for the laws database.

Uses QGraphicsView + QGraphicsScene with QOpenGLWidget viewport for GPU rendering.
  - 8 authority tables (top row) with entry counts + column list
  - 16 entity tables with row counts + FK columns
  - FK bezier curves connecting entities to authorities
  - Drag tables to rearrange (GPU-accelerated)
  - Mouse wheel to zoom, middle-drag to pan
  - Click to highlight FK connections

Run: python3 AuthorityErdGui.py
"""

import sys
import mysql.connector
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QHBoxLayout, QScrollArea, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsPathItem,
    QGraphicsTextItem, QStyleOptionGraphicsItem, QLineEdit,
    QToolBar,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
    QLinearGradient, QFontMetrics, QPolygonF, QIcon, QAction,
)


AUTHORITY_TABLES = [
    "status", "priority", "severity", "confidence",
    "type", "QuestionType", "domain", "category",
]

AUTHORITY_COLORS = {
    "status":        (QColor(46, 90, 130),  QColor(26, 60, 100)),
    "priority":      (QColor(130, 45, 45),  QColor(90, 30, 30)),
    "severity":      (QColor(150, 70, 30),  QColor(110, 50, 20)),
    "confidence":    (QColor(50, 80, 120),  QColor(35, 60, 95)),
    "type":          (QColor(40, 100, 50),  QColor(25, 75, 35)),
    "QuestionType":  (QColor(80, 60, 120),  QColor(60, 40, 90)),
    "domain":        (QColor(120, 85, 35),  QColor(90, 65, 25)),
    "category":      (QColor(110, 50, 100), QColor(80, 35, 75)),
}

ENTITY_COLOR = (QColor(55, 58, 68), QColor(38, 40, 48))


class TableItem(QGraphicsItem):
    """A table box in the ERD scene — draggable, GPU-accelerated."""

    def __init__(self, name, count, columns, fk_columns, is_authority, colors):
        super().__init__()
        self.name = name
        self.count = count
        self.columns = columns
        self.fk_columns = fk_columns
        self.is_authority = is_authority
        self.colors = colors
        self.header_h = 28
        self.row_h = 16
        self.w = 170
        self.h = self.header_h + len(columns) * self.row_h + 8
        self.is_active = False
        self.is_connected = False
        self.is_dimmed = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)
        self.edges = []

    def boundingRect(self):
        return QRectF(0, 0, self.w, self.h)

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.w, self.h), 8, 8)
        return path

    def column_y(self, col_name):
        for i, (cname, _) in enumerate(self.columns):
            if cname == col_name:
                return self.header_h + i * self.row_h + self.row_h / 2
        return self.header_h + self.row_h / 2

    def scene_pos_of_column(self, col_name):
        return QPointF(self.x() + self.w / 2, self.y() + self.column_y(col_name))

    def top_center(self):
        return QPointF(self.x() + self.w / 2, self.y())

    def bottom_center(self):
        return QPointF(self.x() + self.w / 2, self.y() + self.h)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_active:
            top_color = self.colors[0].lighter(150)
            bot_color = self.colors[1].lighter(130)
            border_pen = QPen(QColor(255, 230, 80), 2.5)
        elif self.is_dimmed:
            top_color = QColor(35, 38, 48)
            bot_color = QColor(25, 28, 35)
            border_pen = QPen(QColor(45, 48, 58), 1)
        elif self.is_authority:
            top_color = self.colors[0]
            bot_color = self.colors[1]
            border_pen = QPen(self.colors[0].lighter(120), 1.5)
        else:
            top_color = self.colors[0]
            bot_color = self.colors[1]
            border_pen = QPen(QColor(70, 75, 88), 1)

        gradient = QLinearGradient(0, 0, 0, self.header_h)
        gradient.setColorAt(0, top_color)
        gradient.setColorAt(1, bot_color)
        painter.setBrush(QBrush(gradient))
        painter.setPen(border_pen)
        painter.drawRoundedRect(QRectF(0, 0, self.w, self.h), 8, 8)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 32, 40) if not self.is_active else QColor(40, 42, 52)))
        painter.drawRoundedRect(QRectF(1, self.header_h, self.w - 2, self.h - self.header_h - 1), 0, 0)

        painter.setPen(border_pen)
        painter.drawLine(QPointF(0, self.header_h), QPointF(self.w, self.header_h))

        painter.setPen(QPen(QColor(255, 255, 255)))
        font_name = QFont("Menlo", 10)
        font_name.setBold(True)
        painter.setFont(font_name)
        painter.drawText(QRectF(4, 2, self.w - 8, self.header_h - 4),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.name)

        font_count = QFont("Menlo", 8)
        font_count.setBold(True)
        painter.setFont(font_count)
        if self.is_active:
            painter.setPen(QPen(QColor(255, 230, 80)))
        else:
            painter.setPen(QPen(QColor(180, 190, 200)))
        painter.drawText(QRectF(self.w - 50, 2, 46, self.header_h - 4),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(self.count))

        font_col = QFont("Menlo", 8)
        painter.setFont(font_col)
        for i, (cname, _) in enumerate(self.columns):
            cy = self.header_h + i * self.row_h + 2
            is_fk = any(fk == cname for fk, _ in self.fk_columns)
            if is_fk:
                painter.setPen(QPen(QColor(255, 200, 80)))
                font_fk = QFont("Menlo", 8)
                font_fk.setBold(True)
                painter.setFont(font_fk)
            else:
                painter.setPen(QPen(QColor(160, 170, 185)))
                painter.setFont(font_col)
            painter.drawText(QRectF(6, cy, self.w - 12, self.row_h),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, cname)

            if is_fk:
                fk_auth = next((auth for fk, auth in self.fk_columns if fk == cname), None)
                if fk_auth:
                    auth_color = AUTHORITY_COLORS.get(fk_auth, (QColor(100, 100, 100),))[0]
                    painter.setBrush(QBrush(auth_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(self.w - 6, cy + self.row_h / 2), 3, 3)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.UpdatePath()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """A FK connection line between an entity and an authority."""

    def __init__(self, entity_item, fk_col, auth_item):
        super().__init__()
        self.entity_item = entity_item
        self.fk_col = fk_col
        self.auth_item = auth_item
        self.auth_color = AUTHORITY_COLORS.get(auth_item.name, (QColor(80, 80, 80),))[0]
        self.is_highlighted = False
        self.is_dimmed = False
        self.is_hovered = False
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.label = None
        self.UpdatePath()

    def UpdatePath(self):
        ent = self.entity_item
        auth = self.auth_item

        if ent.y() > auth.y():
            start = QPointF(ent.x() + 5, ent.y() + ent.column_y(self.fk_col))
            end = QPointF(auth.x() + auth.w - 5, auth.y() + auth.h - 3)
        else:
            start = QPointF(ent.x() + ent.w / 2, ent.y())
            end = QPointF(auth.x() + auth.w / 2, auth.y() + auth.h)

        path = QPainterPath()
        path.moveTo(start)
        mid_y = (start.y() + end.y()) / 2
        ctrl1 = QPointF(start.x(), mid_y)
        ctrl2 = QPointF(end.x(), mid_y)
        path.cubicTo(ctrl1, ctrl2, end)
        self.setPath(path)

        if self.is_highlighted or self.is_hovered:
            self.setPen(QPen(self.auth_color.lighter(140), 2.5))
        elif self.is_dimmed:
            self.setPen(QPen(QColor(35, 38, 48, 50), 1))
        else:
            self.setPen(QPen(self.auth_color.darker(160), 1.2))

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.setZValue(20)
        if self.label is None:
            self.label = QGraphicsTextItem(self)
            self.label.setDefaultTextColor(QColor(255, 230, 80))
            font = QFont("Menlo", 8)
            font.setBold(True)
            self.label.setFont(font)
            self.label.setZValue(21)
        mid = self.path().pointAtPercent(0.5)
        text = f"{self.entity_item.name}.{self.fk_col} -> {self.auth_item.name}"
        self.label.setPlainText(text)
        self.label.setPos(mid.x() - self.label.boundingRect().width() / 2,
                          mid.y() - self.label.boundingRect().height() / 2)
        self.label.setVisible(True)
        self.UpdatePath()

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.setZValue(1)
        if self.label:
            self.label.setVisible(False)
        self.UpdatePath()


class ErdScene(QGraphicsScene):
    """Scene holding all ERD items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = {
            "tables": {},
            "edges": [],
            "selected_table": None,
            "db_config": {
                "host": "localhost", "user": "root",
                "password": "", "database": "laws",
            },
        }
        self._p = self.PHelper
        self.LoadData()

    def PHelper(self, key, default=None):
        return self.state.get(key, default)

    def read_state(self):
        return dict(self.state)

    def set_config(self, config):
        if isinstance(config, dict):
            self.state.update(config)

    def LoadData(self):
        self.clear()
        config = self.state["db_config"]
        conn = mysql.connector.connect(**config)
        cur = conn.cursor()

        cur.execute("SHOW TABLES")
        all_tables = [r[0] for r in cur.fetchall()]
        counts = {}
        for t in all_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                counts[t] = cur.fetchone()[0]
            except Exception:
                counts[t] = 0

        cur.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA='laws' AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY REFERENCED_TABLE_NAME, TABLE_NAME
        """)
        fk_rows = cur.fetchall()

        edges_raw = []
        entity_tables = set()
        fk_map = {}
        for entity_table, fk_col, auth_table in fk_rows:
            if auth_table in AUTHORITY_TABLES:
                edges_raw.append((entity_table, fk_col, auth_table))
                entity_tables.add(entity_table)
                fk_map.setdefault(entity_table, []).append((fk_col, auth_table))

        entity_list = sorted(entity_tables)

        table_columns = {}
        for tname in AUTHORITY_TABLES + entity_list:
            cur.execute(f"DESCRIBE `{tname}`")
            table_columns[tname] = [(c[0], c[1]) for c in cur.fetchall()]

        conn.close()

        box_w = 170
        auth_gap = 30
        auth_total_w = len(AUTHORITY_TABLES) * box_w + (len(AUTHORITY_TABLES) - 1) * auth_gap
        canvas_w = max(auth_total_w + 80, 1600)
        auth_start_x = (canvas_w - auth_total_w) / 2
        auth_y = 60

        tables = {}
        for i, tname in enumerate(AUTHORITY_TABLES):
            x = auth_start_x + i * (box_w + auth_gap)
            cols = table_columns.get(tname, [])
            fks = [(fk, auth) for fk, auth in fk_map.get(tname, [])]
            colors = AUTHORITY_COLORS.get(tname, (QColor(80, 80, 80), QColor(60, 60, 60)))
            item = TableItem(tname, counts.get(tname, 0), cols, fks, True, colors)
            item.setPos(x, auth_y)
            tables[tname] = item
            self.addItem(item)

        ent_cols = 6
        ent_gap_x = 30
        ent_gap_y = 50
        max_auth_h = max(t.h for t in tables.values())
        ent_start_y = auth_y + max_auth_h + 100
        ent_total_w = ent_cols * box_w + (ent_cols - 1) * ent_gap_x
        ent_start_x = (canvas_w - ent_total_w) / 2

        for i, tname in enumerate(entity_list):
            col = i % ent_cols
            row = i // ent_cols
            x = ent_start_x + col * (box_w + ent_gap_x)
            y = ent_start_y + row * (130 + ent_gap_y)
            cols = table_columns.get(tname, [])
            fks = [(fk, auth) for fk, auth in fk_map.get(tname, [])]
            item = TableItem(tname, counts.get(tname, 0), cols, fks, False, ENTITY_COLOR)
            item.setPos(x, y)
            tables[tname] = item
            self.addItem(item)

        self.state["tables"] = tables

        edge_items = []
        for entity_table, fk_col, auth_table in edges_raw:
            ent_item = tables.get(entity_table)
            auth_item = tables.get(auth_table)
            if not ent_item or not auth_item:
                continue
            edge = EdgeItem(ent_item, fk_col, auth_item)
            ent_item.edges.append(edge)
            auth_item.edges.append(edge)
            self.addItem(edge)
            edge_items.append(edge)

        self.state["edges"] = edge_items

        all_w = max(t.x() + t.w for t in tables.values()) + 60
        all_h = max(t.y() + t.h for t in tables.values()) + 60
        self.setSceneRect(0, 0, all_w, all_h)

    def UpdateHighlight(self, selected_name):
        self.state["selected_table"] = selected_name
        tables = self.state["tables"]

        for tname, item in tables.items():
            item.is_active = (tname == selected_name)
            item.is_connected = False
            item.is_dimmed = bool(selected_name) and not item.is_active
            item.update()

        if not selected_name:
            for edge in self.state["edges"]:
                edge.is_highlighted = False
                edge.is_dimmed = False
                edge.UpdatePath()
            return

        for edge in self.state["edges"]:
            ent_name = edge.entity_item.name
            auth_name = edge.auth_item.name
            if ent_name == selected_name or auth_name == selected_name:
                edge.is_highlighted = True
                edge.is_dimmed = False
                edge.entity_item.is_dimmed = False
                edge.auth_item.is_dimmed = False
                if ent_name == selected_name:
                    edge.auth_item.is_connected = True
                else:
                    edge.entity_item.is_connected = True
            else:
                edge.is_highlighted = False
                edge.is_dimmed = True
            edge.UpdatePath()

        for item in tables.values():
            item.update()

    def GetConnectedRect(self, table_name):
        """Get bounding rect of a table + all its connected tables."""
        tables = self.state["tables"]
        if table_name not in tables:
            return None

        items_to_show = [tables[table_name]]
        for edge in self.state["edges"]:
            ent_name = edge.entity_item.name
            auth_name = edge.auth_item.name
            if ent_name == table_name:
                items_to_show.append(edge.auth_item)
            elif auth_name == table_name:
                items_to_show.append(edge.entity_item)

        min_x = min(i.x() for i in items_to_show) - 40
        min_y = min(i.y() for i in items_to_show) - 40
        max_x = max(i.x() + i.w for i in items_to_show) + 40
        max_y = max(i.y() + i.h for i in items_to_show) + 40
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def SearchTable(self, query):
        """Find tables matching query. Returns list of (name, item)."""
        query = query.strip().lower()
        if not query:
            return []
        results = []
        for tname, item in self.state["tables"].items():
            if query in tname.lower():
                results.append((tname, item))
        return results


class ErdView(QGraphicsView):
    """GPU-accelerated view — OpenGL viewport, zoom, pan."""

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.state = {"dragging": False}
        self._p = self.PHelper
        self.SetUpViewport()
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setBackgroundBrush(QBrush(QColor(20, 22, 28)))

    def PHelper(self, key, default=None):
        return self.state.get(key, default)

    def read_state(self):
        return dict(self.state)

    def set_config(self, config):
        if isinstance(config, dict):
            self.state.update(config)

    def SetUpViewport(self):
        gl = QOpenGLWidget()
        fmt = gl.format()
        fmt.setSamples(4)
        gl.setFormat(fmt)
        self.setViewport(gl)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom = 1.0 + (event.angleDelta().y() / 1200.0)
            self.scale(zoom, zoom)
        else:
            super().wheelEvent(event)

    def ZoomToRect(self, rect, margin=20):
        """Smoothly fit the view to a scene rect."""
        if rect is None or rect.isNull():
            return
        rect = rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.update()
        parent = self.parent()
        if parent and hasattr(parent, 'UpdateZoomLabel'):
            parent.UpdateZoomLabel()

    def ZoomToTable(self, table_name, scene):
        """Zoom to a table + all its FK-connected tables."""
        rect = scene.GetConnectedRect(table_name)
        self.ZoomToRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.state["dragging"] = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake = event.clone()
            fake.setButton(Qt.MouseButton.LeftButton)
            super().mousePressEvent(fake)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.state["dragging"] = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor(20, 22, 28))
        painter.setPen(QPen(QColor(30, 32, 40), 1))
        left = int(rect.left()) - (int(rect.left()) % 40)
        top = int(rect.top()) - (int(rect.top()) % 40)
        for x in range(left, int(rect.right()), 40):
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for y in range(top, int(rect.bottom()), 40):
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))


class AuthorityErdGui(QMainWindow):
    """Main window wrapping the GPU-accelerated ERD view."""

    def __init__(self):
        super().__init__()
        self.state = {"scene": None, "view": None}
        self._p = self.PHelper
        self.setWindowTitle("Authority ERD — laws database (GPU-accelerated)")
        self.setMinimumSize(1400, 850)
        self.setStyleSheet("QMainWindow { background: #14161c; }")
        self.InitUi()

    def PHelper(self, key, default=None):
        return self.state.get(key, default)

    def read_state(self):
        return dict(self.state)

    def set_config(self, config):
        if isinstance(config, dict):
            self.state.update(config)

    def InitUi(self):
        central = QWidget()
        central.setStyleSheet("background: #14161c;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel(
            "  Authority ERD (GPU) — Drag tables  |  Click to highlight + zoom to FKs  |  "
            "Ctrl+Wheel zoom  |  Middle-drag pan  |  Search to find + zoom"
        )
        header.setStyleSheet(
            "color: #8a8a9a; padding: 6px; font-size: 11px; "
            "background: #1a1c24; border-bottom: 1px solid #2a2c34;"
        )
        layout.addWidget(header)

        search_bar = QHBoxLayout()
        search_bar.setContentsMargins(8, 4, 8, 4)
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #8a8a9a; font-size: 11px;")
        search_bar.addWidget(search_label)

        self.search_field = QLineEdit()
        self.search_field.setStyleSheet(
            "QLineEdit { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; "
            "padding: 4px 8px; border-radius: 4px; font-size: 11px; }"
            "QLineEdit:focus { border: 1px solid #5060a0; }"
        )
        self.search_field.setPlaceholderText("Type table name (e.g. error, status, domain) and press Enter...")
        self.search_field.returnPressed.connect(self.OnSearch)
        search_bar.addWidget(self.search_field)

        self.search_result_label = QLabel("")
        self.search_result_label.setStyleSheet("color: #6a8a6a; font-size: 10px; padding-left: 8px;")
        search_bar.addWidget(self.search_result_label)

        layout.addLayout(search_bar)

        scene = ErdScene()
        self.state["scene"] = scene

        view = ErdView(scene)
        self.state["view"] = view
        layout.addWidget(view)

        scene.selectionChanged.connect(self.OnSelectionChanged)

        toolbar = QToolBar("ERD Tools", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())
        toolbar.setStyleSheet(
            "QToolBar { background: #1a1c24; border: none; border-bottom: 1px solid #2a2c34; "
            "padding: 2px; spacing: 4px; }"
            "QToolBar QToolButton { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; "
            "padding: 4px 12px; border-radius: 4px; font-size: 11px; }"
            "QToolBar QToolButton:hover { background: #3a3c48; border: 1px solid #4a4c58; }"
            "QToolBar QToolButton:pressed { background: #1a1c24; }"
            "QToolBar QToolButton:checked { background: #3a3c48; border: 1px solid #5060a0; }"
            "QToolBar QLabel { color: #6a6a7a; font-size: 10px; padding: 0 4px; }"
            "QToolBar QSeparator { width: 1px; background: #2a2c34; margin: 2px 4px; }"
        )
        self.addToolBar(toolbar)

        act_reload = QAction("Reload DB", self)
        act_reload.setToolTip("Reload data from MySQL")
        act_reload.triggered.connect(self.OnReload)
        toolbar.addAction(act_reload)

        act_clear = QAction("Clear", self)
        act_clear.setToolTip("Clear selection")
        act_clear.triggered.connect(self.OnClear)
        toolbar.addAction(act_clear)

        act_reset = QAction("Reset Layout", self)
        act_reset.setToolTip("Reset all tables to original positions")
        act_reset.triggered.connect(self.OnReset)
        toolbar.addAction(act_reset)

        toolbar.addSeparator()

        act_zoom_in = QAction("Zoom +", self)
        act_zoom_in.setToolTip("Zoom in")
        act_zoom_in.triggered.connect(self.OnZoomIn)
        toolbar.addAction(act_zoom_in)

        act_zoom_out = QAction("Zoom -", self)
        act_zoom_out.setToolTip("Zoom out")
        act_zoom_out.triggered.connect(self.OnZoomOut)
        toolbar.addAction(act_zoom_out)

        act_fit = QAction("Fit All", self)
        act_fit.setToolTip("Fit entire diagram in view")
        act_fit.triggered.connect(self.OnFit)
        toolbar.addAction(act_fit)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  Search:"))
        self.toolbar_search = QLineEdit()
        self.toolbar_search.setStyleSheet(
            "QLineEdit { background: #2a2c36; color: #c0c0d0; border: 1px solid #3a3c48; "
            "padding: 3px 8px; border-radius: 4px; font-size: 11px; min-width: 200px; }"
            "QLineEdit:focus { border: 1px solid #5060a0; }"
        )
        self.toolbar_search.setPlaceholderText("table name...")
        self.toolbar_search.returnPressed.connect(self.OnToolbarSearch)
        toolbar.addWidget(self.toolbar_search)

        self.toolbar_result = QLabel("")
        self.toolbar_result.setStyleSheet("color: #6a8a6a; font-size: 10px;")
        toolbar.addWidget(self.toolbar_result)

        toolbar.addSeparator()

        act_export = QAction("Export PNG", self)
        act_export.setToolTip("Export current view as PNG")
        act_export.triggered.connect(self.OnExport)
        toolbar.addAction(act_export)

        toolbar.addSeparator()

        act_filter = QAction("Hide Unconnected", self)
        act_filter.setToolTip("When a table is selected, hide tables not connected to it")
        act_filter.setCheckable(True)
        act_filter.triggered.connect(self.OnToggleFilter)
        toolbar.addAction(act_filter)
        self.state["filter_action"] = act_filter

        toolbar.addSeparator()

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setStyleSheet("color: #6a6a7a; font-size: 10px;")
        toolbar.addWidget(self.zoom_label)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(8, 2, 8, 2)

        legend_parts = []
        for tname in AUTHORITY_TABLES:
            c = AUTHORITY_COLORS[tname][0]
            hex_color = f"#{c.red():02x}{c.green():02x}{c.blue():02x}"
            legend_parts.append(f"<span style='color:{hex_color}; font-weight:bold;'>{tname}</span>")
        legend = QLabel("  Authorities:  " + "  ".join(legend_parts))
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet("color: #8a8a9a; font-size: 10px;")
        bottom.addWidget(legend)

        bottom.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6a6a7a; font-size: 10px; padding-right: 8px;")
        bottom.addWidget(self.status_label)
        layout.addLayout(bottom)

    def OnSelectionChanged(self):
        scene = self.state["scene"]
        selected = scene.selectedItems()
        if selected:
            item = selected[0]
            if isinstance(item, TableItem):
                scene.UpdateHighlight(item.name)
                self.ApplyFilter(item.name)
                self.state["view"].ZoomToTable(item.name, scene)
        else:
            scene.UpdateHighlight(None)
            self.ApplyFilter(None)

    def ApplyFilter(self, selected_name):
        scene = self.state["scene"]
        filter_on = self.state.get("filter_action") and self.state["filter_action"].isChecked()
        tables = scene.state["tables"]
        if not filter_on or not selected_name:
            for item in tables.values():
                item.setVisible(True)
            for edge in scene.state["edges"]:
                edge.setVisible(True)
            return
        connected = {selected_name}
        for edge in scene.state["edges"]:
            ent_name = edge.entity_item.name
            auth_name = edge.auth_item.name
            if ent_name == selected_name:
                connected.add(auth_name)
            elif auth_name == selected_name:
                connected.add(ent_name)
        for tname, item in tables.items():
            item.setVisible(tname in connected)
        for edge in scene.state["edges"]:
            ent_name = edge.entity_item.name
            auth_name = edge.auth_item.name
            edge.setVisible(ent_name in connected and auth_name in connected)

    def OnToggleFilter(self):
        scene = self.state["scene"]
        selected = scene.selectedItems()
        if selected:
            item = selected[0]
            if isinstance(item, TableItem):
                self.ApplyFilter(item.name)
        else:
            self.ApplyFilter(None)

    def OnReload(self):
        self.state["scene"].LoadData()
        self.status_label.setText("Reloaded from DB")

    def OnSearch(self):
        query = self.search_field.text().strip()
        if not query:
            self.search_result_label.setText("")
            return
        scene = self.state["scene"]
        results = scene.SearchTable(query)
        if not results:
            self.search_result_label.setText("No match")
            self.search_result_label.setStyleSheet("color: #aa6a6a; font-size: 10px; padding-left: 8px;")
            return
        if len(results) == 1:
            tname, item = results[0]
            scene.clearSelection()
            item.setSelected(True)
            scene.UpdateHighlight(tname)
            self.state["view"].ZoomToTable(tname, scene)
            self.search_result_label.setText(f"Found: {tname}")
            self.search_result_label.setStyleSheet("color: #6a8a6a; font-size: 10px; padding-left: 8px;")
        else:
            names = [r[0] for r in results]
            self.search_result_label.setText(f"{len(results)} matches: {', '.join(names[:5])}")
            self.search_result_label.setStyleSheet("color: #6a6aaa; font-size: 10px; padding-left: 8px;")
            scene.clearSelection()
            first = results[0]
            first[1].setSelected(True)
            scene.UpdateHighlight(first[0])
            self.state["view"].ZoomToTable(first[0], scene)

    def OnToolbarSearch(self):
        query = self.toolbar_search.text().strip()
        if not query:
            self.toolbar_result.setText("")
            return
        scene = self.state["scene"]
        results = scene.SearchTable(query)
        if not results:
            self.toolbar_result.setText("No match")
            self.toolbar_result.setStyleSheet("color: #aa6a6a; font-size: 10px;")
            self.status_label.setText(f"Search '{query}': no match")
            return
        if len(results) == 1:
            tname, item = results[0]
            scene.clearSelection()
            item.setSelected(True)
            scene.UpdateHighlight(tname)
            self.state["view"].ZoomToTable(tname, scene)
            self.toolbar_result.setText(f"Found: {tname}")
            self.toolbar_result.setStyleSheet("color: #6a8a6a; font-size: 10px;")
            self.status_label.setText(f"Search '{query}': found {tname}")
        else:
            names = [r[0] for r in results]
            self.toolbar_result.setText(f"{len(results)} matches")
            self.toolbar_result.setStyleSheet("color: #6a6aaa; font-size: 10px;")
            scene.clearSelection()
            first = results[0]
            first[1].setSelected(True)
            scene.UpdateHighlight(first[0])
            self.state["view"].ZoomToTable(first[0], scene)
            self.status_label.setText(f"Search '{query}': {len(results)} matches: {', '.join(names[:5])}")

    def OnClear(self):
        self.state["scene"].clearSelection()
        self.state["scene"].UpdateHighlight(None)

    def OnReset(self):
        self.state["scene"].LoadData()

    def OnZoomIn(self):
        self.state["view"].scale(1.2, 1.2)
        self.UpdateZoomLabel()

    def OnZoomOut(self):
        self.state["view"].scale(1 / 1.2, 1 / 1.2)
        self.UpdateZoomLabel()

    def OnFit(self):
        self.state["view"].fitInView(self.state["scene"].sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_label.setText("Fit all")
        self.UpdateZoomLabel()

    def UpdateZoomLabel(self):
        transform = self.state["view"].transform()
        zoom = int(transform.m11() * 100)
        self.zoom_label.setText(f"Zoom: {zoom}%")

    def OnExport(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "erd_export.png", "PNG Images (*.png)"
        )
        if not path:
            return
        scene = self.state["scene"]
        rect = scene.sceneRect()
        from PyQt6.QtGui import QImage
        img = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
        img.fill(QColor(20, 22, 28))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scene.render(painter, QRectF(img.rect()), rect)
        painter.end()
        img.save(path, "PNG")
        self.status_label.setText(f"Exported to {path}")


def Main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Menlo", 10))
    window = AuthorityErdGui()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(Main())
