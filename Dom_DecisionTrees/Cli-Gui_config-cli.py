#!/usr/bin/env python3
#[@GHOST]{[@file<Cli-Gui_config-cli.py>][@state<active>][@date<2026-07-02>][@ver<1.0.0>][@auth<cascade>]}
#[@VBSTYLE]{[@auth<cascade>][@role<cli_config_editor>][@return<Tuple3>][@orch<Dom_DecisionTrees>][@no<decorators|print|hardcoded>]}
#[@SUMMARY]{CLI tool for browsing and editing WCL_CONFIG in Config.py. Tree navigation, property editing, validation, bidirectional read/write.}
#[@CLASS]{ConfigCli}
#[@METHOD]{Run,Load,Save,Tree,Ls,Cd,Show,Set,Add,Rm,Signals,Validate,Cluster,ClusterAdd,ClusterList,Help}

import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.Dom_Gui.parser import GUIParser
from core.Dom_Gui.node import GUITreeNode


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Config.py")

WCL_TEMPLATE = '# [@WIDGET]{{[@type<{typ}>][@name<{nam}>]{parent_str}{layout_str}{tab_str}{prop_str}}}'
SIGNAL_TEMPLATE = '# [@SIGNAL]{{[@widget<{wid}>][@signal<{sig}>][@handler<{hnd}>]}}'
GUI_TEMPLATE = '# [@GUI]{{[@size<{sz}>][@title<{ti}>]}}'

VALID_WIDGET_TYPES = [
    "QWidget", "QPushButton", "QLabel", "QLineEdit", "QPlainTextEdit",
    "QComboBox", "QSpinBox", "QCheckBox", "QSplitter", "QTabWidget",
    "QGroupBox", "QFrame", "QScrollArea", "QTextEdit", "QSlider",
    "QProgressBar", "QMenuBar", "QMenu", "QToolBar", "QStatusBar",
    "QListWidget", "QTreeWidget", "QTableWidget", "QDial", "QDateEdit",
    "QTimeEdit", "QDateTimeEdit", "QSpinBox", "QDoubleSpinBox",
    "QSystemTrayIcon", "QDialog", "QDialogButtonBox", "QRadioButton",
]

LAYOUT_TYPES = ["VBox", "HBox", "Grid", "Form"]


