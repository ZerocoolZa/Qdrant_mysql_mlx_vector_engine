#!/usr/bin/env python3
"""
Mac Command Database Generator
Creates a comprehensive SQLite database of Mac commands with intent and risk classifications.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Database schema
SCHEMA = """
-- Base commands table
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT,
    path TEXT,
    builtin INTEGER DEFAULT 0,
    requires_root INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Command flags table
CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY,
    command_id INTEGER NOT NULL,
    flag TEXT NOT NULL,
    description TEXT,
    risk_modifier REAL DEFAULT 0.0,
    FOREIGN KEY (command_id) REFERENCES commands(id)
);

-- Intent classifications
CREATE TABLE IF NOT EXISTS intents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT
);

-- Risk levels
CREATE TABLE IF NOT EXISTS risk_levels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    score REAL NOT NULL,
    description TEXT
);

-- Command-intent mapping
CREATE TABLE IF NOT EXISTS command_intents (
    command_id INTEGER NOT NULL,
    intent_id INTEGER NOT NULL,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (command_id, intent_id),
    FOREIGN KEY (command_id) REFERENCES commands(id),
    FOREIGN KEY (intent_id) REFERENCES intents(id)
);

-- Command-risk mapping
CREATE TABLE IF NOT EXISTS command_risks (
    command_id INTEGER NOT NULL,
    risk_id INTEGER NOT NULL,
    context TEXT,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (command_id, risk_id, context),
    FOREIGN KEY (command_id) REFERENCES commands(id),
    FOREIGN KEY (risk_id) REFERENCES risk_levels(id)
);

-- Training examples
CREATE TABLE IF NOT EXISTS training_examples (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL,
    intent_id INTEGER,
    risk_id INTEGER,
    context TEXT,
    risk_score REAL,
    approved INTEGER DEFAULT 0,
    source TEXT DEFAULT 'synthetic',
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (intent_id) REFERENCES intents(id),
    FOREIGN KEY (risk_id) REFERENCES risk_levels(id)
);

