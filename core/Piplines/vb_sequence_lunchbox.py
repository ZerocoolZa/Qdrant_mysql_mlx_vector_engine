#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_sequence_lunchbox.py" date="2026-07-04" author="Cascade" session_id="transformer-lunchbox" context="SequenceLunchbox: BCL packets into input->target token sequences for next-token prediction transformer training."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch spaces only"}
#[@FILEID]{id="vb_sequence_lunchbox.py" domain="Piplines" authority="SequenceLunchbox"}
#[@SUMMARY]{summary="Converts BCL text, Python code, and MySQL learned_rules into input->target token sequences for transformer next-token prediction. Writes packed binary .bin with header + sliding window sequences."}
#[@CLASS]{class="SequenceLunchbox" domain="Piplines" authority="single"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="PrepareBcl" type="command"}
#[@METHOD]{method="PrepareCode" type="command"}
#[@METHOD]{method="PrepareRules" type="command"}
#[@METHOD]{method="PrepareChat" type="command"}
#[@METHOD]{method="Info" type="command"}
#[@METHOD]{method="Tokenize" type="helper"}
#[@METHOD]{method="LoadVocab" type="helper"}
#[@METHOD]{method="BuildSequences" type="helper"}
#[@METHOD]{method="WriteBinary" type="helper"}
#[@METHOD]{method="ScanCodeFiles" type="helper"}
#[@METHOD]{method="QueryRules" type="helper"}
#[@METHOD]{method="RunChatCompressor" type="helper"}
#[@METHOD]{method="_p" type="helper"}
#[@METHOD]{method="read_state" type="command"}
#[@METHOD]{method="set_config" type="command"}
#[@METHOD]{method="__init__" type="ctor"}

"""
SequenceLunchbox -- Transformer Training Data Generator

Converts BCL packets, Python source code, and MySQL learned_rules into
input->target token sequences for next-token prediction.

Three modes:
  bcl   -- BCL text tokenized, sliding window sequences (input=tokens[0:n], target=tokens[1:n+1])
  code  -- Python source tokenized, sliding window sequences
  rules -- MySQL learned_rules (pattern=input, fix_action=target) correction sequences
  chat  -- Chat files run through BclChatCompressor, then BCL output tokenized to sequences

Binary format (SQTX):
  Header: magic(4) + version(4) + mode(4) + seq_len(4) + num_sequences(8) + vocab_size(4)
  Body:   for each sequence: [input_tokens (seq_len int32)] [target_tokens (seq_len int32)]

Usage:
  box.Run("prepare_bcl", {"text": bcl_text, "output": "seq_bcl.bin"})
  box.Run("prepare_code", {"path": "./src", "output": "seq_code.bin"})
  box.Run("prepare_rules", {"output": "seq_rules.bin"})
  box.Run("prepare_chat", {"input_path": "chat.md", "output": "seq_chat.bin"})
  box.Run("info", {})
"""

import os
import re
import sys
import struct
import sqlite3
import numpy as np

PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
WORD_INDEX_DB = os.path.join(PROJECT_DIR, "core", "Piplines", "word_index.db")
SEMANTIC_CORPUS_DB = os.path.join(PROJECT_DIR, "semantic_corpus.db")

MAGIC = b"SQTX"
VERSION = 1
DEFAULT_SEQ_LEN = 256
DEFAULT_STRIDE = 128
UNK_TOKEN = "<UNK>"
UNK_ID = 0

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

SCAN_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".sql", ".sh",
                   ".go", ".c", ".h", ".mm", ".bcl", ".bclir"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".DS_Store", "Archive", "archive",
             "chat_resources", "Cascade_toolStack", "Dom_CoreML_Layout",
             "treasure_trove_backup", ".backup", ".bookmarkai",
             "wordnet_data"}


