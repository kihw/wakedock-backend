#!/usr/bin/env python3
"""
Test d'imports purs des modules MVC individuels
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Test d'imports purs des modules MVC individuels...")

# Test direct du module analytics_models
try:
    # Test direct sans __init__.py
    import importlib.util
    spec = importlib.util.spec_from_file_location("analytics_models", "wakedock/models/analytics_models.py")
    analytics_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analytics_models)
    print("✅ Direct analytics_models module OK")
except Exception as e:
    print(f"❌ Direct analytics_models module failed: {e}")
    import traceback
    traceback.print_exc()

# Test direct du module alerts_models  
try:
    spec = importlib.util.spec_from_file_location("alerts_models", "wakedock/models/alerts_models.py")
    alerts_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alerts_models)
    print("✅ Direct alerts_models module OK")
except Exception as e:
    print(f"❌ Direct alerts_models module failed: {e}")

# Test direct du module containers_models
try:
    spec = importlib.util.spec_from_file_location("containers_models", "wakedock/models/containers_models.py")
    containers_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(containers_models)
    print("✅ Direct containers_models module OK")
except Exception as e:
    print(f"❌ Direct containers_models module failed: {e}")

# Test direct du module authentication_models
try:
    spec = importlib.util.spec_from_file_location("authentication_models", "wakedock/models/authentication_models.py")
    authentication_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(authentication_models)
    print("✅ Direct authentication_models module OK")
except Exception as e:
    print(f"❌ Direct authentication_models module failed: {e}")

# Test direct du module dashboard_models
try:
    spec = importlib.util.spec_from_file_location("dashboard_models", "wakedock/models/dashboard_models.py")
    dashboard_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard_models)
    print("✅ Direct dashboard_models module OK")
except Exception as e:
    print(f"❌ Direct dashboard_models module failed: {e}")

print("\n🎯 Tests d'imports purs terminés")
