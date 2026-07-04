#!/usr/bin/env python3
"""Full system inventory of Windows PC for RustDesk build planning."""
import subprocess
import os
import sys
import json
import platform

def ps(cmd):
    """Run PowerShell command and return output. Strips banner noise."""
    r = subprocess.run(f'powershell -NoProfile -Command "{cmd}"', shell=True, capture_output=True, text=True, timeout=30)
    lines = r.stdout.strip().split('\n')
    # Filter out PowerShell banner lines
    lines = [l for l in lines if 'PowerShell 5.1' not in l and 'Uptime:' not in l and "Type 'help'" not in l]
    return '\n'.join(lines).strip()

def cmd(cmd):
    """Run cmd.exe command."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def main():
    report = {}
    
    # === OS INFO ===
    print("=== OS INFO ===")
    report['os'] = {
        'version': os.environ.get('OS', 'unknown'),
        'arch': os.environ.get('PROCESSOR_ARCHITECTURE', 'unknown'),
        'hostname': os.environ.get('COMPUTERNAME', 'unknown'),
        'username': os.environ.get('USERNAME', 'unknown'),
    }
    for k, v in report['os'].items():
        print(f"  {k}: {v}")
    
    # === HARDWARE RESOURCES ===
    print("\n=== HARDWARE ===")
    def safe_int(s):
        try: return int(s.strip())
        except: return 0
    def safe_gb(s, divisor=1e9):
        v = safe_int(s)
        return round(v / divisor, 1) if v else 'unknown'
    
    ram_total = ps('(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory')
    ram_free = ps('(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory')
    disk_total = ps("(Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\").Size")
    disk_free = ps("(Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\").FreeSpace")
    cpu_name = ps('(Get-CimInstance Win32_Processor).Name')
    cpu_cores = ps('(Get-CimInstance Win32_Processor).NumberOfCores')
    gpu_name = ps('(Get-CimInstance Win32_VideoController).Name')
    
    report['hardware'] = {
        'cpu': cpu_name or 'unknown',
        'cpu_cores': cpu_cores or 'unknown',
        'total_ram_gb': safe_gb(ram_total),
        'free_ram_gb': safe_gb(ram_free, 1e6),
        'total_disk_gb': safe_gb(disk_total),
        'free_disk_gb': safe_gb(disk_free),
        'gpu': gpu_name or 'unknown',
    }
    for k, v in report['hardware'].items():
        print(f"  {k}: {v}")
    
    # === INSTALLED DEV TOOLS ===
    print("\n=== DEV TOOLS ===")
    tools = [
        ('python', 'python --version'),
        ('git', 'git --version'),
        ('rustc', 'rustc --version'),
        ('cargo', 'cargo --version'),
        ('flutter', 'flutter --version'),
        ('dart', 'dart --version'),
        ('node', 'node --version'),
        ('npm', 'npm --version'),
        ('java', 'java -version'),
        ('go', 'go version'),
        ('cmake', 'cmake --version'),
        ('msbuild', 'msbuild -version'),
        ('cl (C++ compiler)', 'where cl'),
        ('nmake', 'where nmake'),
        ('7z', 'where 7z'),
        ('curl', 'curl --version'),
        ('wget', 'where wget'),
        ('sshpass', 'where sshpass'),
        ('devin', 'devin --version'),
        ('rustup', 'rustup --version'),
        ('vcpkg', 'where vcpkg'),
    ]
    report['tools'] = {}
    for name, command in tools:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        installed = r.returncode == 0
        version = r.stdout.strip().split('\n')[0] if r.stdout.strip() else (r.stderr.strip().split('\n')[0] if r.stderr.strip() else 'N/A')
        report['tools'][name] = {'installed': installed, 'version': version if installed else 'NOT INSTALLED'}
        print(f"  {name}: {'YES' if installed else 'NO'} - {version if installed else 'NOT INSTALLED'}")
    
    # === VISUAL STUDIO / BUILD TOOLS ===
    print("\n=== VISUAL STUDIO ===")
    vs_paths = [
        r"C:\Program Files\Microsoft Visual Studio",
        r"C:\Program Files (x86)\Microsoft Visual Studio",
        r"C:\Program Files\MSBuild",
        r"C:\Program Files (x86)\MSBuild",
    ]
    report['vs'] = {}
    for vp in vs_paths:
        exists = os.path.exists(vp)
        report['vs'][vp] = exists
        print(f"  {vp}: {'EXISTS' if exists else 'MISSING'}")
        if exists:
            for item in os.listdir(vp):
                print(f"    -> {item}")
    
    # Check for Windows SDK
    sdk_paths = [
        r"C:\Program Files (x86)\Windows Kits\10\Include",
        r"C:\Program Files (x86)\Windows Kits\10\Lib",
    ]
    report['windows_sdk'] = {}
    for sp in sdk_paths:
        exists = os.path.exists(sp)
        report['windows_sdk'][sp] = exists
        print(f"  {sp}: {'EXISTS' if exists else 'MISSING'}")
        if exists:
            versions = os.listdir(sp)
            print(f"    Versions: {versions}")
    
    # === RUSTDESK SPECIFIC ===
    print("\n=== RUSTDESK ===")
    rustdesk_paths = [
        r"C:\Program Files\RustDesk\rustdesk.exe",
        r"C:\Program Files\RustDesk\data\app.so",
        r"C:\rustdesk_src",
        r"C:\rustdesk_src\flutter\lib\consts.dart",
        r"C:\rustdesk_src\flutter\lib\models\model.dart",
        r"C:\rustdesk_src\flutter\pubspec.yaml",
    ]
    report['rustdesk'] = {}
    for rp in rustdesk_paths:
        exists = os.path.exists(rp)
        report['rustdesk'][rp] = exists
        print(f"  {rp}: {'EXISTS' if exists else 'MISSING'}")
    
    # RustDesk version
    r = subprocess.run(r'"C:\Program Files\RustDesk\rustdesk.exe" --version', shell=True, capture_output=True, text=True, timeout=10)
    report['rustdesk']['version'] = r.stdout.strip()
    print(f"  Version: {r.stdout.strip()}")
    
    # Check if source is patched
    consts_path = r"C:\rustdesk_src\flutter\lib\consts.dart"
    if os.path.exists(consts_path):
        with open(consts_path, 'r', encoding='utf-8') as f:
            content = f.read()
        has_stretch = 'stretch' in content.lower()
        report['rustdesk']['source_patched'] = has_stretch
        print(f"  Source patched (stretch): {has_stretch}")
    
    # Check git status of source
    if os.path.exists(r"C:\rustdesk_src"):
        r = subprocess.run('cd C:\\rustdesk_src && git describe --tags 2>&1', shell=True, capture_output=True, text=True, timeout=10)
        report['rustdesk']['git_tag'] = r.stdout.strip()
        print(f"  Git tag: {r.stdout.strip()}")
        r = subprocess.run('cd C:\\rustdesk_src && git log --oneline -1 2>&1', shell=True, capture_output=True, text=True, timeout=10)
        report['rustdesk']['git_commit'] = r.stdout.strip()
        print(f"  Git commit: {r.stdout.strip()}")
    
    # === RUSTDESK CONFIG ===
    print("\n=== RUSTDESK CONFIG ===")
    config_dir = r"C:\Users\Administrator\AppData\Roaming\RustDesk\config"
    report['config'] = {}
    if os.path.exists(config_dir):
        for f in os.listdir(config_dir):
            fpath = os.path.join(config_dir, f)
            is_file = os.path.isfile(fpath)
            is_readonly = not os.access(fpath, os.W_OK) if is_file else False
            report['config'][f] = {'file': is_file, 'readonly': is_readonly}
            print(f"  {f}: {'file' if is_file else 'dir'}{' (READ-ONLY)' if is_readonly else ''}")
    
    # Per-peer config
    peers_dir = os.path.join(config_dir, "peers")
    if os.path.exists(peers_dir):
        print(f"\n  Peers dir contents:")
        for f in os.listdir(peers_dir):
            fpath = os.path.join(peers_dir, f)
            is_readonly = not os.access(fpath, os.W_OK) if os.path.isfile(fpath) else False
            print(f"    {f}{' (READ-ONLY)' if is_readonly else ''}")
            if f.endswith('.toml'):
                try:
                    with open(fpath, 'r', encoding='utf-8') as fh:
                        for line in fh:
                            if any(k in line for k in ['view_style', 'scroll_style', 'custom_scale', 'image_quality']):
                                print(f"      {line.strip()}")
                except:
                    pass
    
    # === RUNNING PROCESSES (relevant) ===
    print("\n=== RELEVANT RUNNING PROCESSES ===")
    relevant = ['rustdesk', 'sshd', 'devin', 'flutter', 'dart', 'cargo', 'rustc']
    for proc in relevant:
        r = subprocess.run(f'powershell -Command "Get-Process {proc} -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64 | Format-Table -AutoSize"', shell=True, capture_output=True, text=True, timeout=10)
        if r.stdout.strip():
            print(f"  {r.stdout.strip()}")
        else:
            print(f"  {proc}: not running")
    
    # === ENVIRONMENT VARIABLES (relevant) ===
    print("\n=== RELEVANT ENV VARS ===")
    env_vars = ['PATH', 'FLUTTER_ROOT', 'DART_SDK', 'RUSTUP_HOME', 'CARGO_HOME', 'VSINSTALLDIR', 'VCINSTALLDIR', 'WindowsSdkDir']
    for ev in env_vars:
        val = os.environ.get(ev, 'NOT SET')
        if ev == 'PATH':
            # Just show if flutter/rust are in path
            has_flutter = 'flutter' in val.lower()
            has_rust = 'cargo' in val.lower() or 'rust' in val.lower()
            print(f"  PATH: flutter={'YES' if has_flutter else 'NO'}, rust={'YES' if has_rust else 'NO'}")
        else:
            print(f"  {ev}: {val}")
    
    # === NETWORK ===
    print("\n=== NETWORK ===")
    report['network'] = {
        'ip': ps('(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress'),
        'mac': ps('(Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -First 1).MacAddress'),
    }
    for k, v in report['network'].items():
        print(f"  {k}: {v}")
    
    # === SAVE REPORT ===
    report_path = r"C:\system_inventory.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n=== Full report saved to {report_path} ===")

if __name__ == "__main__":
    main()
