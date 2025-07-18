"""
Modèles de base de données pour l'audit de sécurité avancé
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class SecurityEvent(Base):
    """
    Modèle pour les événements de sécurité avec métadonnées enrichies
    """
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), index=True, nullable=False)  # low, medium, high, critical
    risk_score = Column(Integer, nullable=False, default=0)  # 0-100
    
    # Informations utilisateur
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    ip_address = Column(String(45), index=True, nullable=False)  # Support IPv6
    user_agent = Column(Text, nullable=True)
    
    # Détails de l'événement
    resource = Column(String(255), nullable=True)
    action = Column(String(100), nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    
    # Données structurées
    details = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Relations
    user = relationship("User", back_populates="security_events")
    related_anomalies = relationship("AnomalyDetection", back_populates="related_event")
    
    # Index composites pour les requêtes fréquentes
    __table_args__ = (
        Index('idx_security_events_user_date', 'user_id', 'created_at'),
        Index('idx_security_events_ip_date', 'ip_address', 'created_at'),
        Index('idx_security_events_type_severity', 'event_type', 'severity'),
        Index('idx_security_events_risk_score', 'risk_score'),
    )

class AnomalyDetection(Base):
    """
    Modèle pour les anomalies détectées par le système de sécurité
    """
    __tablename__ = "anomaly_detections"
    
    id = Column(Integer, primary_key=True, index=True)
    anomaly_type = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), index=True, nullable=False)  # low, medium, high, critical
    confidence = Column(Float, nullable=False)  # 0.0 - 1.0
    
    # Informations utilisateur/système
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    affected_resource = Column(String(255), nullable=True)
    
    # Description et recommandations
    description = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=True)  # Preuves/données de l'anomalie
    recommended_actions = Column(JSON, nullable=True)  # Actions recommandées
    
    # État de résolution
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Métadonnées
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Référence à l'événement de sécurité déclencheur
    triggering_event_id = Column(String(255), ForeignKey("security_events.event_id"), nullable=True)
    
    # Relations
    user = relationship("User", foreign_keys=[user_id], back_populates="anomalies")
    resolver = relationship("User", foreign_keys=[resolved_by])
    related_event = relationship("SecurityEvent", back_populates="related_anomalies")
    
    # Index composites
    __table_args__ = (
        Index('idx_anomalies_user_resolved', 'user_id', 'resolved'),
        Index('idx_anomalies_severity_date', 'severity', 'created_at'),
        Index('idx_anomalies_type_confidence', 'anomaly_type', 'confidence'),
    )

class SecurityCompliance(Base):
    """
    Modèle pour le suivi de conformité aux standards de sécurité
    """
    __tablename__ = "security_compliance"
    
    id = Column(Integer, primary_key=True, index=True)
    standard_name = Column(String(100), nullable=False)  # ISO27001, GDPR, SOX, etc.
    requirement_id = Column(String(50), nullable=False)  # ID du requirement spécifique
    requirement_name = Column(String(255), nullable=False)
    
    # État de conformité
    compliance_status = Column(String(20), nullable=False)  # compliant, non_compliant, partial, unknown
    last_assessment_date = Column(DateTime, nullable=True)
    next_assessment_date = Column(DateTime, nullable=True)
    
    # Détails
    description = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # Preuves de conformité
    gaps = Column(JSON, nullable=True)  # Lacunes identifiées
    remediation_plan = Column(JSON, nullable=True)  # Plan de remédiation
    
    # Métadonnées
    assessed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    assessor = relationship("User")
    
    # Index pour les requêtes fréquentes
    __table_args__ = (
        Index('idx_compliance_standard_status', 'standard_name', 'compliance_status'),
        Index('idx_compliance_next_assessment', 'next_assessment_date'),
    )

class SecurityAlert(Base):
    """
    Modèle pour les alertes de sécurité automatiques
    """
    __tablename__ = "security_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), index=True, nullable=False)  # low, medium, high, critical
    status = Column(String(20), nullable=False, default="active")  # active, acknowledged, resolved, false_positive
    
    # Contenu de l'alerte
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Source de l'alerte
    source_type = Column(String(50), nullable=False)  # anomaly, threshold, manual, external
    source_id = Column(String(255), nullable=True)  # ID de la source (anomaly_id, event_id, etc.)
    
    # Assignation
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    # Actions automatiques
    auto_actions_taken = Column(JSON, nullable=True)
    manual_actions_required = Column(JSON, nullable=True)
    
    # Métadonnées
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    assignee = relationship("User", back_populates="assigned_security_alerts")
    
    # Index composites
    __table_args__ = (
        Index('idx_security_alerts_status_severity', 'status', 'severity'),
        Index('idx_security_alerts_assigned', 'assigned_to', 'status'),
        Index('idx_security_alerts_type_date', 'alert_type', 'created_at'),
    )

class SecurityMetrics(Base):
    """
    Modèle pour stocker les métriques de sécurité calculées périodiquement
    """
    __tablename__ = "security_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(100), index=True, nullable=False)  # daily, weekly, monthly
    metric_date = Column(DateTime, index=True, nullable=False)
    
    # Métriques calculées
    total_events = Column(Integer, nullable=False, default=0)
    security_incidents = Column(Integer, nullable=False, default=0)
    anomalies_detected = Column(Integer, nullable=False, default=0)
    anomalies_resolved = Column(Integer, nullable=False, default=0)
    average_risk_score = Column(Float, nullable=False, default=0.0)
    
    # Métriques détaillées
    events_by_type = Column(JSON, nullable=True)
    events_by_severity = Column(JSON, nullable=True)
    top_suspicious_ips = Column(JSON, nullable=True)
    compliance_scores = Column(JSON, nullable=True)
    
    # Métadonnées
    calculation_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Index pour les requêtes temporelles
    __table_args__ = (
        Index('idx_security_metrics_type_date', 'metric_type', 'metric_date'),
    )

class LogRetention(Base):
    """
    Modèle pour gérer la rétention des logs de sécurité
    """
    __tablename__ = "log_retention"
    
    id = Column(Integer, primary_key=True, index=True)
    log_type = Column(String(100), index=True, nullable=False)  # security, audit, system, etc.
    log_date = Column(DateTime, index=True, nullable=False)
    
    # Informations du fichier
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # en bytes
    is_compressed = Column(Boolean, nullable=False, default=False)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    
    # Checksums pour intégrité
    file_hash = Column(String(64), nullable=False)  # SHA-256
    compression_ratio = Column(Float, nullable=True)  # Si compressé
    
    # Politique de rétention
    retention_policy = Column(String(100), nullable=False)  # standard, extended, permanent
    retention_until = Column(DateTime, nullable=False)
    
    # État
    status = Column(String(20), nullable=False, default="active")  # active, archived, deleted
    archived_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Métadonnées
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Index pour les requêtes de nettoyage
    __table_args__ = (
        Index('idx_log_retention_date_status', 'log_date', 'status'),
        Index('idx_log_retention_until', 'retention_until'),
        Index('idx_log_retention_type_date', 'log_type', 'log_date'),
    )

# Extensions du modèle User pour les relations de sécurité
def extend_user_model():
    """
    Fonction pour étendre le modèle User avec les relations de sécurité
    À appeler après l'import du modèle User existant
    """
    try:
        from wakedock.models.user import User

        # Ajouter les relations si elles n'existent pas déjà
        if not hasattr(User, 'security_events'):
            User.security_events = relationship("SecurityEvent", back_populates="user")
        
        if not hasattr(User, 'anomalies'):
            User.anomalies = relationship("AnomalyDetection", foreign_keys="AnomalyDetection.user_id", back_populates="user")
        
        if not hasattr(User, 'assigned_security_alerts'):
            User.assigned_security_alerts = relationship("SecurityAlert", back_populates="assignee")
            
    except ImportError:
        # Le modèle User n'existe pas encore ou n'est pas accessible
        pass
