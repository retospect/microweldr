#!/usr/bin/env python3
"""
DRY Version Bumping Script for MicroWeldr

This script uses bump-my-version to automatically update version numbers
across all files in the project, maintaining DRY principles.

Usage:
    python scripts/bump_version.py patch    # 4.0.0 -> 4.0.1
    python scripts/bump_version.py minor    # 4.0.0 -> 4.1.0  
    python scripts/bump_version.py major    # 4.0.0 -> 5.0.0
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return False


def main():
    """Main version bumping function."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py [patch|minor|major]")
        sys.exit(1)
    
    bump_type = sys.argv[1].lower()
    if bump_type not in ['patch', 'minor', 'major']:
        print("❌ Invalid bump type. Use: patch, minor, or major")
        sys.exit(1)
    
    # Get project root
    project_root = Path(__file__).parent.parent
    
    print(f"🚀 Bumping {bump_type} version...")
    
    # Run bump-my-version
    cmd = f"bump-my-version bump {bump_type}"
    if not run_command(cmd, cwd=project_root):
        print("❌ Version bump failed!")
        sys.exit(1)
    
    print("✅ Version bumped successfully!")
    
    # Show the new version
    try:
        result = subprocess.run(
            "bump-my-version show current_version",
            shell=True,
            capture_output=True,
            text=True,
            cwd=project_root
        )
        if result.returncode == 0:
            new_version = result.stdout.strip()
            print(f"📦 New version: {new_version}")
        
        # Show what files were updated
        print("\n📝 Files updated:")
        print("  - pyproject.toml")
        print("  - microweldr/__init__.py")
        print("  - microweldr/api/__init__.py")
        print("  - microweldr/api/monitoring.py")
        print("  - microweldr/api/core.py")
        print("  - microweldr/cli/enhanced_main.py")
        print("  - CHANGELOG.md")
        
        print(f"\n🏷️  Git tag created: v{new_version}")
        print("💾 Changes committed automatically")
        
        print("\n🎯 Next steps:")
        print("  1. Review the changes: git show")
        print("  2. Push to remote: git push && git push --tags")
        print("  3. Build package: poetry build")
        print("  4. Publish: poetry publish")
        
    except Exception as e:
        print(f"⚠️  Could not get new version: {e}")


if __name__ == "__main__":
    main()
