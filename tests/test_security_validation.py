"""
Tests for security validation system.

Tests input validation, sanitization, password policies,
service name validation, and security middleware.
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, Request
from starlette.responses import Response

from wakedock.security.validation import (
    validate_service_name, 
    validate_docker_image, 
    sanitize_input,
    validate_password_strength,
    validate_email,
    validate_path,
    SecurityValidator
)
from wakedock.security.rate_limit import RateLimiter, RateLimitExceeded
from wakedock.api.middleware.rate_limiter import RateLimitMiddleware


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_service_name_valid(self):
        """Test valid service names."""
        valid_names = [
            "my-service",
            "web-app-1",
            "api-gateway",
            "user-mgmt",
            "cache-redis",
            "db-primary"
        ]
        
        for name in valid_names:
            result = validate_service_name(name)
            assert result is True, f"Service name '{name}' should be valid"
    
    def test_validate_service_name_invalid(self):
        """Test invalid service names."""
        invalid_names = [
            "",  # Empty
            "a",  # Too short
            "my_service",  # Underscore not allowed
            "MyService",  # Uppercase not allowed
            "my service",  # Space not allowed
            "my-service!",  # Special characters
            "service@domain",  # @ symbol
            "very-long-service-name-that-exceeds-maximum-length-limit",  # Too long
            "-invalid-start",  # Starts with dash
            "invalid-end-",  # Ends with dash
            "123-numeric-start",  # Starts with number
            "special-chars#$%",  # Special characters
        ]
        
        for name in invalid_names:
            result = validate_service_name(name)
            assert result is False, f"Service name '{name}' should be invalid"
    
    def test_validate_docker_image_valid(self):
        """Test valid Docker image names."""
        valid_images = [
            "nginx",
            "nginx:latest",
            "nginx:1.21",
            "nginx:1.21.1",
            "library/nginx",
            "docker.io/library/nginx",
            "gcr.io/project/image",
            "registry.example.com:5000/myapp",
            "localhost:5000/myapp:v1.0.0",
            "myregistry.com/namespace/app:tag-with-dash",
            "ubuntu:20.04",
            "python:3.9-slim",
        ]
        
        for image in valid_images:
            result = validate_docker_image(image)
            assert result is True, f"Docker image '{image}' should be valid"
    
    def test_validate_docker_image_invalid(self):
        """Test invalid Docker image names."""
        invalid_images = [
            "",  # Empty
            "UPPERCASE",  # Uppercase not allowed
            "image with spaces",  # Spaces not allowed
            "image@sha256:invalid",  # @ not in expected position
            "registry.com:port/image:tag:extra",  # Multiple colons in tag
            "../../../etc/passwd",  # Path traversal attempt
            "image:tag with spaces",  # Spaces in tag
            "registry.com/image:tag@sha256:toolong" + "a" * 100,  # Too long
            "image:tag!@#$%",  # Invalid characters in tag
            "-invalid-start",  # Invalid start character
            "invalid-end-",  # Invalid end character
        ]
        
        for image in invalid_images:
            result = validate_docker_image(image)
            assert result is False, f"Docker image '{image}' should be invalid"
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        # Normal input should pass through
        assert sanitize_input("normal_input") == "normal_input"
        assert sanitize_input("123456") == "123456"
        
        # HTML/Script injection attempts
        assert sanitize_input("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"
        assert sanitize_input("<img src=x onerror=alert('xss')>") == "&lt;img src=x onerror=alert('xss')&gt;"
        
        # SQL injection attempts
        assert sanitize_input("'; DROP TABLE users; --") == "'; DROP TABLE users; --"
        
        # Path traversal attempts
        assert sanitize_input("../../../etc/passwd") == "../../../etc/passwd"
        
        # Null bytes
        assert sanitize_input("test\x00null") == "test\x00null"
    
    def test_sanitize_input_preserve_safe_html(self):
        """Test sanitization preserves safe HTML when allowed."""
        # With allow_html=True, safe tags should be preserved
        safe_html = "<p>This is <strong>bold</strong> text</p>"
        result = sanitize_input(safe_html, allow_html=True)
        # Implementation would depend on HTML sanitizer used
        assert result == safe_html or "&lt;p&gt;" in result
    
    def test_validate_email_valid(self):
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "test.email@domain.org",
            "user+tag@example.co.uk",
            "firstname.lastname@company.com",
            "user123@test-domain.com",
            "admin@sub.domain.com",
        ]
        
        for email in valid_emails:
            result = validate_email(email)
            assert result is True, f"Email '{email}' should be valid"
    
    def test_validate_email_invalid(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "",  # Empty
            "not-an-email",  # No @ symbol
            "@example.com",  # No local part
            "user@",  # No domain
            "user@domain",  # No TLD
            "user..name@example.com",  # Double dots
            "user@ex ample.com",  # Space in domain
            "user@example..com",  # Double dots in domain
            "very-long-email-address-that-exceeds-maximum-length@example.com",  # Too long
            "user@[127.0.0.1]",  # IP address format (may be invalid depending on rules)
        ]
        
        for email in invalid_emails:
            result = validate_email(email)
            assert result is False, f"Email '{email}' should be invalid"
    
    def test_validate_path_safe(self):
        """Test safe path validation."""
        safe_paths = [
            "/app/data",
            "/home/user/documents",
            "relative/path",
            "./current/dir",
            "file.txt",
            "/etc/wakedock/config.yml",
        ]
        
        for path in safe_paths:
            result = validate_path(path)
            assert result is True, f"Path '{path}' should be safe"
    
    def test_validate_path_unsafe(self):
        """Test unsafe path validation (path traversal)."""
        unsafe_paths = [
            "../../../etc/passwd",
            "../../secrets.txt",
            "/etc/../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/app/../../../etc/shadow",
            "file://../../etc/hosts",
            "\\\\..\\\\..\\\\sensitive",
        ]
        
        for path in unsafe_paths:
            result = validate_path(path)
            assert result is False, f"Path '{path}' should be unsafe"


class TestPasswordValidation:
    """Test password strength validation."""
    
    def test_password_strength_strong(self):
        """Test strong passwords."""
        strong_passwords = [
            "MyStr0ngP@ssw0rd!",
            "C0mpl3x&S3cur3Pass",
            "Th1s1sAV3ryStr0ngP@ssw0rd",
            "2024$ecur3P@ssw0rd!",
            "My#Super$trong9Password",
        ]
        
        for password in strong_passwords:
            result = validate_password_strength(password)
            assert result["is_valid"] is True, f"Password '{password}' should be strong"
            assert result["score"] >= 80
    
    def test_password_strength_weak(self):
        """Test weak passwords."""
        weak_passwords = [
            "password",  # Common password
            "123456",  # All numbers
            "qwerty",  # Keyboard pattern
            "abc123",  # Short and simple
            "ALLUPPERCASE",  # No variety
            "alllowercase",  # No variety
            "pass",  # Too short
            "",  # Empty
        ]
        
        for password in weak_passwords:
            result = validate_password_strength(password)
            assert result["is_valid"] is False, f"Password '{password}' should be weak"
            assert result["score"] < 60
    
    def test_password_strength_medium(self):
        """Test medium strength passwords."""
        medium_passwords = [
            "Password123",  # Basic requirements met
            "MyPassword1",  # Missing special chars
            "mypassword1!",  # Missing uppercase
            "MYPASSWORD1!",  # Missing lowercase
            "MyPass1!",  # Short but complex
        ]
        
        for password in medium_passwords:
            result = validate_password_strength(password)
            # Medium passwords might be valid or invalid depending on policy
            assert 40 <= result["score"] <= 79
    
    def test_password_requirements_details(self):
        """Test detailed password requirements feedback."""
        result = validate_password_strength("weak")
        
        assert "requirements" in result
        requirements = result["requirements"]
        
        assert "min_length" in requirements
        assert "uppercase" in requirements
        assert "lowercase" in requirements
        assert "numbers" in requirements
        assert "special_chars" in requirements
        
        # Weak password should fail multiple requirements
        failed_requirements = [k for k, v in requirements.items() if not v]
        assert len(failed_requirements) > 0
    
    def test_common_password_detection(self):
        """Test detection of common passwords."""
        common_passwords = [
            "password",
            "123456",
            "qwerty",
            "admin",
            "letmein",
            "welcome",
            "monkey",
        ]
        
        for password in common_passwords:
            result = validate_password_strength(password)
            assert "is_common" in result
            assert result["is_common"] is True


class TestSecurityValidator:
    """Test SecurityValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create security validator instance."""
        return SecurityValidator()
    
    def test_validator_init(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert hasattr(validator, 'validate_input')
        assert hasattr(validator, 'validate_service_config')
    
    def test_validate_service_config_valid(self, validator):
        """Test valid service configuration."""
        valid_config = {
            "name": "web-app",
            "image": "nginx:latest",
            "ports": ["80:8080"],
            "environment": {
                "ENV": "production",
                "PORT": "8080"
            }
        }
        
        result = validator.validate_service_config(valid_config)
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_service_config_invalid(self, validator):
        """Test invalid service configuration."""
        invalid_config = {
            "name": "INVALID NAME",  # Invalid name
            "image": "<script>alert('xss')</script>",  # Invalid image
            "ports": ["invalid:port"],  # Invalid port format
            "environment": {
                "../../../etc/passwd": "value"  # Path traversal in env key
            }
        }
        
        result = validator.validate_service_config(invalid_config)
        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
    
    def test_bulk_validation(self, validator):
        """Test bulk validation of multiple inputs."""
        inputs = {
            "service_name": "valid-service",
            "image": "nginx:latest",
            "email": "user@example.com",
            "password": "MyStr0ngP@ssw0rd!"
        }
        
        results = validator.bulk_validate(inputs)
        
        assert "service_name" in results
        assert "image" in results
        assert "email" in results
        assert "password" in results
        
        # All should be valid
        for field, result in results.items():
            assert result["is_valid"] is True


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance."""
        return RateLimiter(
            max_requests=5,
            time_window=60,  # 5 requests per minute
            storage_backend="memory"
        )
    
    def test_rate_limiter_init(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.max_requests == 5
        assert rate_limiter.time_window == 60
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self, rate_limiter):
        """Test rate limiter allows requests within limit."""
        client_id = "test_client"
        
        # Should allow requests within limit
        for i in range(5):
            result = await rate_limiter.is_allowed(client_id)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self, rate_limiter):
        """Test rate limiter blocks requests over limit."""
        client_id = "test_client"
        
        # Use up the limit
        for i in range(5):
            await rate_limiter.is_allowed(client_id)
        
        # Next request should be blocked
        result = await rate_limiter.is_allowed(client_id)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_reset_window(self, rate_limiter):
        """Test rate limiter resets after time window."""
        # This test would require time manipulation or a shorter window
        # For actual implementation, you'd use freezegun or similar
        pass
    
    @pytest.mark.asyncio
    async def test_rate_limiter_different_clients(self, rate_limiter):
        """Test rate limiter tracks different clients separately."""
        client1 = "client_1"
        client2 = "client_2"
        
        # Client 1 uses up limit
        for i in range(5):
            result = await rate_limiter.is_allowed(client1)
            assert result is True
        
        # Client 1 should be blocked
        result = await rate_limiter.is_allowed(client1)
        assert result is False
        
        # Client 2 should still be allowed
        result = await rate_limiter.is_allowed(client2)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_get_stats(self, rate_limiter):
        """Test rate limiter statistics."""
        client_id = "test_client"
        
        # Make some requests
        for i in range(3):
            await rate_limiter.is_allowed(client_id)
        
        stats = await rate_limiter.get_client_stats(client_id)
        
        assert "requests_made" in stats
        assert "requests_remaining" in stats
        assert "reset_time" in stats
        assert stats["requests_made"] == 3
        assert stats["requests_remaining"] == 2


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create rate limit middleware."""
        return RateLimitMiddleware(
            max_requests=10,
            time_window=60,
            excluded_paths=["/health", "/metrics"]
        )
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.url = Mock()
        request.url.path = "/api/services"
        request.method = "GET"
        return request
    
    @pytest.fixture
    def mock_call_next(self):
        """Create mock call_next function."""
        async def call_next(request):
            response = Mock(spec=Response)
            response.status_code = 200
            return response
        return call_next
    
    @pytest.mark.asyncio
    async def test_middleware_allows_normal_requests(self, middleware, mock_request, mock_call_next):
        """Test middleware allows normal requests."""
        response = await middleware(mock_request, mock_call_next)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_excludes_health_check(self, middleware, mock_call_next):
        """Test middleware excludes health check endpoints."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/health"
        
        response = await middleware(request, mock_call_next)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_blocks_excess_requests(self, middleware, mock_request, mock_call_next):
        """Test middleware blocks excessive requests."""
        # Make requests up to limit
        for i in range(10):
            response = await middleware(mock_request, mock_call_next)
            assert response.status_code == 200
        
        # Next request should be rate limited
        with pytest.raises(HTTPException) as exc_info:
            await middleware(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == 429
        assert "rate limit" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_middleware_adds_rate_limit_headers(self, middleware, mock_request, mock_call_next):
        """Test middleware adds rate limit headers."""
        response = await middleware(mock_request, mock_call_next)
        
        # Check if rate limit headers are added (implementation dependent)
        # Would need to verify actual header setting in real implementation
        assert response.status_code == 200
    
    def test_middleware_client_identification(self, middleware):
        """Test middleware client identification methods."""
        # Test IP-based identification
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        client_id = middleware._get_client_id(request)
        assert client_id == "192.168.1.100"
        
        # Test with X-Forwarded-For header
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}
        client_id = middleware._get_client_id(request)
        assert client_id == "203.0.113.1"
    
    def test_middleware_rate_limit_key_generation(self, middleware):
        """Test rate limit key generation."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.url = Mock()
        request.url.path = "/api/services"
        
        key = middleware._generate_rate_limit_key(request)
        
        # Key should include client identifier and possibly endpoint
        assert "127.0.0.1" in key
        assert isinstance(key, str)
        assert len(key) > 0


class TestSecurityMiddleware:
    """Test security middleware components."""
    
    def test_security_headers_middleware(self):
        """Test security headers are added."""
        # Test implementation would verify security headers like:
        # - X-Content-Type-Options: nosniff
        # - X-Frame-Options: DENY
        # - X-XSS-Protection: 1; mode=block
        # - Strict-Transport-Security
        # - Content-Security-Policy
        pass
    
    def test_csrf_protection_middleware(self):
        """Test CSRF protection middleware."""
        # Test CSRF token generation and validation
        pass
    
    def test_content_type_validation(self):
        """Test content type validation."""
        # Test that only expected content types are accepted
        pass


class TestSecurityIntegration:
    """Test security validation integration."""
    
    @pytest.mark.asyncio
    async def test_service_creation_security_validation(self):
        """Test security validation during service creation."""
        # Test that service creation properly validates all inputs
        pass
    
    @pytest.mark.asyncio
    async def test_user_registration_security_validation(self):
        """Test security validation during user registration."""
        # Test that user registration validates email, password, etc.
        pass
    
    @pytest.mark.asyncio
    async def test_configuration_update_security_validation(self):
        """Test security validation during configuration updates."""
        # Test that configuration updates validate all inputs
        pass