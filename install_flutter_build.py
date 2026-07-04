#!/usr/bin/env python3
"""Install Flutter SDK on Windows and build patched RustDesk."""
import subprocess
import os
import sys
import urllib.request
import zipfile
import shutil

def run(cmd, check=True, timeout=600):
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr[-1000:]}")
    if check and result.returncode != 0:
        print(f"FAILED with code {result.returncode}")
    return result

def main():
    # Step 1: Install Flutter SDK
    print("=== Step 1: Install Flutter SDK ===")
    flutter_dir = r"C:\flutter"
    flutter_bin = os.path.join(flutter_dir, "bin", "flutter.bat")
    
    if not os.path.exists(flutter_bin):
        print("Downloading Flutter SDK...")
        zip_path = r"C:\flutter.zip"
        url = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.27.0-stable.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
            print(f"Downloaded {os.path.getsize(zip_path)} bytes")
        except Exception as e:
            print(f"Download failed: {e}")
            # Try alternative URL
            url2 = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.0-stable.zip"
            print(f"Trying alternative: {url2}")
            urllib.request.urlretrieve(url2, zip_path)
        
        print("Extracting Flutter SDK...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall("C:\\")
        os.remove(zip_path)
    
    # Add to PATH for this session
    os.environ["PATH"] = flutter_dir + r"\bin;" + os.environ["PATH"]
    
    # Verify
    r = run(f'"{flutter_bin}" --version', check=False)
    
    # Step 2: Check Rust
    print("\n=== Step 2: Check Rust ===")
    run("rustc --version", check=False)
    run("cargo --version", check=False)
    
    # Step 3: Check VS Build Tools
    print("\n=== Step 3: Check VS Build Tools ===")
    r = run('where cl 2>&1', check=False)
    if r.returncode != 0:
        print("C++ compiler not found. Checking for VS installations...")
        vs_paths = [
            r"C:\Program Files\Microsoft Visual Studio",
            r"C:\Program Files (x86)\Microsoft Visual Studio",
        ]
        for vp in vs_paths:
            if os.path.exists(vp):
                print(f"Found VS dir: {vp}")
                for root, dirs, files in os.walk(vp):
                    if 'cl.exe' in files:
                        print(f"  cl.exe at: {os.path.join(root, 'cl.exe')}")
                        break
    
    # Step 4: Check RustDesk source
    print("\n=== Step 4: Check RustDesk source ===")
    src_dir = r"C:\rustdesk_src"
    if not os.path.exists(src_dir):
        print("Cloning RustDesk...")
        run(f"git clone https://github.com/rustdesk/rustdesk.git {src_dir}", timeout=300)
    
    # Check current branch/tag
    run(f'cd {src_dir} && git describe --tags 2>&1', check=False)
    run(f'cd {src_dir} && git log --oneline -1 2>&1', check=False)
    
    # Step 5: Check if already patched
    print("\n=== Step 5: Check patch status ===")
    consts_path = os.path.join(src_dir, "flutter", "lib", "consts.dart")
    model_path = os.path.join(src_dir, "flutter", "lib", "models", "model.dart")
    toolbar_path = os.path.join(src_dir, "flutter", "lib", "desktop", "widgets", "remote_toolbar.dart")
    
    for p in [consts_path, model_path, toolbar_path]:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                content = f.read()
            has_stretch = 'stretch' in content.lower()
            print(f"  {os.path.basename(p)}: stretch={'YES' if has_stretch else 'NO'} ({len(content)} chars)")
        else:
            print(f"  {os.path.basename(p)}: MISSING!")
    
    print("\n=== DONE - Ready for patching and building ===")
    print(f"Flutter: {flutter_bin}")
    print(f"Source: {src_dir}")
    print(f"Rust: installed")
    print(f"VS Build Tools: check above")

if __name__ == "__main__":
    main()
