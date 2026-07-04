# core/Dom_Bloodhound/benchmark_100k.py
# 100K concurrent benchmark — pass only int index, rebuild scenarios inside worker

import os, sys, time, io
import multiprocessing as mp
from datetime import datetime
from multiprocessing import Queue, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_scenario_worker(scenario_index, total_runs, result_queue):
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        from test_error_ai_v3 import build_scenarios
        scenarios = build_scenarios()
        scenario = scenarios[scenario_index]

        knowledge = {}
        encounters = 0
        trig = matched = fixed = correct = 0
        no_fix = fix_changes = 0
        trigger_fail = match_fail = 0

        for _ in range(total_runs):
            encounters += 1
            triggered, actual, _ = scenario.trigger()
            if not triggered:
                trigger_fail += 1
                continue
            trig += 1
            if actual == scenario.expected_error:
                matched += 1
            else:
                match_fail += 1

            key = scenario.name
            known = knowledge.get(key)

            if known and known.get("best_fix"):
                for fname, fcode in scenario.fix_candidates:
                    if fname == known["best_fix"]:
                        ok, correct_fix, _ = scenario.try_fix(fcode)
                        known["encounters"] += 1
                        if ok and correct_fix:
                            known["success_count"] += 1
                            fixed += 1
                            correct += 1
                        else:
                            known["fail_count"] += 1
                            known["best_fix"] = ""
                            fix_changes += 1
                        s = known["success_count"]
                        f = known["fail_count"]
                        known["confidence"] = s / max(1, s + f)
                        break
                continue

            working = []
            failing = []
            for fname, fcode in scenario.fix_candidates:
                ok, correct_fix, _ = scenario.try_fix(fcode)
                if ok and correct_fix:
                    working.append(fname)
                else:
                    failing.append(fname)

            if working:
                knowledge[key] = {
                    "best_fix": working[0],
                    "success_count": 1, "fail_count": 0,
                    "confidence": 1.0 / max(1, len(scenario.fix_candidates)),
                    "encounters": 1,
                }
                fixed += 1
                correct += 1
            else:
                no_fix += 1
                knowledge[key] = {
                    "best_fix": "",
                    "success_count": 0, "fail_count": len(failing),
                    "confidence": 0.0, "encounters": 1,
                }

        k = knowledge.get(scenario.name, {})
        result_queue.put({
            "name": scenario.name,
            "encounters": encounters,
            "trig": trig, "match": matched, "fixed": fixed,
            "correct": correct, "no_fix": no_fix, "fix_changes": fix_changes,
            "trigger_fail": trigger_fail, "match_fail": match_fail,
            "best_fix": k.get("best_fix", "NONE"),
            "confidence": k.get("confidence", 0.0),
        })
    except Exception as e:
        result_queue.put({"name": f"idx_{scenario_index}", "error": str(e)})


