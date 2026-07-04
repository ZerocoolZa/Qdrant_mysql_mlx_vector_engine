#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_pantry.py" date="2026-07-04" author="devin" session_id="vb-pantry-system" context="PantrySystem — versioned, append-only training cache for VBEngine. Stores GPU-ready sealed batch files with a manifest.json index. Safe for concurrent reads by multiple training workers."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE spaces only Tuple3 Run dispatch"}
#[@FILEID]{id="vb_pantry.py" domain="Piplines" authority="PantrySystem"}
#[@SUMMARY]{summary="PantrySystem — versioned append-only training cache. Sealed batch files (immutable binary: header + sequences) indexed by manifest.json. Operations: append, list, load, compact, obsolete, info. Concurrent-read safe via atomic manifest reads and immutable batch files."}
#[@CLASS]{class="PantrySystem" domain="Piplines" authority="pantry"}
#[@METHOD]{method="append" type="writer"}
#[@METHOD]{method="list" type="reader"}
#[@METHOD]{method="load" type="reader"}
#[@METHOD]{method="compact" type="writer"}
#[@METHOD]{method="obsolete" type="writer"}
#[@METHOD]{method="info" type="reader"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}

"""PantrySystem — versioned, append-only training cache for VBEngine.

The Pantry is a directory on disk containing:
  pantry/
  ├── manifest.json          (version, recipes, sealed_batches list)
  ├── batch_001.sealed       (immutable binary: header + sequences)
  ├── batch_002.sealed
  └── ...

Each .sealed file is an immutable binary blob:
  [HEADER]
    magic        4 bytes   b"VBP1"
    version      4 bytes   uint32 (little-endian)
    recipe_json  N bytes   JSON recipe dict, length-prefixed (uint32)
    vocab_ver    4 bytes   uint32
    num_seqs     4 bytes   uint32
  [SEQUENCES]
    For each sequence:
      seq_len  4 bytes   uint32
      tokens   seq_len * 4 bytes  uint32 token ids (little-endian)

manifest.json tracks per batch:
  batch_id, source, recipe, num_sequences, created_date,
  status (active/obsolete), vocab_version, file (relative path),
  size_bytes.

Operations (via Run dispatch):
  append   — generate new batch from input sequences, seal it, update manifest
  list     — show all batches, recipes, counts
  load     — read manifest, yield all active batches as a stream (generator)
  compact  — merge obsolete/old batches into one new sealed batch
  obsolete — mark a batch as obsolete (remove from active list, keep file)
  info     — pantry stats (total batches, active, obsolete, total sequences, bytes)

Concurrency:
  Batch files are immutable once sealed — multiple training workers may read
  them simultaneously without locks. The manifest is written atomically (write
  to temp file then os.replace) so readers always see a consistent snapshot.
  Writers (append/compact/obsolete) should be serialized by the caller.
"""

import os
import json
import time
import struct
import tempfile

# ── Error Codes ──
ERR_UNKNOWN_CMD = "PANTRY_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "PANTRY_BAD_PARAMS"
ERR_NO_PANTRY = "PANTRY_NOT_INITIALIZED"
ERR_BATCH_NOT_FOUND = "PANTRY_BATCH_NOT_FOUND"
ERR_SEAL_FAILED = "PANTRY_SEAL_FAILED"
ERR_MANIFEST_IO = "PANTRY_MANIFEST_IO"
ERR_BATCH_IO = "PANTRY_BATCH_IO"
ERR_COMPACT_NO_INPUT = "PANTRY_COMPACT_NO_INPUT"

# ── Constants ──
MAGIC = b"VBP1"
FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
BATCH_PREFIX = "batch_"
BATCH_SUFFIX = ".sealed"
STATUS_ACTIVE = "active"
STATUS_OBSOLETE = "obsolete"


