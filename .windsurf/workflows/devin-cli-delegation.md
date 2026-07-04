---
description: How to correctly delegate tasks to Devin CLI — lessons learned from RustDesk scaling task
---

# Devin CLI Delegation Workflow

## What Worked

1. **`devin -p "task"`** — Non-interactive print mode. Runs a single task and returns output. Works for simple tasks.
2. **`devin --permission-mode dangerous -p "task"`** — Required for tasks that need to run shell commands, install software, or modify files. Without this, Devin refuses to execute and only suggests commands.
3. **SSH + SCP + run script on remote** — Writing a Python script locally, SCPing it to the Windows machine, then running it via SSH worked reliably.
4. **`expect -c 'spawn ssh... expect "password:" send "2002\r"'`** — SSH with password auth through expect worked consistently for Windows OpenSSH.
5. **Devin installed on Windows** — Devin CLI (v2026.5.26) was already installed on the Windows PC at `C:\Users\Administrator\AppData\Local\devin\cli\bin\devin.exe`. Running Devin directly on the target machine avoids SSH-in-SSH complexity.

## What Did NOT Work

1. **`devin run --task "..."`** — `run` is NOT a valid subcommand. Error: `unexpected argument 'run' found`. Correct syntax is `devin -p "task"` or `devin -- "task"`.
2. **Long multi-line commands via `expect`** — Long task descriptions with quotes, backslashes, and newlines get mangled by expect's string escaping. The terminal freezes or the command gets truncated.
3. **`devin -p "..."` without `--permission-mode dangerous`** — Devin refuses to execute commands in default mode. It only suggests commands for manual execution. Must use `--permission-mode dangerous` for autonomous execution.
4. **PowerShell string replacement via SSH expect** — Single quotes, double quotes, and backslashes in PowerShell commands get eaten by expect's Tcl interpreter. Use Python scripts instead.
5. **Editing files via SSH expect with complex replacements** — Regex replacements with single quotes in TOML files (e.g., `view_style = 'adaptive'`) fail because expect/Tcl interprets the quotes. Always write a Python script, SCP it, and run it.
6. **Background `devin -p` from Mac SSHing to Windows** — Running Devin on Mac with instructions to SSH into Windows works for simple tasks but Devin on Mac doesn't have `sshpass` installed by default and the expect wrapper adds complexity.

## Correct Patterns

### Pattern 1: Simple task (Mac local)
```bash
devin -p "Do X with files in /path/to/dir"
```

### Pattern 2: Task needing command execution
```bash
devin --permission-mode dangerous -p "Install X, build Y, deploy Z"
```

### Pattern 3: Task on remote Windows machine
```bash
# 1. Write task description to a file locally
# 2. SCP the file to Windows
scp -o StrictHostKeyChecking=no task.txt administrator@192.168.8.50:C:/task.txt

# 3. SSH in and run Devin on Windows with the task file
ssh administrator@192.168.8.50
devin --permission-mode dangerous -p "Read C:\task.txt and execute all steps"
```

### Pattern 4: Complex file editing on remote Windows
```bash
# 1. Write a Python script locally that does the edits
# 2. SCP it to Windows
scp fix_script.py administrator@192.168.8.50:C:/fix.py

# 3. Run it via SSH
ssh administrator@192.168.8.50 "python C:\fix.py"
```

## Terminal Management Lessons (CRITICAL)

### SSH Session Leaks
- **Problem**: Each `expect -c 'spawn ssh...'` creates a new SSH connection. If the expect process is killed, canceled, or times out, the SSH session on the remote machine stays open as an orphaned `sshd` process.
- **Evidence**: After ~10 SSH commands, Windows had 7 orphaned `sshd.exe` processes in task manager.
- **Fix**: Always send `exit\r` before `expect eof`. If a command is canceled, SSH back in and kill orphaned sessions: `powershell -Command "Get-Process sshd | Where-Object {$_.Id -ne 8} | Stop-Process -Force"`
- **Rule**: ONE SSH session at a time. Check `command_status` before opening a new SSH connection.

