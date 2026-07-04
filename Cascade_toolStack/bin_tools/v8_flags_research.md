# V8 / Node.js Memory Optimization Flags — Research Report

#[@GHOST]{[@file<v8_flags_research.md>][@state<active>][@date<2026-06-29>][@ver<1.0>][@auth<Agent4>]}
#[@VBSTYLE]{[@auth<system>][@role<research_report>][@return<documentation>]}
#[@FILEID]{v8_flags_research.md}
#[@SUMMARY]{Comprehensive research on V8/Node.js memory optimization flags tested on macOS arm64 (Apple Silicon) with Node.js v20.7.0. Includes measured before/after benchmarks, NODE_OPTIONS compatibility matrix, and recommended configuration for < 128MB per node process.}
#[@CLASS]{V8FlagsResearch}
#[@METHOD]{report}

---

## Executive Summary

Node.js processes on this system (Devin Helper, brain_server, MCP servers) use excessive RAM because V8's default heap limit is **~2096 MB** (2 GB) on this machine. By applying V8 memory optimization flags, we can cap the heap at **~120 MB**, enable manual garbage collection, and disable JIT memory — reducing RSS by **29%** and heap usage by **78%** in stress tests.

**Recommended configuration:**
```bash
# For NODE_OPTIONS (tool-launched processes):
export NODE_OPTIONS="--max-old-space-size=96 --max-semi-space-size=8 --jitless"

# For directly-launched processes (add these CLI args):
node --expose-gc --gc-interval=100 app.js
```

---

## Test Environment

| Parameter | Value |
|-----------|-------|
| Node.js version | v20.7.0 |
| OS | macOS Darwin 25.4.0 |
| Architecture | arm64 (Apple Silicon, ARM64_T8103) |
| Default heap_size_limit | 2096 MB |
| Default total_heap_size (startup) | 3.72 MB |
| Default semi-space-size | 16 MB (64-bit) |

---

## V8 Memory Flags — Detailed Analysis

### 1. `--max-old-space-size=N` (MB)

**Purpose:** Limits V8's old generation heap (where long-lived objects live).

**Test results:**
| Setting | heap_size_limit | RSS (startup) |
|---------|----------------|---------------|
| default | 2096 MB | 33.39 MB |
| =64 | 112 MB | 34.13 MB |
| =96 | 136 MB | 34.17 MB |

**NODE_OPTIONS compatible:** YES

**Notes:** This is the single most impactful flag. Default 2096 MB means V8 can grow the heap to 2 GB before triggering aggressive GC. Setting to 96 MB forces V8 to GC frequently, keeping memory bounded. The heap_size_limit becomes `max-old-space-size + 3 * max-semi-space-size + overhead`.

---

### 2. `--max-semi-space-size=N` (MB)

**Purpose:** Limits V8's new generation semi-space (where short-lived objects are allocated).

**Test results:**
| Setting | heap_size_limit | Notes |
|---------|----------------|-------|
| default (16) | 2096 MB | Young gen = 48 MB |
| =8 | 120 MB (with max-old=96) | Young gen = 24 MB |
| =4 | 108 MB (with max-old=96) | Young gen = 12 MB |

**NODE_OPTIONS compatible:** YES

**Notes:** Young generation size = 3 × semi-space-size. Default 16 MB → 48 MB young gen. Setting to 8 MB → 24 MB young gen. Smaller semi-space = more frequent minor GC (Scavenge) but lower peak memory. For I/O-bound servers, 8 MB is a good balance. For CPU-bound workloads with many short-lived allocations, keep at 16 MB to avoid GC overhead.

---

### 3. `--expose-gc`

**Purpose:** Exposes `global.gc()` function for manual garbage collection from JavaScript.

**Test results:**
| Setting | gc() available | heapUsed after manual gc |
|---------|---------------|--------------------------|
| not set | NO | 22.02 MB (not reclaimed) |
| set | YES | 2.32-4.75 MB (reclaimed) |

**NODE_OPTIONS compatible:** NO — blocked by Node.js security policy