CLUSTERS = {
    "canvas": {
        "desc": "Graphics view for drawing trees, graphs, diagrams",
        "widgets": [
            ("QGraphicsView", "canvas", "Custom graphics view for tree/graph rendering"),
            ("QGraphicsScene", "scene", "Holds graphics items — usually internal"),
        ],
        "actions": [
            ("zoom_in", "Zoom into canvas", "button or shortcut Ctrl++"),
            ("zoom_out", "Zoom out of canvas", "button or shortcut Ctrl+-"),
            ("zoom_fit", "Fit all content in view", "button or shortcut Ctrl+0"),
            ("zoom_reset", "Reset zoom to 100%", "button"),
            ("pan", "Pan canvas by dragging", "mouse middle button or space+drag"),
            ("select", "Select nodes/items", "mouse click"),
            ("multi_select", "Select multiple items", "Ctrl+click or rubber band"),
            ("rubber_band", "Rubber band selection", "mouse drag on empty area"),
            ("context_menu", "Right-click context menu", "customContextMenuRequested"),
            ("grid_toggle", "Toggle grid display", "checkbox or shortcut G"),
            ("snap_to_grid", "Snap items to grid", "checkbox"),
            ("export_image", "Export canvas as PNG/SVG", "button or menu action"),
            ("print_canvas", "Print canvas contents", "menu action"),
            ("overlay", "Overlay layer for annotations", "toggle button"),
            ("minimap", "Minimap/overview panel", "dock widget"),
            ("node_edit", "Edit node label inline", "double-click on node"),
            ("node_create", "Create new node", "double-click on empty area"),
            ("node_delete", "Delete selected node", "Delete key or button"),
            ("edge_create", "Create edge between nodes", "drag from node to node"),
            ("edge_delete", "Delete edge", "select edge + Delete"),
            ("search_highlight", "Highlight nodes matching search", "text input + filter"),
        ],
        "properties": [
            ("render_hints", "Antialiasing, smooth pixmap transform", "QPainter.RenderHint"),
            ("drag_mode", "ScrollHandDrag, RubberBandDrag", "QGraphicsView.DragMode"),
            ("transformation_anchor", "AnchorUnderMouse, AnchorViewCenter", "ViewportAnchor"),
            ("background", "Background color or pattern", "QColor or QBrush"),
            ("scene_rect", "Scene bounding rectangle", "QRectF"),
        ],
    },
    "menu": {
        "desc": "Menu bar, menus, submenus, actions",
        "widgets": [
            ("QMenuBar", "menubar", "Top-level menu bar (auto-created by QMainWindow)"),
            ("QMenu", "menu_file", "File menu"),
            ("QMenu", "menu_edit", "Edit menu"),
            ("QMenu", "menu_view", "View menu"),
            ("QMenu", "menu_tools", "Tools menu"),
            ("QMenu", "menu_help", "Help menu"),
        ],
        "actions": [
            ("action_new", "New file/session", "Ctrl+N"),
            ("action_open", "Open file", "Ctrl+O"),
            ("action_save", "Save", "Ctrl+S"),
            ("action_save_as", "Save As...", "Ctrl+Shift+S"),
            ("action_export", "Export...", ""),
            ("action_import", "Import...", ""),
            ("action_quit", "Quit application", "Ctrl+Q"),
            ("action_undo", "Undo", "Ctrl+Z"),
            ("action_redo", "Redo", "Ctrl+Y"),
            ("action_cut", "Cut", "Ctrl+X"),
            ("action_copy", "Copy", "Ctrl+C"),
            ("action_paste", "Paste", "Ctrl+V"),
            ("action_find", "Find", "Ctrl+F"),
            ("action_preferences", "Preferences...", "Ctrl+,"),
            ("action_zoom_in", "Zoom In", "Ctrl++"),
            ("action_zoom_out", "Zoom Out", "Ctrl+-"),
            ("action_fit_view", "Fit View", "Ctrl+0"),
            ("action_toggle_grid", "Toggle Grid", "G"),
            ("action_about", "About", ""),
            ("action_about_qt", "About Qt", ""),
            ("separator", "--- Separator ---", "addSeparator()"),
        ],
        "properties": [
            ("shortcut", "Keyboard shortcut", "QKeySequence string"),
            ("checkable", "Action is checkable", "bool"),
            ("checked", "Action is checked", "bool"),
            ("enabled", "Action is enabled", "bool"),
            ("icon", "Icon for action", "path or QIcon"),
            ("status_tip", "Status bar tip", "string"),
            ("tooltip", "Tooltip text", "string"),
        ],
    },
    "toolbar": {
        "desc": "Toolbars, tool buttons, action groups",
        "widgets": [
            ("QToolBar", "toolbar_main", "Main toolbar"),
            ("QToolBar", "toolbar_canvas", "Canvas-specific toolbar"),
            ("QToolBar", "toolbar_edit", "Edit toolbar"),
        ],
        "actions": [
            ("tool_button", "Clickable tool button", "QToolButton or QAction"),
            ("toggle_button", "Checkable toggle button", "setCheckable(True)"),
            ("dropdown_button", "Button with dropdown menu", "setPopupMode(MenuButtonPopup)"),
            ("separator", "Toolbar separator", "addSeparator()"),
            ("spacer", "Flexible spacer", "addWidget(stretch)"),
            ("action_group", "Mutually exclusive action group", "QActionGroup"),
            ("icon_only", "Show icon only", "setToolButtonStyle(IconOnly)"),
            ("text_only", "Show text only", "setToolButtonStyle(TextOnly)"),
            ("icon_text", "Show icon + text", "setToolButtonStyle(IconTextBeside)"),
            ("movable", "Toolbar is movable/dockable", "setMovable(True)"),
            ("floatable", "Toolbar can float", "setFloatable(True)"),
        ],
        "properties": [
            ("area", "Dock area: top, bottom, left, right", "ToolBarArea"),
            ("icon_size", "Icon size in pixels", "QSize"),
            ("button_style", "IconOnly, TextOnly, IconText", "ToolButtonStyle"),
        ],
    },
    "tree": {
        "desc": "Tree widget for hierarchical data display",
        "widgets": [
            ("QTreeWidget", "tree_widget", "Tree view with columns"),
            ("QTreeView", "tree_view", "Tree view (model-based)"),
            ("QTreeWidgetItem", "tree_item", "Item in tree widget"),
        ],
        "actions": [
            ("expand_all", "Expand all nodes", "button or shortcut"),
            ("collapse_all", "Collapse all nodes", "button or shortcut"),
            ("expand", "Expand selected", "click or Right arrow"),
            ("collapse", "Collapse selected", "click or Left arrow"),
            ("sort", "Sort by column", "click header"),
            ("filter", "Filter tree items", "text input"),
            ("drag_drop", "Drag and drop reordering", "setDragEnabled"),
            ("inline_edit", "Edit item label inline", "double-click"),
            ("context_menu", "Right-click context menu", "customContextMenuRequested"),
            ("add_item", "Add child item", "button or context menu"),
            ("remove_item", "Remove item", "button or Delete key"),
            ("move_up", "Move item up", "button or Alt+Up"),
            ("move_down", "Move item down", "button or Alt+Down"),
        ],
        "properties": [
            ("columns", "Number of columns", "int"),
            ("header_labels", "Column header labels", "list of strings"),
            ("root_decoration", "Show expand/collapse arrows", "bool"),
            ("alternating_colors", "Alternate row colors", "bool"),
            ("selection_mode", "Single, Multi, Extended, Contiguous", "SelectionMode"),
        ],
    },
    "editor": {
        "desc": "Text editors, code editors, syntax highlighting",
        "widgets": [
            ("QPlainTextEdit", "code_editor", "Plain text editor"),
            ("QTextEdit", "rich_editor", "Rich text editor"),
            ("QSyntaxHighlighter", "highlighter", "Syntax highlighter (internal)"),
        ],
        "actions": [
            ("find", "Find text", "Ctrl+F"),
            ("find_replace", "Find and replace", "Ctrl+H"),
            ("find_next", "Find next", "F3"),
            ("find_prev", "Find previous", "Shift+F3"),
            ("goto_line", "Go to line number", "Ctrl+G"),
            ("autocomplete", "Autocomplete suggestions", "Ctrl+Space"),
            ("comment_toggle", "Toggle line comment", "Ctrl+/"),
            ("indent", "Indent selection", "Tab"),
            ("unindent", "Unindent selection", "Shift+Tab"),
            ("line_numbers", "Toggle line numbers", "checkbox"),
            ("word_wrap", "Toggle word wrap", "checkbox"),
            ("fold", "Fold/unfold code block", "click gutter"),
            ("bookmark", "Toggle bookmark", "Ctrl+B"),
            ("next_bookmark", "Next bookmark", "F2"),
            ("prev_bookmark", "Previous bookmark", "Shift+F2"),
        ],
        "properties": [
            ("font", "Editor font family and size", "QFont"),
            ("tab_width", "Tab width in spaces", "int"),
            ("readonly", "Read-only mode", "bool"),
            ("line_wrap", "Line wrap mode", "LineWrapMode"),
            ("placeholder", "Placeholder text", "string"),
        ],
    },
    "form": {
        "desc": "Form inputs: fields, combos, spinners, checkboxes",
        "widgets": [
            ("QLineEdit", "line_input", "Single-line text input"),
            ("QTextEdit", "text_area", "Multi-line text input"),
            ("QComboBox", "dropdown", "Dropdown selector"),
            ("QSpinBox", "spin_int", "Integer spinner"),
            ("QDoubleSpinBox", "spin_float", "Float spinner"),
            ("QCheckBox", "checkbox", "Checkbox"),
            ("QRadioButton", "radio", "Radio button"),
            ("QButtonGroup", "radio_group", "Group for exclusive radios"),
            ("QSlider", "slider", "Slider control"),
            ("QDial", "dial", "Rotary dial"),
            ("QDateEdit", "date_input", "Date picker"),
            ("QDateTimeEdit", "datetime_input", "Date+time picker"),
            ("QLabel", "form_label", "Label for a field"),
            ("QGroupBox", "form_group", "Group box for related fields"),
        ],
        "actions": [
            ("submit", "Submit form", "button or Enter"),
            ("reset", "Reset to defaults", "button"),
            ("validate", "Validate inputs", "on change or submit"),
            ("clear", "Clear all fields", "button"),
        ],
        "properties": [
            ("placeholder", "Placeholder text", "string"),
            ("readonly", "Read-only", "bool"),
            ("enabled", "Enabled", "bool"),
            ("required", "Field is required", "bool"),
            ("validator", "Validation regex or range", "QValidator"),
            ("min", "Minimum value", "int/float"),
            ("max", "Maximum value", "int/float"),
            ("step", "Step size", "int/float"),
            ("prefix", "Prefix text", "string"),
            ("suffix", "Suffix text", "string"),
        ],
    },
    "layout": {
        "desc": "Layout containers: vbox, hbox, grid, splitter, tabs",
        "widgets": [
            ("QWidget", "container", "Generic container widget"),
            ("QSplitter", "splitter", "Resizable splitter"),
            ("QTabWidget", "tabs", "Tabbed container"),
            ("QScrollArea", "scroll_area", "Scrollable area"),
            ("QStackedWidget", "stacked", "Stacked pages (one visible)"),
            ("QGroupBox", "group_box", "Bordered group with title"),
            ("QFrame", "frame", "Frame container"),
        ],
        "actions": [
            ("add_tab", "Add a new tab", "button or method"),
            ("remove_tab", "Remove current tab", "button or method"),
            ("next_tab", "Switch to next tab", "Ctrl+Tab"),
            ("prev_tab", "Switch to previous tab", "Ctrl+Shift+Tab"),
            ("split_horizontal", "Split horizontally", "button"),
            ("split_vertical", "Split vertically", "button"),
        ],
        "properties": [
            ("layout", "VBox, HBox, Grid, Form", "string"),
            ("margins", "Layout margins", "int tuple"),
            ("spacing", "Layout spacing", "int"),
            ("stretch", "Stretch factors", "list of int"),
            ("orientation", "Horizontal or Vertical", "Qt.Orientation"),
            ("tab_position", "North, South, East, West", "TabPosition"),
            ("collapsible", "Tabs are closable", "bool"),
            ("movable", "Tabs are movable", "bool"),
        ],
    },
    "dialog": {
        "desc": "Dialogs: modal, file, color, font, message, input",
        "widgets": [
            ("QDialog", "dialog", "Custom dialog window"),
            ("QDialogButtonBox", "dialog_buttons", "OK/Cancel button box"),
            ("QFileDialog", "file_dialog", "File open/save dialog"),
            ("QColorDialog", "color_dialog", "Color picker dialog"),
            ("QFontDialog", "font_dialog", "Font picker dialog"),
            ("QInputDialog", "input_dialog", "Simple input dialog"),
            ("QMessageBox", "message_box", "Message dialog"),
            ("QProgressDialog", "progress_dialog", "Progress dialog"),
        ],
        "actions": [
            ("open_file", "Open file dialog", "Ctrl+O"),
            ("save_file", "Save file dialog", "Ctrl+S"),
            ("choose_color", "Pick a color", "button"),
            ("choose_font", "Pick a font", "button"),
            ("confirm", "Confirmation dialog (Yes/No)", "method"),
            ("alert", "Alert dialog (OK)", "method"),
            ("prompt", "Input prompt dialog", "method"),
        ],
        "properties": [
            ("modal", "Modal (blocks) or modeless", "bool"),
            ("title", "Dialog title", "string"),
            ("filter", "File filter pattern", "string"),
            ("default_dir", "Default directory", "path"),
            ("buttons", "Button set (OK, Cancel, Yes, No...)", "QDialogButtonBox.StandardButton"),
        ],
    },
    "statusbar": {
        "desc": "Status bar, progress indicators, temporary messages",
        "widgets": [
            ("QStatusBar", "statusbar", "Status bar (auto-created by QMainWindow)"),
            ("QProgressBar", "progress", "Progress bar widget"),
            ("QLabel", "status_label", "Permanent status label"),
        ],
        "actions": [
            ("show_message", "Show temporary message", "showMessage(text, timeout)"),
            ("clear_message", "Clear temporary message", "clearMessage()"),
            ("add_perman", "Add permanent widget", "addPermanentWidget()"),
            ("add_temp", "Add temporary widget", "addWidget()"),
            ("progress_start", "Start progress indicator", "setRange(0,0)"),
            ("progress_update", "Update progress value", "setValue(n)"),
            ("progress_done", "Finish progress", "setValue(max)"),
        ],
        "properties": [
            ("size_grip", "Show size grip corner", "bool"),
            ("message_timeout", "Temp message timeout (ms)", "int"),
        ],
    },
    "dock": {
        "desc": "Dockable panels, side bars, floating windows",
        "widgets": [
            ("QDockWidget", "dock_panel", "Dockable panel widget"),
        ],
        "actions": [
            ("dock_left", "Dock to left side", "menu or drag"),
            ("dock_right", "Dock to right side", "menu or drag"),
            ("dock_top", "Dock to top", "menu or drag"),
            ("dock_bottom", "Dock to bottom", "menu or drag"),
            ("float", "Float as separate window", "menu or drag"),
            ("hide", "Hide dock", "menu toggle"),
            ("pin", "Pin/unpin dock", "toggle button"),
        ],
        "properties": [
            ("area", "Dock area", "DockWidgetArea"),
            ("features", "Dockable, Movable, Floatable, Closable", "DockWidgetFeature"),
            ("title", "Dock title", "string"),
            ("closable", "User can close dock", "bool"),
            ("floatable", "User can float dock", "bool"),
        ],
    },
    "table": {
        "desc": "Tables, data grids, spreadsheets",
        "widgets": [
            ("QTableWidget", "table", "Table with cells"),
            ("QTableView", "table_view", "Table view (model-based)"),
            ("QHeaderView", "header_view", "Header for table"),
        ],
        "actions": [
            ("add_row", "Add row", "button or context menu"),
            ("remove_row", "Remove row", "button or Delete"),
            ("add_column", "Add column", "button or context menu"),
            ("remove_column", "Remove column", "button"),
            ("sort_column", "Sort by column", "click header"),
            ("filter", "Filter rows", "text input"),
            ("export_csv", "Export to CSV", "button or menu"),
            ("import_csv", "Import from CSV", "button or menu"),
            ("cell_edit", "Edit cell", "double-click"),
            ("copy_cell", "Copy cell value", "Ctrl+C"),
            ("paste_cell", "Paste into cell", "Ctrl+V"),
        ],
        "properties": [
            ("rows", "Row count", "int"),
            ("columns", "Column count", "int"),
            ("header_labels", "Column headers", "list of strings"),
            ("alternating_colors", "Alternate row colors", "bool"),
            ("grid", "Show grid lines", "bool"),
            ("selection_behavior", "Select items, rows, or columns", "SelectionBehavior"),
            ("edit_triggers", "When editing is triggered", "EditTrigger"),
        ],
    },
    "list": {
        "desc": "List widgets, item views, icon lists",
        "widgets": [
            ("QListWidget", "list_widget", "List with items"),
            ("QListView", "list_view", "List view (model-based)"),
        ],
        "actions": [
            ("add_item", "Add item", "button or method"),
            ("remove_item", "Remove selected", "button or Delete"),
            ("clear_all", "Clear all items", "button"),
            ("sort", "Sort items", "button or method"),
            ("filter", "Filter items", "text input"),
            ("drag_reorder", "Drag to reorder", "setDragDropMode"),
            ("icon_mode", "Icon view mode", "setViewMode(IconMode)"),
            ("context_menu", "Right-click context menu", "customContextMenuRequested"),
        ],
        "properties": [
            ("selection_mode", "Single, Multi, Extended", "SelectionMode"),
            ("view_mode", "ListMode or IconMode", "ViewMode"),
            ("icon_size", "Icon size for icon mode", "QSize"),
            ("grid_size", "Grid size for icon mode", "QSize"),
            ("word_wrap", "Wrap item text", "bool"),
        ],
    },
    "tray": {
        "desc": "System tray icon, tray menu, notifications",
        "widgets": [
            ("QSystemTrayIcon", "tray", "System tray icon"),
            ("QMenu", "tray_menu", "Tray context menu"),
        ],
        "actions": [
            ("show_message", "Show tray notification", "showMessage()"),
            ("toggle_visible", "Show/hide main window", "tray click"),
            ("quit", "Quit from tray", "tray menu"),
        ],
        "properties": [
            ("icon", "Tray icon", "QIcon"),
            ("tooltip", "Tray tooltip", "string"),
            ("visible", "Tray icon visible", "bool"),
        ],
    },
    "splitter": {
        "desc": "Splitter panels, resizable sections",
        "widgets": [
            ("QSplitter", "splitter", "Resizable splitter container"),
        ],
        "actions": [
            ("collapse_left", "Collapse left panel", "button or shortcut"),
            ("collapse_right", "Collapse right panel", "button or shortcut"),
            ("toggle_orientation", "Toggle H/V orientation", "button"),
            ("save_state", "Save splitter sizes", "method"),
            ("restore_state", "Restore splitter sizes", "method"),
        ],
        "properties": [
            ("orientation", "Horizontal or Vertical", "Qt.Orientation"),
            ("collapsible", "Children are collapsible", "bool"),
            ("handle_width", "Splitter handle width", "int"),
            ("stretch_factors", "Stretch factors per section", "list of int"),
            ("sizes", "Initial sizes", "list of int"),
        ],
    },
}