### Terminal Freezing
- **Problem**: Long-running commands via `expect` block the terminal. If the remote command takes >30 seconds, expect appears frozen.
- **Fix**: Use `Blocking: false` with `WaitMsBeforeAsync` for long commands. Check with `command_status` periodically.
- **Alternative**: Write a Python script, SCP it, run it with `python script.py > output.txt 2>&1`, then retrieve output.txt separately.

### Command Cancellation
- **Problem**: When user presses Ctrl+C or cancels a step, the expect process dies but the remote SSH session and any remote processes (like Devin) may continue running.
- **Fix**: After cancellation, SSH back in and check for orphaned processes. Kill them if needed.

### Resource Awareness
- **Check before starting**: Is a previous command still running? Use `command_status` on the previous command ID.
- **Check remote resources**: Don't start heavy downloads/builds without checking disk space and available RAM.
- **One heavy task at a time**: Don't run multiple SSH sessions doing heavy work simultaneously on a low-resource machine.
- **Windows 10 with 189GB free disk**: Enough for Flutter SDK (~3GB) + Rust toolchain (~2GB) + RustDesk source + build artifacts.

### Proper SSH Exit Pattern
```tcl
# CORRECT - always exits cleanly
expect -c '
spawn ssh -o StrictHostKeyChecking=no administrator@192.168.8.50
expect "password:"
send "2002\r"
expect ">"
send "your command here\r"
expect ">"
send "exit\r"
expect eof
'
```

### Cleanup Orphaned SSH Sessions
```tcl
# Kill all sshd except the main service (PID 8)
expect -c '
spawn ssh -o StrictHostKeyChecking=no administrator@192.168.8.50
expect "password:"
send "2002\r"
expect ">"
send "powershell -Command \"Get-Process sshd | Where-Object {$_.Id -ne 8} | Stop-Process -Force\"\r"
expect ">"
send "exit\r"
expect eof
'
```

## Key Rules

1. **Always use `--permission-mode dangerous`** for tasks that require running commands
2. **Never use `devin run`** — it's `devin -p` or `devin --`
3. **Write task to a file** for complex multi-step tasks — avoids shell escaping hell
4. **Use Python scripts for file editing** on remote machines — not PowerShell via expect
5. **Run Devin on the target machine** when possible — avoids SSH-in-SSH
6. **Check Devin version on target** before assuming it's installed
7. **Background long Devin tasks** with `WaitMsBeforeAsync` and check with `command_status`
8. **Devin CLI is not Devin cloud** — CLI has limited context window, no persistent sessions across calls
9. **Always `send "exit\r"` before `expect eof`** — prevents orphaned SSH sessions
10. **Check `command_status` on previous commands** before starting new SSH sessions
11. **One SSH session at a time** — don't stack connections
12. **Clean up orphaned sshd processes** if commands were canceled
13. **Check remote disk/RAM** before starting heavy downloads or builds
14. **Use `interact` in expect** for long-running Devin sessions so output streams live

## Devin CLI Commands Reference

| Command | Purpose |
|---------|---------|
| `devin -p "task"` | Non-interactive single task (print mode) |
| `devin -- "task"` | Interactive session |
| `devin --permission-mode dangerous -p "task"` | Auto-approve all tool execution |
| `devin /list-sessions` | List previous sessions (interactive menu) |
| `devin list --format json` | List sessions as JSON (scriptable) |
| `devin -r` | Resume a session (interactive picker) |
| `devin -r <session-id>` | Resume a specific session by ID |
| `devin --version` | Check version |
| `devin --help` | Show help |
| `devin auth login` | Authenticate with Devin account |
| `devin cloud drs ...` | Declarative Repo Setup (sandbox sessions/builds) |
| `/handoff` | Push current session to cloud Devin VM (no args = continue) |
| `/handoff <task>` | Push to cloud with a specific task |
| `/clear` | Start a fresh conversation in current session |
| `/help` | Show available slash commands |