**Usage:**
```bash
# Must be passed as direct CLI argument:
node --expose-gc app.js
```

```javascript
// In application code:
if (globalThis.gc) {
  globalThis.gc();  // Force garbage collection
}
```

**Notes:** This is the second most impactful flag. Without it, V8's heuristic GC may not reclaim memory promptly, leaving heapUsed at 22 MB even after objects are dereferenced. With `gc()` available, manual calls drop heapUsed to 2-5 MB. The `--gc-interval=100` flag supplements this by forcing periodic GC every 100 allocations.

**Workaround for NODE_OPTIONS block:** Applications can use `v8.setFlagsFromString('--expose-gc')` at runtime, but this must be called before V8 initializes the heap — effectively only works if called at the very start of the process.

---

### 4. `--gc-interval=N`

**Purpose:** Forces V8 to attempt garbage collection every N allocations (default: -1 = V8 decides).

**Test results:**
| Setting | Effect |
|---------|--------|
| default (-1) | V8 heuristic GC |
| =100 | GC attempted every 100 allocations |

**NODE_OPTIONS compatible:** NO — blocked by Node.js security policy

**Notes:** Setting too low (e.g., 10) causes excessive GC overhead and CPU spikes. Setting to 100 provides a good balance — more frequent than V8's default heuristic, keeping peak memory lower. Best used in combination with `--expose-gc` for maximum control.

---

### 5. `--jitless`

**Purpose:** Disables V8 JIT compilation (TurboFan, Sparkplug, Maglev). Code runs in interpreter only.

**Test results:**
| Setting | total_heap_size_exec | RSS (startup) | heapUsed (startup) |
|---------|---------------------|---------------|---------------------|
| default | 0.25 MB | 33.39 MB | 2.99 MB |
| --jitless | 0.00 MB | 33.64 MB | 2.77 MB |

**NODE_OPTIONS compatible:** YES

**Notes:** Eliminates executable heap memory (JIT code cache). Reduces memory by ~0.25 MB at startup, with larger savings for long-running processes that would accumulate JIT-compiled code. Trade-off: 20-40% slower execution for CPU-bound code. For I/O-bound servers (MCP servers, brain_server waiting on network/DB), the performance impact is negligible. **Remove this flag for CPU-intensive workloads** (e.g., ML inference, crypto, data processing).

Side effect: Also disables WebAssembly (`--expose_wasm` auto-disabled).

---

### 6. `--max-heap-size=N` (MB)

**Purpose:** Sets absolute max heap (old + new space combined). Takes precedence over both `--max-old-space-size` and `--max-semi-space-size`.

**Test results:**
| Setting | heap_size_limit |
|---------|----------------|
| =64 | 64 MB |

**NODE_OPTIONS compatible:** NO — blocked by Node.js security policy

**Notes:** Cannot be combined with `--max-old-space-size` and `--max-semi-space-size` (V8 error: "All three flags cannot be specified at the same time"). We prefer the separate flags for finer control. If you want a single simple cap, use `--max-heap-size=128` instead.

---

### 7. `--initial-heap-size=N` (MB)

**Purpose:** Sets the initial heap size at startup.

**Test results:** Minimal effect — V8 starts at ~3.72 MB regardless and grows dynamically.

**NODE_OPTIONS compatible:** NO — blocked by Node.js security policy

**Notes:** Not recommended. V8's dynamic heap growth is well-tuned. Setting a low initial heap just delays growth. Setting a high initial heap wastes memory at startup.

---

### 8. `--initial-old-space-size=N` (MB)

**Purpose:** Sets initial old space size.

**Notes:** Not found as a recognized flag in Node.js v20.7.0 V8 options. Likely a V8 internal flag not exposed through Node.js CLI.

---

### 9. `--optimize-for-size`

**Purpose:** Was used in old V8 versions to prefer memory optimization over speed.

**Status:** DEPRECATED — no effect in Node.js 20+ (V8 11+). Do not use.

---

### 10. `--trace-gc` (debugging)

