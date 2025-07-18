#!/usr/bin/env python3
"""
Verbose import test to identify any remaining issues
"""
import sys
import traceback

try:
    print("Testing analytics routes import...")
    from wakedock.routes.analytics_routes import analytics_router
    print("✅ Analytics routes imported successfully!")
    print(f"Router type: {type(analytics_router)}")
    print(f"Router prefix: {getattr(analytics_router, 'prefix', 'No prefix')}")
    print(f"Number of routes: {len(analytics_router.routes)}")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    print(f"Error type: {type(e)}")
    traceback.print_exc()
    sys.exit(1)