class PantrySystem:
    """Versioned, append-only training cache. File-based (LMDB unavailable)."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.state = {
            "class": "PantrySystem",
            "pantry_path": None,
            "version": FORMAT_VERSION,
            "batches_appended": 0,
            "batches_loaded": 0,
            "last_batch_id": None,
            "last_error": None,
            "config": {},
        }
        if param is not None and isinstance(param, dict):
            path = param.get("pantry_path")
            if path is not None:
                self.state["pantry_path"] = path

    def _p(self, label, value):
        """Helper to record state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "append": self.cmd_append,
            "list": self.cmd_list,
            "load": self.cmd_load,
            "compact": self.cmd_compact,
            "obsolete": self.cmd_obsolete,
            "info": self.cmd_info,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    # ──────────────────────────────────────────────────────────────
    #  COMMANDS
    # ──────────────────────────────────────────────────────────────

    def cmd_append(self, params):
        """Generate a new batch from input sequences, seal it, update manifest.

        params:
          pantry_path  str   (required) pantry directory
          sequences    list  (required) list of token-id lists (uint32)
          source       str   (optional) provenance label, default "unknown"
          recipe       dict  (optional) recipe dict, e.g.
                              {"window": 8, "neg": 5, "min_count": 5}
                              or {"seq_len": 64, "stride": 32}
          vocab_version int  (optional) vocab version int, default 1
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        sequences = params.get("sequences")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        if sequences is None or not isinstance(sequences, list):
            return (0, None, (ERR_BAD_PARAMS, "missing or invalid 'sequences'", 0))
        source = params.get("source", "unknown")
        recipe = params.get("recipe", {})
        if not isinstance(recipe, dict):
            recipe = {}
        vocab_version = params.get("vocab_version", 1)
        if not isinstance(vocab_version, int):
            vocab_version = 1

        ok, err = self.ensure_pantry(pantry_path)
        if not ok:
            return (0, None, err)

        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            manifest = self.fresh_manifest()

        batch_id = self.next_batch_id(manifest)
        filename = BATCH_PREFIX + "%03d" % batch_id + BATCH_SUFFIX
        filepath = os.path.join(pantry_path, filename)

        num_seqs = len(sequences)
        seal_ok = self.seal_batch(filepath, recipe, vocab_version, sequences)
        if not seal_ok:
            return (0, None, (ERR_SEAL_FAILED, "failed to seal batch " + filename, 0))

        size_bytes = os.path.getsize(filepath)
        entry = {
            "batch_id": batch_id,
            "source": source,
            "recipe": recipe,
            "num_sequences": num_seqs,
            "created_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": STATUS_ACTIVE,
            "vocab_version": vocab_version,
            "file": filename,
            "size_bytes": size_bytes,
        }
        manifest["sealed_batches"].append(entry)
        manifest["version"] = FORMAT_VERSION

        write_ok = self.write_manifest_atomic(pantry_path, manifest)
        if not write_ok:
            return (0, None, (ERR_MANIFEST_IO, "failed to write manifest", 0))

        self.state["batches_appended"] = self.state.get("batches_appended", 0) + 1
        self.state["last_batch_id"] = batch_id
        self._p("append", batch_id)
        return (1, entry, None)

    def cmd_list(self, params):
        """List all batches, recipes, counts.

        params:
          pantry_path  str  (required)
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            return (0, None, (ERR_NO_PANTRY, "pantry not initialized at " + pantry_path, 0))
        batches = manifest.get("sealed_batches", [])
        self._p("list", len(batches))
        return (1, batches, None)

    def cmd_load(self, params):
        """Read manifest, return all active batches as a stream (generator).

        Yields one dict per active batch:
          {"batch_id": int, "recipe": dict, "vocab_version": int,
           "num_sequences": int, "sequences": generator-of-lists}

        The 'sequences' value is a generator that yields each token-id list,
        so workers can stream large batches without loading everything at once.

        params:
          pantry_path  str  (required)
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            return (0, None, (ERR_NO_PANTRY, "pantry not initialized at " + pantry_path, 0))

        active = [b for b in manifest.get("sealed_batches", []) if b.get("status") == STATUS_ACTIVE]
        self.state["batches_loaded"] = self.state.get("batches_loaded", 0) + len(active)
        self._p("load", len(active))

        def stream():
            for entry in active:
                filepath = os.path.join(pantry_path, entry["file"])
                seqs = self.iter_sequences(filepath)
                yield {
                    "batch_id": entry["batch_id"],
                    "recipe": entry.get("recipe", {}),
                    "vocab_version": entry.get("vocab_version", 1),
                    "num_sequences": entry.get("num_sequences", 0),
                    "sequences": seqs,
                }

        return (1, stream(), None)

    def cmd_compact(self, params):
        """Merge specified batches (or all obsolete) into one new sealed batch.

        The source batches are marked obsolete after the merge; their files
        are kept on disk (append-only guarantee).

        params:
          pantry_path   str        (required)
          batch_ids     list[int]  (optional) specific batch ids to merge.
                                    If omitted, merges all obsolete batches.
          recipe        dict       (optional) recipe for the merged batch.
                                    Defaults to the recipe of the first source.
          vocab_version int        (optional) defaults to first source's.
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            return (0, None, (ERR_NO_PANTRY, "pantry not initialized at " + pantry_path, 0))

        batches = manifest.get("sealed_batches", [])
        by_id = {b["batch_id"]: b for b in batches}
        requested = params.get("batch_ids")
        if requested is not None:
            if not isinstance(requested, list):
                return (0, None, (ERR_BAD_PARAMS, "batch_ids must be a list", 0))
            sources = [by_id[i] for i in requested if i in by_id]
        else:
            sources = [b for b in batches if b.get("status") == STATUS_OBSOLETE]

        if len(sources) == 0:
            return (0, None, (ERR_COMPACT_NO_INPUT, "no batches to compact", 0))

        merged_sequences = []
        first = sources[0]
        recipe = params.get("recipe", first.get("recipe", {}))
        if not isinstance(recipe, dict):
            recipe = {}
        vocab_version = params.get("vocab_version", first.get("vocab_version", 1))
        if not isinstance(vocab_version, int):
            vocab_version = 1

        for src in sources:
            filepath = os.path.join(pantry_path, src["file"])
            for seq in self.iter_sequences(filepath):
                merged_sequences.append(seq)

        batch_id = self.next_batch_id(manifest)
        filename = BATCH_PREFIX + "%03d" % batch_id + BATCH_SUFFIX
        filepath = os.path.join(pantry_path, filename)
        seal_ok = self.seal_batch(filepath, recipe, vocab_version, merged_sequences)
        if not seal_ok:
            return (0, None, (ERR_SEAL_FAILED, "failed to seal compacted batch", 0))

        size_bytes = os.path.getsize(filepath)
        entry = {
            "batch_id": batch_id,
            "source": "compact:" + ",".join(str(s["batch_id"]) for s in sources),
            "recipe": recipe,
            "num_sequences": len(merged_sequences),
            "created_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": STATUS_ACTIVE,
            "vocab_version": vocab_version,
            "file": filename,
            "size_bytes": size_bytes,
        }
        manifest["sealed_batches"].append(entry)

        # Mark source batches obsolete (keep files, append-only)
        for src in sources:
            for b in manifest["sealed_batches"]:
                if b["batch_id"] == src["batch_id"]:
                    b["status"] = STATUS_OBSOLETE

        write_ok = self.write_manifest_atomic(pantry_path, manifest)
        if not write_ok:
            return (0, None, (ERR_MANIFEST_IO, "failed to write manifest", 0))

        self.state["last_batch_id"] = batch_id
        self._p("compact", batch_id)
        return (1, entry, None)

    def cmd_obsolete(self, params):
        """Mark a batch as obsolete (remove from active list, keep file).

        params:
          pantry_path  str  (required)
          batch_id     int  (required)
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        batch_id = params.get("batch_id")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        if batch_id is None or not isinstance(batch_id, int):
            return (0, None, (ERR_BAD_PARAMS, "missing or invalid 'batch_id'", 0))
        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            return (0, None, (ERR_NO_PANTRY, "pantry not initialized at " + pantry_path, 0))

        found = False
        for b in manifest.get("sealed_batches", []):
            if b["batch_id"] == batch_id:
                b["status"] = STATUS_OBSOLETE
                found = True
                break
        if not found:
            return (0, None, (ERR_BATCH_NOT_FOUND, "batch " + str(batch_id) + " not found", 0))

        write_ok = self.write_manifest_atomic(pantry_path, manifest)
        if not write_ok:
            return (0, None, (ERR_MANIFEST_IO, "failed to write manifest", 0))

        self._p("obsolete", batch_id)
        return (1, {"batch_id": batch_id, "status": STATUS_OBSOLETE}, None)

    def cmd_info(self, params):
        """Pantry stats: total batches, active, obsolete, total sequences, bytes.

        params:
          pantry_path  str  (required)
        """
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        pantry_path = params.get("pantry_path")
        if pantry_path is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'pantry_path'", 0))
        manifest = self.read_manifest(pantry_path)
        if manifest is None:
            return (0, None, (ERR_NO_PANTRY, "pantry not initialized at " + pantry_path, 0))

        batches = manifest.get("sealed_batches", [])
        total = len(batches)
        active = [b for b in batches if b.get("status") == STATUS_ACTIVE]
        obsolete = [b for b in batches if b.get("status") == STATUS_OBSOLETE]
        total_seqs = sum(b.get("num_sequences", 0) for b in batches)
        total_bytes = sum(b.get("size_bytes", 0) for b in batches)
        active_seqs = sum(b.get("num_sequences", 0) for b in active)
        active_bytes = sum(b.get("size_bytes", 0) for b in active)

        info = {
            "version": manifest.get("version", FORMAT_VERSION),
            "pantry_path": pantry_path,
            "total_batches": total,
            "active_batches": len(active),
            "obsolete_batches": len(obsolete),
            "total_sequences": total_seqs,
            "active_sequences": active_seqs,
            "total_bytes": total_bytes,
            "active_bytes": active_bytes,
        }
        self._p("info", total)
        return (1, info, None)

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        self.state["config"] = params
        self._p("config", list(params.keys()))
        return (1, None, None)

    # ──────────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ──────────────────────────────────────────────────────────────

    def ensure_pantry(self, pantry_path):
        """Create pantry directory if needed. Returns (bool, err_tuple)."""
        if pantry_path is None:
            return (False, (ERR_BAD_PARAMS, "pantry_path is None", 0))
        if not os.path.isdir(pantry_path):
            try:
                os.makedirs(pantry_path, exist_ok=True)
            except OSError as exc:
                return (False, (ERR_MANIFEST_IO, "cannot create pantry dir: " + str(exc), 0))
        manifest_path = os.path.join(pantry_path, MANIFEST_NAME)
        if not os.path.exists(manifest_path):
            manifest = self.fresh_manifest()
            ok = self.write_manifest_atomic(pantry_path, manifest)
            if not ok:
                return (False, (ERR_MANIFEST_IO, "cannot write initial manifest", 0))
        return (True, None)

    def fresh_manifest(self):
        """Return a new empty manifest dict."""
        return {
            "version": FORMAT_VERSION,
            "recipes": {},
            "sealed_batches": [],
        }

    def read_manifest(self, pantry_path):
        """Read manifest.json. Returns dict or None."""
        manifest_path = os.path.join(pantry_path, MANIFEST_NAME)
        if not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def write_manifest_atomic(self, pantry_path, manifest):
        """Write manifest.json atomically (temp file + os.replace).

        This ensures concurrent readers always see a complete, valid manifest.
        """
        manifest_path = os.path.join(pantry_path, MANIFEST_NAME)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=pantry_path, prefix=".manifest_", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, manifest_path)
            return True
        except OSError:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False

    def next_batch_id(self, manifest):
        """Return the next sequential batch id (1-based)."""
        batches = manifest.get("sealed_batches", [])
        if len(batches) == 0:
            return 1
        return max(b["batch_id"] for b in batches) + 1

    def seal_batch(self, filepath, recipe, vocab_version, sequences):
        """Write an immutable sealed batch file.

        Format:
          MAGIC (4) | version (4) | recipe_len (4) | recipe_json (N)
          | vocab_version (4) | num_seqs (4)
          | [ seq_len (4) | tokens (seq_len*4) ] ...
        """
        recipe_json = json.dumps(recipe, sort_keys=True).encode("utf-8")
        num_seqs = len(sequences)
        try:
            with open(filepath, "wb") as fh:
                fh.write(MAGIC)
                fh.write(struct.pack("<I", FORMAT_VERSION))
                fh.write(struct.pack("<I", len(recipe_json)))
                fh.write(recipe_json)
                fh.write(struct.pack("<I", vocab_version))
                fh.write(struct.pack("<I", num_seqs))
                for seq in sequences:
                    if not isinstance(seq, (list, tuple)):
                        seq = list(seq)
                    fh.write(struct.pack("<I", len(seq)))
                    if len(seq) > 0:
                        fh.write(struct.pack("<%dI" % len(seq), *seq))
            return True
        except (OSError, struct.error):
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            return False

    def iter_sequences(self, filepath):
        """Yield token-id lists from a sealed batch file (generator).

        Safe for concurrent reads — opens file read-only, no locking.
        """
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "rb") as fh:
                magic = fh.read(4)
                if magic != MAGIC:
                    return
                version = struct.unpack("<I", fh.read(4))[0]
                recipe_len = struct.unpack("<I", fh.read(4))[0]
                fh.read(recipe_len)  # skip recipe (available via manifest)
                vocab_version = struct.unpack("<I", fh.read(4))[0]
                num_seqs = struct.unpack("<I", fh.read(4))[0]
                for _ in range(num_seqs):
                    seq_len = struct.unpack("<I", fh.read(4))[0]
                    if seq_len == 0:
                        yield []
                    else:
                        raw = fh.read(seq_len * 4)
                        yield list(struct.unpack("<%dI" % seq_len, raw))
        except (OSError, struct.error):
            return
