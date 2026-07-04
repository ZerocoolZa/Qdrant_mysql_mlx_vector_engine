# [@GHOST]{[@file<GUIParser.py>][@domain<Dom_Gui>][@role<parser>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<bcl_parser>][@return<list>][@orch<GUIBuilder>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Reads BCL/WCL bracket declarations from Config.py, builds GUITreeNode tree}
# [@WCL]{[@input<Config.py_source>][@output<GUITreeNode_list>][@syntax<#_[@WIDGET]{[@type<...>][@name<...>]}>]}

import re
import os
import importlib
import inspect

from .node import GUITreeNode


class GUIParser:
    """Parse BCL/WCL bracket declarations from Config.py into a widget tree.

    WCL (Wayne Cascade Language) format:
        # [@GUI]{[@window<name>][@size<WxH>][@theme<name>][@title<text>]}
        # [@WIDGET]{[@type<QPushButton>][@name<btn>][@parent<bar>][@text<Go>]}
        # [@SIGNAL]{[@widget<btn>][@signal<clicked>][@handler<on_go>]}
    """

    BCL_PATTERN = re.compile(
        r'#\s*\[@(GUI|WIDGET|SIGNAL|LAYOUT|MENU|TRAY)\]\{([^}]*)\}',
        re.MULTILINE
    )
    KV_PATTERN = re.compile(r'\[@(\w+)<([^>]*)>\]')
    LINE_NUM_PATTERN = re.compile(r'^', re.MULTILINE)

    def __init__(self):
        self.nodes = []
        self.errors = []
        self.gui_meta = {}
        self.signals = []

    def parse_string(self, text):
        """Parse BCL declarations from a string. Returns list of GUITreeNode."""
        self.nodes = []
        self.errors = []
        self.gui_meta = {}
        self.signals = []

        line_offsets = [0]
        for i, ch in enumerate(text):
            if ch == '\n':
                line_offsets.append(i + 1)

        def get_line_num(pos):
            lo, hi = 0, len(line_offsets) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if line_offsets[mid] <= pos:
                    lo = mid
                else:
                    hi = mid - 1
            return lo + 1

        for match in self.BCL_PATTERN.finditer(text):
            tag = match.group(1)
            body = match.group(2)
            line_num = get_line_num(match.start())

            kvs = {}
            for kv_match in self.KV_PATTERN.finditer(body):
                kvs[kv_match.group(1)] = kv_match.group(2)

            if tag == "GUI":
                self.gui_meta = kvs
            elif tag == "WIDGET":
                node = GUITreeNode(
                    node_type=kvs.get("type"),
                    name=kvs.get("name"),
                    parent=kvs.get("parent"),
                    properties={k: v for k, v in kvs.items()
                                if k not in ("type", "name", "parent", "tabname", "order")},
                    tab_name=kvs.get("tabname"),
                    order=int(kvs.get("order", 0)),
                    line_num=line_num,
                )
                self.nodes.append(node)
            elif tag == "SIGNAL":
                self.signals.append({
                    "widget": kvs.get("widget"),
                    "signal": kvs.get("signal"),
                    "handler": kvs.get("handler"),
                    "accepts": kvs.get("accepts"),
                    "line": line_num,
                })
            elif tag == "MENU":
                node = GUITreeNode(
                    node_type="QMenu",
                    name=kvs.get("name"),
                    parent=kvs.get("parent"),
                    properties={k: v for k, v in kvs.items()
                                if k not in ("type", "name", "parent", "order")},
                    order=int(kvs.get("order", 0)),
                    line_num=line_num,
                )
                self.nodes.append(node)
            elif tag == "TRAY":
                node = GUITreeNode(
                    node_type="QSystemTrayIcon",
                    name=kvs.get("name", "tray"),
                    parent=None,
                    properties={k: v for k, v in kvs.items()
                                if k not in ("type", "name", "parent", "order")},
                    line_num=line_num,
                )
                self.nodes.append(node)

        self._link_children()
        return self.nodes

    def parse_file(self, path):
        """Parse BCL declarations from a file path."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self.parse_string(f.read())
        except Exception as e:
            self.errors.append(f"File error: {e}")
            return []

    def parse_module(self, module):
        """Parse BCL declarations from a Python module object."""
        try:
            source_file = inspect.getsourcefile(module)
            if source_file and os.path.exists(source_file):
                return self.parse_file(source_file)
            source = inspect.getsource(module)
            return self.parse_string(source)
        except Exception as e:
            self.errors.append(f"Module error: {e}")
            return []

    def _link_children(self):
        """Link child nodes to parent nodes by name."""
        by_name = {}
        for node in self.nodes:
            if node.name:
                by_name[node.name] = node

        for node in self.nodes:
            if node.parent and node.parent in by_name:
                by_name[node.parent].children.append(node)

    def get_tree(self):
        """Return root nodes (nodes with no parent or parent not in tree)."""
        names = {n.name for n in self.nodes if n.name}
        roots = [n for n in self.nodes if not n.parent or n.parent not in names]
        return roots

    def get_signals(self):
        """Return parsed signal declarations."""
        return self.signals

    def get_gui_meta(self):
        """Return [@GUI] metadata (window size, theme, title)."""
        return self.gui_meta
