#[@GHOST]
#[@VBSTYLE]
#[@FILEID] PlfIrCompiler.py
#[@SUMMARY] BCL → BCLIR → PLF IR compiler — converts BCL spec into IR opcodes for the PLF container
#[@CLASS] PlfIrCompiler
#[@METHOD] Run
#[@DATE] 2026-07-04
#[@AUTHOR] Wayne / Cascade
#[@SESSION] CHECKPOINT-VEF-2
#[@CONTEXT] Stage 2 of VEF — BCL parser, BCLIR serializer, IR opcode generator

"""
PLF IR Compiler — BCL → BCLIR → PLF IR → Bytecode

Pipeline:
    BCL (human-readable spec)
      ↓ BclParser
    BCLIR (compact serialized form)
      ↓ BclirSerializer
    PLF IR (typed opcode stream)
      ↓ IrCompiler
    Bytecode (compact binary)
      ↓ PlfContainer
    .plf file

BCL format:
    [@PLF]{
        VERSION(1)
        OBJECT{
            ID(U32) TYPE(U8) FLAGS(U8) ...
        }
    }

BCLIR format:
    PLF(V1 O(ID U32 TY U8 FL U8 ...))

IR Opcodes:
    LOAD_SELF    0x01    LOAD_ATTR    0x02    LOAD_CONST   0x03
    STORE        0x04    PUSH         0x05    POP          0x06
    CALL         0x07    RETURN       0x08    JUMP         0x09
    JUMP_FALSE   0x0A    COMPARE_EQ   0x0B    COMPARE_GT   0x0C
    COMPARE_LT   0x0D    END          0x0E    SQL_SELECT   0x10
    SQL_INSERT   0x11    SQL_UPDATE   0x12    SQL_DELETE   0x13
    SQL_CREATE   0x14    TABLE_REF    0x15    COLUMN_REF   0x16
    COLUMN_ALL   0x17    WHERE_EQ     0x18    PARAM        0x19
    NODE         0x20    EDGE         0x21    DEPENDS      0x22
    CALLS        0x23    REFERENCES   0x24
"""

import struct
import re
import io

OPCODES = {
    "LOAD_SELF":    0x01, "LOAD_ATTR":    0x02, "LOAD_CONST":   0x03,
    "STORE":        0x04, "PUSH":         0x05, "POP":          0x06,
    "CALL":         0x07, "RETURN":       0x08, "JUMP":         0x09,
    "JUMP_FALSE":   0x0A, "COMPARE_EQ":   0x0B, "COMPARE_GT":   0x0C,
    "COMPARE_LT":   0x0D, "END":          0x0E,
    "SQL_SELECT":   0x10, "SQL_INSERT":   0x11, "SQL_UPDATE":   0x12,
    "SQL_DELETE":   0x13, "SQL_CREATE":   0x14, "TABLE_REF":    0x15,
    "COLUMN_REF":   0x16, "COLUMN_ALL":   0x17, "WHERE_EQ":     0x18,
    "PARAM":        0x19,
    "NODE":         0x20, "EDGE":         0x21, "DEPENDS":      0x22,
    "CALLS":        0x23, "REFERENCES":   0x24,
}

OPCODE_NAMES = {v: k for k, v in OPCODES.items()}

TYPE_MAP = {
    "CLASS": 0x01, "METHOD": 0x02, "FUNCTION": 0x03,
    "SQL": 0x04, "GRAPH": 0x05, "BCL": 0x06, "BCLIR": 0x07,
    "LAW": 0x08, "COMMENT": 0x09, "README": 0x0A, "DOCSTRING": 0x0B,
    "EXAMPLE": 0x0C, "EXECUTIONPLAN": 0x0D, "TABLE": 0x0E,
    "CONFIG": 0x14, "RESOURCE": 0x15, "RAW": 0xFF,
}

SQL_OPS = {
    "CREATE": 0x14, "SELECT": 0x10, "INSERT": 0x11,
    "UPDATE": 0x12, "DELETE": 0x13,
}


