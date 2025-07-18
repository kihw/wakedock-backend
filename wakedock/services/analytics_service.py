"""
Analytics Service - Business logic for analytics operations
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import json
import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.repositories.analytics_repository import AnalyticsRepository, MetricType, AggregationType, TimeGranularity
from wakedock.validators.analytics_validator import AnalyticsValidator
from wakedock.core.exceptions import ValidationError, NotFoundError, ServiceError
from wakedock.core.logging import get_logger
from wakedock.core.cache import cache_service
from wakedock.core.metrics import metrics_collector

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics operations and business logic"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repository = AnalyticsRepository(db_session)
        self.validator = AnalyticsValidator()
        self.cache_ttl = 300  # 5 minutes
        self.metric_retention_days = 90
        self.max_data_points = 10000
        self.correlation_threshold = 0.3
        self.anomaly_threshold = 2.0
    
    async def create_metric(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new metric"""
        try:
            # Validate input
            await self.validator.validate_metric_creation(metric_data)
            
            # Check if metric already exists
            existing_metric = await self.repository.get_metric_by_name(metric_data['name'])
            if existing_metric:
                raise ValidationError(f"Metric with name '{metric_data['name']}' already exists")
            
            # Create metric
            metric_id = str(uuid4())
            metric = await self.repository.create_metric(
                metric_id=metric_id,
                name=metric_data['name'],
                type=metric_data['type'],
                description=metric_data.get('description'),
                unit=metric_data.get('unit'),
                labels=metric_data.get('labels', {}),
                metadata=metric_data.get('metadata', {})
            )
            
            # Clear cache
            await self._clear_metrics_cache()
            
            logger.info(f"Created metric: {metric_data['name']}")
            return {
                'metric_id': metric_id,
                'name': metric['name'],
                'type': metric['type'],
                'description': metric.get('description'),
                'unit': metric.get('unit'),
                'labels': metric.get('labels', {}),
                'metadata': metric.get('metadata', {}),
                'created_at': metric['created_at']
            }
            
        except Exception as e:
            logger.error(f"Error creating metric: {str(e)}")
            raise ServiceError(f"Failed to create metric: {str(e)}")
    
    async def record_metric_value(self, metric_id: str, value: Any, timestamp: datetime = None, 
                                 labels: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record a metric value"""
        try:
            # Validate input
            await self.validator.validate_metric_id(metric_id)
            await self.validator.validate_metric_value(value)
            
            if timestamp:
                await self.validator.validate_timestamp(timestamp)
            else:
                timestamp = datetime.utcnow()
            
            if labels:
                await self.validator.validate_labels(labels)
            
            # Check if metric exists
            metric = await self.repository.get_metric_by_id(metric_id)
            if not metric:
                raise NotFoundError(f"Metric {metric_id} not found")
            
            # Record the value
            data_point = await self.repository.record_metric_value(
                metric_id=metric_id,
                value=value,
                timestamp=timestamp,
                labels=labels or {}
            )
            
            # Update metric statistics
            await self._update_metric_statistics(metric_id, value, timestamp)
            
            # Check for anomalies
            await self._check_for_anomalies(metric_id, value, timestamp)
            
            # Clear related caches
            await self._clear_metric_cache(metric_id)
            
            logger.debug(f"Recorded value {value} for metric {metric_id}")
            return {
                'metric_id': metric_id,
                'value': value,
                'timestamp': timestamp,
                'labels': labels or {},
                'data_point_id': data_point['id']
            }
            
        except Exception as e:
            logger.error(f"Error recording metric value: {str(e)}")
            raise ServiceError(f"Failed to record metric value: {str(e)}")
    
    async def get_metric_aggregation(self, metric_id: str, aggregation_type: str,
                                   start_time: datetime, end_time: datetime,
                                   granularity: str = None) -> Dict[str, Any]:
        """Get metric aggregation for a time range"""
        try:
            # Validate input
            await self.validator.validate_metric_id(metric_id)
            await self.validator.validate_aggregation_type(aggregation_type)
            await self.validator.validate_time_range(start_time, end_time)
            
            if granularity:
                await self.validator.validate_granularity(granularity)
            else:
                granularity = self._determine_optimal_granularity(start_time, end_time)
            
            # Check cache
            cache_key = f"metric_aggregation:{metric_id}:{aggregation_type}:{granularity}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get aggregation from repository
            aggregation = await self.repository.get_aggregated_metrics(
                metric_id=metric_id,
                aggregation_type=AggregationType(aggregation_type),
                start_time=start_time,
                end_time=end_time,
                granularity=TimeGranularity(granularity)
            )
            
            # Enhance with additional statistics
            enhanced_aggregation = await self._enhance_aggregation(aggregation, metric_id, start_time, end_time)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_aggregation, self.cache_ttl)
            
            logger.debug(f"Retrieved aggregation for metric {metric_id}")
            return enhanced_aggregation
            
        except Exception as e:
            logger.error(f"Error getting metric aggregation: {str(e)}")
            raise ServiceError(f"Failed to get metric aggregation: {str(e)}")
    
    async def get_container_analytics(self, container_id: str, start_time: datetime, 
                                    end_time: datetime) -> Dict[str, Any]:
        """Get comprehensive analytics for a container"""
        try:
            # Validate input
            await self.validator.validate_container_id(container_id)
            await self.validator.validate_time_range(start_time, end_time)
            
            # Check cache
            cache_key = f"container_analytics:{container_id}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get analytics from repository
            analytics = await self.repository.get_container_analytics(
                container_id=container_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # Enhance with business logic
            enhanced_analytics = await self._enhance_container_analytics(analytics, container_id, start_time, end_time)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_analytics, self.cache_ttl)
            
            logger.debug(f"Retrieved analytics for container {container_id}")
            return enhanced_analytics
            
        except Exception as e:
            logger.error(f"Error getting container analytics: {str(e)}")
            raise ServiceError(f"Failed to get container analytics: {str(e)}")
    
    async def get_service_analytics(self, service_id: str, start_time: datetime, 
                                  end_time: datetime) -> Dict[str, Any]:
        """Get comprehensive analytics for a service"""
        try:
            # Validate input
            await self.validator.validate_service_id(service_id)
            await self.validator.validate_time_range(start_time, end_time)
            
            # Check cache
            cache_key = f"service_analytics:{service_id}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get analytics from repository
            analytics = await self.repository.get_service_analytics(
                service_id=service_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # Enhance with business logic
            enhanced_analytics = await self._enhance_service_analytics(analytics, service_id, start_time, end_time)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_analytics, self.cache_ttl)
            
            logger.debug(f"Retrieved analytics for service {service_id}")
            return enhanced_analytics
            
        except Exception as e:
            logger.error(f"Error getting service analytics: {str(e)}")
            raise ServiceError(f"Failed to get service analytics: {str(e)}")
    
    async def create_custom_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a custom analytics report"""
        try:
            # Validate input
            await self.validator.validate_report_config(report_config)
            
            # Extract configuration
            report_type = report_config['report_type']
            metric_ids = report_config['metrics']
            time_range = report_config['time_range']
            
            start_time = datetime.fromisoformat(time_range['start'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(time_range['end'].replace('Z', '+00:00'))
            
            aggregation = report_config.get('aggregation', 'avg')
            granularity = report_config.get('granularity', 'hour')
            
            # Generate report data
            report_data = await self._generate_report_data(
                report_type=report_type,
                metric_ids=metric_ids,
                start_time=start_time,
                end_time=end_time,
                aggregation=aggregation,
                granularity=granularity
            )
            
            # Create report record
            report_id = str(uuid4())
            report = await self.repository.create_report(
                report_id=report_id,
                name=report_config.get('name', f"Report_{report_id}"),
                description=report_config.get('description', ''),
                report_type=report_type,
                config=report_config,
                data=report_data
            )
            
            logger.info(f"Created custom report: {report_id}")
            return {
                'report_id': report_id,
                'name': report['name'],
                'report_type': report_type,
                'created_at': report['created_at'],
                'data': report_data
            }
            
        except Exception as e:
            logger.error(f"Error creating custom report: {str(e)}")
            raise ServiceError(f"Failed to create custom report: {str(e)}")
    
    async def get_metric_correlations(self, metric_ids: List[str], start_time: datetime, 
                                    end_time: datetime) -> Dict[str, Any]:
        """Calculate correlations between metrics"""
        try:
            # Validate input
            await self.validator.validate_correlation_request(metric_ids)
            await self.validator.validate_time_range(start_time, end_time)
            
            # Check cache
            cache_key = f"metric_correlations:{':'.join(sorted(metric_ids))}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get correlations from repository
            correlations = await self.repository.get_metric_correlations(
                metric_ids=metric_ids,
                start_time=start_time,
                end_time=end_time
            )
            
            # Enhance with business insights
            enhanced_correlations = await self._enhance_correlations(correlations, metric_ids)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_correlations, self.cache_ttl)
            
            logger.debug(f"Calculated correlations for {len(metric_ids)} metrics")
            return enhanced_correlations
            
        except Exception as e:
            logger.error(f"Error getting metric correlations: {str(e)}")
            raise ServiceError(f"Failed to get metric correlations: {str(e)}")
    
    async def get_anomaly_detection(self, metric_id: str, start_time: datetime, 
                                  end_time: datetime, sensitivity: float = 2.0) -> Dict[str, Any]:
        """Detect anomalies in metric data"""
        try:
            # Validate input
            await self.validator.validate_anomaly_detection_request(metric_id, sensitivity)
            await self.validator.validate_time_range(start_time, end_time)
            
            # Check cache
            cache_key = f"anomaly_detection:{metric_id}:{sensitivity}:{start_time.isoformat()}:{end_time.isoformat()}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get anomaly detection from repository
            anomalies = await self.repository.get_anomaly_detection(
                metric_id=metric_id,
                start_time=start_time,
                end_time=end_time,
                sensitivity=sensitivity
            )
            
            # Enhance with business context
            enhanced_anomalies = await self._enhance_anomalies(anomalies, metric_id, sensitivity)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_anomalies, self.cache_ttl)
            
            logger.debug(f"Detected {len(anomalies.get('anomalies', []))} anomalies for metric {metric_id}")
            return enhanced_anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            raise ServiceError(f"Failed to detect anomalies: {str(e)}")
    
    async def get_forecasting(self, metric_id: str, forecast_hours: int = 24) -> Dict[str, Any]:
        """Generate forecasting for a metric"""
        try:
            # Validate input
            await self.validator.validate_forecast_request(metric_id, forecast_hours)
            
            # Check cache
            cache_key = f"forecasting:{metric_id}:{forecast_hours}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get forecasting from repository
            forecast = await self.repository.get_forecasting(
                metric_id=metric_id,
                forecast_hours=forecast_hours
            )
            
            # Enhance with business insights
            enhanced_forecast = await self._enhance_forecast(forecast, metric_id, forecast_hours)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_forecast, self.cache_ttl)
            
            logger.debug(f"Generated {forecast_hours}h forecast for metric {metric_id}")
            return enhanced_forecast
            
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            raise ServiceError(f"Failed to generate forecast: {str(e)}")
    
    async def export_metrics_data(self, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """Export metrics data in specified format"""
        try:
            # Validate input
            await self.validator.validate_export_config(export_config)
            
            # Extract configuration
            format_type = export_config['format']
            metric_ids = export_config['metrics']
            time_range = export_config.get('time_range')
            
            # Get data from repository
            export_data = await self.repository.export_metrics_data(
                metric_ids=metric_ids,
                format_type=format_type,
                time_range=time_range
            )
            
            # Enhance with business context
            enhanced_export = await self._enhance_export_data(export_data, export_config)
            
            logger.info(f"Exported {len(metric_ids)} metrics in {format_type} format")
            return enhanced_export
            
        except Exception as e:
            logger.error(f"Error exporting metrics data: {str(e)}")
            raise ServiceError(f"Failed to export metrics data: {str(e)}")
    
    async def get_system_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            # Check cache
            cache_key = "system_health_metrics"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get health metrics from repository
            health_metrics = await self.repository.get_system_health_metrics()
            
            # Enhance with system-level insights
            enhanced_health = await self._enhance_system_health(health_metrics)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_health, self.cache_ttl)
            
            logger.debug("Retrieved system health metrics")
            return enhanced_health
            
        except Exception as e:
            logger.error(f"Error getting system health metrics: {str(e)}")
            raise ServiceError(f"Failed to get system health metrics: {str(e)}")
    
    async def cleanup_old_metrics(self, retention_days: int = None) -> Dict[str, Any]:
        """Clean up old metric data"""
        try:
            retention_days = retention_days or self.metric_retention_days
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Get cleanup statistics
            cleanup_stats = await self.repository.cleanup_old_metrics(cutoff_date)
            
            # Clear caches
            await self._clear_all_caches()
            
            logger.info(f"Cleaned up metrics older than {retention_days} days")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {str(e)}")
            raise ServiceError(f"Failed to clean up old metrics: {str(e)}")
    
    async def bulk_metric_operation(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform bulk operation on metrics"""
        try:
            # Validate input
            await self.validator.validate_bulk_metric_operation(operation_data)
            
            metric_ids = operation_data['metric_ids']
            operation = operation_data['operation']
            
            # Perform operation
            if operation == 'delete':
                results = await self._bulk_delete_metrics(metric_ids)
            elif operation == 'update_metadata':
                results = await self._bulk_update_metadata(metric_ids, operation_data.get('metadata', {}))
            elif operation == 'update_labels':
                results = await self._bulk_update_labels(metric_ids, operation_data.get('labels', {}))
            elif operation == 'aggregate':
                results = await self._bulk_aggregate_metrics(metric_ids, operation_data.get('aggregation_config', {}))
            else:
                raise ValidationError(f"Unsupported bulk operation: {operation}")
            
            # Clear caches
            await self._clear_all_caches()
            
            logger.info(f"Performed bulk {operation} on {len(metric_ids)} metrics")
            return results
            
        except Exception as e:
            logger.error(f"Error performing bulk operation: {str(e)}")
            raise ServiceError(f"Failed to perform bulk operation: {str(e)}")
    
    # Private helper methods
    
    def _determine_optimal_granularity(self, start_time: datetime, end_time: datetime) -> str:
        """Determine optimal granularity based on time range"""
        time_diff = end_time - start_time
        
        if time_diff.total_seconds() <= 3600:  # <= 1 hour
            return 'minute'
        elif time_diff.total_seconds() <= 86400:  # <= 1 day
            return 'hour'
        elif time_diff.days <= 30:  # <= 30 days
            return 'day'
        elif time_diff.days <= 365:  # <= 1 year
            return 'week'
        else:
            return 'month'
    
    async def _enhance_aggregation(self, aggregation: Dict[str, Any], metric_id: str, 
                                 start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Enhance aggregation with additional insights"""
        enhanced = aggregation.copy()
        
        # Add trend analysis
        if 'data_points' in aggregation and len(aggregation['data_points']) > 1:
            enhanced['trend'] = self._calculate_trend(aggregation['data_points'])
        
        # Add statistical insights
        if 'statistics' in aggregation:
            enhanced['insights'] = await self._generate_statistical_insights(aggregation['statistics'])
        
        return enhanced
    
    async def _enhance_container_analytics(self, analytics: Dict[str, Any], container_id: str, 
                                         start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Enhance container analytics with business logic"""
        enhanced = analytics.copy()
        
        # Add performance score
        enhanced['performance_score'] = await self._calculate_container_performance_score(analytics)
        
        # Add resource efficiency
        enhanced['resource_efficiency'] = await self._calculate_resource_efficiency(analytics)
        
        # Add recommendations
        enhanced['recommendations'] = await self._generate_container_recommendations(analytics)
        
        return enhanced
    
    async def _enhance_service_analytics(self, analytics: Dict[str, Any], service_id: str, 
                                       start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Enhance service analytics with business logic"""
        enhanced = analytics.copy()
        
        # Add service health score
        enhanced['health_score'] = await self._calculate_service_health_score(analytics)
        
        # Add scaling recommendations
        enhanced['scaling_recommendations'] = await self._generate_scaling_recommendations(analytics)
        
        # Add cost analysis
        enhanced['cost_analysis'] = await self._calculate_cost_analysis(analytics)
        
        return enhanced
    
    async def _generate_report_data(self, report_type: str, metric_ids: List[str], 
                                  start_time: datetime, end_time: datetime, 
                                  aggregation: str, granularity: str) -> Dict[str, Any]:
        """Generate report data based on type and parameters"""
        report_data = {
            'type': report_type,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'metrics': [],
            'summary': {}
        }
        
        # Get data for each metric
        for metric_id in metric_ids:
            metric_data = await self.get_metric_aggregation(
                metric_id=metric_id,
                aggregation_type=aggregation,
                start_time=start_time,
                end_time=end_time,
                granularity=granularity
            )
            report_data['metrics'].append(metric_data)
        
        # Generate summary based on report type
        if report_type == 'summary':
            report_data['summary'] = await self._generate_summary_report(report_data['metrics'])
        elif report_type == 'comparison':
            report_data['summary'] = await self._generate_comparison_report(report_data['metrics'])
        elif report_type == 'trend':
            report_data['summary'] = await self._generate_trend_report(report_data['metrics'])
        
        return report_data
    
    async def _enhance_correlations(self, correlations: Dict[str, Any], metric_ids: List[str]) -> Dict[str, Any]:
        """Enhance correlations with business insights"""
        enhanced = correlations.copy()
        
        # Add correlation strength interpretation
        enhanced['insights'] = []
        for correlation in correlations.get('correlations', []):
            if abs(correlation['coefficient']) > 0.7:
                enhanced['insights'].append({
                    'type': 'strong_correlation',
                    'metrics': [correlation['metric_1'], correlation['metric_2']],
                    'coefficient': correlation['coefficient'],
                    'interpretation': 'Strong correlation detected'
                })
        
        return enhanced
    
    async def _enhance_anomalies(self, anomalies: Dict[str, Any], metric_id: str, 
                               sensitivity: float) -> Dict[str, Any]:
        """Enhance anomalies with business context"""
        enhanced = anomalies.copy()
        
        # Add anomaly severity
        for anomaly in enhanced.get('anomalies', []):
            severity = abs(anomaly['deviation'])
            if severity > 3.0:
                anomaly['severity'] = 'critical'
            elif severity > 2.0:
                anomaly['severity'] = 'high'
            elif severity > 1.0:
                anomaly['severity'] = 'medium'
            else:
                anomaly['severity'] = 'low'
        
        return enhanced
    
    async def _enhance_forecast(self, forecast: Dict[str, Any], metric_id: str, 
                              forecast_hours: int) -> Dict[str, Any]:
        """Enhance forecast with business insights"""
        enhanced = forecast.copy()
        
        # Add confidence intervals
        enhanced['confidence_intervals'] = await self._calculate_confidence_intervals(forecast)
        
        # Add forecast quality score
        enhanced['quality_score'] = await self._calculate_forecast_quality(forecast)
        
        return enhanced
    
    async def _enhance_export_data(self, export_data: Dict[str, Any], 
                                 export_config: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance export data with metadata"""
        enhanced = export_data.copy()
        
        # Add export metadata
        enhanced['metadata'] = {
            'exported_at': datetime.utcnow().isoformat(),
            'format': export_config['format'],
            'metrics_count': len(export_config['metrics']),
            'data_points_count': len(export_data.get('data', [])),
            'config': export_config
        }
        
        return enhanced
    
    async def _enhance_system_health(self, health_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance system health with insights"""
        enhanced = health_metrics.copy()
        
        # Calculate overall health score
        enhanced['overall_health_score'] = await self._calculate_overall_health_score(health_metrics)
        
        # Add health recommendations
        enhanced['recommendations'] = await self._generate_health_recommendations(health_metrics)
        
        return enhanced
    
    def _calculate_trend(self, data_points: List[Dict]) -> Dict[str, Any]:
        """Calculate trend from data points"""
        if len(data_points) < 2:
            return {'direction': 'neutral', 'strength': 0.0}
        
        values = [point['value'] for point in data_points]
        x = range(len(values))
        
        # Calculate linear regression
        correlation = np.corrcoef(x, values)[0, 1] if len(values) > 1 else 0
        
        if correlation > 0.3:
            direction = 'increasing'
        elif correlation < -0.3:
            direction = 'decreasing'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'strength': abs(correlation),
            'correlation': correlation
        }
    
    async def _update_metric_statistics(self, metric_id: str, value: float, timestamp: datetime):
        """Update metric statistics"""
        try:
            # Update real-time statistics
            await self.repository.update_metric_statistics(metric_id, value, timestamp)
        except Exception as e:
            logger.error(f"Error updating metric statistics: {str(e)}")
    
    async def _check_for_anomalies(self, metric_id: str, value: float, timestamp: datetime):
        """Check for anomalies in real-time"""
        try:
            # Get recent statistics
            stats = await self.repository.get_metric_statistics(metric_id)
            if not stats:
                return
            
            # Check for anomaly
            if stats.get('stddev', 0) > 0:
                z_score = abs(value - stats['mean']) / stats['stddev']
                if z_score > self.anomaly_threshold:
                    # Log anomaly
                    logger.warning(f"Anomaly detected for metric {metric_id}: value={value}, z_score={z_score}")
                    
                    # Could trigger alert here
                    # await self.alert_service.create_anomaly_alert(metric_id, value, z_score)
        except Exception as e:
            logger.error(f"Error checking for anomalies: {str(e)}")
    
    async def _clear_metrics_cache(self):
        """Clear metrics-related cache"""
        await cache_service.delete_pattern("metric_*")
    
    async def _clear_metric_cache(self, metric_id: str):
        """Clear cache for specific metric"""
        await cache_service.delete_pattern(f"metric_*:{metric_id}:*")
    
    async def _clear_all_caches(self):
        """Clear all analytics caches"""
        await cache_service.delete_pattern("metric_*")
        await cache_service.delete_pattern("analytics_*")
        await cache_service.delete_pattern("container_analytics:*")
        await cache_service.delete_pattern("service_analytics:*")
    
    async def _bulk_delete_metrics(self, metric_ids: List[str]) -> Dict[str, Any]:
        """Bulk delete metrics"""
        deleted_count = 0
        errors = []
        
        for metric_id in metric_ids:
            try:
                await self.repository.delete_metric(metric_id)
                deleted_count += 1
            except Exception as e:
                errors.append({'metric_id': metric_id, 'error': str(e)})
        
        return {
            'deleted_count': deleted_count,
            'errors': errors,
            'total_requested': len(metric_ids)
        }
    
    async def _bulk_update_metadata(self, metric_ids: List[str], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update metadata for metrics"""
        updated_count = 0
        errors = []
        
        for metric_id in metric_ids:
            try:
                await self.repository.update_metric_metadata(metric_id, metadata)
                updated_count += 1
            except Exception as e:
                errors.append({'metric_id': metric_id, 'error': str(e)})
        
        return {
            'updated_count': updated_count,
            'errors': errors,
            'total_requested': len(metric_ids)
        }
    
    async def _bulk_update_labels(self, metric_ids: List[str], labels: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update labels for metrics"""
        updated_count = 0
        errors = []
        
        for metric_id in metric_ids:
            try:
                await self.repository.update_metric_labels(metric_id, labels)
                updated_count += 1
            except Exception as e:
                errors.append({'metric_id': metric_id, 'error': str(e)})
        
        return {
            'updated_count': updated_count,
            'errors': errors,
            'total_requested': len(metric_ids)
        }
    
    async def _bulk_aggregate_metrics(self, metric_ids: List[str], aggregation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk aggregate metrics"""
        # Implementation depends on specific aggregation requirements
        return {
            'aggregated_count': len(metric_ids),
            'config': aggregation_config
        }
    
    # Additional helper methods for business logic calculations
    
    async def _generate_statistical_insights(self, statistics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate insights from statistics"""
        insights = []
        
        if 'variance' in statistics and statistics['variance'] > 0:
            cv = statistics.get('stddev', 0) / statistics.get('mean', 1)
            if cv > 0.5:
                insights.append({
                    'type': 'high_variability',
                    'message': 'High variability detected in metric values',
                    'value': cv
                })
        
        return insights
    
    async def _calculate_container_performance_score(self, analytics: Dict[str, Any]) -> float:
        """Calculate container performance score"""
        # Simplified performance score calculation
        cpu_score = min(100, max(0, 100 - analytics.get('cpu_usage_avg', 0)))
        memory_score = min(100, max(0, 100 - analytics.get('memory_usage_avg', 0)))
        network_score = 100 - min(100, analytics.get('network_errors', 0))
        
        return (cpu_score + memory_score + network_score) / 3
    
    async def _calculate_resource_efficiency(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate resource efficiency metrics"""
        return {
            'cpu_efficiency': analytics.get('cpu_usage_avg', 0) / analytics.get('cpu_limit', 100),
            'memory_efficiency': analytics.get('memory_usage_avg', 0) / analytics.get('memory_limit', 100),
            'network_efficiency': 100 - analytics.get('network_errors', 0)
        }
    
    async def _generate_container_recommendations(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate container recommendations"""
        recommendations = []
        
        if analytics.get('cpu_usage_avg', 0) > 80:
            recommendations.append({
                'type': 'scale_up',
                'resource': 'cpu',
                'message': 'Consider increasing CPU limits'
            })
        
        if analytics.get('memory_usage_avg', 0) > 80:
            recommendations.append({
                'type': 'scale_up',
                'resource': 'memory',
                'message': 'Consider increasing memory limits'
            })
        
        return recommendations
    
    async def _calculate_service_health_score(self, analytics: Dict[str, Any]) -> float:
        """Calculate service health score"""
        error_rate = analytics.get('error_rate', 0)
        response_time = analytics.get('avg_response_time', 0)
        uptime = analytics.get('uptime_percentage', 100)
        
        health_score = (
            (100 - min(100, error_rate * 10)) * 0.4 +
            (100 - min(100, response_time / 10)) * 0.3 +
            uptime * 0.3
        )
        
        return max(0, min(100, health_score))
    
    async def _generate_scaling_recommendations(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate scaling recommendations"""
        recommendations = []
        
        if analytics.get('cpu_usage_avg', 0) > 70:
            recommendations.append({
                'type': 'horizontal_scale',
                'message': 'Consider horizontal scaling due to high CPU usage'
            })
        
        return recommendations
    
    async def _calculate_cost_analysis(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate cost analysis"""
        return {
            'estimated_cost': analytics.get('resource_usage', 0) * 0.01,  # Simplified
            'cost_per_request': analytics.get('total_cost', 0) / max(1, analytics.get('request_count', 1)),
            'optimization_potential': 'medium'
        }
    
    async def _generate_summary_report(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary report"""
        return {
            'total_metrics': len(metrics_data),
            'average_values': {
                metric['metric_id']: metric.get('statistics', {}).get('mean', 0)
                for metric in metrics_data
            }
        }
    
    async def _generate_comparison_report(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comparison report"""
        return {
            'comparisons': [
                {
                    'metric_1': metrics_data[i]['metric_id'],
                    'metric_2': metrics_data[j]['metric_id'],
                    'correlation': 0.5  # Simplified
                }
                for i in range(len(metrics_data))
                for j in range(i+1, len(metrics_data))
            ]
        }
    
    async def _generate_trend_report(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate trend report"""
        return {
            'trends': [
                {
                    'metric_id': metric['metric_id'],
                    'trend': metric.get('trend', 'neutral')
                }
                for metric in metrics_data
            ]
        }
    
    async def _calculate_confidence_intervals(self, forecast: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence intervals for forecast"""
        return {
            'confidence_95': {
                'lower': forecast.get('lower_bound', 0),
                'upper': forecast.get('upper_bound', 0)
            }
        }
    
    async def _calculate_forecast_quality(self, forecast: Dict[str, Any]) -> float:
        """Calculate forecast quality score"""
        return forecast.get('accuracy', 0.8)  # Simplified
    
    async def _calculate_overall_health_score(self, health_metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score"""
        scores = []
        
        if 'cpu_health' in health_metrics:
            scores.append(health_metrics['cpu_health'])
        
        if 'memory_health' in health_metrics:
            scores.append(health_metrics['memory_health'])
        
        if 'disk_health' in health_metrics:
            scores.append(health_metrics['disk_health'])
        
        return sum(scores) / len(scores) if scores else 0.0
    
    async def _generate_health_recommendations(self, health_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate health recommendations"""
        recommendations = []
        
        if health_metrics.get('cpu_health', 100) < 50:
            recommendations.append({
                'type': 'cpu_optimization',
                'message': 'CPU utilization is high, consider optimization'
            })
        
        if health_metrics.get('memory_health', 100) < 50:
            recommendations.append({
                'type': 'memory_optimization',
                'message': 'Memory utilization is high, consider optimization'
            })
        
        return recommendations
