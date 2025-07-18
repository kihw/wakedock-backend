#!/usr/bin/env python3
"""
Test script to verify database connectivity and import functionality
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_db_import():
    """Test database and FastAPI app imports"""
    try:
        print("1. Testing core database import...")
        from wakedock.core.database import get_db_session
        print("✅ get_db_session imported successfully!")
        
        print("2. Testing dashboard API import...")
        from wakedock.api.routes.dashboard_api import router as dashboard_router
        print("✅ Dashboard API router imported successfully!")
        
        print("3. Testing full app import...")
        from wakedock.api.app import create_app
        print("✅ App imported successfully!")
        
        print("4. Testing app creation...")
        # Import required services
        from wakedock.core.orchestrator import DockerOrchestrator
        from wakedock.core.monitoring import MonitoringService
        from wakedock.core.advanced_analytics import AdvancedAnalyticsService
        from wakedock.core.alerts_service import AlertsService
        
        # Create services
        orchestrator = DockerOrchestrator()
        monitoring_service = MonitoringService()
        analytics_service = AdvancedAnalyticsService(
            metrics_collector=None,
            storage_path="./data/analytics"
        )
        alerts_service = AlertsService(
            metrics_collector=None,
            storage_path="./data/alerts"
        )
        
        # Create app
        app = create_app(orchestrator, monitoring_service, analytics_service, alerts_service)
        print("✅ App created successfully!")
        
        print("5. Testing main application creation...")
        from wakedock.main import create_application
        test_app = create_application()
        print("✅ Main application created successfully!")
        
        print("\n🎉 All tests passed! FastAPI app is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_db_import()
    sys.exit(0 if success else 1)
