"""
Routeur principal pour l'API WakeDock
"""
from fastapi import APIRouter
from wakedock.api.routes import (
    health, containers, services, images, logs, system,
    monitoring, centralized_logs, analytics, alerts, logs_optimization, auth
)

# Créer le routeur principal
api_router = APIRouter(prefix="/api/v1")

# Inclure tous les sous-routeurs
api_router.include_router(health.router, tags=["health"])
api_router.include_router(containers.router, tags=["containers"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(images.router, tags=["images"])
api_router.include_router(logs.router, tags=["logs"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(monitoring.router, tags=["monitoring"])
api_router.include_router(centralized_logs.router, tags=["centralized-logs"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(alerts.router, tags=["alerts"])
api_router.include_router(logs_optimization.router, tags=["logs-optimization"])
api_router.include_router(auth.router, tags=["authentication"])

__all__ = ["api_router"]