class SequenceLunchbox:
    """Transformer lunchbox: text in, input->target sequences out."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "seq_len": DEFAULT_SEQ_LEN,
                "stride": DEFAULT_STRIDE,
                "vocab_db": WORD_INDEX_DB,
                "corpus_db": SEMANTIC_CORPUS_DB,
                "mysql_host": "localhost",
                "mysql_user": "root",
                "mysql_password": "",
                "mysql_db": "vb_shared",
            },
            "vocab": {},
            "vocab_size": 0,
            "sequences_generated": 0,
            "last_output": "",
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "prepare_bcl":
            return self.PrepareBcl(params)
        elif command == "prepare_code":
            return self.PrepareCode(params)
        elif command == "prepare_rules":
            return self.PrepareRules(params)
        elif command == "prepare_chat":
            return self.PrepareChat(params)
        elif command == "info":
            return self.Info(params)
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

    def Info(self, params):
        config = dict(self.state["config"])
        info = {
            "magic": MAGIC.decode("ascii"),
            "version": VERSION,
            "modes": ["bcl", "code", "rules", "chat"],
            "seq_len": config["seq_len"],
            "stride": config["stride"],
            "vocab_size": self.state["vocab_size"],
            "sequences_generated": self.state["sequences_generated"],
            "vocab_db": config["vocab_db"],
            "corpus_db": config["corpus_db"],
            "unk_token": UNK_TOKEN,
            "unk_id": UNK_ID,
        }
        return (1, info, None)

    def LoadVocab(self, params=None):
        """Load vocab from word_index.db. Falls back to semantic_corpus.db if empty."""
        vocab = {}
        vocab_db = self.state["config"]["vocab_db"]
        corpus_db = self.state["config"]["corpus_db"]

        if os.path.exists(vocab_db) and os.path.getsize(vocab_db) > 0:
            try:
                conn = sqlite3.connect(vocab_db)
                cur = conn.execute("SELECT word, idx FROM word_index")
                for word, idx in cur.fetchall():
                    vocab[word.lower()] = idx
                conn.close()
            except Exception:
                pass

        if len(vocab) == 0 and os.path.exists(corpus_db):
            try:
                conn = sqlite3.connect(corpus_db)
                cur = conn.execute("SELECT term FROM embeddings ORDER BY term")
                idx = 1
                for (term,) in cur.fetchall():
                    vocab[term.lower()] = idx
                    idx += 1
                conn.close()
            except Exception:
                pass

        if len(vocab) == 0:
            return (0, None, ("VOCAB_EMPTY", "No vocab found in word_index.db or semantic_corpus.db", 0))

        vocab[UNK_TOKEN] = UNK_ID
        self.state["vocab"] = vocab
        self.state["vocab_size"] = len(vocab)
        return (1, {"vocab_size": len(vocab), "unk_id": UNK_ID}, None)

    def Tokenize(self, text, mode="bcl"):
        """Tokenize text into lowercase token strings."""
        if mode == "bcl":
            tokens = TOKEN_RE.findall(text)
        elif mode == "code":
            tokens = TOKEN_RE.findall(text)
        else:
            tokens = TOKEN_RE.findall(text)
        return [t.lower() for t in tokens if len(t) >= 1]

    def TokensToIds(self, tokens):
        """Convert token strings to integer ids using vocab. Unknown -> UNK_ID."""
        vocab = self.state["vocab"]
        ids = []
        for t in tokens:
            ids.append(vocab.get(t, UNK_ID))
        return ids

    def BuildSequences(self, token_ids, seq_len, stride):
        """Build sliding window sequences: input=tokens[0:n], target=tokens[1:n+1]."""
        sequences = []
        n = len(token_ids)
        if n < seq_len + 1:
            return sequences
        i = 0
        while i + seq_len + 1 <= n:
            input_ids = token_ids[i:i + seq_len]
            target_ids = token_ids[i + 1:i + seq_len + 1]
            sequences.append((input_ids, target_ids))
            i += stride
        return sequences

    def WriteBinary(self, path, mode, seq_len, sequences, vocab_size):
        """Write packed binary file with SQTX header + sequences."""
        num_sequences = len(sequences)
        mode_bytes = mode.encode("utf-8").ljust(4, b"\x00")[:4]

        with open(path, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack("<i", VERSION))
            f.write(mode_bytes)
            f.write(struct.pack("<i", seq_len))
            f.write(struct.pack("<q", num_sequences))
            f.write(struct.pack("<i", vocab_size))

            for input_ids, target_ids in sequences:
                input_arr = np.array(input_ids, dtype=np.int32)
                target_arr = np.array(target_ids, dtype=np.int32)
                f.write(input_arr.tobytes())
                f.write(target_arr.tobytes())

        size_bytes = os.path.getsize(path)
        return (1, {"path": path, "num_sequences": num_sequences,
                    "size_bytes": size_bytes, "vocab_size": vocab_size,
                    "seq_len": seq_len, "mode": mode}, None)

    def PrepareBcl(self, params):
        """Take BCL text or file path, generate sequences, write to .bin."""
        text = self._p(params, "text")
        path = self._p(params, "path")
        output = self._p(params, "output", "seq_bcl.bin")
        seq_len = self._p(params, "seq_len", self.state["config"]["seq_len"])
        stride = self._p(params, "stride", self.state["config"]["stride"])

        if text is None and path is not None:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError as exc:
                return (0, None, ("FILE_READ_FAILED", str(exc), 0))
        if text is None:
            return (0, None, ("MISSING_PARAM", "text or path required", 0))

        vocab_result = self.LoadVocab()
        if vocab_result[0] == 0:
            return vocab_result

        tokens = self.Tokenize(text, mode="bcl")
        token_ids = self.TokensToIds(tokens)
        sequences = self.BuildSequences(token_ids, seq_len, stride)

        if len(sequences) == 0:
            return (0, None, ("NO_SEQUENCES", "Text too short for seq_len=%d" % seq_len, 0))

        write_result = self.WriteBinary(output, "bcl", seq_len, sequences, self.state["vocab_size"])
        if write_result[0] == 0:
            return write_result

        self.state["sequences_generated"] = len(sequences)
        self.state["last_output"] = output
        result = write_result[1]
        result["tokens"] = len(tokens)
        result["vocab_size"] = self.state["vocab_size"]
        return (1, result, None)

    def ScanCodeFiles(self, root_path):
        """Scan directory for source files, return list of (filepath, content)."""
        files = []
        if os.path.isfile(root_path):
            ext = os.path.splitext(root_path)[1].lower()
            if ext in SCAN_EXTENSIONS or ext == ".py":
                try:
                    with open(root_path, "r", encoding="utf-8", errors="ignore") as f:
                        files.append((root_path, f.read()))
                except OSError:
                    pass
            return files

        for root, dirs, filenames in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SCAN_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    files.append((fpath, content))
                except OSError:
                    pass
        return files

    def PrepareCode(self, params):
        """Take Python file/dir, generate sequences, write to .bin."""
        path = self._p(params, "path")
        output = self._p(params, "output", "seq_code.bin")
        seq_len = self._p(params, "seq_len", self.state["config"]["seq_len"])
        stride = self._p(params, "stride", self.state["config"]["stride"])

        if path is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))

        vocab_result = self.LoadVocab()
        if vocab_result[0] == 0:
            return vocab_result

        files = self.ScanCodeFiles(path)
        if len(files) == 0:
            return (0, None, ("NO_FILES", "No source files found at %s" % path, 0))

        all_token_ids = []
        for fpath, content in files:
            tokens = self.Tokenize(content, mode="code")
            ids = self.TokensToIds(tokens)
            all_token_ids.extend(ids)

        sequences = self.BuildSequences(all_token_ids, seq_len, stride)
        if len(sequences) == 0:
            return (0, None, ("NO_SEQUENCES", "Corpus too short for seq_len=%d" % seq_len, 0))

        write_result = self.WriteBinary(output, "code", seq_len, sequences, self.state["vocab_size"])
        if write_result[0] == 0:
            return write_result

        self.state["sequences_generated"] = len(sequences)
        self.state["last_output"] = output
        result = write_result[1]
        result["files_scanned"] = len(files)
        result["total_tokens"] = len(all_token_ids)
        return (1, result, None)

    def QueryRules(self, params):
        """Query MySQL learned_rules table for (pattern, fix_action) pairs."""
        cfg = self.state["config"]
        host = cfg.get("mysql_host", "localhost")
        user = cfg.get("mysql_user", "root")
        password = cfg.get("mysql_password", "")
        database = cfg.get("mysql_db", "vb_shared")
        limit = self._p(params, "limit", 0)
        min_confidence = self._p(params, "min_confidence", 0.0)

        try:
            import pymysql
            conn = pymysql.connect(host=host, user=user, password=password,
                                   database=database, charset="utf8mb4")
        except Exception:
            try:
                import MySQLdb
                conn = MySQLdb.connect(host=host, user=user, passwd=password,
                                       db=database, charset="utf8mb4")
            except Exception as exc:
                return (0, None, ("MYSQL_CONNECT_FAILED", str(exc), 0))

        query = "SELECT pattern, fix_action FROM learned_rules WHERE fix_action IS NOT NULL AND fix_action != ''"
        if min_confidence > 0:
            query += " AND confidence >= %s" % str(min_confidence)
        query += " ORDER BY confidence DESC"
        if limit > 0:
            query += " LIMIT %d" % limit

        try:
            cur = conn.execute(query) if hasattr(conn, "execute") else conn.cursor()
            rows = cur.fetchall() if hasattr(cur, "fetchall") else conn.fetchall()
        except Exception as exc:
            conn.close()
            return (0, None, ("MYSQL_QUERY_FAILED", str(exc), 0))

        conn.close()
        return (1, rows, None)

    def PrepareRules(self, params):
        """Query MySQL learned_rules, generate correction sequences, write to .bin."""
        output = self._p(params, "output", "seq_rules.bin")
        seq_len = self._p(params, "seq_len", self.state["config"]["seq_len"])
        stride = self._p(params, "stride", self.state["config"]["stride"])
        limit = self._p(params, "limit", 0)
        min_confidence = self._p(params, "min_confidence", 0.0)

        vocab_result = self.LoadVocab()
        if vocab_result[0] == 0:
            return vocab_result

        rules_result = self.QueryRules({"limit": limit, "min_confidence": min_confidence})
        if rules_result[0] == 0:
            return rules_result

        rows = rules_result[1]
        if len(rows) == 0:
            return (0, None, ("NO_RULES", "No learned_rules found in MySQL", 0))

        sequences = []
        for row in rows:
            pattern_text = str(row[0]) if row[0] else ""
            fix_text = str(row[1]) if row[1] else ""

            pattern_tokens = self.Tokenize(pattern_text, mode="bcl")
            fix_tokens = self.Tokenize(fix_text, mode="bcl")

            pattern_ids = self.TokensToIds(pattern_tokens)
            fix_ids = self.TokensToIds(fix_tokens)

            combined = pattern_ids + fix_ids
            if len(combined) < 2:
                continue

            padded = combined[:seq_len + 1]
            while len(padded) < seq_len + 1:
                padded.append(UNK_ID)

            input_ids = padded[:seq_len]
            target_ids = padded[1:seq_len + 1]
            sequences.append((input_ids, target_ids))

        if len(sequences) == 0:
            return (0, None, ("NO_SEQUENCES", "No valid rule sequences generated", 0))

        write_result = self.WriteBinary(output, "rules", seq_len, sequences, self.state["vocab_size"])
        if write_result[0] == 0:
            return write_result

        self.state["sequences_generated"] = len(sequences)
        self.state["last_output"] = output
        result = write_result[1]
        result["rules_queried"] = len(rows)
        return (1, result, None)

    def PrepareChat(self, params):
        """Take chat file, run BclChatCompressor, convert BCL output to sequences, write to .bin."""
        input_path = self._p(params, "input_path")
        output = self._p(params, "output", "seq_chat.bin")
        seq_len = self._p(params, "seq_len", self.state["config"]["seq_len"])
        stride = self._p(params, "stride", self.state["config"]["stride"])

        if input_path is None:
            return (0, None, ("MISSING_PARAM", "input_path required", 0))

        if not os.path.exists(input_path):
            return (0, None, ("FILE_NOT_FOUND", "Chat file not found: %s" % input_path, 0))

        vocab_result = self.LoadVocab()
        if vocab_result[0] == 0:
            return vocab_result

        compressor_result = self.RunChatCompressor(input_path)
        if compressor_result[0] == 0:
            return compressor_result

        bcl_text = compressor_result[1]["bcl_text"]
        token_count = compressor_result[1]["token_count"]

        tokens = self.Tokenize(bcl_text, mode="bcl")
        token_ids = self.TokensToIds(tokens)
        sequences = self.BuildSequences(token_ids, seq_len, stride)

        if len(sequences) == 0:
            return (0, None, ("NO_SEQUENCES", "Compressed BCL too short for seq_len=%d" % seq_len, 0))

        write_result = self.WriteBinary(output, "chat", seq_len, sequences, self.state["vocab_size"])
        if write_result[0] == 0:
            return write_result

        self.state["sequences_generated"] = len(sequences)
        self.state["last_output"] = output
        result = write_result[1]
        result["chat_tokens_extracted"] = token_count
        result["bcl_text_length"] = len(bcl_text)
        return (1, result, None)

    def RunChatCompressor(self, input_path):
        """Run BclChatCompressor on chat file, return BCL text output."""
        chat_compressor_path = os.path.join(PROJECT_DIR, "chat_mover")
        if chat_compressor_path not in sys.path:
            sys.path.insert(0, chat_compressor_path)

        try:
            from bcl_chat_compressor import BclChatCompressor
        except ImportError as exc:
            return (0, None, ("IMPORT_FAILED", "Cannot import BclChatCompressor: %s" % str(exc), 0))

        compressor = BclChatCompressor()
        compress_result = compressor.Run("dry_run", {
            "input_path": input_path,
        })

        if compress_result[0] == 0:
            return compress_result

        data = compress_result[1]
        bcl_text = data.get("output_text", "")
        token_count = data.get("token_count", 0)

        if len(bcl_text) == 0:
            return (0, None, ("EMPTY_BCL", "BclChatCompressor produced empty output", 0))

        return (1, {"bcl_text": bcl_text, "token_count": token_count}, None)


def Main():
    box = SequenceLunchbox()

    if len(sys.argv) < 2:
        info = box.Run("info")[1]
        sys.stderr.write("SequenceLunchbox -- Transformer Training Data Generator\n")
        sys.stderr.write("Modes: bcl, code, rules, chat\n")
        sys.stderr.write("Usage:\n")
        sys.stderr.write("  python3 vb_sequence_lunchbox.py prepare_bcl --text '...' --output seq.bin\n")
        sys.stderr.write("  python3 vb_sequence_lunchbox.py prepare_code --path ./src --output seq.bin\n")
        sys.stderr.write("  python3 vb_sequence_lunchbox.py prepare_rules --output seq.bin\n")
        sys.stderr.write("  python3 vb_sequence_lunchbox.py prepare_chat --input_path chat.md --output seq.bin\n")
        sys.stderr.write("  python3 vb_sequence_lunchbox.py info\n")
        return

    command = sys.argv[1]
    params = {}
    i = 2
    while i < len(sys.argv) - 1:
        key = sys.argv[i]
        if key.startswith("--"):
            key = key[2:]
            params[key] = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    result = box.Run(command, params)
    if result[0] == 1:
        sys.stderr.write("[SEQLUNCH] OK: %s\n" % str(result[1]))
    else:
        sys.stderr.write("[SEQLUNCH] ERROR: %s\n" % str(result[2]))


if __name__ == "__main__":
    Main()
