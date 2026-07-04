#!/bin/bash
# =============================================================================
# File: disable_spotlight.sh
# Created: June 23, 2026
# Reason: Spotlight indexing was consuming 30% CPU and 200MB RAM on an 8GB Mac
# Idea: Permanently disable Spotlight indexing and remove the menu bar icon
# =============================================================================

# 1. Turn off indexing on all volumes
sudo mdutil -a -i off

# 2. Erase existing index
sudo mdutil -E /

# 3. Disable Spotlight launch agent (stops it from starting on boot)
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.metadata.mds.plist
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.metadata.mds.scan.plist 2>/dev/null

# 4. Kill current processes
sudo killall mds mds_stores mdworker_shared 2>/dev/null

echo "Spotlight disabled. To re-enable later:"
echo "  sudo mdutil -a -i on"
echo "  sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.metadata.mds.plist"
