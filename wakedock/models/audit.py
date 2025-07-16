"""
Énumérations et modèles pour l'audit et la sécurité
"""
from enum import Enum


class AuditAction(str, Enum):
    """
    Actions d'audit pour la traçabilité
    """
    # Authentification
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # Gestion des utilisateurs
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    
    # Gestion des rôles et permissions
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    
    # Conteneurs Docker
    CONTAINER_CREATED = "container_created"
    CONTAINER_STARTED = "container_started"
    CONTAINER_STOPPED = "container_stopped"
    CONTAINER_RESTARTED = "container_restarted"
    CONTAINER_DELETED = "container_deleted"
    CONTAINER_LOGS_ACCESSED = "container_logs_accessed"
    
    # Images Docker
    IMAGE_PULLED = "image_pulled"
    IMAGE_BUILT = "image_built"
    IMAGE_DELETED = "image_deleted"
    IMAGE_TAGGED = "image_tagged"
    
    # Réseaux Docker
    NETWORK_CREATED = "network_created"
    NETWORK_DELETED = "network_deleted"
    NETWORK_CONNECTED = "network_connected"
    NETWORK_DISCONNECTED = "network_disconnected"
    
    # Volumes Docker
    VOLUME_CREATED = "volume_created"
    VOLUME_DELETED = "volume_deleted"
    VOLUME_MOUNTED = "volume_mounted"
    VOLUME_UNMOUNTED = "volume_unmounted"
    
    # CI/CD
    PIPELINE_CREATED = "pipeline_created"
    PIPELINE_UPDATED = "pipeline_updated"
    PIPELINE_DELETED = "pipeline_deleted"
    PIPELINE_EXECUTED = "pipeline_executed"
    PIPELINE_FAILED = "pipeline_failed"
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYMENT_COMPLETED = "deployment_completed"
    DEPLOYMENT_FAILED = "deployment_failed"
    
    # Auto Deployment (version 0.4.2)
    AUTO_DEPLOYMENT_CREATED = "auto_deployment_created"
    AUTO_DEPLOYMENT_UPDATED = "auto_deployment_updated"
    AUTO_DEPLOYMENT_DELETED = "auto_deployment_deleted"
    AUTO_DEPLOYMENT_TRIGGERED = "auto_deployment_triggered"
    AUTO_DEPLOYMENT_COMPLETED = "auto_deployment_completed"
    AUTO_DEPLOYMENT_FAILED = "auto_deployment_failed"
    AUTO_DEPLOYMENT_ROLLBACK = "auto_deployment_rollback"
    
    # Docker Swarm (version 0.4.3)
    SWARM_CLUSTER_CREATED = "swarm_cluster_created"
    SWARM_CLUSTER_UPDATED = "swarm_cluster_updated"
    SWARM_CLUSTER_DELETED = "swarm_cluster_deleted"
    SWARM_NODE_JOINED = "swarm_node_joined"
    SWARM_NODE_LEFT = "swarm_node_left"
    SWARM_NODE_PROMOTED = "swarm_node_promoted"
    SWARM_NODE_DEMOTED = "swarm_node_demoted"
    SWARM_SERVICE_CREATED = "swarm_service_created"
    SWARM_SERVICE_UPDATED = "swarm_service_updated"
    SWARM_SERVICE_DELETED = "swarm_service_deleted"
    SWARM_SERVICE_SCALED = "swarm_service_scaled"
    SWARM_SERVICE_ROLLED_BACK = "swarm_service_rolled_back"
    SWARM_NETWORK_CREATED = "swarm_network_created"
    SWARM_NETWORK_DELETED = "swarm_network_deleted"
    SWARM_SECRET_CREATED = "swarm_secret_created"
    SWARM_SECRET_UPDATED = "swarm_secret_updated"
    SWARM_SECRET_DELETED = "swarm_secret_deleted"
    SWARM_CONFIG_CREATED = "swarm_config_created"
    SWARM_CONFIG_UPDATED = "swarm_config_updated"
    SWARM_CONFIG_DELETED = "swarm_config_deleted"
    SWARM_STACK_DEPLOYED = "swarm_stack_deployed"
    SWARM_STACK_UPDATED = "swarm_stack_updated"
    SWARM_STACK_REMOVED = "swarm_stack_removed"
    SWARM_LOAD_BALANCER_CREATED = "swarm_load_balancer_created"
    SWARM_LOAD_BALANCER_UPDATED = "swarm_load_balancer_updated"
    SWARM_LOAD_BALANCER_DELETED = "swarm_load_balancer_deleted"
    
    # Environment Management (version 0.4.4)
    ENVIRONMENT_CREATED = "environment_created"
    ENVIRONMENT_UPDATED = "environment_updated"
    ENVIRONMENT_DELETED = "environment_deleted"
    ENVIRONMENT_ACTIVATED = "environment_activated"
    ENVIRONMENT_DEACTIVATED = "environment_deactivated"
    ENVIRONMENT_VARIABLES_UPDATED = "environment_variables_updated"
    ENVIRONMENT_CONFIG_UPDATED = "environment_config_updated"
    BUILD_PROMOTION_STARTED = "build_promotion_started"
    BUILD_PROMOTION_APPROVED = "build_promotion_approved"
    BUILD_PROMOTION_REJECTED = "build_promotion_rejected"
    BUILD_PROMOTION_COMPLETED = "build_promotion_completed"
    BUILD_PROMOTION_FAILED = "build_promotion_failed"
    BUILD_PROMOTION_ROLLBACK = "build_promotion_rollback"
    ENVIRONMENT_DEPLOYMENT_STARTED = "environment_deployment_started"
    ENVIRONMENT_DEPLOYMENT_COMPLETED = "environment_deployment_completed"
    ENVIRONMENT_DEPLOYMENT_FAILED = "environment_deployment_failed"
    ENVIRONMENT_HEALTH_CHECK = "environment_health_check"
    
    # Sécurité
    SECURITY_SCAN_STARTED = "security_scan_started"
    SECURITY_SCAN_COMPLETED = "security_scan_completed"
    SECURITY_VULNERABILITY_DETECTED = "security_vulnerability_detected"
    SECURITY_THREAT_BLOCKED = "security_threat_blocked"
    SECURITY_CONFIG_CHANGED = "security_config_changed"
    ACCESS_DENIED = "access_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Configuration système
    CONFIG_UPDATED = "config_updated"
    SYSTEM_BACKUP_CREATED = "system_backup_created"
    SYSTEM_RESTORED = "system_restored"
    SYSTEM_MAINTENANCE_STARTED = "system_maintenance_started"
    SYSTEM_MAINTENANCE_COMPLETED = "system_maintenance_completed"
    
    # Monitoring et alertes
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"
    METRIC_THRESHOLD_EXCEEDED = "metric_threshold_exceeded"
    HEALTH_CHECK_FAILED = "health_check_failed"
    HEALTH_CHECK_RECOVERED = "health_check_recovered"


class SecurityEventType(str, Enum):
    """
    Types d'événements de sécurité
    """
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_CHANGE = "system_change"
    THREAT_DETECTION = "threat_detection"
    VULNERABILITY_SCAN = "vulnerability_scan"
    COMPLIANCE_CHECK = "compliance_check"
    INCIDENT_RESPONSE = "incident_response"


class SecuritySeverity(str, Enum):
    """
    Niveaux de gravité pour les événements de sécurité
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogLevel(str, Enum):
    """
    Niveaux de log pour l'audit
    """
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
