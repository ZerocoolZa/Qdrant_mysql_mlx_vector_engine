#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Benchmark script comparing sequential vs parallel IrExtractor MySQL scanning. NO VBStyle headers (no GHOST/VBSTYLE/FILEID/SUMMARY/CLASS/METHOD). print() x4. No Run() dispatch, no class, no Tuple3 returns. Hardcoded db_name 'vb_code_test'. Not VBStyle compliant -- utility script.>][@todos<1. Add VBStyle identity headers (GHOST/VBSTYLE/FILEID/SUMMARY/CLASS/METHOD). 2. Remove print() calls, use return Tuple3. 3. Wrap in a class with Run() dispatch. 4. Remove hardcoded db_name.>]}
import time
from ir_extractor import IrExtractor

if __name__ == "__main__":
    # Sequential
    ext1 = IrExtractor()
    t0 = time.time()
    ext1.Run('scan_mysql', {'db_name': 'vb_code_test', 'limit': 200})
    t1 = time.time()
    seq_time = t1 - t0
    seq_methods = ext1.state['stats']['total_methods']
    print(f'Sequential (200 classes): {seq_time:.2f}s  methods={seq_methods}')

    # Parallel 4 processes
    ext2 = IrExtractor()
    t0 = time.time()
    ext2.Run('scan_mysql_parallel', {'db_name': 'vb_code_test', 'limit': 200, 'workers': 4})
    t1 = time.time()
    par_time = t1 - t0
    par_methods = ext2.state['stats']['total_methods']
    print(f'Parallel 4 processes:     {par_time:.2f}s  methods={par_methods}')
    print(f'Speedup: {seq_time/par_time:.2f}x')

    # Parallel 8 processes
    ext3 = IrExtractor()
    t0 = time.time()
    ext3.Run('scan_mysql_parallel', {'db_name': 'vb_code_test', 'limit': 200, 'workers': 8})
    t1 = time.time()
    par8_time = t1 - t0
    print(f'Parallel 8 processes:     {par8_time:.2f}s  methods={ext3.state["stats"]["total_methods"]}')
    print(f'Speedup: {seq_time/par8_time:.2f}x')
