#!/usr/bin/env python3
"""
Compare SS64 scraped patterns against current destruction_guard patterns.
Generate SQL INSERT for missing patterns only.
"""

# Current patterns from destruction_guard teach_list output
CURRENT_PATTERNS = {
    '/bin/rm', '\brm\b', '\brmdir\b', '\bunlink\b', '\bshutil\.rmtree',
    '\bos\.remove', '\bos\.unlink', '\bDROP\s+TABLE', '\bDELETE\s+FROM',
    '\bTRUNCATE\s+TABLE', '\btruncate\s+-s\s*0', '\bgit\s+push.*-f',
    '\bgit\s+clean.*-f'
}

# SS64 scraped patterns (from parse_ss64_commands.py output)
SS64_PATTERNS = {
    'dd', 'diskutil', 'fdisk', 'fsck', 'gpt', 'halt', 'kill', 'killall',
    'mount', 'rm', 'rmdir', 'shutdown', 'srm', 'umount', 'asr', 'bless',
    'chflags', 'chgrp', 'chmod', 'chown', 'codesign', 'cp', 'csrutil',
    'defaults', 'hdiutil', 'install', 'launchctl', 'mv', 'nvram', 'profiles',
    'rsync', 'security', 'softwareupdate', 'spctl', 'sysctl', 'tar', 'tmutil'
}

# Risk descriptions
RISK_DESCRIPTIONS = {
    'dd': 'Disk destroyer - can overwrite entire disks',
    'diskutil': 'Disk utility - partition/format/erase disks',
    'fdisk': 'Partition table editor - modify disk partitions',
    'fsck': 'Filesystem check - can corrupt if misused',
    'gpt': 'GUID partition table editor',
    'halt': 'Halt the system',
    'kill': 'Terminate processes',
    'killall': 'Terminate all processes by name',
    'mount': 'Mount filesystems',
    'shutdown': 'Shutdown the system',
    'srm': 'Secure remove - permanently delete files',
    'umount': 'Unmount filesystems',
    'asr': 'Apple Software Restore',
    'bless': 'Set boot volume',
    'chflags': 'Change file flags',
    'chgrp': 'Change group ownership',
    'chmod': 'Change file permissions',
    'chown': 'Change file ownership',
    'codesign': 'Modify code signatures',
    'cp': 'Copy files - can overwrite',
    'csrutil': 'Configure System Integrity Protection',
    'defaults': 'Modify system preferences',
    'hdiutil': 'Disk image operations',
    'install': 'Install files - can overwrite',
    'launchctl': 'Control launch daemons/agents',
    'mv': 'Move/rename files - can overwrite',
    'nvram': 'Modify NVRAM settings',
    'profiles': 'Manage configuration profiles',
    'rsync': 'Sync files - can overwrite',
    'security': 'Manage keychains and certificates',
    'softwareupdate': 'Install system updates',
    'spctl': 'Control Gatekeeper',
    'sysctl': 'Modify system parameters',
    'tar': 'Archive files - can overwrite',
    'tmutil': 'Time Machine operations',
}

def is_pattern_in_current(pattern):
    """Check if pattern exists in current patterns."""
    # Check exact match
    if pattern in CURRENT_PATTERNS:
        return True
    
    # Check if pattern is a substring of any current pattern
    for current in CURRENT_PATTERNS:
        if pattern in current:
            return True
    
    return False

def generate_sql_insert(pattern, severity, description):
    """Generate SQL INSERT statement."""
    pattern_type = "literal"
    action = "block" if severity >= 3 else "warn"
    confidence = 0.8 if severity >= 3 else 0.6
    category = "ss64-scraped"
    
    # Escape single quotes
    desc_escaped = description.replace("'", "''")
    
    sql = f"""INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('{pattern}', '{action}', '{category}', {severity}, {confidence}, 'ss64-scrape', '{desc_escaped}', '{pattern_type}');"""
    
    return sql

def main():
    print("Comparing SS64 patterns against current destruction_guard patterns...")
    
    missing_patterns = []
    for pattern in SS64_PATTERNS:
        if not is_pattern_in_current(pattern):
            missing_patterns.append(pattern)
    
    print(f"\n=== MISSING PATTERNS ({len(missing_patterns)}) ===")
    for pattern in missing_patterns:
        print(f"  {pattern}")
    
    # Generate SQL for missing patterns
    print(f"\n=== SQL INSERT STATEMENTS FOR MISSING PATTERNS ===")
    
    with open('missing_patterns.sql', 'w') as f:
        for pattern in missing_patterns:
            severity = 5 if pattern in {'dd', 'diskutil', 'fdisk', 'fsck', 'gpt', 'halt', 'kill', 'killall', 'mount', 'shutdown', 'srm', 'umount'} else 3
            description = RISK_DESCRIPTIONS.get(pattern, "Destructive command")
            sql = generate_sql_insert(pattern, severity, description)
            print(sql)
            f.write(sql + '\n')
    
    print(f"\nSQL statements saved to missing_patterns.sql")

if __name__ == "__main__":
    main()
