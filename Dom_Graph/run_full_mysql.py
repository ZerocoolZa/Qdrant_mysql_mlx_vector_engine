#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Test runner script for full vb_code_test MySQL scan. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 11 print() calls. Uses if __name__ == '__main__' procedural pattern. Calls Run() on imported engines but file itself is not VBStyle.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Wrap in class with Run() dispatch and Tuple3 returns.>]}
import time
from ir_extractor import IrExtractor
from unit_partitioner import UnitPartitioner
from bcl_db import BclDb

if __name__ == "__main__":
    print("=== FULL vb_code_test (1394 classes, 13818 methods) ===")
    print()

    ext = IrExtractor()
    t0 = time.time()
    r = ext.Run('scan_mysql_parallel', {'db_name': 'vb_code_test', 'workers': 6})
    t1 = time.time()
    print(f"Scan (parallel 6): {t1-t0:.1f}s -> {r[1] if r[0] else r[2]}")

    t0 = time.time()
    ext.Run('classify_all', {})
    t1 = time.time()
    print(f"Classify: {t1-t0:.1f}s")

    rep = ext.Run('report', {})
    d = rep[1]
    ec = d["edge_certainty"]
    mt = d["method_types"]
    total_m = sum(mt.values()) if mt else 1
    print(f"  classes={d['total_classes']} methods={d['total_methods']} edges={d['total_edges']}")
    print(f"  CERTAIN={ec['CERTAIN']} PROBABLE={ec['PROBABLE']} UNKNOWN={ec['UNKNOWN']} ({ec['unknown_pct']}%)")
    print(f"  IO={mt.get('IO',0)} CORE={mt.get('CORE',0)} LINK={mt.get('LINK',0)} INIT={mt.get('INIT',0)}")

    print()
    t0 = time.time()
    part = UnitPartitioner()
    pr = part.Run('partition', {'extractor': ext})
    t1 = time.time()
    print(f"Partition: {t1-t0:.1f}s -> {pr[1] if pr[0] else pr[2]}")

    print()
    t0 = time.time()
    db = BclDb(param={"db_name": "bcl_ir"})
    sr = db.Run('store_all', {
        'extractor': ext,
        'partitioner': part,
        'codebase_name': 'vb_code_test_full'
    })
    t1 = time.time()
    print(f"Store to MySQL: {t1-t0:.1f}s -> {sr[1] if sr[0] else sr[2]}")
