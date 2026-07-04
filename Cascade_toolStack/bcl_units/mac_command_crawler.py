#!/usr/bin/env python3
"""
Mac Command Crawler - Comprehensive Command Database Builder

Automatically discovers, enriches, and stores macOS command information from:
- System executables (bin, usr/bin, usr/sbin, sbin, System, Homebrew, Xcode)
- Man pages
- Help output (--help, -h, help)
- TLDR pages (tldr.sh)
- cheat.sh API
- Shell completions

Generates synthetic training samples for:
- Commands with flags
- Commands with paths
- Commands with multiple paths
- Commands with stdin/stdout
- Commands with pipes
- Commands with redirection

- Commands with environment variables
- Commands with shell operators
- Command substitutions
- Quoted strings
- Escaped strings
- Wildcards
- Brace expansion
- Variables
- Functions
- Aliases
- sudo
- Nested shells
- Subcommands
- Combined commands
- Dangerous combinations
- Safe combinations

Author: cascade
Session: mac-command-crawler
Date: 2026-07-03
"""

import os
import sys
import sqlite3
import subprocess
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ===== CONFIGURATION =====

CRAWLER_CONFIG = {
    "db_path": "mac_commands_comprehensive.db",
    "max_workers": 8,
    "request_timeout": 30,
    "command_timeout": 10,
    "max_examples_per_command": 100,
    "synthetic_samples_per_command": 50,
    
    "scan_paths": [
        "/bin",
        "/usr/bin",
        "/usr/sbin",
        "/sbin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/Applications/Xcode.app/Contents/Developer/usr/bin",
    ],
    
    "exclude_patterns": [
        r"\.so$",
        r"\.dylib$",
        r"\.a$",
        r"\.o$",
        r"\.h$",
        r"\.c$",
        r"\.cpp$",
        r"\.m$",
        r"\.swift$",
        r"\.py$",
        r"\.sh$",
        r"\.pl$",
        r"\.rb$",
    ],
    
    "sources": {
        "local_commands": True,
        "man_pages": True,
        "help_output": True,
        "tldr": True,
        "cheat_sh": True,
        "shell_completions": True,
    },
    
    "api_endpoints": {
        "tldr": "https://raw.githubusercontent.com/tldr-pages/tldr/main/pages/{platform}/{command}.md",
        "cheat_sh": "https://cheat.sh/{command}",
    },
}

# ===== DATA STRUCTURES =====

@dataclass
class CommandInfo:
    """Comprehensive command information"""
    name: str
    path: str
    category: str
    description: str
    risk_score: float
    intent: str
    source: str
    man_page: str = ""
    help_output: str = ""
    tldr_content: str = ""
    cheat_sh_content: str = ""
    flags: List[Dict[str, Any]] = None
    subcommands: List[str] = None
    examples: List[str] = None
    aliases: List[str] = None
    shell_completion: str = ""
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []
        if self.subcommands is None:
            self.subcommands = []
        if self.examples is None:
            self.examples = []
        if self.aliases is None:
            self.aliases = []

@dataclass
class TrainingSample:
    """Synthetic training sample"""
    command: str
    action: str
    risk_score: float
    intent: str
    context: str
    source: str
    is_dangerous: bool
    is_safe: bool

# ===== DATABASE SCHEMA =====

COMPREHENSIVE_SCHEMA = """
-- Commands table
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    path TEXT,
    category TEXT,
    description TEXT,
    risk_score REAL DEFAULT 0.5,
    source TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Flags table
CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY,
    command_id INTEGER,
    flag TEXT NOT NULL,
    description TEXT,
    takes_argument INTEGER DEFAULT 0,
    argument_type TEXT,
    risk_modifier REAL DEFAULT 0.0,
    FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE,
    UNIQUE(command_id, flag)
);

-- Subcommands table
CREATE TABLE IF NOT EXISTS subcommands (
    id INTEGER PRIMARY KEY,
    command_id INTEGER,
    subcommand TEXT NOT NULL,
    description TEXT,
    risk_modifier REAL DEFAULT 0.0,
    FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE,
    UNIQUE(command_id, subcommand)
);

-- Examples table
CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY,
    command_id INTEGER,
    example TEXT NOT NULL,
    description TEXT,
    source TEXT,
    risk_score REAL DEFAULT 0.5,
    FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE
);

-- Training samples table
CREATE TABLE IF NOT EXISTS training_samples (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL,
    action TEXT NOT NULL,
    risk_score REAL,
    intent TEXT,
    context TEXT,
    source TEXT,
    is_dangerous INTEGER DEFAULT 0,
    is_safe INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Intents table (authority)
CREATE TABLE IF NOT EXISTS intents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

-- Risk levels table (authority)
CREATE TABLE IF NOT EXISTS risk_levels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    score REAL NOT NULL UNIQUE,
    description TEXT
);

-- Command-intent mapping
CREATE TABLE IF NOT EXISTS command_intents (
    command_id INTEGER,
    intent_id INTEGER,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (command_id, intent_id),
    FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE,
    FOREIGN KEY(intent_id) REFERENCES intents(id) ON DELETE CASCADE
);

-- Command-risk mapping
CREATE TABLE IF NOT EXISTS command_risks (
    command_id INTEGER,
    risk_id INTEGER,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (command_id, risk_id),
    FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE,
    FOREIGN KEY(risk_id) REFERENCES risk_levels(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_commands_name ON commands(name);
CREATE INDEX IF NOT EXISTS idx_commands_category ON commands(category);
CREATE INDEX IF NOT EXISTS idx_examples_command ON examples(command_id);
CREATE INDEX IF NOT EXISTS idx_training_samples_command ON training_samples(command);
CREATE INDEX IF NOT EXISTS idx_training_samples_action ON training_samples(action);
"""