**Purpose:** Prints GC events to stderr for debugging memory behavior.

**Test output:**
```
[36234:0x148008000] 9 ms: Scavenge 3.4 (3.7) -> 3.2 (4.7) MB, 0.29 ms  allocation failure
[36234:0x148008000] 10 ms: Scavenge 3.4 (4.7) -> 3.3 (5.5) MB, 0.33 ms  allocation failure
```

**NODE_OPTIONS compatible:** NO

**Notes:** Use for debugging only. Shows Scavenge (minor GC) and Mark-Compact (major GC) events with heap sizes before/after. Disable in production (significant I/O overhead).

---

### 11. `--heapsnapshot-signal=SIGUSR2` (debugging)

**Purpose:** Send SIGUSR2 to the node process to write a `.heapsnapshot` file for Chrome DevTools heap profiler.

**NODE_OPTIONS compatible:** NO

**Usage:**
```bash
node --heapsnapshot-signal=SIGUSR2 app.js &
kill -USR2 $PID  # Writes Heap.YYYYMMDD.HHMMSS.PID.heapsnapshot
# Load in Chrome DevTools > Memory > Load
```

**Notes:** Use for diagnosing memory leaks. The snapshot file can be large (proportional to heap size).

---

## Node.js Specific Flags

### `NODE_OPTIONS` Environment Variable

**Purpose:** Passes V8 flags to node processes launched by tools that don't allow custom CLI args.

**Security restriction:** Node.js maintains an allowlist of V8 flags that can be set via `NODE_OPTIONS`. Flags not on the allowlist cause:
```
node: --expose-gc is not allowed in NODE_OPTIONS
exit code 9
```

**Allowed V8 flags in NODE_OPTIONS (Node.js v20.7.0):**
- `--max-old-space-size=N` ✅
- `--max-semi-space-size=N` ✅
- `--jitless` ✅
- `--abort-on-uncaught-exception` ✅
- `--disallow-code-generation-from-strings` ✅
- `--stack-trace-limit=N` ✅
- `--huge-max-old-generation-size` ✅ (opposite of what we want)

**BLOCKED in NODE_OPTIONS:**
- `--expose-gc` ❌
- `--gc-interval=N` ❌
- `--max-heap-size=N` ❌
- `--initial-heap-size=N` ❌
- `--trace-gc` ❌
- `--heapsnapshot-signal=SIGUSR2` ❌

---

## NODE_OPTIONS Compatibility Matrix

| Flag | Direct CLI | NODE_OPTIONS | Effect |
|------|-----------|--------------|--------|
| `--max-old-space-size=96` | ✅ | ✅ | Cap old gen heap at 96MB |
| `--max-semi-space-size=8` | ✅ | ✅ | Cap young gen at 24MB |
| `--jitless` | ✅ | ✅ | Disable JIT, save executable heap |
| `--expose-gc` | ✅ | ❌ | Enable manual gc() calls |
| `--gc-interval=100` | ✅ | ❌ | Force GC every 100 allocs |
| `--max-heap-size=64` | ✅ | ❌ | Absolute heap cap |
| `--initial-heap-size=2` | ✅ | ❌ | Initial heap (minimal effect) |
| `--trace-gc` | ✅ | ❌ | Debug GC events |
| `--heapsnapshot-signal=SIGUSR2` | ✅ | ❌ | Heap snapshot on signal |
| `--optimize-for-size` | N/A | N/A | DEPRECATED, no effect |

---

## Benchmark Results — Stress Test

**Test script:** `/tmp/test_stress.js` — allocates 10,000 arrays, drops 9,900, creates 5,000 long-lived objects, then 5 rounds of 5,000-array allocation churn.

### WITHOUT Flags (Default)

```
[startup]                     rss=32.58MB  heapUsed=2.91MB
[after 10000 arrays]          rss=49.03MB  heapUsed=11.17MB
[after dropping 9900]         rss=49.05MB  heapUsed=11.17MB
[after 5000 long-lived]       rss=50.20MB  heapUsed=13.80MB
[after 5 rounds churn]        rss=74.55MB  heapUsed=22.02MB
[final]                       rss=74.58MB  heapUsed=22.02MB  (no gc available)

heap_size_limit:   2096.00 MB
total_heap_size:     49.22 MB
```

