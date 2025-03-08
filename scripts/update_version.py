#!/usr/bin/env python
"""
Version management script for the Azure Egress Management project.
"""
import os
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

def get_current_version(setup_file: str) -> str:
    """
    Extract the current version from setup.py.
    
    Args:
        setup_file: Path to setup.py
        
    Returns:
        Current version string
    """
    with open(setup_file, 'r') as f:
        content = f.read()
        
    match = re.search(r'version="([^"]+)"', content)
    if match:
        return match.group(1)
    else:
        return "0.1.0"  # Default version

def update_version(setup_file: str, new_version: str) -> None:
    """
    Update the version in setup.py.
    
    Args:
        setup_file: Path to setup.py
        new_version: New version string
    """
    with open(setup_file, 'r') as f:
        content = f.read()
        
    updated_content = re.sub(r'version="[^"]+"', f'version="{new_version}"', content)
    
    with open(setup_file, 'w') as f:
        f.write(updated_content)
        
    print(f"Updated version to {new_version} in {setup_file}")

def create_changelog_entry(changelog_file: str, new_version: str, changes: str) -> None:
    """
    Add a new entry to the changelog.
    
    Args:
        changelog_file: Path to CHANGELOG.md
        new_version: New version string
        changes: Description of changes
    """
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"""
## [{new_version}] - {today}

{changes}
"""
    
    if not os.path.exists(changelog_file):
        # Create new changelog file
        full_content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
{new_entry}
"""
        with open(changelog_file, 'w') as f:
            f.write(full_content)
        print(f"Created changelog file {changelog_file} with version {new_version}")
        return
        
    # Update existing changelog
    with open(changelog_file, 'r') as f:
        content = f.read()
        
    # Find position to insert (after the header)
    header_end = content.find("## [")
    if header_end == -1:
        # No existing entries, add after the header text
        header_end = content.find("# Changelog")
        if header_end == -1:
            # No header, start at the beginning
            header_end = 0
        else:
            # Skip to the end of the line
            header_end = content.find('\n', header_end) + 1
            
    updated_content = content[:header_end] + new_entry + content[header_end:]
    
    with open(changelog_file, 'w') as f:
        f.write(updated_content)
        
    print(f"Updated changelog file {changelog_file} with version {new_version}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manage project versioning")
    parser.add_argument("--major", action="store_true", help="Bump major version")
    parser.add_argument("--minor", action="store_true", help="Bump minor version")
    parser.add_argument("--patch", action="store_true", help="Bump patch version")
    parser.add_argument("--set-version", help="Set specific version")
    parser.add_argument("--changes", help="Description of changes for changelog")
    
    args = parser.parse_args()
    
    # Determine paths
    project_root = Path(__file__).parent.parent
    setup_file = project_root / "setup.py"
    changelog_file = project_root / "CHANGELOG.md"
    
    # Check if setup.py exists
    if not setup_file.exists():
        print(f"Error: {setup_file} not found")
        return 1
        
    # Get current version
    current_version = get_current_version(str(setup_file))
    print(f"Current version: {current_version}")
    
    # Determine new version
    if args.set_version:
        new_version = args.set_version
    else:
        major, minor, patch = map(int, current_version.split('.'))
        
        if args.major:
            major += 1
            minor = 0
            patch = 0
        elif args.minor:
            minor += 1
            patch = 0
        elif args.patch:
            patch += 1
        else:
            # Default to patch increment if no flag specified
            patch += 1
            
        new_version = f"{major}.{minor}.{patch}"
    
    print(f"New version: {new_version}")
    
    # Update setup.py
    update_version(str(setup_file), new_version)
    
    # Update changelog if changes were provided
    if args.changes:
        create_changelog_entry(str(changelog_file), new_version, args.changes)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
