#!/usr/bin/env python3
"""
WakeDock v0.6.3 - Syntax Error Fix
Fix remaining syntax issues after Black formatting
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

def fix_python_syntax(file_path: Path) -> bool:
    """Fix common Python syntax issues in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix common syntax issues
        fixes = [
            # Fix broken docstrings at class/function level
            (r'class\s+(\w+)[^:]*:\s*"""\s*([^"]*)\s*"""', r'class \1:\n    """\n    \2\n    """'),
            (r'def\s+(\w+)[^:]*:\s*"""\s*([^"]*)\s*"""', r'def \1:\n        """\n        \2\n        """'),
            
            # Fix indentation after enums/classes
            (r'class\s+(\w+)[^:]*:\s*"""[^"]*"""\s*(\w+\s*=)', r'class \1:\n    """\n    Description\n    """\n\n    \2'),
            
            # Fix broken enum docstrings
            (r'"""([^"]*ache[^"]*""")', r'"""\n    Cache strategies for different data types\n    """'),
            (r'"""([^"]*ypes of[^"]*""")', r'"""\n    Types of performance metrics\n    """'),
            
            # Fix method indentation
            (r'^\s{3}(\w+\s*=)', r'    \1'),  # Fix 3-space indentation to 4-space
            
            # Fix broken function definitions
            (r'def\s+(\w+)\([^)]*\):\s*"""[^"]*"""\s*^(\s*)(\w)', r'def \1():\n        """\n        Function description\n        """\n\2\3'),
        ]
        
        for pattern, replacement in fixes:
            import re
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # Try to parse and identify specific issues
        try:
            ast.parse(content)
        except SyntaxError as e:
            print(f"⚠️  Syntax error in {file_path}:{e.lineno}: {e.msg}")
            
            # Try to fix specific line issues
            lines = content.split('\n')
            if e.lineno <= len(lines):
                line = lines[e.lineno - 1]
                
                # Fix common issues
                if 'unexpected indent' in e.msg.lower():
                    # Fix indentation
                    stripped = line.lstrip()
                    if stripped:
                        # Determine correct indentation level
                        prev_line_idx = e.lineno - 2
                        while prev_line_idx >= 0 and not lines[prev_line_idx].strip():
                            prev_line_idx -= 1
                        
                        if prev_line_idx >= 0:
                            prev_line = lines[prev_line_idx]
                            if prev_line.strip().endswith(':'):
                                # Should be indented relative to previous line
                                prev_indent = len(prev_line) - len(prev_line.lstrip())
                                new_indent = ' ' * (prev_indent + 4)
                                lines[e.lineno - 1] = new_indent + stripped
                                content = '\n'.join(lines)
                
                elif 'invalid character' in e.msg.lower():
                    # Remove invalid characters
                    cleaned_line = ''.join(c for c in line if ord(c) < 128)
                    lines[e.lineno - 1] = cleaned_line
                    content = '\n'.join(lines)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def validate_python_syntax(file_path: Path) -> bool:
    """Validate Python syntax of a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        ast.parse(content)
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path}:{e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ Error parsing {file_path}: {e}")
        return False

def fix_all_syntax_errors(root_dir: Path) -> Dict[str, Any]:
    """Fix syntax errors in all Python files"""
    
    results = {
        "files_processed": 0,
        "files_fixed": 0,
        "files_with_errors": 0,
        "syntax_valid": 0,
        "fixed_files": [],
        "error_files": []
    }
    
    # Find all Python files
    python_files = list(root_dir.rglob("*.py"))
    
    for py_file in python_files:
        results["files_processed"] += 1
        
        # First, try to fix syntax issues
        try:
            if fix_python_syntax(py_file):
                results["files_fixed"] += 1
                results["fixed_files"].append(str(py_file))
                print(f"🔧 Fixed: {py_file}")
        except Exception as e:
            print(f"⚠️  Error fixing {py_file}: {e}")
        
        # Then validate syntax
        if validate_python_syntax(py_file):
            results["syntax_valid"] += 1
            if py_file not in results["fixed_files"]:
                print(f"✅ Valid: {py_file}")
        else:
            results["files_with_errors"] += 1
            results["error_files"].append(str(py_file))
    
    return results

def main():
    """Main function to fix syntax errors"""
    print("🔧 WakeDock v0.6.3 - Python Syntax Fix")
    print("=" * 50)
    
    # Get the wakedock directory
    current_dir = Path(__file__).parent
    wakedock_dir = current_dir / "wakedock"
    
    if not wakedock_dir.exists():
        print(f"❌ Wakedock directory not found: {wakedock_dir}")
        return
    
    print(f"📂 Processing directory: {wakedock_dir}")
    
    # Fix all syntax errors
    results = fix_all_syntax_errors(wakedock_dir)
    
    print("\n" + "=" * 50)
    print("📊 SYNTAX FIX RESULTS:")
    print(f"   Files processed: {results['files_processed']}")
    print(f"   Files fixed: {results['files_fixed']}")
    print(f"   Syntax valid: {results['syntax_valid']}")
    print(f"   Files with errors: {results['files_with_errors']}")
    
    if results['error_files']:
        print(f"\n❌ Files with syntax errors:")
        for file_path in results['error_files']:
            print(f"   • {file_path}")
    
    if results['files_with_errors'] == 0:
        print(f"\n✅ All files have valid Python syntax!")
    else:
        print(f"\n⚠️  {results['files_with_errors']} files still have syntax errors")
    
    print("\n🎯 Python syntax validation complete!")

if __name__ == "__main__":
    main()
