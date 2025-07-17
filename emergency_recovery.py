#!/usr/bin/env python3
"""
WakeDock v0.6.3 - Emergency Code Recovery
Restore files from Black formatter damage
"""

import os
import subprocess
import sys
from pathlib import Path

def emergency_git_restore():
    """Emergency restore using git if available"""
    try:
        # Check if we're in a git repository
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            print("🔄 Git repository detected, attempting restore...")
            
            # Restore all Python files to last commit
            restore_result = subprocess.run([
                'git', 'checkout', 'HEAD', '--', '**/*.py'
            ], capture_output=True, text=True)
            
            if restore_result.returncode == 0:
                print("✅ Successfully restored files from git")
                return True
            else:
                print(f"❌ Git restore failed: {restore_result.stderr}")
                return False
        else:
            print("⚠️  Not in a git repository")
            return False
    except Exception as e:
        print(f"❌ Git restore error: {e}")
        return False

def main():
    """Main recovery function"""
    print("🚨 WakeDock v0.6.3 - Emergency Code Recovery")
    print("=" * 50)
    print("Black formatter has introduced syntax errors.")
    print("Attempting recovery...")
    
    # Try git restore first
    if emergency_git_restore():
        print("\n✅ Files restored successfully!")
        print("🎯 You can now proceed with manual code standardization")
        return True
    
    print("\n❌ Automatic recovery failed")
    print("\n🔧 Manual recovery steps:")
    print("1. Use your editor's undo functionality")
    print("2. Restore from backup if available")
    print("3. Use git stash/reset if in git repository")
    print("4. Manually fix syntax errors in key files")
    
    print("\n📋 Priority files to fix:")
    priority_files = [
        "wakedock/core/performance_monitor.py",
        "wakedock/core/cache.py", 
        "wakedock/core/exceptions.py",
        "wakedock/main.py",
        "wakedock/config.py"
    ]
    
    for file_path in priority_files:
        print(f"   • {file_path}")
    
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
