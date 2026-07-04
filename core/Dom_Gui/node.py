# [@GHOST]{[@file<GUITreeNode.py>][@domain<Dom_Gui>][@role<data>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<gui_data_node>][@return<dict>][@orch<GUIParser>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Pure data class — one node in the GUI widget tree parsed from BCL declarations}


class GUITreeNode:
    """One widget declaration parsed from a BCL [@WIDGET] or [@GUI] line."""

    def __init__(self, node_type=None, name=None, parent=None,
                 properties=None, signals=None, children=None,
                 tab_name=None, order=0, line_num=0):
        self.node_type = node_type
        self.name = name
        self.parent = parent
        self.properties = properties if properties is not None else {}
        self.signals = signals if signals is not None else []
        self.children = children if children is not None else []
        self.tab_name = tab_name
        self.order = order
        self.line_num = line_num

    def to_dict(self):
        return {
            "type": self.node_type,
            "name": self.name,
            "parent": self.parent,
            "properties": self.properties,
            "signals": self.signals,
            "children": [c.to_dict() for c in self.children],
            "tab_name": self.tab_name,
            "order": self.order,
            "line": self.line_num,
        }

    def __repr__(self):
        return f"GUITreeNode({self.node_type}/{self.name} parent={self.parent} children={len(self.children)})"