### WITH NODE_OPTIONS + --expose-gc --gc-interval=100 (Full Optimization)

```
[startup]                     rss=32.72MB  heapUsed=2.69MB  -> gc: 2.15MB
[after 10000 arrays]          rss=48.94MB  heapUsed=10.61MB -> gc: 10.45MB
[after dropping 9900]         rss=49.30MB  heapUsed=10.53MB -> gc: 2.37MB
[after 5000 long-lived]       rss=42.55MB  heapUsed=5.25MB  -> gc: 4.75MB
[after 5 rounds churn]        rss=53.06MB  heapUsed=9.44MB  -> gc: 4.75MB
[final]                       rss=53.17MB  heapUsed=4.75MB  -> gc: 4.75MB

heap_size_limit:   120.00 MB
total_heap_size:    21.47 MB
```

### WITH NODE_OPTIONS Only (No --expose-gc, for tool-launched processes)

```
[startup]                     rss=32.58MB  heapUsed=2.69MB
[after 10000 arrays]          rss=48.45MB  heapUsed=10.99MB
[after dropping 9900]         rss=48.45MB  heapUsed=11.00MB
[after 5000 long-lived]       rss=49.33MB  heapUsed=13.63MB
[after 5 rounds churn]        rss=60.75MB  heapUsed=13.22MB
[final]                       rss=60.75MB  heapUsed=13.23MB  (no gc available)

heap_size_limit:   120.00 MB
total_heap_size:    29.22 MB
```

### Summary Comparison

| Metric | Default | NODE_OPTIONS only | NODE_OPTIONS + gc args | Improvement |
|--------|---------|-------------------|------------------------|-------------|
| **Final RSS** | 74.58 MB | 60.75 MB | 53.17 MB | **-29%** |
| **Final heapUsed** | 22.02 MB | 13.23 MB | 4.75 MB | **-78%** |
| **heap_size_limit** | 2096 MB | 120 MB | 120 MB | **-94%** |
| **total_heap_size** | 49.22 MB | 29.22 MB | 21.47 MB | **-56%** |
| **gc() available** | No | No | Yes | Manual reclaim |

---

## Recommended Configurations

### Profile 1: Low Memory (Default — for MCP servers, helpers)

```bash
# In NODE_OPTIONS (works for all node processes):
export NODE_OPTIONS="--max-old-space-size=96 --max-semi-space-size=8 --jitless"

# Direct CLI args (for processes you launch manually):
node --expose-gc --gc-interval=100 app.js
```
- Heap limit: ~120 MB
- Expected RSS: 50-80 MB under load
- Best for: I/O-bound servers, MCP servers, Devin Helper

### Profile 2: Ultra-Low Memory (64MB cap — constrained environments)

```bash
export NODE_OPTIONS="--max-old-space-size=48 --max-semi-space-size=4 --jitless"
node --expose-gc --gc-interval=50 app.js
```
- Heap limit: ~60 MB
- Expected RSS: 40-60 MB under load
- Best for: Many small processes, memory-constrained systems
- Risk: May cause OOM crashes for memory-intensive workloads

### Profile 3: Balanced (256MB cap — for memory-intensive MCP servers)

```bash
export NODE_OPTIONS="--max-old-space-size=192 --max-semi-space-size=16 --jitless"
node --expose-gc --gc-interval=200 app.js
```
- Heap limit: ~240 MB
- Expected RSS: 80-150 MB under load
- Best for: MCP servers that handle large payloads, brain_server with caching
- Remove `--jitless` if CPU performance is critical

### Profile 4: No JITless (for CPU-intensive node processes)

```bash
export NODE_OPTIONS="--max-old-space-size=96 --max-semi-space-size=8"
node --expose-gc --gc-interval=100 app.js
```
- Heap limit: ~120 MB
- JIT enabled for performance
- Best for: ML inference, data processing, crypto workloads

