#!/usr/bin/env python3
"""
BCL live server — watches .bcl file and serves HTML preview on localhost.
Run: python3 bcl_serve.py db_stack.bcl 8765
Then open in Windsurf Simple Browser: http://localhost:8765
"""
import sys
import os
import time
import subprocess
import http.server
import threading

def run_watcher(bcl_file, out_file, script):
    last_mtime = 0
    while True:
        try:
            mtime = os.path.getmtime(bcl_file)
            if mtime != last_mtime:
                last_mtime = mtime
                subprocess.run(
                    ["python3", script, bcl_file, out_file],
                    capture_output=True, text=True, timeout=10
                )
                print(f"[{time.strftime('%H:%M:%S')}] Updated")
            time.sleep(0.5)
        except Exception as e:
            print(f"Watcher error: {e}")
            time.sleep(1)

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 bcl_serve.py input.bcl port")
        sys.exit(1)

    bcl_file = os.path.abspath(sys.argv[1])
    port = int(sys.argv[2])
    base = os.path.dirname(bcl_file)
    script = os.path.join(base, "bcl_to_excalidraw.py")
    out_file = os.path.join(base, "Untitled-1.excalidraw")
    html_file = os.path.join(base, "Untitled-1.html")

    # Initial render
    subprocess.run(["python3", script, bcl_file, out_file], capture_output=True, text=True)

    # Start watcher in background thread
    t = threading.Thread(target=run_watcher, args=(bcl_file, out_file, script), daemon=True)
    t.start()

    # Serve files
    os.chdir(base)
    handler = http.server.SimpleHTTPRequestHandler

    class QuietHandler(handler):
        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), QuietHandler)
    print(f"Serving at http://localhost:{port}")
    print(f"Watching {bcl_file}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
