"""
Models for alerts management
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wakedock.models.base import BaseModel, AuditableModel

class Alert(AuditableModel):
    """Model for alerts"""
    
    __tablename__ = "alerts"
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(50), default="info")  # info, warning, error, critical
    source = Column(String(255), nullable=True)
    target = Column(String(255), nullable=True)
    status = Column(String(50), default="active")  # active, resolved, dismissed
    alert_type = Column(String(100), nullable=False)
    alert_metadata = Column(JSON, nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(255), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(255), nullable=True)
    
    # Relations
    rules = relationship("AlertRule", back_populates="alert")
    
    def __repr__(self):
        return f"<Alert {self.id}: {self.title}>"


class AlertRule(AuditableModel):
    """Model for alert rules"""
    
    __tablename__ = "alert_rules"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    condition = Column(Text, nullable=False)  # SQL-like condition
    severity = Column(String(50), default="info")
    is_enabled = Column(Boolean, default=True)
    threshold_value = Column(String(100), nullable=True)
    threshold_operator = Column(String(20), nullable=True)  # >, <, =, >=, <=
    evaluation_interval = Column(Integer, default=300)  # seconds
    notification_channels = Column(JSON, nullable=True)
    last_evaluation = Column(DateTime(timezone=True), nullable=True)
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True)
    
    # Relations
    alert = relationship("Alert", back_populates="rules")
    
    def __repr__(self):
        return f"<AlertRule {self.id}: {self.name}>"


class AlertHistory(BaseModel):
    """Model for alert history"""
    
    __tablename__ = "alert_history"
    
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    action = Column(String(50), nullable=False)  # created, updated, resolved, dismissed
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    user_id = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<AlertHistory {self.id}: {self.action}>"


class AlertNotification(BaseModel):
    """Model for alert notifications"""
    
    __tablename__ = "alert_notifications"
    
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    channel = Column(String(50), nullable=False)  # email, slack, webhook, etc.
    recipient = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="pending")  # pending, sent, failed
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<AlertNotification {self.id}: {self.channel}>"
