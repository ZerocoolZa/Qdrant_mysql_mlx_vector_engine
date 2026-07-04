INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('mount', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Mount filesystems', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('spctl', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Control Gatekeeper', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('codesign', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Modify code signatures', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('cp', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Copy files - can overwrite', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('security', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Manage keychains and certificates', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('umount', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Unmount filesystems', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('chgrp', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Change group ownership', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('killall', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Terminate all processes by name', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('hdiutil', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Disk image operations', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('asr', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Apple Software Restore', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('chown', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Change file ownership', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('dd', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Disk destroyer - can overwrite entire disks', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('srm', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Secure remove - permanently delete files', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('halt', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Halt the system', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('kill', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Terminate processes', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('fsck', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Filesystem check - can corrupt if misused', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('shutdown', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Shutdown the system', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('nvram', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Modify NVRAM settings', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('gpt', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'GUID partition table editor', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('fdisk', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Partition table editor - modify disk partitions', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('softwareupdate', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Install system updates', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('launchctl', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Control launch daemons/agents', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('diskutil', 'block', 'ss64-scraped', 5, 0.8, 'ss64-scrape', 'Disk utility - partition/format/erase disks', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('csrutil', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Configure System Integrity Protection', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('bless', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Set boot volume', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('sysctl', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Modify system parameters', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('chflags', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Change file flags', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('profiles', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Manage configuration profiles', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('install', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Install files - can overwrite', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('tar', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Archive files - can overwrite', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('mv', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Move/rename files - can overwrite', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('defaults', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Modify system preferences', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('chmod', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Change file permissions', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('tmutil', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Time Machine operations', 'literal');
INSERT INTO patterns 
    (pattern, action, category, severity, confidence, source, description, pattern_type)
    VALUES ('rsync', 'block', 'ss64-scraped', 3, 0.8, 'ss64-scrape', 'Sync files - can overwrite', 'literal');
