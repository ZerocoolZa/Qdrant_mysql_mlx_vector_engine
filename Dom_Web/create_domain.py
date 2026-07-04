#!/usr/bin/env python3
"""
#[@GHOST]{[@file<create_domain.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<domain_engine>][@return<Tuple3>][@orch<none>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<create_domain.py>][@hash<placeholder>]}
#[@SUMMARY]{Universal domain engine - loads external domain definitions, generates dom_*.py skeletons, 8 graph data sets, trees, symbol indexes. Data-driven, not hardcoded.}
#[@CLASS]{DomainEngine}
#[@METHOD]{__init__, LoadDomainDefinition, ListDomains, BuildHeader, BuildMainClass, BuildNestedClasses, WritePython, WriteMarkdownTree, WriteGraphviz, WriteMermaid, WriteSymbolIndex, WriteGraphData, WriteConfigData, GenerateAll, GuidedCLI, Run, Main}
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List


class DomainEngine:
    """
    Universal domain engine.
    Loads domain definitions from external JSON files.
    Generates Python skeletons, graph data, trees, symbol indexes.
    Data-driven: engine code never changes, only definitions change.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "domain": None,
            "definition": None,
            "output_dir": None,
            "definitions_dir": None,
            "generated_files": [],
            "errors": [],
            "stats": {
                "classes": 0,
                "methods": 0,
                "edges": 0,
                "files": 0,
            },
        }
        home = os.path.dirname(os.path.abspath(__file__))
        self.state["definitions_dir"] = os.path.join(home, "domain_definitions")

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
        return (1, self.state, None)

    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if not params:
            return (0, None, (1, "Missing config params", 0))
        self.state.update(params)
        return (1, "Config updated", None)

    def ListDomains(self) -> Tuple[int, List[str], Optional[Tuple]]:
        """List all available domain definition files"""
        defs_dir = self.state["definitions_dir"]
        if not os.path.exists(defs_dir):
            return (1, [], None)
        domains = []
        for fname in sorted(os.listdir(defs_dir)):
            if fname.endswith(".json"):
                domains.append(fname.replace(".json", ""))
        return (1, domains, None)

    def LoadDomainDefinition(self, domain_name: str) -> Tuple[int, Dict, Optional[Tuple]]:
        """Load a domain definition from an external JSON file"""
        defs_dir = self.state["definitions_dir"]
        fpath = os.path.join(defs_dir, f"{domain_name}.json")
        if not os.path.exists(fpath):
            available = []
            if os.path.exists(defs_dir):
                available = [f.replace(".json", "") for f in os.listdir(defs_dir) if f.endswith(".json")]
            return (0, None, (2, f"Domain definition not found: {domain_name}. Available: {', '.join(available) if available else 'none'}", 0))
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                definition = json.load(f)
            required = ["name", "file", "classes"]
            for key in required:
                if key not in definition:
                    return (0, None, (3, f"Domain definition missing required key: {key}", 0))
            self.state["domain"] = domain_name
            self.state["definition"] = definition
            return (1, definition, None)
        except json.JSONDecodeError as e:
            return (0, None, (4, f"JSON parse error: {str(e)}", 0))
        except Exception as e:
            return (0, None, (5, f"Load error: {str(e)}", 0))

    def SaveDomainDefinition(self, definition: Dict, domain_name: str) -> Tuple[int, str, Optional[Tuple]]:
        """Save a domain definition to an external JSON file"""
        defs_dir = self.state["definitions_dir"]
        if not os.path.exists(defs_dir):
            os.makedirs(defs_dir, exist_ok=True)
        fpath = os.path.join(defs_dir, f"{domain_name}.json")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(definition, f, indent=2)
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (6, f"Save error: {str(e)}", 0))

    def BuildHeader(self, definition: Dict) -> str:
        """Build VBStyle BCL header for the domain file"""
        now = datetime.now().strftime("%Y-%m-%d")
        name = definition["name"]
        fname = definition["file"]
        summary = definition.get("summary", f"{name} domain")
        classes = [c["name"] for c in definition["classes"]]
        all_methods = []
        for c in definition["classes"]:
            all_methods.extend(c.get("methods", []))
        class_str = ", ".join(classes)
        method_str = ", ".join(all_methods[:20])
        if len(all_methods) > 20:
            method_str += ", ..."
        return f'''#!/usr/bin/env python3
"""
#[@GHOST]{{[@file<{fname}>][@state<active>][@date<{now}>][@ver<1.0>][@auth<DomainEngine>]}}
#[@VBSTYLE]{{[@auth<system>][@role<domain>][@return<Tuple3>][@orch<{name}>][@mem<none>][@db<none>]}}
#[@FILEID]{{[@path<{fname}>][@hash<placeholder>]}}
#[@SUMMARY]{{{summary}}}
#[@CLASS]{{{class_str}}}
#[@METHOD]{{{method_str}}}
"""

import os
import sys
import json
import re
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
'''

    def BuildNestedClasses(self, definition: Dict) -> str:
        """Build all nested class definitions with method stubs"""
        lines = []
        indent = "    "
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            lines.append(f"{indent}class {cls_name}:")
            lines.append(f'{indent}    """{cls_name} component"""')
            lines.append("")
            lines.append(f"{indent}    def __init__(self, mem=None, db=None, param=None):")
            lines.append(f"{indent}        self.state = {{}}")
            lines.append("")
            for method in methods:
                lines.append(f"{indent}    def {method}(self, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
                lines.append(f"{indent}        return (1, None, None)")
                lines.append("")
            lines.append(f"{indent}    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
            lines.append(f"{indent}        if params is None:")
            lines.append(f"{indent}            params = {{}}")
            for method in methods:
                lines.append(f'{indent}        if command == "{method.lower()}":')
                lines.append(f"{indent}            return self.{method}(params)")
            lines.append(f'{indent}        return (0, None, (1, f"Unknown command: {{command}}", 0))')
            lines.append("")
            lines.append("")
        return "\n".join(lines)

    def BuildMainClass(self, definition: Dict) -> str:
        """Build the main controller class with Run dispatch"""
        name = definition["name"]
        classes = definition["classes"]
        lines = []
        lines.append(f"class {name}:")
        lines.append(f'    """{name} domain controller / authority"""')
        lines.append("")
        lines.append(f"    def __init__(self, mem=None, db=None, param=None):")
        lines.append(f"        self.state = {{")
        lines.append(f"            'config': {{}},")
        lines.append(f"            'catalog': [],")
        lines.append(f"            'results': [],")
        lines.append(f"            'errors': [],")
        lines.append(f"            'meta': {{")
        lines.append(f"                'last_command': None,")
        lines.append(f"                'last_component': None,")
        lines.append(f"            }},")
        lines.append(f"        }}")
        lines.append("")
        for cls in classes:
            lines.append(f"        self.{cls['name'].lower()} = self.{cls['name']}()")
        lines.append("")
        lines.append(f"    def _p(self, params, key, default=None):")
        lines.append(f"        if not params:")
        lines.append(f"            return default")
        lines.append(f"        return params.get(key, default)")
        lines.append("")
        lines.append(f"    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:")
        lines.append(f"        return (1, self.state, None)")
        lines.append("")
        lines.append(f"    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:")
        lines.append(f"        if not params:")
        lines.append(f"            return (0, None, (1, 'Missing config params', 0))")
        lines.append(f"        self.state['config'].update(params)")
        lines.append(f"        return (1, 'Config updated', None)")
        lines.append("")
        lines.append(f"    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:")
        lines.append(f'        """Dispatch to nested component classes"""')
        lines.append(f"        if params is None:")
        lines.append(f"            params = {{}}")
        lines.append(f"        self.state['meta']['last_command'] = command")
        lines.append("")
        for cls in classes:
            cls_lower = cls["name"].lower()
            methods = cls.get("methods", [])
            method_names = ", ".join([f'"{m.lower()}"' for m in methods])
            lines.append(f"        if command in ({method_names}):")
            lines.append(f"            self.state['meta']['last_component'] = '{cls_lower}'")
            lines.append(f"            return self.{cls_lower}.Run(command, params)")
            lines.append("")
        lines.append(f'        if command == "read_state":')
        lines.append(f"            return self.read_state()")
        lines.append(f'        if command == "set_config":')
        lines.append(f"            return self.SetConfig(params)")
        lines.append(f'        return (0, None, (2, f"Unknown command: {{command}}", 0))')
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def WritePython(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write the complete dom_*.py file"""
        header = self.BuildHeader(definition)
        nested = self.BuildNestedClasses(definition)
        main_class = self.BuildMainClass(definition)
        content = header + "\n" + main_class + nested
        fname = definition["file"]
        fpath = os.path.join(output_dir, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (10, f"Write error: {str(e)}", 0))

    def WriteMarkdownTree(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write markdown class tree"""
        name = definition["name"]
        fname = definition["file"].replace(".py", "_tree.md")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"# {name} Domain Tree")
        lines.append(f"")
        lines.append(f"Generated by DomainEngine on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"")
        lines.append(f"```")
        lines.append(f"{name}")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            if methods:
                lines.append(f"├── {cls_name}")
                for i, m in enumerate(methods):
                    prefix = "│   ├──" if i < len(methods) - 1 else "│   └──"
                    lines.append(f"{prefix} {m}()")
            else:
                lines.append(f"├── {cls_name}")
        lines.append(f"└── Run()  ← orchestrator dispatch")
        lines.append(f"```")
        lines.append(f"")
        total_methods = sum(len(c.get("methods", [])) for c in definition["classes"])
        lines.append(f"**Classes:** {len(definition['classes'])}")
        lines.append(f"**Methods:** {total_methods}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (11, f"Write error: {str(e)}", 0))

    def WriteGraphviz(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write Graphviz .dot file"""
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.dot")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"digraph {name} {{")
        lines.append(f'    rankdir=TB;')
        lines.append(f'    node [shape=box, style=filled, fillcolor=lightblue];')
        lines.append(f'    "{name}" [shape=box, style=filled, fillcolor=lightgreen, fontsize=16];')
        lines.append(f"")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            lines.append(f'    "{name}" -> "{cls_name}";')
            methods = cls.get("methods", [])
            for m in methods:
                m_node = f"{cls_name}.{m}"
                lines.append(f'    "{cls_name}" -> "{m_node}" [shape=ellipse, style=filled, fillcolor=lightyellow];')
        edges = definition.get("edges", [])
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'    "{src}" -> "{dst}" [label="{etype}", style=dashed, color=gray];')
        self.state["stats"]["edges"] = len(edges)
        lines.append(f"")
        lines.append(f'    "{name}" -> "Run" [label="dispatch", style=dashed];')
        lines.append(f"}}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (12, f"Write error: {str(e)}", 0))

    def WriteMermaid(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write Mermaid graph file"""
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph.mmd")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f"graph TD")
        lines.append(f"    {name}[{name} Controller]")
        lines.append(f"")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            safe = re.sub(r'[^a-zA-Z0-9]', '_', cls_name)
            lines.append(f"    {name} --> {safe}[{cls_name}]")
            methods = cls.get("methods", [])
            for m in methods:
                m_safe = re.sub(r'[^a-zA-Z0-9]', '_', m)
                lines.append(f"    {safe} --> {safe}_{m_safe}({m})")
        edges = definition.get("edges", [])
        for edge in edges:
            src = re.sub(r'[^a-zA-Z0-9]', '_', edge.get("src", ""))
            dst = re.sub(r'[^a-zA-Z0-9]', '_', edge.get("dst", ""))
            etype = edge.get("type", "USES")
            lines.append(f"    {src} -.->|{etype}| {dst}")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (13, f"Write error: {str(e)}", 0))

    def WriteSymbolIndex(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write JSON symbol index"""
        name = definition["name"]
        fname = definition["file"].replace(".py", "_symbols.json")
        fpath = os.path.join(output_dir, fname)
        symbols = {
            "domain": name,
            "file": definition["file"],
            "generated": datetime.now().isoformat(),
            "controller": name,
            "classes": [],
            "edges": definition.get("edges", []),
            "total_classes": len(definition["classes"]),
            "total_methods": 0,
            "total_edges": len(definition.get("edges", [])),
        }
        total_methods = 0
        for cls in definition["classes"]:
            methods = cls.get("methods", [])
            total_methods += len(methods)
            symbols["classes"].append({
                "name": cls["name"],
                "methods": methods,
                "method_count": len(methods),
            })
        symbols["total_methods"] = total_methods
        self.state["stats"]["classes"] = len(definition["classes"])
        self.state["stats"]["methods"] = total_methods
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(symbols, f, indent=2)
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (14, f"Write error: {str(e)}", 0))

    def WriteGraphData(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """
        Write graph data file compatible with Dom_Graph viewers.
        Produces GRAPH_CLASSES, GRAPH_EDGES, GRAPH_FLOWS, GRAPH_CATEGORIES
        that the 8 graph viewers (Plan, Spec, Flow, Lifecycle, Dep, Error, Orch, Gap) consume.
        """
        name = definition["name"]
        fname = definition["file"].replace(".py", "_graph_data.py")
        fpath = os.path.join(output_dir, fname)
        lines = []
        lines.append(f'"""')
        lines.append(f'Graph data for {name} domain.')
        lines.append(f'Generated by DomainEngine. Consumed by the 8 graph viewers.')
        lines.append(f'"""')
        lines.append(f"")
        lines.append(f"GRAPH_CLASSES = [")
        for cls in definition["classes"]:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            dispatch = ", ".join([f'"{m.lower()}"' for m in methods])
            desc = cls.get("description", f"{cls_name} component")
            lines.append(f'    ("{cls_name}", "class", [{dispatch}], "{desc}"),')
        lines.append(f"]")
        lines.append(f"")
        edges = definition.get("edges", [])
        lines.append(f"GRAPH_EDGES = [")
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'    ("{src}", "{dst}", "{etype}"),')
        lines.append(f"]")
        lines.append(f"")
        flows = definition.get("flows", {})
        lines.append(f"GRAPH_FLOWS = {{")
        for cls_name, flow_steps in flows.items():
            lines.append(f'    "{cls_name}": [')
            for step in flow_steps:
                step_type = step.get("type", "step")
                desc = step.get("desc", "")
                lines.append(f'        ("{step_type}", "{desc}"),')
            lines.append(f"    ],")
        lines.append(f"}}")
        lines.append(f"")
        categories = definition.get("categories", {})
        lines.append(f"GRAPH_CATEGORIES = {{")
        for cat, classes in categories.items():
            cls_list = ", ".join([f'"{c}"' for c in classes])
            lines.append(f'    "{cat}": [{cls_list}],')
        lines.append(f"}}")
        lines.append(f"")
        lines.append(f"GRAPH_DOMAIN_NAME = \"{name}\"")
        lines.append(f"GRAPH_DOMAIN_FILE = \"{definition['file']}\"")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (15, f"Write error: {str(e)}", 0))

    def WriteConfigData(self, definition: Dict, output_dir: str) -> Tuple[int, str, Optional[Tuple]]:
        """Write Config.py for the domain with graph data embedded"""
        name = definition["name"]
        fname = "Config_" + definition["file"].replace("dom_", "").replace(".py", ".py")
        fpath = os.path.join(output_dir, fname)
        classes = definition["classes"]
        edges = definition.get("edges", [])
        flows = definition.get("flows", {})
        categories = definition.get("categories", {})
        lines = []
        lines.append(f'#!/usr/bin/env python3')
        lines.append(f'"""')
        lines.append(f'Config for {name} domain.')
        lines.append(f'Generated by DomainEngine.')
        lines.append(f'"""')
        lines.append(f"")
        lines.append(f"DOMAIN_NAME = \"{name}\"")
        lines.append(f"DOMAIN_FILE = \"{definition['file']}\"")
        lines.append(f"DOMAIN_SUMMARY = \"{definition.get('summary', '')}\"")
        lines.append(f"")
        lines.append(f"GRAPH_CLASSES = [")
        for cls in classes:
            cls_name = cls["name"]
            methods = cls.get("methods", [])
            dispatch = ", ".join([f'"{m.lower()}"' for m in methods])
            desc = cls.get("description", f"{cls_name} component")
            lines.append(f'    ("{cls_name}", "class", [{dispatch}], "{desc}"),')
        lines.append(f"]")
        lines.append(f"")
        lines.append(f"GRAPH_EDGES = [")
        for edge in edges:
            src = edge.get("src", "")
            dst = edge.get("dst", "")
            etype = edge.get("type", "USES")
            lines.append(f'    ("{src}", "{dst}", "{etype}"),')
        lines.append(f"]")
        lines.append(f"")
        lines.append(f"GRAPH_FLOWS = {{")
        for cls_name, flow_steps in flows.items():
            lines.append(f'    "{cls_name}": [')
            for step in flow_steps:
                step_type = step.get("type", "step")
                desc = step.get("desc", "")
                lines.append(f'        ("{step_type}", "{desc}"),')
            lines.append(f"    ],")
        lines.append(f"}}")
        lines.append(f"")
        lines.append(f"GRAPH_CATEGORIES = {{")
        for cat, cat_classes in categories.items():
            cls_list = ", ".join([f'"{c}"' for c in cat_classes])
            lines.append(f'    "{cat}": [{cls_list}],')
        lines.append(f"}}")
        lines.append(f"")
        lines.append(f"GRAPH_CATEGORY_ORDER = list(GRAPH_CATEGORIES.keys())")
        lines.append(f"")
        lines.append(f"class Config:")
        lines.append(f'    """Config for {name} domain"""')
        lines.append(f"    DOMAIN_NAME = DOMAIN_NAME")
        lines.append(f"    DOMAIN_FILE = DOMAIN_FILE")
        lines.append(f"    GRAPH_CLASSES = GRAPH_CLASSES")
        lines.append(f"    GRAPH_EDGES = GRAPH_EDGES")
        lines.append(f"    GRAPH_FLOWS = GRAPH_FLOWS")
        lines.append(f"    GRAPH_CATEGORIES = GRAPH_CATEGORIES")
        lines.append(f"    GRAPH_CATEGORY_ORDER = GRAPH_CATEGORY_ORDER")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.state["generated_files"].append(fpath)
            self.state["stats"]["files"] += 1
            return (1, fpath, None)
        except Exception as e:
            return (0, None, (16, f"Write error: {str(e)}", 0))

    def GenerateAll(self, domain_name: str, output_dir: str) -> Tuple[int, Dict, Optional[Tuple]]:
        """Generate all outputs for a domain"""
        success, definition, error = self.LoadDomainDefinition(domain_name)
        if not success:
            return (0, None, error)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        self.state["output_dir"] = output_dir
        self.state["generated_files"] = []
        self.state["errors"] = []
        self.state["stats"] = {"classes": 0, "methods": 0, "edges": 0, "files": 0}
        results = {}
        builders = [
            ("python", self.WritePython),
            ("tree", self.WriteMarkdownTree),
            ("graphviz", self.WriteGraphviz),
            ("mermaid", self.WriteMermaid),
            ("symbols", self.WriteSymbolIndex),
            ("graph_data", self.WriteGraphData),
            ("config", self.WriteConfigData),
        ]
        for builder_name, builder_fn in builders:
            success, result, error = builder_fn(definition, output_dir)
            results[builder_name] = {"success": success, "path": result, "error": error}
            if not success:
                self.state["errors"].append(f"{builder_name}: {error}")
        return (1, results, None)

    def GuidedCLI(self) -> Tuple[int, Dict, Optional[Tuple]]:
        """
        Interactive guided CLI for building a new domain definition.
        Walks the user through: name, file, classes, methods, edges, categories.
        Returns the constructed definition dict.
        """
        definition = {}
        sys.stdout.write("=== Domain Engine - Guided Domain Builder ===\n")
        sys.stdout.write("\n")
        sys.stdout.write("Domain name (e.g. Web, Sql, Audio): ")
        sys.stdout.flush()
        name = sys.stdin.readline().strip()
        if not name:
            return (0, None, (20, "Domain name required", 0))
        definition["name"] = name
        sys.stdout.write("File name (e.g. dom_web.py): ")
        sys.stdout.flush()
        fname = sys.stdin.readline().strip()
        if not fname:
            fname = f"dom_{name.lower()}.py"
        definition["file"] = fname
        sys.stdout.write("Summary: ")
        sys.stdout.flush()
        summary = sys.stdin.readline().strip()
        definition["summary"] = summary
        definition["classes"] = []
        definition["edges"] = []
        definition["flows"] = {}
        definition["categories"] = {}
        sys.stdout.write("\n--- Add classes (empty name to finish) ---\n")
        while True:
            sys.stdout.write(f"\nClass #{len(definition['classes']) + 1} name: ")
            sys.stdout.flush()
            cls_name = sys.stdin.readline().strip()
            if not cls_name:
                break
            sys.stdout.write(f"  Methods for {cls_name} (comma-separated): ")
            sys.stdout.flush()
            methods_input = sys.stdin.readline().strip()
            methods = [m.strip() for m in methods_input.split(",") if m.strip()]
            sys.stdout.write(f"  Description for {cls_name}: ")
            sys.stdout.flush()
            desc = sys.stdin.readline().strip()
            cls_def = {"name": cls_name, "methods": methods}
            if desc:
                cls_def["description"] = desc
            definition["classes"].append(cls_def)
        if len(definition["classes"]) < 1:
            return (0, None, (21, "At least one class required", 0))
        sys.stdout.write("\n--- Add edges (empty src to finish) ---\n")
        while True:
            sys.stdout.write(f"\nEdge #{len(definition['edges']) + 1} source class: ")
            sys.stdout.flush()
            src = sys.stdin.readline().strip()
            if not src:
                break
            sys.stdout.write(f"  Target class: ")
            sys.stdout.flush()
            dst = sys.stdin.readline().strip()
            if not dst:
                break
            sys.stdout.write(f"  Edge type (USES, WRAPS, FEEDS, ENABLES, TRIGGERS, FALLBACK): ")
            sys.stdout.flush()
            etype = sys.stdin.readline().strip() or "USES"
            definition["edges"].append({"src": src, "dst": dst, "type": etype})
        domain_key = name.lower()
        success, save_path, error = self.SaveDomainDefinition(definition, domain_key)
        if not success:
            return (0, None, error)
        sys.stdout.write(f"\nDomain definition saved: {save_path}\n")
        sys.stdout.write(f"Classes: {len(definition['classes'])}\n")
        total_methods = sum(len(c.get("methods", [])) for c in definition["classes"])
        sys.stdout.write(f"Methods: {total_methods}\n")
        sys.stdout.write(f"Edges:   {len(definition['edges'])}\n")
        sys.stdout.write(f"\nGenerate domain files? (y/n): ")
        sys.stdout.flush()
        confirm = sys.stdin.readline().strip().lower()
        if confirm == "y":
            output_dir = os.path.dirname(self.state["definitions_dir"])
            success, results, error = self.GenerateAll(domain_key, output_dir)
            if success:
                sys.stdout.write(f"\nGenerated {len(results)} files:\n")
                for builder, info in results.items():
                    if info["success"]:
                        sys.stdout.write(f"  [OK]  {builder:12s} -> {info['path']}\n")
                    else:
                        sys.stdout.write(f"  [FAIL] {builder:12s} -> {info['error']}\n")
            else:
                return (0, None, error)
        return (1, definition, None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
        """
        Dispatch commands for DomainEngine.

        Commands:
            generate: Generate all outputs (params: domain, output_dir)
            list: List available domain definitions
            load: Load a domain definition (params: domain)
            save: Save a domain definition (params: definition, domain)
            guided: Run interactive guided CLI builder
            build_python: Build Python file only (params: domain, output_dir)
            build_tree: Build markdown tree only (params: domain, output_dir)
            build_graphviz: Build graphviz dot only (params: domain, output_dir)
            build_mermaid: Build mermaid graph only (params: domain, output_dir)
            build_symbols: Build symbol index only (params: domain, output_dir)
            build_graph_data: Build graph data file only (params: domain, output_dir)
            build_config: Build Config.py only (params: domain, output_dir)
            read_state: Return engine state
            set_config: Update engine config
        """
        if params is None:
            params = {}
        if command == "generate":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (1, "Missing required param: domain", 0))
            return self.GenerateAll(domain, output_dir)
        elif command == "list":
            return self.ListDomains()
        elif command == "load":
            domain = params.get("domain")
            if not domain:
                return (0, None, (2, "Missing required param: domain", 0))
            return self.LoadDomainDefinition(domain)
        elif command == "save":
            definition = params.get("definition")
            domain = params.get("domain")
            if not definition or not domain:
                return (0, None, (3, "Missing required params: definition, domain", 0))
            return self.SaveDomainDefinition(definition, domain)
        elif command == "guided":
            return self.GuidedCLI()
        elif command == "build_python":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (4, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WritePython(definition, output_dir)
        elif command == "build_tree":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (5, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteMarkdownTree(definition, output_dir)
        elif command == "build_graphviz":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (6, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteGraphviz(definition, output_dir)
        elif command == "build_mermaid":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (7, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteMermaid(definition, output_dir)
        elif command == "build_symbols":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (8, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteSymbolIndex(definition, output_dir)
        elif command == "build_graph_data":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (9, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteGraphData(definition, output_dir)
        elif command == "build_config":
            domain = params.get("domain")
            output_dir = params.get("output_dir", ".")
            if not domain:
                return (0, None, (10, "Missing required param: domain", 0))
            success, definition, error = self.LoadDomainDefinition(domain)
            if not success:
                return (0, None, error)
            return self.WriteConfigData(definition, output_dir)
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.SetConfig(params)
        else:
            return (0, None, (99, f"Unknown command: {command}", 0))


def Main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        sys.stdout.write("Usage:\n")
        sys.stdout.write("  python create_domain.py <domain> [output_dir]   Generate domain files\n")
        sys.stdout.write("  python create_domain.py list                    List available domains\n")
        sys.stdout.write("  python create_domain.py guided                  Interactive domain builder\n")
        sys.stdout.write("  python create_domain.py new <name>              Create blank domain definition\n")
        sys.stdout.write("\n")
        sys.stdout.write("Domain definitions live in: domain_definitions/*.json\n")
        sys.stdout.write("Each definition generates 7 files:\n")
        sys.stdout.write("  dom_*.py            Python skeleton (nested classes + Run dispatch)\n")
        sys.stdout.write("  dom_*_tree.md       Markdown class tree\n")
        sys.stdout.write("  dom_*_graph.dot     Graphviz graph\n")
        sys.stdout.write("  dom_*_graph.mmd     Mermaid graph\n")
        sys.stdout.write("  dom_*_symbols.json  Symbol index\n")
        sys.stdout.write("  dom_*_graph_data.py Graph data (for 8 graph viewers)\n")
        sys.stdout.write("  Config_*.py         Config with graph data\n")
        sys.exit(1)
    arg = sys.argv[1].lower()
    engine = DomainEngine()
    if arg == "list":
        success, domains, error = engine.Run("list")
        if success:
            if not domains:
                sys.stdout.write("No domain definitions found.\n")
                sys.stdout.write(f"Create one with: python create_domain.py guided\n")
                sys.stdout.write(f"Or add JSON files to: {engine.state['definitions_dir']}/\n")
            else:
                sys.stdout.write("Available domains:\n")
                for d in domains:
                    success, defn, _ = engine.Run("load", {"domain": d})
                    if success:
                        cls_count = len(defn["classes"])
                        method_count = sum(len(c.get("methods", [])) for c in defn["classes"])
                        edge_count = len(defn.get("edges", []))
                        sys.stdout.write(f"  {d:15s}  {defn['name']:10s}  {cls_count:3d} classes  {method_count:3d} methods  {edge_count:3d} edges  {defn['file']}\n")
        else:
            sys.stdout.write(f"Error: {error}\n")
        sys.exit(0)
    elif arg == "guided":
        success, definition, error = engine.Run("guided")
        if not success:
            sys.stdout.write(f"Error: {error}\n")
            sys.exit(1)
        sys.exit(0)
    elif arg == "new":
        if len(sys.argv) < 3:
            sys.stdout.write("Usage: python create_domain.py new <name>\n")
            sys.exit(1)
        domain_name = sys.argv[2].lower()
        blank = {
            "name": domain_name.capitalize(),
            "file": f"dom_{domain_name}.py",
            "summary": f"{domain_name.capitalize()} domain",
            "classes": [
                {"name": "Component", "methods": ["Init", "Run", "Status"]}
            ],
            "edges": [],
            "flows": {},
            "categories": {},
        }
        success, path, error = engine.Run("save", {"definition": blank, "domain": domain_name})
        if success:
            sys.stdout.write(f"Created blank definition: {path}\n")
            sys.stdout.write(f"Edit it, then run: python create_domain.py {domain_name}\n")
        else:
            sys.stdout.write(f"Error: {error}\n")
            sys.exit(1)
        sys.exit(0)
    else:
        domain = arg
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        success, results, error = engine.Run("generate", {"domain": domain, "output_dir": output_dir})
        if not success:
            sys.stdout.write(f"Error: {error}\n")
            sys.exit(1)
        sys.stdout.write(f"Domain: {domain}\n")
        sys.stdout.write(f"Output: {output_dir}\n")
        sys.stdout.write(f"\n")
        for builder, info in results.items():
            if info["success"]:
                sys.stdout.write(f"  [OK]   {builder:12s} -> {info['path']}\n")
            else:
                sys.stdout.write(f"  [FAIL] {builder:12s} -> {info['error']}\n")
        stats = engine.state["stats"]
        sys.stdout.write(f"\n")
        sys.stdout.write(f"Classes: {stats['classes']}\n")
        sys.stdout.write(f"Methods: {stats['methods']}\n")
        sys.stdout.write(f"Edges:   {stats['edges']}\n")
        sys.stdout.write(f"Files:   {stats['files']}\n")
        sys.exit(0)


if __name__ == "__main__":
    Main()
