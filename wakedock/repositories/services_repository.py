"""
Repository for Docker services management
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from wakedock.repositories.base_repository import BaseRepository
from wakedock.models.stack import StackInfo, StackStatus, StackType, ContainerStackInfo


class ServicesRepository(BaseRepository[StackInfo]):
    """Repository for managing Docker services/stacks"""
    
    def __init__(self, session: AsyncSession):
        # For now, we'll work with StackInfo as our service model
        super().__init__(session, StackInfo)
    
    async def get_by_name(self, name: str) -> Optional[StackInfo]:
        """Get a service by name"""
        query = select(self.model).where(self.model.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_status(self, status: StackStatus, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get services by status"""
        query = select(self.model).where(self.model.status == status).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_by_type(self, stack_type: StackType, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get services by type"""
        query = select(self.model).where(self.model.type == stack_type).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def search_by_name(self, name_pattern: str, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Search services by name pattern"""
        query = select(self.model).where(
            self.model.name.ilike(f"%{name_pattern}%")
        ).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_running_services(self, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get all running services"""
        return await self.get_by_status(StackStatus.RUNNING, skip, limit)
    
    async def get_stopped_services(self, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get all stopped services"""
        return await self.get_by_status(StackStatus.STOPPED, skip, limit)
    
    async def get_services_with_errors(self, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get services with error status"""
        return await self.get_by_status(StackStatus.ERROR, skip, limit)
    
    async def count_by_status(self, status: StackStatus) -> int:
        """Count services by status"""
        query = select(func.count(self.model.id)).where(self.model.status == status)
        result = await self.session.execute(query)
        return result.scalar()
    
    async def count_by_type(self, stack_type: StackType) -> int:
        """Count services by type"""
        query = select(func.count(self.model.id)).where(self.model.type == stack_type)
        result = await self.session.execute(query)
        return result.scalar()
    
    async def get_services_stats(self) -> Dict[str, Any]:
        """Get comprehensive services statistics"""
        stats = {}
        
        # Count by status
        for status in StackStatus:
            stats[f"count_{status.value}"] = await self.count_by_status(status)
        
        # Count by type
        for stack_type in StackType:
            stats[f"count_{stack_type.value}"] = await self.count_by_type(stack_type)
        
        # Total count
        stats["total"] = await self.count()
        
        return stats
    
    async def update_service_status(self, service_id: str, status: StackStatus) -> Optional[StackInfo]:
        """Update service status"""
        return await self.update(service_id, {"status": status})
    
    async def get_services_by_multiple_statuses(
        self, 
        statuses: List[StackStatus], 
        skip: int = 0, 
        limit: int = 100
    ) -> List[StackInfo]:
        """Get services by multiple statuses"""
        query = select(self.model).where(
            self.model.status.in_(statuses)
        ).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_services_by_multiple_types(
        self, 
        types: List[StackType], 
        skip: int = 0, 
        limit: int = 100
    ) -> List[StackInfo]:
        """Get services by multiple types"""
        query = select(self.model).where(
            self.model.type.in_(types)
        ).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def advanced_search(
        self,
        name_pattern: Optional[str] = None,
        statuses: Optional[List[StackStatus]] = None,
        types: Optional[List[StackType]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[StackInfo]:
        """Advanced search with multiple filters"""
        query = select(self.model)
        
        conditions = []
        
        if name_pattern:
            conditions.append(self.model.name.ilike(f"%{name_pattern}%"))
        
        if statuses:
            conditions.append(self.model.status.in_(statuses))
        
        if types:
            conditions.append(self.model.type.in_(types))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_services_needing_attention(self, skip: int = 0, limit: int = 100) -> List[StackInfo]:
        """Get services that need attention (error, starting, stopping)"""
        attention_statuses = [StackStatus.ERROR, StackStatus.STARTING, StackStatus.STOPPING]
        return await self.get_services_by_multiple_statuses(attention_statuses, skip, limit)
    
    async def exists_by_name(self, name: str) -> bool:
        """Check if a service exists by name"""
        query = select(func.count(self.model.id)).where(self.model.name == name)
        result = await self.session.execute(query)
        return result.scalar() > 0
    
    async def get_services_summary(self) -> Dict[str, Any]:
        """Get a summary of all services"""
        stats = await self.get_services_stats()
        
        # Get recent services (last 10)
        recent_query = select(self.model).order_by(self.model.created.desc()).limit(10)
        recent_result = await self.session.execute(recent_query)
        recent_services = recent_result.scalars().all()
        
        return {
            "statistics": stats,
            "recent_services": [
                {
                    "id": service.id,
                    "name": service.name,
                    "status": service.status,
                    "type": service.type,
                    "created": service.created.isoformat() if service.created else None
                }
                for service in recent_services
            ]
        }
