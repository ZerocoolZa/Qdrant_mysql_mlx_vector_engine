#!/usr/bin/env python3
"""Fix FILE_REGISTRY in Config.py with new Dom_Graph names."""
from pathlib import Path

p = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Config.py")
content = p.read_text()

# Find the FILE_REGISTRY line
lines = content.split("\n")
for i, line in enumerate(lines):
    if line.startswith("FILE_REGISTRY = "):
        new_line = line
        # Do longest-first replacements to avoid partial matches
        replacements = [
            ("RuntimeTwinPopulate.py", "Dom_Graph_Runtime.py"),
            ("RuntimeTwinPopulate", "DomGraphRuntime"),
            ("DomGraphEngine.py", "Dom_Graph_Engine.py"),
            ("GraphEngineV2.py", "Dom_Graph_EngineV2.py"),
            ("GraphEngineV2", "DomGraphEngineV2"),
            ("PlanGraph.py", "Dom_Graph_Plan.py"),
            ("PlanGraph", "DomGraphPlan"),
            ("SpecGraph.py", "Dom_Graph_Spec.py"),
            ("SpecGraph", "DomGraphSpec"),
            ("SpecFlow.py", "Dom_Graph_Flow.py"),
            ("SpecFlow", "DomGraphFlow"),
            ("LifecycleGraph.py", "Dom_Graph_Lifecycle.py"),
            ("LifecycleGraph", "DomGraphLifecycle"),
            ("DepGraph.py", "Dom_Graph_Dep.py"),
            ("DepGraph", "DomGraphDep"),
            ("ErrorGraph.py", "Dom_Graph_Error.py"),
            ("ErrorGraph", "DomGraphError"),
            ("OrchGraph.py", "Dom_Graph_Orch.py"),
            ("OrchGraph", "DomGraphOrch"),
            ("GapGraph.py", "Dom_Graph_Gap.py"),
            ("GapGraph", "DomGraphGap"),
            ("EfiAgentGraph.py", "Dom_Graph_Agent.py"),
            ("EfiAgentGraph", "DomGraphAgent"),
            ("EfiBootGraph.py", "Dom_Graph_Boot.py"),
            ("EfiBootGraph", "DomGraphBoot"),
            ("EfiCodeGraph.py", "Dom_Graph_Code.py"),
            ("EfiCodeGraph", "DomGraphCode"),
            ("EfiGraphViewer.py", "Dom_Graph_Viewer.py"),
            ("EfiGraphViewer", "DomGraphViewer"),
            ("DbArchitectureGui.py", "Dom_Graph_Gui.py"),
            ("DbArchitectureGui", "DomGraphGui"),
            ("IngestGraphFromMysql.py", "Dom_Graph_Ingest.py"),
            ("IngestGraphFromMysql", "DomGraphIngest"),
        ]
        for old, new in replacements:
            new_line = new_line.replace(old, new)
        lines[i] = new_line
        print(f"Fixed line {i+1}")
        break

p.write_text("\n".join(lines), encoding="utf-8")
print("Config.py FILE_REGISTRY updated")
