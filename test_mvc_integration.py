#!/usr/bin/env python3
"""
Test d'intégration finale MVC WakeDock
"""

import sys
import asyncio
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🚀 DÉMARRAGE DES TESTS D'INTÉGRATION MVC WAKEDOCK")
print("=" * 60)

# Test 1: Imports des modèles
print("\n1️⃣ Test des imports des modèles...")
try:
    from wakedock.models.base import BaseModel, AuditableModel
    print("✅ Base models OK")
    
    from wakedock.models.alerts_models import Alert, AlertRule
    print("✅ Alerts models OK")
    
    from wakedock.models.containers_models import Container, ContainerStack
    print("✅ Containers models OK")
    
    from wakedock.models.authentication_models import User, Role
    print("✅ Authentication models OK")
    
    from wakedock.models.dashboard_models import Dashboard, Widget
    print("✅ Dashboard models OK")
    
    from wakedock.models.analytics_models import Metric, MetricData
    print("✅ Analytics models OK")
    
    models_success = True
except Exception as e:
    print(f"❌ Erreur imports modèles: {e}")
    models_success = False

# Test 2: Imports de la base de données
print("\n2️⃣ Test des imports de la base de données...")
try:
    from wakedock.core.database import Base, get_db, AsyncSessionLocal
    print("✅ Database core OK")
    db_success = True
except Exception as e:
    print(f"❌ Erreur database: {e}")
    db_success = False

# Test 3: Imports des serializers
print("\n3️⃣ Test des imports des serializers...")
try:
    from wakedock.serializers.alerts_serializers import CreateAlertRequest
    print("✅ Alerts serializers OK")
    
    from wakedock.serializers.containers_serializers import CreateContainerRequest
    print("✅ Containers serializers OK")
    
    from wakedock.serializers.authentication_serializers import RegisterRequest
    print("✅ Authentication serializers OK")
    
    from wakedock.serializers.dashboard_serializers import CreateDashboardRequest
    print("✅ Dashboard serializers OK")
    
    from wakedock.serializers.analytics_serializers import CreateMetricRequest
    print("✅ Analytics serializers OK")
    
    serializers_success = True
except Exception as e:
    print(f"❌ Erreur serializers: {e}")
    serializers_success = False

# Test 4: Imports des repositories
print("\n4️⃣ Test des imports des repositories...")
try:
    from wakedock.repositories.alerts_repository import AlertsRepository
    print("✅ Alerts repository OK")
    
    from wakedock.repositories.containers_repository import ContainersRepository
    print("✅ Containers repository OK")
    
    from wakedock.repositories.authentication_repository import AuthenticationRepository
    print("✅ Authentication repository OK")
    
    from wakedock.repositories.dashboard_repository import DashboardRepository
    print("✅ Dashboard repository OK")
    
    from wakedock.repositories.analytics_repository import AnalyticsRepository
    print("✅ Analytics repository OK")
    
    repositories_success = True
except Exception as e:
    print(f"❌ Erreur repositories: {e}")
    repositories_success = False

# Test 5: Imports des services
print("\n5️⃣ Test des imports des services...")
try:
    from wakedock.services.alerts_service import AlertsService
    print("✅ Alerts service OK")
    
    from wakedock.services.containers_service import ContainersService
    print("✅ Containers service OK")
    
    from wakedock.services.authentication_service import AuthenticationService
    print("✅ Authentication service OK")
    
    from wakedock.services.dashboard_service import DashboardService
    print("✅ Dashboard service OK")
    
    from wakedock.services.analytics_service import AnalyticsService
    print("✅ Analytics service OK")
    
    services_success = True
except Exception as e:
    print(f"❌ Erreur services: {e}")
    services_success = False

# Test 6: Imports des controllers
print("\n6️⃣ Test des imports des controllers...")
try:
    from wakedock.controllers.alerts_controller import AlertsController
    print("✅ Alerts controller OK")
    
    from wakedock.controllers.containers_controller import ContainersController
    print("✅ Containers controller OK")
    
    from wakedock.controllers.authentication_controller import AuthenticationController
    print("✅ Authentication controller OK")
    
    from wakedock.controllers.dashboard_controller import DashboardController
    print("✅ Dashboard controller OK")
    
    from wakedock.controllers.analytics_controller import AnalyticsController
    print("✅ Analytics controller OK")
    
    controllers_success = True
except Exception as e:
    print(f"❌ Erreur controllers: {e}")
    controllers_success = False

# Test 7: Imports des routes
print("\n7️⃣ Test des imports des routes...")
try:
    from wakedock.routes.alerts_routes import router as alerts_router
    print("✅ Alerts routes OK")
    
    from wakedock.routes.containers_routes import router as containers_router
    print("✅ Containers routes OK")
    
    from wakedock.routes.authentication_routes import router as auth_router
    print("✅ Authentication routes OK")
    
    from wakedock.routes.dashboard_routes import router as dashboard_router
    print("✅ Dashboard routes OK")
    
    from wakedock.routes.analytics_routes import router as analytics_router
    print("✅ Analytics routes OK")
    
    routes_success = True
except Exception as e:
    print(f"❌ Erreur routes: {e}")
    routes_success = False

# Résumé final
print("\n" + "=" * 60)
print("📊 RÉSUMÉ DES TESTS D'INTÉGRATION MVC")
print("=" * 60)

tests = [
    ("Modèles", models_success),
    ("Base de données", db_success),
    ("Serializers", serializers_success),
    ("Repositories", repositories_success),
    ("Services", services_success),
    ("Controllers", controllers_success),
    ("Routes", routes_success)
]

successful_tests = 0
total_tests = len(tests)

for test_name, success in tests:
    status = "✅ RÉUSSI" if success else "❌ ÉCHOUÉ"
    print(f"{test_name:<20} {status}")
    if success:
        successful_tests += 1

print("\n" + "=" * 60)
print(f"🎯 RÉSULTAT FINAL: {successful_tests}/{total_tests} tests réussis")
print(f"📈 Taux de réussite: {(successful_tests/total_tests)*100:.1f}%")

if successful_tests == total_tests:
    print("🎉 TOUS LES TESTS SONT RÉUSSIS!")
    print("✅ Architecture MVC prête pour l'intégration avec FastAPI")
else:
    print(f"⚠️  {total_tests - successful_tests} test(s) ont échoué")
    print("❌ Corrections nécessaires avant déploiement")

print("=" * 60)
