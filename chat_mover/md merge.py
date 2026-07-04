#!/usr/bin/env python3

from pathlib import Path
import shutil

# ==========================================================
# CONFIG
# ==========================================================

BASE = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover")
OUT_DIR = BASE / "PLF_"
OUT_FILE = OUT_DIR / "CLI Error Prevention.md"

FILES = [
    BASE / "CLI Error Prevention_AI_PROMPT.md",
    BASE / "CLI Error Prevention_BCL_stage1.md",
    BASE / "CLI_Error_Prevention_AI_PROMPT.md",
    BASE / "CLI_Error_Prevention_BCL_stage1.md",
    BASE / "CLI_Error_Prevention_BCL_v2.md",
    BASE / "CLI_Error_Prevention_BCL.md",
]

# ==========================================================
# CREATE OUTPUT DIRECTORY
# ==========================================================

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================================
# MERGE
# ==========================================================

written = []

with OUT_FILE.open("w", encoding="utf-8") as out:

    out.write("# CLI Error Prevention\n\n")

    for file in FILES:

        if not file.exists():
            print(f"Missing: {file.name}")
            continue

        written.append(file)

        out.write("\n")
        out.write("=" * 80 + "\n")
        out.write(f"# {file.name}\n")
        out.write("=" * 80 + "\n\n")

        with file.open("r", encoding="utf-8") as f:
            shutil.copyfileobj(f, out)

        out.write("\n\n")

print(f"\nCreated:\n{OUT_FILE}")

# ==========================================================
# DELETE ORIGINALS ONLY IF MERGE SUCCEEDED
# ==========================================================

if OUT_FILE.exists() and OUT_FILE.stat().st_size > 0:

    print("\nRemoving originals...\n")

    for file in written:
        try:
            file.unlink()
            print(f"Deleted: {file.name}")
        except Exception as e:
            print(f"Failed: {file.name} ({e})")

    print("\nDone.")

else:
    print("\nMerge failed. Original files were NOT deleted.")