## Session Management

- **List sessions**: `devin /list-sessions` (interactive) or `devin list --format json` (scriptable)
- **Resume a session**: `devin -r` (interactive picker) or `devin -r <session-id>` (direct)
- **Cannot switch sessions from inside a running session** — must exit first, then resume from terminal
- **Session IDs are human-readable** (e.g., `marvelous-culotte`, `supreme-wrinkle`, `solar-calcium`)
- **Sessions are per-directory** — listed under `~/Qdrant_mysql_mlx_vector_engine`

## /handoff — Cloud Offloading (DETAILED)

### What it does
- Pushes current terminal session to a cloud Devin VM
- Cloud VM has shell, browser, and full repo access
- Keeps running after you close your laptop
- Carries over repo, branch, conversation context, and uncommitted diff
- Track progress in terminal or at https://app.devin.ai

### Prerequisites
- **MUST be in a git repo with a remote configured** — `/handoff` fails with "No git remote found" if not
- Must be authenticated (`devin auth login`)
- The current workspace (`~/Qdrant_mysql_mlx_vector_engine`) is NOT a git repo — `/handoff` will fail here
- `git remote -v` must return at least one remote URL
- `git rev-parse --is-inside-work-tree` must succeed (must be inside a `.git` repo)

### When /handoff fails (no git repo/remote)
Devin presents a 4-option menu:
1. **I run it via SSH** — Devin SSHes from Mac into remote machine, does everything step by step, confirms before each install/build/replace
2. **Init git repo first** — Set up git repo + remote so cloud handoff works (need to provide remote URL e.g. GitHub repo)
3. **Just patch the files** — Skip remote build, prepare patches locally for manual application on remote machine
4. **Stop, rethink** — Don't do anything yet

**Best choice for remote Windows tasks**: Option 1 (SSH from Mac). No git repo needed, Devin runs commands directly.
**Best choice for heavy builds**: Option 2 (init git repo + remote, then `/handoff` to cloud VM with more resources).
**Best choice for quick patches**: Option 3 (prepare patches locally, apply manually).

### Devin's safety behavior on risky tasks
When a task involves irreversible changes (installing software, replacing binaries), Devin will:
- Flag risks before starting (credentials in plaintext, scope is irreversible, build may fail)
- Ask for confirmation before each major step
- NOT auto-proceed even with `--permission-mode dangerous` for destructive actions
- Warn about credentials appearing in shell commands

### When /handoff is NOT available (no git repo)
- Use `devin --permission-mode dangerous -p "task"` locally instead
- Or start a cloud session from scratch at https://app.devin.ai
- Or init a git repo + add a remote, then `/handoff` works

### /handoff is all-or-nothing
- NOT a per-task router — no auto-offload for heavy tasks
- After `/handoff`: EVERYTHING runs in cloud (model inference, builds, embeddings, browsers)
- Before `/handoff`: EVERYTHING runs locally on your Mac
- No "detect heavy task and send to cloud" automatic behavior

### Practical pattern for 8GB Mac
- **Light work locally**: reading code, small edits, planning, chatting → `devin -p "task"`
- **Heavy work to cloud**: embeddings, document ingestion, builds → `/handoff` or web app
- **Alternative**: Start directly at https://app.devin.ai for heavy tasks (no CLI needed)

## Devin CLI vs Devin Cloud (UPDATED)

