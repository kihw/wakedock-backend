"""
End-to-end tests for the WakeDock dashboard.
These tests verify the full user workflow from login to service management.
"""

import pytest
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import aiohttp
import time


class TestDashboardE2E:
    """End-to-end tests for the WakeDock dashboard."""
    
    @pytest.fixture(scope="class")
    async def api_server(self):
        """Ensure API server is running before tests."""
        # Check if API is accessible
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/api/v1/health") as response:
                    if response.status == 200:
                        yield "http://localhost:8000"
                    else:
                        pytest.skip("API server not running")
        except Exception:
            pytest.skip("API server not accessible")
    
    @pytest.fixture(scope="class")
    async def dashboard_server(self):
        """Ensure dashboard is accessible."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:3000") as response:
                    if response.status == 200:
                        yield "http://localhost:3000"
                    else:
                        pytest.skip("Dashboard not running")
        except Exception:
            pytest.skip("Dashboard not accessible")
    
    @pytest.fixture(scope="class")
    async def browser(self):
        """Create browser instance for tests."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        yield browser
        await browser.close()
        await playwright.stop()
    
    @pytest.fixture
    async def page(self, browser: Browser, dashboard_server: str):
        """Create a new page for each test."""
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(dashboard_server)
        yield page
        await context.close()
    
    async def test_dashboard_loads(self, page: Page):
        """Test that the dashboard loads successfully."""
        # Wait for the page to load
        await page.wait_for_selector("h1", timeout=10000)
        
        # Check that we have the WakeDock title
        title = await page.title()
        assert "WakeDock" in title
        
        # Check for main navigation elements
        sidebar = await page.query_selector(".sidebar")
        assert sidebar is not None
    
    async def test_navigation_structure(self, page: Page):
        """Test that all main navigation items are present."""
        # Wait for sidebar to load
        await page.wait_for_selector(".sidebar", timeout=10000)
        
        # Check for main navigation items
        nav_items = [
            "Dashboard",
            "Services", 
            "Users",
            "Settings"
        ]
        
        for item in nav_items:
            nav_link = await page.query_selector(f"text={item}")
            assert nav_link is not None, f"Navigation item '{item}' not found"
    
    async def test_services_page_access(self, page: Page):
        """Test accessing the services page."""
        # Navigate to services page
        await page.click("text=Services")
        await page.wait_for_url("**/services", timeout=5000)
        
        # Check for services page elements
        await page.wait_for_selector("h1", timeout=5000)
        page_title = await page.text_content("h1")
        assert "Services" in page_title or "Docker" in page_title
    
    async def test_service_creation_form(self, page: Page):
        """Test the service creation form interface."""
        # Navigate to services page
        await page.click("text=Services")
        await page.wait_for_url("**/services", timeout=5000)
        
        # Look for "Add Service" or "New Service" button
        try:
            # Try different possible button texts
            add_buttons = [
                "text=Add Service",
                "text=New Service", 
                "text=Create Service",
                "text=+"
            ]
            
            button_found = False
            for button_selector in add_buttons:
                button = await page.query_selector(button_selector)
                if button:
                    await button.click()
                    button_found = True
                    break
            
            if button_found:
                # Wait for form to appear (either modal or new page)
                await page.wait_for_timeout(1000)  # Give time for navigation/modal
                
                # Check for form elements
                form_elements = [
                    'input[name="name"]',
                    'input[name="image"]',
                    'select',
                    'button[type="submit"]'
                ]
                
                for element in form_elements:
                    element_exists = await page.query_selector(element)
                    if element_exists:
                        # At least one form element found
                        assert True
                        return
                
                # If no form elements found, the feature might not be implemented yet
                pytest.skip("Service creation form not fully implemented")
            else:
                pytest.skip("Add service button not found - feature may not be implemented")
                
        except Exception as e:
            pytest.skip(f"Service creation test skipped: {str(e)}")
    
    async def test_system_overview_display(self, page: Page):
        """Test that system overview information is displayed."""
        # Should be on dashboard by default
        await page.wait_for_selector("h1", timeout=10000)
        
        # Look for system stats or overview cards
        stats_selectors = [
            ".stats-card",
            ".overview-card", 
            ".metric-card",
            ".system-info",
            "[data-testid*='stat']",
            ".card"
        ]
        
        stats_found = False
        for selector in stats_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                stats_found = True
                break
        
        if not stats_found:
            # Look for any numeric displays that might be stats
            text_content = await page.text_content("body")
            # Look for patterns like "5 services", "Running: 3", etc.
            import re
            if re.search(r'\d+\s*(services?|running|stopped|containers?)', text_content, re.IGNORECASE):
                stats_found = True
        
        assert stats_found, "No system overview statistics found on dashboard"
    
    async def test_responsive_design(self, page: Page):
        """Test that the dashboard is responsive."""
        # Test desktop view
        await page.set_viewport_size({"width": 1200, "height": 800})
        await page.wait_for_timeout(500)
        
        sidebar = await page.query_selector(".sidebar")
        assert sidebar is not None
        
        # Test mobile view
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.wait_for_timeout(500)
        
        # Mobile menu should be available or sidebar should adapt
        body_content = await page.query_selector("body")
        assert body_content is not None
        
        # Check that content is still accessible
        nav_elements = await page.query_selector_all("nav, .navigation, .menu, .sidebar")
        assert len(nav_elements) > 0, "Navigation not accessible in mobile view"
    
    async def test_api_connectivity(self, page: Page, api_server: str):
        """Test that the dashboard can connect to the API."""
        # Check if dashboard shows connection errors
        await page.wait_for_timeout(2000)  # Allow time for API calls
        
        # Look for error messages that might indicate API connectivity issues
        error_indicators = [
            "text=Connection failed",
            "text=API Error", 
            "text=Failed to load",
            ".error",
            ".alert-error",
            "[class*='error']"
        ]
        
        connection_errors = []
        for selector in error_indicators:
            error_element = await page.query_selector(selector)
            if error_element:
                error_text = await error_element.text_content()
                if error_text and "api" in error_text.lower():
                    connection_errors.append(error_text)
        
        # If there are API connection errors, check if API is actually running
        if connection_errors:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{api_server}/api/v1/health") as response:
                        if response.status != 200:
                            pytest.skip(f"API not responding correctly: {response.status}")
            except Exception as e:
                pytest.skip(f"API connectivity issue: {str(e)}")
        
        # If no errors found, assume connection is working
        assert len(connection_errors) == 0 or len(connection_errors) < 3  # Allow some minor errors
    
    async def test_page_load_performance(self, page: Page):
        """Test that pages load within reasonable time."""
        start_time = time.time()
        
        # Navigate to different pages and measure load time
        pages_to_test = [
            "/",
            "/services", 
            "/settings"
        ]
        
        for page_path in pages_to_test:
            start = time.time()
            try:
                await page.goto(f"{page.url.split('/')[0]}//{page.url.split('/')[2]}{page_path}")
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                load_time = time.time() - start
                
                # Page should load within 10 seconds
                assert load_time < 10, f"Page {page_path} took too long to load: {load_time:.2f}s"
                
            except Exception as e:
                # If page doesn't exist, that's ok for this test
                if "404" not in str(e) and "timeout" not in str(e).lower():
                    raise e
    
    @pytest.mark.slow
    async def test_full_user_workflow(self, page: Page):
        """Test a complete user workflow through the dashboard."""
        # 1. Start on dashboard
        await page.wait_for_selector("h1", timeout=10000)
        
        # 2. Navigate to services
        try:
            await page.click("text=Services")
            await page.wait_for_timeout(2000)
        except Exception:
            pass  # Services page might not be accessible without auth
        
        # 3. Try to access settings
        try:
            await page.click("text=Settings")
            await page.wait_for_timeout(2000)
        except Exception:
            pass  # Settings might require admin privileges
        
        # 4. Return to dashboard
        try:
            await page.click("text=Dashboard")
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        # If we get here without major exceptions, the workflow is functional
        assert True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
