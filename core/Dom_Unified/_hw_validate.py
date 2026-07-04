import sqlite3
import tempfile
import os
import subprocess

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/_hw_extract.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# Pull merged code from DB
row = c.execute("SELECT source_text, content_hash FROM merged_code WHERE label='HardwareDetector_merged'").fetchone()
merged_src = row[0]
chash = row[1]

print("Retrieved merged code from DB: hash=%s, %d lines" % (chash, len(merged_src.splitlines())))

# Write to temp file, compile, test, then report
tmp_path = "/tmp/_hw_merged_test.py"
with open(tmp_path, "w") as f:
    f.write(merged_src)

# Compile check
result = subprocess.run(["python3", "-m", "py_compile", tmp_path], capture_output=True, text=True)
if result.returncode == 0:
    print("[PASS] py_compile: compiles cleanly")
else:
    print("[FAIL] py_compile: %s" % result.stderr)
    conn.close()
    exit(1)

# Import and functional test
import sys
sys.path.insert(0, "/tmp")

# Rename for import
import shutil
shutil.copy(tmp_path, "/tmp/HardwareDetector.py")

from HardwareDetector import HardwareDetector

hw = HardwareDetector()

tests = [
    ("detect", {}, "platform + cpu_cores + ram_total_mb"),
    ("check_ram", {}, "free_gb"),
    ("check_cpu", {}, "cpu_percent"),
    ("check_gpu", {}, "gpu_available"),
    ("can_download", {"size_mb": 4000}, "can_download"),
    ("can_run", {"size_mb": 4000}, "can_run"),
    ("check_model", {"model": {"name": "bert-base", "size_mb": 4000}}, "overall_ok"),
    ("get_summary", {}, "cpu"),
    ("read_state", {}, "stats"),
    ("set_config", {"ram_safety_margin_mb": 256}, "ram_safety_margin_mb"),
]

all_pass = True
for cmd, params, check_key in tests:
    ok, data, err = hw.Run(cmd, params if params else None)
    if ok:
        val = data.get(check_key, "?") if isinstance(data, dict) else "?"
        print("[PASS] %s: ok=1, %s=%s" % (cmd, check_key, val))
    else:
        print("[FAIL] %s: ok=0, err=%s" % (cmd, err[1] if err else "unknown"))
        all_pass = False

# Test unknown command
ok, data, err = hw.Run("bogus")
if not ok and err:
    print("[PASS] unknown_cmd: ok=0, err=%s" % err[1])
else:
    print("[FAIL] unknown_cmd: should have returned error")
    all_pass = False

# Clean up temp files
os.remove("/tmp/HardwareDetector.py")
os.remove(tmp_path)
if os.path.exists(tmp_path + "c"):
    os.remove(tmp_path + "c")
if os.path.exists("/tmp/HardwareDetector.pyc"):
    os.remove("/tmp/HardwareDetector.pyc")
if os.path.exists("/tmp/__pycache__/HardwareDetector.cpython-313.pyc"):
    os.remove("/tmp/__pycache__/HardwareDetector.cpython-313.pyc")

print()
if all_pass:
    print("ALL FUNCTIONAL TESTS PASSED")
    # Mark steps as done
    c.execute("UPDATE extraction_plan SET status='done' WHERE step IN (1,2,3,4,5,6,9,10)")
    conn.commit()
    print("Steps 1-6, 9-10 marked done in DB. Ready for export.")
else:
    print("FUNCTIONAL TESTS FAILED — do not export")

conn.close()