| Feature | Devin CLI (local) | Devin Cloud (/handoff) | Devin Web (app.devin.ai) |
|---------|-------------------|------------------------|--------------------------|
| Execution | Runs on local machine | Cloud VM | Cloud VM |
| Git repo required | No | Yes (with remote) | No (can create) |
| File access | Direct local filesystem | Repo checkout on VM | Repo checkout on VM |
| Permission mode | `--permission-mode dangerous` | Auto-approved | Auto-approved |
| Context window | ~200k tokens | Carries over from CLI | Fresh |
| Sessions | `/list-sessions`, `-r` | Continues from CLI | Web-based |
| Browser access | No | Yes | Yes |
| Heavy builds | Slow on 8GB Mac | Fast on cloud VM | Fast on cloud VM |
| Best for | Quick edits, file ops | Continuing work in cloud | Starting fresh in cloud |
| Closes laptop | Session dies | Keeps running | Keeps running |

### When to use Devin Cloud instead of CLI
- Building from source (Flutter SDK + Rust + VS Build Tools = hours of installs)
- Multi-file patching across a codebase
- Tasks that need web access (downloading SDKs, reading docs)
- When the local machine is low on resources (8GB Mac)
- When the task will take >10 minutes
- Embeddings / document ingestion pipelines

### IDE Integrations (ACP)
- JetBrains (IntelliJ, PyCharm, GoLand) including Remote Development
- Zed
- Drive Devin from editor's AI Chat / Agent Panel
- Docs: jetbrains.mdx, zed.mdx

**For remote Windows machine access via Devin Cloud:**
- Devin Cloud VM can SSH to external machines
- Provide SSH credentials (IP, user, password) in the handoff prompt
- Devin Cloud has internet access directly (can download SDKs, read docs)

## SSH to Windows PC (192.168.8.50)

```
User: administrator
Password: 2002
Shell: cmd.exe (use powershell -Command "..." for complex ops)
Devin: C:\Users\Administrator\AppData\Local\devin\cli\bin\devin.exe (v2026.5.26)
Python: 3.14
Git: installed
Rust: installed (C:\Users\Administrator\.cargo\bin\)
Flutter: NOT installed (needs download)
VS Build Tools: NOT installed (needs download)
RustDesk: v1.4.8 at C:\Program Files\RustDesk\
RustDesk source: C:\rustdesk_src (cloned, not patched)
Disk space: ~189GB free
```

## Error Log (real errors encountered)

1. `devin run --task` → `unexpected argument 'run' found` — wrong subcommand
2. `devin -p` without `--permission-mode dangerous` → Devin refuses to execute, only suggests commands
3. Long expect commands with quotes/backslashes → terminal freezes, commands truncated
4. PowerShell `echo` with single quotes → quotes eaten by cmd.exe, TOML values corrupted (e.g., `custom_scale_percent = '` instead of `custom_scale_percent = '100'`)
5. `python -c "complex code"` via expect → Tcl interprets Python string escapes, corrupts the command
6. `expect -timeout 300` with `interact` → blocks forever, had to Ctrl+C
7. Canceled expect commands → orphaned sshd.exe processes on Windows (7 found)
8. SCP with expect → works but adds another SSH session if not cleaned up
9. `timeout /t 3 /nobreak >nul` via expect → sometimes the `>` redirect doesn't work in cmd.exe through expect
10. `taskkill /f /im rustdesk.exe` → `ERROR: The service cannot be started` — rustdesk runs as service, need `net stop rustdesk` instead
11. `/handoff` → `Handoff failed: No git remote found` — workspace must be a git repo WITH a remote configured
12. `devin /session marvelous-culotte` → `Unknown command /session` — use `devin -r <session-id>` to resume, not `/session`
13. `devin session list` → `unexpected argument 'session'` — `session` is not a subcommand. Use `devin list` or `devin /list-sessions`
14. PowerShell `Get-WmiObject` via `powershell -Command` from Python → returns empty string or banner noise. Use `Get-CimInstance` instead, and always use `-NoProfile` flag
15. `$_` in PowerShell commands via expect → Tcl interprets `$_` as a Tcl variable. Must escape as `\\$_` or use Python subprocess instead
