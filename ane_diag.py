#!/usr/bin/env python3
"""ANE Compiler Diagnostic Tool — traces what triggers ANECompilerService on macOS."""

import subprocess
import time
from datetime import datetime

TARGET = "ANECompilerService"


def get_process_info(name):
    results = []
    try:
        out = subprocess.check_output(["ps", "-Axo", "pid,ppid,pcpu,comm"], text=True)
        for line in out.strip().split("\n")[1:]:
            parts = line.strip().split(None, 3)
            if len(parts) < 4:
                continue
            pid, ppid, cpu, comm = parts
            if name.lower() in comm.lower():
                results.append((int(pid), int(ppid), float(cpu), comm))
    except Exception:
        pass
    return results


def get_parent_chain(pid):
    chain = []
    try:
        out = subprocess.check_output(["ps", "-Axo", "pid,ppid,comm"], text=True)
        proc_map = {}
        for line in out.strip().split("\n")[1:]:
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            proc_map[int(parts[0])] = (int(parts[1]), parts[2])
        current = pid
        while current in proc_map:
            ppid, comm = proc_map[current]
            chain.append((current, comm))
            current = ppid
            if current == 0 or current == 1:
                chain.append((current, "launchd" if current == 1 else "kernel"))
                break
    except Exception:
        pass
    return chain


def system_context():
    print("\n🧠 SYSTEM CONTEXT SNAPSHOT")
    print("-" * 50)
    try:
        out = subprocess.check_output(
            ["ps", "-ax"], text=True
        )
        lines = [l for l in out.split("\n") if any(
            kw in l.lower() for kw in [
                "photoanalysis", "spotlight", "mds", "mdworker",
                "siriactivation", "coreml", "vision", "mediaanalysis",
                "categories", "contextkit", "ane", "neural"
            ]
        )]
        print("\n".join(lines) if lines else "No obvious ML-related services active.")
    except Exception:
        print("Context scan failed.")


def top_cpu_processes():
    print("\n🔥 TOP CPU PROCESSES")
    print("-" * 50)
    try:
        out = subprocess.check_output(
            ["ps", "-Arco", "pid,pcpu,pmem,comm"], text=True
        )
        for line in out.strip().split("\n")[:11]:
            print(line)
    except Exception:
        print("Failed to get CPU processes.")


def launchd_hints():
    print("\n🔗 LAUNCHD OWNERSHIP HINTS")
    print("-" * 50)
    try:
        out = subprocess.check_output(
            ["launchctl", "list"], text=True
        )
        lines = [l for l in out.split("\n") if any(
            kw in l.lower() for kw in ["ane", "neural", "coreml", "photo", "spotlight", "siri", "media", "categories", "context"]
        )]
        print("\n".join(lines[:15]) if lines else "No relevant launchd jobs found.")
    except Exception:
        print("launchctl list failed.")


def live_monitor(duration=30):
    print(f"\n📡 Monitoring {TARGET} for {duration}s...\n")
    start = time.time()
    seen_pids = set()

    while time.time() - start < duration:
        procs = get_process_info(TARGET)
        if procs:
            for pid, ppid, cpu, comm in procs:
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    print(f"\n⚠️  DETECTED {TARGET} at {datetime.now().strftime('%H:%M:%S')}")
                    print(f"   PID: {pid} | PPID: {ppid} | CPU: {cpu}%")
                    chain = get_parent_chain(pid)
                    print("   🔗 Parent Chain:")
                    for c in chain[:6]:
                        print(f"      {c[0]} → {c[1]}")
                else:
                    print(f"   [{datetime.now().strftime('%H:%M:%S')}] PID {pid} still running — CPU: {cpu}%")
        else:
            print(f"   [{datetime.now().strftime('%H:%M:%S')}] {TARGET} not running")
        time.sleep(5)

    print(f"\n✅ Monitoring complete. Unique PIDs seen: {len(seen_pids)}")


if __name__ == "__main__":
    print("\n🧪 ANE COMPILER DIAGNOSTIC TOOL STARTED\n")
    system_context()
    top_cpu_processes()
    launchd_hints()
    live_monitor(30)
    print("\n🏁 Done.\n")
