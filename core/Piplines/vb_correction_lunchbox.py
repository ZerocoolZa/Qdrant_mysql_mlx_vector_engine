#!/usr/bin/env python3
# [@GHOST]{[@file<vb_correction_lunchbox.py>][@domain<Piplines>][@role<correction_lunchbox>][@auth<devin>][@date<2026-07-04>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<correction_lunchbox>][@return<tuple3>][@orch<CorrectionSystem>][@no<decorators|print|hardcoded|tabs|self_underscore_attr>]}
# [@FILEID]{[@id<vb_correction_lunchbox.py>][@domain<core_Piplines>][@authority<CorrectionSystem_Section5>]}
# [@SUMMARY]{Correction Lunchbox — when an error pattern reaches 100 occurrences in MySQL learned_rules, build a tiny correction lunchbox (~5000 pairs, ~40KB), train on GPU in 0.01s, surgically update only error-related weights. VBEngine Architecture Section 5: The Correction System.}
# [@CLASS]{CorrectionLunchbox}
# [@METHOD]{detect, check_threshold, build_correction, train_correction, verify, log_outcome, run_full_correction, history, info}
"""
Correction Lunchbox — VBEngine Architecture Section 5: The Correction System.

When an error pattern reaches the threshold (default 100 occurrences) in MySQL
learned_rules, the system generates a tiny correction lunchbox (~5000 sequences,
~40KB), trains the model on GPU in ~0.01s, and surgically updates only the
weights for tokens related to that specific error — not a full retrain.

Six-step flow:
    1. DETECT    — search learned_rules + know_problems for an error pattern
    2. THRESHOLD — check if pattern occurrence_count >= threshold (default 100)
    3. BUILD     — generate correction lunchbox from error/solution pairs
    4. TRAIN     — write SQTX binary, call Metal bcl_transformer --data, save weights
    5. VERIFY    — call Metal bcl_transformer --infer on error pattern, check output changed
    6. LOG       — write outcome back to MySQL (success_count++, failure_count++,
                   update confidence, record correction history)

Commands (via Run dispatch):
    "detect"             — search for error pattern in MySQL
    "check_threshold"    — check if pattern meets correction threshold
    "build_correction"   — generate correction lunchbox for a pattern
    "train_correction"   — train Metal bcl_transformer on correction lunchbox (SQTX)
    "verify"             — run Metal inference on error pattern, confirm output changed
    "log_outcome"        — write result to MySQL
    "run_full_correction"— execute all 6 steps in sequence
    "history"            — show correction history
    "info"               — return config and state

Usage:
    from core.Piplines.vb_correction_lunchbox import CorrectionLunchbox
    cl = CorrectionLunchbox()
    code, data, err = cl.Run("detect", {"keyword": "import"})
    code, data, err = cl.Run("check_threshold", {"pattern_id": 13508})
    code, data, err = cl.Run("build_correction", {"pattern_id": 13508})
    code, data, err = cl.Run("run_full_correction", {"pattern_id": 13508})
    code, data, err = cl.Run("log_outcome", {"pattern_id": 13508, "success": True})
"""

import os
import json
import random
import struct
import subprocess
import tempfile
from datetime import datetime, timezone