class ConfigCli:
    """CLI for browsing and editing WCL GUI config in Config.py.

    Bidirectional: reads WCL_CONFIG from Config.py, allows tree navigation
    and editing, writes changes back. Validates and gives feedback.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config_path": param.get("config_path", CONFIG_PATH) if param else CONFIG_PATH,
            "parser": None,
            "nodes": [],
            "signals": [],
            "gui_meta": {},
            "cwd": None,
            "cwd_stack": [],
            "dirty": False,
            "running": True,
        }
        self.Load()

    def _p(self, msg, end="\n"):
        sys.stdout.write(str(msg) + end)
        sys.stdout.flush()

    def _err(self, msg):
        sys.stderr.write("ERROR: " + str(msg) + "\n")
        sys.stderr.flush()

    def Run(self, command, params=None):
        """Dispatch a single command. Returns Tuple3."""
        dispatch = {
            "tree": self.Tree,
            "ls": self.Ls,
            "cd": self.Cd,
            "show": self.Show,
            "info": self.Show,
            "props": self.Show,
            "set": self.Set,
            "add": self.Add,
            "add-widget": self.Add,
            "rm": self.Rm,
            "del": self.Rm,
            "signals": self.Signals,
            "add-signal": self.AddSignal,
            "rm-signal": self.RmSignal,
            "validate": self.Validate,
            "save": self.Save,
            "reload": self.Load,
            "help": self.Help,
            "quit": self.Quit,
            "exit": self.Quit,
            "pwd": self.Pwd,
            "find": self.Find,
            "meta": self.Meta,
            "cluster": self.Cluster,
            "clusters": self.ClusterList,
            "cluster-add": self.ClusterAdd,
        }
        handler = dispatch.get(command)
        if handler is None:
            self._err(f"Unknown command: {command}. Type 'help' for available commands.")
            return (0, None, ("UNKNOWN_CMD", f"Unknown: {command}", 0))
        if params is None:
            params = []
        return handler(params)

    def Load(self, params=None):
        """Reload WCL_CONFIG from Config.py."""
        path = self.state["config_path"]
        if not os.path.exists(path):
            self._err(f"Config file not found: {path}")
            return (0, None, ("NO_FILE", path, 0))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        wcl_text = self._extract_wcl(content)
        if wcl_text is None:
            self._err("Could not find WCL_CONFIG in Config.py")
            return (0, None, ("NO_WCL", "WCL_CONFIG not found", 0))
        parser = GUIParser()
        parser.parse_string(wcl_text)
        self.state["parser"] = parser
        self.state["nodes"] = parser.nodes
        self.state["signals"] = parser.signals
        self.state["gui_meta"] = parser.gui_meta
        self.state["cwd"] = None
        self.state["cwd_stack"] = []
        self.state["dirty"] = False
        self._p(f"Loaded {len(self.state['nodes'])} widgets, {len(self.state['signals'])} signals from {os.path.basename(path)}")
        return (1, True, None)

    def _extract_wcl(self, content):
        """Extract the WCL_CONFIG triple-quoted string from Config.py source."""
        match = re.search(r'WCL_CONFIG\s*=\s*"""(.*?)"""', content, re.DOTALL)
        if match:
            return match.group(1)
        match = re.search(r"WCL_CONFIG\s*=\s*'''(.*?)'''", content, re.DOTALL)
        if match:
            return match.group(1)
        return None

    def Save(self, params=None):
        """Write current config back to Config.py."""
        if not self.state["dirty"]:
            self._p("No changes to save.")
            return (1, True, None)
        path = self.state["config_path"]
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        new_wcl = self._generate_wcl()
        new_content = re.sub(
            r'(WCL_CONFIG\s*=\s*""")(.*?)(""")',
            lambda m: m.group(1) + new_wcl + m.group(3),
            content,
            count=1,
            flags=re.DOTALL,
        )
        if new_content == content:
            self._p("No changes detected in file content.")
            return (1, True, None)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        self.state["dirty"] = False
        self._p(f"Saved to {os.path.basename(path)}")
        return (1, True, None)

    def _generate_wcl(self):
        """Regenerate WCL_CONFIG string from current nodes and signals."""
        lines = []
        meta = self.state["gui_meta"]
        size = meta.get("size", "1400x900")
        title = meta.get("title", "GUI")
        lines.append(GUI_TEMPLATE.format(sz=size, ti=title))
        for node in self.state["nodes"]:
            parent_str = f"[@parent<{node.parent}>]" if node.parent else ""
            layout = node.properties.get("layout", "")
            layout_str = f"[@layout<{layout}>]" if layout else ""
            tab_str = f"[@tabname<{node.tab_name}>]" if node.tab_name else ""
            prop_parts = []
            for k, v in node.properties.items():
                if k == "layout":
                    continue
                prop_parts.append(f"[@{k}<{v}>]")
            prop_str = "".join(prop_parts)
            line = WCL_TEMPLATE.format(
                typ=node.node_type, nam=node.name,
                parent_str=parent_str, layout_str=layout_str,
                tab_str=tab_str, prop_str=prop_str,
            )
            lines.append(line)
        for sig in self.state["signals"]:
            lines.append(SIGNAL_TEMPLATE.format(
                wid=sig["widget"], sig=sig["signal"], hnd=sig["handler"],
            ))
        return "\n" + "\n".join(lines) + "\n"

    def _find_node(self, name):
        """Find a node by name."""
        for n in self.state["nodes"]:
            if n.name == name:
                return n
        return None

    def _children_of(self, name):
        """Get direct children of a widget by name."""
        return [n for n in self.state["nodes"] if n.parent == name]

    def _current_node(self):
        """Get the node for current cwd, or None if at root."""
        if self.state["cwd"] is None:
            return None
        return self._find_node(self.state["cwd"])

    def Tree(self, params=None):
        """Show full widget tree."""
        self._p("")
        self._print_tree(None, 0)
        self._p("")
        return (1, True, None)

    def _print_tree(self, parent_name, depth):
        """Recursively print tree from a parent."""
        children = self._children_of(parent_name)
        for child in children:
            indent = "  " * depth
            marker = "> " if self.state["cwd"] == child.name else "  "
            props_count = len(child.properties)
            tab_info = f" [tab:{child.tab_name}]" if child.tab_name else ""
            self._p(f"{marker}{indent}{child.node_type}  {child.name}  ({props_count} props){tab_info}")
            self._print_tree(child.name, depth + 1)

    def Ls(self, params=None):
        """List children of current widget (or roots if at root)."""
        cwd = self.state["cwd"]
        if cwd is None:
            roots = [n for n in self.state["nodes"] if not n.parent or not self._find_node(n.parent)]
            if not roots:
                roots = [n for n in self.state["nodes"] if not n.parent]
            self._p("")
            self._p("ROOT LEVEL:")
            for n in roots:
                child_count = len(self._children_of(n.name))
                self._p(f"  {n.node_type}  {n.name}  ({child_count} children)")
            self._p("")
        else:
            children = self._children_of(cwd)
            node = self._find_node(cwd)
            self._p("")
            self._p(f"{node.node_type} / {node.name}  ({len(children)} children)")
            self._p("")
            for c in children:
                gc = len(self._children_of(c.name))
                self._p(f"  {c.node_type}  {c.name}  ({gc} children)")
            self._p("")
        return (1, True, None)

    def Cd(self, params):
        """Navigate to a child widget or back to root."""
        if not params:
            self._err("Usage: cd <widget_name | .. | / >")
            return (0, None, ("USAGE", "cd <name|..|/>", 0))
        target = params[0]
        if target == "/" or target == "..":
            if target == ".." and self.state["cwd_stack"]:
                self.state["cwd"] = self.state["cwd_stack"].pop()
            else:
                self.state["cwd"] = None
                self.state["cwd_stack"] = []
            self._p(f"cwd: /{self.state['cwd'] or ''}")
            return (1, True, None)
        node = self._find_node(target)
        if node is None:
            self._err(f"No widget named '{target}'")
            return (0, None, ("NO_WIDGET", target, 0))
        if self.state["cwd"]:
            self.state["cwd_stack"].append(self.state["cwd"])
        self.state["cwd"] = target
        self._p(f"cwd: {target}  ({node.node_type})")
        return (1, True, None)

    def Pwd(self, params=None):
        """Show current position in tree."""
        cwd = self.state["cwd"]
        if cwd is None:
            self._p("/")
        else:
            path_parts = []
            current = cwd
            while current:
                path_parts.insert(0, current)
                node = self._find_node(current)
                if node and node.parent and self._find_node(node.parent):
                    current = node.parent
                else:
                    current = None
            self._p("/" + "/".join(path_parts))
        return (1, True, None)

    def Show(self, params=None):
        """Show details of current or specified widget."""
        target = params[0] if params else self.state["cwd"]
        if target is None:
            self._p("At root level. Use 'cd <widget>' to navigate, or 'show <widget>'.")
            self._p(f"Total widgets: {len(self.state['nodes'])}")
            self._p(f"Total signals: {len(self.state['signals'])}")
            return (1, True, None)
        node = self._find_node(target)
        if node is None:
            self._err(f"No widget named '{target}'")
            return (0, None, ("NO_WIDGET", target, 0))
        self._p("")
        self._p(f"  Type:     {node.node_type}")
        self._p(f"  Name:     {node.name}")
        self._p(f"  Parent:   {node.parent or '(root)'}")
        if node.tab_name:
            self._p(f"  Tab:      {node.tab_name}")
        if node.properties:
            self._p("  Properties:")
            for k, v in node.properties.items():
                self._p(f"    {k} = {v}")
        else:
            self._p("  Properties: (none)")
        children = self._children_of(node.name)
        if children:
            self._p(f"  Children ({len(children)}):")
            for c in children:
                self._p(f"    {c.node_type}  {c.name}")
        sigs = [s for s in self.state["signals"] if s["widget"] == node.name]
        if sigs:
            self._p(f"  Signals ({len(sigs)}):")
            for s in sigs:
                self._p(f"    {s['signal']} -> {s['handler']}")
        self._p("")
        return (1, True, None)

    def Set(self, params):
        """Set a property on current or specified widget."""
        if len(params) < 2:
            self._err("Usage: set <prop> <value> [widget_name]")
            self._err("  If widget_name omitted, uses current cwd.")
            return (0, None, ("USAGE", "set <prop> <value> [widget]", 0))
        prop = params[0]
        value = params[1]
        widget_name = params[2] if len(params) > 2 else self.state["cwd"]
        if widget_name is None:
            self._err("No widget selected. 'cd' to a widget or specify name.")
            return (0, None, ("NO_CWD", "No widget selected", 0))
        node = self._find_node(widget_name)
        if node is None:
            self._err(f"No widget named '{widget_name}'")
            return (0, None, ("NO_WIDGET", widget_name, 0))
        if prop in ("type", "name", "parent", "tabname"):
            if prop == "type":
                node.node_type = value
            elif prop == "name":
                old = node.name
                node.name = value
                for n in self.state["nodes"]:
                    if n.parent == old:
                        n.parent = value
                for s in self.state["signals"]:
                    if s["widget"] == old:
                        s["widget"] = value
                if self.state["cwd"] == old:
                    self.state["cwd"] = value
            elif prop == "parent":
                node.parent = value if value != "none" else None
            elif prop == "tabname":
                node.tab_name = value
            self.state["dirty"] = True
            self._p(f"Set {prop} = {value} on {widget_name}")
        else:
            if value.lower() == "none" or value.lower() == "delete":
                if prop in node.properties:
                    del node.properties[prop]
                    self.state["dirty"] = True
                    self._p(f"Removed property '{prop}' from {widget_name}")
                else:
                    self._p(f"Property '{prop}' not found on {widget_name}")
            else:
                node.properties[prop] = value
                self.state["dirty"] = True
                self._p(f"Set {prop} = {value} on {widget_name}")
        return (1, True, None)

    def Add(self, params):
        """Add a new widget."""
        if len(params) < 2:
            self._err("Usage: add <type> <name> [parent] [prop1=val1 prop2=val2 ...]")
            return (0, None, ("USAGE", "add <type> <name> [parent] [props]", 0))
        wtype = params[0]
        wname = params[1]
        parent = params[2] if len(params) > 2 else self.state["cwd"]
        if self._find_node(wname):
            self._err(f"Widget '{wname}' already exists")
            return (0, None, ("DUP", wname, 0))
        if parent and parent != "none" and not self._find_node(parent):
            self._err(f"Parent '{parent}' does not exist")
            return (0, None, ("NO_PARENT", parent, 0))
        props = {}
        tab_name = None
        for extra in params[3:]:
            if "=" in extra:
                k, v = extra.split("=", 1)
                if k == "tabname":
                    tab_name = v
                elif k == "layout":
                    props["layout"] = v
                else:
                    props[k] = v
        node = GUITreeNode(
            node_type=wtype,
            name=wname,
            parent=parent if parent != "none" else None,
            properties=props,
            tab_name=tab_name,
            line_num=0,
        )
        self.state["nodes"].append(node)
        self.state["dirty"] = True
        self._p(f"Added {wtype} '{wname}' parent={parent or '(root)'}")
        return (1, node, None)

    def Rm(self, params):
        """Remove a widget and its descendants."""
        if not params:
            self._err("Usage: rm <name>")
            return (0, None, ("USAGE", "rm <name>", 0))
        target = params[0]
        node = self._find_node(target)
        if node is None:
            self._err(f"No widget named '{target}'")
            return (0, None, ("NO_WIDGET", target, 0))
        to_remove = set()
        self._collect_subtree(target, to_remove)
        self.state["nodes"] = [n for n in self.state["nodes"] if n.name not in to_remove]
        self.state["signals"] = [s for s in self.state["signals"] if s["widget"] not in to_remove]
        if self.state["cwd"] in to_remove:
            self.state["cwd"] = None
            self.state["cwd_stack"] = []
        self.state["dirty"] = True
        self._p(f"Removed '{target}' and {len(to_remove) - 1} descendants")
        return (1, True, None)

    def _collect_subtree(self, name, acc):
        acc.add(name)
        for child in self._children_of(name):
            self._collect_subtree(child.name, acc)

    def Signals(self, params=None):
        """Show all signal declarations."""
        sigs = self.state["signals"]
        if not sigs:
            self._p("No signals defined.")
            return (1, True, None)
        self._p("")
        self._p(f"SIGNALS ({len(sigs)}):")
        for s in sigs:
            self._p(f"  {s['widget']:20s}  {s['signal']:25s}  ->  {s['handler']}")
        self._p("")
        return (1, True, None)

    def AddSignal(self, params):
        """Add a signal connection."""
        if len(params) < 3:
            self._err("Usage: add-signal <widget> <signal> <handler>")
            return (0, None, ("USAGE", "add-signal <widget> <signal> <handler>", 0))
        wid, sig, hnd = params[0], params[1], params[2]
        if not self._find_node(wid):
            self._err(f"Widget '{wid}' does not exist")
            return (0, None, ("NO_WIDGET", wid, 0))
        for existing in self.state["signals"]:
            if existing["widget"] == wid and existing["signal"] == sig:
                self._err(f"Signal {sig} on {wid} already exists -> {existing['handler']}")
                return (0, None, ("DUP_SIG", f"{wid}.{sig}", 0))
        self.state["signals"].append({
            "widget": wid, "signal": sig, "handler": hnd, "line": 0,
        })
        self.state["dirty"] = True
        self._p(f"Added signal: {wid}.{sig} -> {hnd}")
        return (1, True, None)

    def RmSignal(self, params):
        """Remove a signal connection."""
        if len(params) < 2:
            self._err("Usage: rm-signal <widget> <signal>")
            return (0, None, ("USAGE", "rm-signal <widget> <signal>", 0))
        wid, sig = params[0], params[1]
        before = len(self.state["signals"])
        self.state["signals"] = [
            s for s in self.state["signals"]
            if not (s["widget"] == wid and s["signal"] == sig)
        ]
        if len(self.state["signals"]) == before:
            self._err(f"No signal {sig} on {wid} found")
            return (0, None, ("NOT_FOUND", f"{wid}.{sig}", 0))
        self.state["dirty"] = True
        self._p(f"Removed signal: {wid}.{sig}")
        return (1, True, None)

    def Validate(self, params=None):
        """Validate the config for common issues."""
        issues = []
        names = set()
        for n in self.state["nodes"]:
            if not n.name:
                issues.append(("ERROR", f"Widget has no name: type={n.node_type} line={n.line_num}"))
            elif n.name in names:
                issues.append(("ERROR", f"Duplicate widget name: {n.name}"))
            else:
                names.add(n.name)
            if not n.node_type:
                issues.append(("ERROR", f"Widget '{n.name}' has no type"))
            elif n.node_type not in VALID_WIDGET_TYPES:
                issues.append(("WARN", f"Widget '{n.name}' has unknown type: {n.node_type}"))
        for n in self.state["nodes"]:
            if n.parent and n.parent not in names:
                issues.append(("ERROR", f"Widget '{n.name}' references missing parent: {n.parent}"))
        for n in self.state["nodes"]:
            if n.parent and n.parent == n.name:
                issues.append(("ERROR", f"Widget '{n.name}' is its own parent"))
        for s in self.state["signals"]:
            if s["widget"] not in names:
                issues.append(("ERROR", f"Signal references missing widget: {s['widget']}.{s['signal']}"))
            if not s["signal"]:
                issues.append(("ERROR", f"Signal on '{s['widget']}' has no signal name"))
            if not s["handler"]:
                issues.append(("ERROR", f"Signal {s['widget']}.{s['signal']} has no handler"))
        roots = [n for n in self.state["nodes"] if not n.parent or n.parent not in names]
        if len(roots) == 0 and len(self.state["nodes"]) > 0:
            issues.append(("ERROR", "No root widgets found (possible cycle)"))
        elif len(roots) > 1:
            root_names = [r.name or "(unnamed)" for r in roots]
            issues.append(("INFO", f"Multiple roots: {', '.join(root_names)}"))
        for n in self.state["nodes"]:
            layout = n.properties.get("layout")
            if layout and layout not in LAYOUT_TYPES:
                issues.append(("WARN", f"Widget '{n.name}' has unknown layout: {layout}"))
        if not self.state["gui_meta"]:
            issues.append(("WARN", "No [@GUI] metadata found (size/title)"))
        self._p("")
        if not issues:
            self._p("VALIDATION PASSED — no issues found.")
        else:
            errors = [i for i in issues if i[0] == "ERROR"]
            warns = [i for i in issues if i[0] == "WARN"]
            infos = [i for i in issues if i[0] == "INFO"]
            self._p(f"VALIDATION: {len(errors)} errors, {len(warns)} warnings, {len(infos)} info")
            self._p("")
            for level, msg in issues:
                symbol = {"ERROR": "[ERR]", "WARN": "[WRN]", "INFO": "[INF]"}[level]
                self._p(f"  {symbol} {msg}")
        self._p("")
        if self.state["dirty"]:
            self._p("  (unsaved changes — use 'save' to write to Config.py)")
        return (1, issues, None)

    def Find(self, params):
        """Find widgets by name or type pattern."""
        if not params:
            self._err("Usage: find <pattern>")
            return (0, None, ("USAGE", "find <pattern>", 0))
        pattern = params[0].lower()
        matches = []
        for n in self.state["nodes"]:
            if pattern in (n.name or "").lower() or pattern in (n.node_type or "").lower():
                matches.append(n)
        if not matches:
            self._p(f"No widgets matching '{pattern}'")
        else:
            self._p(f"\nFOUND {len(matches)} match(es):")
            for n in matches:
                self._p(f"  {n.node_type}  {n.name}  parent={n.parent or '(root)'}")
            self._p("")
        return (1, matches, None)

    def Meta(self, params=None):
        """Show or set GUI metadata."""
        meta = self.state["gui_meta"]
        if not params:
            self._p("")
            self._p("GUI METADATA:")
            for k, v in meta.items():
                self._p(f"  {k} = {v}")
            self._p("")
            return (1, meta, None)
        if len(params) < 2:
            self._err("Usage: meta <key> <value>  (e.g. meta size 1600x1000)")
            return (0, None, ("USAGE", "meta <key> <value>", 0))
        key, value = params[0], params[1]
        meta[key] = value
        self.state["dirty"] = True
        self._p(f"Set meta {key} = {value}")
        return (1, True, None)

    def ClusterList(self, params=None):
        """List all available cluster categories."""
        self._p("")
        self._p(f"CLUSTERS ({len(CLUSTERS)} categories):")
        self._p("")
        for name, info in CLUSTERS.items():
            widget_count = len(info.get("widgets", []))
            action_count = len(info.get("actions", []))
            prop_count = len(info.get("properties", []))
            total = widget_count + action_count + prop_count
            self._p(f"  {name:15s}  {info['desc']}")
            self._p(f"  {'':15s}  {widget_count} widgets, {action_count} actions, {prop_count} properties ({total} total)")
            self._p("")
        self._p("Use 'cluster <name>' to see all items in a category.")
        self._p("Use 'cluster-add <cluster> <item_name> [parent]' to add from a cluster.")
        self._p("")
        return (1, True, None)

    def Cluster(self, params):
        """Show all items in a cluster category."""
        if not params:
            return self.ClusterList()
        cluster_name = params[0].lower()
        cluster = CLUSTERS.get(cluster_name)
        if cluster is None:
            self._err(f"Unknown cluster: {cluster_name}. Use 'clusters' to see available.")
            return (0, None, ("NO_CLUSTER", cluster_name, 0))
        self._p("")
        self._p(f"CLUSTER: {cluster_name} — {cluster['desc']}")
        self._p("=" * 60)
        widgets = cluster.get("widgets", [])
        if widgets:
            self._p("")
            self._p(f"WIDGETS ({len(widgets)}):")
            for i, (typ, name, desc) in enumerate(widgets):
                self._p(f"  [{i:2d}] {typ:25s}  {name:20s}  {desc}")
        actions = cluster.get("actions", [])
        if actions:
            self._p("")
            self._p(f"ACTIONS ({len(actions)}):")
            for i, (name, desc, hint) in enumerate(actions):
                self._p(f"  [{i:2d}] {name:25s}  {desc}")
                if hint:
                    self._p(f"       {'':25s}  hint: {hint}")
        properties = cluster.get("properties", [])
        if properties:
            self._p("")
            self._p(f"PROPERTIES ({len(properties)}):")
            for i, (name, desc, ptype) in enumerate(properties):
                self._p(f"  [{i:2d}] {name:25s}  {desc}  ({ptype})")
        self._p("")
        self._p("Use 'cluster-add <cluster> <item_name> [parent]' to add an item.")
        self._p("  For widgets: cluster-add canvas canvas central")
        self._p("  For actions: cluster-add canvas zoom_in ctrl_row")
        self._p("")
        return (1, cluster, None)

    def ClusterAdd(self, params):
        """Add a widget or action from a cluster to the config tree."""
        if len(params) < 2:
            self._err("Usage: cluster-add <cluster_name> <item_name> [parent]")
            self._err("  Example: cluster-add canvas zoom_in ctrl_row")
            self._err("  Example: cluster-add canvas canvas central")
            return (0, None, ("USAGE", "cluster-add <cluster> <item> [parent]", 0))
        cluster_name = params[0].lower()
        item_name = params[1].lower()
        parent = params[2] if len(params) > 2 else self.state["cwd"]
        cluster = CLUSTERS.get(cluster_name)
        if cluster is None:
            self._err(f"Unknown cluster: {cluster_name}. Use 'clusters' to see available.")
            return (0, None, ("NO_CLUSTER", cluster_name, 0))
        found = None
        found_kind = None
        for typ, name, desc in cluster.get("widgets", []):
            if name.lower() == item_name:
                found = ("widget", typ, name, desc)
                found_kind = "widget"
                break
        if not found:
            for name, desc, hint in cluster.get("actions", []):
                if name.lower() == item_name:
                    found = ("action", None, name, desc)
                    found_kind = "action"
                    break
        if not found:
            self._err(f"Item '{item_name}' not found in cluster '{cluster_name}'.")
            self._p(f"Use 'cluster {cluster_name}' to see available items.")
            return (0, None, ("NO_ITEM", item_name, 0))
        if found_kind == "widget":
            _, wtype, wname, wdesc = found
            if self._find_node(wname):
                self._err(f"Widget '{wname}' already exists in config.")
                return (0, None, ("DUP", wname, 0))
            if parent and parent != "none" and not self._find_node(parent):
                self._err(f"Parent '{parent}' does not exist.")
                return (0, None, ("NO_PARENT", parent, 0))
            node = GUITreeNode(
                node_type=wtype,
                name=wname,
                parent=parent if parent != "none" else None,
                properties={},
                line_num=0,
            )
            self.state["nodes"].append(node)
            self.state["dirty"] = True
            self._p(f"Added widget: {wtype} '{wname}' parent={parent or '(root)'}")
            self._p(f"  {wdesc}")
            return (1, node, None)
        else:
            _, _, aname, adesc = found
            btn_name = f"btn_{aname}"
            if self._find_node(btn_name):
                self._err(f"Widget '{btn_name}' already exists.")
                return (0, None, ("DUP", btn_name, 0))
            if parent and parent != "none" and not self._find_node(parent):
                self._err(f"Parent '{parent}' does not exist.")
                return (0, None, ("NO_PARENT", parent, 0))
            node = GUITreeNode(
                node_type="QPushButton",
                name=btn_name,
                parent=parent if parent != "none" else None,
                properties={"text": aname.replace("_", " ").title()},
                line_num=0,
            )
            self.state["nodes"].append(node)
            handler_name = f"on_{aname}"
            self.state["signals"].append({
                "widget": btn_name, "signal": "clicked",
                "handler": handler_name, "line": 0,
            })
            self.state["dirty"] = True
            self._p(f"Added action button: QPushButton '{btn_name}' parent={parent or '(root)'}")
            self._p(f"  Action: {aname} — {adesc}")
            self._p(f"  Signal: {btn_name}.clicked -> {handler_name}")
            return (1, node, None)

    def Help(self, params=None):
        """Show available commands."""
        self._p("")
        self._p("CONFIG CLI — Commands:")
        self._p("")
        self._p("  NAVIGATION:")
        self._p("    tree              Show full widget tree")
        self._p("    ls                List children of current widget")
        self._p("    cd <name>         Navigate into a widget")
        self._p("    cd ..             Go back one level")
        self._p("    cd /              Go to root")
        self._p("    pwd               Show current path")
        self._p("    find <pattern>    Find widgets by name or type")
        self._p("")
        self._p("  INSPECTION:")
        self._p("    show [name]       Show widget details (current if no name)")
        self._p("    signals           Show all signal connections")
        self._p("    meta [key val]    Show/set GUI metadata (size, title)")
        self._p("")
        self._p("  CLUSTERS (GUI taxonomy — discover what's possible):")
        self._p("    clusters          List all cluster categories")
        self._p("    cluster <name>    Show all items in a cluster (canvas, menu, toolbar, ...)")
        self._p("    cluster-add <cluster> <item> [parent]  Add item from cluster to tree")
        self._p("")
        self._p("  EDITING:")
        self._p("    set <prop> <val> [widget]  Set a property on widget")
        self._p("    add <type> <name> [parent] [k=v ...]  Add widget")
        self._p("    rm <name>         Remove widget and descendants")
        self._p("    add-signal <w> <sig> <handler>  Add signal connection")
        self._p("    rm-signal <w> <sig>           Remove signal connection")
        self._p("    meta <key> <val>  Set GUI metadata")
        self._p("")
        self._p("  FILE:")
        self._p("    save              Write changes to Config.py")
        self._p("    reload            Reload from Config.py (discards unsaved)")
        self._p("    validate          Check config for errors")
        self._p("")
        self._p("    help              Show this help")
        self._p("    quit / exit       Exit the CLI")
        self._p("")
        return (1, True, None)

    def Quit(self, params=None):
        """Exit the CLI."""
        if self.state["dirty"]:
            self._p("You have unsaved changes. Use 'save' to write, or 'quit' again to discard.")
            self.state["dirty"] = False
            return (1, True, None)
        self.state["running"] = False
        self._p("Bye.")
        return (1, True, None)

    def Repl(self):
        """Run interactive REPL loop."""
        self._p("")
        self._p("=" * 60)
        self._p("  CONFIG CLI — WCL GUI Config Editor")
        self._p("  Type 'help' for commands, 'tree' to see widget tree")
        self._p("=" * 60)
        self._p("")
        while self.state["running"]:
            try:
                cwd = self.state["cwd"] or "/"
                prompt = f"config-cli:{cwd}> "
                raw = input(prompt).strip()
                if not raw:
                    continue
                parts = raw.split()
                command = parts[0]
                params = parts[1:]
                self.Run(command, params)
            except KeyboardInterrupt:
                self._p("")
                if self.state["dirty"]:
                    self._p("Unsaved changes. Press Ctrl+C again to force quit.")
                    self.state["dirty"] = False
                else:
                    self._p("Bye.")
                    break
            except EOFError:
                self._p("Bye.")
                break
            except Exception as e:
                self._err(f"Exception: {e}")


def main():
    args = sys.argv[1:]
    if not args:
        cli = ConfigCli()
        cli.Repl()
        return
    if args[0] in ("-h", "--help", "help"):
        sys.stdout.write(
            "Usage: Cli-Gui_config-cli.py [command] [args...]\n"
            "       Cli-Gui_config-cli.py --interactive\n\n"
            "Commands: tree, ls, show, set, add, rm, signals, validate, save, reload, help, cluster, clusters, cluster-add\n"
            "Use --interactive or no args for REPL mode.\n"
        )
        return
    if args[0] == "--interactive" or args[0] == "-i":
        cli = ConfigCli()
        cli.Repl()
        return
    cli = ConfigCli()
    command = args[0]
    params = args[1:]
    result = cli.Run(command, params)
    if result[0] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
