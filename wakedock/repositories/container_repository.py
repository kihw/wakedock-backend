"""
Container repository for data access - MVC Architecture
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wakedock.repositories.base_repository import BaseRepository
from wakedock.models.container import Container, ContainerLog, ContainerMetrics, ContainerNetwork
from wakedock.core.exceptions import ContainerNotFoundError, ContainerOperationError

import logging
logger = logging.getLogger(__name__)


class ContainerRepository(BaseRepository):
    """Repository for container data access operations"""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session, Container)
    
    async def get_by_container_id(self, container_id: str) -> Optional[Container]:
        """Get container by Docker container ID"""
        try:
            stmt = select(Container).where(Container.container_id == container_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting container by ID {container_id}: {str(e)}")
            return None
    
    async def get_by_name(self, name: str) -> Optional[Container]:
        """Get container by name"""
        try:
            stmt = select(Container).where(Container.name == name)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting container by name {name}: {str(e)}")
            return None
    
    async def get_by_status(self, status: str) -> List[Container]:
        """Get containers by status"""
        try:
            stmt = select(Container).where(Container.status == status)
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting containers by status {status}: {str(e)}")
            return []
    
    async def get_by_image(self, image: str) -> List[Container]:
        """Get containers by image"""
        try:
            stmt = select(Container).where(Container.image.ilike(f"%{image}%"))
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting containers by image {image}: {str(e)}")
            return []
    
    async def get_running_containers(self) -> List[Container]:
        """Get all running containers"""
        try:
            stmt = select(Container).where(Container.status == "running")
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting running containers: {str(e)}")
            return []
    
    async def get_stopped_containers(self) -> List[Container]:
        """Get all stopped containers"""
        try:
            stmt = select(Container).where(Container.status.in_(["stopped", "exited"]))
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting stopped containers: {str(e)}")
            return []
    
    async def get_containers_with_logs(self, limit: int = 10) -> List[Container]:
        """Get containers with their logs"""
        try:
            stmt = (
                select(Container)
                .options(selectinload(Container.logs))
                .limit(limit)
            )
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting containers with logs: {str(e)}")
            return []
    
    async def get_containers_with_metrics(self, limit: int = 10) -> List[Container]:
        """Get containers with their metrics"""
        try:
            stmt = (
                select(Container)
                .options(selectinload(Container.metrics))
                .limit(limit)
            )
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting containers with metrics: {str(e)}")
            return []
    
    async def search_containers(
        self,
        query: str,
        status: Optional[str] = None,
        image: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Container]:
        """Search containers with filters"""
        try:
            conditions = []
            
            # Search query
            if query:
                conditions.append(
                    or_(
                        Container.name.ilike(f"%{query}%"),
                        Container.image.ilike(f"%{query}%"),
                        Container.command.ilike(f"%{query}%")
                    )
                )
            
            # Status filter
            if status:
                conditions.append(Container.status == status)
            
            # Image filter
            if image:
                conditions.append(Container.image.ilike(f"%{image}%"))
            
            stmt = select(Container)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.limit(limit).offset(offset)
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error searching containers: {str(e)}")
            return []
    
    async def get_container_statistics(self) -> Dict[str, Any]:
        """Get container statistics"""
        try:
            # Total containers
            total_stmt = select(func.count(Container.id))
            total_result = await self.db_session.execute(total_stmt)
            total_count = total_result.scalar()
            
            # Running containers
            running_stmt = select(func.count(Container.id)).where(Container.status == "running")
            running_result = await self.db_session.execute(running_stmt)
            running_count = running_result.scalar()
            
            # Stopped containers
            stopped_stmt = select(func.count(Container.id)).where(Container.status.in_(["stopped", "exited"]))
            stopped_result = await self.db_session.execute(stopped_stmt)
            stopped_count = stopped_result.scalar()
            
            # Containers by image
            image_stmt = (
                select(Container.image, func.count(Container.id))
                .group_by(Container.image)
                .order_by(func.count(Container.id).desc())
                .limit(10)
            )
            image_result = await self.db_session.execute(image_stmt)
            image_stats = dict(image_result.fetchall())
            
            return {
                "total_containers": total_count,
                "running_containers": running_count,
                "stopped_containers": stopped_count,
                "containers_by_image": image_stats,
                "uptime_percentage": (running_count / total_count * 100) if total_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting container statistics: {str(e)}")
            return {
                "total_containers": 0,
                "running_containers": 0,
                "stopped_containers": 0,
                "containers_by_image": {},
                "uptime_percentage": 0
            }
    
    async def create_container(self, **kwargs) -> Container:
        """Create new container record"""
        try:
            container = Container(**kwargs)
            self.db_session.add(container)
            await self.db_session.commit()
            await self.db_session.refresh(container)
            
            logger.info(f"Created container record: {container.name}")
            return container
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating container: {str(e)}")
            raise ContainerOperationError(f"Failed to create container: {str(e)}")
    
    async def update_container_status(self, container_id: str, status: str) -> Optional[Container]:
        """Update container status"""
        try:
            stmt = (
                update(Container)
                .where(Container.container_id == container_id)
                .values(status=status, updated_at=datetime.utcnow())
                .returning(Container)
            )
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            container = result.scalar_one_or_none()
            if container:
                logger.info(f"Updated container {container_id} status to {status}")
            
            return container
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating container status: {str(e)}")
            raise ContainerOperationError(f"Failed to update container status: {str(e)}")
    
    async def update_container_metrics(self, container_id: str, metrics: Dict[str, Any]) -> bool:
        """Update container metrics"""
        try:
            # Get container
            container = await self.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Create metrics record
            container_metrics = ContainerMetrics(
                container_id=container.id,
                cpu_usage=metrics.get("cpu_usage", 0.0),
                memory_usage=metrics.get("memory_usage", 0),
                memory_limit=metrics.get("memory_limit", 0),
                network_rx=metrics.get("network_rx", 0),
                network_tx=metrics.get("network_tx", 0),
                disk_read=metrics.get("disk_read", 0),
                disk_write=metrics.get("disk_write", 0),
                timestamp=datetime.utcnow()
            )
            
            self.db_session.add(container_metrics)
            await self.db_session.commit()
            
            logger.debug(f"Updated metrics for container {container_id}")
            return True
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating container metrics: {str(e)}")
            return False
    
    async def add_container_log(self, container_id: str, log_data: Dict[str, Any]) -> bool:
        """Add container log entry"""
        try:
            # Get container
            container = await self.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Create log record
            container_log = ContainerLog(
                container_id=container.id,
                log_level=log_data.get("level", "INFO"),
                message=log_data.get("message", ""),
                source=log_data.get("source", "container"),
                timestamp=datetime.utcnow()
            )
            
            self.db_session.add(container_log)
            await self.db_session.commit()
            
            logger.debug(f"Added log entry for container {container_id}")
            return True
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error adding container log: {str(e)}")
            return False
    
    async def get_container_logs(
        self,
        container_id: str,
        limit: int = 100,
        level: Optional[str] = None
    ) -> List[ContainerLog]:
        """Get container logs"""
        try:
            container = await self.get_by_container_id(container_id)
            if not container:
                return []
            
            stmt = select(ContainerLog).where(ContainerLog.container_id == container.id)
            
            if level:
                stmt = stmt.where(ContainerLog.log_level == level)
            
            stmt = stmt.order_by(ContainerLog.timestamp.desc()).limit(limit)
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting container logs: {str(e)}")
            return []
    
    async def get_container_metrics_history(
        self,
        container_id: str,
        hours: int = 24
    ) -> List[ContainerMetrics]:
        """Get container metrics history"""
        try:
            container = await self.get_by_container_id(container_id)
            if not container:
                return []
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            stmt = (
                select(ContainerMetrics)
                .where(
                    and_(
                        ContainerMetrics.container_id == container.id,
                        ContainerMetrics.timestamp >= cutoff_time
                    )
                )
                .order_by(ContainerMetrics.timestamp.desc())
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting container metrics history: {str(e)}")
            return []
    
    async def cleanup_old_logs(self, days: int = 30) -> int:
        """Clean up old container logs"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            stmt = delete(ContainerLog).where(ContainerLog.timestamp < cutoff_time)
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old log entries")
            return deleted_count
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error cleaning up old logs: {str(e)}")
            return 0
    
    async def cleanup_old_metrics(self, days: int = 7) -> int:
        """Clean up old container metrics"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            stmt = delete(ContainerMetrics).where(ContainerMetrics.timestamp < cutoff_time)
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old metric entries")
            return deleted_count
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error cleaning up old metrics: {str(e)}")
            return 0
