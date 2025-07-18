"""
Alert Controller - Business logic for alerts and notifications
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from wakedock.repositories.alert_repository import AlertRepository, AlertSeverity, AlertStatus
from wakedock.validators.alert_validator import AlertValidator
from wakedock.services.alert_service import AlertService
from wakedock.core.exceptions import (
    AlertNotFoundError, ValidationError, AlertProcessingError
)

import logging
logger = logging.getLogger(__name__)


class AlertController:
    """Controller for alert business logic"""
    
    def __init__(self, alert_repository: AlertRepository, alert_validator: AlertValidator, alert_service: AlertService):
        self.alert_repository = alert_repository
        self.alert_validator = alert_validator
        self.alert_service = alert_service
    
    async def get_all_alerts(self, limit: int = 50, offset: int = 0, severity: str = None, status: str = None) -> Dict[str, Any]:
        """Get all alerts with optional filters"""
        try:
            # Validate parameters
            if limit <= 0 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Build filters
            filters = {}
            if severity:
                await self.alert_validator.validate_severity(severity)
                filters['severity'] = severity
            
            if status:
                await self.alert_validator.validate_status(status)
                filters['status'] = status
            
            # Get alerts
            if filters:
                alerts = await self.alert_repository.search_alerts("", filters, limit, offset)
            else:
                alerts = await self.alert_repository.get_active_alerts(limit, offset)
            
            # Get total count
            total_count = await self.alert_repository.get_alert_count(filters)
            
            return {
                'alerts': alerts,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(alerts) < total_count,
                'filters': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise AlertProcessingError(f"Failed to get alerts: {str(e)}")
    
    async def get_alert_by_id(self, alert_id: str) -> Dict[str, Any]:
        """Get alert by ID"""
        try:
            # Validate alert ID
            await self.alert_validator.validate_alert_id(alert_id)
            
            # Get alert
            alert = await self.alert_repository.get_by_id(alert_id)
            if not alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Get alert history
            history = await self.alert_repository.get_alert_history(alert_id)
            
            return {
                'alert': alert,
                'history': history
            }
            
        except Exception as e:
            logger.error(f"Error getting alert by ID: {str(e)}")
            raise AlertProcessingError(f"Failed to get alert: {str(e)}")
    
    async def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new alert"""
        try:
            # Validate alert data
            await self.alert_validator.validate_alert_creation(alert_data)
            
            # Generate alert ID
            alert_id = str(uuid4())
            alert_data['id'] = alert_id
            
            # Check for duplicate alerts
            if await self.alert_service.is_duplicate_alert(alert_data):
                logger.info(f"Duplicate alert detected, skipping creation")
                existing_alert = await self.alert_service.find_similar_alert(alert_data)
                return {
                    'alert': existing_alert,
                    'created': False,
                    'reason': 'duplicate'
                }
            
            # Create alert
            alert = await self.alert_repository.create_alert(alert_data)
            
            # Create history entry
            await self.alert_repository.create_alert_history(
                alert_id=alert.id,
                action='created',
                details={'source': 'api'}
            )
            
            # Send notifications
            await self.alert_service.send_alert_notifications(alert)
            
            logger.info(f"Alert created successfully: {alert.id}")
            
            return {
                'alert': alert,
                'created': True,
                'notifications_sent': True
            }
            
        except Exception as e:
            logger.error(f"Error creating alert: {str(e)}")
            raise AlertProcessingError(f"Failed to create alert: {str(e)}")
    
    async def update_alert(self, alert_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update alert"""
        try:
            # Validate alert ID
            await self.alert_validator.validate_alert_id(alert_id)
            
            # Validate update data
            await self.alert_validator.validate_alert_update(update_data)
            
            # Get current alert
            current_alert = await self.alert_repository.get_by_id(alert_id)
            if not current_alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Update alert
            updated_alert = await self.alert_repository.update_alert(alert_id, update_data)
            
            # Create history entry
            await self.alert_repository.create_alert_history(
                alert_id=alert_id,
                action='updated',
                details={'changes': update_data}
            )
            
            logger.info(f"Alert updated successfully: {alert_id}")
            
            return {
                'alert': updated_alert,
                'updated': True
            }
            
        except Exception as e:
            logger.error(f"Error updating alert: {str(e)}")
            raise AlertProcessingError(f"Failed to update alert: {str(e)}")
    
    async def acknowledge_alert(self, alert_id: str, user_id: str) -> Dict[str, Any]:
        """Acknowledge alert"""
        try:
            # Validate alert ID
            await self.alert_validator.validate_alert_id(alert_id)
            
            # Get current alert
            current_alert = await self.alert_repository.get_by_id(alert_id)
            if not current_alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Check if already acknowledged
            if current_alert.status == AlertStatus.ACKNOWLEDGED.value:
                return {
                    'alert': current_alert,
                    'acknowledged': False,
                    'reason': 'already_acknowledged'
                }
            
            # Acknowledge alert
            alert = await self.alert_repository.acknowledge_alert(alert_id, user_id)
            
            # Create history entry
            await self.alert_repository.create_alert_history(
                alert_id=alert_id,
                action='acknowledged',
                user_id=user_id,
                details={'acknowledged_at': datetime.utcnow().isoformat()}
            )
            
            # Send notification
            await self.alert_service.send_acknowledgment_notification(alert, user_id)
            
            logger.info(f"Alert acknowledged: {alert_id} by user: {user_id}")
            
            return {
                'alert': alert,
                'acknowledged': True,
                'acknowledged_by': user_id
            }
            
        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            raise AlertProcessingError(f"Failed to acknowledge alert: {str(e)}")
    
    async def resolve_alert(self, alert_id: str, user_id: str, resolution_note: str = None) -> Dict[str, Any]:
        """Resolve alert"""
        try:
            # Validate alert ID
            await self.alert_validator.validate_alert_id(alert_id)
            
            # Get current alert
            current_alert = await self.alert_repository.get_by_id(alert_id)
            if not current_alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Check if already resolved
            if current_alert.status == AlertStatus.RESOLVED.value:
                return {
                    'alert': current_alert,
                    'resolved': False,
                    'reason': 'already_resolved'
                }
            
            # Resolve alert
            alert = await self.alert_repository.resolve_alert(alert_id, user_id, resolution_note)
            
            # Create history entry
            await self.alert_repository.create_alert_history(
                alert_id=alert_id,
                action='resolved',
                user_id=user_id,
                details={
                    'resolved_at': datetime.utcnow().isoformat(),
                    'resolution_note': resolution_note
                }
            )
            
            # Send notification
            await self.alert_service.send_resolution_notification(alert, user_id)
            
            logger.info(f"Alert resolved: {alert_id} by user: {user_id}")
            
            return {
                'alert': alert,
                'resolved': True,
                'resolved_by': user_id,
                'resolution_note': resolution_note
            }
            
        except Exception as e:
            logger.error(f"Error resolving alert: {str(e)}")
            raise AlertProcessingError(f"Failed to resolve alert: {str(e)}")
    
    async def delete_alert(self, alert_id: str) -> Dict[str, Any]:
        """Delete alert"""
        try:
            # Validate alert ID
            await self.alert_validator.validate_alert_id(alert_id)
            
            # Get current alert
            current_alert = await self.alert_repository.get_by_id(alert_id)
            if not current_alert:
                raise AlertNotFoundError(f"Alert not found: {alert_id}")
            
            # Delete alert
            deleted = await self.alert_repository.delete_alert(alert_id)
            
            logger.info(f"Alert deleted: {alert_id}")
            
            return {
                'alert_id': alert_id,
                'deleted': deleted
            }
            
        except Exception as e:
            logger.error(f"Error deleting alert: {str(e)}")
            raise AlertProcessingError(f"Failed to delete alert: {str(e)}")
    
    async def search_alerts(self, query: str, filters: Dict[str, Any], limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Search alerts"""
        try:
            # Validate parameters
            if limit <= 0 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Validate search query
            await self.alert_validator.validate_search_query(query)
            
            # Validate filters
            await self.alert_validator.validate_search_filters(filters)
            
            # Search alerts
            alerts = await self.alert_repository.search_alerts(query, filters, limit, offset)
            
            # Get total count
            total_count = await self.alert_repository.get_alert_count(filters)
            
            return {
                'alerts': alerts,
                'query': query,
                'filters': filters,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(alerts) < total_count
            }
            
        except Exception as e:
            logger.error(f"Error searching alerts: {str(e)}")
            raise AlertProcessingError(f"Failed to search alerts: {str(e)}")
    
    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics"""
        try:
            # Get database statistics
            db_stats = await self.alert_repository.get_alert_statistics()
            
            # Get additional statistics from alert service
            service_stats = await self.alert_service.get_alert_service_stats()
            
            # Get critical alerts
            critical_alerts = await self.alert_repository.get_critical_alerts()
            
            return {
                'database_stats': db_stats,
                'service_stats': service_stats,
                'critical_alerts': critical_alerts,
                'summary': {
                    'total_alerts': db_stats['total_alerts'],
                    'active_alerts': db_stats['active_alerts'],
                    'critical_count': len(critical_alerts),
                    'recent_alerts': db_stats['recent_alerts']
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {str(e)}")
            raise AlertProcessingError(f"Failed to get alert statistics: {str(e)}")
    
    async def get_alert_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get alert trends"""
        try:
            # Validate days parameter
            if days <= 0 or days > 365:
                raise ValidationError("Days must be between 1 and 365")
            
            # Get trends from repository
            trends = await self.alert_repository.get_alert_trends(days)
            
            # Calculate trend metrics
            trend_metrics = await self.alert_service.calculate_trend_metrics(trends)
            
            return {
                'trends': trends,
                'metrics': trend_metrics,
                'period': days
            }
            
        except Exception as e:
            logger.error(f"Error getting alert trends: {str(e)}")
            raise AlertProcessingError(f"Failed to get alert trends: {str(e)}")
    
    async def get_alerts_by_container(self, container_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get alerts for specific container"""
        try:
            # Validate container ID
            await self.alert_validator.validate_container_id(container_id)
            
            # Get alerts
            alerts = await self.alert_repository.get_alerts_by_container(container_id, limit, offset)
            
            # Get total count
            filters = {'container_id': container_id}
            total_count = await self.alert_repository.get_alert_count(filters)
            
            return {
                'alerts': alerts,
                'container_id': container_id,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(alerts) < total_count
            }
            
        except Exception as e:
            logger.error(f"Error getting alerts by container: {str(e)}")
            raise AlertProcessingError(f"Failed to get alerts by container: {str(e)}")
    
    async def get_alerts_by_service(self, service_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get alerts for specific service"""
        try:
            # Validate service ID
            await self.alert_validator.validate_service_id(service_id)
            
            # Get alerts
            alerts = await self.alert_repository.get_alerts_by_service(service_id, limit, offset)
            
            # Get total count
            filters = {'service_id': service_id}
            total_count = await self.alert_repository.get_alert_count(filters)
            
            return {
                'alerts': alerts,
                'service_id': service_id,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(alerts) < total_count
            }
            
        except Exception as e:
            logger.error(f"Error getting alerts by service: {str(e)}")
            raise AlertProcessingError(f"Failed to get alerts by service: {str(e)}")
    
    async def get_critical_alerts(self) -> Dict[str, Any]:
        """Get critical alerts"""
        try:
            # Get critical alerts
            critical_alerts = await self.alert_repository.get_critical_alerts()
            
            # Get critical alert metrics
            critical_metrics = await self.alert_service.get_critical_alert_metrics(critical_alerts)
            
            return {
                'critical_alerts': critical_alerts,
                'count': len(critical_alerts),
                'metrics': critical_metrics
            }
            
        except Exception as e:
            logger.error(f"Error getting critical alerts: {str(e)}")
            raise AlertProcessingError(f"Failed to get critical alerts: {str(e)}")
    
    async def cleanup_old_alerts(self, days: int = 30) -> Dict[str, Any]:
        """Cleanup old alerts"""
        try:
            # Validate days parameter
            if days <= 0:
                raise ValidationError("Days must be positive")
            
            # Cleanup old alerts
            cleaned_count = await self.alert_repository.cleanup_old_alerts(days)
            
            logger.info(f"Cleaned up {cleaned_count} old alerts (older than {days} days)")
            
            return {
                'cleaned_count': cleaned_count,
                'days': days,
                'cleaned_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {str(e)}")
            raise AlertProcessingError(f"Failed to cleanup old alerts: {str(e)}")
    
    async def process_metric_alert(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process metric-based alert"""
        try:
            # Validate metric data
            await self.alert_validator.validate_metric_data(metric_data)
            
            # Process metric through alert service
            result = await self.alert_service.process_metric_alert(metric_data)
            
            # Create alerts if thresholds are exceeded
            alerts_created = []
            for alert_data in result.get('triggered_alerts', []):
                alert_result = await self.create_alert(alert_data)
                if alert_result['created']:
                    alerts_created.append(alert_result['alert'])
            
            return {
                'metric_processed': True,
                'alerts_created': alerts_created,
                'alerts_count': len(alerts_created),
                'metric_data': metric_data
            }
            
        except Exception as e:
            logger.error(f"Error processing metric alert: {str(e)}")
            raise AlertProcessingError(f"Failed to process metric alert: {str(e)}")
    
    async def test_alert_system(self) -> Dict[str, Any]:
        """Test alert system functionality"""
        try:
            # Test database connectivity
            test_results = {
                'database_connection': False,
                'alert_creation': False,
                'notification_service': False,
                'alert_processing': False
            }
            
            # Test database
            try:
                await self.alert_repository.get_alert_statistics()
                test_results['database_connection'] = True
            except Exception as e:
                logger.error(f"Database test failed: {str(e)}")
            
            # Test alert creation
            try:
                test_alert_data = {
                    'title': 'Test Alert',
                    'description': 'System test alert',
                    'severity': AlertSeverity.LOW.value,
                    'metric_name': 'test_metric',
                    'metric_value': 100,
                    'threshold': 90,
                    'tags': {'test': True}
                }
                
                test_alert = await self.create_alert(test_alert_data)
                if test_alert['created']:
                    test_results['alert_creation'] = True
                    # Clean up test alert
                    await self.delete_alert(test_alert['alert'].id)
            except Exception as e:
                logger.error(f"Alert creation test failed: {str(e)}")
            
            # Test notification service
            try:
                notification_test = await self.alert_service.test_notifications()
                test_results['notification_service'] = notification_test['success']
            except Exception as e:
                logger.error(f"Notification test failed: {str(e)}")
            
            # Test alert processing
            try:
                processing_test = await self.alert_service.test_alert_processing()
                test_results['alert_processing'] = processing_test['success']
            except Exception as e:
                logger.error(f"Alert processing test failed: {str(e)}")
            
            # Overall health
            all_passed = all(test_results.values())
            
            return {
                'system_health': 'healthy' if all_passed else 'degraded',
                'test_results': test_results,
                'tested_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error testing alert system: {str(e)}")
            raise AlertProcessingError(f"Failed to test alert system: {str(e)}")
