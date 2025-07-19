"""
Dépendances FastAPI pour l'application WakeDock
"""
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

# Security scheme for JWT authentication
oauth2_scheme = HTTPBearer()

from wakedock.core.alerts_service import AlertsService
from wakedock.core.auth_service import AuthService, get_auth_service
# Temporarily disabled - causes import chain issues
# from wakedock.core.auto_deployment_service import AutoDeploymentService
from wakedock.core.cicd_service import CICDService, get_cicd_service
from wakedock.core.docker_manager import DockerManager
from wakedock.core.docker_client import docker_client
from wakedock.core.environment_service import EnvironmentService
from wakedock.core.log_optimization_service import LogOptimizationService
from wakedock.core.metrics_collector import MetricsCollector
from wakedock.core.rbac_service import get_rbac_service, RBACService
from wakedock.core.security_audit_service import (
    get_security_audit_service,
    SecurityAuditService,
)
from wakedock.core.swarm_service import SwarmService
from wakedock.core.user_profile_service import (
    get_user_profile_service,
    UserProfileService,
)
from wakedock.database.database import get_db_session

# Instances globales
_docker_manager: DockerManager = None
_metrics_collector: MetricsCollector = None
_alerts_service: AlertsService = None
_log_optimization_service: LogOptimizationService = None
_auth_service: AuthService = None
_user_profile_service: UserProfileService = None
_rbac_service: RBACService = None
_security_audit_service: SecurityAuditService = None
_cicd_service: CICDService = None
# _auto_deployment_service: AutoDeploymentService = None
_auto_deployment_service = None
_swarm_service: SwarmService = None
_environment_service: EnvironmentService = None

def get_docker_manager() -> DockerManager:
    """
    Dépendance FastAPI pour obtenir le manager Docker
    """
    global _docker_manager
    
    if _docker_manager is None:
        _docker_manager = DockerManager()
    
    return _docker_manager


def get_docker_client():
    """Get Docker client instance"""
    return docker_client


