#[@GHOST]
#[@VBSTYLE]
#[@FILEID] PlfContainer.py
#[@SUMMARY] PLF Binary Container — .plf file format with header, string pool, symbol table, type table, block manager
#[@CLASS] PlfContainer
#[@METHOD] Run
#[@DATE] 2026-07-04
#[@AUTHOR] Wayne / Cascade
#[@SESSION] CHECKPOINT-VEF-1
#[@CONTEXT] Stage 1 of VEF — binary object container format

"""
PLF Binary Container (.plf)

File Layout:
    +------------------+
    | Header (64 bytes)|
    +------------------+
    | String Pool      |
    +------------------+
    | Symbol Table     |
    +------------------+
    | Type Table       |
    +------------------+
    | Object Index     |
    +------------------+
    | Blocks           |
    +------------------+
    | Metadata         |
    +------------------+
    | SHA256 (32 bytes)|
    +------------------+

Block Layout (per object):
    ObjectID      4 bytes
    TypeID        1 byte
    Flags         1 byte
    Version       2 bytes
    ParentID      4 bytes
    CompressedLen 4 bytes
    OriginalLen   4 bytes
    CRC32         4 bytes
    Payload       CompressedLen bytes

Usage:
    from PlfContainer import PlfContainer

    c = PlfContainer()
    c.Run("add_string", {"text": "CREATE TABLE"})
    c.Run("add_object", {"type": "SQL", "name": "CreatePerson", "payload": b"..."})
    c.Run("write", {"path": "/tmp/test.plf"})
    c.Run("read", {"path": "/tmp/test.plf"})
    c.Run("get_object", {"object_id": 1})
"""

import struct
import zlib
import hashlib
import json
import io
from typing import Dict, List, Tuple, Optional

MAGIC = b"PLF1"
HEADER_SIZE = 64
BLOCK_HEADER_SIZE = 24  # 4+1+1+2+4+4+4+4

TYPE_IDS = {
    "CLASS":         0x01,
    "METHOD":        0x02,
    "FUNCTION":      0x03,
    "SQL":           0x04,
    "GRAPH":         0x05,
    "BCL":           0x06,
    "BCLIR":         0x07,
    "LAW":           0x08,
    "COMMENT":       0x09,
    "README":        0x0A,
    "DOCSTRING":     0x0B,
    "EXAMPLE":       0x0C,
    "EXECUTIONPLAN": 0x0D,
    "TABLE":         0x0E,
    "INDEX":         0x0F,
    "VIEW":          0x10,
    "TRIGGER":       0x11,
    "PROCEDURE":     0x12,
    "FUNCTION_SQL":  0x13,
    "CONFIG":        0x14,
    "RESOURCE":      0x15,
    "METADATA":      0x16,
    "BYTECODE":      0x17,
    "IR":            0x18,
    "FUNCTION_DESC": 0x19,
    "RAW":           0xFF,
}

TYPE_NAMES = {v: k for k, v in TYPE_IDS.items()}

FLAG_COMPRESSED = 0x01
FLAG_ENCRYPTED  = 0x02
FLAG_DELETED    = 0x04
FLAG_DELTA      = 0x08