-- Context zones
CREATE TABLE IF NOT EXISTS context_zones (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    risk_multiplier REAL DEFAULT 1.0,
    description TEXT
);
"""

# Command data
COMMANDS = {
    # Filesystem - Delete
    'rm': {
        'category': 'filesystem',
        'description': 'Remove files or directories',
        'path': '/bin/rm',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-r': {'desc': 'Recursive', 'risk_mod': 0.3},
            '-f': {'desc': 'Force', 'risk_mod': 0.2},
            '-i': {'desc': 'Interactive', 'risk_mod': -0.1},
            '-v': {'desc': 'Verbose', 'risk_mod': 0.0},
            '-rf': {'desc': 'Recursive force', 'risk_mod': 0.5},
            '-ri': {'desc': 'Recursive interactive', 'risk_mod': 0.2},
            '-rfv': {'desc': 'Recursive force verbose', 'risk_mod': 0.5},
        }
    },
    'rmdir': {
        'category': 'filesystem',
        'description': 'Remove empty directories',
        'path': '/bin/rmdir',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-p': {'desc': 'Parent directories', 'risk_mod': 0.2},
        }
    },
    'unlink': {
        'category': 'filesystem',
        'description': 'Remove file',
        'path': '/usr/bin/unlink',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    
    # Filesystem - Move/Copy
    'mv': {
        'category': 'filesystem',
        'description': 'Move or rename files',
        'path': '/bin/mv',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-f': {'desc': 'Force overwrite', 'risk_mod': 0.2},
            '-i': {'desc': 'Interactive', 'risk_mod': -0.1},
            '-n': {'desc': 'No clobber', 'risk_mod': -0.2},
        }
    },
    'cp': {
        'category': 'filesystem',
        'description': 'Copy files',
        'path': '/bin/cp',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-r': {'desc': 'Recursive', 'risk_mod': 0.1},
            '-f': {'desc': 'Force', 'risk_mod': 0.2},
            '-i': {'desc': 'Interactive', 'risk_mod': -0.1},
            '-a': {'desc': 'Archive', 'risk_mod': 0.0},
        }
    },
    
    # Filesystem - Modify
    'chmod': {
        'category': 'filesystem',
        'description': 'Change file permissions',
        'path': '/bin/chmod',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-R': {'desc': 'Recursive', 'risk_mod': 0.3},
            '-v': {'desc': 'Verbose', 'risk_mod': 0.0},
        }
    },
    'chown': {
        'category': 'filesystem',
        'description': 'Change file owner',
        'path': '/usr/sbin/chown',
        'builtin': 0,
        'requires_root': 1,
        'flags': {
            '-R': {'desc': 'Recursive', 'risk_mod': 0.4},
        }
    },
    'touch': {
        'category': 'filesystem',
        'description': 'Create empty file or update timestamp',
        'path': '/usr/bin/touch',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'truncate': {
        'category': 'filesystem',
        'description': 'Truncate file to size',
        'path': '/usr/bin/truncate',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-s': {'desc': 'Size', 'risk_mod': 0.0},
        }
    },
    
    # Disk operations
    'dd': {
        'category': 'disk',
        'description': 'Convert and copy a file',
        'path': '/bin/dd',
        'builtin': 0,
        'requires_root': 1,
        'flags': {
            'if': {'desc': 'Input file', 'risk_mod': 0.3},
            'of': {'desc': 'Output file', 'risk_mod': 0.5},
            'bs': {'desc': 'Block size', 'risk_mod': 0.0},
        }
    },
    'mkfs': {
        'category': 'disk',
        'description': 'Make filesystem',
        'path': '/sbin/mkfs',
        'builtin': 0,
        'requires_root': 1,
        'flags': {}
    },
    'diskutil': {
        'category': 'disk',
        'description': 'Disk utility',
        'path': '/usr/sbin/diskutil',
        'builtin': 0,
        'requires_root': 1,
        'flags': {
            'eraseDisk': {'desc': 'Erase disk', 'risk_mod': 1.0},
            'partitionDisk': {'desc': 'Partition disk', 'risk_mod': 0.8},
            'reformat': {'desc': 'Reformat', 'risk_mod': 0.7},
        }
    },
    
    # Compression
    'tar': {
        'category': 'compression',
        'description': 'Archive files',
        'path': '/usr/bin/tar',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-x': {'desc': 'Extract', 'risk_mod': 0.1},
            '-c': {'desc': 'Create', 'risk_mod': 0.0},
            '-f': {'desc': 'File', 'risk_mod': 0.0},
        }
    },
    'zip': {
        'category': 'compression',
        'description': 'Package files',
        'path': '/usr/bin/zip',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'unzip': {
        'category': 'compression',
        'description': 'Extract zip files',
        'path': '/usr/bin/unzip',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    
    # Find operations
    'find': {
        'category': 'filesystem',
        'description': 'Search for files',
        'path': '/usr/bin/find',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-delete': {'desc': 'Delete found files', 'risk_mod': 0.8},
            '-exec': {'desc': 'Execute command', 'risk_mod': 0.6},
        }
    },
    'xargs': {
        'category': 'filesystem',
        'description': 'Execute commands from stdin',
        'path': '/usr/bin/xargs',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    
    # Git
    'git': {
        'category': 'version_control',
        'description': 'Version control',
        'path': '/usr/bin/git',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            'push': {'desc': 'Push changes', 'risk_mod': 0.2},
            'push -f': {'desc': 'Force push', 'risk_mod': 0.8},
            'reset': {'desc': 'Reset changes', 'risk_mod': 0.5},
            'clean': {'desc': 'Clean untracked', 'risk_mod': 0.4},
            'clean -fdx': {'desc': 'Force clean', 'risk_mod': 0.7},
        }
    },
    
    # Shell
    'bash': {
        'category': 'shell',
        'description': 'Bash shell',
        'path': '/bin/bash',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'sh': {
        'category': 'shell',
        'description': 'POSIX shell',
        'path': '/bin/sh',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'zsh': {
        'category': 'shell',
        'description': 'Z shell',
        'path': '/bin/zsh',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'source': {
        'category': 'shell',
        'description': 'Source script',
        'path': None,
        'builtin': 1,
        'requires_root': 0,
        'flags': {}
    },
    'exec': {
        'category': 'shell',
        'description': 'Execute command',
        'path': None,
        'builtin': 1,
        'requires_root': 0,
        'flags': {}
    },
    'eval': {
        'category': 'shell',
        'description': 'Evaluate expression',
        'path': None,
        'builtin': 1,
        'requires_root': 0,
        'flags': {}
    },
    
    # Python
    'python': {
        'category': 'programming',
        'description': 'Python interpreter',
        'path': '/usr/bin/python3',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-c': {'desc': 'Execute string', 'risk_mod': 0.3},
        }
    },
    'python3': {
        'category': 'programming',
        'description': 'Python 3 interpreter',
        'path': '/usr/bin/python3',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-c': {'desc': 'Execute string', 'risk_mod': 0.3},
        }
    },
    
    # SQLite
    'sqlite3': {
        'category': 'database',
        'description': 'SQLite command line',
        'path': '/usr/bin/sqlite3',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    
    # Networking
    'curl': {
        'category': 'networking',
        'description': 'Transfer data from URL',
        'path': '/usr/bin/curl',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-o': {'desc': 'Output file', 'risk_mod': 0.1},
        }
    },
    'wget': {
        'category': 'networking',
        'description': 'Download files',
        'path': '/usr/local/bin/wget',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'scp': {
        'category': 'networking',
        'description': 'Secure copy',
        'path': '/usr/bin/scp',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'ssh': {
        'category': 'networking',
        'description': 'Secure shell',
        'path': '/usr/bin/ssh',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'rsync': {
        'category': 'networking',
        'description': 'Remote sync',
        'path': '/usr/bin/rsync',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '--delete': {'desc': 'Delete destination', 'risk_mod': 0.6},
            '-a': {'desc': 'Archive', 'risk_mod': 0.0},
        }
    },
    'nc': {
        'category': 'networking',
        'description': 'Netcat',
        'path': '/usr/bin/nc',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    
    # System
    'launchctl': {
        'category': 'system',
        'description': 'Launch control',
        'path': '/bin/launchctl',
        'builtin': 0,
        'requires_root': 1,
        'flags': {
            'stop': {'desc': 'Stop service', 'risk_mod': 0.4},
            'start': {'desc': 'Start service', 'risk_mod': 0.2},
            'unload': {'desc': 'Unload service', 'risk_mod': 0.5},
        }
    },
    'kill': {
        'category': 'system',
        'description': 'Terminate process',
        'path': '/bin/kill',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-9': {'desc': 'Force kill', 'risk_mod': 0.3},
        }
    },
    'killall': {
        'category': 'system',
        'description': 'Kill all processes by name',
        'path': '/usr/bin/killall',
        'builtin': 0,
        'requires_root': 0,
        'flags': {
            '-9': {'desc': 'Force kill', 'risk_mod': 0.4},
        }
    },
    'pkill': {
        'category': 'system',
        'description': 'Kill processes by pattern',
        'path': '/usr/bin/pkill',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
    'sudo': {
        'category': 'system',
        'description': 'Execute as superuser',
        'path': '/usr/bin/sudo',
        'builtin': 0,
        'requires_root': 0,
        'flags': {}
    },
}

# Intent classifications
INTENTS = {
    'DeleteFile': {'category': 'destructive', 'desc': 'Delete a file'},
    'DeleteDirectory': {'category': 'destructive', 'desc': 'Delete a directory'},
    'MoveFile': {'category': 'modify', 'desc': 'Move or rename a file'},
    'CopyFile': {'category': 'modify', 'desc': 'Copy a file'},
    'ModifyPermissions': {'category': 'modify', 'desc': 'Change file permissions'},
    'ChangeOwner': {'category': 'modify', 'desc': 'Change file owner'},
    'CreateFile': {'category': 'create', 'desc': 'Create a new file'},
    'ExecuteProgram': {'category': 'execute', 'desc': 'Execute a program'},
    'DownloadFile': {'category': 'network', 'desc': 'Download a file from network'},
    'ReadFile': {'category': 'read', 'desc': 'Read file contents'},
    'WriteFile': {'category': 'write', 'desc': 'Write to a file'},
    'EraseDisk': {'category': 'destructive', 'desc': 'Erase a disk'},
    'FormatDisk': {'category': 'destructive', 'desc': 'Format a disk'},
    'KillProcess': {'category': 'system', 'desc': 'Terminate a process'},
    'ModifyDatabase': {'category': 'database', 'desc': 'Modify database contents'},
    'ModifyGit': {'category': 'version_control', 'desc': 'Modify git repository'},
    'CompressFiles': {'category': 'compression', 'desc': 'Compress files'},
    'ExtractFiles': {'category': 'compression', 'desc': 'Extract compressed files'},
    'ExecuteShell': {'category': 'shell', 'desc': 'Execute shell command'},
    'ElevatePrivileges': {'category': 'security', 'desc': 'Run with elevated privileges'},
}

# Risk levels
RISK_LEVELS = {
    'SAFE': {'score': 0.0, 'desc': 'No risk'},
    'LOW': {'score': 0.2, 'desc': 'Low risk'},
    'MEDIUM': {'score': 0.5, 'desc': 'Medium risk'},
    'HIGH': {'score': 0.8, 'desc': 'High risk'},
    'CRITICAL': {'score': 1.0, 'desc': 'Critical risk'},
}

# Context zones
CONTEXT_ZONES = {
    '/tmp': {'mult': 0.2, 'desc': 'Temporary files - low risk'},
    '/var/tmp': {'mult': 0.2, 'desc': 'Temporary files - low risk'},
    '/Users': {'mult': 0.5, 'desc': 'User directories - medium risk'},
    '/Applications': {'mult': 0.6, 'desc': 'Applications - medium-high risk'},
    '/System': {'mult': 1.0, 'desc': 'System files - critical risk'},
    '/Library': {'mult': 0.9, 'desc': 'Library files - high risk'},
    '/etc': {'mult': 1.0, 'desc': 'Configuration - critical risk'},
    '/usr': {'mult': 0.9, 'desc': 'System binaries - high risk'},
    '/bin': {'mult': 1.0, 'desc': 'System binaries - critical risk'},
    '/sbin': {'mult': 1.0, 'desc': 'System binaries - critical risk'},
    '~': {'mult': 0.4, 'desc': 'Home directory - low-medium risk'},
    '/Volumes': {'mult': 0.7, 'desc': 'Mounted volumes - high risk'},
}

# Command-intent mappings
COMMAND_INTENTS = {
    'rm': ['DeleteFile', 'DeleteDirectory'],
    'rmdir': ['DeleteDirectory'],
    'unlink': ['DeleteFile'],
    'mv': ['MoveFile'],
    'cp': ['CopyFile'],
    'chmod': ['ModifyPermissions'],
    'chown': ['ChangeOwner'],
    'touch': ['CreateFile'],
    'truncate': ['WriteFile'],
    'dd': ['WriteFile', 'EraseDisk'],
    'mkfs': ['FormatDisk'],
    'diskutil': ['EraseDisk', 'FormatDisk'],
    'tar': ['CompressFiles', 'ExtractFiles'],
    'zip': ['CompressFiles'],
    'unzip': ['ExtractFiles'],
    'find': ['ReadFile', 'DeleteFile'],
    'git': ['ModifyGit'],
    'bash': ['ExecuteShell'],
    'sh': ['ExecuteShell'],
    'zsh': ['ExecuteShell'],
    'source': ['ExecuteShell'],
    'exec': ['ExecuteShell'],
    'eval': ['ExecuteShell'],
    'python': ['ExecuteProgram'],
    'python3': ['ExecuteProgram'],
    'sqlite3': ['ModifyDatabase', 'ReadFile'],
    'curl': ['DownloadFile'],
    'wget': ['DownloadFile'],
    'scp': ['CopyFile'],
    'ssh': ['ExecuteShell'],
    'rsync': ['CopyFile', 'DeleteFile'],
    'nc': ['ExecuteShell'],
    'launchctl': ['KillProcess'],
    'kill': ['KillProcess'],
    'killall': ['KillProcess'],
    'pkill': ['KillProcess'],
    'sudo': ['ElevatePrivileges'],
}

# Command-risk mappings
COMMAND_RISKS = {
    'rm': ['HIGH'],
    'rmdir': ['MEDIUM'],
    'unlink': ['MEDIUM'],
    'mv': ['LOW'],
    'cp': ['LOW'],
    'chmod': ['MEDIUM'],
    'chown': ['HIGH'],
    'touch': ['SAFE'],
    'truncate': ['MEDIUM'],
    'dd': ['CRITICAL'],
    'mkfs': ['CRITICAL'],
    'diskutil': ['CRITICAL'],
    'tar': ['LOW'],
    'zip': ['SAFE'],
    'unzip': ['LOW'],
    'find': ['MEDIUM'],
    'git': ['MEDIUM'],
    'bash': ['MEDIUM'],
    'sh': ['MEDIUM'],
    'zsh': ['MEDIUM'],
    'source': ['MEDIUM'],
    'exec': ['MEDIUM'],
    'eval': ['HIGH'],
    'python': ['MEDIUM'],
    'python3': ['MEDIUM'],
    'sqlite3': ['MEDIUM'],
    'curl': ['LOW'],
    'wget': ['LOW'],
    'scp': ['LOW'],
    'ssh': ['MEDIUM'],
    'rsync': ['MEDIUM'],
    'nc': ['MEDIUM'],
    'launchctl': ['HIGH'],
    'kill': ['MEDIUM'],
    'killall': ['HIGH'],
    'pkill': ['HIGH'],
    'sudo': ['HIGH'],
}


def create_database(db_path: str):
    """Create the command database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Execute schema
    for statement in SCHEMA.split(';'):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)
    
    conn.commit()
    return conn


