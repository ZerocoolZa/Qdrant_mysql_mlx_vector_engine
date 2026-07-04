#!/usr/bin/env python3
"""Test PantrySystem: create pantry, append 2 batches, list, load back."""
import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_pantry import PantrySystem

def main():
    pantry_dir = tempfile.mkdtemp(prefix="pantry_test_")
    try:
        ps = PantrySystem(param={"pantry_path": pantry_dir})

        # append batch 1
        seqs1 = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
        ok, data, err = ps.Run("append", {
            "pantry_path": pantry_dir,
            "sequences": seqs1,
            "source": "test_corpus_a",
            "recipe": {"window": 8, "neg": 5, "min_count": 5},
            "vocab_version": 1,
        })
        assert ok == 1, "append1 failed: %r" % (err,)
        assert data["batch_id"] == 1, "expected batch_id=1, got %r" % data["batch_id"]
        assert data["num_sequences"] == 3
        sys.stderr.write("[TEST] append batch 1 OK: %r\n" % data)

        # append batch 2
        seqs2 = [[13, 14, 15], [16, 17, 18, 19, 20]]
        ok, data, err = ps.Run("append", {
            "pantry_path": pantry_dir,
            "sequences": seqs2,
            "source": "test_corpus_b",
            "recipe": {"seq_len": 64, "stride": 32},
            "vocab_version": 1,
        })
        assert ok == 1, "append2 failed: %r" % (err,)
        assert data["batch_id"] == 2
        assert data["num_sequences"] == 2
        sys.stderr.write("[TEST] append batch 2 OK: %r\n" % data)

        # list
        ok, batches, err = ps.Run("list", {"pantry_path": pantry_dir})
        assert ok == 1, "list failed: %r" % (err,)
        assert len(batches) == 2, "expected 2 batches, got %d" % len(batches)
        sys.stderr.write("[TEST] list OK: %d batches\n" % len(batches))
        for b in batches:
            sys.stderr.write("       batch %d: recipe=%r seqs=%d status=%s\n"
                             % (b["batch_id"], b["recipe"], b["num_sequences"], b["status"]))

        # load — stream back
        ok, stream, err = ps.Run("load", {"pantry_path": pantry_dir})
        assert ok == 1, "load failed: %r" % (err,)
        loaded_seqs = []
        loaded_meta = []
        for batch in stream:
            sys.stderr.write("[TEST] load batch %d: %d seqs recipe=%r\n"
                             % (batch["batch_id"], batch["num_sequences"], batch["recipe"]))
            loaded_meta.append((batch["batch_id"], batch["num_sequences"], batch["recipe"]))
            for seq in batch["sequences"]:
                loaded_seqs.append(seq)
        assert len(loaded_meta) == 2, "expected 2 active batches, got %d" % len(loaded_meta)
        # batch 1 sequences first (manifest order), then batch 2
        expected = seqs1 + seqs2
        assert loaded_seqs == expected, "sequences mismatch:\n  got=%r\n  exp=%r" % (loaded_seqs, expected)
        sys.stderr.write("[TEST] load OK: %d sequences round-tripped correctly\n" % len(loaded_seqs))

        # info
        ok, info, err = ps.Run("info", {"pantry_path": pantry_dir})
        assert ok == 1, "info failed: %r" % (err,)
        assert info["total_batches"] == 2
        assert info["active_batches"] == 2
        assert info["obsolete_batches"] == 0
        assert info["total_sequences"] == 5
        sys.stderr.write("[TEST] info OK: %r\n" % info)

        # obsolete batch 1, then verify load only returns batch 2
        ok, data, err = ps.Run("obsolete", {"pantry_path": pantry_dir, "batch_id": 1})
        assert ok == 1, "obsolete failed: %r" % (err,)
        ok, stream, err = ps.Run("load", {"pantry_path": pantry_dir})
        assert ok == 1
        active_ids = [b["batch_id"] for b in stream]
        assert active_ids == [2], "expected only batch 2 active, got %r" % active_ids
        sys.stderr.write("[TEST] obsolete batch 1 OK: active=%r\n" % active_ids)

        # compact: merge obsolete batch 1 into a new batch
        ok, data, err = ps.Run("compact", {"pantry_path": pantry_dir})
        assert ok == 1, "compact failed: %r" % (err,)
        assert data["batch_id"] == 3
        assert data["num_sequences"] == 3  # batch 1 had 3 seqs
        sys.stderr.write("[TEST] compact OK: new batch %d with %d seqs\n"
                         % (data["batch_id"], data["num_sequences"]))

        # verify compacted batch loads with correct sequences
        ok, stream, err = ps.Run("load", {"pantry_path": pantry_dir})
        assert ok == 1
        all_seqs = []
        for batch in stream:
            for seq in batch["sequences"]:
                all_seqs.append(seq)
        # batch 2 (2 seqs) + compacted batch 3 (3 seqs from batch 1)
        assert all_seqs == seqs2 + seqs1, "compact round-trip mismatch:\n  got=%r\n  exp=%r" % (all_seqs, seqs2 + seqs1)
        sys.stderr.write("[TEST] compact load OK: %d sequences\n" % len(all_seqs))

        # read_state
        ok, state, err = ps.Run("read_state", None)
        assert ok == 1
        assert state["batches_appended"] == 2
        sys.stderr.write("[TEST] read_state OK: appended=%d loaded=%d\n"
                         % (state["batches_appended"], state["batches_loaded"]))

        sys.stderr.write("\n[TEST] ALL PASSED\n")
        return 0
    finally:
        shutil.rmtree(pantry_dir, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
