#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/_test_sequence_lunchbox.py" date="2026-07-04" author="Cascade" session_id="transformer-lunchbox" context="Test SequenceLunchbox: generate 5 sequences from BCL sample."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3"}

import sys
import os
import struct
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from vb_sequence_lunchbox import SequenceLunchbox

BCL_SAMPLE = """
[@GHOST]{file_path="core/Dom_Bcl/bcl_parser.py" date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix" context="Stage 2 BCL Parser recursive descent tokens in AST out"}
[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
[@FILEID]{id="bcl_parser.py" domain="BCL" authority="BCLParser"}
[@SUMMARY]{summary="BCL Parser token stream in BCLNode AST tree out recursive descent no regex no guessing"}
[@CLASS]{class="BCLParser" domain="BCL" authority="single"}
[@METHOD]{method="Run" type="dispatch"}
[@METHOD]{method="parse" type="command"}
[@METHOD]{method="parse_container" type="command"}
[@METHOD]{method="parse_body" type="command"}
[@METHOD]{method="parse_tuple" type="command"}
[@METHOD]{method="read_state" type="command"}
[@METHOD]{method="set_config" type="command"}
[@METHOD]{method="Peek" type="helper"}
[@METHOD]{method="Advance" type="helper"}
[@METHOD]{method="Expect" type="helper"}
[@METHOD]{method="Parse" type="command"}
[@METHOD]{method="ParseContainer" type="command"}
[@METHOD]{method="ParseBody" type="command"}
[@METHOD]{method="ParseTuple" type="command"}
[@METHOD]{method="_p" type="helper"}
[@METHOD]{method="__init__" type="ctor"}
"""

def main():
    box = SequenceLunchbox()

    # Use small seq_len for test so we get sequences from the sample
    result = box.Run("prepare_bcl", {
        "text": BCL_SAMPLE,
        "output": "/tmp/seq_bcl_test.bin",
        "seq_len": 16,
        "stride": 8,
    })

    if result[0] == 0:
        sys.stderr.write("ERROR: %s\n" % str(result[2]))
        sys.exit(1)

    info = result[1]
    sys.stderr.write("=== prepare_bcl result ===\n")
    sys.stderr.write("output: %s\n" % info["path"])
    sys.stderr.write("num_sequences: %d\n" % info["num_sequences"])
    sys.stderr.write("tokens: %d\n" % info["tokens"])
    sys.stderr.write("vocab_size: %d\n" % info["vocab_size"])
    sys.stderr.write("seq_len: %d\n" % info["seq_len"])
    sys.stderr.write("size_bytes: %d\n" % info["size_bytes"])

    # Read back the binary and show 5 sequences
    path = info["path"]
    with open(path, "rb") as f:
        magic = f.read(4)
        version = struct.unpack("<i", f.read(4))[0]
        mode = f.read(4).rstrip(b"\x00").decode("ascii")
        seq_len = struct.unpack("<i", f.read(4))[0]
        num_sequences = struct.unpack("<q", f.read(8))[0]
        vocab_size = struct.unpack("<i", f.read(4))[0]

        sys.stderr.write("\n=== binary header ===\n")
        sys.stderr.write("magic: %s\n" % magic.decode("ascii"))
        sys.stderr.write("version: %d\n" % version)
        sys.stderr.write("mode: %s\n" % mode)
        sys.stderr.write("seq_len: %d\n" % seq_len)
        sys.stderr.write("num_sequences: %d\n" % num_sequences)
        sys.stderr.write("vocab_size: %d\n" % vocab_size)

        # Build reverse vocab for display
        vocab = box.state["vocab"]
        id_to_word = {v: k for k, v in vocab.items()}

        show = min(5, num_sequences)
        sys.stderr.write("\n=== first %d sequences ===\n" % show)
        for i in range(show):
            input_bytes = f.read(seq_len * 4)
            target_bytes = f.read(seq_len * 4)
            input_ids = np.frombuffer(input_bytes, dtype=np.int32)
            target_ids = np.frombuffer(target_bytes, dtype=np.int32)

            input_words = [id_to_word.get(int(x), "<?>") for x in input_ids]
            target_words = [id_to_word.get(int(x), "<?>") for x in target_ids]

            sys.stderr.write("\n--- sequence %d ---\n" % i)
            sys.stderr.write("INPUT:  %s\n" % " ".join(input_words[:16]))
            sys.stderr.write("TARGET: %s\n" % " ".join(target_words[:16]))
            sys.stderr.write("INPUT_IDS:  %s\n" % list(input_ids[:16]))
            sys.stderr.write("TARGET_IDS: %s\n" % list(target_ids[:16]))

    # Test info command
    info_result = box.Run("info")
    sys.stderr.write("\n=== info ===\n")
    sys.stderr.write("%s\n" % str(info_result[1]))

    # Test chat mode with a synthetic chat file
    chat_path = "/tmp/test_chat_for_seqlunch.md"
    with open(chat_path, "w") as cf:
        cf.write("### User Input\n")
        cf.write("I have a TypeError when calling parse()\n")
        cf.write("### Planner Response\n")
        cf.write("The issue is in the parser. Fix the type check.\n")
        cf.write("### User Input\n")
        cf.write("Now I get a KeyError on the token stream\n")
        cf.write("### Planner Response\n")
        cf.write("KeyError means the token was not found. Add a fallback.\n")

    chat_result = box.Run("prepare_chat", {
        "input_path": chat_path,
        "output": "/tmp/seq_chat_test.bin",
        "seq_len": 16,
        "stride": 8,
    })

    if chat_result[0] == 1:
        chat_info = chat_result[1]
        sys.stderr.write("\n=== prepare_chat result ===\n")
        sys.stderr.write("output: %s\n" % chat_info["path"])
        sys.stderr.write("num_sequences: %d\n" % chat_info["num_sequences"])
        sys.stderr.write("chat_tokens_extracted: %d\n" % chat_info.get("chat_tokens_extracted", 0))
        sys.stderr.write("bcl_text_length: %d\n" % chat_info.get("bcl_text_length", 0))
    else:
        sys.stderr.write("\n=== prepare_chat ERROR: %s ===\n" % str(chat_result[2]))

    sys.stderr.write("\n[TEST] PASSED\n")

if __name__ == "__main__":
    main()