class PlfContainer:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "strings": [],
            "string_map": {},
            "symbols": {},
            "objects": {},
            "next_id": 1,
            "metadata": {},
            "version": 1,
        }
        self._buf = None
        self._cursor = 0

    def Run(self, command, params=None):
        dispatch = {
            "add_string": self._add_string,
            "get_string": self._get_string,
            "add_object": self._add_object,
            "get_object": self._get_object,
            "get_by_name": self._get_by_name,
            "list_objects": self._list_objects,
            "list_strings": self._list_strings,
            "write": self._write,
            "read": self._read,
            "inspect": self._inspect,
            "stats": self._stats,
            "set_metadata": self._set_metadata,
            "get_metadata": self._get_metadata,
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

    # ── String Pool ───────────────────────────────────────────

    def _add_string(self, params):
        text = params.get("text", "")
        if text in self.state["string_map"]:
            return (1, {"index": self.state["string_map"][text]}, None)
        idx = len(self.state["strings"])
        self.state["strings"].append(text)
        self.state["string_map"][text] = idx
        return (1, {"index": idx}, None)

    def _get_string(self, params):
        idx = params.get("index", -1)
        if 0 <= idx < len(self.state["strings"]):
            return (1, {"text": self.state["strings"][idx]}, None)
        return (0, None, ("STRING_NOT_FOUND", f"Index {idx} out of range", 0))

    def _list_strings(self, params):
        return (1, {"strings": self.state["strings"], "count": len(self.state["strings"])}, None)

    # ── Object Manager ────────────────────────────────────────

    def _add_object(self, params):
        obj_type = params.get("type", "RAW")
        type_id = TYPE_IDS.get(obj_type, 0xFF)
        name = params.get("name", "")
        payload = params.get("payload", b"")
        parent_id = params.get("parent_id", 0)
        flags = params.get("flags", 0)
        compress = params.get("compress", True)

        if isinstance(payload, str):
            payload = payload.encode("utf-8")

        original_len = len(payload)
        crc = zlib.crc32(payload) & 0xFFFFFFFF

        if compress and original_len > 0:
            payload_stored = zlib.compress(payload, 9)
            flags |= FLAG_COMPRESSED
        else:
            payload_stored = payload
            flags &= ~FLAG_COMPRESSED

        obj_id = self.state["next_id"]
        self.state["next_id"] += 1

        if name:
            self.state["symbols"][name] = obj_id
            self._add_string({"text": name})

        self.state["objects"][obj_id] = {
            "object_id": obj_id,
            "type_id": type_id,
            "type_name": obj_type,
            "flags": flags,
            "version": self.state["version"],
            "parent_id": parent_id,
            "name": name,
            "compressed_len": len(payload_stored),
            "original_len": original_len,
            "crc32": crc,
            "payload": payload_stored,
        }

        return (1, {"object_id": obj_id, "compressed_len": len(payload_stored),
                     "original_len": original_len}, None)

    def _get_object(self, params):
        obj_id = params.get("object_id", -1)
        obj = self.state["objects"].get(obj_id)
        if obj is None:
            return (0, None, ("OBJECT_NOT_FOUND", f"Object {obj_id} not found", 0))

        payload = obj["payload"]
        if obj["flags"] & FLAG_COMPRESSED:
            payload = zlib.decompress(payload)

        return (1, {
            "object_id": obj["object_id"],
            "type": obj["type_name"],
            "flags": obj["flags"],
            "version": obj["version"],
            "parent_id": obj["parent_id"],
            "name": obj["name"],
            "payload": payload,
            "original_len": obj["original_len"],
            "crc32": obj["crc32"],
        }, None)

    def _get_by_name(self, params):
        name = params.get("name", "")
        obj_id = self.state["symbols"].get(name)
        if obj_id is None:
            return (0, None, ("NAME_NOT_FOUND", f"Symbol '{name}' not found", 0))
        return self._get_object({"object_id": obj_id})

    def _list_objects(self, params):
        type_filter = params.get("type")
        result = []
        for obj in self.state["objects"].values():
            if type_filter and obj["type_name"] != type_filter:
                continue
            result.append({
                "object_id": obj["object_id"],
                "type": obj["type_name"],
                "name": obj["name"],
                "version": obj["version"],
                "parent_id": obj["parent_id"],
                "original_len": obj["original_len"],
                "compressed_len": obj["compressed_len"],
            })
        return (1, {"objects": result, "count": len(result)}, None)

    # ── Metadata ──────────────────────────────────────────────

    def _set_metadata(self, params):
        key = params.get("key", "")
        value = params.get("value", "")
        if key:
            self.state["metadata"][key] = value
            return (1, {"key": key, "value": value}, None)
        return (0, None, ("MISSING_KEY", "Metadata key required", 0))

    def _get_metadata(self, params):
        key = params.get("key", "")
        if key:
            return (1, {"key": key, "value": self.state["metadata"].get(key)}, None)
        return (1, {"metadata": self.state["metadata"]}, None)

    # ── Binary Write ──────────────────────────────────────────

    def _write(self, params):
        path = params.get("path", "")
        if not path:
            return (0, None, ("MISSING_PATH", "File path required", 0))

        buf = io.BytesIO()

        string_pool = self._pack_string_pool()
        symbol_table = self._pack_symbol_table()
        type_table = self._pack_type_table()
        object_index, blocks = self._pack_blocks()

        offsets = {
            "string_pool": HEADER_SIZE,
            "symbol_table": 0,
            "type_table": 0,
            "object_index": 0,
            "blocks": 0,
            "metadata": 0,
        }
        cur = offsets["string_pool"] + len(string_pool)
        offsets["symbol_table"] = cur
        cur += len(symbol_table)
        offsets["type_table"] = cur
        cur += len(type_table)
        offsets["object_index"] = cur
        cur += len(object_index)
        offsets["blocks"] = cur
        cur += len(blocks)
        offsets["metadata"] = cur

        meta_bytes = json.dumps(self.state["metadata"], separators=(",", ":")).encode("utf-8")
        cur += len(meta_bytes)

        header = struct.pack(">4sHHIIIIII",
            MAGIC,
            self.state["version"],
            len(self.state["objects"]),
            offsets["string_pool"],
            offsets["symbol_table"],
            offsets["type_table"],
            offsets["object_index"],
            offsets["blocks"],
            offsets["metadata"],
        )
        header = header.ljust(HEADER_SIZE, b"\x00")
        buf.write(header)

        buf.write(string_pool)
        buf.write(symbol_table)
        buf.write(type_table)
        buf.write(object_index)
        buf.write(blocks)
        buf.write(meta_bytes)

        all_bytes = buf.getvalue()
        sha = hashlib.sha256(all_bytes).digest()
        buf.write(sha)

        with open(path, "wb") as f:
            f.write(buf.getvalue())

        return (1, {"path": path, "size": len(all_bytes) + 32,
                     "objects": len(self.state["objects"]),
                     "strings": len(self.state["strings"])}, None)

    def _pack_string_pool(self):
        buf = io.BytesIO()
        strings = self.state["strings"]
        buf.write(struct.pack(">I", len(strings)))
        for s in strings:
            b = s.encode("utf-8")
            buf.write(struct.pack(">I", len(b)))
            buf.write(b)
        return buf.getvalue()

    def _pack_symbol_table(self):
        buf = io.BytesIO()
        symbols = self.state["symbols"]
        buf.write(struct.pack(">I", len(symbols)))
        for name, obj_id in symbols.items():
            nb = name.encode("utf-8")
            buf.write(struct.pack(">H", len(nb)))
            buf.write(nb)
            buf.write(struct.pack(">I", obj_id))
        return buf.getvalue()

    def _pack_type_table(self):
        buf = io.BytesIO()
        buf.write(struct.pack(">B", len(TYPE_IDS)))
        for name, tid in TYPE_IDS.items():
            nb = name.encode("utf-8")
            buf.write(struct.pack(">B", tid))
            buf.write(struct.pack(">B", len(nb)))
            buf.write(nb)
        return buf.getvalue()

    def _pack_blocks(self):
        index_buf = io.BytesIO()
        blocks_buf = io.BytesIO()
        objects = self.state["objects"]

        index_buf.write(struct.pack(">I", len(objects)))

        for obj_id in sorted(objects.keys()):
            obj = objects[obj_id]
            offset = blocks_buf.tell()

            blocks_buf.write(struct.pack(">IBBHIIII",
                obj["object_id"],
                obj["type_id"],
                obj["flags"],
                obj["version"],
                obj["parent_id"],
                obj["compressed_len"],
                obj["original_len"],
                obj["crc32"],
            ))
            blocks_buf.write(obj["payload"])

            index_buf.write(struct.pack(">III",
                obj_id,
                offset,
                BLOCK_HEADER_SIZE + obj["compressed_len"],
            ))

        return index_buf.getvalue(), blocks_buf.getvalue()

    # ── Binary Read ───────────────────────────────────────────

    def _read(self, params):
        path = params.get("path", "")
        if not path:
            return (0, None, ("MISSING_PATH", "File path required", 0))

        with open(path, "rb") as f:
            data = f.read()

        if len(data) < HEADER_SIZE + 32:
            return (0, None, ("FILE_TOO_SMALL", "File is too small to be valid", 0))

        payload = data[:-32]
        stored_sha = data[-32:]
        actual_sha = hashlib.sha256(payload).digest()
        if stored_sha != actual_sha:
            return (0, None, ("CHECKSUM_FAIL", "SHA256 mismatch — file corrupted", 0))

        magic, version, obj_count, sp_off, st_off, tt_off, oi_off, bl_off, md_off = \
            struct.unpack_from(">4sHHIIIIII", data, 0)

        if magic != MAGIC:
            return (0, None, ("BAD_MAGIC", "Not a PLF file", 0))

        self.state["version"] = version
        self.state["strings"] = []
        self.state["string_map"] = {}
        self.state["symbols"] = {}
        self.state["objects"] = {}
        self.state["metadata"] = {}

        self._parse_string_pool(data, sp_off)
        self._parse_symbol_table(data, st_off)
        self._parse_blocks(data, oi_off, bl_off, obj_count)
        self._parse_metadata(data, md_off)

        self.state["next_id"] = max(self.state["objects"].keys(), default=0) + 1

        return (1, {"objects": len(self.state["objects"]),
                     "strings": len(self.state["strings"]),
                     "symbols": len(self.state["symbols"]),
                     "version": version}, None)

    def _parse_string_pool(self, data, offset):
        count = struct.unpack_from(">I", data, offset)[0]
        pos = offset + 4
        for _ in range(count):
            slen = struct.unpack_from(">I", data, pos)[0]
            pos += 4
            s = data[pos:pos+slen].decode("utf-8")
            pos += slen
            idx = len(self.state["strings"])
            self.state["strings"].append(s)
            self.state["string_map"][s] = idx

    def _parse_symbol_table(self, data, offset):
        count = struct.unpack_from(">I", data, offset)[0]
        pos = offset + 4
        for _ in range(count):
            nlen = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            name = data[pos:pos+nlen].decode("utf-8")
            pos += nlen
            obj_id = struct.unpack_from(">I", data, pos)[0]
            pos += 4
            self.state["symbols"][name] = obj_id

    def _parse_blocks(self, data, index_off, blocks_off, obj_count):
        pos = index_off + 4  # skip count prefix
        for _ in range(obj_count):
            obj_id, offset, block_size = struct.unpack_from(">III", data, pos)
            pos += 12

            bpos = blocks_off + offset
            oid, type_id, flags, version, parent_id, clen, olen, crc = \
                struct.unpack_from(">IBBHIIII", data, bpos)
            payload = data[bpos+BLOCK_HEADER_SIZE : bpos+BLOCK_HEADER_SIZE+clen]

            self.state["objects"][oid] = {
                "object_id": oid,
                "type_id": type_id,
                "type_name": TYPE_NAMES.get(type_id, "UNKNOWN"),
                "flags": flags,
                "version": version,
                "parent_id": parent_id,
                "name": "",
                "compressed_len": clen,
                "original_len": olen,
                "crc32": crc,
                "payload": payload,
            }

        for name, obj_id in self.state["symbols"].items():
            if obj_id in self.state["objects"]:
                self.state["objects"][obj_id]["name"] = name

    def _parse_metadata(self, data, offset):
        meta_end = len(data) - 32
        if offset < meta_end:
            meta_bytes = data[offset:meta_end]
            try:
                self.state["metadata"] = json.loads(meta_bytes.decode("utf-8"))
            except Exception:
                self.state["metadata"] = {}

    # ── Inspect / Stats ───────────────────────────────────────

    def _inspect(self, params):
        path = params.get("path", "")
        if not path:
            return (0, None, ("MISSING_PATH", "File path required", 0))

        with open(path, "rb") as f:
            data = f.read()

        magic, version, obj_count, sp_off, st_off, tt_off, oi_off, bl_off, md_off = \
            struct.unpack_from(">4sHHIIIIII", data, 0)

        sha_ok = hashlib.sha256(data[:-32]).digest() == data[-32:]

        return (1, {
            "magic": magic.decode("ascii", "replace"),
            "version": version,
            "objects": obj_count,
            "file_size": len(data),
            "sha256_ok": sha_ok,
            "offsets": {
                "string_pool": sp_off,
                "symbol_table": st_off,
                "type_table": tt_off,
                "object_index": oi_off,
                "blocks": bl_off,
                "metadata": md_off,
            },
        }, None)

    def _stats(self, params):
        objects = self.state["objects"]
        strings = self.state["strings"]
        symbols = self.state["symbols"]

        total_compressed = sum(o["compressed_len"] for o in objects.values())
        total_original = sum(o["original_len"] for o in objects.values())

        by_type = {}
        for o in objects.values():
            t = o["type_name"]
            if t not in by_type:
                by_type[t] = {"count": 0, "compressed": 0, "original": 0}
            by_type[t]["count"] += 1
            by_type[t]["compressed"] += o["compressed_len"]
            by_type[t]["original"] += o["original_len"]

        ratio = (total_compressed / total_original * 100) if total_original > 0 else 0

        return (1, {
            "objects": len(objects),
            "strings": len(strings),
            "symbols": len(symbols),
            "total_compressed": total_compressed,
            "total_original": total_original,
            "ratio": f"{ratio:.1f}%",
            "by_type": by_type,
        }, None)


if __name__ == "__main__":
    c = PlfContainer()

    print("=== PLF Container Demo ===\n")

    for s in ["CREATE TABLE", "Person", "id", "name", "SELECT", "WHERE", "INSERT INTO"]:
        c.Run("add_string", {"text": s})

    c.Run("add_object", {"type": "SQL", "name": "CreatePerson",
         "payload": "CREATE TABLE Person (id INT PRIMARY KEY, name TEXT)"})
    c.Run("add_object", {"type": "SQL", "name": "SelectPerson",
         "payload": "SELECT * FROM Person WHERE id = ?"})
    c.Run("add_object", {"type": "SQL", "name": "InsertPerson",
         "payload": "INSERT INTO Person (id, name) VALUES (?, ?)"})
    c.Run("add_object", {"type": "CLASS", "name": "PersonModel",
         "payload": "class PersonModel:\n    def save(self):\n        return True"})
    c.Run("add_object", {"type": "GRAPH", "name": "CallGraph",
         "payload": "NODE 1\nNODE 2\nEDGE 1 2"})
    c.Run("add_object", {"type": "BCL", "name": "PersonBcl",
         "payload": "[@PERSON]{(id;1)(name;2)}"})
    c.Run("add_object", {"type": "LAW", "name": "LAW262",
         "payload": "Table names must use PascalCase."})
    c.Run("add_object", {"type": "METADATA", "name": "ProjectInfo",
         "payload": '{"author":"Wayne","version":"1.0"}'})

    c.Run("set_metadata", {"key": "author", "value": "Wayne"})
    c.Run("set_metadata", {"key": "project", "value": "VEF Demo"})

    ok, stats, _ = c.Run("stats", {})
    print(f"Objects: {stats['objects']}  Strings: {stats['strings']}  Symbols: {stats['symbols']}")
    print(f"Compressed: {stats['total_compressed']}  Original: {stats['total_original']}  Ratio: {stats['ratio']}")
    type_summary = ', '.join(f"{k}={v['count']}" for k, v in stats['by_type'].items())
    print(f"By type: {type_summary}")

    ok, winfo, _ = c.Run("write", {"path": "/tmp/demo.plf"})
    print(f"\nWritten: {winfo}")

    ok, info, _ = c.Run("inspect", {"path": "/tmp/demo.plf"})
    print(f"Inspect: magic={info['magic']}  version={info['version']}  sha256_ok={info['sha256_ok']}")
    print(f"  Offsets: {info['offsets']}")

    c2 = PlfContainer()
    ok, rinfo, _ = c2.Run("read", {"path": "/tmp/demo.plf"})
    print(f"\nRead: {rinfo}")

    ok, obj, _ = c2.Run("get_by_name", {"name": "CreatePerson"})
    print(f"CreatePerson: type={obj['type']}  payload={obj['payload'][:50]}...")

    ok, obj, _ = c2.Run("get_by_name", {"name": "PersonBcl"})
    print(f"PersonBcl: type={obj['type']}  payload={obj['payload']}")

    ok, obj, _ = c2.Run("get_by_name", {"name": "CallGraph"})
    print(f"CallGraph: type={obj['type']}  payload={obj['payload']}")

    ok, lst, _ = c2.Run("list_objects", {})
    print(f"\nObjects in container:")
    for o in lst["objects"]:
        print(f"  [{o['object_id']:3d}] {o['type']:15s} {o['name']:20s} {o['compressed_len']:5d}/{o['original_len']:5d} bytes")

    ok, stats2, _ = c2.Run("stats", {})
    print(f"\nRound-trip stats: {stats2['objects']} objects, {stats2['strings']} strings, ratio {stats2['ratio']}")
