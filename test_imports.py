#!/usr/bin/env python3
"""
Test d'imports et de cohérence des modules MVC
"""

import sys
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Test d'imports des modules MVC...")

# Test des imports de base
try:
    from wakedock.core.database import Base, AsyncSessionLocal, engine
    print("✅ Core database imports OK")
except Exception as e:
    print(f"❌ Core database imports failed: {e}")

# Test des imports des modèles
models_status = {}

try:
    from wakedock.models.dashboard_models import Dashboard, Widget
    models_status['dashboard'] = "✅ OK"
except Exception as e:
    models_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.models.analytics_models import Metric, MetricData
    models_status['analytics'] = "✅ OK"
except Exception as e:
    models_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.models.alerts_models import Alert, AlertRule
    models_status['alerts'] = "✅ OK"
except Exception as e:
    models_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.models.containers_models import Container, ContainerStack
    models_status['containers'] = "✅ OK"
except Exception as e:
    models_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.models.authentication_models import User, Role
    models_status['authentication'] = "✅ OK"
except Exception as e:
    models_status['authentication'] = f"❌ Error: {e}"

# Test des imports des repositories
repositories_status = {}

try:
    from wakedock.repositories.dashboard_repository import DashboardRepository
    repositories_status['dashboard'] = "✅ OK"
except Exception as e:
    repositories_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.repositories.analytics_repository import AnalyticsRepository
    repositories_status['analytics'] = "✅ OK"
except Exception as e:
    repositories_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.repositories.alerts_repository import AlertsRepository
    repositories_status['alerts'] = "✅ OK"
except Exception as e:
    repositories_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.repositories.containers_repository import ContainersRepository
    repositories_status['containers'] = "✅ OK"
except Exception as e:
    repositories_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.repositories.authentication_repository import AuthenticationRepository
    repositories_status['authentication'] = "✅ OK"
except Exception as e:
    repositories_status['authentication'] = f"❌ Error: {e}"

# Test des imports des controllers
controllers_status = {}

try:
    from wakedock.controllers.dashboard_controller import DashboardController
    controllers_status['dashboard'] = "✅ OK"
except Exception as e:
    controllers_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.controllers.analytics_controller import AnalyticsController
    controllers_status['analytics'] = "✅ OK"
except Exception as e:
    controllers_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.controllers.alerts_controller import AlertsController
    controllers_status['alerts'] = "✅ OK"
except Exception as e:
    controllers_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.controllers.containers_controller import ContainersController
    controllers_status['containers'] = "✅ OK"
except Exception as e:
    controllers_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.controllers.authentication_controller import AuthenticationController
    controllers_status['authentication'] = "✅ OK"
except Exception as e:
    controllers_status['authentication'] = f"❌ Error: {e}"

# Test des imports des services
services_status = {}

try:
    from wakedock.services.dashboard_service import DashboardService
    services_status['dashboard'] = "✅ OK"
except Exception as e:
    services_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.services.analytics_service import AnalyticsService
    services_status['analytics'] = "✅ OK"
except Exception as e:
    services_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.services.alerts_service import AlertsService
    services_status['alerts'] = "✅ OK"
except Exception as e:
    services_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.services.containers_service import ContainersService
    services_status['containers'] = "✅ OK"
except Exception as e:
    services_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.services.authentication_service import AuthenticationService
    services_status['authentication'] = "✅ OK"
except Exception as e:
    services_status['authentication'] = f"❌ Error: {e}"

# Test des imports des validators
validators_status = {}

try:
    from wakedock.validators.dashboard_validator import DashboardValidator
    validators_status['dashboard'] = "✅ OK"
except Exception as e:
    validators_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.validators.analytics_validator import AnalyticsValidator
    validators_status['analytics'] = "✅ OK"
except Exception as e:
    validators_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.validators.alerts_validator import AlertsValidator
    validators_status['alerts'] = "✅ OK"
except Exception as e:
    validators_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.validators.containers_validator import ContainersValidator
    validators_status['containers'] = "✅ OK"
except Exception as e:
    validators_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.validators.authentication_validator import AuthenticationValidator
    validators_status['authentication'] = "✅ OK"
except Exception as e:
    validators_status['authentication'] = f"❌ Error: {e}"

# Test des imports des views
views_status = {}

try:
    from wakedock.views.dashboard_view import DashboardView
    views_status['dashboard'] = "✅ OK"
except Exception as e:
    views_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.views.analytics_view import AnalyticsView
    views_status['analytics'] = "✅ OK"
except Exception as e:
    views_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.views.alerts_view import AlertsView
    views_status['alerts'] = "✅ OK"
