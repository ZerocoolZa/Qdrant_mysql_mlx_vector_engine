#!/usr/bin/env python3
"""
BCL live watcher — monitors .bcl file, auto-regenerates .excalidraw on save.
Run in background: python3 bcl_watch.py db_stack.bcl Untitled-1.excalidraw
"""
import sys
import os
import time
import subprocess

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 bcl_watch.py input.bcl output.excalidraw")
        sys.exit(1)

    bcl_file = os.path.abspath(sys.argv[1])
    out_file = os.path.abspath(sys.argv[2])
    html_file = out_file.replace(".excalidraw", ".html")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcl_to_excalidraw.py")

    last_mtime = 0
    print(f"Watching {bcl_file} -> {out_file} + {html_file}")
    print("Press Ctrl+C to stop.")

    while True:
        try:
            mtime = os.path.getmtime(bcl_file)
            if mtime != last_mtime:
                last_mtime = mtime
                result = subprocess.run(
                    ["python3", script, bcl_file, out_file],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] Updated -> {out_file}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] ERROR: {result.stderr.strip()}")
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
