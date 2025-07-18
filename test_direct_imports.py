#!/usr/bin/env python3
"""
Test d'imports directs des modules MVC
"""

import sys
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Test d'imports directs des modules MVC...")

# Test alqerts_models direct
try:
    from wakedock.models.alerts_models import Alert, AlertRule
    print("✅ Direct Alert models imports OK")
except Exception as e:
    print(f"❌ Direct Alert models imports failed: {e}")
    traceback.print_exc()

# Test containers_models direct
try:
    from wakedock.models.containers_models import Container, ContainerStack
    print("✅ Direct Container models imports OK")
except Exception as e:
    print(f"❌ Direct Container models imports failed: {e}")
    traceback.print_exc()

# Test authentication_models direct
try:
    from wakedock.models.authentication_models import User, Role
    print("✅ Direct Authentication models imports OK")
except Exception as e:
    print(f"❌ Direct Authentication models imports failed: {e}")
    traceback.print_exc()

# Test analytics_models direct
try:
    from wakedock.models.analytics_models import Metric, MetricData
    print("✅ Direct Analytics models imports OK")
except Exception as e:
    print(f"❌ Direct Analytics models imports failed: {e}")
    traceback.print_exc()

# Test dashboard_models direct
try:
    from wakedock.models.dashboard_models import Dashboard, Widget
    print("✅ Direct Dashboard models imports OK")
except Exception as e:
    print(f"❌ Direct Dashboard models imports failed: {e}")
    traceback.print_exc()

print("\n🎯 Tests d'imports directs terminés")
