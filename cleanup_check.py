import subprocess, os, sys

# Kill orphaned sshd processes (keep PID 8 which is the main service)
print("=== Cleaning orphaned sshd processes ===")
r = subprocess.run('powershell -Command "Get-Process sshd | Where-Object {$_.Id -gt 1000} | Stop-Process -Force; echo CLEANED"', shell=True, capture_output=True, text=True)
print(r.stdout)
print(r.stderr)

# Count remaining
r = subprocess.run('powershell -Command "(Get-Process sshd).Count"', shell=True, capture_output=True, text=True)
print(f"Remaining sshd processes: {r.stdout.strip()}")

# Check Flutter
print("\n=== Checking Flutter ===")
if os.path.exists(r"C:\flutter\bin\flutter.bat"):
    print("Flutter SDK: INSTALLED")
    r = subprocess.run(r'C:\flutter\bin\flutter.bat --version', shell=True, capture_output=True, text=True)
    print(r.stdout)
else:
    print("Flutter SDK: NOT INSTALLED")

# Check RustDesk source
print("\n=== Checking RustDesk source ===")
if os.path.exists(r"C:\rustdesk_src\flutter\lib\consts.dart"):
    print("RustDesk source: CLONED")
else:
    print("RustDesk source: MISSING")
