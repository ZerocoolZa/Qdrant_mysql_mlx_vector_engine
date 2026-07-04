#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLBackpack.py
#[@SUMMARY] Backpack format: self-contained expert bundle with weights + normalization + metadata
#[@CLASS] CoreMLBackpack
#[@METHOD] pack, unpack, inspect, list_backpacks, store_in_db, load_from_db
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import time
import struct
import sqlite3
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

BACKPACK_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/backpacks"
DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"
TOTAL_PARAMS = 23050
MAGIC = b"BPCK"
VERSION = 1

BACKPACK_FORMAT_SPEC = {
    "magic": "BPCK (4 bytes)",
    "format_version": 1,
    "layout": [
        "4 bytes: magic 'BPCK'",
        "4 bytes: format version (uint32 LE)",
        "4 bytes: metadata length (uint32 LE)",
        "N bytes: metadata JSON (UTF-8)",
        "4 bytes: normalization length (uint32 LE)",
        "M bytes: normalization JSON (UTF-8)",
        "4 bytes: weights length (uint32 LE)",
        "W bytes: raw float32 weights (little-endian)",
    ],
    "metadata_fields": ["name", "domain", "version", "description", "created_at", "architecture"],
    "normalization_fields": ["mean", "std", "min", "max", "method"],
    "weights": "23050 x float32 = 92200 bytes",
    "total_size": "~92 KB + metadata",
    "contract": "all backpacks share 40D input, 10D output, 128x128 hidden",
}


