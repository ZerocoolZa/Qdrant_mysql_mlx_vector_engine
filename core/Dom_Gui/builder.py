# [@GHOST]{[@file<GUIBuilder.py>][@domain<Dom_Gui>][@role<builder>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<widget_builder>][@return<dict>][@orch<GUIParser>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Walks GUITreeNode tree, instantiates real PyQt6 widgets, applies layouts and properties}

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFrame, QLabel, QPushButton, QTextEdit, QPlainTextEdit, QLineEdit,
    QTabWidget, QComboBox, QStatusBar, QCheckBox, QTableWidget, QHeaderView,
    QGraphicsView, QGraphicsScene, QScrollArea, QMenu, QMenuBar,
    QSystemTrayIcon, QToolBar, QProgressBar, QSlider, QSpinBox,
    QFileDialog, QInputDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QPixmap, QColor, QIcon, QAction

from .node import GUITreeNode
from .router import EventRouter


class GUIBuilder:
    """Build PyQt6 widgets from a GUITreeNode tree parsed by GUIParser.

    Widget type map translates BCL type strings to PyQt6 classes.
    Properties are applied by name (text, size, style, stretch, etc).
    Layouts are auto-created based on [@layout] property.
    """

    WIDGET_MAP = {
        "QMainWindow": QMainWindow,
        "QWidget": QWidget,
        "QFrame": QFrame,
        "QLabel": QLabel,
        "QPushButton": QPushButton,
        "QTextEdit": QTextEdit,
        "QPlainTextEdit": QPlainTextEdit,
        "QLineEdit": QLineEdit,
        "QTabWidget": QTabWidget,
        "QComboBox": QComboBox,
        "QStatusBar": QStatusBar,
        "QCheckBox": QCheckBox,
        "QTableWidget": QTableWidget,
        "QGraphicsView": QGraphicsView,
        "QGraphicsScene": QGraphicsScene,
        "QScrollArea": QScrollArea,
        "QSplitter": QSplitter,
        "QProgressBar": QProgressBar,
        "QSlider": QSlider,
        "QSpinBox": QSpinBox,
    }

    LAYOUT_MAP = {
        "VBox": QVBoxLayout,
        "HBox": QHBoxLayout,
    }

    def __init__(self, host=None, theme=None):
        self.host = host
        self.theme = theme
        self.widgets = {}
        self.layouts = {}
        self.router = EventRouter()
        self.warnings = []

    def build(self, tree, signals=None):
        """Build all widgets from the tree. Returns dict of {name: widget}.

        Args:
            tree: list of GUITreeNode (from GUIParser)
            signals: list of signal dicts (from GUIParser.get_signals())

        Returns:
            dict of {name: QWidget}
        """
        self.widgets = {}
        self.layouts = {}
        self.warnings = []

        sorted_nodes = self._topo_sort(tree)

        for node in sorted_nodes:
            self._build_node(node)

        if signals:
            self.router.route(signals, self.host, self.widgets)
            self.warnings.extend(self.router.get_warnings())

        return self.widgets

    def _topo_sort(self, nodes):
        """Topological sort: parents before children (BFS by depth)."""
        name_to_node = {}
        children_of = {}
        roots = []
        for n in nodes:
            if n.name:
                name_to_node[n.name] = n
            children_of.setdefault(n.name, [])
        for n in nodes:
            if n.parent and n.parent in name_to_node:
                children_of.setdefault(n.parent, []).append(n)
            else:
                roots.append(n)
        result = []
        queue = list(roots)
        while queue:
            n = queue.pop(0)
            result.append(n)
            for child in children_of.get(n.name, []):
                queue.append(child)
        return result

    def _build_node(self, node):
        """Build a single widget node."""
        if node.node_type == "QMenuBar":
            self._build_menu_bar(node)
            return
        if node.node_type == "QSystemTrayIcon":
            self._build_tray(node)
            return
        if node.node_type == "QMenu":
            self._build_menu(node)
            return

        cls = self.WIDGET_MAP.get(node.node_type)
        if cls is None:
            self.warnings.append(f"Unknown widget type: {node.node_type} (line {node.line_num})")
            return

        try:
            widget = cls()
        except Exception as e:
            self.warnings.append(f"Failed to create {node.node_type}: {e}")
            return

        if node.name:
            self.widgets[node.name] = widget

        self._apply_properties(widget, node)

        if node.parent and node.parent in self.widgets:
            parent_widget = self.widgets[node.parent]
            self._add_to_parent(parent_widget, widget, node)

        if node.node_type == "QMainWindow" and self.host:
            self.host.setCentralWidget(widget)

    def _apply_properties(self, widget, node):
        """Apply properties from BCL to the widget."""
        props = node.properties

        if "text" in props:
            widget.setText(props["text"])
        if "title" in props and hasattr(widget, "setWindowTitle"):
            widget.setWindowTitle(props["title"])
        if "placeholder" in props and hasattr(widget, "setPlaceholderText"):
            widget.setPlaceholderText(props["placeholder"])
        if "readonly" in props and hasattr(widget, "setReadOnly"):
            widget.setReadOnly(props["readonly"].lower() == "true")
        if "tooltip" in props and hasattr(widget, "setToolTip"):
            widget.setToolTip(props["tooltip"])

        if "size" in props:
            parts = props["size"].split("x")
            if len(parts) == 2:
                try:
                    widget.setFixedSize(QSize(int(parts[0]), int(parts[1])))
                except ValueError:
                    pass

        if "width" in props:
            try:
                widget.setFixedWidth(int(props["width"]))
            except ValueError:
                pass

        if "height" in props:
            try:
                widget.setFixedHeight(int(props["height"]))
            except ValueError:
                pass

        if "style" in props:
            style_name = props["style"]
            stylesheet = self._resolve_style(style_name)
            if stylesheet:
                widget.setStyleSheet(stylesheet)

        if "stylesheet" in props:
            widget.setStyleSheet(props["stylesheet"])

        if "stretch" in props:
            widget._dgs_stretch = int(props["stretch"])

        if "tabname" in props and hasattr(widget, "_dgs_tabname"):
            widget._dgs_tabname = props["tabname"]
        if node.tab_name:
            widget._dgs_tabname = node.tab_name

    def _resolve_style(self, style_name):
        """Resolve a style name to a stylesheet string."""
        try:
            from Config import Style
            return getattr(Style, style_name, None)
        except Exception:
            return None

    def _add_to_parent(self, parent, child, node):
        """Add child widget to parent's layout, creating layout if needed."""
        layout_type = node.properties.get("layout", None)

        if isinstance(parent, QTabWidget):
            tab_name = getattr(child, "_dgs_tabname", node.tab_name or "Tab")
            parent.addTab(child, tab_name)
            return

        if isinstance(parent, QSplitter):
            parent.addWidget(child)
            return

        if parent is self.host:
            central = QWidget()
            self.host.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.addWidget(child)
            return

        layout = self.layouts.get(id(parent))
        if layout is None:
            if layout_type in self.LAYOUT_MAP:
                layout_cls = self.LAYOUT_MAP[layout_type]
                layout = layout_cls(parent)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(1)
                self.layouts[id(parent)] = layout
            else:
                layout = QVBoxLayout(parent)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(1)
                self.layouts[id(parent)] = layout

        stretch = getattr(child, "_dgs_stretch", 0)
        layout.addWidget(child, stretch=stretch)

    def _build_menu_bar(self, node):
        """Build menu bar entries on the host's menuBar()."""
        if self.host is None:
            return
        menubar = self.host.menuBar()
        menu_name = node.name or "Menu"
        menu = menubar.addMenu(menu_name)

        for child in node.children:
            if child.node_type == "QAction" or "text" in child.properties:
                text = child.properties.get("text", child.name or "Action")
                handler_name = child.properties.get("handler")
                action = QAction(text, self.host)
                if handler_name and hasattr(self.host, handler_name):
                    action.triggered.connect(getattr(self.host, handler_name))
                menu.addAction(action)

        self.widgets[node.name or menu_name] = menu

    def _build_menu(self, node):
        """Build a QMenu (context or submenu)."""
        menu = QMenu(self.host)
        menu.setTitle(node.properties.get("title", node.name or "Menu"))
        for child in node.children:
            text = child.properties.get("text", child.name or "Action")
            handler_name = child.properties.get("handler")
            action = QAction(text, self.host)
            if handler_name and hasattr(self.host, handler_name):
                action.triggered.connect(getattr(self.host, handler_name))
            menu.addAction(action)
        if node.name:
            self.widgets[node.name] = menu

    def _build_tray(self, node):
        """Build a QSystemTrayIcon."""
        tray = QSystemTrayIcon(self.host)
        tray.setToolTip(node.properties.get("tooltip", "App"))

        icon_color = node.properties.get("icon", "#58a6ff")
        pix = QPixmap(32, 32)
        pix.fill(QColor(icon_color))
        tray.setIcon(QIcon(pix))

        if node.name:
            self.widgets[node.name] = tray
        tray.show()

    def get_widget(self, name):
        """Get a widget by name."""
        return self.widgets.get(name)

    def get_warnings(self):
        """Return build warnings."""
        return self.warnings

    def refresh(self, tree, signals=None):
        """Rebuild from a new tree (live edit support)."""
        return self.build(tree, signals)