def populate_commands(conn):
    """Populate the commands table."""
    cursor = conn.cursor()
    
    for cmd_name, cmd_data in COMMANDS.items():
        cursor.execute("""
            INSERT OR REPLACE INTO commands 
            (name, category, description, path, builtin, requires_root)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            cmd_name,
            cmd_data['category'],
            cmd_data['description'],
            cmd_data['path'],
            cmd_data['builtin'],
            cmd_data['requires_root']
        ))
        
        # Get command ID
        cmd_id = cursor.lastrowid
        
        # Insert flags
        for flag, flag_data in cmd_data['flags'].items():
            cursor.execute("""
                INSERT INTO flags (command_id, flag, description, risk_modifier)
                VALUES (?, ?, ?, ?)
            """, (cmd_id, flag, flag_data['desc'], flag_data['risk_mod']))
    
    conn.commit()


def populate_intents(conn):
    """Populate the intents table."""
    cursor = conn.cursor()
    
    for intent_name, intent_data in INTENTS.items():
        cursor.execute("""
            INSERT OR REPLACE INTO intents (name, category, description)
            VALUES (?, ?, ?)
        """, (intent_name, intent_data['category'], intent_data['desc']))
    
    conn.commit()


def populate_risk_levels(conn):
    """Populate the risk levels table."""
    cursor = conn.cursor()
    
    for risk_name, risk_data in RISK_LEVELS.items():
        cursor.execute("""
            INSERT OR REPLACE INTO risk_levels (name, score, description)
            VALUES (?, ?, ?)
        """, (risk_name, risk_data['score'], risk_data['desc']))
    
    conn.commit()


def populate_context_zones(conn):
    """Populate the context zones table."""
    cursor = conn.cursor()
    
    for zone_path, zone_data in CONTEXT_ZONES.items():
        cursor.execute("""
            INSERT OR REPLACE INTO context_zones (path, risk_multiplier, description)
            VALUES (?, ?, ?)
        """, (zone_path, zone_data['mult'], zone_data['desc']))
    
    conn.commit()


def populate_command_intents(conn):
    """Populate command-intent mappings."""
    cursor = conn.cursor()
    
    for cmd_name, intent_names in COMMAND_INTENTS.items():
        # Get command ID
        cursor.execute("SELECT id FROM commands WHERE name = ?", (cmd_name,))
        cmd_row = cursor.fetchone()
        if not cmd_row:
            continue
        cmd_id = cmd_row[0]
        
        # Get intent IDs
        for intent_name in intent_names:
            cursor.execute("SELECT id FROM intents WHERE name = ?", (intent_name,))
            intent_row = cursor.fetchone()
            if intent_row:
                intent_id = intent_row[0]
                cursor.execute("""
                    INSERT OR REPLACE INTO command_intents (command_id, intent_id, confidence)
                    VALUES (?, ?, 1.0)
                """, (cmd_id, intent_id))
    
    conn.commit()


def populate_command_risks(conn):
    """Populate command-risk mappings."""
    cursor = conn.cursor()
    
    for cmd_name, risk_names in COMMAND_RISKS.items():
        # Get command ID
        cursor.execute("SELECT id FROM commands WHERE name = ?", (cmd_name,))
        cmd_row = cursor.fetchone()
        if not cmd_row:
            continue
        cmd_id = cmd_row[0]
        
        # Get risk IDs
        for risk_name in risk_names:
            cursor.execute("SELECT id FROM risk_levels WHERE name = ?", (risk_name,))
            risk_row = cursor.fetchone()
            if risk_row:
                risk_id = risk_row[0]
                cursor.execute("""
                    INSERT OR REPLACE INTO command_risks (command_id, risk_id, context, confidence)
                    VALUES (?, ?, '', 1.0)
                """, (cmd_id, risk_id))
    
    conn.commit()


def generate_training_examples(conn):
    """Generate synthetic training examples."""
    cursor = conn.cursor()
    
    # Generate examples for each command
    for cmd_name, cmd_data in COMMANDS.items():
        cursor.execute("SELECT id FROM commands WHERE name = ?", (cmd_name,))
        cmd_row = cursor.fetchone()
        if not cmd_row:
            continue
        cmd_id = cmd_row[0]
        
        # Get intent and risk
        cursor.execute("""
            SELECT intent_id FROM command_intents WHERE command_id = ?
        """, (cmd_id,))
        intent_row = cursor.fetchone()
        intent_id = intent_row[0] if intent_row else None
        
        cursor.execute("""
            SELECT risk_id FROM command_risks WHERE command_id = ?
        """, (cmd_id,))
        risk_row = cursor.fetchone()
        risk_id = risk_row[0] if risk_row else None
        
        # Get risk score
        if risk_id:
            cursor.execute("SELECT score FROM risk_levels WHERE id = ?", (risk_id,))
            score_row = cursor.fetchone()
            risk_score = score_row[0] if score_row else 0.5
        else:
            risk_score = 0.5
        
        # Generate base example
        cursor.execute("""
            INSERT INTO training_examples (command, intent_id, risk_id, context, risk_score, source)
            VALUES (?, ?, ?, ?, ?, 'synthetic')
        """, (cmd_name, intent_id, risk_id, '', risk_score))
        
        # Generate examples with flags
        for flag, flag_data in cmd_data['flags'].items():
            cmd_with_flag = f"{cmd_name} {flag}"
            modified_risk = min(1.0, risk_score + flag_data['risk_mod'])
            
            cursor.execute("""
                INSERT INTO training_examples (command, intent_id, risk_id, context, risk_score, source)
                VALUES (?, ?, ?, ?, ?, 'synthetic')
            """, (cmd_with_flag, intent_id, risk_id, '', modified_risk))
    
    conn.commit()


def main():
    """Main function to generate the database."""
    db_path = Path(__file__).parent / "mac_commands.db"
    
    print(f"Creating database at {db_path}")
    conn = create_database(str(db_path))
    
    print("Populating commands...")
    populate_commands(conn)
    
    print("Populating intents...")
    populate_intents(conn)
    
    print("Populating risk levels...")
    populate_risk_levels(conn)
    
    print("Populating context zones...")
    populate_context_zones(conn)
    
    print("Populating command-intent mappings...")
    populate_command_intents(conn)
    
    print("Populating command-risk mappings...")
    populate_command_risks(conn)
    
    print("Generating training examples...")
    generate_training_examples(conn)
    
    # Print statistics
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM commands")
    print(f"Commands: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM flags")
    print(f"Flags: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM intents")
    print(f"Intents: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM training_examples")
    print(f"Training examples: {cursor.fetchone()[0]}")
    
    conn.close()
    print("Database generation complete!")


if __name__ == "__main__":
    main()
