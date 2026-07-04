#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Populates runtime digital twin with mac_server.c data. No #[@...] headers. No Run dispatch. No Tuple3 returns. No class. Has hardcoded absolute paths (SCHEMA, DB, SOURCE in /Users/wws/Downloads/). Uses pass statements. Has print comment.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Wrap in class with Run dispatch and Tuple3. Remove hardcoded absolute paths. Move to Config.py.>]}
"""
Populate the runtime digital twin with mac_server.c data.
Every function, lock, buffer, syscall, and state becomes a runtime actor.
"""
import sqlite3, os, re, time
SCHEMA = "/Users/wws/Downloads/runtime_twin_schema.sql"
DB = "/Users/wws/Downloads/runtime_twin.db"
SOURCE = "/Users/wws/Downloads/mac_server.c"
def main():
    # Fresh DB
    if os.path.exists(DB):
        os.remove(DB)
    
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # Load schema
    with open(SCHEMA, "r") as f:
        cur.executescript(f.read())
    conn.commit()
    pass  # VBStyle: no print
    
    # ─── Parse mac_server.c to extract AST nodes ───
    with open(SOURCE, "r") as f:
        content = f.read()
    lines = content.split("\n")
    
    # Find struct/class blocks and functions
    # Pattern: typedef struct Name { ... } Name;
    # Pattern: static int Name( ... ) {
    # Pattern: static void Name( ... ) {
    
    structs = []
    functions = []
    
    # Find typedef structs (our "classes")
    for i, line in enumerate(lines):
        m = re.match(r'^typedef struct (\w+) \{', line)
        if m:
            name = m.group(1)
            # Find closing brace
            depth = 1
            end = i + 1
            while end < len(lines) and depth > 0:
                depth += lines[end].count("{") - lines[end].count("}")
                if depth <= 0:
                    break
                end += 1
            structs.append({"name": name, "line_start": i+1, "line_end": end+1})
    
    # Find functions
    for i, line in enumerate(lines):
        m = re.match(r'^static (int|void|CGImageRef|int\d_t) (\w+)\(', line)
        if not m:
            m = re.match(r'^static (int|void) (\w+)\(', line)
        if m:
            ret_type = m.group(1)
            name = m.group(2)
            # Find which struct it belongs to
            parent = None
            for s in structs:
                if name.startswith(s["name"] + "_") or name.startswith(s["name"]):
                    parent = s["name"]
                    break
            
            # Find end of function
            depth = 0
            end = i
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and j > i:
                    end = j
                    break
            
            functions.append({
                "name": name,
                "ret_type": ret_type,
                "line_start": i+1,
                "line_end": end+1,
                "parent_struct": parent,
                "body": "\n".join(lines[i:end+1]),
            })
    
    # Also find main()
    for i, line in enumerate(lines):
        if re.match(r'^int main\(', line):
            depth = 0
            end = i
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and j > i:
                    end = j
                    break
            functions.append({
                "name": "main",
                "ret_type": "int",
                "line_start": i+1,
                "line_end": end+1,
                "parent_struct": None,
                "body": "\n".join(lines[i:end+1]),
            })
    
    pass  # VBStyle: no print
    
    # ─── Insert AST nodes ───
    # Structs as container nodes
    struct_ids = {}
    for s in structs:
        cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, line_end, language, is_entry_point)
            VALUES ('struct', ?, ?, ?, ?, ?, 'c', 0)""",
            (s["name"], s["name"], "mac_server.c", s["line_start"], s["line_end"]))
        struct_ids[s["name"]] = cur.lastrowid
    
    # Functions as function nodes
    func_ids = {}
    for f in functions:
        parent_id = struct_ids.get(f["parent_struct"]) if f["parent_struct"] else None
        cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, line_end, language, parent_node_id, is_entry_point)
            VALUES ('function', ?, ?, ?, ?, ?, 'c', ?, ?)""",
            (f["name"], f["name"], "mac_server.c", f["line_start"], f["line_end"], parent_id, 1 if f["name"] == "main" else 0))
        func_ids[f["name"]] = cur.lastrowid
    
    # ─── Extract sub-nodes from function bodies ───
    # Locks, syscalls, allocations, branches, buffers
    
    LOCK_RE = re.compile(r'pthread_mutex_(lock|init|destroy|unlock)\w*\(')
    MUTEX_RE = re.compile(r'\b(\w+Lock|\w+_lock|frameLock)\b')
    SYSCALL_RE = re.compile(r'\b(send|recv|socket|bind|listen|accept|close|fcntl|read|write)\s*\(')
    ALLOC_RE = re.compile(r'\b(malloc|calloc|realloc|memset|memcpy|CFDataCreate|CFRelease|CGImageRelease|CGDataProviderCreate)\s*\(')
    BRANCH_RE = re.compile(r'\bif\s*\(|else\s*\{|switch\s*\(|case\s+')
    LOOP_RE = re.compile(r'\bwhile\s*\(|for\s*\(')
    CGEVENT_RE = re.compile(r'CGEvent(Create|Post)')
    CGDISPLAY_RE = re.compile(r'CG(Display|Main|Image)')
    SOCKET_RE = re.compile(r'\b(send|recv)\s*\(')
    
    for f in functions:
        fid = func_ids[f["name"]]
        body = f["body"]
        body_lines = body.split("\n")
        
        # Extract locks
        for i, line in enumerate(body_lines):
            if LOCK_RE.search(line):
                m = MUTEX_RE.search(line)
                lock_name = m.group(1) if m else "unknown_lock"
                cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, language, parent_node_id)
                    VALUES ('lock', ?, ?, 'mac_server.c', ?, 'c', ?)""",
                    (lock_name, f"{f['name']}:{lock_name}", f["line_start"] + i, fid))
                lock_node_id = cur.lastrowid
                
                # Insert into locks table
                cur.execute("""INSERT INTO locks (name, lock_type, source_file, line_number, contention_level, hold_time_us)
                    VALUES (?, 'pthread_mutex', 'mac_server.c', ?, 0.3, 50.0)""",
                    (lock_name, f["line_start"] + i))
                lock_id = cur.lastrowid
                
                cur.execute("""INSERT INTO lock_acquisitions (lock_id, node_id, acquisition_order, is_blocking, wait_time_us)
                    VALUES (?, ?, 1, 1, 0)""", (lock_id, fid))
        
        # Extract syscalls
        for i, line in enumerate(body_lines):
            if SYSCALL_RE.search(line):
                m = SYSCALL_RE.search(line)
                sc_name = m.group(1)
                cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, language, parent_node_id, is_extern)
                    VALUES ('syscall', ?, ?, 'mac_server.c', ?, 'c', ?, 1)""",
                    (sc_name, f"{f['name']}:{sc_name}", f["line_start"] + i, fid))
                sc_id = cur.lastrowid
                
                # IO operation
                io_type = "socket_send" if sc_name == "send" else "socket_recv" if sc_name == "recv" else "file_op"
                is_block = 1 if sc_name in ("send", "recv", "accept") else 0
                cur.execute("""INSERT INTO io_operations (node_id, io_type, device, bandwidth_mbps, queue_depth, latency_us, is_blocking, kernel_transition)
                    VALUES (?, ?, 'network', 100, 0, 50, ?, 1)""",
                    (sc_id, io_type, is_block))
                
                # Cost
                cur.execute("""INSERT INTO exec_costs (node_id, cost_type, cost_cpu_us, cost_mem_bytes, cost_io_us, is_kernel, is_blocking, description)
                    VALUES (?, 'syscall', 2.0, 0, 50.0, 1, ?, ?)""",
                    (sc_id, is_block, f"{sc_name}() kernel transition"))
        
        # Extract CGEvent calls (OS injection)
        for i, line in enumerate(body_lines):
            if CGEVENT_RE.search(line):
                cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, language, parent_node_id, is_extern)
                    VALUES ('syscall', 'CGEventPost', ?, 'mac_server.c', ?, 'c', ?, 1)""",
                    (f"{f['name']}:CGEventPost", f["line_start"] + i, fid))
                cg_id = cur.lastrowid
                cur.execute("""INSERT INTO io_operations (node_id, io_type, device, latency_us, is_blocking, kernel_transition)
                    VALUES (?, 'display_post', 'windowserver', 200, 0, 1)""", (cg_id,))
                cur.execute("""INSERT INTO exec_costs (node_id, cost_type, cost_cpu_us, cost_io_us, is_kernel, description)
                    VALUES (?, 'syscall', 5.0, 200.0, 1, 'CGEventPost to HID event tap')""", (cg_id,))
        
        # Extract CGDisplay calls
        for i, line in enumerate(body_lines):
            if CGDISPLAY_RE.search(line):
                m = re.search(r'CG(\w+)', line)
                name = m.group(0) if m else "CGDisplay"
                cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, language, parent_node_id, is_extern)
                    VALUES ('syscall', ?, ?, 'mac_server.c', ?, 'c', ?, 1)""",
                    (name, f"{f['name']}:{name}", f["line_start"] + i, fid))
                cg_id = cur.lastrowid
                cur.execute("""INSERT INTO io_operations (node_id, io_type, device, latency_us, is_blocking, kernel_transition)
                    VALUES (?, 'gpu_download', 'gpu', 5000, 1, 1)""", (cg_id,))
                cur.execute("""INSERT INTO exec_costs (node_id, cost_type, cost_cpu_us, cost_io_us, is_kernel, is_blocking, description)
                    VALUES (?, 'gpu', 100.0, 5000.0, 1, 1, 'CGDisplay capture — GPU to CPU transfer')""", (cg_id,))
        
        # Extract allocations
        alloc_count = 0
        for i, line in enumerate(body_lines):
            if ALLOC_RE.search(line):
                m = ALLOC_RE.search(line)
                alloc_name = m.group(1)
                cur.execute("""INSERT INTO ast_nodes (node_type, name, qualified_name, source_file, line_start, language, parent_node_id)
                    VALUES ('alloc', ?, ?, 'mac_server.c', ?, 'c', ?)""",
                    (alloc_name, f"{f['name']}:{alloc_name}", f["line_start"] + i, fid))
                alloc_id = cur.lastrowid
                
                size = 8294400 if "CGDataProvider" in alloc_name or "CGImage" in alloc_name else 1024
                cur.execute("""INSERT INTO exec_costs (node_id, cost_type, cost_cpu_us, cost_mem_bytes, is_kernel, description)
                    VALUES (?, 'malloc', 1.0, ?, 0, ?)""",
                    (alloc_id, size, f"{alloc_name} allocation"))
                alloc_count += 1
        
        # Extract branches
        branch_count = 0
        for i, line in enumerate(body_lines):
            if BRANCH_RE.search(line):
                branch_count += 1
        
        # Extract loops
        loop_count = 0
        for i, line in enumerate(body_lines):
            if LOOP_RE.search(line):
                loop_count += 1
        
        # ─── Insert exec_nodes (runtime actor profile) ───
        # Heuristic cost model based on function role
        fn_lower = f["name"].lower()
        
        if "grabframe" in fn_lower or "capture" in fn_lower:
            cpu_pct = 18.0
            mem_bytes = 31 * 1024 * 1024
            produces = 8294400  # 1920*1080*4
            consumes = 0
            latency_p50 = 7000
            latency_p99 = 15000
            failure = 0.003
            locks = 1
            syscalls_count = 2  # CGDisplay calls
        elif "encode" in fn_lower and "raw" in fn_lower:
            cpu_pct = 2.0
            mem_bytes = 8294400
            produces = 8294400
            consumes = 8294400
            latency_p50 = 100
            latency_p99 = 200
            failure = 0.001
            locks = 0
            syscalls_count = 0
        elif "encode" in fn_lower and "jpeg" in fn_lower:
            cpu_pct = 42.0
            mem_bytes = 8294400 + 400000
            produces = 400000  # ~400KB JPEG
            consumes = 8294400
            latency_p50 = 11000
            latency_p99 = 25000
            failure = 0.005
            locks = 0
            syscalls_count = 0
            alloc_count += 14  # JPEG temp allocations
        elif "sendmsg" in fn_lower or "send" in fn_lower:
            cpu_pct = 5.0
            mem_bytes = 400000
            produces = 0
            consumes = 400000
            latency_p50 = 4000
            latency_p99 = 50000
            failure = 0.03
            locks = 0
            syscalls_count = 1
        elif "recvmsg" in fn_lower or "recv" in fn_lower:
            cpu_pct = 1.0
            mem_bytes = 256
            produces = 0
            consumes = 0
            latency_p50 = 1000
            latency_p99 = 10000
            failure = 0.02
            locks = 0
            syscalls_count = 1
        elif "mouse" in fn_lower:
            cpu_pct = 0.5
            mem_bytes = 64
            produces = 0
            consumes = 6
            latency_p50 = 200
            latency_p99 = 500
            failure = 0.001
            locks = 0
            syscalls_count = 1
        elif "keyboard" in fn_lower:
            cpu_pct = 0.5
            mem_bytes = 64
            produces = 0
            consumes = 4
            latency_p50 = 200
            latency_p99 = 500
            failure = 0.001
            locks = 0
            syscalls_count = 1
        elif "init" in fn_lower:
            cpu_pct = 0.1
            mem_bytes = 1024
            produces = 0
            consumes = 0
            latency_p50 = 100
            latency_p99 = 1000
            failure = 0.01
            locks = 0
            syscalls_count = 0
        elif "main" in fn_lower:
            cpu_pct = 0.1
            mem_bytes = 0
            produces = 0
            consumes = 0
            latency_p50 = 0
            latency_p99 = 0
            failure = 0.0
            locks = 0
            syscalls_count = 0
        else:
            cpu_pct = 1.0
            mem_bytes = 1024
            produces = 0
            consumes = 0
            latency_p50 = 500
            latency_p99 = 2000
            failure = 0.005
            locks = 0
            syscalls_count = 0
        
        cur.execute("""INSERT OR REPLACE INTO exec_nodes 
            (node_id, ast_node_id, cpu_percent, memory_bytes, memory_delta, allocations, frees,
             reads, writes, locks_held, syscalls, branches, is_async, cache_locality,
             failure_chance, throughput_mbps, latency_p50_us, latency_p95_us, latency_p99_us,
             latency_worst_us, produces_bytes, consumes_bytes)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0, 0.5, ?, 0, ?, ?, ?, ?, ?, ?)""",
            (fid, fid, cpu_pct, mem_bytes, mem_bytes, alloc_count,
             locks, syscalls_count, branch_count,  # locks_held, syscalls, branches
             failure,  # failure_chance
             latency_p50, latency_p50 * 3, latency_p99, latency_p99 * 5,
             produces, consumes))
        
        # Timing graph
        cur.execute("""INSERT INTO timing_graph (node_id, p50_us, p95_us, p99_us, worst_us, best_us, mean_us, stddev_us, samples, is_bottleneck)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, ?)""",
            (fid, latency_p50, latency_p50 * 3, latency_p99, latency_p99 * 5,
             latency_p50 * 0.5, latency_p50, latency_p99 * 0.3,
             1 if latency_p99 > 10000 else 0))
        
        # CPU profile
        cur.execute("""INSERT INTO cpu_profile (node_id, integer_ops, float_ops, vector_ops, branch_ops, memory_ops, syscall_ops, cache_misses, cache_hits, cache_hit_rate, context_switches, ipc)
            VALUES (?, ?, 0, 0, ?, ?, ?, 100, 900, 0.9, 0, 1.5)""",
            (fid, branch_count * 10, branch_count, syscalls_count * 50, syscalls_count))
        
        # Heap stats
        cur.execute("""INSERT INTO heap_stats (node_id, total_allocs, total_frees, peak_bytes, current_bytes, fragmentation, leak_risk)
            VALUES (?, ?, 0, ?, ?, 0.1, ?)""",
            (fid, alloc_count, mem_bytes, mem_bytes, 0.01 if alloc_count > 0 else 0))
        
        # Failure modes
        if "grabframe" in fn_lower:
            for cond, prob in [("image == NULL", 0.003), ("dataRef == NULL", 0.002), ("provider == NULL", 0.001)]:
                cur.execute("""INSERT INTO failure_modes (node_id, failure_type, failure_condition, probability, recovery_action, cascading_impact)
                    VALUES (?, 'null_return', ?, ?, 'skip_frame', 'frame dropped, client sees stale frame')""",
                    (fid, cond, prob))
        elif "jpeg" in fn_lower and "encode" in fn_lower:
            for cond, prob in [("image == NULL", 0.005), ("provider == NULL", 0.003), ("dst == NULL", 0.002), ("jpgData == NULL", 0.002)]:
                cur.execute("""INSERT INTO failure_modes (node_id, failure_type, failure_condition, probability, recovery_action, cascading_impact)
                    VALUES (?, 'null_return', ?, ?, 'fallback_raw', 'degraded quality, larger frame')""",
                    (fid, cond, prob))
        elif "sendmsg" in fn_lower or "send" in fn_lower:
            cur.execute("""INSERT INTO failure_modes (node_id, failure_type, failure_condition, probability, recovery_action, cascading_impact)
                VALUES (?, 'errno', 'send() returns < 0', 0.03, 'disconnect', 'client disconnect, stream ends')""", (fid,))
        elif "accept" in fn_lower:
            cur.execute("""INSERT INTO failure_modes (node_id, failure_type, failure_condition, probability, recovery_action, cascading_impact)
                VALUES (?, 'errno', 'accept() fails', 0.01, 'retry', 'client cannot connect')""", (fid,))
    
    # ─── Insert exec_edges (data flow between functions) ───
    edges = [
        ("main", "Capture_Init", "calls", 0, 0, 100, 1.0),
        ("main", "VidCodec_Init", "calls", 0, 0, 100, 1.0),
        ("main", "Network_Init", "calls", 0, 0, 100, 1.0),
        ("main", "Network_WaitClient", "calls", 0, 0, 1000, 1.0),
        ("main", "Input_Init", "calls", 0, 0, 100, 1.0),
        ("main", "Capture_GrabFrame", "calls", 0, 0, 7000, 1.0),
        ("Capture_GrabFrame", "Capture_GetFrame", "produces", 8294400, 0, 100, 1.0),
        ("main", "Capture_GetFrame", "calls", 8294400, 0, 100, 1.0),
        ("main", "VidCodec_Encode", "calls", 8294400, 0, 11000, 1.0),
        ("VidCodec_Encode", "VidCodec_EncodeJPEG", "calls", 8294400, 0, 11000, 1.0),
        ("VidCodec_EncodeJPEG", "VidCodec_EncodeRaw", "fallback", 8294400, 0, 100, 0.005),
        ("main", "Network_SendMsg", "calls", 400000, 1, 4000, 1.0),
        ("Network_SendMsg", "send", "calls", 400000, 1, 4000, 1.0),
        ("main", "Network_RecvMsg", "calls", 0, 0, 100, 1.0),
        ("Network_RecvMsg", "recv", "calls", 0, 0, 100, 1.0),
        ("main", "Input_HandleMouseEvent", "calls", 0, 0, 200, 0.3),
        ("main", "Input_HandleKeyboardEvent", "calls", 0, 0, 200, 0.1),
        ("Input_HandleMouseEvent", "CGEventPost", "calls", 0, 0, 200, 1.0),
        ("Input_HandleKeyboardEvent", "CGEventPost", "calls", 0, 0, 200, 1.0),
    ]
    
    for src, tgt, etype, data_bytes, blocking, latency, prob in edges:
        src_id = func_ids.get(src)
        tgt_id = func_ids.get(tgt)
        if not src_id or not tgt_id:
            # Try to find in ast_nodes by name
            cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (tgt,))
            r = cur.fetchone()
            if r:
                tgt_id = r[0]
            else:
                continue
        cur.execute("""INSERT INTO exec_edges (source_node_id, target_node_id, edge_type, data_bytes, is_blocking, latency_us, probability)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (src_id, tgt_id, etype, data_bytes, blocking, latency, prob))
    
    # ─── Insert resources (buffers) ───
    resources = [
        ("frameBuffer", "buffer", 8294400, "Capture", "mac_server.c", 50),
        ("encodedFrame", "buffer", 400000, "VidCodec", "mac_server.c", 200),
        ("rawFrame", "buffer", 8294400, "main", "mac_server.c", 550),
        ("framePayload", "buffer", 400012, "main", "mac_server.c", 560),
        ("frameLock", "mutex", 0, "Capture", "mac_server.c", 80),
        ("serverFd", "fd", 0, "Network", "mac_server.c", 150),
        ("clientFd", "fd", 0, "Network", "mac_server.c", 155),
    ]
    
    for name, rtype, size, owner, file, line in resources:
        cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (owner,))
        r = cur.fetchone()
        owner_id = r[0] if r else None
        cur.execute("""INSERT INTO resources (name, resource_type, size_bytes, owner_node_id, source_file, line_number)
            VALUES (?, ?, ?, ?, ?, ?)""", (name, rtype, size, owner_id, file, line))
        res_id = cur.lastrowid
        
        # Resource access patterns
        if name == "frameBuffer":
            cur.execute("SELECT id FROM ast_nodes WHERE name = 'Capture_GrabFrame' LIMIT 1")
            r = cur.fetchone()
            if r:
                cur.execute("""INSERT INTO resource_access (resource_id, node_id, access_type, is_exclusive, line_number)
                    VALUES (?, ?, 'write', 1, 130)""", (res_id, r[0]))
            cur.execute("SELECT id FROM ast_nodes WHERE name = 'Capture_GetFrame' LIMIT 1")
            r = cur.fetchone()
            if r:
                cur.execute("""INSERT INTO resource_access (resource_id, node_id, access_type, is_exclusive, line_number)
                    VALUES (?, ?, 'read', 0, 145)""", (res_id, r[0]))
        elif name == "frameLock":
            cur.execute("SELECT id FROM ast_nodes WHERE name = 'Capture_GrabFrame' LIMIT 1")
            r = cur.fetchone()
            if r:
                cur.execute("""INSERT INTO resource_access (resource_id, node_id, access_type, is_exclusive, line_number)
                    VALUES (?, ?, 'acquire', 1, 128)""", (res_id, r[0]))
                cur.execute("""INSERT INTO resource_access (resource_id, node_id, access_type, is_exclusive, line_number)
                    VALUES (?, ?, 'release', 0, 138)""", (res_id, r[0]))
    
    # ─── Insert state machines ───
    # Frame lifecycle: empty → captured → encoded → queued → sent → freed
    capture_id = struct_ids.get("Capture")
    if capture_id:
        cur.execute("INSERT INTO state_machines (node_id, variable_name, source_file, line_number) VALUES (?, 'frameBuffer', 'mac_server.c', 50)", (capture_id,))
    else:
        cur.execute("INSERT INTO state_machines (variable_name, source_file, line_number) VALUES ('frameBuffer', 'mac_server.c', 50)")
    sm_id = cur.lastrowid
    
    states = [
        ("empty", "captured", "Capture_GrabFrame", 1.0, "image != NULL"),
        ("captured", "encoded", "VidCodec_Encode", 0.995, "encodedSize > 0"),
        ("captured", "error", "VidCodec_Encode", 0.005, "encodedSize <= 0"),
        ("encoded", "queued", "Network_SendMsg", 1.0, "send() >= 0"),
        ("queued", "sent", "send", 0.97, "send() >= 0"),
        ("queued", "error", "send", 0.03, "send() < 0"),
        ("sent", "freed", "main", 1.0, "loop continues"),
        ("error", "freed", "main", 1.0, "skip frame"),
    ]
    
    for from_s, to_s, trigger, prob, guard in states:
        cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (trigger,))
        r = cur.fetchone()
        trigger_id = r[0] if r else None
        cur.execute("""INSERT INTO state_transitions (state_machine_id, from_state, to_state, trigger_node_id, probability, guard_condition)
            VALUES (?, ?, ?, ?, ?, ?)""", (sm_id, from_s, to_s, trigger_id, prob, guard))
    
    # RUNNING variable state machine
    main_id = func_ids.get("main")
    if main_id:
        cur.execute("INSERT INTO state_machines (node_id, variable_name, source_file, line_number) VALUES (?, 'RUNNING', 'mac_server.c', 60)", (main_id,))
    else:
        cur.execute("INSERT INTO state_machines (variable_name, source_file, line_number) VALUES ('RUNNING', 'mac_server.c', 60)")
    sm2_id = cur.lastrowid
    cur.execute("""INSERT INTO state_transitions (state_machine_id, from_state, to_state, probability, guard_condition)
        VALUES (?, 'true', 'true', 0.999, 'no signal')""", (sm2_id,))
    cur.execute("""INSERT INTO state_transitions (state_machine_id, from_state, to_state, probability, guard_condition)
        VALUES (?, 'true', 'false', 0.001, 'SIGINT/SIGTERM')""", (sm2_id,))
    cur.execute("""INSERT INTO state_transitions (state_machine_id, from_state, to_state, probability, guard_condition)
        VALUES (?, 'false', 'cleanup', 1.0, 'always')""", (sm2_id,))
    
    # ─── Insert timing paths ───
    # Main frame loop path
    frame_path = "Capture_GrabFrame -> Capture_GetFrame -> VidCodec_Encode -> Network_SendMsg -> Network_RecvMsg"
    cur.execute("""INSERT INTO timing_paths (path_name, node_sequence, total_p50_us, total_p95_us, total_p99_us, total_worst_us, predicted_fps, bottleneck_node, bottleneck_us)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Frame Loop (JPEG)", frame_path,
         7000 + 100 + 11000 + 4000 + 100,   # p50 = 22300us
         21000 + 300 + 33000 + 12000 + 300,  # p95 = 66600us
         15000 + 200 + 25000 + 50000 + 1000, # p99 = 91200us
         75000 + 1000 + 125000 + 250000 + 5000, # worst = 456000us
         1000000 / 22300,  # ~44.8 fps
         "VidCodec_Encode", 11000))
    
    # Input path
    input_path = "Network_RecvMsg -> Input_HandleMouseEvent -> CGEventPost"
    cur.execute("""INSERT INTO timing_paths (path_name, node_sequence, total_p50_us, total_p95_us, total_p99_us, total_worst_us, predicted_fps, bottleneck_node, bottleneck_us)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Input Path (Mouse)", input_path,
         100 + 200 + 200,    # 500us
         300 + 600 + 600,    # 1500us
         1000 + 500 + 500,   # 2000us
         10000 + 2500 + 2500, # 15000us
         1000000 / 500,      # 2000 fps (not bottleneck)
         "CGEventPost", 200))
    
    # ─── Insert branch probabilities ───
    branches = [
        ("Capture_GrabFrame", "if", "image_null", 0.003, 0.5, "code"),
        ("Capture_GrabFrame", "if", "image_ok", 0.997, 0.5, "code"),
        ("Capture_GrabFrame", "if", "dataRef_null", 0.002, 0.5, "code"),
        ("VidCodec_EncodeJPEG", "if", "image_null", 0.005, 0.5, "code"),
        ("VidCodec_EncodeJPEG", "if", "dst_null", 0.002, 0.5, "code"),
        ("Network_SendMsg", "if", "send_fail", 0.03, 0.5, "code"),
        ("Network_SendMsg", "if", "send_ok", 0.97, 0.5, "code"),
        ("Network_RecvMsg", "if", "no_data", 0.9, 0.7, "heuristic"),
        ("Network_RecvMsg", "if", "has_data", 0.1, 0.7, "heuristic"),
        ("main", "if", "grabframe_fail", 0.003, 0.5, "code"),
        ("main", "if", "encode_fail", 0.005, 0.5, "code"),
        ("main", "if", "send_fail", 0.03, 0.5, "code"),
        ("main", "if", "mouse_event", 0.3, 0.6, "heuristic"),
        ("main", "if", "keyboard_event", 0.1, 0.6, "heuristic"),
    ]
    
    for node_name, btype, path, prob, conf, source in branches:
        cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (node_name,))
        r = cur.fetchone()
        nid = r[0] if r else None
        if nid:
            cur.execute("""INSERT INTO branch_probabilities (node_id, branch_type, taken_path, probability, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?)""", (nid, btype, path, prob, conf, source))
    
    # ─── Insert failure predictions ───
    cur.execute("""INSERT INTO failure_predictions (path_name, frames_simulated, expected_failures, failure_prob_path, mtbf_frames, worst_case)
        VALUES (?, ?, ?, ?, ?, ?)""",
        ("Frame Loop (JPEG)", 5000, 5000 * 0.038, 0.038, 1/0.038, "send() fails → client disconnect → stream ends"))
    
    cur.execute("""INSERT INTO failure_predictions (path_name, frames_simulated, expected_failures, failure_prob_path, mtbf_frames, worst_case)
        VALUES (?, ?, ?, ?, ?, ?)""",
        ("Input Path (Mouse)", 5000, 5000 * 0.001, 0.001, 1000, "CGEventPost fails → input lost"))
    
    # ─── Insert heap objects ───
    heap_objs = [
        ("frameBuffer", "Capture_Init", None, 8294400, "static", "permanent", 0, 0),
        ("encodedFrame", "main", None, 400000, "static", "permanent", 0, 0),
        ("rawFrame", "main", None, 8294400, "static", "permanent", 0, 0),
        ("image", "Capture_GrabFrame", "Capture_GrabFrame", 8294400, "malloc", "transient", 1, 1),
        ("dataRef", "Capture_GrabFrame", "Capture_GrabFrame", 8294400, "malloc", "transient", 1, 1),
        ("jpgData", "VidCodec_EncodeJPEG", "VidCodec_EncodeJPEG", 400000, "malloc", "transient", 1, 1),
        ("dst", "VidCodec_EncodeJPEG", "VidCodec_EncodeJPEG", 1024, "malloc", "transient", 1, 0),
        ("event", "Input_HandleMouseEvent", "Input_HandleMouseEvent", 256, "malloc", "transient", 1, 0),
    ]
    
    for name, alloc_node, free_node, size, atype, lifetime, is_freed, is_aliased in heap_objs:
        cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (alloc_node,))
        r = cur.fetchone()
        alloc_id = r[0] if r else None
        free_id = None
        if free_node:
            cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (free_node,))
            r = cur.fetchone()
            free_id = r[0] if r else None
        cur.execute("""INSERT INTO heap_objects (name, alloc_node_id, free_node_id, size_bytes, alloc_type, escape_scope, lifetime, is_freed, is_aliased)
            VALUES (?, ?, ?, ?, ?, 'function', ?, ?, ?)""",
            (name, alloc_id, free_id, size, atype, lifetime, is_freed, is_aliased))
    
    # ─── Insert feature parameters + impact ───
    cur.execute("""INSERT INTO feature_parameters (param_name, current_value, unit, affected_nodes, description)
        VALUES ('jpeg_quality', '80', 'percent', 'VidCodec_EncodeJPEG', 'JPEG compression quality 1-100')""")
    jq_id = cur.lastrowid
    
    impacts = [
        (jq_id, "80", "95", 14.0, 0.0, 19.0, 61.0, -8.0, 0.0, 0.8),
        (jq_id, "80", "50", -18.0, 0.0, -12.0, -38.0, 12.0, 0.0, 0.8),
        (jq_id, "80", "100", 22.0, 0.0, 35.0, 120.0, -15.0, 0.0, 0.7),
    ]
    for pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf in impacts:
        cur.execute("""INSERT INTO feature_impact (param_id, from_value, to_value, delta_cpu, delta_memory, delta_latency, delta_bandwidth, delta_fps, delta_failure, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf))
    
    cur.execute("""INSERT INTO feature_parameters (param_name, current_value, unit, affected_nodes, description)
        VALUES ('fps_target', '30', 'fps', 'main', 'Target frames per second')""")
    fps_id = cur.lastrowid
    
    impacts2 = [
        (fps_id, "30", "60", 100.0, 0.0, -50.0, 100.0, 100.0, 10.0, 0.9),
        (fps_id, "30", "15", -50.0, 0.0, 100.0, -50.0, -50.0, -5.0, 0.9),
    ]
    for pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf in impacts2:
        cur.execute("""INSERT INTO feature_impact (param_id, from_value, to_value, delta_cpu, delta_memory, delta_latency, delta_bandwidth, delta_fps, delta_failure, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf))
    
    cur.execute("""INSERT INTO feature_parameters (param_name, current_value, unit, affected_nodes, description)
        VALUES ('resolution', '1920x1080', 'pixels', 'Capture, VidCodec', 'Capture resolution')""")
    res_id = cur.lastrowid
    
    impacts3 = [
        (res_id, "1920x1080", "1280x720", -55.0, -55.0, -55.0, -55.0, 120.0, -30.0, 0.95),
        (res_id, "1920x1080", "3840x2160", 300.0, 300.0, 300.0, 300.0, -70.0, 50.0, 0.95),
    ]
    for pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf in impacts3:
        cur.execute("""INSERT INTO feature_impact (param_id, from_value, to_value, delta_cpu, delta_memory, delta_latency, delta_bandwidth, delta_fps, delta_failure, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (pid, fv, tv, dcpu, dmem, dlat, dbw, dfps, dfail, conf))
    
    # ─── Insert system entropy ───
    subsystems = [
        ("Capture", 8, 0.3, 0.9, 0.7, 0.4, 0.6, 0.5, 0.7, 0.65, "Add error retry for CGDisplayCreateImage"),
        ("VidCodec", 12, 0.2, 0.85, 0.5, 0.3, 0.7, 0.4, 0.8, 0.52, "H264/VP8 stubs need implementation"),
        ("Network", 10, 0.4, 0.95, 0.9, 0.5, 0.6, 0.3, 0.6, 0.71, "Add reconnection logic"),
        ("Input", 6, 0.2, 0.7, 0.3, 0.2, 0.5, 0.6, 0.9, 0.38, "Low risk, well isolated"),
        ("Main Loop", 7, 0.5, 1.0, 0.8, 0.6, 0.5, 0.5, 0.5, 0.68, "Add graceful shutdown on SIGTERM"),
    ]
    
    for sub, complexity, coupling, criticality, famp, repair, conf, obs, pred, entropy, rec in subsystems:
        cur.execute("""INSERT INTO system_entropy (subsystem, complexity, coupling, criticality, failure_amp, repair_difficulty, confidence, observability, predictability, entropy_score, recommendation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sub, complexity, coupling, criticality, famp, repair, conf, obs, pred, entropy, rec))
    
    # ─── Insert execution replay (simulate 3 frames) ───
    for frame_num in range(1, 4):
        cur.execute("""INSERT INTO execution_frames (frame_number, path_name, total_latency_us, predicted_fps, failure_occurred, timestamp_sim)
            VALUES (?, 'Frame Loop (JPEG)', 22300, 44.8, 0, ?)""",
            (frame_num, frame_num * 0.0223))
        frame_id = cur.lastrowid
        
        steps = [
            ("Capture_GrabFrame", 7000, 8294400, 8294400, 0, None, 0),
            ("Capture_GetFrame", 100, 0, 8294400, 0, None, 0),
            ("VidCodec_Encode", 11000, 8294400, 400000, 0, None, 0),
            ("Network_SendMsg", 4000, 400000, 0, 0, "send_ok", 0),
            ("Network_RecvMsg", 100, 0, 0, 0, "no_data", 0),
        ]
        
        if frame_num == 3:
            # Simulate a failure on frame 3
            steps[0] = ("Capture_GrabFrame", 7000, 0, 0, 0, "image_null", 1)
            steps[2] = ("VidCodec_Encode", 0, 0, 0, 0, "encode_fail", 1)
        
        for order, (name, cpu, mem, produced, consumed, branch, fail) in enumerate(steps):
            cur.execute("SELECT id FROM ast_nodes WHERE name = ? LIMIT 1", (name,))
            r = cur.fetchone()
            nid = r[0] if r else None
            if nid:
                cur.execute("""INSERT INTO execution_steps (frame_id, step_order, node_id, cpu_used_us, mem_used_bytes, bytes_produced, bytes_consumed, latency_us, branch_taken, failure_simulated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (frame_id, order, nid, cpu, mem, produced, consumed, cpu, branch, fail))
    
    conn.commit()
    
    # ─── Print summary ───
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    
    tables = [
        ("ast_nodes", "AST Node Registry"),
        ("exec_nodes", "Runtime Actors"),
        ("exec_edges", "Data Movement Edges"),
        ("exec_costs", "Cost Extraction"),
        ("state_machines", "State Machines"),
        ("state_transitions", "State Transitions"),
        ("resources", "Resources"),
        ("resource_access", "Resource Access"),
        ("timing_graph", "Timing Graph"),
        ("timing_paths", "Timing Paths"),
        ("branch_probabilities", "Branch Probabilities"),
        ("failure_modes", "Failure Modes"),
        ("failure_predictions", "Failure Predictions"),
        ("locks", "Locks"),
        ("lock_acquisitions", "Lock Acquisitions"),
        ("lock_cycles", "Lock Cycles"),
        ("heap_objects", "Heap Objects"),
        ("heap_stats", "Heap Stats"),
        ("cpu_profile", "CPU Profile"),
        ("io_operations", "IO Operations"),
        ("async_tasks", "Async Tasks"),
        ("execution_frames", "Execution Frames"),
        ("execution_steps", "Execution Steps"),
        ("feature_parameters", "Feature Parameters"),
        ("feature_impact", "Feature Impact"),
        ("system_entropy", "System Entropy"),
    ]
    
    for table, desc in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        if count > 0:
            pass  # VBStyle: no print
    
    # Print key simulation views
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT name, cpu_percent, p99_ms, failure_chance FROM v_bottlenecks LIMIT 10")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT path_name, p50_ms, p95_ms, p99_ms, worst_ms, predicted_fps, bottleneck_node FROM v_path_latency")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT path_name, frames_simulated, expected_failures, failure_percent, mtbf_frames, worst_case FROM v_failure_prediction")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT name, size_bytes, alloc_node, free_node, lifetime, leak_risk FROM v_leak_candidates LIMIT 10")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT param_name, from_value, to_value, cpu_pct_change, latency_pct_change, fps_pct_change, bandwidth_pct_change, confidence FROM v_feature_impact")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT subsystem, complexity, coupling, criticality, entropy_score, recommendation FROM v_entropy")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT frame_number, step_order, node_name, cpu_used_us, bytes_produced, bytes_consumed, branch_taken, failure_simulated FROM v_execution_replay WHERE frame_number = 1")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    pass  # VBStyle: no print
    cur.execute("SELECT frame_number, step_order, node_name, cpu_used_us, bytes_produced, bytes_consumed, branch_taken, failure_simulated FROM v_execution_replay WHERE frame_number = 3")
    for r in cur.fetchall():
        pass  # VBStyle: no print
    
    conn.close()
    pass  # VBStyle: no print
    pass  # VBStyle: no print
if __name__ == "__main__":
    main()
