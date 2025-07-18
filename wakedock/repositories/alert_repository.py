"""
Alert Repository - Data access layer for alerts and notifications
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from enum import Enum

from wakedock.models.alert import Alert, AlertRule, AlertHistory, AlertChannel
from wakedock.core.database import AsyncSessionLocal
from wakedock.core.exceptions import DatabaseError, AlertNotFoundError

import logging
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status types"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class AlertRepository:
    """Repository for alert data access"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        try:
            query = select(Alert).where(Alert.id == alert_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting alert by ID: {str(e)}")
            raise DatabaseError(f"Failed to get alert: {str(e)}")
    
    async def get_by_rule_id(self, rule_id: str) -> List[Alert]:
        """Get alerts by rule ID"""
        try:
            query = select(Alert).where(Alert.rule_id == rule_id)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting alerts by rule ID: {str(e)}")
            raise DatabaseError(f"Failed to get alerts: {str(e)}")
    
    async def get_active_alerts(self, limit: int = 50, offset: int = 0) -> List[Alert]:
        """Get active alerts"""
        try:
            query = (
                select(Alert)
                .where(Alert.status == AlertStatus.ACTIVE.value)
                .order_by(desc(Alert.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}")
            raise DatabaseError(f"Failed to get active alerts: {str(e)}")
    
    async def get_alerts_by_severity(self, severity: AlertSeverity, limit: int = 50, offset: int = 0) -> List[Alert]:
        """Get alerts by severity"""
        try:
            query = (
                select(Alert)
                .where(Alert.severity == severity.value)
                .order_by(desc(Alert.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting alerts by severity: {str(e)}")
            raise DatabaseError(f"Failed to get alerts: {str(e)}")
    
    async def get_alerts_by_container(self, container_id: str, limit: int = 50, offset: int = 0) -> List[Alert]:
        """Get alerts for specific container"""
        try:
            query = (
                select(Alert)
                .where(Alert.container_id == container_id)
                .order_by(desc(Alert.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting alerts by container: {str(e)}")
            raise DatabaseError(f"Failed to get alerts: {str(e)}")
    
    async def get_alerts_by_service(self, service_id: str, limit: int = 50, offset: int = 0) -> List[Alert]:
        """Get alerts for specific service"""
        try:
            query = (
                select(Alert)
                .where(Alert.service_id == service_id)
                .order_by(desc(Alert.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting alerts by service: {str(e)}")
            raise DatabaseError(f"Failed to get alerts: {str(e)}")
    
    async def create_alert(self, alert_data: Dict[str, Any]) -> Alert:
        """Create new alert"""
        try:
            alert = Alert(
                id=alert_data.get('id'),
                rule_id=alert_data.get('rule_id'),
                title=alert_data.get('title'),
                description=alert_data.get('description'),
                severity=alert_data.get('severity', AlertSeverity.MEDIUM.value),
                status=alert_data.get('status', AlertStatus.ACTIVE.value),
                container_id=alert_data.get('container_id'),
                service_id=alert_data.get('service_id'),
                node_id=alert_data.get('node_id'),
                metric_name=alert_data.get('metric_name'),
                metric_value=alert_data.get('metric_value'),
                threshold=alert_data.get('threshold'),
                operator=alert_data.get('operator', 'gt'),
                tags=alert_data.get('tags', {}),
                metadata=alert_data.get('metadata', {}),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.session.add(alert)
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Created alert: {alert.id}")
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating alert: {str(e)}")
            raise DatabaseError(f"Failed to create alert: {str(e)}")
    
    async def update_alert(self, alert_id: str, update_data: Dict[str, Any]) -> Alert:
        """Update alert"""
        try:
            alert = await self.get_by_id(alert_id)
            if not alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Update allowed fields
            allowed_fields = ['status', 'severity', 'description', 'metadata', 'resolved_at', 'acknowledged_at']
            for field in allowed_fields:
                if field in update_data:
                    setattr(alert, field, update_data[field])
            
            alert.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Updated alert: {alert.id}")
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating alert: {str(e)}")
            raise DatabaseError(f"Failed to update alert: {str(e)}")
    
    async def delete_alert(self, alert_id: str) -> bool:
        """Delete alert"""
        try:
            alert = await self.get_by_id(alert_id)
            if not alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            await self.session.delete(alert)
            await self.session.commit()
            
            logger.info(f"Deleted alert: {alert_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting alert: {str(e)}")
            raise DatabaseError(f"Failed to delete alert: {str(e)}")
    
    async def acknowledge_alert(self, alert_id: str, user_id: str) -> Alert:
        """Acknowledge alert"""
        try:
            alert = await self.get_by_id(alert_id)
            if not alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            alert.status = AlertStatus.ACKNOWLEDGED.value
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = user_id
            alert.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Acknowledged alert: {alert_id} by user: {user_id}")
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error acknowledging alert: {str(e)}")
            raise DatabaseError(f"Failed to acknowledge alert: {str(e)}")
    
    async def resolve_alert(self, alert_id: str, user_id: str, resolution_note: str = None) -> Alert:
        """Resolve alert"""
        try:
            alert = await self.get_by_id(alert_id)
            if not alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            alert.status = AlertStatus.RESOLVED.value
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = user_id
            alert.resolution_note = resolution_note
            alert.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(alert)
            
            logger.info(f"Resolved alert: {alert_id} by user: {user_id}")
            return alert
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error resolving alert: {str(e)}")
            raise DatabaseError(f"Failed to resolve alert: {str(e)}")
    
    async def search_alerts(self, query: str, filters: Dict[str, Any], limit: int = 50, offset: int = 0) -> List[Alert]:
        """Search alerts with filters"""
        try:
            stmt = select(Alert)
            
            # Add search query
            if query:
                search_filter = or_(
                    Alert.title.ilike(f"%{query}%"),
                    Alert.description.ilike(f"%{query}%"),
                    Alert.metric_name.ilike(f"%{query}%")
                )
                stmt = stmt.where(search_filter)
            
            # Add filters
            if filters.get('severity'):
                stmt = stmt.where(Alert.severity == filters['severity'])
            
            if filters.get('status'):
                stmt = stmt.where(Alert.status == filters['status'])
            
            if filters.get('container_id'):
                stmt = stmt.where(Alert.container_id == filters['container_id'])
            
            if filters.get('service_id'):
                stmt = stmt.where(Alert.service_id == filters['service_id'])
            
            if filters.get('created_after'):
                stmt = stmt.where(Alert.created_at >= filters['created_after'])
            
            if filters.get('created_before'):
                stmt = stmt.where(Alert.created_at <= filters['created_before'])
            
            # Apply ordering, limit, offset
            stmt = stmt.order_by(desc(Alert.created_at)).limit(limit).offset(offset)
            
            result = await self.session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error searching alerts: {str(e)}")
            raise DatabaseError(f"Failed to search alerts: {str(e)}")
    
    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics"""
        try:
            # Total alerts
            total_query = select(func.count(Alert.id))
            total_result = await self.session.execute(total_query)
            total_alerts = total_result.scalar()
            
            # Active alerts
            active_query = select(func.count(Alert.id)).where(Alert.status == AlertStatus.ACTIVE.value)
            active_result = await self.session.execute(active_query)
            active_alerts = active_result.scalar()
            
            # Alerts by severity
            severity_query = select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
            severity_result = await self.session.execute(severity_query)
            severity_stats = {row[0]: row[1] for row in severity_result.fetchall()}
            
            # Alerts by status
            status_query = select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
            status_result = await self.session.execute(status_query)
            status_stats = {row[0]: row[1] for row in status_result.fetchall()}
            
            # Recent alerts (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_query = select(func.count(Alert.id)).where(Alert.created_at >= recent_cutoff)
            recent_result = await self.session.execute(recent_query)
            recent_alerts = recent_result.scalar()
            
            return {
                'total_alerts': total_alerts,
                'active_alerts': active_alerts,
                'recent_alerts': recent_alerts,
                'severity_distribution': severity_stats,
                'status_distribution': status_stats,
                'alert_rate': {
                    'last_24h': recent_alerts,
                    'avg_daily': total_alerts / 30 if total_alerts > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {str(e)}")
            raise DatabaseError(f"Failed to get alert statistics: {str(e)}")
    
    async def get_alert_history(self, alert_id: str, limit: int = 50, offset: int = 0) -> List[AlertHistory]:
        """Get alert history"""
        try:
            query = (
                select(AlertHistory)
                .where(AlertHistory.alert_id == alert_id)
                .order_by(desc(AlertHistory.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting alert history: {str(e)}")
            raise DatabaseError(f"Failed to get alert history: {str(e)}")
    
    async def create_alert_history(self, alert_id: str, action: str, user_id: str = None, details: Dict[str, Any] = None) -> AlertHistory:
        """Create alert history entry"""
        try:
            history = AlertHistory(
                alert_id=alert_id,
                action=action,
                user_id=user_id,
                details=details or {},
                created_at=datetime.utcnow()
            )
            
            self.session.add(history)
            await self.session.commit()
            await self.session.refresh(history)
            
            return history
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating alert history: {str(e)}")
            raise DatabaseError(f"Failed to create alert history: {str(e)}")
    
    async def get_alert_count(self, filters: Dict[str, Any] = None) -> int:
        """Get total count of alerts with optional filters"""
        try:
            query = select(func.count(Alert.id))
            
            if filters:
                if filters.get('severity'):
                    query = query.where(Alert.severity == filters['severity'])
                
                if filters.get('status'):
                    query = query.where(Alert.status == filters['status'])
                
                if filters.get('container_id'):
                    query = query.where(Alert.container_id == filters['container_id'])
                
                if filters.get('service_id'):
                    query = query.where(Alert.service_id == filters['service_id'])
            
            result = await self.session.execute(query)
            return result.scalar()
            
        except Exception as e:
            logger.error(f"Error getting alert count: {str(e)}")
            raise DatabaseError(f"Failed to get alert count: {str(e)}")
    
    async def get_critical_alerts(self, limit: int = 10) -> List[Alert]:
        """Get critical alerts"""
        try:
            query = (
                select(Alert)
                .where(and_(
                    Alert.severity == AlertSeverity.CRITICAL.value,
                    Alert.status == AlertStatus.ACTIVE.value
                ))
                .order_by(desc(Alert.created_at))
                .limit(limit)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting critical alerts: {str(e)}")
            raise DatabaseError(f"Failed to get critical alerts: {str(e)}")
    
    async def get_alert_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get alert trends for specified number of days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Daily alert counts
            daily_query = select(
                func.date(Alert.created_at).label('date'),
                func.count(Alert.id).label('count')
            ).where(Alert.created_at >= cutoff_date).group_by(func.date(Alert.created_at))
            
            daily_result = await self.session.execute(daily_query)
            daily_trends = {str(row.date): row.count for row in daily_result.fetchall()}
            
            # Severity trends
            severity_query = select(
                func.date(Alert.created_at).label('date'),
                Alert.severity,
                func.count(Alert.id).label('count')
            ).where(Alert.created_at >= cutoff_date).group_by(func.date(Alert.created_at), Alert.severity)
            
            severity_result = await self.session.execute(severity_query)
            severity_trends = {}
            for row in severity_result.fetchall():
                date_str = str(row.date)
                if date_str not in severity_trends:
                    severity_trends[date_str] = {}
                severity_trends[date_str][row.severity] = row.count
            
            return {
                'daily_trends': daily_trends,
                'severity_trends': severity_trends,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting alert trends: {str(e)}")
            raise DatabaseError(f"Failed to get alert trends: {str(e)}")
    
    async def cleanup_old_alerts(self, days: int = 30) -> int:
        """Cleanup old resolved alerts"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old resolved alerts
            delete_query = select(Alert).where(and_(
                Alert.status == AlertStatus.RESOLVED.value,
                Alert.resolved_at < cutoff_date
            ))
            
            result = await self.session.execute(delete_query)
            alerts_to_delete = result.scalars().all()
            
            for alert in alerts_to_delete:
                await self.session.delete(alert)
            
            await self.session.commit()
            
            logger.info(f"Cleaned up {len(alerts_to_delete)} old alerts")
            return len(alerts_to_delete)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cleaning up old alerts: {str(e)}")
            raise DatabaseError(f"Failed to cleanup old alerts: {str(e)}")
