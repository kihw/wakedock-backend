#!/usr/bin/env python3
"""
WakeDock v0.6.3 - Docstring Formatting Fix
Fix encoding issues introduced by Black formatter
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any

def fix_docstring_encoding(file_path: Path) -> bool:
    """Fix docstring encoding issues in a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern to match corrupted docstrings
        patterns = [
            # Fix \1\n patterns in docstrings
            (r'\\1\\n\s*"""\s*\\n\s*\\1([^\\]+)\\1\\n\s*"""', r'"""\n    \1\n    """'),
            
            # Fix simple \1 patterns
            (r'\\1([^\\]+)\\1', r'\1'),
            
            # Fix escaped newlines in docstrings
            (r'\\n\s*"""\s*\\n', r'"""\n    '),
            (r'\\n\s*"""', r'\n    """'),
            
            # Fix specific patterns we see
            (r'"""\s*\\n\s*\\1([^\\]+)\\1\\n\s*"""', r'"""\n    \1\n    """'),
            
            # Fix class/function docstring patterns
            (r'class\s+(\w+).*?:\s*\\1\\n\s*"""\s*\\n\s*\\1([^\\]+)\\1\\n\s*"""', 
             r'class \1:\n    """\n    \2\n    """'),
            
            # Fix method docstring patterns  
            (r'def\s+(\w+).*?:\s*\\1\\n\s*"""\s*\\n\s*\\1([^\\]+)\\1\\n\s*"""',
             r'def \1:\n        """\n        \2\n        """'),
        ]
        
        # Apply fixes
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        
        # Additional specific fixes for common corrupted patterns
        replacements = [
            ('\\1\\n    """\\n    \\1ypes of performance metric\\1\\n    """', 
             '"""\n    Types of performance metrics\n    """'),
            
            ('\\1\\n    """\\n    \\1lert severity level\\1\\n    """',
             '"""\n    Alert severity levels\n    """'),
             
            ('\\1\\n    """\\n    \\1erformance metric data structur\\1\\n    """',
             '"""\n    Performance metric data structure\n    """'),
             
            ('\\1\\n    """\\n    \\1ystem resource metric\\1\\n    """',
             '"""\n    System resource metrics\n    """'),
             
            ('\\1\\n    """\\n    \\1PI endpoint performance metric\\1\\n    """',
             '"""\n    API endpoint performance metrics\n    """'),
             
            ('\\1\\n    """\\n    \\1erformance alert definitio\\1\\n    """',
             '"""\n    Performance alert definition\n    """'),
             
            ('\\1\\n        """\\n        \\1valuate if alert should trigge\\1\\n        """',
             '"""\n        Evaluate if alert should trigger\n        """'),
             
            ('\\1\\n        """\\n        \\1ormat alert messag\\1\\n        """',
             '"""\n        Format alert message\n        """'),
             
            ('\\1\\n    """\\n    \\1ollects and aggregates performance metric\\1\\n    """',
             '"""\n    Collects and aggregates performance metrics\n    """'),
             
            ('\\1\\n        """\\n        \\1ecord a performance metri\\1\\n        """',
             '"""\n        Record a performance metric\n        """'),
             
            ('\\1\\n        """\\n        \\1ecord API performance metric\\1\\n        """',
             '"""\n        Record API performance metrics\n        """'),
             
            ('\\1\\n        """\\n        \\1ollect system resource metric\\1\\n        """',
             '"""\n        Collect system resource metrics\n        """'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        # Generic cleanup for remaining \1 patterns
        content = re.sub(r'\\1([^\\]*?)\\1', r'\1', content)
        content = re.sub(r'\\n\s*"""', r'\n    """', content)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def fix_all_docstrings(root_dir: Path) -> Dict[str, Any]:
    """Fix docstring encoding issues in all Python files"""
    
    results = {
        "files_processed": 0,
        "files_fixed": 0,
        "files_with_errors": 0,
        "fixed_files": []
    }
    
    # Find all Python files
    python_files = list(root_dir.rglob("*.py"))
    
    for py_file in python_files:
        results["files_processed"] += 1
        
        try:
            if fix_docstring_encoding(py_file):
                results["files_fixed"] += 1
                results["fixed_files"].append(str(py_file))
                print(f"✅ Fixed: {py_file}")
            else:
                print(f"✓ Clean: {py_file}")
                
        except Exception as e:
            results["files_with_errors"] += 1
            print(f"❌ Error in {py_file}: {e}")
    
    return results

def main():
    """Main function to fix docstring encoding issues"""
    print("🔧 WakeDock v0.6.3 - Docstring Encoding Fix")
    print("=" * 50)
    
    # Get the wakedock directory
    current_dir = Path(__file__).parent
    wakedock_dir = current_dir / "wakedock"
    
    if not wakedock_dir.exists():
        print(f"❌ Wakedock directory not found: {wakedock_dir}")
        return
    
    print(f"📂 Processing directory: {wakedock_dir}")
    
    # Fix all docstrings
    results = fix_all_docstrings(wakedock_dir)
    
    print("\n" + "=" * 50)
    print("📊 DOCSTRING FIX RESULTS:")
    print(f"   Files processed: {results['files_processed']}")
    print(f"   Files fixed: {results['files_fixed']}")
    print(f"   Files with errors: {results['files_with_errors']}")
    
    if results['fixed_files']:
        print(f"\n🔧 Fixed files:")
        for file_path in results['fixed_files'][:10]:  # Show first 10
            print(f"   • {file_path}")
        
        if len(results['fixed_files']) > 10:
            print(f"   ... and {len(results['fixed_files']) - 10} more files")
    
    if results['files_fixed'] > 0:
        print(f"\n✅ Successfully fixed {results['files_fixed']} files!")
    else:
        print(f"\n✅ No files needed fixing!")
    
    print("\n🎯 Docstring encoding issues resolved!")

if __name__ == "__main__":
    main()
