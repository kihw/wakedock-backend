"""
Analytics Controller - Business logic for metrics, analytics and reporting
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import json

from wakedock.repositories.analytics_repository import (
    AnalyticsRepository, MetricType, AggregationType, TimeGranularity
)
from wakedock.validators.analytics_validator import AnalyticsValidator
from wakedock.services.analytics_service import AnalyticsService
from wakedock.core.exceptions import (
    AnalyticsError, ValidationError, MetricNotFoundError
)

import logging
logger = logging.getLogger(__name__)


class AnalyticsController:
    """Controller for analytics business logic"""
    
    def __init__(self, analytics_repository: AnalyticsRepository, 
                 analytics_validator: AnalyticsValidator, 
                 analytics_service: AnalyticsService):
        self.analytics_repository = analytics_repository
        self.analytics_validator = analytics_validator
        self.analytics_service = analytics_service
    
    async def get_all_metrics(self, limit: int = 50, offset: int = 0, 
                            metric_type: str = None) -> Dict[str, Any]:
        """Get all metrics with optional filtering"""
        try:
            # Validate parameters
            if limit <= 0 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Validate metric type
            if metric_type:
                await self.analytics_validator.validate_metric_type(metric_type)
                metric_type_enum = MetricType(metric_type)
            else:
                metric_type_enum = None
            
            # Get metrics
            if metric_type_enum:
                metrics = await self.analytics_repository.get_metrics_by_type(metric_type_enum)
            else:
                # Get top metrics by activity
                top_metrics = await self.analytics_repository.get_top_metrics(limit=limit)
                metrics = [item['metric'] for item in top_metrics]
            
            # Apply pagination
            paginated_metrics = metrics[offset:offset + limit]
            
            # Get additional metadata for each metric
            enriched_metrics = []
            for metric in paginated_metrics:
                metric_health = await self.analytics_repository.get_metric_health(metric.id)
                enriched_metric = {
                    'metric': metric,
                    'health': metric_health
                }
                enriched_metrics.append(enriched_metric)
            
            return {
                'metrics': enriched_metrics,
                'total_count': len(metrics),
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(paginated_metrics) < len(metrics),
                'metric_type_filter': metric_type
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            raise AnalyticsError(f"Failed to get metrics: {str(e)}")
    
    async def get_metric_by_id(self, metric_id: str) -> Dict[str, Any]:
        """Get metric by ID with detailed information"""
        try:
            # Validate metric ID
            await self.analytics_validator.validate_metric_id(metric_id)
            
            # Get metric
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Get metric health
            health = await self.analytics_repository.get_metric_health(metric_id)
            
            # Get recent statistics (last 24 hours)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            stats = await self.analytics_repository.get_metric_statistics(
                metric_id, start_time, end_time
            )
            
            # Get trends
            trends = await self.analytics_repository.get_metric_trends(metric_id, days=7)
            
            return {
                'metric': metric,
                'health': health,
                'statistics': stats,
                'trends': trends,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting metric by ID: {str(e)}")
            raise AnalyticsError(f"Failed to get metric: {str(e)}")
    
    async def create_metric(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new metric"""
        try:
            # Validate metric data
            await self.analytics_validator.validate_metric_creation(metric_data)
            
            # Check if metric already exists
            existing_metrics = await self.analytics_repository.get_metrics_by_name(
                metric_data['name']
            )
            if existing_metrics:
                raise ValidationError(f"Metric with name '{metric_data['name']}' already exists")
            
            # Generate metric ID
            metric_id = str(uuid4())
            metric_data['id'] = metric_id
            
            # Create metric
            metric = await self.analytics_repository.create_metric(metric_data)
            
            # Initialize metric in analytics service
            await self.analytics_service.initialize_metric(metric)
            
            logger.info(f"Metric created successfully: {metric.name}")
            
            return {
                'metric': metric,
                'created': True,
                'initialized': True
            }
            
        except Exception as e:
            logger.error(f"Error creating metric: {str(e)}")
            raise AnalyticsError(f"Failed to create metric: {str(e)}")
    
    async def store_metric_data(self, metric_id: str, value: float, 
                              timestamp: datetime = None, 
                              labels: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store metric data point"""
        try:
            # Validate metric ID
            await self.analytics_validator.validate_metric_id(metric_id)
            
            # Validate metric value
            await self.analytics_validator.validate_metric_value(value)
            
            # Validate timestamp
            if timestamp:
                await self.analytics_validator.validate_timestamp(timestamp)
            
            # Validate labels
            if labels:
                await self.analytics_validator.validate_labels(labels)
            
            # Check if metric exists
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Store data point
            data_point = await self.analytics_repository.store_metric_data(
                metric_id, value, timestamp, labels
            )
            
            # Process data point through analytics service
            await self.analytics_service.process_metric_data(metric, data_point)
            
            return {
                'data_point': data_point,
                'stored': True,
                'processed': True
            }
            
        except Exception as e:
            logger.error(f"Error storing metric data: {str(e)}")
            raise AnalyticsError(f"Failed to store metric data: {str(e)}")
    
    async def get_metric_data(self, metric_id: str, start_time: datetime, 
                            end_time: datetime, limit: int = 1000) -> Dict[str, Any]:
        """Get metric data points"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_metric_id(metric_id)
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            if limit <= 0 or limit > 10000:
                raise ValidationError("Limit must be between 1 and 10000")
            
            # Get metric
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Get data points
            data_points = await self.analytics_repository.get_metric_data(
                metric_id, start_time, end_time, limit
            )
            
            # Get statistics for the time range
            stats = await self.analytics_repository.get_metric_statistics(
                metric_id, start_time, end_time
            )
            
            return {
                'metric': metric,
                'data_points': data_points,
                'statistics': stats,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                },
                'count': len(data_points),
                'limit': limit
            }
            
        except Exception as e:
            logger.error(f"Error getting metric data: {str(e)}")
            raise AnalyticsError(f"Failed to get metric data: {str(e)}")
    
    async def get_aggregated_metrics(self, metric_id: str, aggregation: str, 
                                   granularity: str, start_time: datetime, 
                                   end_time: datetime) -> Dict[str, Any]:
        """Get aggregated metric data"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_metric_id(metric_id)
            await self.analytics_validator.validate_aggregation_type(aggregation)
            await self.analytics_validator.validate_granularity(granularity)
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            # Convert to enums
            aggregation_enum = AggregationType(aggregation)
            granularity_enum = TimeGranularity(granularity)
            
            # Get metric
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Get aggregated data
            aggregated_data = await self.analytics_repository.get_aggregated_metrics(
                metric_id, aggregation_enum, granularity_enum, start_time, end_time
            )
            
            # Calculate additional metrics
            analysis = await self.analytics_service.analyze_aggregated_data(
                aggregated_data, aggregation_enum, granularity_enum
            )
            
            return {
                'metric': metric,
                'aggregated_data': aggregated_data,
                'aggregation': aggregation,
                'granularity': granularity,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                },
                'analysis': analysis,
                'data_points': len(aggregated_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {str(e)}")
            raise AnalyticsError(f"Failed to get aggregated metrics: {str(e)}")
    
    async def search_metrics(self, query: str, metric_type: str = None, 
                           limit: int = 50) -> Dict[str, Any]:
        """Search metrics"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_search_query(query)
            
            if limit <= 0 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Validate metric type
            metric_type_enum = None
            if metric_type:
                await self.analytics_validator.validate_metric_type(metric_type)
                metric_type_enum = MetricType(metric_type)
            
            # Search metrics
            metrics = await self.analytics_repository.search_metrics(
                query, metric_type_enum, limit
            )
            
            # Enrich results with health information
            enriched_metrics = []
            for metric in metrics:
                health = await self.analytics_repository.get_metric_health(metric.id)
                enriched_metrics.append({
                    'metric': metric,
                    'health': health
                })
            
            return {
                'metrics': enriched_metrics,
                'query': query,
                'metric_type_filter': metric_type,
                'total_results': len(metrics),
                'limit': limit
            }
            
        except Exception as e:
            logger.error(f"Error searching metrics: {str(e)}")
            raise AnalyticsError(f"Failed to search metrics: {str(e)}")
    
    async def get_container_analytics(self, container_id: str, 
                                    start_time: datetime, 
                                    end_time: datetime) -> Dict[str, Any]:
        """Get comprehensive analytics for container"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_container_id(container_id)
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            # Get container metrics
            container_metrics = await self.analytics_repository.get_container_metrics(
                container_id, start_time, end_time
            )
            
            # Process metrics through analytics service
            analytics_data = await self.analytics_service.process_container_analytics(
                container_id, container_metrics, start_time, end_time
            )
            
            return {
                'container_id': container_id,
                'metrics': container_metrics,
                'analytics': analytics_data,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting container analytics: {str(e)}")
            raise AnalyticsError(f"Failed to get container analytics: {str(e)}")
    
    async def get_service_analytics(self, service_id: str, 
                                  start_time: datetime, 
                                  end_time: datetime) -> Dict[str, Any]:
        """Get comprehensive analytics for service"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_service_id(service_id)
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            # Get service metrics
            service_metrics = await self.analytics_repository.get_service_metrics(
                service_id, start_time, end_time
            )
            
            # Process metrics through analytics service
            analytics_data = await self.analytics_service.process_service_analytics(
                service_id, service_metrics, start_time, end_time
            )
            
            return {
                'service_id': service_id,
                'metrics': service_metrics,
                'analytics': analytics_data,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting service analytics: {str(e)}")
            raise AnalyticsError(f"Failed to get service analytics: {str(e)}")
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Get system-wide analytics overview"""
        try:
            # Get system metrics overview
            system_metrics = await self.analytics_repository.get_system_metrics_overview()
            
            # Get top metrics
            top_metrics = await self.analytics_repository.get_top_metrics(limit=5)
            
            # Get system health from analytics service
            system_health = await self.analytics_service.get_system_health()
            
            # Get performance metrics
            performance_metrics = await self.analytics_service.get_performance_metrics()
            
            return {
                'system_metrics': system_metrics,
                'top_metrics': top_metrics,
                'system_health': system_health,
                'performance_metrics': performance_metrics,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system overview: {str(e)}")
            raise AnalyticsError(f"Failed to get system overview: {str(e)}")
    
    async def create_custom_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create custom analytics report"""
        try:
            # Validate report configuration
            await self.analytics_validator.validate_report_config(report_config)
            
            # Generate report through analytics service
            report_data = await self.analytics_service.generate_custom_report(report_config)
            
            return {
                'report': report_data,
                'config': report_config,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating custom report: {str(e)}")
            raise AnalyticsError(f"Failed to create custom report: {str(e)}")
    
    async def get_metric_correlations(self, metric_ids: List[str], 
                                    start_time: datetime, 
                                    end_time: datetime) -> Dict[str, Any]:
        """Get correlations between metrics"""
        try:
            # Validate parameters
            if not metric_ids or len(metric_ids) < 2:
                raise ValidationError("At least 2 metrics required for correlation")
            
            if len(metric_ids) > 10:
                raise ValidationError("Maximum 10 metrics allowed for correlation")
            
            for metric_id in metric_ids:
                await self.analytics_validator.validate_metric_id(metric_id)
            
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            # Get correlation analysis
            correlations = await self.analytics_service.calculate_metric_correlations(
                metric_ids, start_time, end_time
            )
            
            return {
                'metric_ids': metric_ids,
                'correlations': correlations,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting metric correlations: {str(e)}")
            raise AnalyticsError(f"Failed to get metric correlations: {str(e)}")
    
    async def get_anomaly_detection(self, metric_id: str, 
                                  start_time: datetime, 
                                  end_time: datetime) -> Dict[str, Any]:
        """Get anomaly detection results for metric"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_metric_id(metric_id)
            await self.analytics_validator.validate_time_range(start_time, end_time)
            
            # Get metric
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Run anomaly detection
            anomalies = await self.analytics_service.detect_anomalies(
                metric_id, start_time, end_time
            )
            
            return {
                'metric': metric,
                'anomalies': anomalies,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting anomaly detection: {str(e)}")
            raise AnalyticsError(f"Failed to get anomaly detection: {str(e)}")
    
    async def get_forecasting(self, metric_id: str, forecast_hours: int = 24) -> Dict[str, Any]:
        """Get metric forecasting"""
        try:
            # Validate parameters
            await self.analytics_validator.validate_metric_id(metric_id)
            
            if forecast_hours <= 0 or forecast_hours > 168:  # Max 1 week
                raise ValidationError("Forecast hours must be between 1 and 168")
            
            # Get metric
            metric = await self.analytics_repository.get_metric_by_id(metric_id)
            if not metric:
                raise MetricNotFoundError(f"Metric not found: {metric_id}")
            
            # Generate forecast
            forecast = await self.analytics_service.generate_forecast(
                metric_id, forecast_hours
            )
            
            return {
                'metric': metric,
                'forecast': forecast,
                'forecast_hours': forecast_hours
            }
            
        except Exception as e:
            logger.error(f"Error getting forecasting: {str(e)}")
            raise AnalyticsError(f"Failed to get forecasting: {str(e)}")
    
    async def cleanup_old_data(self, days: int = 90) -> Dict[str, Any]:
        """Cleanup old analytics data"""
        try:
            # Validate days parameter
            if days <= 0:
                raise ValidationError("Days must be positive")
            
            # Cleanup old data
            cleaned_count = await self.analytics_repository.cleanup_old_metric_data(days)
            
            logger.info(f"Cleaned up {cleaned_count} old data points (older than {days} days)")
            
            return {
                'cleaned_count': cleaned_count,
                'days': days,
                'cleaned_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}")
            raise AnalyticsError(f"Failed to cleanup old data: {str(e)}")
    
    async def export_analytics_data(self, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """Export analytics data"""
        try:
            # Validate export configuration
            await self.analytics_validator.validate_export_config(export_config)
            
            # Export data through analytics service
            export_data = await self.analytics_service.export_data(export_config)
            
            return {
                'export_data': export_data,
                'config': export_config,
                'exported_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting analytics data: {str(e)}")
            raise AnalyticsError(f"Failed to export analytics data: {str(e)}")
    
    async def get_analytics_health(self) -> Dict[str, Any]:
        """Get analytics system health"""
        try:
            # Get system overview
            system_overview = await self.analytics_repository.get_system_metrics_overview()
            
            # Get service health
            service_health = await self.analytics_service.get_service_health()
            
            # Calculate overall health score
            health_score = await self._calculate_analytics_health_score(
                system_overview, service_health
            )
            
            return {
                'health_score': health_score,
                'system_overview': system_overview,
                'service_health': service_health,
                'status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 50 else 'unhealthy',
                'checked_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics health: {str(e)}")
            raise AnalyticsError(f"Failed to get analytics health: {str(e)}")
    
    async def _calculate_analytics_health_score(self, system_overview: Dict[str, Any], 
                                              service_health: Dict[str, Any]) -> int:
        """Calculate overall analytics health score"""
        try:
            score = 0
            
            # Data ingestion rate (40% of score)
            ingestion_rate = system_overview.get('data_ingestion_rate', 0)
            if ingestion_rate > 100:
                score += 40
            elif ingestion_rate > 50:
                score += 30
            elif ingestion_rate > 10:
                score += 20
            else:
                score += 10
            
            # Service health (30% of score)
            service_score = service_health.get('score', 0)
            score += int(service_score * 0.3)
            
            # Recent data availability (30% of score)
            recent_data = system_overview.get('recent_data_points', 0)
            if recent_data > 1000:
                score += 30
            elif recent_data > 500:
                score += 25
            elif recent_data > 100:
                score += 20
            else:
                score += 10
            
            return min(100, score)
            
        except Exception as e:
            logger.error(f"Error calculating health score: {str(e)}")
            return 0