except Exception as e:
    views_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.views.containers_view import ContainersView
    views_status['containers'] = "✅ OK"
except Exception as e:
    views_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.views.authentication_view import AuthenticationView
    views_status['authentication'] = "✅ OK"
except Exception as e:
    views_status['authentication'] = f"❌ Error: {e}"

# Test des imports des serializers
serializers_status = {}

try:
    from wakedock.serializers.dashboard_serializers import CreateDashboardRequest
    serializers_status['dashboard'] = "✅ OK"
except Exception as e:
    serializers_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.serializers.analytics_serializers import CreateMetricRequest
    serializers_status['analytics'] = "✅ OK"
except Exception as e:
    serializers_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.serializers.alerts_serializers import CreateAlertRequest
    serializers_status['alerts'] = "✅ OK"
except Exception as e:
    serializers_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.serializers.containers_serializers import CreateContainerRequest
    serializers_status['containers'] = "✅ OK"
except Exception as e:
    serializers_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.serializers.authentication_serializers import RegisterRequest
    serializers_status['authentication'] = "✅ OK"
except Exception as e:
    serializers_status['authentication'] = f"❌ Error: {e}"

# Test des imports des routes
routes_status = {}

try:
    from wakedock.routes.dashboard_routes import router
    routes_status['dashboard'] = "✅ OK"
except Exception as e:
    routes_status['dashboard'] = f"❌ Error: {e}"

try:
    from wakedock.routes.analytics_routes import router
    routes_status['analytics'] = "✅ OK"
except Exception as e:
    routes_status['analytics'] = f"❌ Error: {e}"

try:
    from wakedock.routes.alerts_routes import router
    routes_status['alerts'] = "✅ OK"
except Exception as e:
    routes_status['alerts'] = f"❌ Error: {e}"

try:
    from wakedock.routes.containers_routes import router
    routes_status['containers'] = "✅ OK"
except Exception as e:
    routes_status['containers'] = f"❌ Error: {e}"

try:
    from wakedock.routes.authentication_routes import router
    routes_status['authentication'] = "✅ OK"
except Exception as e:
    routes_status['authentication'] = f"❌ Error: {e}"

# Affichage des résultats
print("\n" + "="*60)
print("📊 RÉSULTATS DES TESTS D'IMPORTS MVC")
print("="*60)

domains = ['dashboard', 'analytics', 'alerts', 'containers', 'authentication']
components = ['models', 'repositories', 'controllers', 'services', 'validators', 'views', 'serializers', 'routes']

status_maps = {
    'models': models_status,
    'repositories': repositories_status,
    'controllers': controllers_status,
    'services': services_status,
    'validators': validators_status,
    'views': views_status,
    'serializers': serializers_status,
    'routes': routes_status
}

# Créer un tableau de résultats
print(f"{'Component':<15} {'Dashboard':<12} {'Analytics':<12} {'Alerts':<12} {'Containers':<12} {'Auth':<12}")
print("-" * 75)

for component in components:
    status_map = status_maps[component]
    row = f"{component:<15}"
    
    for domain in domains:
        status = status_map.get(domain, "❌ Missing")
        # Raccourcir le statut pour l'affichage
        if "✅ OK" in status:
            display_status = "✅ OK"
        elif "❌ Error" in status:
            display_status = "❌ ERR"
        else:
            display_status = "❌ ???"
        
        row += f" {display_status:<12}"
    
    print(row)

# Statistiques globales
total_tests = len(domains) * len(components)
passed_tests = 0
failed_tests = 0

for component in components:
    status_map = status_maps[component]
    for domain in domains:
        status = status_map.get(domain, "❌ Missing")
        if "✅ OK" in status:
            passed_tests += 1
        else:
            failed_tests += 1

print("\n" + "="*60)
print(f"📈 STATISTIQUES GLOBALES")
print("="*60)
print(f"Total tests: {total_tests}")
print(f"✅ Réussis: {passed_tests}")
print(f"❌ Échoués: {failed_tests}")
print(f"📊 Taux de réussite: {(passed_tests/total_tests)*100:.1f}%")

# Afficher les erreurs détaillées
print("\n🔍 ERREURS DÉTAILLÉES:")
print("-" * 60)

for component in components:
    status_map = status_maps[component]
    for domain in domains:
        status = status_map.get(domain, "❌ Missing")
        if "❌ Error" in status:
            print(f"{component}.{domain}: {status}")

if failed_tests == 0:
    print("\n🎉 TOUS LES IMPORTS SONT RÉUSSIS!")
    print("✅ Système MVC prêt pour l'intégration")
else:
    print(f"\n⚠️  {failed_tests} import(s) ont échoué")
    print("❌ Corrections nécessaires")

print("="*60)
