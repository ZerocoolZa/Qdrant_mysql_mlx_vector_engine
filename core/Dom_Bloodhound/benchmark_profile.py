#!/usr/bin/env python3
"""
benchmark_profile.py — Lean profiling benchmark.
No SQLite, no rich, no events. Just timing dicts.
Shows per-scenario, per-operation ms breakdown.

Usage:
  python3 benchmark_profile.py 1000     # 1000 runs, show timings
  python3 benchmark_profile.py 10000    # 10K runs
"""

import os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_error_ai_v3 import build_scenarios


def main():
    TOTAL_RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    scenarios = build_scenarios()
    n = len(scenarios)

    print(f"ErrorAI v3 — Lean Profile Benchmark")
    print(f"Scenarios: {n} | Runs: {TOTAL_RUNS:,} | Total encounters: {n * TOTAL_RUNS:,}")
    print()

    # Timing storage: {scenario_name: {"trigger": [ms,...], "fix:fname": [ms,...]}}
    timings = defaultdict(lambda: defaultdict(list))
    # Counters
    counts = defaultdict(lambda: defaultdict(int))

    start = time.time()

    for run_num in range(1, TOTAL_RUNS + 1):
        for s in scenarios:
            # trigger
            t0 = time.time()
            try:
                exec(s.broken_code, {})
                triggered = False
            except BaseException:
                triggered = True
            timings[s.name]["trigger"].append((time.time() - t0) * 1000)
            counts[s.name]["trigger"] += 1

            if not triggered:
                counts[s.name]["not_triggered"] += 1
                continue

            # try each fix
            for fname, fcode in s.fix_candidates:
                t0 = time.time()
                try:
                    ns = {}
                    exec(fcode, ns)
                    ok = True
                except BaseException:
                    ok = False
                    ns = None
                if ok:
                    try:
                        correct = s.result_checker(ns)
                    except BaseException:
                        correct = False
                else:
                    correct = False
                elapsed = (time.time() - t0) * 1000
                timings[s.name][f"fix:{fname}"].append(elapsed)
                counts[s.name][f"fix:{fname}"] += 1
                if ok and correct:
                    counts[s.name]["fixed"] += 1
                    break  # first working fix
                else:
                    counts[s.name]["fix_failed"] += 1

        if run_num % max(1, TOTAL_RUNS // 10) == 0:
            elapsed = time.time() - start
            pct = run_num / TOTAL_RUNS * 100
            rate = run_num / elapsed
            eta = (TOTAL_RUNS - run_num) / rate
            print(f"  {pct:5.1f}% run {run_num:>6,}/{TOTAL_RUNS:,} | {elapsed:.1f}s | {rate:,.0f} runs/s | ETA {eta:.0f}s")

    elapsed = time.time() - start

    # ---- Report ----
    print()
    print("=" * 100)
    print(f"DONE — {TOTAL_RUNS:,} runs, {n * TOTAL_RUNS:,} encounters in {elapsed:.1f}s")
    print("=" * 100)

    # Per-scenario breakdown
    print()
    print(f"{'Scenario':<25s} {'trig ms':>8s} {'fix ms':>8s} {'enc ms':>8s} {'calls':>8s} {'est 100K':>10s} {'flag':>6s}")
    print("-" * 80)

    scenario_totals = []
    for s in scenarios:
        trig_times = timings[s.name]["trigger"]
        fix_times = []
        for fname, _ in s.fix_candidates:
            fix_times.extend(timings[s.name][f"fix:{fname}"])

        avg_trig = sum(trig_times) / max(1, len(trig_times))
        avg_fix = sum(fix_times) / max(1, len(fix_times))
        avg_enc = avg_trig + avg_fix * len(s.fix_candidates)
        total_calls = len(trig_times) + len(fix_times)
        est_100k = avg_enc * 100000 / 1000

        flag = "SLOW!" if est_100k > 60 else ""
        scenario_totals.append((s.name, avg_trig, avg_fix, avg_enc, total_calls, est_100k, flag))

        print(f"{s.name:<25s} {avg_trig:8.3f} {avg_fix:8.3f} {avg_enc:8.3f} {total_calls:8,} {est_100k:8.1f}s {flag:>6s}")

    # Sort by slowest
    scenario_totals.sort(key=lambda x: -x[5])
    print()
    print(f"{'TOP 10 SLOWEST (est 100K)':^80s}")
    print("-" * 80)
    for name, avg_trig, avg_fix, avg_enc, calls, est, flag in scenario_totals[:10]:
        print(f"  {name:<25s} trig={avg_trig:.3f}ms fix={avg_fix:.3f}ms enc={avg_enc:.3f}ms est_100K={est:.1f}s {flag}")

    # Per-fix breakdown for slowest scenario
    slowest_name = scenario_totals[0][0]
    print()
    print(f"PER-FIX BREAKDOWN — {slowest_name}")
    print("-" * 60)
    for fname, _ in scenarios[0].fix_candidates:
        pass  # placeholder
    for s in scenarios:
        if s.name == slowest_name:
            for fname, _ in s.fix_candidates:
                times = timings[s.name][f"fix:{fname}"]
                if times:
                    avg = sum(times) / len(times)
                    mx = max(times)
                    mn = min(times)
                    print(f"  fix:{fname:<20s} avg={avg:.3f}ms min={mn:.3f}ms max={mx:.3f}ms n={len(times):,}")
            trig = timings[s.name]["trigger"]
            print(f"  trigger                  avg={sum(trig)/len(trig):.3f}ms min={min(trig):.3f}ms max={max(trig):.3f}ms n={len(trig):,}")
            break

    # Overall stats
    all_trig = []
    all_fix = []
    for s in scenarios:
        all_trig.extend(timings[s.name]["trigger"])
        for fname, _ in s.fix_candidates:
            all_fix.extend(timings[s.name][f"fix:{fname}"])

    print()
    print(f"{'OVERALL':^80s}")
    print("-" * 80)
    print(f"  trigger avg: {sum(all_trig)/len(all_trig):.3f}ms  min: {min(all_trig):.3f}ms  max: {max(all_trig):.3f}ms  n={len(all_trig):,}")
    print(f"  fix     avg: {sum(all_fix)/len(all_fix):.3f}ms  min: {min(all_fix):.3f}ms  max: {max(all_fix):.3f}ms  n={len(all_fix):,}")
    print(f"  total time:  {elapsed:.1f}s")
    print(f"  throughput:  {n * TOTAL_RUNS / elapsed:,.0f} encounters/s")


if __name__ == "__main__":
    main()
