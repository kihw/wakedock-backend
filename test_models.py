#!/usr/bin/env python3
"""
Simple test for notification model
"""
import sys
import os
sys.path.insert(0, '/Docker/code/wakedock-env/wakedock-backend')

print("Testing notification model import...")
try:
    from wakedock.models.notification import Notification
    print("✅ Notification model imported successfully")
except Exception as e:
    print(f"❌ Error importing notification model: {e}")
    import traceback
    traceback.print_exc()

print("Testing dashboard model import...")
try:
    from wakedock.models.dashboard import DashboardLayout
    print("✅ Dashboard model imported successfully")
except Exception as e:
    print(f"❌ Error importing dashboard model: {e}")
    import traceback
    traceback.print_exc()

print("All basic model tests completed!")