class BclNode:
    """A parsed BCL node — container with children and values."""

    def __init__(self, tag=None):
        self.tag = tag
        self.children = []
        self.values = []
        self.attrs = {}

    def add_child(self, node):
        self.children.append(node)

    def add_value(self, value):
        self.values.append(value)

    def find(self, tag):
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def find_all(self, tag):
        return [c for c in self.children if c.tag == tag]


class BclParser:
    """Parse BCL text into a tree of BclNode objects."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"text": "", "pos": 0, "root": None}

    def Run(self, command, params=None):
        dispatch = {"parse": self._parse, "tokens": self._tokens}
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state.update(config)
        return (1, {"state": self.state}, None)

    def _parse(self, params):
        text = params.get("text", "")
        self.state["text"] = text
        self.state["pos"] = 0
        try:
            root = self._parse_container()
            self.state["root"] = root
            return (1, {"root": root, "tag": root.tag if root else None}, None)
        except Exception as e:
            return (0, None, ("PARSE_ERROR", str(e), 0))

    def _tokens(self, params):
        text = params.get("text", "")
        self.state["text"] = text
        self.state["pos"] = 0
        tokens = []
        try:
            root = self._parse_container()
            self._collect_tokens(root, tokens)
        except Exception:
            pass
        return (1, {"tokens": tokens}, None)

    def _collect_tokens(self, node, out):
        if node.tag:
            out.append(("CONTAINER", node.tag))
        for v in node.values:
            out.append(("VALUE", v))
        for c in node.children:
            self._collect_tokens(c, out)

    def _parse_container(self):
        self._skip_ws()
        if self.state["pos"] >= len(self.state["text"]):
            return None
        if self.state["text"][self.state["pos"]] != "[":
            return None
        self.state["pos"] += 1
        if self.state["pos"] < len(self.state["text"]) and self.state["text"][self.state["pos"]] == "@":
            self.state["pos"] += 1
        tag = self._read_tag()
        node = BclNode(tag)
        self._skip_ws()
        if self.state["pos"] < len(self.state["text"]) and self.state["text"][self.state["pos"]] == "]":
            self.state["pos"] += 1
        self._skip_ws()
        if self.state["pos"] < len(self.state["text"]) and self.state["text"][self.state["pos"]] == "{":
            self.state["pos"] += 1
            self._parse_body(node)
        return node

    def _parse_body(self, node):
        while self.state["pos"] < len(self.state["text"]):
            self._skip_ws()
            if self.state["pos"] >= len(self.state["text"]):
                break
            ch = self.state["text"][self.state["pos"]]
            if ch == "}":
                self.state["pos"] += 1
                break
            if ch == "[":
                child = self._parse_container()
                if child:
                    node.add_child(child)
            elif ch == "(":
                values = self._parse_array()
                for v in values:
                    node.add_value(v)
            else:
                tag = self._read_tag()
                if tag:
                    self._skip_ws()
                    if self.state["pos"] < len(self.state["text"]) and self.state["text"][self.state["pos"]] == "{":
                        self.state["pos"] += 1
                        child = BclNode(tag)
                        self._parse_body(child)
                        node.add_child(child)
                    elif self.state["pos"] < len(self.state["text"]) and self.state["text"][self.state["pos"]] == "(":
                        vals = self._parse_array()
                        child = BclNode(tag)
                        for v in vals:
                            child.add_value(v)
                        node.add_child(child)
                    else:
                        node.add_value(tag)

    def _parse_array(self):
        self.state["pos"] += 1
        values = []
        buf = ""
        while self.state["pos"] < len(self.state["text"]):
            ch = self.state["text"][self.state["pos"]]
            if ch == ")":
                self.state["pos"] += 1
                if buf.strip():
                    values.append(buf.strip())
                break
            if ch == ";":
                if buf.strip():
                    values.append(buf.strip())
                buf = ""
                self.state["pos"] += 1
            else:
                buf += ch
                self.state["pos"] += 1
        return values

    def _read_tag(self):
        buf = ""
        while self.state["pos"] < len(self.state["text"]):
            ch = self.state["text"][self.state["pos"]]
            if ch.isalnum() or ch == "_" or ch == "@":
                buf += ch
                self.state["pos"] += 1
            else:
                break
        return buf

    def _skip_ws(self):
        while self.state["pos"] < len(self.state["text"]):
            if self.state["text"][self.state["pos"]] in " \t\n\r":
                self.state["pos"] += 1
            else:
                break


class BclirSerializer:
    """Serialize BclNode tree into compact BCLIR text form."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"output": ""}

    def Run(self, command, params=None):
        dispatch = {"serialize": self._serialize, "deserialize": self._deserialize}
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state.update(config)
        return (1, {"state": self.state}, None)

    def _serialize(self, params):
        node = params.get("node")
        if node is None:
            return (0, None, ("MISSING_NODE", "BclNode required", 0))
        out = self._node_to_bclir(node, 0)
        self.state["output"] = out
        return (1, {"bclir": out}, None)

    def _node_to_bclir(self, node, depth):
        if node.tag is None:
            return ""
        tag = self._short_tag(node.tag)
        parts = []
        for v in node.values:
            parts.append(self._short_value(v))
        for c in node.children:
            parts.append(self._node_to_bclir(c, depth + 1))
        if len(parts) == 0:
            return tag
        if len(parts) == 1 and not node.children:
            return f"{tag}({parts[0]})"
        inner = " ".join(parts)
        return f"{tag}({inner})"

    def _short_tag(self, tag):
        shortcuts = {
            "VERSION": "V", "STAGES": "S", "CONTAINER": "C", "OBJECT": "O",
            "STRINGPOOL": "SP", "SYMBOLTABLE": "ST", "TYPETABLE": "TT",
            "OBJECTINDEX": "OI", "BLOCKS": "BL", "METADATA": "MD",
            "SHA256": "SHA", "HEADER": "H", "PAYLOAD": "P",
            "TYPE": "TY", "FLAGS": "FL", "PARENT": "PA", "NAMESID": "NS",
            "CHILD": "FC", "SIBLING": "NSB", "OFFSET": "OF",
            "CLENGTH": "CL", "OLENGTH": "OL", "CRC32": "CRC",
            "ID": "ID", "CLASS": "CLS", "METHOD": "MTH", "FUNCTION": "FUN",
            "SQL": "SQL", "GRAPH": "GPH", "BCL": "BCL", "LAW": "LAW",
            "CONFIG": "CFG", "RESOURCE": "RES", "RAW": "RAW",
            "NODE": "N", "EDGE": "E", "DEPENDS": "D", "CALLS": "C",
            "REFERENCES": "R", "LOAD": "LD", "STORE": "ST",
            "PUSH": "PS", "POP": "PP", "CALL": "CAL", "RETURN": "RET",
            "JUMP": "JMP", "BRANCH": "BR", "COMPARE": "CMP", "END": "END",
            "FETCH": "F", "DECODE": "D", "EXECUTE": "X",
            "LAZYLOAD": "LAZY", "PIN": "PIN", "EVICT": "EVICT",
            "SNAPSHOT": "SNAP", "DELTA": "DELTA", "MERGE": "MERGE",
            "EXPLANATION": "EX", "EXAMPLE": "EXA", "ALGORITHM": "ALG",
            "EXECUTIONPLAN": "PLAN", "README": "DOC", "COMMENT": "CMT",
        }
        return shortcuts.get(tag, tag)

    def _short_value(self, val):
        val = val.strip().strip('"').strip("'")
        shortcuts = {
            "U32": "U32", "U16": "U16", "U8": "U8", "B32": "B32",
            "CREATE": "CR", "SELECT": "SEL", "INSERT": "INS",
            "UPDATE": "UPD", "DELETE": "DEL", "PROCEDURE": "PROC",
            "VIEW": "VIEW", "INDEX": "IDX", "TRIGGER": "TRG",
        }
        return shortcuts.get(val, val)

    def _deserialize(self, params):
        bclir = params.get("bclir", "")
        parser = BclParser()
        ok, data, err = parser.Run("parse", {"text": bclir})
        if not ok:
            return (0, None, ("DESERIALIZE_FAILED", err[1], 0))
        return (1, {"node": data["root"]}, None)