def main():
    TOTAL_RUNS = 100000
    ctx = mp.get_context("fork")

    print("ErrorAI v3 — 100K Concurrent Benchmark")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"CPU cores: {cpu_count()}")

    from test_error_ai_v3 import build_scenarios
    scenarios = build_scenarios()
    n = len(scenarios)

    print(f"Scenarios: {n}")
    print(f"Runs per scenario: {TOTAL_RUNS:,}")
    print(f"Total encounters: {n * TOTAL_RUNS:,}")
    print(f"Mode: fork, pass int index only")
    print()

    q = ctx.Queue()
    procs = []
    start = time.time()

    for i in range(n):
        p = ctx.Process(target=run_scenario_worker, args=(i, TOTAL_RUNS, q))
        p.start()
        procs.append(p)

    results = []
    for _ in range(n):
        r = q.get()
        results.append(r)
        done = len(results)
        elapsed = time.time() - start
        if "error" in r:
            print(f"  [{done:>2}/{n}] FAIL {r['name']}: {r['error']}")
        else:
            print(f"  [{done:>2}/{n}] {r['name']:<25s} {elapsed:6.1f}s"
                  f" trig={r['trig']:,} fixed={r['fixed']:,}"
                  f" nofix={r['no_fix']:,} chgs={r['fix_changes']:,}"
                  f" best={r['best_fix']:<16s} conf={r['confidence']:.3f}")

    for p in procs:
        p.join()

    elapsed = time.time() - start
    results.sort(key=lambda r: r.get("name", ""))

    print()
    print("=" * 80)
    print(f"DONE — {TOTAL_RUNS:,} runs, {n * TOTAL_RUNS:,} encounters in {elapsed:.1f}s")
    print("=" * 80)
    print()
    print(f"{'Scenario':<25s} {'Trig':>8s} {'Match':>8s} {'Fixed':>8s} {'Correct':>8s} {'NoFix':>6s} {'Chgs':>5s} {'BestFix':<16s} {'Conf':>6s}")
    print("-" * 100)

    tot_enc = tot_trig = tot_match = tot_fixed = tot_correct = 0
    tot_nofix = tot_changes = tot_trigfail = tot_matchfail = 0

    for r in results:
        if "error" in r:
            print(f"{r['name']:<25s} ERROR: {r['error']}")
            continue
        print(f"{r['name']:<25s} {r['trig']:8,} {r['match']:8,} {r['fixed']:8,}"
              f" {r['correct']:8,} {r['no_fix']:6,} {r['fix_changes']:5,}"
              f" {r['best_fix']:<16s} {r['confidence']:6.3f}")
        tot_trig += r["trig"]
        tot_match += r["match"]
        tot_fixed += r["fixed"]
        tot_correct += r["correct"]
        tot_nofix += r["no_fix"]
        tot_changes += r["fix_changes"]
        tot_trigfail += r["trigger_fail"]
        tot_matchfail += r["match_fail"]

    tot_enc = n * TOTAL_RUNS
    print()
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"  Total encounters:    {tot_enc:,}")
    print(f"  Triggered:           {tot_trig:,} ({tot_trig/tot_enc*100:.2f}%)")
    print(f"  Trigger failures:    {tot_trigfail:,} ({tot_trigfail/tot_enc*100:.2f}%)")
    print(f"  Matched:             {tot_match:,} ({tot_match/tot_enc*100:.2f}%)")
    print(f"  Match failures:      {tot_matchfail:,} ({tot_matchfail/tot_enc*100:.2f}%)")
    print(f"  Fixes found:         {tot_fixed:,} ({tot_fixed/tot_enc*100:.2f}%)")
    print(f"  Result correct:      {tot_correct:,} ({tot_correct/tot_enc*100:.2f}%)")
    print(f"  No fix found:        {tot_nofix:,}")
    print(f"  Fix changes:         {tot_changes:,}")
    print()

    with_fix = sum(1 for r in results if "error" not in r and r["best_fix"] != "NONE")
    no_fix = sum(1 for r in results if "error" not in r and r["best_fix"] == "NONE")
    avg_conf = sum(r["confidence"] for r in results if "error" not in r) / max(1, len(results))

    print(f"  Patterns learned:    {len(results)}")
    print(f"  With fix:            {with_fix}")
    print(f"  Without fix:         {no_fix}")
    print(f"  Avg confidence:      {avg_conf:.3f}")
    fix_rate = tot_fixed / max(1, tot_trig) * 100
    print(f"  Fix rate:            {fix_rate:.2f}%")

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_ai_100k_report.txt")
    with open(report_path, "w") as f:
        f.write(f"ErrorAI v3 — 100K Concurrent Benchmark\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Scenarios: {n}\n")
        f.write(f"Runs per scenario: {TOTAL_RUNS:,}\n")
        f.write(f"Total encounters: {tot_enc:,}\n")
        f.write(f"Time: {elapsed:.1f}s\n\n")
        f.write(f"{'Scenario':<25s} {'Trig':>8s} {'Match':>8s} {'Fixed':>8s} {'Correct':>8s} {'NoFix':>6s} {'Chgs':>5s} {'BestFix':<16s} {'Conf':>6s}\n")
        f.write("-" * 100 + "\n")
        for r in results:
            if "error" in r:
                f.write(f"{r['name']:<25s} ERROR: {r['error']}\n")
                continue
            f.write(f"{r['name']:<25s} {r['trig']:8,} {r['match']:8,} {r['fixed']:8,}"
                    f" {r['correct']:8,} {r['no_fix']:6,} {r['fix_changes']:5,}"
                    f" {r['best_fix']:<16s} {r['confidence']:6.3f}\n")
        f.write(f"\nFix rate: {fix_rate:.2f}%\n")
        f.write(f"Avg confidence: {avg_conf:.3f}\n")
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
