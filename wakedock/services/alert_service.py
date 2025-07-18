"""
Alert Service - Business logic for alert processing and notifications
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
import ssl

from wakedock.repositories.alert_repository import AlertSeverity, AlertStatus
from wakedock.core.config import settings
from wakedock.core.cache import redis_client
from wakedock.core.exceptions import AlertServiceError, NotificationError

import logging
logger = logging.getLogger(__name__)


class AlertService:
    """Service for alert processing and notifications"""
    
    def __init__(self):
        self.notification_channels = {
            'email': self._send_email_notification,
            'slack': self._send_slack_notification,
            'webhook': self._send_webhook_notification,
            'discord': self._send_discord_notification
        }
        self.alert_cache_ttl = 3600  # 1 hour
        self.duplicate_window = 300  # 5 minutes
        self.cooldown_periods = {
            AlertSeverity.CRITICAL.value: 60,    # 1 minute
            AlertSeverity.HIGH.value: 300,       # 5 minutes
            AlertSeverity.MEDIUM.value: 900,     # 15 minutes
            AlertSeverity.LOW.value: 3600        # 1 hour
        }
    
    async def is_duplicate_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert is a duplicate"""
        try:
            # Create duplicate key
            duplicate_key = self._get_duplicate_key(alert_data)
            
            # Check if duplicate exists in cache
            cached_alert = await redis_client.get(duplicate_key)
            if cached_alert:
                return True
            
            # Cache this alert for duplicate detection
            await redis_client.setex(
                duplicate_key,
                self.duplicate_window,
                json.dumps({
                    'timestamp': datetime.utcnow().isoformat(),
                    'alert_data': alert_data
                })
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate alert: {str(e)}")
            return False
    
    def _get_duplicate_key(self, alert_data: Dict[str, Any]) -> str:
        """Generate duplicate detection key"""
        key_parts = [
            alert_data.get('metric_name', ''),
            alert_data.get('container_id', ''),
            alert_data.get('service_id', ''),
            alert_data.get('severity', ''),
            str(alert_data.get('threshold', ''))
        ]
        return f"alert_duplicate:{':'.join(key_parts)}"
    
    async def find_similar_alert(self, alert_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find similar existing alert"""
        try:
            # This would typically query the database for similar alerts
            # For now, return None (no similar alert found)
            return None
            
        except Exception as e:
            logger.error(f"Error finding similar alert: {str(e)}")
            return None
    
    async def send_alert_notifications(self, alert: Any) -> Dict[str, Any]:
        """Send notifications for alert"""
        try:
            notification_results = {}
            
            # Get notification channels for alert severity
            channels = await self._get_notification_channels(alert.severity)
            
            # Send notifications to each channel
            for channel in channels:
                try:
                    result = await self._send_notification(channel, alert)
                    notification_results[channel['name']] = result
                except Exception as e:
                    logger.error(f"Error sending notification to {channel['name']}: {str(e)}")
                    notification_results[channel['name']] = {'success': False, 'error': str(e)}
            
            return {
                'notifications_sent': len([r for r in notification_results.values() if r.get('success')]),
                'total_channels': len(channels),
                'results': notification_results
            }
            
        except Exception as e:
            logger.error(f"Error sending alert notifications: {str(e)}")
            raise NotificationError(f"Failed to send notifications: {str(e)}")
    
    async def _get_notification_channels(self, severity: str) -> List[Dict[str, Any]]:
        """Get notification channels for severity level"""
        # This would typically be configured in database
        # For now, return default channels based on severity
        channels = []
        
        if severity == AlertSeverity.CRITICAL.value:
            channels = [
                {'name': 'email', 'type': 'email', 'config': {'recipient': settings.ALERT_EMAIL}},
                {'name': 'slack', 'type': 'slack', 'config': {'webhook_url': settings.SLACK_WEBHOOK_URL}}
            ]
        elif severity == AlertSeverity.HIGH.value:
            channels = [
                {'name': 'email', 'type': 'email', 'config': {'recipient': settings.ALERT_EMAIL}}
            ]
        elif severity == AlertSeverity.MEDIUM.value:
            channels = [
                {'name': 'slack', 'type': 'slack', 'config': {'webhook_url': settings.SLACK_WEBHOOK_URL}}
            ]
        
        return channels
    
    async def _send_notification(self, channel: Dict[str, Any], alert: Any) -> Dict[str, Any]:
        """Send notification to specific channel"""
        try:
            channel_type = channel['type']
            
            if channel_type in self.notification_channels:
                handler = self.notification_channels[channel_type]
                return await handler(channel, alert)
            else:
                raise NotificationError(f"Unsupported notification channel: {channel_type}")
                
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise NotificationError(f"Failed to send notification: {str(e)}")
    
    async def _send_email_notification(self, channel: Dict[str, Any], alert: Any) -> Dict[str, Any]:
        """Send email notification"""
        try:
            recipient = channel['config']['recipient']
            
            # Create email message
            message = MIMEMultipart()
            message['From'] = settings.SMTP_FROM_EMAIL
            message['To'] = recipient
            message['Subject'] = f"[{alert.severity.upper()}] {alert.title}"
            
            # Email body
            body = f"""
            Alert: {alert.title}
            Severity: {alert.severity.upper()}
            Status: {alert.status.upper()}
            
            Description: {alert.description}
            
            Metric: {alert.metric_name}
            Value: {alert.metric_value}
            Threshold: {alert.threshold}
            
            Container: {alert.container_id or 'N/A'}
            Service: {alert.service_id or 'N/A'}
            
            Created: {alert.created_at}
            
            Alert ID: {alert.id}
            """
            
            message.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
            server.send_message(message)
            server.quit()
            
            return {'success': True, 'channel': 'email', 'recipient': recipient}
            
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _send_slack_notification(self, channel: Dict[str, Any], alert: Any) -> Dict[str, Any]:
        """Send Slack notification"""
        try:
            webhook_url = channel['config']['webhook_url']
            
            # Color based on severity
            color_map = {
                AlertSeverity.CRITICAL.value: '#FF0000',
                AlertSeverity.HIGH.value: '#FF8000',
                AlertSeverity.MEDIUM.value: '#FFFF00',
                AlertSeverity.LOW.value: '#00FF00'
            }
            
            # Create Slack message
            payload = {
                'attachments': [{
                    'color': color_map.get(alert.severity, '#808080'),
                    'title': f"[{alert.severity.upper()}] {alert.title}",
                    'text': alert.description,
                    'fields': [
                        {'title': 'Metric', 'value': alert.metric_name, 'short': True},
                        {'title': 'Value', 'value': str(alert.metric_value), 'short': True},
                        {'title': 'Threshold', 'value': str(alert.threshold), 'short': True},
                        {'title': 'Status', 'value': alert.status.upper(), 'short': True},
                        {'title': 'Container', 'value': alert.container_id or 'N/A', 'short': True},
                        {'title': 'Service', 'value': alert.service_id or 'N/A', 'short': True}
                    ],
                    'footer': 'WakeDock Alert System',
                    'ts': int(alert.created_at.timestamp())
                }]
            }
            
            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        return {'success': True, 'channel': 'slack'}
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f"Slack API error: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _send_webhook_notification(self, channel: Dict[str, Any], alert: Any) -> Dict[str, Any]:
        """Send webhook notification"""
        try:
            webhook_url = channel['config']['url']
            
            # Create webhook payload
            payload = {
                'alert_id': alert.id,
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity,
                'status': alert.status,
                'metric_name': alert.metric_name,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold,
                'container_id': alert.container_id,
                'service_id': alert.service_id,
                'created_at': alert.created_at.isoformat(),
                'tags': alert.tags,
                'metadata': alert.metadata
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status < 400:
                        return {'success': True, 'channel': 'webhook'}
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f"Webhook error: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error sending webhook notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _send_discord_notification(self, channel: Dict[str, Any], alert: Any) -> Dict[str, Any]:
        """Send Discord notification"""
        try:
            webhook_url = channel['config']['webhook_url']
            
            # Color based on severity
            color_map = {
                AlertSeverity.CRITICAL.value: 0xFF0000,
                AlertSeverity.HIGH.value: 0xFF8000,
                AlertSeverity.MEDIUM.value: 0xFFFF00,
                AlertSeverity.LOW.value: 0x00FF00
            }
            
            # Create Discord embed
            embed = {
                'title': f"[{alert.severity.upper()}] {alert.title}",
                'description': alert.description,
                'color': color_map.get(alert.severity, 0x808080),
                'fields': [
                    {'name': 'Metric', 'value': alert.metric_name, 'inline': True},
                    {'name': 'Value', 'value': str(alert.metric_value), 'inline': True},
                    {'name': 'Threshold', 'value': str(alert.threshold), 'inline': True},
                    {'name': 'Status', 'value': alert.status.upper(), 'inline': True},
                    {'name': 'Container', 'value': alert.container_id or 'N/A', 'inline': True},
                    {'name': 'Service', 'value': alert.service_id or 'N/A', 'inline': True}
                ],
                'footer': {'text': 'WakeDock Alert System'},
                'timestamp': alert.created_at.isoformat()
            }
            
            payload = {'embeds': [embed]}
            
            # Send to Discord
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        return {'success': True, 'channel': 'discord'}
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f"Discord API error: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error sending Discord notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def send_acknowledgment_notification(self, alert: Any, user_id: str) -> Dict[str, Any]:
        """Send acknowledgment notification"""
        try:
            # Create acknowledgment message
            message = f"Alert '{alert.title}' has been acknowledged by user {user_id}"
            
            # Send notification to relevant channels
            result = await self._send_status_notification(alert, message, 'acknowledged')
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def send_resolution_notification(self, alert: Any, user_id: str) -> Dict[str, Any]:
        """Send resolution notification"""
        try:
            # Create resolution message
            message = f"Alert '{alert.title}' has been resolved by user {user_id}"
            
            # Send notification to relevant channels
            result = await self._send_status_notification(alert, message, 'resolved')
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending resolution notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _send_status_notification(self, alert: Any, message: str, status: str) -> Dict[str, Any]:
        """Send status change notification"""
        try:
            # For now, just send to Slack if configured
            if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
                payload = {
                    'text': message,
                    'attachments': [{
                        'color': '#00FF00' if status == 'resolved' else '#FFFF00',
                        'title': f"Alert {status.capitalize()}",
                        'fields': [
                            {'title': 'Alert ID', 'value': alert.id, 'short': True},
                            {'title': 'Severity', 'value': alert.severity.upper(), 'short': True}
                        ]
                    }]
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(settings.SLACK_WEBHOOK_URL, json=payload) as response:
                        if response.status == 200:
                            return {'success': True, 'channel': 'slack'}
                        else:
                            return {'success': False, 'error': 'Slack API error'}
            
            return {'success': True, 'message': 'No notification channels configured'}
            
        except Exception as e:
            logger.error(f"Error sending status notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def process_metric_alert(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process metric data for alert generation"""
        try:
            triggered_alerts = []
            
            # Get alert rules for this metric
            rules = await self._get_alert_rules(metric_data['metric_name'])
            
            for rule in rules:
                # Check if rule conditions are met
                if await self._evaluate_rule(rule, metric_data):
                    # Check cooldown period
                    if await self._is_in_cooldown(rule, metric_data):
                        continue
                    
                    # Create alert data
                    alert_data = {
                        'rule_id': rule['id'],
                        'title': rule['name'],
                        'description': f"Metric {metric_data['metric_name']} exceeded threshold",
                        'severity': rule['severity'],
                        'metric_name': metric_data['metric_name'],
                        'metric_value': metric_data['metric_value'],
                        'threshold': rule['threshold'],
                        'operator': rule['operator'],
                        'container_id': metric_data.get('container_id'),
                        'service_id': metric_data.get('service_id'),
                        'tags': metric_data.get('tags', {}),
                        'metadata': {
                            'metric_timestamp': metric_data.get('timestamp'),
                            'rule_triggered': True
                        }
                    }
                    
                    triggered_alerts.append(alert_data)
                    
                    # Set cooldown
                    await self._set_rule_cooldown(rule, metric_data)
            
            return {
                'triggered_alerts': triggered_alerts,
                'rules_evaluated': len(rules),
                'alerts_triggered': len(triggered_alerts)
            }
            
        except Exception as e:
            logger.error(f"Error processing metric alert: {str(e)}")
            raise AlertServiceError(f"Failed to process metric alert: {str(e)}")
    
    async def _get_alert_rules(self, metric_name: str) -> List[Dict[str, Any]]:
        """Get alert rules for metric"""
        # This would typically query the database
        # For now, return sample rules
        return [
            {
                'id': 'cpu_high',
                'name': 'High CPU Usage',
                'metric_name': 'cpu_usage',
                'operator': 'gt',
                'threshold': 80,
                'severity': AlertSeverity.HIGH.value
            },
            {
                'id': 'memory_high',
                'name': 'High Memory Usage',
                'metric_name': 'memory_usage',
                'operator': 'gt',
                'threshold': 90,
                'severity': AlertSeverity.CRITICAL.value
            }
        ]
    
    async def _evaluate_rule(self, rule: Dict[str, Any], metric_data: Dict[str, Any]) -> bool:
        """Evaluate if rule conditions are met"""
        try:
            metric_value = float(metric_data['metric_value'])
            threshold = float(rule['threshold'])
            operator = rule['operator']
            
            if operator == 'gt':
                return metric_value > threshold
            elif operator == 'lt':
                return metric_value < threshold
            elif operator == 'gte':
                return metric_value >= threshold
            elif operator == 'lte':
                return metric_value <= threshold
            elif operator == 'eq':
                return metric_value == threshold
            elif operator == 'ne':
                return metric_value != threshold
            else:
                return False
                
        except (ValueError, TypeError):
            return False
    
    async def _is_in_cooldown(self, rule: Dict[str, Any], metric_data: Dict[str, Any]) -> bool:
        """Check if rule is in cooldown period"""
        try:
            cooldown_key = f"rule_cooldown:{rule['id']}:{metric_data.get('container_id', 'global')}"
            
            cached_cooldown = await redis_client.get(cooldown_key)
            return cached_cooldown is not None
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {str(e)}")
            return False
    
    async def _set_rule_cooldown(self, rule: Dict[str, Any], metric_data: Dict[str, Any]):
        """Set rule cooldown period"""
        try:
            cooldown_key = f"rule_cooldown:{rule['id']}:{metric_data.get('container_id', 'global')}"
            cooldown_period = self.cooldown_periods.get(rule['severity'], 300)
            
            await redis_client.setex(cooldown_key, cooldown_period, "1")
            
        except Exception as e:
            logger.error(f"Error setting cooldown: {str(e)}")
    
    async def get_alert_service_stats(self) -> Dict[str, Any]:
        """Get alert service statistics"""
        try:
            return {
                'notification_channels': len(self.notification_channels),
                'cache_ttl': self.alert_cache_ttl,
                'duplicate_window': self.duplicate_window,
                'cooldown_periods': self.cooldown_periods
            }
            
        except Exception as e:
            logger.error(f"Error getting service stats: {str(e)}")
            return {}
    
    async def calculate_trend_metrics(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate trend metrics"""
        try:
            daily_trends = trends.get('daily_trends', {})
            
            if not daily_trends:
                return {}
            
            # Calculate trend metrics
            values = list(daily_trends.values())
            
            total_alerts = sum(values)
            avg_daily = total_alerts / len(values) if values else 0
            max_daily = max(values) if values else 0
            min_daily = min(values) if values else 0
            
            # Calculate trend direction
            if len(values) >= 2:
                recent_avg = sum(values[-3:]) / min(3, len(values))
                older_avg = sum(values[:-3]) / max(1, len(values) - 3) if len(values) > 3 else recent_avg
                
                if recent_avg > older_avg * 1.1:
                    trend_direction = 'increasing'
                elif recent_avg < older_avg * 0.9:
                    trend_direction = 'decreasing'
                else:
                    trend_direction = 'stable'
            else:
                trend_direction = 'insufficient_data'
            
            return {
                'total_alerts': total_alerts,
                'avg_daily': avg_daily,
                'max_daily': max_daily,
                'min_daily': min_daily,
                'trend_direction': trend_direction
            }
            
        except Exception as e:
            logger.error(f"Error calculating trend metrics: {str(e)}")
            return {}
    
    async def get_critical_alert_metrics(self, critical_alerts: List[Any]) -> Dict[str, Any]:
        """Get metrics for critical alerts"""
        try:
            if not critical_alerts:
                return {
                    'count': 0,
                    'avg_age': 0,
                    'oldest_age': 0,
                    'newest_age': 0
                }
            
            now = datetime.utcnow()
            ages = [(now - alert.created_at).total_seconds() for alert in critical_alerts]
            
            return {
                'count': len(critical_alerts),
                'avg_age': sum(ages) / len(ages),
                'oldest_age': max(ages),
                'newest_age': min(ages)
            }
            
        except Exception as e:
            logger.error(f"Error getting critical alert metrics: {str(e)}")
            return {}
    
    async def test_notifications(self) -> Dict[str, Any]:
        """Test notification system"""
        try:
            # Test basic notification functionality
            test_alert = type('TestAlert', (), {
                'id': 'test-alert-id',
                'title': 'Test Alert',
                'description': 'Test notification system',
                'severity': AlertSeverity.LOW.value,
                'status': AlertStatus.ACTIVE.value,
                'metric_name': 'test_metric',
                'metric_value': 100,
                'threshold': 50,
                'container_id': None,
                'service_id': None,
                'created_at': datetime.utcnow(),
                'tags': {},
                'metadata': {}
            })()
            
            # Test notification channels
            test_results = {}
            
            # Test email if configured
            if hasattr(settings, 'SMTP_SERVER') and settings.SMTP_SERVER:
                email_channel = {
                    'type': 'email',
                    'config': {'recipient': settings.ALERT_EMAIL}
                }
                test_results['email'] = await self._send_email_notification(email_channel, test_alert)
            
            # Test Slack if configured
            if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
                slack_channel = {
                    'type': 'slack',
                    'config': {'webhook_url': settings.SLACK_WEBHOOK_URL}
                }
                test_results['slack'] = await self._send_slack_notification(slack_channel, test_alert)
            
            success = all(result.get('success', False) for result in test_results.values())
            
            return {
                'success': success,
                'test_results': test_results,
                'tested_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error testing notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'tested_at': datetime.utcnow().isoformat()
            }
    
    async def test_alert_processing(self) -> Dict[str, Any]:
        """Test alert processing functionality"""
        try:
            # Test metric processing
            test_metric = {
                'metric_name': 'test_cpu_usage',
                'metric_value': 95,
                'timestamp': datetime.utcnow().isoformat(),
                'container_id': 'test-container',
                'tags': {'test': True}
            }
            
            result = await self.process_metric_alert(test_metric)
            
            return {
                'success': True,
                'metric_processed': True,
                'rules_evaluated': result['rules_evaluated'],
                'alerts_triggered': result['alerts_triggered']
            }
            
        except Exception as e:
            logger.error(f"Error testing alert processing: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
