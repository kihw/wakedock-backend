"""
Analytics Repository - Data access layer for metrics, statistics and analytics
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text, case
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from enum import Enum
import json

from wakedock.models.analytics_models import (
    Metric, MetricData, Dashboard, Widget, Report, 
    MetricStatistics, Correlation, Anomaly, Forecast, Export, Alert, AlertIncident
)
from wakedock.core.database import AsyncSessionLocal
from wakedock.core.exceptions import DatabaseError, AnalyticsError

import logging
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AggregationType(Enum):
    """Aggregation types"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"


class TimeGranularity(Enum):
    """Time granularity for aggregations"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalyticsRepository:
    """Repository for analytics data access"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_metric_by_id(self, metric_id: str) -> Optional[Metric]:
        """Get metric by ID"""
        try:
            query = select(Metric).where(Metric.id == metric_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting metric by ID: {str(e)}")
            raise DatabaseError(f"Failed to get metric: {str(e)}")
    
    async def get_metrics_by_name(self, metric_name: str) -> List[Metric]:
        """Get metrics by name"""
        try:
            query = select(Metric).where(Metric.name == metric_name)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting metrics by name: {str(e)}")
            raise DatabaseError(f"Failed to get metrics: {str(e)}")
    
    async def get_metrics_by_type(self, metric_type: MetricType) -> List[Metric]:
        """Get metrics by type"""
        try:
            query = select(Metric).where(Metric.type == metric_type.value)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting metrics by type: {str(e)}")
            raise DatabaseError(f"Failed to get metrics: {str(e)}")
    
    async def create_metric(self, metric_data: Dict[str, Any]) -> Metric:
        """Create new metric"""
        try:
            metric = Metric(
                id=metric_data.get('id'),
                name=metric_data.get('name'),
                type=metric_data.get('type', MetricType.GAUGE.value),
                description=metric_data.get('description'),
                unit=metric_data.get('unit'),
                labels=metric_data.get('labels', {}),
                metadata=metric_data.get('metadata', {}),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.session.add(metric)
            await self.session.commit()
            await self.session.refresh(metric)
            
            logger.info(f"Created metric: {metric.name}")
            return metric
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating metric: {str(e)}")
            raise DatabaseError(f"Failed to create metric: {str(e)}")
    
    async def store_metric_data(self, metric_id: str, value: float, timestamp: datetime = None, labels: Dict[str, Any] = None) -> MetricData:
        """Store metric data point"""
        try:
            metric_data = MetricData(
                metric_id=metric_id,
                value=value,
                timestamp=timestamp or datetime.utcnow(),
                labels=labels or {},
                created_at=datetime.utcnow()
            )
            
            self.session.add(metric_data)
            await self.session.commit()
            await self.session.refresh(metric_data)
            
            return metric_data
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error storing metric data: {str(e)}")
            raise DatabaseError(f"Failed to store metric data: {str(e)}")
    
    async def get_metric_data(self, metric_id: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[MetricData]:
        """Get metric data points in time range"""
        try:
            query = (
                select(MetricData)
                .where(and_(
                    MetricData.metric_id == metric_id,
                    MetricData.timestamp >= start_time,
                    MetricData.timestamp <= end_time
                ))
                .order_by(MetricData.timestamp)
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting metric data: {str(e)}")
            raise DatabaseError(f"Failed to get metric data: {str(e)}")
    
    async def get_aggregated_metrics(self, metric_id: str, aggregation: AggregationType, 
                                   granularity: TimeGranularity, start_time: datetime, 
                                   end_time: datetime) -> List[Dict[str, Any]]:
        """Get aggregated metric data"""
        try:
            # Build time truncation expression based on granularity
            time_trunc_expr = self._get_time_truncation_expr(granularity)
            
            # Build aggregation expression
            agg_expr = self._get_aggregation_expr(aggregation)
            
            query = (
                select(
                    time_trunc_expr.label('time_bucket'),
                    agg_expr.label('value')
                )
                .select_from(MetricData)
                .where(and_(
                    MetricData.metric_id == metric_id,
                    MetricData.timestamp >= start_time,
                    MetricData.timestamp <= end_time
                ))
                .group_by(time_trunc_expr)
                .order_by(time_trunc_expr)
            )
            
            result = await self.session.execute(query)
            
            return [
                {
                    'timestamp': row.time_bucket,
                    'value': float(row.value) if row.value is not None else 0.0
                }
                for row in result.fetchall()
            ]
            
        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {str(e)}")
            raise DatabaseError(f"Failed to get aggregated metrics: {str(e)}")
    
    def _get_time_truncation_expr(self, granularity: TimeGranularity):
        """Get time truncation expression for SQL"""
        if granularity == TimeGranularity.MINUTE:
            return func.date_trunc('minute', MetricData.timestamp)
        elif granularity == TimeGranularity.HOUR:
            return func.date_trunc('hour', MetricData.timestamp)
        elif granularity == TimeGranularity.DAY:
            return func.date_trunc('day', MetricData.timestamp)
        elif granularity == TimeGranularity.WEEK:
            return func.date_trunc('week', MetricData.timestamp)
        elif granularity == TimeGranularity.MONTH:
            return func.date_trunc('month', MetricData.timestamp)
        else:
            return func.date_trunc('hour', MetricData.timestamp)
    
    def _get_aggregation_expr(self, aggregation: AggregationType):
        """Get aggregation expression for SQL"""
        if aggregation == AggregationType.SUM:
            return func.sum(MetricData.value)
        elif aggregation == AggregationType.AVG:
            return func.avg(MetricData.value)
        elif aggregation == AggregationType.MIN:
            return func.min(MetricData.value)
        elif aggregation == AggregationType.MAX:
            return func.max(MetricData.value)
        elif aggregation == AggregationType.COUNT:
            return func.count(MetricData.value)
        elif aggregation == AggregationType.PERCENTILE:
            return func.percentile_cont(0.95).within_group(MetricData.value)
        else:
            return func.avg(MetricData.value)
    
    async def get_metric_statistics(self, metric_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get comprehensive metric statistics"""
        try:
            query = (
                select(
                    func.count(MetricData.value).label('count'),
                    func.avg(MetricData.value).label('avg'),
                    func.min(MetricData.value).label('min'),
                    func.max(MetricData.value).label('max'),
                    func.sum(MetricData.value).label('sum'),
                    func.stddev(MetricData.value).label('stddev')
                )
                .select_from(MetricData)
                .where(and_(
                    MetricData.metric_id == metric_id,
                    MetricData.timestamp >= start_time,
                    MetricData.timestamp <= end_time
                ))
            )
            
            result = await self.session.execute(query)
            row = result.fetchone()
            
            if not row:
                return {
                    'count': 0,
                    'avg': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                    'sum': 0.0,
                    'stddev': 0.0
                }
            
            return {
                'count': row.count or 0,
                'avg': float(row.avg) if row.avg is not None else 0.0,
                'min': float(row.min) if row.min is not None else 0.0,
                'max': float(row.max) if row.max is not None else 0.0,
                'sum': float(row.sum) if row.sum is not None else 0.0,
                'stddev': float(row.stddev) if row.stddev is not None else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting metric statistics: {str(e)}")
            raise DatabaseError(f"Failed to get metric statistics: {str(e)}")
    
    async def get_top_metrics(self, metric_type: MetricType = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top metrics by data volume"""
        try:
            query = (
                select(
                    Metric,
                    func.count(MetricData.id).label('data_points')
                )
                .outerjoin(MetricData, Metric.id == MetricData.metric_id)
                .group_by(Metric.id)
                .order_by(desc('data_points'))
                .limit(limit)
            )
            
            if metric_type:
                query = query.where(Metric.type == metric_type.value)
            
            result = await self.session.execute(query)
            
            return [
                {
                    'metric': row.Metric,
                    'data_points': row.data_points or 0
                }
                for row in result.fetchall()
            ]
            
        except Exception as e:
            logger.error(f"Error getting top metrics: {str(e)}")
            raise DatabaseError(f"Failed to get top metrics: {str(e)}")
    
    async def search_metrics(self, query: str, metric_type: MetricType = None, limit: int = 50) -> List[Metric]:
        """Search metrics by name or description"""
        try:
            stmt = select(Metric)
            
            # Add search conditions
            if query:
                search_filter = or_(
                    Metric.name.ilike(f"%{query}%"),
                    Metric.description.ilike(f"%{query}%")
                )
                stmt = stmt.where(search_filter)
            
            # Add type filter
            if metric_type:
                stmt = stmt.where(Metric.type == metric_type.value)
            
            stmt = stmt.order_by(Metric.name).limit(limit)
            
            result = await self.session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error searching metrics: {str(e)}")
            raise DatabaseError(f"Failed to search metrics: {str(e)}")
    
    async def get_metrics_by_labels(self, labels: Dict[str, Any]) -> List[Metric]:
        """Get metrics by labels"""
        try:
            conditions = []
            for key, value in labels.items():
                # Use JSONB contains operator for PostgreSQL
                conditions.append(Metric.labels.contains({key: value}))
            
            query = select(Metric).where(and_(*conditions))
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting metrics by labels: {str(e)}")
            raise DatabaseError(f"Failed to get metrics by labels: {str(e)}")
    
    async def get_system_metrics_overview(self) -> Dict[str, Any]:
        """Get system-wide metrics overview"""
        try:
            # Total metrics
            total_metrics_query = select(func.count(Metric.id))
            total_metrics_result = await self.session.execute(total_metrics_query)
            total_metrics = total_metrics_result.scalar()
            
            # Metrics by type
            metrics_by_type_query = select(
                Metric.type,
                func.count(Metric.id).label('count')
            ).group_by(Metric.type)
            metrics_by_type_result = await self.session.execute(metrics_by_type_query)
            metrics_by_type = {row.type: row.count for row in metrics_by_type_result.fetchall()}
            
            # Total data points
            total_data_points_query = select(func.count(MetricData.id))
            total_data_points_result = await self.session.execute(total_data_points_query)
            total_data_points = total_data_points_result.scalar()
            
            # Recent data points (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_data_query = select(func.count(MetricData.id)).where(
                MetricData.timestamp >= recent_cutoff
            )
            recent_data_result = await self.session.execute(recent_data_query)
            recent_data_points = recent_data_result.scalar()
            
            # Average data points per metric
            avg_data_points = total_data_points / total_metrics if total_metrics > 0 else 0
            
            return {
                'total_metrics': total_metrics,
                'metrics_by_type': metrics_by_type,
                'total_data_points': total_data_points,
                'recent_data_points': recent_data_points,
                'average_data_points_per_metric': avg_data_points,
                'data_ingestion_rate': recent_data_points / 24 if recent_data_points > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics overview: {str(e)}")
            raise DatabaseError(f"Failed to get system metrics overview: {str(e)}")
    
    async def get_container_metrics(self, container_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get metrics for specific container"""
        try:
            # Get container-specific metrics
            container_metrics_query = (
                select(Metric)
                .where(Metric.labels.contains({'container_id': container_id}))
            )
            container_metrics_result = await self.session.execute(container_metrics_query)
            container_metrics = container_metrics_result.scalars().all()
            
            # Get data for each metric
            metrics_data = {}
            for metric in container_metrics:
                data_query = (
                    select(MetricData)
                    .where(and_(
                        MetricData.metric_id == metric.id,
                        MetricData.timestamp >= start_time,
                        MetricData.timestamp <= end_time
                    ))
                    .order_by(MetricData.timestamp)
                )
                data_result = await self.session.execute(data_query)
                data_points = data_result.scalars().all()
                
                metrics_data[metric.name] = {
                    'metric': metric,
                    'data_points': data_points,
                    'latest_value': data_points[-1].value if data_points else None,
                    'count': len(data_points)
                }
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"Error getting container metrics: {str(e)}")
            raise DatabaseError(f"Failed to get container metrics: {str(e)}")
    
    async def get_service_metrics(self, service_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get metrics for specific service"""
        try:
            # Get service-specific metrics
            service_metrics_query = (
                select(Metric)
                .where(Metric.labels.contains({'service_id': service_id}))
            )
            service_metrics_result = await self.session.execute(service_metrics_query)
            service_metrics = service_metrics_result.scalars().all()
            
            # Get aggregated data for each metric
            metrics_data = {}
            for metric in service_metrics:
                stats = await self.get_metric_statistics(metric.id, start_time, end_time)
                aggregated_data = await self.get_aggregated_metrics(
                    metric.id, AggregationType.AVG, TimeGranularity.HOUR, start_time, end_time
                )
                
                metrics_data[metric.name] = {
                    'metric': metric,
                    'statistics': stats,
                    'time_series': aggregated_data
                }
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"Error getting service metrics: {str(e)}")
            raise DatabaseError(f"Failed to get service metrics: {str(e)}")
    
    async def create_metric_aggregation(self, metric_id: str, aggregation_type: AggregationType, 
                                       granularity: TimeGranularity, start_time: datetime, 
                                       end_time: datetime) -> Dict[str, Any]:
        """Create and store metric aggregation"""
        try:
            # Calculate aggregated values
            aggregated_data = await self.get_aggregated_metrics(
                metric_id, aggregation_type, granularity, start_time, end_time
            )
            
            # Create aggregation record using MetricStatistics
            aggregation = MetricStatistics(
                metric_id=metric_id,
                period_start=start_time,
                period_end=end_time,
                granularity=granularity.value,
                count=len(aggregated_data),
                mean=sum(point['value'] for point in aggregated_data) / len(aggregated_data) if aggregated_data else 0,
                created_at=datetime.utcnow()
            )
            
            self.session.add(aggregation)
            await self.session.commit()
            await self.session.refresh(aggregation)
            
            return {
                'aggregation_id': aggregation.id,
                'metric_id': metric_id,
                'aggregation_type': aggregation_type.value,
                'granularity': granularity.value,
                'start_time': start_time,
                'end_time': end_time,
                'data': aggregated_data,
                'created_at': aggregation.created_at
            }
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating metric aggregation: {str(e)}")
            raise DatabaseError(f"Failed to create metric aggregation: {str(e)}")
    
    async def get_metric_trends(self, metric_id: str, days: int = 30) -> Dict[str, Any]:
        """Get metric trends over time"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # Get daily aggregated data
            daily_data = await self.get_aggregated_metrics(
                metric_id, AggregationType.AVG, TimeGranularity.DAY, start_time, end_time
            )
            
            if not daily_data:
                return {
                    'trend_direction': 'no_data',
                    'trend_percentage': 0.0,
                    'daily_data': [],
                    'analysis': 'Insufficient data for trend analysis'
                }
            
            # Calculate trend
            values = [point['value'] for point in daily_data]
            
            # Simple linear trend calculation
            if len(values) >= 2:
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                
                if first_avg > 0:
                    trend_percentage = ((second_avg - first_avg) / first_avg) * 100
                else:
                    trend_percentage = 0.0
                
                if trend_percentage > 5:
                    trend_direction = 'increasing'
                elif trend_percentage < -5:
                    trend_direction = 'decreasing'
                else:
                    trend_direction = 'stable'
            else:
                trend_direction = 'insufficient_data'
                trend_percentage = 0.0
            
            return {
                'trend_direction': trend_direction,
                'trend_percentage': round(trend_percentage, 2),
                'daily_data': daily_data,
                'analysis': f"Metric trend over {days} days: {trend_direction} ({trend_percentage:.2f}%)"
            }
            
        except Exception as e:
            logger.error(f"Error getting metric trends: {str(e)}")
            raise DatabaseError(f"Failed to get metric trends: {str(e)}")
    
    async def cleanup_old_metric_data(self, days: int = 90) -> int:
        """Cleanup old metric data"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old metric data
            delete_query = select(MetricData).where(MetricData.timestamp < cutoff_date)
            result = await self.session.execute(delete_query)
            data_to_delete = result.scalars().all()
            
            for data in data_to_delete:
                await self.session.delete(data)
            
            await self.session.commit()
            
            logger.info(f"Cleaned up {len(data_to_delete)} old metric data points")
            return len(data_to_delete)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cleaning up old metric data: {str(e)}")
            raise DatabaseError(f"Failed to cleanup old metric data: {str(e)}")
    
    async def get_metric_health(self, metric_id: str) -> Dict[str, Any]:
        """Get metric health status"""
        try:
            metric = await self.get_metric_by_id(metric_id)
            if not metric:
                return {'status': 'not_found', 'health_score': 0}
            
            # Get recent data (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_data_query = select(func.count(MetricData.id)).where(and_(
                MetricData.metric_id == metric_id,
                MetricData.timestamp >= recent_cutoff
            ))
            recent_data_result = await self.session.execute(recent_data_query)
            recent_count = recent_data_result.scalar()
            
            # Calculate health score
            expected_points = 24 * 60  # 1 point per minute
            health_score = min(100, (recent_count / expected_points) * 100)
            
            if health_score >= 80:
                status = 'healthy'
            elif health_score >= 50:
                status = 'degraded'
            else:
                status = 'unhealthy'
            
            return {
                'status': status,
                'health_score': round(health_score, 2),
                'recent_data_points': recent_count,
                'expected_data_points': expected_points,
                'last_updated': metric.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting metric health: {str(e)}")
            raise DatabaseError(f"Failed to get metric health: {str(e)}")
