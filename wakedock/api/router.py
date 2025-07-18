"""
Routeur principal pour l'API WakeDock
"""
from fastapi import APIRouter

from wakedock.api.routes import (
    alerts,
    analytics,
    auth,
    auto_deployment,
    centralized_logs,
    cicd,
    compose_stacks,
    containers,
    health,
    images,
    logs,
    logs_optimization,
    monitoring,
    rbac,
    security_audit,
    services,
    stacks,
    swarm,
    system,
    user_profile,
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
api_router.include_router(user_profile.router, tags=["user-profile"])
api_router.include_router(rbac.router, tags=["rbac"])
api_router.include_router(security_audit.router, tags=["security-audit"])
api_router.include_router(cicd.router, tags=["ci-cd"])
api_router.include_router(auto_deployment.router, tags=["auto-deployment"])
api_router.include_router(swarm.router, tags=["swarm"])
api_router.include_router(stacks.router, tags=["stacks"])
api_router.include_router(compose_stacks.router, tags=["compose-stacks"])

__all__ = ["api_router"]
