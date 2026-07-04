#!/usr/bin/env python3
"""
stst.py

Pipeline:
    populate

Scans a project, discovers Python classes and methods,
and prints a registry.
"""

from pathlib import Path
import ast
import argparse


class RegistryPopulator:

    def __init__(self):
        self.registry = []

    def Run(self, command, params=None):

        dispatch = {
            "populate": self._populate
        }

        if command not in dispatch:
            raise ValueError(f"Unknown command: {command}")

        return dispatch[command](params or {})

    def _populate(self, params):

        registry = self._scan_project(
            params["root"]
        )

        self._index_registry()

        self.objects = self._build_objects()

        self._lookup = self._build_lookup(
            self.objects
        )

        self._finalize_registry()

        self._print_summary()

        return {
            "summary": self._summary(),
            "registry": registry,
            "objects": self.objects
        }

    def _scan_file(self, file):

        try:
            source = file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            return

        module = {
            "file": str(file),
            "classes": []
        }

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                module["classes"].append(self._scan_class(node))

        if module["classes"]:
            self.registry.append(module)

    def _scan_class(self, node):

        cls = {
            "name": node.name,
            "doc": ast.get_docstring(node),
            "methods": []
        }

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                cls["methods"].append(self._scan_method(item))

        return cls

    def _scan_method(self, node):

        return {
            "name": node.name,
            "args": [a.arg for a in node.args.args],
            "doc": ast.get_docstring(node)
        }


