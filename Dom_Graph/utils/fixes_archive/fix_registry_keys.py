#!/usr/bin/env python3
"""Fix FILE_REGISTRY in Config.py — revert DomGraph* keys back to simple names."""
from pathlib import Path

p = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/Config.py")
content = p.read_text()
lines = content.split("\n")
for i, line in enumerate(lines):
    if line.startswith("FILE_REGISTRY = "):
        replacements = [
            ("'DomGraphRuntime'", "'RuntimeTwinPopulate'"),
            ("'DomGraphEngineV2'", "'GraphEngineV2'"),
            ("'DomGraphPlan'", "'PlanGraph'"),
            ("'DomGraphSpec'", "'SpecGraph'"),
            ("'DomGraphFlow'", "'SpecFlow'"),
            ("'DomGraphLifecycle'", "'LifecycleGraph'"),
            ("'DomGraphDep'", "'DepGraph'"),
            ("'DomGraphError'", "'ErrorGraph'"),
            ("'DomGraphOrch'", "'OrchGraph'"),
            ("'DomGraphGap'", "'GapGraph'"),
            ("'DomGraphAgent'", "'AgentGraph'"),
            ("'DomGraphBoot'", "'BootGraph'"),
            ("'DomGraphCode'", "'CodeGraph'"),
            ("'DomGraphViewer'", "'GraphViewer'"),
            ("'DomGraphGui'", "'DbArchitectureGui'"),
            ("'DomGraphIngest'", "'IngestGraphFromMysql'"),
        ]
        for old, new in replacements:
            line = line.replace(old, new)
        lines[i] = line
        print(f"Fixed line {i+1}")
        break

p.write_text("\n".join(lines))
print("FILE_REGISTRY updated")
