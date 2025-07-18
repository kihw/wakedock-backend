#!/usr/bin/env python3
"""
Test d'imports simplifié pour les modules MVC critiques
"""

import sys
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Test d'imports des modules MVC critiques...")

# Test des imports de base
try:
    from wakedock.models.base import Base, BaseModel
    print("✅ Base models imports OK")
except Exception as e:
    print(f"❌ Base models imports failed: {e}")
    traceback.print_exc()

# Test des imports des modèles critiques
try:
    from wakedock.models.alerts_models import Alert, AlertRule
    print("✅ Alert models imports OK")
except Exception as e:
    print(f"❌ Alert models imports failed: {e}")
    traceback.print_exc()

try:
    from wakedock.models.containers_models import Container, ContainerStack
    print("✅ Container models imports OK")
except Exception as e:
    print(f"❌ Container models imports failed: {e}")
    traceback.print_exc()

try:
    from wakedock.models.authentication_models import User, Role
    print("✅ Authentication models imports OK")
except Exception as e:
    print(f"❌ Authentication models imports failed: {e}")
    traceback.print_exc()

# Test core database
try:
    from wakedock.core.database import Base, AsyncSessionLocal, engine, get_db
    print("✅ Core database imports OK")
except Exception as e:
    print(f"❌ Core database imports failed: {e}")
    traceback.print_exc()

print("\n🎯 Tests d'imports critiques terminés")
