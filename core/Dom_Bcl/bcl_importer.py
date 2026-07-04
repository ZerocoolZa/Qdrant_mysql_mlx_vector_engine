#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_importer.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Importer — mirror of IRExporter, imports IR from SQLite back into BCLNode AST"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_importer.py" domain="BCL" authority="BCLImporter"}
# [@SUMMARY]{summary="BCL Importer: reads IR nodes from SQLite, reconstructs BCLNode AST tree. Round-trip partner to IRExporter."}
# [@CLASS]{class="BCLImporter" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="import_sqlite" type="command"}
# [@METHOD]{method="import_sqlite_bcl" type="command"}
# [@METHOD]{method="rebuild_tree" type="command"}
# [@METHOD]{method="parse_bcl_block" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3

from bcl_parser import BCLNode, BCLParser
from bcl_lexer import BCLTokenizer


class BCLImporter:
    """Import IR from SQLite back into BCLNode AST tree."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "last_import": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "import_sqlite":
            return self.ImportSqlite(params)
        elif command == "import_sqlite_bcl":
            return self.ImportSqliteBcl(params)
        elif command == "rebuild_tree":
            return self.RebuildTree(params)
        elif command == "parse_bcl_block":
            return self.ParseBclBlock(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def ImportSqlite(self, params):
        db_path = self._p(params, "db_path")
        if db_path is None:
            return (0, None, ("MISSING_PARAM", "db_path required", 0))
        if not os.path.exists(db_path):
            return (0, None, ("FILE_NOT_FOUND", str(db_path), 0))
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, type, parent, filepath, bcl FROM ir_nodes")
        rows = cur.fetchall()
        cur.execute("SELECT filepath, file_id, blocks, classes, methods, violations FROM ir_files")
        file_rows = cur.fetchall()
        conn.close()
        self.state["last_import"] = {"db_path": db_path, "nodes": len(rows), "files": len(file_rows)}
        return (1, {"nodes": rows, "files": file_rows, "node_count": len(rows), "file_count": len(file_rows)}, None)

    def ImportSqliteBcl(self, params):
        db_path = self._p(params, "db_path")
        if db_path is None:
            return (0, None, ("MISSING_PARAM", "db_path required", 0))
        import_result = self.ImportSqlite({"db_path": db_path})
        if import_result[0] == 0:
            return import_result
        data = import_result[1]
        tree_result = self.RebuildTree({"nodes": data["nodes"]})
        if tree_result[0] == 0:
            return tree_result
        root = tree_result[1]
        self.state["last_import"] = {"db_path": db_path, "nodes": data["node_count"], "files": data["file_count"], "root": root}
        return (1, {"root": root, "node_count": data["node_count"], "file_count": data["file_count"]}, None)

    def RebuildTree(self, params):
        nodes = self._p(params, "nodes")
        if nodes is None:
            return (0, None, ("MISSING_PARAM", "nodes required", 0))
        root = BCLNode("root")
        node_map = {}
        pending = []
        for row in nodes:
            node_id = row[0]
            node_type = row[1]
            parent_id = row[2]
            bcl_text = row[4]
            parse_result = self.ParseBclBlock({"bcl": bcl_text, "node_id": node_id, "node_type": node_type})
            if parse_result[0] == 1 and parse_result[1] is not None:
                bcl_node = parse_result[1]
                node_map[node_id] = {"node": bcl_node, "parent_id": parent_id}
            else:
                pending.append({"id": node_id, "parent_id": parent_id, "bcl": bcl_text})
        for node_id, info in node_map.items():
            parent_id = info["parent_id"]
            bcl_node = info["node"]
            if parent_id and parent_id in node_map:
                parent_node = node_map[parent_id]["node"]
                bcl_node.state["parent"] = parent_node
                parent_node.state["children"].append(bcl_node)
            else:
                bcl_node.state["parent"] = root
                root.state["children"].append(bcl_node)
        return (1, root, None)

    def ParseBclBlock(self, params):
        bcl_text = self._p(params, "bcl")
        node_id = self._p(params, "node_id", "")
        node_type = self._p(params, "node_type", "")
        if bcl_text is None:
            return (0, None, ("MISSING_PARAM", "bcl required", 0))
        tokenizer = BCLTokenizer()
        tok_result = tokenizer.Run("tokenize", {"text": bcl_text})
        if tok_result[0] == 0:
            return (0, None, ("TOKENIZE_ERROR", str(tok_result[2]), 0))
        tokens = tok_result[1]["tokens"]
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tokens})
        if parse_result[0] == 0:
            return (0, None, ("PARSE_ERROR", str(parse_result[2]), 0))
        root = parse_result[1]["root"]
        if root.state["children"]:
            return (1, root.state["children"][0], None)
        return (1, root, None)
