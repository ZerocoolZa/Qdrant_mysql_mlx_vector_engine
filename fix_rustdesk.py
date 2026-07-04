#!/usr/bin/env python3
"""Fix RustDesk scaling by patching the Flutter assets to add stretch view style."""
import os
import sys
import subprocess
import shutil
import re
import pathlib

def run(cmd, check=True):
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    if check and result.returncode != 0:
        print(f"FAILED with code {result.returncode}")
    return result

def main():
    # 1. Find RustDesk install location
    print("=== Step 1: Find RustDesk ===")
    r = run('where rustdesk', check=False)
    rustdesk_exe = None
    paths_to_check = [
        r"C:\Program Files\RustDesk\rustdesk.exe",
        r"C:\Program Files (x86)\RustDesk\rustdesk.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\RustDesk\rustdesk.exe"),
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            rustdesk_exe = p
            break
    if not rustdesk_exe:
        # Try where command output
        if r.stdout.strip():
            rustdesk_exe = r.stdout.strip().split('\n')[0].strip()
    
    if not rustdesk_exe:
        print("Could not find rustdesk.exe!")
        sys.exit(1)
    
    rustdesk_dir = os.path.dirname(rustdesk_exe)
    print(f"RustDesk found at: {rustdesk_exe}")
    print(f"RustDesk dir: {rustdesk_dir}")
    
    # 2. Check RustDesk version
    print("\n=== Step 2: Check version ===")
    r = run(f'"{rustdesk_exe}" --version', check=False)
    
    # 3. Find Flutter assets (kernel.bin or app.so or app.asar)
    print("\n=== Step 3: Find Flutter assets ===")
    data_dir = os.path.join(rustdesk_dir, "data")
    flutter_assets = os.path.join(rustdesk_dir, "data", "flutter_assets")
    
    # Check various locations
    candidate_dirs = [
        os.path.join(rustdesk_dir, "data"),
        os.path.join(rustdesk_dir, "flutter_assets"),
        rustdesk_dir,
    ]
    
    kernel_files = []
    for d in candidate_dirs:
        if os.path.exists(d):
            print(f"Checking {d}...")
            for f in os.listdir(d):
                print(f"  {f}")
                if f in ("kernel.bin", "app.so", "app.asar", "kernel_blob.bin"):
                    kernel_files.append(os.path.join(d, f))
    
    if not kernel_files:
        # Search recursively
        for root, dirs, files in os.walk(rustdesk_dir):
            for f in files:
                if f in ("kernel.bin", "app.so", "app.asar", "kernel_blob.bin"):
                    kernel_files.append(os.path.join(root, f))
                    print(f"Found: {os.path.join(root, f)}")
    
    if not kernel_files:
        print("No Flutter kernel/assets found. Listing all files in RustDesk dir:")
        for root, dirs, files in os.walk(rustdesk_dir):
            for f in files:
                print(f"  {os.path.join(root, f)}")
    
    # 4. Look for the view style strings in the binary
    print("\n=== Step 4: Search for view style strings ===")
    for kf in kernel_files:
        print(f"\nSearching in {kf}...")
        try:
            with open(kf, 'rb') as f:
                data = f.read()
            
            # Search for 'adaptive' and 'original' strings
            for needle in [b'kRemoteViewStyleAdaptive', b'kRemoteViewStyleOriginal', b'kRemoteViewStyleCustom', b'adaptive', b'original']:
                idx = data.find(needle)
                if idx >= 0:
                    print(f"  Found '{needle.decode()}' at offset {idx}")
                    # Show context
                    start = max(0, idx - 50)
                    end = min(len(data), idx + len(needle) + 50)
                    print(f"  Context: {data[start:end]}")
        except Exception as e:
            print(f"  Error reading: {e}")
    
    # 5. Report findings
    print("\n=== Step 5: Report ===")
    print(f"RustDesk exe: {rustdesk_exe}")
    print(f"RustDesk dir: {rustdesk_dir}")
    print(f"Kernel files: {kernel_files}")
    
    # 6. Also check if there's a simpler approach - check all .toml files
    print("\n=== Step 6: Check all config files ===")
    config_dir = r"C:\Users\Administrator\AppData\Roaming\RustDesk\config"
    if os.path.exists(config_dir):
        for f in os.listdir(config_dir):
            print(f"  {f}")
        peers_dir = os.path.join(config_dir, "peers")
        if os.path.exists(peers_dir):
            print(f"  Peers dir:")
            for f in os.listdir(peers_dir):
                print(f"    {f}")

if __name__ == "__main__":
    main()
