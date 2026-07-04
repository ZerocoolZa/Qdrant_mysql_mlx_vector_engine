#!/usr/bin/env python3
#[@GHOST]{("file_path=_tmp_wcl_test.py";"identity=_tmp_wcl_test.py";"purpose=";"date=2026-06-28";"version=1.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@pass]{"return=Tuple3";"dispatch=Run";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete"}[@fail]{"decorators_found";"print_found";"hardcoded_values";"self._used"}}
#[@FILEID]{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}
#[@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true")}

import sys
sys.path.insert(0, "core")
from Dom_Gui.parser import GUIParser
from Dom_Gui.builder import GUIBuilder

sample = '''# [@GUI]{[@name<demo>][@size<800x600>][@title<WCL Demo>]}
# [@WIDGET]{[@type<QMainWindow>][@name<main>]}
# [@WIDGET]{[@type<QSplitter>][@name<split>][@parent<main>]}
# [@WIDGET]{[@type<QPlainTextEdit>][@name<json_ed>][@parent<split>]}
# [@WIDGET]{[@type<QTabWidget>][@name<tabs>][@parent<split>]}
# [@WIDGET]{[@type<QGraphicsView>][@name<canvas>][@parent<tabs>][@tabname<Canvas>]}
# [@SIGNAL]{[@widget<json_ed>][@signal<textChanged>][@handler<on_json_changed>]}
'''

p = GUIParser()
nodes = p.parse_string(sample)
print("PARSED nodes:", len(nodes), "| signals:", len(p.get_signals()))
print("GUI meta:", p.get_gui_meta())
for n in nodes:
    print("  ", n.node_type, "/", n.name, "parent=", n.parent)

from PyQt6.QtWidgets import QApplication, QMainWindow
app = QApplication(sys.argv)

class FakeHost(QMainWindow):
    def on_json_changed(self):
        pass

host = FakeHost()
b = GUIBuilder(host=host)
widgets = b.build(nodes, p.get_signals())
print("BUILT widgets:", list(widgets.keys()))
print("Warnings:", b.get_warnings())
print("Connections:", b.router.connections)

# Check the LAYOUT tag gap
sample2 = "# [@LAYOUT]{[@type<VBox>][@name<main_layout>]}"
p2 = GUIParser()
n2 = p2.parse_string(sample2)
print("LAYOUT tag handled?", len(n2), "nodes (should be >0 if handled, 0 if silently dropped)")
