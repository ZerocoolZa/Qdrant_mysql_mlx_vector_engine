#!/usr/bin/env bash
#[@GHOST]{[@file<node_mem_flags.sh>][@state<active>][@date<2026-06-29>][@ver<1.0>][@auth<Agent4>]}
#[@VBSTYLE]{[@auth<system>][@role<memory_optimization>][@return<env_setup>]}
#[@FILEID]{node_mem_flags.sh}
#[@SUMMARY]{Sets NODE_OPTIONS env var with optimal V8 memory flags for low-RAM node processes. Source this script before running any node process to cap heap at 96MB, reduce semi-space, disable JIT executable heap, and enable manual GC.}
#[@CLASS]{NodeMemFlags}
#[@METHOD]{source}

#=============================================================================
# node_mem_flags.sh — V8/Node.js Memory Optimization Environment Setup
#=============================================================================
# PURPOSE:  Reduce per-process RAM for Node.js (Devin Helper, brain_server,
#           MCP servers) to < 128MB by capping V8 heap sizes and enabling
#           aggressive garbage collection.
#
# USAGE:
#   source /Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/node_mem_flags.sh
#   node your_server.js
#
#   Or for processes that support direct node args (recommended for --expose-gc):
#   NODE_MEM_ARGS="--expose-gc --gc-interval=100"
#   node $NODE_MEM_ARGS your_server.js
#
# TESTED ON: Node.js v20.7.0, macOS arm64 (Darwin 25.4.0, Apple Silicon)
#=============================================================================

#-----------------------------------------------------------------------------
# FLAG DOCUMENTATION
#-----------------------------------------------------------------------------
# --max-old-space-size=96
#   Limits V8's old generation heap to 96 MB (default: ~2096 MB on this machine).
#   Old space holds long-lived objects. Capping it forces V8 to GC aggressively
#   rather than growing unbounded. Measured: heap_size_limit 2096MB -> 120MB.
#
# --max-semi-space-size=8
#   Limits V8's new generation (semi-space) to 8 MB (default: 16 MB on 64-bit).
#   New space is where short-lived objects are allocated. Smaller semi-space
#   means more frequent minor GC but lower peak memory. Young gen = 3x this
#   value, so 8 MB -> 24 MB young gen (vs 48 MB default).
#
# --jitless
#   Disables V8 JIT compilation (TurboFan/Sparkplug). Code runs in interpreter
#   only. Eliminates executable heap memory (total_heap_size_exec: 0.25MB -> 0MB)
#   and JIT code cache. Trade-off: ~20-40% slower execution for CPU-bound code.
#   Good for I/O-bound servers (MCP, brain_server) where memory matters more
#   than raw CPU speed. Remove this flag if your workload is CPU-intensive.
#
# --expose-gc  (CANNOT be set via NODE_OPTIONS — must be direct CLI arg)
#   Exposes global.gc() function for manual garbage collection. Lets code call
#   gc() after processing large batches to reclaim memory immediately rather
#   than waiting for V8's heuristic. Must be passed as: node --expose-gc app.js
#
# --gc-interval=100  (CANNOT be set via NODE_OPTIONS — must be direct CLI arg)
#   Forces V8 to attempt garbage collection every 100 allocations (default: -1,
#   meaning V8 decides automatically). Lower values = more frequent GC = lower
#   peak memory but more CPU overhead. 100 is a balanced value.
#
# --max-heap-size=N  (CANNOT be set via NODE_OPTIONS — must be direct CLI arg)
#   Sets absolute max heap (old + new space combined). Takes precedence over
#   both max-old-space-size and max-semi-space-size. Cannot be combined with
#   them. We use max-old-space-size + max-semi-space-size instead for finer
#   control.
#
# --initial-heap-size=N  (CANNOT be set via NODE_OPTIONS — must be direct CLI arg)
#   Sets the initial heap size. V8 grows the heap dynamically, so this mainly
#   affects startup. Not set here — let V8 start small and grow as needed.
#
# --trace-gc  (debugging only — CANNOT be set via NODE_OPTIONS)
#   Prints GC events to stderr. Use for debugging memory issues:
#   node --trace-gc app.js 2>&1 | grep Scavenge
#
# --heapsnapshot-signal=SIGUSR2  (debugging only)
#   Send SIGUSR2 to the node process to write a .heapsnapshot file for
#   Chrome DevTools heap profiler analysis.
#
# --optimize-for-size  (DEPRECATED in modern V8)
#   Was used in old V8 versions to prefer memory over speed. No longer
#   has effect in Node.js 20+. Do not use.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# NODE_OPTIONS — flags allowed in NODE_OPTIONS environment variable
#-----------------------------------------------------------------------------
# Node.js restricts which V8 flags can be set via NODE_OPTIONS for security.
# Tested on Node.js v20.7.0:
#   ALLOWED:    --max-old-space-size, --max-semi-space-size, --jitless
#   BLOCKED:    --expose-gc, --gc-interval, --max-heap-size,
#               --initial-heap-size, --trace-gc, --heapsnapshot-signal
#
# For blocked flags, pass them directly on the command line:
#   node --expose-gc --gc-interval=100 app.js
#-----------------------------------------------------------------------------