def main():

    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("populate")
    p.add_argument("--root", required=True)

    args = parser.parse_args()

    if args.command != "populate":
        parser.print_help()
        return

    engine = RegistryPopulator()

    result = engine.Run(
        "populate",
        {
            "root": args.root
        }
    )

    for module in result:

        print(module["file"])

        for cls in module["classes"]:

            print("  CLASS:", cls["name"])

            for method in cls["methods"]:
                print("      ", method["name"])


    def _scan_imports(self, tree):
        """Return imported modules."""
        imports = []

        import ast

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.append(n.name)

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                imports.append(mod)

        return sorted(set(imports))


    def _scan_globals(self, tree):
        """Return module-level constants."""
        import ast

        globals_ = {}

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals_[target.id] = ast.unparse(node.value)

        return globals_


    def _scan_tags(self, source):
        """Extract #[@...] tags."""
        tags = []

        for line in source.splitlines():
            line = line.strip()
            if line.startswith("#[@"):
                tags.append(line)

        return tags


    def _scan_sql(self, tree):
        """Locate likely SQL strings inside the AST."""
        import ast
        sql = []
        KEYWORDS = (
            "SELECT ",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "CREATE ",
            "ALTER ",
            "DROP ",
            "TRUNCATE ",
            "CALL ",
            "REPLACE "
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    s = node.value.strip()
                    upper = s.upper()
                    if upper.startswith(KEYWORDS):
                        sql.append(
                            {
                                "type": upper.split()[0],
                                "sql": s
                            }
                        )
        return sql
    def _scan_calls(self, tree):
        """Locate function and method calls."""
        import ast
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
        return sorted(set(calls))
    def _scan_docstrings(self, tree):
        """Return every class/function docstring."""
        import ast
        docs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                if doc:
                    docs.append(
                        {
                            "name": getattr(node, "name", ""),
                            "doc": doc
                        }
                    )
        return docs
    def _scan_statistics(self, source):
        """Basic file statistics."""
        import hashlib
        return {
            "lines": len(source.splitlines()),
            "characters": len(source),
            "sha256": hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest()
        }


    def _scan_classes(self, tree):
        """Return complete class metadata."""

        import ast

        classes = []

        for node in tree.body:

            if not isinstance(node, ast.ClassDef):
                continue

            cls = {
                "name": node.name,
                "bases": [],
                "decorators": [],
                "doc": ast.get_docstring(node),
                "methods": [],
                "properties": []
            }

            for base in node.bases:
                try:
                    cls["bases"].append(ast.unparse(base))
                except Exception:
                    pass

            for dec in node.decorator_list:
                try:
                    cls["decorators"].append(ast.unparse(dec))
                except Exception:
                    pass

            for item in node.body:

                if isinstance(item, ast.FunctionDef):

                    cls["methods"].append(
                        {
                            "name": item.name,
                            "args": [a.arg for a in item.args.args],
                            "returns": ast.unparse(item.returns) if item.returns else None,
                            "doc": ast.get_docstring(item),
                            "line": item.lineno
                        }
                    )

                elif isinstance(item, ast.Assign):

                    for target in item.targets:

                        if isinstance(target, ast.Name):

                            cls["properties"].append(target.id)

            classes.append(cls)

        return classes


    def _build_graph(self, classes):
        """Build a simple class/method graph."""

        graph = []

        for cls in classes:

            graph.append(
                {
                    "type": "CLASS",
                    "id": cls["name"]
                }
            )

            for method in cls["methods"]:

                graph.append(
                    {
                        "type": "METHOD",
                        "id": f'{cls["name"]}.{method["name"]}',
                        "parent": cls["name"]
                    }
                )

        return graph


    def _build_registry(self, module):
        """Convert scanned module into registry object."""

        return {
            "file": module["file"],
            "classes": module.get("classes", []),
            "graph": self._build_graph(module.get("classes", [])),
            "version": 1
        }



    def _scan_comments(self, source):
        """Extract TODO/FIXME and normal comments."""

        comments = []

        for lineno, line in enumerate(source.splitlines(), 1):

            s = line.strip()

            if not s.startswith("#"):
                continue

            kind = "COMMENT"

            if "TODO" in s.upper():
                kind = "TODO"

            elif "FIXME" in s.upper():
                kind = "FIXME"

            elif s.startswith("#[@"):
                kind = "TAG"

            comments.append({
                "line": lineno,
                "type": kind,
                "text": s
            })

        return comments


    def _scan_functions(self, tree):
        """Return every top-level function."""

        import ast

        functions = []

        for node in tree.body:

            if not isinstance(node, ast.FunctionDef):
                continue

            functions.append({

                "name": node.name,

                "args": [a.arg for a in node.args.args],

                "returns":
                    ast.unparse(node.returns)
                    if node.returns
                    else None,

                "doc":
                    ast.get_docstring(node),

                "line":
                    node.lineno

            })

        return functions


    def _scan_constants(self, tree):
        """Extract ALL_CAPS module constants."""

        import ast

        constants = []

        for node in tree.body:

            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:

                if not isinstance(target, ast.Name):
                    continue

                if not target.id.isupper():
                    continue

                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    value = None

                constants.append({

                    "name": target.id,

                    "value": value

                })

        return constants


    def _scan_file(self, file):

        try:

            source = file.read_text(encoding="utf-8")

            tree = ast.parse(source)

        except Exception:

            return

        module = {

            "file": str(file),

            "classes": self._scan_classes(tree),

            "functions": self._scan_functions(tree),

            "constants": self._scan_constants(tree),

            "imports": self._scan_imports(tree),

            "comments": self._scan_comments(source),

            "tags": self._scan_tags(source),

            "sql": self._scan_sql(tree),

            "calls": self._scan_calls(tree),

            "docs": self._scan_docstrings(tree),

            "stats": self._scan_statistics(source)

        }

        self.registry.append(
            self._build_registry(module)
        )



    def _discover_python_files(self, root):
        """Return every Python source file."""

        from pathlib import Path

        root = Path(root)

        files = []

        for file in root.rglob("*.py"):

            if "__pycache__" in file.parts:
                continue

            files.append(file)

        files.sort()

        return files


    def _scan_project(self, root):
        """Scan an entire project."""

        self.registry = []

        files = self._discover_python_files(root)

        for file in files:

            self._scan_file(file)

        return self.registry


    def _index_registry(self):
        """Assign IDs to discovered objects."""

        next_id = 1

        for module in self.registry:

            module["id"] = next_id

            next_id += 1

            for cls in module.get("classes", []):

                cls["id"] = next_id

                next_id += 1

                for method in cls.get("methods", []):

                    method["id"] = next_id

                    next_id += 1


    def _summary(self):
        """Generate project summary."""

        summary = {

            "files": len(self.registry),

            "classes": 0,

            "methods": 0,

            "functions": 0,

            "sql": 0

        }

        for module in self.registry:

            summary["functions"] += len(
                module.get("functions", [])
            )

            summary["sql"] += len(
                module.get("sql", [])
            )

            for cls in module.get("classes", []):

                summary["classes"] += 1

                summary["methods"] += len(
                    cls.get("methods", [])
                )

        return summary




    def _build_objects(self):
        """Convert scanned registry into executable registry objects."""

        objects = []

        for module in self.registry:

            objects.append({
                "objectType": "FILE",
                "name": module["file"],
                "payload": module
            })

            for cls in module.get("classes", []):

                objects.append({
                    "objectType": "CLASS",
                    "name": cls["name"],
                    "parent": module["file"],
                    "payload": cls
                })

                for method in cls.get("methods", []):

                    objects.append({
                        "objectType": "METHOD",
                        "name": method["name"],
                        "parent": cls["name"],
                        "payload": method
                    })

            for fn in module.get("functions", []):

                objects.append({
                    "objectType": "FUNCTION",
                    "name": fn["name"],
                    "parent": module["file"],
                    "payload": fn
                })

            for sql in module.get("sql", []):

                objects.append({
                    "objectType": "SQL",
                    "name": sql["type"],
                    "parent": module["file"],
                    "payload": sql
                })

        return objects


    def _build_lookup(self, objects):
        """Build fast object lookup."""

        lookup = {}

        for obj in objects:

            key = f'{obj["objectType"]}:{obj["name"]}'

            lookup[key] = obj

        return lookup


    def _find_object(self, object_type, name):
        """Find a registry object."""

        if not hasattr(self, "_lookup"):
            return None

        return self._lookup.get(f"{object_type}:{name}")


    def _print_summary(self):

        s = self._summary()

        print()

        print("=" * 60)
        print("PROJECT SUMMARY")
        print("=" * 60)

        print(f'Files     : {s["files"]}')
        print(f'Classes   : {s["classes"]}')
        print(f'Methods   : {s["methods"]}')
        print(f'Functions : {s["functions"]}')
        print(f'SQL       : {s["sql"]}')

        print("=" * 60)



    def _discover_relationships(self):
        """Build relationships between discovered objects."""

        relationships = []

        for module in self.registry:

            file_name = module["file"]

            for cls in module.get("classes", []):

                relationships.append({
                    "type": "FILE_CLASS",
                    "from": file_name,
                    "to": cls["name"]
                })

                for method in cls.get("methods", []):

                    relationships.append({
                        "type": "CLASS_METHOD",
                        "from": cls["name"],
                        "to": method["name"]
                    })

            for fn in module.get("functions", []):

                relationships.append({
                    "type": "FILE_FUNCTION",
                    "from": file_name,
                    "to": fn["name"]
                })

        return relationships


    def _build_call_graph(self):
        """Build a simple project call graph."""

        graph = {}

        for module in self.registry:

            graph[module["file"]] = module.get("calls", [])

        return graph


    def _build_statistics(self):

        stats = {

            "files": len(self.registry),

            "classes": 0,

            "methods": 0,

            "functions": 0,

            "sql": 0,

            "comments": 0,

            "tags": 0

        }

        for module in self.registry:

            stats["functions"] += len(module.get("functions", []))
            stats["sql"] += len(module.get("sql", []))
            stats["comments"] += len(module.get("comments", []))
            stats["tags"] += len(module.get("tags", []))

            for cls in module.get("classes", []):

                stats["classes"] += 1
                stats["methods"] += len(cls.get("methods", []))

        return stats


    def _finalize_registry(self):

        self.relationships = self._discover_relationships()

        self.call_graph = self._build_call_graph()

        self.statistics = self._build_statistics()



    def _serialize_registry(self):
        """Serialize the complete registry."""

        import json

        return json.dumps(
            {
                "registry": self.registry,
                "objects": getattr(self, "objects", []),
                "relationships": getattr(self, "relationships", []),
                "call_graph": getattr(self, "call_graph", {}),
                "statistics": getattr(self, "statistics", {})
            },
            indent=2,
            default=str
        )


    def _compress_registry(self):

        """Compress the registry payload."""

        import zlib

        payload = self._serialize_registry().encode("utf-8")

        compressed = zlib.compress(payload, level=9)

        return compressed


    def _decompress_registry(self, payload):

        """Restore compressed registry."""

        import zlib
        import json

        return json.loads(
            zlib.decompress(payload).decode("utf-8")
        )


    def _checksum(self, payload):

        """SHA256 checksum."""

        import hashlib

        return hashlib.sha256(payload).hexdigest()


    def _build_package(self):

        """Build distributable package."""

        payload = self._compress_registry()

        return {

            "compression": "zlib",

            "size_raw": len(
                self._serialize_registry().encode("utf-8")
            ),

            "size_compressed": len(payload),

            "checksum": self._checksum(payload),

            "payload": payload

        }


    def _save_package(self, filename):

        """Save compressed package."""

        from pathlib import Path

        pkg = self._build_package()

        Path(filename).write_bytes(pkg["payload"])

        return pkg



    ###########################################################################
    # COMPRESSED OBJECT ENGINE
    ###########################################################################

    def RegisterObject(
        self,
        tag,
        payload,
        metadata=None
    ):
        """
        Register a compressed object.

        Example tags

            TABLE_ENGINE
            CRUD_INSERT
            CRUD_UPDATE
            CRUD_DELETE
            CRUD_SELECT
            CREATE_TABLE
            DROP_TABLE
            INDEX_ENGINE
            GRAPH
            BCL
            BCLIR
            LAW
            EXPLANATION
            EXECUTION_PLAN
        """

        if not hasattr(self, "_objects"):
            self._objects = {}

        obj = {

            "tag": tag,

            "metadata": metadata or {},

            "compressed": self._compress(payload),

            "raw_size": len(payload.encode("utf8")),

            "checksum": self._checksum_bytes(
                payload.encode("utf8")
            )

        }

        self._objects[tag] = obj

        return obj


    def GetObject(self, tag):

        if not hasattr(self, "_objects"):
            return None

        return self._objects.get(tag)


    def GetPayload(self, tag):

        obj = self.GetObject(tag)

        if obj is None:
            return None

        return self._decompress(
            obj["compressed"]
        )


    def ExecuteObject(
        self,
        tag,
        parameters=None,
        connection=None
    ):
        """
        Decompress SQL and execute.

        Parameters replace %s placeholders.
        """

        sql = self.GetPayload(tag)

        if sql is None:
            raise ValueError(tag)

        cursor = connection.cursor()

        cursor.execute(
            sql,
            parameters or ()
        )

        try:
            result = cursor.fetchall()
        except Exception:
            result = None

        return result


    def _compress(self, text):

        import zstandard as zstd
        from PlfCompressor import PlfCompressor

        plf = PlfCompressor()
        domain_packed = plf.compress(text)

        c = zstd.ZstdCompressor(level=15)

        return c.compress(domain_packed)


    def _decompress(self, blob):

        import zstandard as zstd
        from PlfCompressor import PlfCompressor

        d = zstd.ZstdDecompressor()

        zstd_out = d.decompress(blob)

        plf = PlfCompressor()

        return plf.decompress(zstd_out)


    def _checksum_bytes(self, data):

        import hashlib

        return hashlib.sha256(data).hexdigest()



##############################################################################
# TEMPLATE / PREPARED STATEMENT ENGINE
##############################################################################

    def RegisterTemplate(
        self,
        tag,
        sql,
        description="",
        parameters=None,
        returns="",
        laws=None,
        graph="",
        bcl="",
        bclir=""
    ):
        """
        Register a reusable SQL template.

        Everything about the statement is stored together.
        """

        template = {

            "tag": tag,

            "description": description,

            "sql": sql,

            "parameters": parameters or [],

            "returns": returns,

            "laws": laws or [],

            "graph": graph,

            "bcl": bcl,

            "bclir": bclir

        }

        import json

        self.RegisterObject(

            tag,

            json.dumps(
                template,
                ensure_ascii=False,
                separators=(",", ":")
            )

        )

        return template


    def ExecuteTemplate(
        self,
        tag,
        values=None,
        connection=None
    ):
        """
        Execute a registered template.
        """

        import json

        template = json.loads(
            self.GetPayload(tag)
        )

        sql = template["sql"]

        cursor = connection.cursor()

        cursor.execute(
            sql,
            values or ()
        )

        try:
            rows = cursor.fetchall()

        except Exception:

            rows = None

        return {

            "tag": tag,

            "rows": rows,

            "template": template

        }


    def ListTemplates(self):

        if not hasattr(self, "_objects"):

            return []

        return sorted(self._objects.keys())


    def ExportTemplates(self):

        import json

        export = {}

        for tag in self.ListTemplates():

            export[tag] = json.loads(
                self.GetPayload(tag)
            )

        return export


    def ImportTemplates(
        self,
        templates
    ):

        for tag, obj in templates.items():

            self.RegisterTemplate(

                tag=tag,

                sql=obj.get("sql",""),

                description=obj.get("description",""),

                parameters=obj.get("parameters",[]),

                returns=obj.get("returns",""),

                laws=obj.get("laws",[]),

                graph=obj.get("graph",""),

                bcl=obj.get("bcl",""),

                bclir=obj.get("bclir","")

            )



if __name__ == "__main__":
    main()