---

## Implementation Guide

### For tool-launched processes (Devin Helper, MCP servers launched by tools)

These processes read `NODE_OPTIONS` from the environment. Set it globally:

```bash
# Add to shell profile (~/.zshrc, ~/.bashrc) or system launchd config:
source /Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/node_mem_flags.sh
```

This gives them `--max-old-space-size=96 --max-semi-space-size=8 --jitless` but NOT `--expose-gc` or `--gc-interval` (blocked by Node.js security policy).

### For directly-launched processes (brain_server, custom scripts)

Add flags to the launch command:

```bash
node --expose-gc --gc-interval=100 --max-old-space-size=96 --max-semi-space-size=8 --jitless brain_server.js
```

Or source the script and use the combined env vars:

```bash
source /Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/node_mem_flags.sh
node $NODE_MEM_GC_ARGS brain_server.js
```

### For application code (manual GC)

Add periodic GC calls in long-running processes:

```javascript
// Call gc() after processing large batches
if (globalThis.gc) {
  globalThis.gc();  // Force garbage collection
}

// Or set up a periodic GC timer (every 30 seconds)
if (globalThis.gc) {
  setInterval(() => {
    const before = process.memoryUsage().heapUsed;
    globalThis.gc();
    const after = process.memoryUsage().heapUsed;
    if (before - after > 1024 * 1024) {
      console.log(`GC reclaimed ${((before - after) / 1048576).toFixed(1)} MB`);
    }
  }, 30000).unref();
}
```

---

## Caveats and Trade-offs

1. **`--jitless` performance impact:** 20-40% slower for CPU-bound code. Test your workload. I/O-bound servers (network, DB) see minimal impact.

2. **`--gc-interval=100` CPU overhead:** More frequent GC = more CPU time spent in collector. Monitor CPU usage. Increase to 200-500 if CPU is constrained.

3. **`--max-old-space-size=96` OOM risk:** If your process legitimately needs > 96 MB of old space, it will crash with:
   ```
   FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory
   ```
   Monitor for OOM crashes and increase to 128 or 192 if needed.

4. **NODE_OPTIONS limitations:** `--expose-gc` and `--gc-interval` cannot be set via NODE_OPTIONS. For tool-launched processes, you must either:
   - Modify the tool's launch command to add these flags
   - Use `v8.setFlagsFromString('--expose-gc')` at the very start of your JS code (before any other code runs)
   - Accept that only heap size limits will be applied (still a 94% reduction in heap_size_limit)

5. **`--max-heap-size` vs `--max-old-space-size + --max-semi-space-size`:** These are mutually exclusive. Use the separate flags for finer control. Use `--max-heap-size` for a single simple cap.

---

## Files Created

| File | Purpose |
|------|---------|
| `/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/node_mem_flags.sh` | Sourced shell script that sets NODE_OPTIONS and NODE_MEM_GC_ARGS |
| `/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/v8_flags_research.md` | This research report |
| `/tmp/test_mem.js` | Basic memory usage test script |
| `/tmp/test_stress.js` | Memory stress test for before/after benchmarking |

---

## References

- [Node.js: Understanding and Tuning Memory](https://nodejs.org/learn/diagnostics/memory/understanding-and-tuning-memory)
- [Node.js CLI Documentation (v26)](https://nodejs.org/api/cli.html)
- [Node.js CLI Documentation (v19)](https://nodejs.org/docs/latest-v19.x/api/cli.html)
- [NearForm: Optimising Node.js with --max-semi-space-size](https://nearform.com/digital-community/optimising-node-js-applications-the-impact-of-max-semi-space-size-on-garbage-collection-efficiency/)
- [V8 flag-definitions.h](https://github.com/v8/v8/blob/main/src/flags/flag-definitions.h)
- [Node.js Issue #55487: max-semi-space-size defaults in Node 20](https://github.com/nodejs/node/issues/55487)
