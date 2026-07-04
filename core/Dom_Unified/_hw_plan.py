import sqlite3

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/_hw_extract.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# Clear old plan
c.execute("DELETE FROM extraction_plan")

plan = [
    # Step 1: Cut HardwareDetector class from GhostQAEngine.py (lines 48-147)
    (1, "CUT", "GhostQAEngine.py", "HardwareDetector", "48-147",
     "core/Dom_Unified/HardwareDetector.py",
     "Cut the VBStyle HardwareDetector class (Run dispatch, Tuple3, __init__(mem,db,param), self.state) from GhostQAEngine.py. This is the base class."),

    # Step 2: Merge detect_all from ModelControlCenter version
    (2, "MERGE", "hardware_detector.py", "HardwareDetector", "24-39",
     "core/Dom_Unified/HardwareDetector.py",
     "Merge detect_all() as a new Run command 'detect'. Provides platform, cpu_brand, ram, disk, gpu, neural_engine, metal in one call. Adapt to VBStyle: return Tuple3."),

    # Step 3: Merge CPU/RAM/Disk/GPU/Neural helpers from ModelControlCenter
    (3, "MERGE", "hardware_detector.py", "HardwareDetector", "41-185",
     "core/Dom_Unified/HardwareDetector.py",
     "Merge get_cpu_cores, get_cpu_brand, get_ram_total_mb, get_ram_available_mb, get_disk_total_mb, get_disk_free_mb, get_gpu_info, get_neural_engine_info, is_metal_supported as private helpers (_prefix). These are called by detect_all."),

    # Step 4: Merge can_download/can_run/check_model from ModelControlCenter
    (4, "MERGE", "hardware_detector.py", "HardwareDetector", "187-247",
     "core/Dom_Unified/HardwareDetector.py",
     "Merge can_download, can_run, check_model, generate_warnings as Run commands. These provide model fit checks. Adapt to VBStyle: return Tuple3."),

    # Step 5: Merge get_summary from ModelControlCenter
    (5, "MERGE", "hardware_detector.py", "HardwareDetector", "249-262",
     "core/Dom_Unified/HardwareDetector.py",
     "Merge get_summary as a Run command 'get_summary'. Returns concise dict for GUI display."),

    # Step 6: Merge _check_ram/_check_cpu/_check_gpu from LocalAgent
    (6, "MERGE", "LocalAgent.py", "LocalAgent", "210-310",
     "core/Dom_Unified/HardwareDetector.py",
     "Merge _check_ram (vm_stat with page_size parsing), _check_cpu (top -l 1), _check_gpu (mlx.core.metal) as Run commands: 'check_ram', 'check_cpu', 'check_gpu'. These provide runtime resource monitoring. Adapt to VBStyle: return Tuple3."),

    # Step 7: Update GhostQAEngine.py to import from new location
    (7, "UPDATE_IMPORT", "GhostQAEngine.py", None, "48-147",
     "GhostQAEngine.py",
     "Remove the HardwareDetector class definition (lines 48-147). Add import: from Dom_Unified.HardwareDetector import HardwareDetector. Keep everything else unchanged."),

    # Step 8: Update ModelControlCenter to import from new location
    (8, "UPDATE_IMPORT", "hardware_detector.py", None, "1-262",
     "ModelControlCenter/model_manager.py",
     "Update model_manager.py import from 'from hardware_detector import HardwareDetector' to 'from Dom_Unified.HardwareDetector import HardwareDetector'. The old hardware_detector.py stays as-is (archived, not deleted)."),

    # Step 9: Validate in DB
    (9, "VALIDATE", None, None, None,
     "core/Dom_Unified/HardwareDetector.py",
     "Run VBStyle checks against merged code in DB: no print(), no @staticmethod/@property/@classmethod, no self._, all methods return Tuple3, Run() exists, __init__(mem,db,param) exists, self.state dict exists."),

    # Step 10: Export to file only after validation passes
    (10, "EXPORT", None, None, None,
     "core/Dom_Unified/HardwareDetector.py",
     "Write the validated merged code from DB to the actual file. Only after all validation checks pass."),

    # Step 11: Archive old files (don't delete)
    (11, "ARCHIVE", "hardware_detector.py", None, None,
     "ModelControlCenter/hardware_detector.py",
     "Old hardware_detector.py stays in place. Not deleted. Just superseded by the unified one."),
]

for step in plan:
    c.execute(
        "INSERT INTO extraction_plan (step, action, source_file, source_class, source_lines, target_file, details) VALUES (?,?,?,?,?,?,?)",
        step,
    )

conn.commit()

print("=== EXTRACTION PLAN (%d steps) ===" % len(plan))
for row in c.execute("SELECT step, action, source_file, source_class, target_file, status FROM extraction_plan ORDER BY step"):
    src = row[2].split("/")[-1] if row[2] else "-"
    tgt = row[4].split("/")[-1] if row[4] else "-"
    print("  Step %d: %s  %s::%s -> %s  [%s]" % (row[0], row[1], src, row[3] or "-", tgt, row[5]))

conn.close()
