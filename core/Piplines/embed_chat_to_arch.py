#!/usr/bin/env python3
"""
embed_chat_to_arch.py
Embeds the source chat transcript into VBENGINE_ARCHITECTURE.md as gzip+base64.

Usage:
    python3 embed_chat_to_arch.py

Reads:
  - ~/Downloads/Optimizing Word2Vec Metal Trainer.md  (source chat)
  - core/Piplines/VBENGINE_ARCHITECTURE.md            (target doc)

Writes:
  - Appends compressed chat as base64 block to the end of the architecture doc.
"""

import gzip
import base64
import os
import hashlib
from datetime import datetime
from pathlib import Path

CHAT_SOURCE = os.path.expanduser("~/Downloads/Optimizing Word2Vec Metal Trainer.md")
ARCH_DOC = os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine/core/Piplines/VBENGINE_ARCHITECTURE.md")

def main():
    # Read chat
    with open(CHAT_SOURCE, "rb") as f:
        chat_bytes = f.read()
    chat_size = len(chat_bytes)
    chat_md5 = hashlib.md5(chat_bytes).hexdigest()

    # Compress
    compressed = gzip.compress(chat_bytes, compresslevel=9)
    comp_size = len(compressed)

    # Base64 encode
    b64_bytes = base64.b64encode(compressed)
    b64_str = b64_bytes.decode("ascii")
    b64_size = len(b64_str)

    # Read existing arch doc
    with open(ARCH_DOC, "r") as f:
        arch_content = f.read()

    # Check if already embedded
    if "BEGIN_VBENGINE_CHAT" in arch_content:
        # Strip old embed
        idx = arch_content.find("<!-- BEGIN_VBENGINE_CHAT -->")
        if idx > 0:
            # Find the line before the marker
            arch_content = arch_content[:idx].rstrip()
            print(f"Stripped old embed, arch now {len(arch_content)} bytes")

    # Build appendix
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    appendix = f"""

---

## Appendix A: Source Chat Transcript

> **File**: `Optimizing Word2Vec Metal Trainer.md`
> **Location**: `~/Downloads/`
> **Original size**: {chat_size:,} bytes ({chat_size/1024:.0f} KB)
> **Compressed**: gzip level 9 -> {comp_size:,} bytes ({comp_size/1024:.0f} KB)
> **Base64 encoded**: {b64_size:,} bytes ({b64_size/1024:.0f} KB)
> **MD5**: `{chat_md5}`
> **Date embedded**: {now}
> **Description**: Full conversation between WWS and Cascade that designed and proved the VBEngine architecture. From initial fp32 baseline through packed pairs, fully-packed experiments, pantry concept, and correction system design.
> **Encoding**: base64(gzip(markdown))
> **To extract**:
> ```bash
> python3 -c "
> import re, base64, gzip
> doc = open('VBENGINE_ARCHITECTURE.md').read()
> m = re.search(r'<!-- BEGIN_VBENGINE_CHAT -->\\n(.*?)\\n<!-- END_VBENGINE_CHAT -->', doc, re.DOTALL)
> open('chat.md','wb').write(gzip.decompress(base64.b64decode(m.group(1))))
> "
> ```

<!-- BEGIN_VBENGINE_CHAT -->
{b64_str}
<!-- END_VBENGINE_CHAT -->
"""

    # Write combined
    with open(ARCH_DOC, "w") as f:
        f.write(arch_content + appendix)

    final_size = os.path.getsize(ARCH_DOC)
    print(f"Done. Architecture doc: {final_size:,} bytes ({final_size/1024:.0f} KB)")
    print(f"  Chat: {chat_size:,} -> gzip {comp_size:,} -> base64 {b64_size:,}")
    print(f"  Ratio: {b64_size/chat_size*100:.1f}% of original")

if __name__ == "__main__":
    main()