# --- Core memory limit flags (safe for NODE_OPTIONS) ---
export NODE_OPTIONS="--max-old-space-size=96 --max-semi-space-size=8 --jitless"

# --- Direct CLI args for flags NOT allowed in NODE_OPTIONS ---
# Use these when launching node processes you control:
#   node $NODE_MEM_GC_ARGS app.js
export NODE_MEM_GC_ARGS="--expose-gc --gc-interval=100"

# --- Combined recommended launch command ---
# For processes you fully control (can modify launch command):
#   node --expose-gc --gc-interval=100 --max-old-space-size=96 --max-semi-space-size=8 --jitless app.js
#
# For processes launched by tools that only read NODE_OPTIONS:
#   source this script, then the tool launches node (gets heap limits + jitless)
#   but NOT --expose-gc (code must use v8.setFlagsFromString('--expose-gc') workaround)

#-----------------------------------------------------------------------------
# OPTIONAL: Lower memory profile (64MB cap — for very constrained environments)
#-----------------------------------------------------------------------------
# Uncomment for even more aggressive memory limiting:
# export NODE_OPTIONS="--max-old-space-size=48 --max-semi-space-size=4 --jitless"
# export NODE_MEM_GC_ARGS="--expose-gc --gc-interval=50"

#-----------------------------------------------------------------------------
# OPTIONAL: Balanced profile (256MB cap — for memory-intensive MCP servers)
#-----------------------------------------------------------------------------
# Uncomment if 96MB causes OOM crashes:
# export NODE_OPTIONS="--max-old-space-size=192 --max-semi-space-size=16 --jitless"
# export NODE_MEM_GC_ARGS="--expose-gc --gc-interval=200"

#-----------------------------------------------------------------------------
# VERIFICATION — run this to check flags are active
#-----------------------------------------------------------------------------
# node -e "const v8=require('v8'); const hs=v8.getHeapStatistics(); \
#   console.log('heap_size_limit:', (hs.heap_size_limit/1048576).toFixed(0)+'MB', \
#   '(target: <=120MB)'); \
#   console.log('gc available:', typeof globalThis.gc !== 'undefined');"

#-----------------------------------------------------------------------------
# MEASURED RESULTS (Node.js v20.7.0, macOS arm64, Apple Silicon)
#-----------------------------------------------------------------------------
# Test: /tmp/test_stress.js (10000 array alloc + 5000 long-lived objects + churn)
#
# WITHOUT FLAGS (default):
#   final rss:         74.58 MB
#   final heapUsed:    22.02 MB  (no gc() available, memory not reclaimed)
#   heap_size_limit:   2096.00 MB
#   total_heap_size:   49.22 MB
#
# WITH NODE_OPTIONS + --expose-gc --gc-interval=100:
#   final rss:         53.17 MB   (-29% RSS)
#   final heapUsed:     4.75 MB   (-78% heapUsed, gc() reclaims memory)
#   heap_size_limit:   120.00 MB  (-94% heap limit)
#   total_heap_size:   21.47 MB   (-56% total heap)
#
# WITH NODE_OPTIONS only (no --expose-gc, for tool-launched processes):
#   final rss:         60.75 MB   (-19% RSS)
#   final heapUsed:    13.23 MB   (-40% heapUsed)
#   heap_size_limit:   120.00 MB  (-94% heap limit)
#   total_heap_size:   29.22 MB   (-41% total heap)
#-----------------------------------------------------------------------------

echo "node_mem_flags.sh: NODE_OPTIONS set to: $NODE_OPTIONS"
echo "node_mem_flags.sh: NODE_MEM_GC_ARGS set to: $NODE_MEM_GC_ARGS"
echo "node_mem_flags.sh: Heap limit capped at ~120MB (96MB old + 24MB young)"
echo "node_mem_flags.sh: JIT disabled (--jitless) for lower memory"
echo "node_mem_flags.sh: For manual GC, launch with: node \$NODE_MEM_GC_ARGS app.js"