class IrCompiler:
    """Compile BclNode tree into PLF IR opcode stream."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"opcodes": [], "strings": [], "string_map": {}, "constants": []}

    def Run(self, command, params=None):
        dispatch = {
            "compile": self._compile,
            "compile_sql": self._compile_sql,
            "compile_graph": self._compile_graph,
            "compile_python": self._compile_python,
            "to_bytecode": self._to_bytecode,
            "from_bytecode": self._from_bytecode,
            "disassemble": self._disassemble,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state.update(config)
        return (1, {"state": self.state}, None)

    def _sid(self, text):
        if text in self.state["string_map"]:
            return self.state["string_map"][text]
        sid = len(self.state["strings"])
        self.state["strings"].append(text)
        self.state["string_map"][text] = sid
        return sid

    def _emit(self, op_name, operand=None):
        op = OPCODES.get(op_name)
        if op is None:
            return
        self.state["opcodes"].append((op, operand))

    def _compile(self, params):
        node = params.get("node")
        if node is None:
            return (0, None, ("MISSING_NODE", "BclNode required", 0))
        self.state["opcodes"] = []
        self._compile_node(node)
        return (1, {"opcodes": self.state["opcodes"], "count": len(self.state["opcodes"])}, None)

    def _compile_node(self, node):
        if node.tag == "SQL":
            self._compile_sql_node(node)
        elif node.tag == "GRAPH":
            self._compile_graph_node(node)
        elif node.tag in ("METHOD", "FUNCTION"):
            self._compile_method_node(node)
        else:
            for c in node.children:
                self._compile_node(c)

    def _compile_sql_node(self, node):
        for v in node.values:
            v_upper = v.upper().strip('"').strip("'")
            if v_upper in SQL_OPS:
                self._emit("SQL_SELECT" if v_upper == "SELECT" else
                          f"SQL_{v_upper}")

    def _compile_graph_node(self, node):
        for c in node.children:
            if c.tag == "NODE":
                for v in c.values:
                    self._emit("NODE", int(v) if v.isdigit() else self._sid(v))
            elif c.tag == "EDGE":
                vals = c.values
                if len(vals) >= 2:
                    a = int(vals[0]) if vals[0].isdigit() else self._sid(vals[0])
                    b = int(vals[1]) if vals[1].isdigit() else self._sid(vals[1])
                    self._emit("EDGE", (a, b))

    def _compile_method_node(self, node):
        for c in node.children:
            if c.tag == "IR":
                for v in c.values:
                    v_upper = v.upper().strip('"').strip("'")
                    if v_upper in OPCODES:
                        self._emit(v_upper)
            else:
                self._compile_node(c)

    def _compile_sql(self, params):
        sql = params.get("sql", "")
        self.state["opcodes"] = []
        sql_upper = sql.upper().strip()
        if sql_upper.startswith("SELECT"):
            self._emit("SQL_SELECT")
            self._parse_sql_tables(sql)
            self._parse_sql_where(sql)
        elif sql_upper.startswith("INSERT"):
            self._emit("SQL_INSERT")
            self._parse_sql_tables(sql)
        elif sql_upper.startswith("UPDATE"):
            self._emit("SQL_UPDATE")
            self._parse_sql_tables(sql)
        elif sql_upper.startswith("DELETE"):
            self._emit("SQL_DELETE")
            self._parse_sql_tables(sql)
        elif sql_upper.startswith("CREATE"):
            self._emit("SQL_CREATE")
            self._parse_sql_tables(sql)
        self._emit("END")
        return (1, {"opcodes": self.state["opcodes"], "count": len(self.state["opcodes"])}, None)

    def _parse_sql_tables(self, sql):
        words = sql.split()
        for i, w in enumerate(words):
            w_clean = w.strip(",();")
            if w_clean.upper() in ("FROM", "INTO", "TABLE", "UPDATE") and i + 1 < len(words):
                table = words[i + 1].strip(",();")
                sid = self._sid(table)
                self._emit("TABLE_REF", sid)
                break

    def _parse_sql_where(self, sql):
        if "WHERE" in sql.upper():
            self._emit("WHERE_EQ")
            self._emit("PARAM", 0)

    def _compile_graph(self, params):
        edges = params.get("edges", [])
        self.state["opcodes"] = []
        for a, b in edges:
            self._emit("NODE", a)
            self._emit("NODE", b)
            self._emit("EDGE", (a, b))
        self._emit("END")
        return (1, {"opcodes": self.state["opcodes"], "count": len(self.state["opcodes"])}, None)

    def _compile_python(self, params):
        source = params.get("source", "")
        self.state["opcodes"] = []
        lines = source.strip().splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("return True"):
                self._emit("PUSH", 1)
                self._emit("RETURN")
            elif stripped.startswith("return False"):
                self._emit("PUSH", 0)
                self._emit("RETURN")
            elif stripped.startswith("return None"):
                self._emit("PUSH", None)
                self._emit("RETURN")
            elif stripped.startswith("return "):
                val = stripped[7:]
                self._emit("LOAD_CONST", self._sid(val))
                self._emit("RETURN")
            elif ".execute(" in stripped:
                self._emit("LOAD_SELF")
                self._emit("LOAD_ATTR", self._sid("cursor"))
                self._emit("CALL", self._sid("execute"))
            elif stripped.startswith("if "):
                self._emit("COMPARE_EQ")
                self._emit("JUMP_FALSE")
        self._emit("END")
        return (1, {"opcodes": self.state["opcodes"], "count": len(self.state["opcodes"])}, None)

    def _to_bytecode(self, params):
        opcodes = params.get("opcodes", self.state["opcodes"])
        buf = io.BytesIO()
        for op, operand in opcodes:
            buf.write(struct.pack(">B", op))
            if operand is None:
                buf.write(struct.pack(">B", 0))
            elif isinstance(operand, int):
                if 0 <= operand <= 255:
                    buf.write(struct.pack(">B", 1))
                    buf.write(struct.pack(">B", operand))
                else:
                    buf.write(struct.pack(">B", 2))
                    buf.write(struct.pack(">I", operand))
            elif isinstance(operand, tuple):
                buf.write(struct.pack(">B", 3))
                buf.write(struct.pack(">II", operand[0], operand[1]))
            else:
                buf.write(struct.pack(">B", 0))
        data = buf.getvalue()
        return (1, {"bytecode": data, "size": len(data)}, None)

    def _from_bytecode(self, params):
        data = params.get("bytecode", b"")
        opcodes = []
        pos = 0
        while pos < len(data):
            op = data[pos]
            pos += 1
            if pos >= len(data):
                break
            operand_type = data[pos]
            pos += 1
            operand = None
            if operand_type == 0:
                operand = None
            elif operand_type == 1:
                operand = data[pos]
                pos += 1
            elif operand_type == 2:
                operand = struct.unpack_from(">I", data, pos)[0]
                pos += 4
            elif operand_type == 3:
                a, b = struct.unpack_from(">II", data, pos)
                pos += 8
                operand = (a, b)
            opcodes.append((op, operand))
        self.state["opcodes"] = opcodes
        return (1, {"opcodes": opcodes, "count": len(opcodes)}, None)

    def _disassemble(self, params):
        opcodes = params.get("opcodes", self.state["opcodes"])
        lines = []
        for op, operand in opcodes:
            name = OPCODE_NAMES.get(op, f"0x{op:02x}")
            if operand is None:
                lines.append(f"  {name}")
            elif isinstance(operand, tuple):
                lines.append(f"  {name} {operand[0]} {operand[1]}")
            else:
                lines.append(f"  {name} {operand}")
        return (1, {"disasm": lines}, None)


class PlfIrCompiler:
    """Top-level orchestrator: BCL → BCLIR → IR → Bytecode → Container."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"parser": BclParser(), "serializer": BclirSerializer(),
                      "ir": IrCompiler(), "results": {}}

    def Run(self, command, params=None):
        dispatch = {
            "compile_bcl": self._compile_bcl,
            "compile_sql": self._compile_sql,
            "compile_python": self._compile_python,
            "compile_graph": self._compile_graph,
            "pipeline": self._pipeline,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state.update(config)
        return (1, {"state": self.state}, None)

    def _compile_bcl(self, params):
        bcl_text = params.get("bcl", "")
        parser = self.state["parser"]
        ok, pdata, perr = parser.Run("parse", {"text": bcl_text})
        if not ok:
            return (0, None, perr)

        serializer = self.state["serializer"]
        ok, sdata, serr = serializer.Run("serialize", {"node": pdata["root"]})
        if not ok:
            return (0, None, serr)

        ir = self.state["ir"]
        ok, idata, ierr = ir.Run("compile", {"node": pdata["root"]})
        if not ok:
            return (0, None, ierr)

        ok, bdata, berr = ir.Run("to_bytecode", {"opcodes": idata["opcodes"]})
        if not ok:
            return (0, None, berr)

        ok, disasm, _ = ir.Run("disassemble", {"opcodes": idata["opcodes"]})

        return (1, {
            "bclir": sdata["bclir"],
            "opcodes": idata["opcodes"],
            "opcode_count": idata["count"],
            "bytecode": bdata["bytecode"],
            "bytecode_size": bdata["size"],
            "disasm": disasm.get("disasm", []),
            "strings": ir.state["strings"],
        }, None)

    def _compile_sql(self, params):
        sql = params.get("sql", "")
        ir = self.state["ir"]
        ok, idata, ierr = ir.Run("compile_sql", {"sql": sql})
        if not ok:
            return (0, None, ierr)
        ok, bdata, _ = ir.Run("to_bytecode", {"opcodes": idata["opcodes"]})
        ok, disasm, _ = ir.Run("disassemble", {"opcodes": idata["opcodes"]})
        return (1, {
            "opcodes": idata["opcodes"],
            "bytecode": bdata["bytecode"],
            "bytecode_size": bdata["size"],
            "disasm": disasm.get("disasm", []),
            "strings": ir.state["strings"],
        }, None)

    def _compile_python(self, params):
        source = params.get("source", "")
        ir = self.state["ir"]
        ok, idata, ierr = ir.Run("compile_python", {"source": source})
        if not ok:
            return (0, None, ierr)
        ok, bdata, _ = ir.Run("to_bytecode", {"opcodes": idata["opcodes"]})
        ok, disasm, _ = ir.Run("disassemble", {"opcodes": idata["opcodes"]})
        return (1, {
            "opcodes": idata["opcodes"],
            "bytecode": bdata["bytecode"],
            "bytecode_size": bdata["size"],
            "disasm": disasm.get("disasm", []),
            "strings": ir.state["strings"],
        }, None)

    def _compile_graph(self, params):
        edges = params.get("edges", [])
        ir = self.state["ir"]
        ok, idata, ierr = ir.Run("compile_graph", {"edges": edges})
        if not ok:
            return (0, None, ierr)
        ok, bdata, _ = ir.Run("to_bytecode", {"opcodes": idata["opcodes"]})
        ok, disasm, _ = ir.Run("disassemble", {"opcodes": idata["opcodes"]})
        return (1, {
            "opcodes": idata["opcodes"],
            "bytecode": bdata["bytecode"],
            "bytecode_size": bdata["size"],
            "disasm": disasm.get("disasm", []),
        }, None)

    def _pipeline(self, params):
        """Full pipeline: BCL → BCLIR → IR → Bytecode → Container."""
        bcl_text = params.get("bcl", "")
        container_path = params.get("path", "/tmp/output.plf")

        ok, result, err = self._compile_bcl({"bcl": bcl_text})
        if not ok:
            return (0, None, err)

        from PlfContainer import PlfContainer
        c = PlfContainer()

        for s in result["strings"]:
            c.Run("add_string", {"text": s})

        c.Run("add_object", {
            "type": "BCL",
            "name": "BclSource",
            "payload": bcl_text,
        })
        c.Run("add_object", {
            "type": "BCLIR",
            "name": "BclirForm",
            "payload": result["bclir"],
        })
        c.Run("add_object", {
            "type": "RAW",
            "name": "Bytecode",
            "payload": result["bytecode"],
        })

        ok, winfo, werr = c.Run("write", {"path": container_path})
        if not ok:
            return (0, None, werr)

        return (1, {
            "bclir": result["bclir"],
            "opcode_count": result["opcode_count"],
            "bytecode_size": result["bytecode_size"],
            "container": winfo,
            "disasm": result["disasm"],
        }, None)


if __name__ == "__main__":
    print("=== PLF IR Compiler Demo ===\n")

    compiler = PlfIrCompiler()

    # Test 1: Compile SQL to IR
    print("--- SQL Compilation ---")
    ok, data, _ = compiler.Run("compile_sql", {
        "sql": "SELECT * FROM Person WHERE id = ?"
    })
    print(f"Bytecode: {data['bytecode_size']} bytes")
    print(f"Strings: {data['strings']}")
    for line in data["disasm"]:
        print(line)

    # Test 2: Compile Python to IR
    print("\n--- Python Compilation ---")
    ok, data, _ = compiler.Run("compile_python", {
        "source": "def save(self):\n    return True"
    })
    print(f"Bytecode: {data['bytecode_size']} bytes")
    for line in data["disasm"]:
        print(line)

    # Test 3: Compile graph to IR
    print("\n--- Graph Compilation ---")
    ok, data, _ = compiler.Run("compile_graph", {
        "edges": [(1, 2), (2, 3), (3, 1)]
    })
    print(f"Bytecode: {data['bytecode_size']} bytes")
    for line in data["disasm"]:
        print(line)

    # Test 4: Full BCL pipeline
    print("\n--- Full BCL Pipeline ---")
    bcl = """
[@PLF]{
    VERSION(1)
    SQL{
        SELECT
        TABLE(Person)
        WHERE
        COLUMN(id)
        PARAM(0)
        END
    }
    GRAPH{
        NODE(1)
        NODE(2)
        EDGE(1;2)
    }
}
"""
    ok, data, _ = compiler.Run("compile_bcl", {"bcl": bcl})
    print(f"BCLIR: {data['bclir']}")
    print(f"Opcodes: {data['opcode_count']}")
    print(f"Bytecode: {data['bytecode_size']} bytes")
    for line in data["disasm"]:
        print(line)

    # Test 5: Full pipeline to .plf
    print("\n--- Full Pipeline to .plf ---")
    ok, data, _ = compiler.Run("pipeline", {"bcl": bcl, "path": "/tmp/ir_test.plf"})
    print(f"BCLIR: {data['bclir'][:80]}...")
    print(f"Opcodes: {data['opcode_count']}")
    print(f"Bytecode: {data['bytecode_size']} bytes")
    print(f"Container: {data['container']}")

    # Test 6: Bytecode round-trip
    print("\n--- Bytecode Round-Trip ---")
    ir = IrCompiler()
    ok, data, _ = ir.Run("compile_sql", {"sql": "SELECT * FROM Person WHERE id = ?"})
    ok, bdata, _ = ir.Run("to_bytecode", {"opcodes": data["opcodes"]})
    ok, rdata, _ = ir.Run("from_bytecode", {"bytecode": bdata["bytecode"]})
    ok, disasm, _ = ir.Run("disassemble", {"opcodes": rdata["opcodes"]})
    print(f"Original: {data['count']} opcodes")
    print(f"Round-trip: {rdata['count']} opcodes")
    for line in disasm["disasm"]:
        print(line)