class CoreMLBackpack:
    """Backpack format — self-contained expert model bundle.

    Each .backpack file contains:
      - Magic header (BPCK)
      - Format version
      - Metadata JSON (name, domain, version, architecture)
      - Normalization JSON (mean, std, min, max per feature)
      - Weights binary (23050 x float32)

    Pack: weights.bin + norm.json + meta.json → expert.backpack
    Unpack: expert.backpack → weights.bin + norm.json + meta.json
    Store: expert.backpack → SQLite BLOB
    Load: SQLite BLOB → expert.backpack → weights in RAM
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "backpack_dir": BACKPACK_DIR,
                "db_path": DB_PATH,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()

    def Run(self, command, params=None):
        params = params or {}
        if command == "pack":
            return self.cmdPack(params)
        if command == "unpack":
            return self.cmdUnpack(params)
        if command == "inspect":
            return self.cmdInspect(params)
        if command == "list_backpacks":
            return self.cmdListBackpacks(params)
        if command == "store_in_db":
            return self.cmdStoreInDB(params)
        if command == "load_from_db":
            return self.cmdLoadFromDB(params)
        if command == "create_norm":
            return self.cmdCreateNorm(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def ensureDirs(self):
        if not os.path.exists(BACKPACK_DIR):
            os.makedirs(BACKPACK_DIR, exist_ok=True)

    def cmdPack(self, params):
        """Pack weights + normalization + metadata into a .backpack file."""
        try:
            name = self.p(params, "name")
            domain = self.p(params, "domain", "general")
            version = int(self.p(params, "version", 1))
            description = self.p(params, "description", "")
            weightsPath = self.p(params, "weights_path")
            normData = self.p(params, "normalization", None)
            if not name or not weightsPath:
                return (0, None, ("PARAMS_ERROR", "name and weights_path required", 0))
            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", weightsPath, 0))
            with open(weightsPath, "rb") as f:
                weightsBlob = f.read()
            if len(weightsBlob) != TOTAL_PARAMS * 4:
                return (0, None, ("WEIGHTS_SIZE", "Expected " + str(TOTAL_PARAMS * 4) + " got " + str(len(weightsBlob)), 0))
            if normData is None:
                normData = self.defaultNormalization()
            metadata = {
                "name": name,
                "domain": domain,
                "version": version,
                "description": description,
                "created_at": time.time(),
                "architecture": {
                    "input_dim": INPUT_DIM,
                    "hidden_dim": HIDDEN_DIM,
                    "output_dim": OUTPUT_DIM,
                    "total_params": TOTAL_PARAMS,
                    "layers": "40->128->128->10",
                    "activation": "relu",
                },
                "format": "backpack_v1",
                "contract": "40D input, 10D output, shared interface",
            }
            metaJson = json.dumps(metadata, indent=2).encode("utf-8")
            normJson = json.dumps(normData, indent=2).encode("utf-8")
            outputPath = os.path.join(BACKPACK_DIR, name + ".backpack")
            with open(outputPath, "wb") as f:
                f.write(MAGIC)
                f.write(struct.pack("<I", VERSION))
                f.write(struct.pack("<I", len(metaJson)))
                f.write(metaJson)
                f.write(struct.pack("<I", len(normJson)))
                f.write(normJson)
                f.write(struct.pack("<I", len(weightsBlob)))
                f.write(weightsBlob)
            totalSize = os.path.getsize(outputPath)
            return (1, {
                "packed": name,
                "path": outputPath,
                "total_bytes": totalSize,
                "total_kb": round(totalSize / 1024, 1),
                "weights_bytes": len(weightsBlob),
                "metadata_bytes": len(metaJson),
                "normalization_bytes": len(normJson),
            }, None)
        except Exception as e:
            return (0, None, ("PACK_ERROR", str(e), 0))

    def cmdUnpack(self, params):
        """Unpack a .backpack file into weights + norm + metadata."""
        try:
            backpackPath = self.p(params, "path")
            outputDir = self.p(params, "output_dir", None)
            if not backpackPath:
                return (0, None, ("PARAMS_ERROR", "path required", 0))
            if not os.path.exists(backpackPath):
                return (0, None, ("BACKPACK_NOT_FOUND", backpackPath, 0))
            with open(backpackPath, "rb") as f:
                magic = f.read(4)
                if magic != MAGIC:
                    return (0, None, ("BAD_MAGIC", "Not a backpack file", 0))
                fmtVer = struct.unpack("<I", f.read(4))[0]
                metaLen = struct.unpack("<I", f.read(4))[0]
                metaJson = f.read(metaLen).decode("utf-8")
                metadata = json.loads(metaJson)
                normLen = struct.unpack("<I", f.read(4))[0]
                normJson = f.read(normLen).decode("utf-8")
                normalization = json.loads(normJson)
                wLen = struct.unpack("<I", f.read(4))[0]
                weightsBlob = f.read(wLen)
            if outputDir:
                if not os.path.exists(outputDir):
                    os.makedirs(outputDir, exist_ok=True)
                wPath = os.path.join(outputDir, metadata["name"] + ".weights.bin")
                with open(wPath, "wb") as f:
                    f.write(weightsBlob)
                nPath = os.path.join(outputDir, metadata["name"] + ".norm.json")
                with open(nPath, "w") as f:
                    json.dump(normalization, f, indent=2)
                mPath = os.path.join(outputDir, metadata["name"] + ".meta.json")
                with open(mPath, "w") as f:
                    json.dump(metadata, f, indent=2)
            return (1, {
                "unpacked": metadata["name"],
                "format_version": fmtVer,
                "metadata": metadata,
                "normalization": normalization,
                "weights_bytes": len(weightsBlob),
                "output_dir": outputDir,
            }, None)
        except Exception as e:
            return (0, None, ("UNPACK_ERROR", str(e), 0))

    def cmdInspect(self, params):
        """Inspect a .backpack file without unpacking."""
        try:
            backpackPath = self.p(params, "path")
            if not backpackPath:
                return (0, None, ("PARAMS_ERROR", "path required", 0))
            if not os.path.exists(backpackPath):
                return (0, None, ("BACKPACK_NOT_FOUND", backpackPath, 0))
            with open(backpackPath, "rb") as f:
                magic = f.read(4)
                if magic != MAGIC:
                    return (0, None, ("BAD_MAGIC", "Not a backpack file", 0))
                fmtVer = struct.unpack("<I", f.read(4))[0]
                metaLen = struct.unpack("<I", f.read(4))[0]
                metaJson = f.read(metaLen).decode("utf-8")
                metadata = json.loads(metaJson)
                normLen = struct.unpack("<I", f.read(4))[0]
                normLenActual = normLen
                f.seek(8 + 4 + metaLen + 4 + normLen)
                wLen = struct.unpack("<I", f.read(4))[0]
            fileSize = os.path.getsize(backpackPath)
            return (1, {
                "file": backpackPath,
                "file_size": fileSize,
                "file_size_kb": round(fileSize / 1024, 1),
                "format_version": fmtVer,
                "magic": "BPCK",
                "metadata": metadata,
                "normalization_bytes": normLenActual,
                "weights_bytes": wLen,
                "weights_params": wLen // 4,
            }, None)
        except Exception as e:
            return (0, None, ("INSPECT_ERROR", str(e), 0))

    def cmdListBackpacks(self, params):
        """List all .backpack files in the backpack directory."""
        try:
            if not os.path.exists(BACKPACK_DIR):
                return (1, {"backpacks": [], "total": 0}, None)
            backpacks = []
            for fname in sorted(os.listdir(BACKPACK_DIR)):
                if not fname.endswith(".backpack"):
                    continue
                fpath = os.path.join(BACKPACK_DIR, fname)
                ok, data, _ = self.cmdInspect({"path": fpath})
                if ok:
                    backpacks.append({
                        "file": fname,
                        "name": data["metadata"]["name"],
                        "domain": data["metadata"]["domain"],
                        "version": data["metadata"]["version"],
                        "size_kb": data["file_size_kb"],
                    })
            return (1, {
                "backpacks": backpacks,
                "total": len(backpacks),
                "dir": BACKPACK_DIR,
            }, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def cmdStoreInDB(self, params):
        """Store a .backpack file as a BLOB in the SQLite database."""
        try:
            backpackPath = self.p(params, "path")
            if not backpackPath:
                return (0, None, ("PARAMS_ERROR", "path required", 0))
            if not os.path.exists(backpackPath):
                return (0, None, ("BACKPACK_NOT_FOUND", backpackPath, 0))
            ok, inspectData, inspectErr = self.cmdInspect({"path": backpackPath})
            if not ok:
                return (0, None, inspectErr)
            meta = inspectData["metadata"]
            with open(backpackPath, "rb") as f:
                blob = f.read()
            conn = sqlite3.connect(self.state["config"]["db_path"])
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS backpacks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, domain TEXT, version INTEGER, blob BLOB, created_at REAL, UNIQUE(name, version))"
            )
            conn.execute("UPDATE backpacks SET id=id WHERE 0")
            conn.execute(
                "INSERT OR REPLACE INTO backpacks (name, domain, version, blob, created_at) VALUES (?,?,?,?,?)",
                (meta["name"], meta["domain"], meta["version"], blob, time.time()),
            )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM backpacks").fetchone()[0]
            conn.close()
            return (1, {
                "stored": meta["name"],
                "version": meta["version"],
                "domain": meta["domain"],
                "blob_size": len(blob),
                "total_backpacks_in_db": count,
            }, None)
        except Exception as e:
            return (0, None, ("STORE_DB_ERROR", str(e), 0))

    def cmdLoadFromDB(self, params):
        """Load a backpack from the SQLite database and write to file."""
        try:
            name = self.p(params, "name")
            version = self.p(params, "version", "latest")
            outputPath = self.p(params, "output_path", None)
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            conn = sqlite3.connect(self.state["config"]["db_path"])
            if version == "latest":
                row = conn.execute(
                    "SELECT version, blob FROM backpacks WHERE name=? ORDER BY version DESC LIMIT 1", (name,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT version, blob FROM backpacks WHERE name=? AND version=?", (name, int(version))
                ).fetchone()
            if not row:
                conn.close()
                return (0, None, ("BACKPACK_NOT_IN_DB", name + " v" + str(version), 0))
            ver, blob = row
            if not outputPath:
                outputPath = os.path.join(BACKPACK_DIR, name + ".backpack")
            with open(outputPath, "wb") as f:
                f.write(blob)
            conn.close()
            ok, inspectData, _ = self.cmdInspect({"path": outputPath})
            return (1, {
                "loaded": name,
                "version": ver,
                "path": outputPath,
                "blob_size": len(blob),
                "metadata": inspectData.get("metadata", {}) if ok else {},
            }, None)
        except Exception as e:
            return (0, None, ("LOAD_DB_ERROR", str(e), 0))

    def cmdCreateNorm(self, params):
        """Create a default normalization JSON for 40D features."""
        try:
            mean = [0.5] * INPUT_DIM
            std = [0.25] * INPUT_DIM
            minVal = [0.0] * INPUT_DIM
            maxVal = [1.0] * INPUT_DIM
            norm = {
                "mean": mean,
                "std": std,
                "min": minVal,
                "max": maxVal,
                "method": "minmax_0_1",
                "feature_count": INPUT_DIM,
                "note": "default normalization, replace with measured values",
            }
            return (1, norm, None)
        except Exception as e:
            return (0, None, ("NORM_ERROR", str(e), 0))

    def defaultNormalization(self):
        ok, data, _ = self.cmdCreateNorm({})
        if ok:
            return data
        return {"mean": [0.5] * INPUT_DIM, "std": [0.25] * INPUT_DIM, "method": "minmax_0_1"}

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "backpack_dir": BACKPACK_DIR,
            "format_spec": BACKPACK_FORMAT_SPEC,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
