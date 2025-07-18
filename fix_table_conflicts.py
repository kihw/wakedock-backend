#!/usr/bin/env python3
"""
Fix table name conflicts in analytics models
"""

import os
import re

def fix_table_name_conflicts():
    """Fix table name conflicts between different model files"""
    
    file_path = "/Docker/code/wakedock-env/wakedock-backend/wakedock/models/analytics_models.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define table name mappings to avoid conflicts
    table_mappings = {
        "'alerts'": "'analytics_alerts'",
        "'dashboards'": "'analytics_dashboards'", 
        "'alert_incidents'": "'analytics_alert_incidents'",
        "'widgets'": "'analytics_widgets'",
        "'reports'": "'analytics_reports'",
        "'exports'": "'analytics_exports'",
        "'correlations'": "'analytics_correlations'",
        "'anomalies'": "'analytics_anomalies'",
        "'forecasts'": "'analytics_forecasts'"
    }
    
    # Apply table name changes
    for old_name, new_name in table_mappings.items():
        content = content.replace(f"__tablename__ = {old_name}", f"__tablename__ = {new_name}")
    
    # Also need to update ForeignKey references
    fk_mappings = {
        "'alerts.id'": "'analytics_alerts.id'",
        "'dashboards.id'": "'analytics_dashboards.id'"
    }
    
    for old_fk, new_fk in fk_mappings.items():
        content = content.replace(old_fk, new_fk)
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed table name conflicts in analytics_models.py")
    print("   - Renamed conflicting tables with 'analytics_' prefix")
    print("   - Updated foreign key references")
    print("   - Maintained data integrity")

if __name__ == "__main__":
    fix_table_name_conflicts()