def get_metrics_collector() -> MetricsCollector:
    """
    Dépendance FastAPI pour obtenir le collecteur de métriques
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        docker_manager = get_docker_manager()
        _metrics_collector = MetricsCollector(docker_manager)
    
    return _metrics_collector

def get_alerts_service() -> AlertsService:
    """
    Dépendance FastAPI pour obtenir le service d'alertes
    """
    global _alerts_service
    
    if _alerts_service is None:
        metrics_collector = get_metrics_collector()
        _alerts_service = AlertsService(
            metrics_collector=metrics_collector,
            storage_path="/var/log/wakedock/alerts"
        )
    
    return _alerts_service

def get_log_optimization_service() -> LogOptimizationService:
    """
    Dépendance FastAPI pour obtenir le service d'optimisation des logs
    """
    global _log_optimization_service
    
    if _log_optimization_service is None:
        _log_optimization_service = LogOptimizationService(
            storage_path="/var/log/wakedock/logs_optimization"
        )
    
    return _log_optimization_service

def get_auth_service_dependency() -> AuthService:
    """
    Dépendance FastAPI pour obtenir le service d'authentification
    """
    global _auth_service
    
    if _auth_service is None:
        _auth_service = get_auth_service()
    
    return _auth_service

def get_user_profile_service_dependency() -> UserProfileService:
    """
    Dépendance FastAPI pour obtenir le service de profils utilisateur
    """
    global _user_profile_service
    
    if _user_profile_service is None:
        _user_profile_service = get_user_profile_service()
    
    return _user_profile_service

def get_rbac_service_dependency() -> RBACService:
    """
    Dépendance FastAPI pour obtenir le service RBAC
    """
    global _rbac_service
    
    if _rbac_service is None:
        _rbac_service = get_rbac_service()
    
    return _rbac_service

def get_security_audit_service_dependency() -> SecurityAuditService:
    """
    Dépendance FastAPI pour obtenir le service d'audit de sécurité
    """
    global _security_audit_service
    
    if _security_audit_service is None:
        _security_audit_service = get_security_audit_service()
    
    return _security_audit_service

def get_cicd_service_dependency() -> CICDService:
    """
    Dépendance FastAPI pour obtenir le service CI/CD
    """
    global _cicd_service
    
    if _cicd_service is None:
        _cicd_service = get_cicd_service()
    
    return _cicd_service

def get_auto_deployment_service(
    db: Session = Depends(get_db_session),
    security_service: SecurityAuditService = Depends(get_security_audit_service_dependency),
    rbac_service: RBACService = Depends(get_rbac_service_dependency)
):  # -> AutoDeploymentService:
    """
    Factory function pour créer le service de déploiement automatique
    Utilisé comme dependency FastAPI avec injection des dépendances
    """
    # Temporarily return None - AutoDeploymentService disabled
    return None
    # return AutoDeploymentService(
    #     db_session=db,
    #     security_service=security_service,
    #     rbac_service=rbac_service
    # )

def get_swarm_service(
    db: Session = Depends(get_db_session),
    security_service: SecurityAuditService = Depends(get_security_audit_service_dependency),
    rbac_service: RBACService = Depends(get_rbac_service_dependency)
) -> SwarmService:
    """
    Factory function pour créer le service Swarm
    Utilisé comme dependency FastAPI avec injection des dépendances
    """
    return SwarmService(
        db_session=db,
        security_service=security_service,
        rbac_service=rbac_service
    )

def get_environment_service(
    db: Session = Depends(get_db_session),
) -> EnvironmentService:
    """Get environment service with database session"""
    return EnvironmentService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> dict:
    """Get current user from JWT token"""
    # For now, return a mock user
    # In production, this would validate the JWT token and return the user
    return {
        "id": 1,
        "username": "admin",
        "email": "admin@wakedock.com",
        "roles": ["admin"]
    }


# Services lifecycle management

async def startup_services():
    """
    Démarre tous les services au startup de l'application
    """
    # Démarre le collecteur de métriques
    metrics_collector = get_metrics_collector()
    await metrics_collector.start()
    
    # Démarre le service d'alertes
    alerts_service = get_alerts_service()
    await alerts_service.start()
    
    # Démarre le service d'optimisation des logs
    log_optimization_service = get_log_optimization_service()
    await log_optimization_service.start()
    
    # Initialise le service d'authentification
    auth_service = get_auth_service_dependency()
    # Le service d'auth n'a pas besoin de start() car il est stateless
    
    # Nettoie les sessions expirées au démarrage
    auth_service.cleanup_expired_sessions()
    
    # Initialise le service de profils utilisateur
    get_user_profile_service_dependency()
    # Le service de profils n'a pas besoin de start() car il est stateless
    
    # Initialise le service RBAC
    rbac_service = get_rbac_service_dependency()
    # Initialiser les rôles et permissions par défaut
    await rbac_service.initialize_default_roles_and_permissions()
    
    # Nettoyer les assignations de rôles expirées
    await rbac_service.cleanup_expired_role_assignments()
    
    # Initialise le service d'audit de sécurité
    security_audit_service = get_security_audit_service_dependency()
    await security_audit_service.start()
    
    # Initialise le service CI/CD
    cicd_service = get_cicd_service_dependency()
    await cicd_service.start()
    
    # Initialise le service d'environnements
    environment_service = _environment_service
    if environment_service:
        await environment_service.start_monitoring()

async def shutdown_services():
    """
    Arrête tous les services au shutdown de l'application
    """
    global _alerts_service, _metrics_collector, _docker_client, _log_optimization_service, _auth_service, _user_profile_service, _rbac_service, _security_audit_service, _cicd_service, _environment_service
    
    # Arrêt du service CI/CD
    if _cicd_service:
        await _cicd_service.stop()
        _cicd_service = None
    
    # Arrêt du service d'environnements
    if _environment_service:
        await _environment_service.stop_monitoring()
        _environment_service = None
    
    # Arrêt du service d'audit de sécurité
    if _security_audit_service:
        await _security_audit_service.stop()
        _security_audit_service = None
    
    # Nettoyage du service RBAC
    if _rbac_service:
        # Nettoyer les assignations expirées une dernière fois
        await _rbac_service.cleanup_expired_role_assignments()
        _rbac_service = None
    
    # Nettoie le service de profils utilisateur
    if _user_profile_service:
        _user_profile_service = None
    
    # Nettoie les sessions d'authentification
    if _auth_service:
        _auth_service.cleanup_expired_sessions()
        _auth_service = None
    
    # Arrête le service d'optimisation des logs
    if _log_optimization_service:
        await _log_optimization_service.stop()
        _log_optimization_service = None
    
    # Arrête le service d'alertes
    if _alerts_service:
        await _alerts_service.stop()
        _alerts_service = None
    
    # Arrête le collecteur de métriques
    if _metrics_collector:
        await _metrics_collector.stop()
        _metrics_collector = None
    
    # Ferme le manager Docker
    if _docker_manager:
        _docker_manager.close()
