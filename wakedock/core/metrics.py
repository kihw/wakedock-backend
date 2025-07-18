"""
Metrics module for WakeDock
"""

class MockMetricsCollector:
    """Mock metrics collector for testing"""
    def __init__(self):
        pass
    
    def collect_metrics(self):
        return {}

# Use mock for now to avoid circular dependencies
metrics_collector = MockMetricsCollector()

__all__ = ['metrics_collector']