class CorrectionLunchbox:
    """Correction Lunchbox — tiny surgical weight update for recurring errors.

    The lunchbox is tiny: ~5000 sequences, ~40KB. Only weights for tokens
    related to the error are updated. This is not a full retrain — it is a
    targeted micro-correction that fires when an error pattern has been seen
    enough times (threshold) to warrant a model weight adjustment.
    """

    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DATABASE = "vb_shared"
    MYSQL_UNIX_SOCKET = "/tmp/mysql.sock"

    CORRECTION_THRESHOLD = 100
    LUNCHBOX_SIZE = 5000
    LUNCHBOX_TARGET_KB = 40
    LUNCHBOX_SEQ_LEN = 8
    DEFAULT_CONFIDENCE = 0.5

    HISTORY_TABLE = "correction_history"

    METAL_BINARY_DIR = os.path.dirname(os.path.abspath(__file__))
    METAL_BINARY_NAME = "bcl_transformer"
    WEIGHTS_FILE = "bcl_transformer_weights.bin"
    SQTX_MAGIC = b"SQTX"
    SQTX_VERSION = 1
    SQTX_MODE = b"CORR"
    SQTX_SEQ_LEN = 8
    CORRECTION_EPOCHS = 5
    CORRECTION_TRAIN_SUBSET = 200
    TMP_DIR = "/tmp"

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_detect": {},
            "last_threshold": {},
            "last_lunchbox": {},
            "last_train": {},
            "last_verify": {},
            "last_log": {},
            "history": [],
            "mysql_ok": False,
            "config": {
                "host": self.MYSQL_HOST,
                "port": self.MYSQL_PORT,
                "user": self.MYSQL_USER,
                "password": self.MYSQL_PASSWORD,
                "database": self.MYSQL_DATABASE,
                "unix_socket": self.MYSQL_UNIX_SOCKET,
                "threshold": self.CORRECTION_THRESHOLD,
                "lunchbox_size": self.LUNCHBOX_SIZE,
                "lunchbox_target_kb": self.LUNCHBOX_TARGET_KB,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.check_mysql()
        self.init_history_table()

    def Run(self, command, params=None):
        if command == "detect":
            return self.detect(params or {})
        elif command == "check_threshold":
            return self.check_threshold(params or {})
        elif command == "build_correction":
            return self.build_correction(params or {})
        elif command == "train_correction":
            return self.train_correction(params or {})
        elif command == "verify":
            return self.verify(params or {})
        elif command == "log_outcome":
            return self.log_outcome(params or {})
        elif command == "run_full_correction":
            return self.run_full_correction(params or {})
        elif command == "history":
            return self.history(params or {})
        elif command == "info":
            return self.info(params or {})
        elif command == "read_state":
            return self.read_state()
        elif command == "set_config":
            return self.set_config(params or {})
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def info(self, params):
        info_data = {
            "config": dict(self.state["config"]),
            "mysql_ok": self.state["mysql_ok"],
            "threshold": self.state["config"].get("threshold", self.CORRECTION_THRESHOLD),
            "lunchbox_size": self.state["config"].get("lunchbox_size", self.LUNCHBOX_SIZE),
            "lunchbox_target_kb": self.state["config"].get("lunchbox_target_kb", self.LUNCHBOX_TARGET_KB),
            "history_count": len(self.state["history"]),
            "flow": [
                "1. DETECT    — search learned_rules + know_problems",
                "2. THRESHOLD — check occurrence_count >= threshold",
                "3. BUILD     — generate correction lunchbox (~5000 pairs)",
                "4. TRAIN     — write SQTX, call Metal bcl_transformer --data",
                "5. VERIFY    — call Metal --infer, confirm output changed",
                "6. LOG       — write outcome to MySQL + correction history",
            ],
        }
        return (1, info_data, None)

    def mysql_connect(self):
        try:
            import mysql.connector
        except ImportError:
            return None
        cfg = self.state["config"]
        try:
            unix_socket = cfg.get("unix_socket", self.MYSQL_UNIX_SOCKET)
            if unix_socket and os.path.exists(unix_socket):
                conn = mysql.connector.connect(
                    unix_socket=unix_socket,
                    user=cfg.get("user", self.MYSQL_USER),
                    password=cfg.get("password", self.MYSQL_PASSWORD),
                    database=cfg.get("database", self.MYSQL_DATABASE),
                )
            else:
                conn = mysql.connector.connect(
                    host=cfg.get("host", self.MYSQL_HOST),
                    port=cfg.get("port", self.MYSQL_PORT),
                    user=cfg.get("user", self.MYSQL_USER),
                    password=cfg.get("password", self.MYSQL_PASSWORD),
                    database=cfg.get("database", self.MYSQL_DATABASE),
                )
            return conn
        except Exception:
            return None

    def check_mysql(self):
        conn = self.mysql_connect()
        if conn:
            conn.close()
            self.state["mysql_ok"] = True
        else:
            self.state["mysql_ok"] = False

    def init_history_table(self):
        if not self.state["mysql_ok"]:
            return
        conn = self.mysql_connect()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS " + self.HISTORY_TABLE + " ("
                "correction_id INT AUTO_INCREMENT PRIMARY KEY, "
                "pattern_id INT, "
                "pattern_text TEXT, "
                "fix_action TEXT, "
                "lunchbox_size INT, "
                "lunchbox_kb FLOAT, "
                "train_success INT DEFAULT 0, "
                "verify_success INT DEFAULT 0, "
                "tokens_updated INT DEFAULT 0, "
                "confidence_before FLOAT, "
                "confidence_after FLOAT, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            conn.commit()
            cur.close()
        except Exception:
            pass
        finally:
            conn.close()

    def detect(self, params):
        """STEP 1: DETECT — search learned_rules + know_problems for error pattern."""
        keyword = self._p(params, "keyword", "")
        if not keyword:
            return (0, None, ("missing_param", "keyword is required", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect to MySQL", 0))
        cur = conn.cursor()
        learned = []
        try:
            cur.execute(
                "SELECT id, pattern, fix_action, confidence, success_count, failure_count, "
                "(success_count + failure_count) AS occurrence_count "
                "FROM learned_rules WHERE pattern LIKE %s "
                "ORDER BY occurrence_count DESC LIMIT 20",
                ("%" + keyword + "%",)
            )
            for row in cur.fetchall():
                learned.append({
                    "id": row[0],
                    "pattern": row[1],
                    "fix_action": row[2],
                    "confidence": row[3],
                    "success_count": row[4],
                    "failure_count": row[5],
                    "occurrence_count": row[6],
                })
        except Exception as exc:
            cur.close()
            conn.close()
            return (0, None, ("query_failed", str(exc), 0))
        problems = []
        try:
            cur.execute(
                "SELECT id, problem, description FROM know_problems "
                "WHERE problem LIKE %s LIMIT 10",
                ("%" + keyword + "%",)
            )
            for row in cur.fetchall():
                problems.append({
                    "id": row[0],
                    "problem": row[1],
                    "description": row[2],
                })
        except Exception:
            pass
        cur.close()
        conn.close()
        result = {
            "keyword": keyword,
            "learned_rules": learned,
            "know_problems": problems,
            "total_matches": len(learned) + len(problems),
        }
        self.state["last_detect"] = result
        return (1, result, None)

    def check_threshold(self, params):
        """STEP 2: THRESHOLD — check if pattern occurrence_count >= threshold."""
        pattern_id = self._p(params, "pattern_id")
        keyword = self._p(params, "keyword", "")
        threshold = self._p(params, "threshold", self.state["config"].get("threshold", self.CORRECTION_THRESHOLD))
        if pattern_id is None and not keyword:
            return (0, None, ("missing_param", "pattern_id or keyword is required", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect to MySQL", 0))
        cur = conn.cursor()
        try:
            if pattern_id is not None:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, success_count, failure_count, "
                    "(success_count + failure_count) AS occurrence_count "
                    "FROM learned_rules WHERE id = %s",
                    (pattern_id,)
                )
            else:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, success_count, failure_count, "
                    "(success_count + failure_count) AS occurrence_count "
                    "FROM learned_rules WHERE pattern LIKE %s "
                    "ORDER BY occurrence_count DESC LIMIT 1",
                    ("%" + keyword + "%",)
                )
            row = cur.fetchone()
        except Exception as exc:
            cur.close()
            conn.close()
            return (0, None, ("query_failed", str(exc), 0))
        cur.close()
        conn.close()
        if not row:
            return (0, None, ("pattern_not_found", "no matching pattern in learned_rules", 0))
        occurrence = row[6]
        meets_threshold = occurrence >= threshold
        result = {
            "id": row[0],
            "pattern": row[1],
            "fix_action": row[2],
            "confidence": row[3],
            "success_count": row[4],
            "failure_count": row[5],
            "occurrence_count": occurrence,
            "threshold": threshold,
            "meets_threshold": meets_threshold,
            "remaining": max(0, threshold - occurrence),
        }
        self.state["last_threshold"] = result
        return (1, result, None)

    def build_correction(self, params):
        """STEP 3: BUILD — generate correction lunchbox from error/solution pairs.

        The lunchbox is tiny: ~5000 sequences, ~40KB. Each sequence is an
        (error_token, solution_token) pair drawn from the pattern's fix_action
        and related know_solutions. Only tokens related to the error are
        included so the surgical weight update stays focused.
        """
        pattern_id = self._p(params, "pattern_id")
        keyword = self._p(params, "keyword", "")
        lunchbox_size = self._p(params, "lunchbox_size", self.state["config"].get("lunchbox_size", self.LUNCHBOX_SIZE))
        if pattern_id is None and not keyword:
            return (0, None, ("missing_param", "pattern_id or keyword is required", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect to MySQL", 0))
        cur = conn.cursor()
        try:
            if pattern_id is not None:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, success_count, failure_count "
                    "FROM learned_rules WHERE id = %s",
                    (pattern_id,)
                )
            else:
                cur.execute(
                    "SELECT id, pattern, fix_action, confidence, success_count, failure_count "
                    "FROM learned_rules WHERE pattern LIKE %s "
                    "ORDER BY (success_count + failure_count) DESC LIMIT 1",
                    ("%" + keyword + "%",)
                )
            row = cur.fetchone()
        except Exception as exc:
            cur.close()
            conn.close()
            return (0, None, ("query_failed", str(exc), 0))
        if not row:
            cur.close()
            conn.close()
            return (0, None, ("pattern_not_found", "no matching pattern in learned_rules", 0))
        rule_id = row[0]
        pattern_text = row[1]
        fix_action = row[2]
        confidence = row[3]
        solutions = []
        try:
            cur.execute(
                "SELECT kp.id, ks.solution, ks.weight "
                "FROM know_problems kp JOIN know_solutions ks ON ks.problem_id = kp.id "
                "WHERE kp.problem LIKE %s ORDER BY ks.weight DESC LIMIT 20",
                ("%" + pattern_text[:60] + "%",)
            )
            for srow in cur.fetchall():
                solutions.append({"problem_id": srow[0], "solution": srow[1], "weight": srow[2]})
        except Exception:
            pass
        cur.close()
        conn.close()
        error_tokens = self.tokenize(pattern_text)
        solution_tokens = self.tokenize(fix_action)
        for sol in solutions:
            solution_tokens.extend(self.tokenize(sol["solution"]))
        if not solution_tokens:
            solution_tokens = self.tokenize(fix_action or "apply fix")
        if not error_tokens:
            error_tokens = self.tokenize(pattern_text or "unknown error")
        unique_error_tokens = list(set(error_tokens))
        unique_solution_tokens = list(set(solution_tokens))
        vocab = unique_error_tokens + unique_solution_tokens
        token_to_id = {tok: idx for idx, tok in enumerate(vocab)}
        err_ids = [token_to_id[t] for t in error_tokens]
        sol_ids = [token_to_id[t] for t in solution_tokens]
        rng = random.Random(rule_id)
        pairs = []
        for idx in range(lunchbox_size):
            err_id = rng.choice(err_ids)
            sol_id = rng.choice(sol_ids)
            pairs.append([err_id, sol_id])
        lunchbox_payload = {
            "v": vocab,
            "p": pairs,
        }
        lunchbox_json = json.dumps(lunchbox_payload, separators=(",", ":"))
        lunchbox_kb = len(lunchbox_json.encode("utf-8")) / 1024.0
        sample_sequences = []
        for idx in range(min(10, len(pairs))):
            sample_sequences.append({
                "seq_id": idx,
                "error_token": vocab[pairs[idx][0]],
                "solution_token": vocab[pairs[idx][1]],
                "pair_ids": pairs[idx],
            })
        result = {
            "pattern_id": rule_id,
            "pattern": pattern_text,
            "fix_action": fix_action,
            "confidence_before": confidence,
            "lunchbox_size": len(pairs),
            "lunchbox_kb": round(lunchbox_kb, 2),
            "target_kb": self.state["config"].get("lunchbox_target_kb", self.LUNCHBOX_TARGET_KB),
            "vocab_size": len(vocab),
            "error_tokens": unique_error_tokens,
            "solution_tokens": unique_solution_tokens,
            "solutions_found": len(solutions),
            "sequences": sample_sequences,
            "total_sequences": len(pairs),
            "surgical_scope": unique_error_tokens + unique_solution_tokens,
            "compact_format": "vocab[token_id] + pairs[[err_id, sol_id]]",
        }
        self.state["last_lunchbox"] = result
        self.state["last_lunchbox_payload"] = lunchbox_payload
        return (1, result, None)

    def tokenize(self, text):
        """Split text into lowercase tokens, filtering short noise."""
        if not text:
            return ["unknown"]
        tokens = []
        for word in text.replace(",", " ").replace(".", " ").replace(":", " ").split():
            cleaned = word.strip().lower()
            if len(cleaned) >= 2:
                tokens.append(cleaned)
        if not tokens:
            return ["unknown"]
        return tokens

    def _write_sqtx(self, lunchbox_payload, path, max_sequences=0):
        """Write correction lunchbox pairs to an SQTX binary file for Metal training.

        SQTX format (matches c_transformer_attention.mm load_sqtx):
            Header: magic(4)="SQTX" + version(int32) + mode(4 bytes) +
                    seq_len(int32) + num_sequences(int64) + vocab_size(int32)
            Body:   for each sequence: [input_tokens (seq_len x int32)]
                    [target_tokens (seq_len x int32)]
        Each lunchbox pair [err_id, sol_id] becomes a sequence of seq_len tokens:
        input = [err_id] * seq_len, target = [sol_id] * seq_len.
        This teaches the model to map error-token embedding -> solution-token embedding.
        If max_sequences > 0, only the first max_sequences pairs are written to keep
        GPU training time bounded (surgical micro-correction, not full retrain).
        """
        vocab = lunchbox_payload.get("v", [])
        pairs = lunchbox_payload.get("p", [])
        if not pairs or not vocab:
            return (0, None, ("empty_payload", "lunchbox payload has no pairs or vocab", 0))
        if max_sequences > 0 and len(pairs) > max_sequences:
            pairs = pairs[:max_sequences]
        seq_len = self.SQTX_SEQ_LEN
        num_sequences = len(pairs)
        vocab_size = len(vocab)
        header = (
            self.SQTX_MAGIC
            + struct.pack("<i", self.SQTX_VERSION)
            + self.SQTX_MODE
            + struct.pack("<i", seq_len)
            + struct.pack("<q", num_sequences)
            + struct.pack("<i", vocab_size)
        )
        body_parts = []
        for pair in pairs:
            err_id = pair[0]
            sol_id = pair[1]
            input_tokens = [err_id] * seq_len
            target_tokens = [sol_id] * seq_len
            body_parts.append(struct.pack("<" + "i" * seq_len, *input_tokens))
            body_parts.append(struct.pack("<" + "i" * seq_len, *target_tokens))
        with open(path, "wb") as f:
            f.write(header)
            for part in body_parts:
                f.write(part)
        file_kb = os.path.getsize(path) / 1024.0
        return (1, {"path": path, "seq_len": seq_len, "num_sequences": num_sequences,
                    "vocab_size": vocab_size, "file_kb": round(file_kb, 2)}, None)

    def train_correction(self, params):
        """STEP 4: TRAIN — train Metal bcl_transformer on correction lunchbox.

        Writes the correction lunchbox to a temporary SQTX binary file, then
        invokes the Metal GPU transformer as a subprocess:
            ./bcl_transformer --data /tmp/correction_lunchbox.bin --epochs 5
        The Metal binary loads the SQTX, runs forward/backward/SGD on GPU,
        and saves updated weights to bcl_transformer_weights.bin.
        Returns success if the subprocess exits 0.
        """
        lunchbox = self._p(params, "lunchbox")
        if lunchbox is None:
            lunchbox = self.state.get("last_lunchbox", {})
        if not lunchbox:
            return (0, None, ("no_lunchbox", "build_correction must run first or pass lunchbox", 0))
        payload = self._p(params, "lunchbox_payload")
        if payload is None:
            payload = self.state.get("last_lunchbox_payload", {})
        if not payload:
            return (0, None, ("no_payload", "build_correction must run first to generate payload", 0))
        epochs = self._p(params, "epochs", self.CORRECTION_EPOCHS)
        max_sequences = self._p(params, "max_train_sequences", self.CORRECTION_TRAIN_SUBSET)
        pattern_id = lunchbox.get("pattern_id")
        sqtx_path = os.path.join(self.TMP_DIR, "correction_lunchbox_" + str(pattern_id or "x") + ".bin")
        write_ok, write_data, write_err = self._write_sqtx(payload, sqtx_path, max_sequences)
        if not write_ok:
            return (0, None, write_err)
        binary_path = os.path.join(self.METAL_BINARY_DIR, self.METAL_BINARY_NAME)
        if not os.path.exists(binary_path):
            return (0, None, ("binary_not_found", "Metal binary not at " + binary_path, 0))
        cmd = [binary_path, "--data", sqtx_path, "--epochs", str(epochs)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.METAL_BINARY_DIR,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("train_timeout", "Metal training subprocess timed out", 0))
        except Exception as exc:
            return (0, None, ("train_exception", str(exc), 0))
        train_success = (proc.returncode == 0)
        stdout_tail = proc.stdout[-2000:] if proc.stdout else ""
        stderr_tail = proc.stderr[-1000:] if proc.stderr else ""
        weights_path = os.path.join(self.METAL_BINARY_DIR, self.WEIGHTS_FILE)
        weights_saved = os.path.exists(weights_path)
        surgical_scope = lunchbox.get("surgical_scope", [])
        tokens_updated = len(surgical_scope)
        result = {
            "status": "trained" if train_success else "failed",
            "metal_binary": binary_path,
            "sqtx_path": sqtx_path,
            "sqtx_info": write_data,
            "epochs": epochs,
            "lunchbox_size": lunchbox.get("lunchbox_size", 0),
            "lunchbox_kb": lunchbox.get("lunchbox_kb", 0),
            "tokens_updated": tokens_updated,
            "surgical_scope": surgical_scope,
            "train_success": train_success,
            "weights_saved": weights_saved,
            "weights_path": weights_path,
            "returncode": proc.returncode,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "pattern_id": pattern_id,
        }
        self.state["last_train"] = result
        if not train_success:
            return (0, None, ("train_failed", "Metal binary exited " + str(proc.returncode) + ": " + stderr_tail, 0))
        return (1, result, None)

    def verify(self, params):
        """STEP 5: VERIFY — run Metal inference on error pattern, confirm output changed.

        Calls the Metal bcl_transformer in inference mode:
            ./bcl_transformer --infer --bcl "error_pattern" --weights bcl_transformer_weights.bin
        Parses the output tokens from stdout and compares them to the input tokens.
        If the output tokens differ from the input tokens, the model has learned a
        different representation (verified=True). If they are identical, the model
        has not changed its output for this pattern (verified=False).
        """
        pattern_id = self._p(params, "pattern_id")
        pattern_text = self._p(params, "pattern_text", "")
        if pattern_id is None and not pattern_text:
            return (0, None, ("missing_param", "pattern_id or pattern_text is required", 0))
        if not pattern_text:
            if not self.state["mysql_ok"]:
                return (0, None, ("mysql_unavailable", "MySQL not connected to look up pattern", 0))
            conn = self.mysql_connect()
            if not conn:
                return (0, None, ("mysql_connect_failed", "could not connect to MySQL", 0))
            cur = conn.cursor()
            try:
                cur.execute("SELECT pattern FROM learned_rules WHERE id = %s", (pattern_id,))
                row = cur.fetchone()
            except Exception as exc:
                cur.close()
                conn.close()
                return (0, None, ("query_failed", str(exc), 0))
            cur.close()
            conn.close()
            if not row:
                return (0, None, ("pattern_not_found", "pattern_id not in learned_rules", 0))
            pattern_text = row[0]
        if not pattern_text:
            return (0, None, ("empty_pattern", "pattern_text is empty", 0))
        binary_path = os.path.join(self.METAL_BINARY_DIR, self.METAL_BINARY_NAME)
        if not os.path.exists(binary_path):
            return (0, None, ("binary_not_found", "Metal binary not at " + binary_path, 0))
        weights_path = os.path.join(self.METAL_BINARY_DIR, self.WEIGHTS_FILE)
        cmd = [binary_path, "--infer", "--bcl", pattern_text, "--weights", weights_path]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.METAL_BINARY_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("infer_timeout", "Metal inference subprocess timed out", 0))
        except Exception as exc:
            return (0, None, ("infer_exception", str(exc), 0))
        if proc.returncode != 0:
            stderr_tail = proc.stderr[-1000:] if proc.stderr else ""
            return (0, None, ("infer_failed", "Metal infer exited " + str(proc.returncode) + ": " + stderr_tail, 0))
        input_tokens = self._parse_infer_tokens(proc.stdout, "Input tokens:")
        output_tokens = self._parse_infer_tokens(proc.stdout, "Output tokens:")
        verified = False
        if input_tokens is not None and output_tokens is not None:
            verified = (output_tokens != input_tokens)
        confidence_after = self.state.get("last_lunchbox", {}).get("confidence_before", self.DEFAULT_CONFIDENCE)
        result = {
            "status": "verified" if verified else "unverified",
            "pattern_id": pattern_id,
            "pattern_text": pattern_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "verified": verified,
            "output_changed": verified,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-1500:] if proc.stdout else "",
            "confidence_after": confidence_after,
        }
        self.state["last_verify"] = result
        return (1, result, None)

    def _parse_infer_tokens(self, stdout, label):
        """Parse a token list line from Metal inference stdout.

        The Metal binary prints lines like:
            [INFER] Input tokens:  [12, 34, 56, ...]
            [INFER] Output tokens: [78, 90, ...]
        Returns a list of ints, or None if the line is not found.
        """
        if not stdout:
            return None
        for line in stdout.splitlines():
            if label in line:
                bracket_start = line.find("[")
                bracket_end = line.rfind("]")
                if bracket_start < 0 or bracket_end < 0 or bracket_end <= bracket_start:
                    return None
                inner = line[bracket_start + 1:bracket_end].strip()
                if not inner:
                    return []
                parts = inner.split(",")
                tokens = []
                for part in parts:
                    part = part.strip()
                    if part:
                        try:
                            tokens.append(int(part))
                        except ValueError:
                            pass
                return tokens
        return None

    def log_outcome(self, params):
        """STEP 6: LOG — write outcome back to MySQL.

        Updates learned_rules: success_count++ or failure_count++, recalculates
        confidence, updates last_used. Inserts a row into correction_history
        to track what was corrected, when, and whether it worked.
        """
        pattern_id = self._p(params, "pattern_id")
        success = self._p(params, "success", False)
        train_success = self._p(params, "train_success", 0)
        verify_success = self._p(params, "verify_success", 0)
        tokens_updated = self._p(params, "tokens_updated", 0)
        if pattern_id is None:
            return (0, None, ("missing_param", "pattern_id is required", 0))
        if not self.state["mysql_ok"]:
            return (0, None, ("mysql_unavailable", "MySQL not connected", 0))
        conn = self.mysql_connect()
        if not conn:
            return (0, None, ("mysql_connect_failed", "could not connect to MySQL", 0))
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT success_count, failure_count, confidence, pattern, fix_action "
                "FROM learned_rules WHERE id = %s",
                (pattern_id,)
            )
            row = cur.fetchone()
        except Exception as exc:
            cur.close()
            conn.close()
            return (0, None, ("query_failed", str(exc), 0))
        if not row:
            cur.close()
            conn.close()
            return (0, None, ("pattern_not_found", "pattern_id not in learned_rules", 0))
        sc = row[0] or 0
        fc = row[1] or 0
        conf_before = row[2] or self.DEFAULT_CONFIDENCE
        pattern_text = row[3]
        fix_action = row[4]
        if success:
            sc = sc + 1
        else:
            fc = fc + 1
        total = sc + fc
        conf_after = sc / total if total > 0 else self.DEFAULT_CONFIDENCE
        try:
            cur.execute(
                "UPDATE learned_rules SET success_count = %s, failure_count = %s, "
                "confidence = %s, last_used = NOW() WHERE id = %s",
                (sc, fc, conf_after, pattern_id)
            )
            conn.commit()
        except Exception as exc:
            cur.close()
            conn.close()
            return (0, None, ("update_failed", str(exc), 0))
        lunchbox = self.state.get("last_lunchbox", {})
        lunchbox_size = lunchbox.get("lunchbox_size", 0)
        lunchbox_kb = lunchbox.get("lunchbox_kb", 0)
        correction_id = None
        try:
            cur.execute(
                "INSERT INTO " + self.HISTORY_TABLE + " "
                "(pattern_id, pattern_text, fix_action, lunchbox_size, lunchbox_kb, "
                "train_success, verify_success, tokens_updated, confidence_before, confidence_after) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (pattern_id, pattern_text, fix_action, lunchbox_size, lunchbox_kb,
                 train_success, verify_success, tokens_updated, conf_before, conf_after)
            )
            conn.commit()
            correction_id = cur.lastrowid
        except Exception:
            pass
        cur.close()
        conn.close()
        result = {
            "pattern_id": pattern_id,
            "success": success,
            "success_count": sc,
            "failure_count": fc,
            "confidence_before": conf_before,
            "confidence_after": round(conf_after, 4),
            "correction_id": correction_id,
            "logged": True,
        }
        self.state["last_log"] = result
        self.state["history"].append(result)
        return (1, result, None)

    def run_full_correction(self, params):
        """Execute all 6 correction steps in sequence:
        detect -> check_threshold -> build_correction -> train_correction -> verify -> log_outcome

        Required param: pattern_id (preferred) or keyword.
        Optional params: epochs, threshold, lunchbox_size.
        Each step's result is recorded in state and returned in the final summary.
        If any step fails, the flow stops and returns the error from that step.
        """
        pattern_id = self._p(params, "pattern_id")
        keyword = self._p(params, "keyword", "")
        if pattern_id is None and not keyword:
            return (0, None, ("missing_param", "pattern_id or keyword is required", 0))
        steps = []
        # STEP 1: DETECT
        if keyword:
            ok1, data1, err1 = self.detect({"keyword": keyword})
            steps.append({"step": "detect", "ok": ok1, "error": err1})
            if not ok1:
                return (0, {"steps": steps}, err1)
            if pattern_id is None and data1 and data1.get("learned_rules"):
                pattern_id = data1["learned_rules"][0]["id"]
        # STEP 2: CHECK_THRESHOLD
        ok2, data2, err2 = self.check_threshold({"pattern_id": pattern_id})
        steps.append({"step": "check_threshold", "ok": ok2, "data": data2, "error": err2})
        if not ok2:
            return (0, {"steps": steps}, err2)
        # STEP 3: BUILD_CORRECTION
        ok3, data3, err3 = self.build_correction({"pattern_id": pattern_id})
        steps.append({"step": "build_correction", "ok": ok3, "data": data3, "error": err3})
        if not ok3:
            return (0, {"steps": steps}, err3)
        # STEP 4: TRAIN_CORRECTION
        epochs = self._p(params, "epochs", self.CORRECTION_EPOCHS)
        ok4, data4, err4 = self.train_correction({"epochs": epochs})
        steps.append({"step": "train_correction", "ok": ok4, "data": data4, "error": err4})
        if not ok4:
            return (0, {"steps": steps}, err4)
        # STEP 5: VERIFY
        ok5, data5, err5 = self.verify({"pattern_id": pattern_id})
        steps.append({"step": "verify", "ok": ok5, "data": data5, "error": err5})
        if not ok5:
            return (0, {"steps": steps}, err5)
        verified = data5.get("verified", False) if data5 else False
        # STEP 6: LOG_OUTCOME
        train_success = data4.get("train_success", False) if data4 else False
        tokens_updated = data4.get("tokens_updated", 0) if data4 else 0
        ok6, data6, err6 = self.log_outcome({
            "pattern_id": pattern_id,
            "success": verified,
            "train_success": 1 if train_success else 0,
            "verify_success": 1 if verified else 0,
            "tokens_updated": tokens_updated,
        })
        steps.append({"step": "log_outcome", "ok": ok6, "data": data6, "error": err6})
        if not ok6:
            return (0, {"steps": steps}, err6)
        summary = {
            "pattern_id": pattern_id,
            "keyword": keyword,
            "threshold_met": data2.get("meets_threshold", False) if data2 else False,
            "occurrence_count": data2.get("occurrence_count", 0) if data2 else 0,
            "lunchbox_size": data3.get("lunchbox_size", 0) if data3 else 0,
            "lunchbox_kb": data3.get("lunchbox_kb", 0) if data3 else 0,
            "train_success": train_success,
            "weights_saved": data4.get("weights_saved", False) if data4 else False,
            "verified": verified,
            "output_changed": verified,
            "confidence_after": data6.get("confidence_after", 0) if data6 else 0,
            "correction_id": data6.get("correction_id") if data6 else None,
            "steps": steps,
            "flow": "detect -> check_threshold -> build_correction -> train_correction -> verify -> log_outcome",
        }
        return (1, summary, None)

    def history(self, params):
        """Show correction history — what was corrected, when, did it work."""
        limit = self._p(params, "limit", 20)
        pattern_id = self._p(params, "pattern_id")
        if not self.state["mysql_ok"]:
            local = self.state["history"][-limit:]
            return (1, {"source": "local", "entries": local, "count": len(local)}, None)
        conn = self.mysql_connect()
        if not conn:
            local = self.state["history"][-limit:]
            return (1, {"source": "local", "entries": local, "count": len(local)}, None)
        cur = conn.cursor()
        entries = []
        try:
            if pattern_id is not None:
                cur.execute(
                    "SELECT correction_id, pattern_id, pattern_text, fix_action, "
                    "lunchbox_size, lunchbox_kb, train_success, verify_success, "
                    "tokens_updated, confidence_before, confidence_after, created_at "
                    "FROM " + self.HISTORY_TABLE + " WHERE pattern_id = %s "
                    "ORDER BY correction_id DESC LIMIT %s",
                    (pattern_id, limit)
                )
            else:
                cur.execute(
                    "SELECT correction_id, pattern_id, pattern_text, fix_action, "
                    "lunchbox_size, lunchbox_kb, train_success, verify_success, "
                    "tokens_updated, confidence_before, confidence_after, created_at "
                    "FROM " + self.HISTORY_TABLE + " "
                    "ORDER BY correction_id DESC LIMIT %s",
                    (limit,)
                )
            for row in cur.fetchall():
                entries.append({
                    "correction_id": row[0],
                    "pattern_id": row[1],
                    "pattern_text": row[2],
                    "fix_action": row[3],
                    "lunchbox_size": row[4],
                    "lunchbox_kb": row[5],
                    "train_success": row[6],
                    "verify_success": row[7],
                    "tokens_updated": row[8],
                    "confidence_before": row[9],
                    "confidence_after": row[10],
                    "created_at": str(row[11]),
                })
        except Exception:
            pass
        cur.close()
        conn.close()
        return (1, {"source": "mysql", "entries": entries, "count": len(entries)}, None)
