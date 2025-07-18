"""
Script d'intégration des routes MVC avec l'application principale
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from wakedock.api.app import create_app
from wakedock.core.orchestrator import DockerOrchestrator  
from wakedock.core.monitoring import MonitoringService
from wakedock.core.advanced_analytics import AdvancedAnalyticsService
from wakedock.core.alerts_service import AlertsService

# Import nouvelles routes MVC
from wakedock.routes.dashboard_routes import router as dashboard_router
from wakedock.routes.analytics_routes import router as analytics_router
from wakedock.routes.alerts_routes import router as alerts_router
from wakedock.routes.containers_routes import router as containers_router
from wakedock.routes.authentication_routes import router as auth_router

def integrate_mvc_routes(app):
    """Intégrer les routes MVC dans l'application"""
    
    # Ajout des routes MVC
    app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboards"])
    app.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])
    app.include_router(alerts_router, prefix="/api/v1", tags=["alerts"])
    app.include_router(containers_router, prefix="/api/v1", tags=["containers"])
    app.include_router(auth_router, prefix="/api/v1", tags=["authentication"])
    
    print("✅ Routes MVC intégrées avec succès")
    
    return app


def create_integrated_app():
    """Créer l'application avec l'intégration MVC"""
    try:
        # Créer les services de base
        orchestrator = DockerOrchestrator()
        monitoring_service = MonitoringService()
        analytics_service = AdvancedAnalyticsService()
        alerts_service = AlertsService()
        
        # Créer l'application de base
        app = create_app(orchestrator, monitoring_service, analytics_service, alerts_service)
        
        # Intégrer les routes MVC
        app = integrate_mvc_routes(app)
        
        print("🎉 Application intégrée créée avec succès!")
        return app
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'application intégrée: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    app = create_integrated_app()
    
    if app:
        # Afficher les routes disponibles
        print("\n📋 Routes disponibles:")
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"  {route.methods} {route.path}")
        
        print("\n🚀 Application prête pour les tests!")
    else:
        print("💥 Échec de la création de l'application")
        sys.exit(1)