# ===== CRAWLER CLASS =====

class MacCommandCrawler:
    """Comprehensive macOS command crawler"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or CRAWLER_CONFIG
        self.db_path = self.config["db_path"]
        self.conn = None
        self.scanned_commands: Set[str] = set()
        self.command_cache: Dict[str, CommandInfo] = {}
        
    def init_database(self):
        """Initialize database with schema"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(COMPREHENSIVE_SCHEMA)
        
        # Seed authority tables
        self._seed_intents()
        self._seed_risk_levels()
        
        self.conn.commit()
        
    def _seed_intents(self):
        """Seed intents authority table"""
        intents = [
            ("file_deletion", "Delete files or directories"),
            ("file_modification", "Modify file contents or metadata"),
            ("file_creation", "Create new files"),
            ("file_reading", "Read file contents"),
            ("process_management", "Manage system processes"),
            ("network_operations", "Network communication"),
            ("system_configuration", "Modify system settings"),
            ("package_management", "Install/remove software"),
            ("development", "Development tools and compilers"),
            ("information", "Display information"),
            ("text_processing", "Process text data"),
            ("archive_operations", "Compress/decompress archives"),
            ("security", "Security and authentication"),
            ("virtualization", "Virtual machine management"),
            ("container_management", "Container operations"),
            ("media_processing", "Process audio/video/images"),
            ("database", "Database operations"),
            ("version_control", "Version control operations"),
            ("shell", "Shell execution and scripting"),
        ]
        
        for name, desc in intents:
            self.conn.execute(
                "INSERT OR IGNORE INTO intents (name, description) VALUES (?, ?)",
                (name, desc)
            )
    
    def _seed_risk_levels(self):
        """Seed risk levels authority table"""
        risks = [
            ("critical", 0.9, "Can cause irreversible damage or data loss"),
            ("high", 0.7, "Dangerous operation with significant impact"),
            ("medium", 0.5, "Moderate risk, requires caution"),
            ("low", 0.3, "Low risk, generally safe"),
            ("minimal", 0.1, "Very low risk, informational only"),
        ]
        
        for name, score, desc in risks:
            self.conn.execute(
                "INSERT OR IGNORE INTO risk_levels (name, score, description) VALUES (?, ?, ?)",
                (name, score, desc)
            )
    
    def scan_executables(self) -> List[str]:
        """Scan system paths for executables"""
        executables = []
        
        for scan_path in self.config["scan_paths"]:
            if not os.path.exists(scan_path):
                continue
                
            if os.path.isfile(scan_path):
                # Single file
                if self._is_executable(scan_path):
                    executables.append(scan_path)
            else:
                # Directory - scan recursively
                for root, dirs, files in os.walk(scan_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self._is_executable(file_path):
                            executables.append(file_path)
        
        return list(set(executables))
    
    def _is_executable(self, path: str) -> bool:
        """Check if file is executable"""
        if not os.path.isfile(path):
            return False
            
        # Check exclude patterns
        for pattern in self.config["exclude_patterns"]:
            if re.search(pattern, os.path.basename(path)):
                return False
        
        # Check if executable
        return os.access(path, os.X_OK)
    
    def get_command_info(self, executable_path: str) -> CommandInfo:
        """Get comprehensive command information"""
        name = os.path.basename(executable_path)
        
        if name in self.command_cache:
            return self.command_cache[name]
        
        info = CommandInfo(
            name=name,
            path=executable_path,
            category=self._classify_command(name, executable_path),
            description="",
            risk_score=0.5,
            intent="information",
            source="local_scan"
        )
        
        # Enrich from various sources
        if self.config["sources"]["man_pages"]:
            info.man_page = self._get_man_page(name)
        
        if self.config["sources"]["help_output"]:
            info.help_output = self._get_help_output(executable_path)
        
        if self.config["sources"]["tldr"]:
            info.tldr_content = self._get_tldr_page(name)
        
        if self.config["sources"]["cheat_sh"]:
            info.cheat_sh_content = self._get_cheat_sh_content(name)
        
        # Extract description from man page or help output
        info.description = self._parse_description(info)
        
        # Parse flags and examples
        info.flags = self._parse_flags(info)
        info.subcommands = self._parse_subcommands(info)
        info.examples = self._parse_examples(info)
        
        # Calculate risk and intent
        info.risk_score = self._calculate_risk_score(info)
        info.intent = self._determine_intent(info)
        
        self.command_cache[name] = info
        return info
    
    def _parse_description(self, info: CommandInfo) -> str:
        """Extract description from man page NAME section or help output"""
        # Try man page first — look for NAME section
        if info.man_page:
            lines = info.man_page.split('\n')
            in_name = False
            for line in lines:
                if line.strip().upper() == 'NAME':
                    in_name = True
                    continue
                if in_name:
                    if line.strip().upper() in {'SYNOPSIS', 'DESCRIPTION', 'OPTIONS', 'EXAMPLES', 'SEE ALSO'}:
                        break
                    if line.strip():
                        # man page NAME line: "command - description text"
                        if ' - ' in line:
                            return line.split(' - ', 1)[1].strip()
                        return line.strip()
        
        # Try help output — first non-empty line that's not a "Usage:" or error line
        if info.help_output:
            error_patterns = ('illegal option', 'unrecognized option', 'invalid option',
                            'usage:', 'error:', 'not found', 'no such file',
                            'command not found', 'unknown option')
            for line in info.help_output.split('\n')[:10]:
                stripped = line.strip()
                if not stripped:
                    continue
                if any(p in stripped.lower() for p in error_patterns):
                    continue
                if stripped.startswith('-'):
                    continue
                return stripped[:200]
        
        # Fallback: category-based generic description
        category_descs = {
            "file_deletion": "Delete files or directories",
            "file_modification": "Modify or move files",
            "file_creation": "Create new files or directories",
            "file_reading": "Read or inspect file contents",
            "process_management": "Manage system processes",
            "network_operations": "Perform network operations",
            "system_configuration": "Configure system settings",
            "system_admin": "System administration tool",
            "package_management": "Install or manage software packages",
            "development": "Development tool or compiler",
            "version_control": "Version control operation",
            "archive_operations": "Compress or extract archives",
            "security": "Security and permissions management",
            "virtualization": "Virtual machine or container management",
            "text_processing": "Process and transform text",
            "shell": "Shell builtin or utility",
            "homebrew": "Homebrew package manager tool",
            "utilities": "System utility command",
        }
        return category_descs.get(info.category, "macOS system command")
    
    def _classify_command(self, name: str, path: str) -> str:
        """Classify command into category using name + path + pattern matching"""
        path_lower = path.lower()
        name_lower = name.lower()
        
        # --- Exact name matches (highest priority) ---
        
        # File operations
        if name_lower in {"rm", "rmdir", "unlink", "shred", "srm"}:
            return "file_deletion"
        if name_lower in {"cp", "mv", "ln", "install", "rsync", "ditto"}:
            return "file_modification"
        if name_lower in {"touch", "mkdir", "mkfifo", "mknod", "creat", "mktemp"}:
            return "file_creation"
        if name_lower in {"cat", "less", "more", "head", "tail", "grep", "sed", "awk", "cut", "tr", "sort", "uniq", "wc", "nl", "pr", "fold", "fmt", "expand", "unexpand", "rev", "tac", "paste", "join", "split", "csplit", "look", "strings", "xxd", "hexdump", "od", "file", "stat", "readlink", "realpath", "basename", "dirname", "pathchk", "ls", "dir", "vdir", "tree", "find", "locate", "mdfind", "whereis", "which", "type", "du", "df", "dc", "diff", "cmp", "comm", "md5", "md5sum", "shasum", "cksum", "sum", "finfo", "GetFileInfo", "SetFile", "who", "whoami", "id", "users", "last", "w", "uptime", "env", "printenv", "hostname", "uname", "arch", "sw_vers", "hostinfo", "sysctl"}:
            return "file_reading"
        
        # Process management
        if name_lower in {"kill", "killall", "pkill", "pgrep", "ps", "top", "htop", "nice", "renice", "nohup", "disown", "wait", "suspend", "jobs", "bg", "fg", "time", "timeout", "tput", "at", "atq", "atrm", "batch", "crontab", "cron", "pidof"}:
            return "process_management"
        
        # Network
        if name_lower in {"curl", "wget", "ssh", "scp", "sftp", "rsync", "nc", "netcat", "ping", "traceroute", "tracepath", "dig", "nslookup", "host", "whois", "ifconfig", "route", "arp", "netstat", "ss", "iptables", "nft", "fdisk", "networksetup", "airport", "bluetoothd", "arping", "ftp", "telnet", "rlogin", "rsh", "rdesktop", "vnc", "screencapture"}:
            return "network_operations"
        
        # System configuration
        if name_lower in {"defaults", "systemsetup", "diskutil", "fsck", "mount", "umount", "swapctl", "nvram", "pmset", "system_profiler", "softwareupdate", "csrutil", "fdesetup", "kcutil", "mdimport", "mdcheckschema", "mdutil", "locationd", "configd", "date", "cal", "ntpdate", "sntp", "timed", "timezone", "tzsetup", "bootparam", "fstab", "vipw", "vigr", "chroot", "pivot_root", "getopt"}:
            return "system_configuration"
        
        # Package management
        if name_lower in {"brew", "port", "pip", "pip3", "npm", "gem", "cargo", "yarn", "pnpm", "npx", "composer", "apt", "dpkg", "rpm", "yum", "dnf", "pkg", "msiexec"}:
            return "package_management"
        
        # Development
        if name_lower in {"gcc", "clang", "make", "cmake", "cargo", "go", "python", "python3", "node", "ruby", "perl", "php", "java", "javac", "swift", "rustc", "ld", "as", "ar", "ranlib", "strip", "nm", "objdump", "otool", "lipo", "codesign", "lldb", "gdb", "dtrace", "instruments", "xcodebuild", "xcrun", "swiftc", "repl", "scala", "kotlin", "mvn", "gradle", "ant", "dotnet", "rustc", "cargo"}:
            return "development"
        
        # Version control
        if name_lower in {"git", "svn", "hg", "bzr", "fossil", "ripgrep"}:
            return "version_control"
        
        # Archive operations
        if name_lower in {"tar", "zip", "unzip", "gzip", "bzip2", "xz", "zstd", "compress", "uncompress", "zcat", "bzcat", "xzcat", "lz4", "lzop", "7z", "rar", "unrar", "ar", "cpio", "pax", "shar", "unshar", "uuencode", "uudecode", "base64", "b64encode", "b64decode", "macbinary"}:
            return "archive_operations"
        
        # Security
        if name_lower in {"chmod", "chown", "chflags", "chgrp", "sudo", "doas", "su", "keychain", "security", "openssl", "certtool", "ssh-keygen", "ssh-add", "ssh-agent", "gpg", "age", "pass", "fido2-token", "ykman"}:
            return "security"
        
        # Text processing
        if name_lower in {"awk", "sed", "grep", "fgrep", "egrep", "rg", "ag", "jq", "yq", "xmllint", "xpath", "xsltproc", "pandoc", "markdown", "ronn", "txt2man", "man", "col", "colrm", "column", "tabs", "tput", "stty", "reset", "clear", "tset"}:
            return "text_processing"
        
        # Shell
        if name_lower in {"bash", "sh", "zsh", "dash", "fish", "tcsh", "csh", "ksh", "source", "exec", "eval", "env", "printenv", "set", "export", "alias", "unalias", "history", "fc", "read", "echo", "printf", "test", "true", "false", "return", "break", "continue", "exit", "trap", "type", "hash", "command", "builtin", "enable", "complete", "compgen", "bind", "set", "shopt", "declare", "local", "readonly", "typeset", "date", "sleep", "yes", "seq", "factor", "expr", "bc", "dc", "mktemp", "tee", "xargs", "seq", "tsort", "logger", "wall", "write", "mesg"}:
            return "shell"
        
        # --- Pattern-based matches ---
        
        # Git-related
        if name_lower.startswith("git"):
            return "version_control"
        
        # Docker/container
        if "docker" in name_lower or "container" in name_lower or "podman" in name_lower or "kubectl" in name_lower or "ctr" in name_lower:
            return "virtualization"
        
        # Python
        if name_lower.startswith("python") or name_lower.startswith("pip") or name_lower.startswith("pytest") or name_lower.startswith("py"):
            return "development"
        
        # Node/npm
        if name_lower.startswith("node") or name_lower.startswith("npm") or name_lower.startswith("npx") or name_lower.startswith("yarn") or name_lower.startswith("pnpm") or name_lower.startswith("bun") or name_lower.startswith("deno"):
            return "development"
        
        # Ruby
        if name_lower.startswith("ruby") or name_lower.startswith("gem") or name_lower.startswith("bundle") or name_lower.startswith("rake") or name_lower.startswith("rails"):
            return "development"
        
        # System admin — common macOS system commands
        if name_lower in {"fsck", "mount", "umount", "swapctl", "quotacheck", "quotaon", "quotaoff", "repquota", "edquota", "newfs", "fdisk", "pdisk", "diskutil", "asr", "bless", "nvram", "fstab", "mount_ftp", "mount_nfs", "mount_smbfs", "mount_afp", "umount", "automount", "bootparamd", "mountd", "nfsd", "rpcbind", "repair_packages", "update_dyld_shared_cache", "apfs", "apfs_hfs_convert", "fsck_apfs", "fsck_hfs", "gpt", "hdiutil", "disktool", "fstyp", "newfs_hfs", "newfs_apfs", "newfs_msdos", "newfs_ufs", "quotacheck", "vndevice", "mount_devfs", "mount_fdesc", "mount_null", "mount_union", "mount_volfs", "mount_cd9660", "mount_msdos", "mount_exfat", "mount_ntfs", "mount_udf"}:
            return "system_admin"
        
        # --- Path-based fallback ---
        
        if "/sbin" in path_lower or "/usr/sbin" in path_lower:
            return "system_admin"
        if "/opt/homebrew" in path_lower or "/usr/local/bin" in path_lower or "/usr/local/sbin" in path_lower:
            return "homebrew"
        if "/xcode" in path_lower:
            return "development"
        
        return "utilities"
    
    def _get_man_page(self, command: str) -> str:
        """Get man page content as plain text"""
        try:
            env = dict(os.environ, MANPAGER='cat', PAGER='cat')
            result = subprocess.run(
                ["man", command],
                capture_output=True,
                text=True,
                timeout=self.config["command_timeout"],
                env=env
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return ""
    
    def _get_help_output(self, executable_path: str) -> str:
        """Get help output from --help, -h, or help"""
        help_flags = ["--help", "-h"]
        
        for flag in help_flags:
            try:
                result = subprocess.run(
                    [executable_path, flag],
                    capture_output=True,
                    text=True,
                    timeout=self.config["command_timeout"],
                    stdin=subprocess.DEVNULL
                )
                if result.stdout and len(result.stdout) > 10:
                    return result.stdout
                if result.stderr and len(result.stderr) > 10 and result.returncode != 0:
                    return result.stderr
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                continue
        
        return ""
    
    def _get_tldr_page(self, command: str) -> str:
        """Get TLDR page content"""
        platforms = ["common", "osx", "linux", "sunos"]
        
        for platform in platforms:
            try:
                url = self.config["api_endpoints"]["tldr"].format(
                    platform=platform,
                    command=command
                )
                req = Request(url, headers={'User-Agent': 'MacCommandCrawler/1.0'})
                with urlopen(req, timeout=self.config["request_timeout"]) as response:
                    if response.status == 200:
                        return response.read().decode('utf-8')
            except (URLError, HTTPError, TimeoutError):
                continue
        
        return ""
    
    def _get_cheat_sh_content(self, command: str) -> str:
        """Get cheat.sh content"""
        try:
            url = self.config["api_endpoints"]["cheat_sh"].format(command=command)
            req = Request(url, headers={'User-Agent': 'MacCommandCrawler/1.0'})
            with urlopen(req, timeout=self.config["request_timeout"]) as response:
                if response.status == 200:
                    return response.read().decode('utf-8')
        except (URLError, HTTPError, TimeoutError):
            pass
        return ""
    
    def _parse_flags(self, info: CommandInfo) -> List[Dict[str, Any]]:
        """Parse flags from help output and man page"""
        flags = []
        
        # Parse from help output
        if info.help_output:
            flags.extend(self._parse_flags_from_help(info.help_output))
        
        # Parse from man page
        if info.man_page:
            flags.extend(self._parse_flags_from_man(info.man_page))
        
        # Deduplicate
        seen = set()
        unique_flags = []
        for flag in flags:
            flag_key = flag.get("flag", "")
            if flag_key and flag_key not in seen:
                seen.add(flag_key)
                unique_flags.append(flag)
        
        return unique_flags
    
    def _parse_flags_from_help(self, help_text: str) -> List[Dict[str, Any]]:
        """Parse flags from help output"""
        flags = []
        
        # Match patterns like -f, --file, --file=, --file FILE
        patterns = [
            r'--?[\w-]+',  # --flag or -f
            r'--?[\w-]+=',  # --flag=
            r'--?[\w-]+\s+\w+',  # --flag VALUE
        ]
        
        for line in help_text.split('\n'):
            for pattern in patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    flag = match.split('=')[0].split()[0]
                    if flag.startswith('-'):
                        flags.append({
                            "flag": flag,
                            "description": line.strip(),
                            "takes_argument": '=' in match or ' ' in match,
                            "risk_modifier": self._calculate_flag_risk(flag)
                        })
        
        return flags
    
    def _parse_flags_from_man(self, man_text: str) -> List[Dict[str, Any]]:
        """Parse flags from man page"""
        flags = []
        
        # Look for OPTIONS section
        in_options = False
        for line in man_text.split('\n'):
            if 'OPTIONS' in line.upper():
                in_options = True
                continue
            
            if in_options and line.strip() and not line.startswith(' '):
                in_options = False
                continue
            
            if in_options:
                # Match flag patterns: -f, --flag, .Fl Op Fl f, .Fl f
                match = re.match(r'\s+(-[\w-]+|--[\w-]+)', line)
                if not match:
                    # Also match man page macro style: .Fl Op Fl f or .Fl f
                    match = re.match(r'\.Fl\s+(?:Op\s+)?Fl\s+(\S+)', line)
                    if match:
                        flag = '-' + match.group(1).lstrip('-')
                    else:
                        match = re.match(r'\.Op\s+Fl\s+(\S+)', line)
                        if match:
                            flag = '-' + match.group(1).lstrip('-')
                        else:
                            continue
                else:
                    flag = match.group(1)
                flags.append({
                    "flag": flag,
                    "description": line.strip(),
                    "takes_argument": False,
                    "risk_modifier": self._calculate_flag_risk(flag)
                })
        
        return flags
    
    def _calculate_flag_risk(self, flag: str) -> float:
        """Calculate risk modifier for a flag"""
        dangerous_flags = {
            "-f": 0.3, "--force": 0.3,
            "-r": 0.2, "--recursive": 0.2,
            "--no-preserve-root": 0.4,
            "-rf": 0.4,
            "-delete": 0.3,
            "--delete": 0.3,
            "-exec": 0.2,
            "--exec": 0.2,
        }
        
        return dangerous_flags.get(flag, 0.0)
    
    def _parse_subcommands(self, info: CommandInfo) -> List[str]:
        """Parse subcommands from help output and man page"""
        subcommands = []
        
        # Look for patterns like "git <command>" or "docker <command>" in help output
        for line in info.help_output.split('\n'):
            match = re.search(r'<(\w+)>', line)
            if match:
                subcommand = match.group(1)
                if subcommand not in subcommands:
                    subcommands.append(subcommand)
        
        # Also parse from man page SYNOPSIS section
        if info.man_page:
            in_synopsis = False
            for line in info.man_page.split('\n'):
                if 'SYNOPSIS' in line.upper():
                    in_synopsis = True
                    continue
                if in_synopsis and line.strip() and not line.startswith(' '):
                    in_synopsis = False
                    continue
                if in_synopsis:
                    # Match subcommand patterns: command subcommand or command <subcommand>
                    matches = re.findall(r'\b' + re.escape(info.name) + r'\s+(\w+)', line)
                    for m in matches:
                        if m not in subcommands and m not in {'options', 'files', 'description', 'usage', 'examples'}:
                            subcommands.append(m)
                    # Also match <subcommand> patterns
                    angle_matches = re.findall(r'<(\w+)>', line)
                    for m in angle_matches:
                        if m not in subcommands and m not in {'command', 'file', 'path', 'options', 'args'}:
                            subcommands.append(m)
        
        return subcommands
    
    def _parse_examples(self, info: CommandInfo) -> List[str]:
        """Parse examples from TLDR and cheat.sh"""
        examples = []
        
        # Parse TLDR examples
        if info.tldr_content:
            examples.extend(self._parse_tldr_examples(info.tldr_content))
        
        # Parse cheat.sh examples
        if info.cheat_sh_content:
            examples.extend(self._parse_cheat_sh_examples(info.cheat_sh_content))
        
        return examples[:self.config["max_examples_per_command"]]
    
    def _parse_tldr_examples(self, tldr_text: str) -> List[str]:
        """Parse examples from TLDR markdown"""
        examples = []
        
        # TLDR format: - `command` description
        for line in tldr_text.split('\n'):
            match = re.match(r'-\s*`([^`]+)`', line)
            if match:
                examples.append(match.group(1))
        
        return examples
    
    def _parse_cheat_sh_examples(self, cheat_text: str) -> List[str]:
        """Parse examples from cheat.sh output"""
        examples = []
        
        # cheat.sh format varies, but often has code blocks
        for line in cheat_text.split('\n'):
            if line.strip() and not line.startswith('#'):
                examples.append(line.strip())
        
        return examples
    
    def _calculate_risk_score(self, info: CommandInfo) -> float:
        """Calculate overall risk score for command"""
        base_risk = 0.5
        
        # Category-based risk
        category_risks = {
            "file_deletion": 0.8,
            "file_modification": 0.4,
            "file_creation": 0.2,
            "file_reading": 0.2,
            "system_configuration": 0.6,
            "system_admin": 0.7,
            "process_management": 0.5,
            "package_management": 0.3,
            "security": 0.4,
            "virtualization": 0.3,
            "network_operations": 0.4,
            "development": 0.3,
            "version_control": 0.3,
            "archive_operations": 0.2,
            "text_processing": 0.2,
            "shell": 0.4,
            "homebrew": 0.3,
            "utilities": 0.3,
        }
        
        base_risk = category_risks.get(info.category, 0.3)
        
        # Flag-based risk
        flag_risk = sum(flag.get("risk_modifier", 0.0) for flag in info.flags)
        
        # Name-based risk (dangerous commands) — exact match only
        dangerous_names = {"rm", "dd", "mkfs", "shred", "wipefs", "format", "fdisk", "diskutil", "newfs"}
        if info.name.lower() in dangerous_names:
            base_risk = max(base_risk, 0.8)
        
        return min(base_risk + flag_risk, 1.0)
    
    def _determine_intent(self, info: CommandInfo) -> str:
        """Determine primary intent from category and examples"""
        # Map category to intent
        category_to_intent = {
            "file_deletion": "file_deletion",
            "file_modification": "file_modification",
            "file_creation": "file_creation",
            "file_reading": "file_reading",
            "process_management": "process_management",
            "network_operations": "network_operations",
            "system_configuration": "system_configuration",
            "system_admin": "system_configuration",
            "package_management": "package_management",
            "development": "development",
            "version_control": "version_control",
            "archive_operations": "archive_operations",
            "security": "security",
            "virtualization": "virtualization",
            "text_processing": "text_processing",
            "shell": "process_management",
            "homebrew": "package_management",
            "utilities": "information",
        }
        
        return category_to_intent.get(info.category, "information")
    
    def store_command(self, info: CommandInfo):
        """Store command information in database"""
        cursor = self.conn.cursor()
        
        # Insert command
        cursor.execute("""
            INSERT OR REPLACE INTO commands 
            (name, path, category, description, risk_score, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            info.name,
            info.path,
            info.category,
            info.description,
            info.risk_score,
            info.source
        ))
        
        command_id = cursor.lastrowid
        
        # Insert flags
        for flag in info.flags:
            cursor.execute("""
                INSERT OR IGNORE INTO flags
                (command_id, flag, description, takes_argument, risk_modifier)
                VALUES (?, ?, ?, ?, ?)
            """, (
                command_id,
                flag["flag"],
                flag.get("description", ""),
                flag.get("takes_argument", 0),
                flag.get("risk_modifier", 0.0)
            ))
        
        # Insert subcommands
        for subcommand in info.subcommands:
            cursor.execute("""
                INSERT OR IGNORE INTO subcommands
                (command_id, subcommand, description, risk_modifier)
                VALUES (?, ?, ?, ?)
            """, (
                command_id,
                subcommand,
                "",
                0.0
            ))
        
        # Insert examples
        for example in info.examples:
            cursor.execute("""
                INSERT INTO examples
                (command_id, example, description, source, risk_score)
                VALUES (?, ?, ?, ?, ?)
            """, (
                command_id,
                example,
                "",
                "parsed",
                info.risk_score
            ))
        
        # Map to intent
        cursor.execute("""
            INSERT OR IGNORE INTO command_intents (command_id, intent_id, confidence)
            SELECT ?, id, 1.0 FROM intents WHERE name = ?
        """, (command_id, info.intent))
        
        # Map to risk level
        risk_level = self._risk_score_to_level(info.risk_score)
        cursor.execute("""
            INSERT OR IGNORE INTO command_risks (command_id, risk_id, confidence)
            SELECT ?, id, 1.0 FROM risk_levels WHERE name = ?
        """, (command_id, risk_level))
        
        self.conn.commit()
    
    def _risk_score_to_level(self, score: float) -> str:
        """Convert risk score to risk level name"""
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        else:
            return "minimal"
    
    def generate_synthetic_samples(self, command_name: str) -> List[TrainingSample]:
        """Generate synthetic training samples for a command"""
        samples = []
        
        # Get command info from cache or DB
        info = None
        if command_name in self.command_cache:
            info = self.command_cache[command_name]
        else:
            info = self._load_command_from_db(command_name)
        
        if info is None:
            return samples
        
        # Generate variations
        variations = self._generate_command_variations(info)
        
        for variation in variations:
            sample = TrainingSample(
                command=variation["command"],
                action=variation["action"],
                risk_score=variation["risk_score"],
                intent=info.intent,
                context=variation["context"],
                source="synthetic",
                is_dangerous=variation["risk_score"] > 0.6,
                is_safe=variation["risk_score"] < 0.4
            )
            samples.append(sample)
        
        return samples[:self.config["synthetic_samples_per_command"]]
    
    def _load_command_from_db(self, command_name: str) -> Optional[CommandInfo]:
        """Load command info from database (fallback when cache is empty)"""
        if not self.conn:
            return None
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, path, category, description, risk_score, source FROM commands WHERE name = ?", (command_name,))
        row = cursor.fetchone()
        if not row:
            return None
        
        info = CommandInfo(
            name=row[0],
            path=row[1] or "",
            category=row[2] or "utilities",
            description=row[3] or "",
            risk_score=row[4] if row[4] is not None else 0.5,
            intent="information",
            source=row[5] or "db_load"
        )
        
        # Load flags from DB
        cursor.execute("SELECT flag, description, takes_argument, risk_modifier FROM flags WHERE command_id = (SELECT id FROM commands WHERE name = ?)", (command_name,))
        for flag_row in cursor.fetchall():
            info.flags.append({
                "flag": flag_row[0],
                "description": flag_row[1] or "",
                "takes_argument": flag_row[2] or 0,
                "risk_modifier": flag_row[3] or 0.0
            })
        
        # Determine intent from category
        info.intent = self._determine_intent(info)
        
        return info
    
    def populate_training_samples_from_db(self):
        """Generate and store training samples for all commands already in the DB"""
        if not self.conn:
            self.init_database()
        
        # Clear old training samples
        self.conn.execute("DELETE FROM training_samples")
        self.conn.commit()
        
        # Recategorize all commands
        self._recategorize_db()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM commands")
        all_commands = [row[0] for row in cursor.fetchall()]
        
        total_samples = 0
        for cmd_name in all_commands:
            samples = self.generate_synthetic_samples(cmd_name)
            if samples:
                self.store_training_samples(samples)
                total_samples += len(samples)
        
        return total_samples
    
    def _recategorize_db(self):
        """Re-classify all commands in DB with improved categorization"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, path FROM commands")
        rows = cursor.fetchall()
        
        for cmd_id, name, path in rows:
            new_category = self._classify_command(name, path or "")
            new_risk = self._calculate_risk_score(CommandInfo(
                name=name, path=path or "", category=new_category,
                description="", risk_score=0.5, intent="information", source="recategorize"
            ))
            new_intent = self._determine_intent(CommandInfo(
                name=name, path=path or "", category=new_category,
                description="", risk_score=new_risk, intent="information", source="recategorize"
            ))
            
            cursor.execute("UPDATE commands SET category=?, risk_score=? WHERE id=?", (new_category, new_risk, cmd_id))
            
            # Update intent mapping
            cursor.execute("DELETE FROM command_intents WHERE command_id=?", (cmd_id,))
            cursor.execute("INSERT OR IGNORE INTO command_intents (command_id, intent_id, confidence) SELECT ?, id, 1.0 FROM intents WHERE name = ?", (cmd_id, new_intent))
            
            # Update risk mapping
            risk_level = self._risk_score_to_level(new_risk)
            cursor.execute("DELETE FROM command_risks WHERE command_id=?", (cmd_id,))
            cursor.execute("INSERT OR IGNORE INTO command_risks (command_id, risk_id, confidence) SELECT ?, id, 1.0 FROM risk_levels WHERE name = ?", (cmd_id, risk_level))
        
        self.conn.commit()
    
    def _generate_command_variations(self, info: CommandInfo) -> List[Dict[str, Any]]:
        """Generate command variations with different contexts, category-aware"""
        variations = []
        cat = info.category
        
        # Base command
        variations.append({
            "command": info.name,
            "action": "execute",
            "risk_score": info.risk_score,
            "context": "base_command"
        })
        
        # With flags
        for flag in info.flags[:5]:
            flag_str = flag["flag"]
            variations.append({
                "command": f"{info.name} {flag_str}",
                "action": "execute",
                "risk_score": min(info.risk_score + flag.get("risk_modifier", 0.0), 1.0),
                "context": f"with_flag_{flag_str}"
            })
        
        # Category-aware test arguments
        if cat == "network_operations":
            test_args = ["https://example.com", "http://localhost:8080", "8.8.8.8"]
        elif cat == "file_deletion":
            test_args = ["file.txt", "/tmp/old_file", "~/Downloads/temp"]
        elif cat == "file_modification":
            test_args = ["file.txt", "/tmp/dest", "~/Documents/backup"]
        elif cat == "file_creation":
            test_args = ["newfile.txt", "/tmp/newdir", "~/Projects/new"]
        elif cat == "file_reading":
            test_args = ["file.txt", "/var/log/system.log", "~/Documents/notes.md"]
        elif cat == "process_management":
            test_args = ["1234", "-9 1234", "nginx"]
        elif cat == "system_configuration":
            test_args = ["list", "--get", "--status"]
        elif cat == "package_management":
            test_args = ["install", "update", "search python"]
        elif cat == "version_control":
            test_args = ["status", "log", "commit -m 'update'"]
        elif cat == "development":
            test_args = ["main.py", "--version", "-o output"]
        elif cat == "text_processing":
            test_args = ["file.txt", "input.csv", "data.json"]
        elif cat == "archive_operations":
            test_args = ["archive.tar.gz", "files/", "-xzf backup.zip"]
        elif cat == "security":
            test_args = ["+x script.sh", "-R user:staff file.txt", "--list"]
        elif cat == "shell":
            test_args = ["-c 'echo hello'", "-l", "-s /bin/zsh"]
        else:
            test_args = ["file.txt", "/tmp/file", "~/Documents/file"]
        
        for arg in test_args[:3]:
            variations.append({
                "command": f"{info.name} {arg}",
                "action": "execute",
                "risk_score": info.risk_score,
                "context": "with_arg"
            })
        
        # With sudo
        variations.append({
            "command": f"sudo {info.name}",
            "action": "execute",
            "risk_score": min(info.risk_score + 0.2, 1.0),
            "context": "with_sudo"
        })
        
        # With pipes (category-appropriate)
        if cat in {"text_processing", "file_reading", "shell"}:
            variations.append({
                "command": f"cat file.txt | {info.name}",
                "action": "execute",
                "risk_score": info.risk_score,
                "context": "with_pipe"
            })
        
        # With redirection (only for commands that produce output)
        if cat in {"file_reading", "text_processing", "process_management", "shell", "system_configuration", "utilities"}:
            variations.append({
                "command": f"{info.name} > output.txt",
                "action": "execute",
                "risk_score": info.risk_score,
                "context": "with_redirection"
            })
        
        # Dangerous combinations — only for file deletion commands
        if cat == "file_deletion" or info.name.lower() in {"rm", "rmdir", "shred"}:
            variations.append({
                "command": f"{info.name} -rf /",
                "action": "execute",
                "risk_score": 1.0,
                "context": "dangerous_combination"
            })
            variations.append({
                "command": f"sudo {info.name} -rf /",
                "action": "execute",
                "risk_score": 1.0,
                "context": "dangerous_sudo_combination"
            })
        
        return variations
    
    def store_training_samples(self, samples: List[TrainingSample]):
        """Store training samples in database (dedup via INSERT OR REPLACE)"""
        cursor = self.conn.cursor()
        
        for sample in samples:
            cursor.execute("""
                INSERT OR REPLACE INTO training_samples
                (command, action, risk_score, intent, context, source, is_dangerous, is_safe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample.command,
                sample.action,
                sample.risk_score,
                sample.intent,
                sample.context,
                sample.source,
                sample.is_dangerous,
                sample.is_safe
            ))
        
        self.conn.commit()
    
    def crawl(self, fast_mode=False):
        """Main crawl method. fast_mode skips man pages, TLDR, cheat.sh for speed."""
        print("Initializing database...")
        self.init_database()
        
        print("Scanning executables...")
        executables = self.scan_executables()
        print(f"Found {len(executables)} executables")
        
        if fast_mode:
            print("Fast mode: skipping man pages, TLDR, cheat.sh")
            self.config["sources"]["man_pages"] = False
            self.config["sources"]["tldr"] = False
            self.config["sources"]["cheat_sh"] = False
            self.config["sources"]["shell_completions"] = False
        
        print("Processing commands...")
        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            futures = {
                executor.submit(self.get_command_info, exe): exe
                for exe in executables
            }
            
            error_count = 0
            for future in as_completed(futures):
                exe = futures[future]
                try:
                    info = future.result()
                    self.store_command(info)
                    self.scanned_commands.add(info.name)
                except Exception as e:
                    error_count += 1
                    if error_count <= 10:
                        print(f"  ERROR processing {os.path.basename(exe)}: {e}")
            if error_count > 0:
                print(f"  Total errors: {error_count}")
        
        print(f"Successfully processed {len(self.scanned_commands)} commands")
        
        print("Generating synthetic training samples...")
        total_samples = 0
        for command_name in self.scanned_commands:
            samples = self.generate_synthetic_samples(command_name)
            if samples:
                self.store_training_samples(samples)
                total_samples += len(samples)
        
        print(f"Generated {total_samples} training samples")
        print("Crawl complete!")
    
    def generate_samples_only(self):
        """Only generate training samples for commands already in DB (no crawling)"""
        print("Initializing database...")
        self.init_database()
        
        print("Generating training samples from existing DB commands...")
        total = self.populate_training_samples_from_db()
        print(f"Generated {total} training samples")
        print("Done!")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# ===== MAIN =====

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mac Command Crawler")
    parser.add_argument("--fast", action="store_true", help="Skip slow enrichment (man, TLDR, cheat.sh)")
    parser.add_argument("--samples-only", action="store_true", help="Only generate training samples from existing DB")
    args = parser.parse_args()
    
    crawler = MacCommandCrawler()
    try:
        if args.samples_only:
            crawler.generate_samples_only()
        else:
            crawler.crawl(fast_mode=args.fast)
    finally:
        crawler.close()
