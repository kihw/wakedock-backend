#!/usr/bin/env python3
"""
Clean up analytics models file - fix escaped quotes and other issues
"""

import os
import re

def fix_analytics_models():
    """Fix all issues in analytics_models.py"""
    
    file_path = "/Docker/code/wakedock-env/wakedock-backend/wakedock/models/analytics_models.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix escaped quotes
    content = content.replace(r"\'", "'")
    
    # Fix duplicate __table_args__ declarations
    # Remove lines that have duplicate __table_args__ = {'extend_existing': True}
    lines = content.split('\n')
    cleaned_lines = []
    
    for i, line in enumerate(lines):
        # Skip duplicate __table_args__ lines that are standalone
        if line.strip() == "__table_args__ = {'extend_existing': True}" and i > 0:
            # Check if previous line already has __table_args__
            prev_line = lines[i-1].strip()
            if prev_line.startswith("__table_args__ = ("):
                continue
        
        cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed analytics_models.py")
    print("   - Removed escaped quotes")
    print("   - Cleaned up duplicate __table_args__ declarations")

if __name__ == "__main__":
    fix_analytics_models()
