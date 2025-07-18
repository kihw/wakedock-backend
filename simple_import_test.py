#!/usr/bin/env python3
"""
Simple test to identify the exact import issue
"""

import sys
import os
sys.path.insert(0, '/Docker/code/wakedock-env/wakedock-backend')

def test_imports():
    """Test imports step by step"""
    
    print("🔍 DIAGNOSTIC DES IMPORTS")
    print("=" * 40)
    
    try:
        print("1. Test import basic...")
        from wakedock.routes import analytics_routes
        print("✅ Import analytics_routes réussi")
    except Exception as e:
        print(f"❌ Erreur import analytics_routes: {str(e)}")
        return
    
    try:
        print("2. Test import router...")
        from wakedock.routes.analytics_routes import analytics_router
        print("✅ Import analytics_router réussi")
    except Exception as e:
        print(f"❌ Erreur import analytics_router: {str(e)}")
        return
    
    try:
        print("3. Test routes count...")
        route_count = len(analytics_router.routes)
        print(f"✅ Router has {route_count} routes")
    except Exception as e:
        print(f"❌ Erreur accessing routes: {str(e)}")
        return
    
    print("\n✅ Tous les imports réussis!")

if __name__ == "__main__":
    test_imports()
