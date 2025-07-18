"""
Pagination utilities for WakeDock
"""
from typing import Any, Dict, List


class Pagination:
    """Simple pagination helper"""
    
    def __init__(self, page: int = 1, per_page: int = 20):
        self.page = max(1, page)
        self.per_page = min(100, max(1, per_page))
    
    def paginate(self, items: List[Any]) -> Dict[str, Any]:
        """Paginate a list of items"""
        total = len(items)
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        
        return {
            "items": items[start:end],
            "page": self.page,
            "per_page": self.per_page,
            "total": total,
            "pages": (total + self.per_page - 1) // self.per_page
        }
