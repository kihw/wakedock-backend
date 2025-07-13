"""
Simple security validation tests.
"""

import pytest
from wakedock.security.validation import (
    validate_service_name,
    validate_docker_image,
    sanitize_input,
    validate_email,
    validate_path
)


class TestSecurityValidation:
    """Test security validation functions."""
    
    def test_validate_service_name_valid(self):
        """Test valid service names."""
        valid_names = [
            "web-app",
            "api-service",
            "my-database",
            "cache-redis",
            "frontend-ui"
        ]
        
        for name in valid_names:
            result = validate_service_name(name)
            assert result is True, f"Service name '{name}' should be valid"
    
    def test_validate_service_name_invalid(self):
        """Test invalid service names."""
        invalid_names = [
            "",  # Empty
            "UPPERCASE",  # Uppercase
            "service_with_underscore",  # Underscore
            "service with spaces",  # Spaces
            "service!@#",  # Special chars
            "-starts-with-dash",  # Starts with dash
            "ends-with-dash-",  # Ends with dash
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
            "library/nginx",
            "docker.io/nginx",
            "localhost:5000/myapp:v1.0.0"
        ]
        
        for image in valid_images:
            result = validate_docker_image(image)
            assert result is True, f"Docker image '{image}' should be valid"
    
    def test_validate_docker_image_invalid(self):
        """Test invalid Docker image names."""
        invalid_images = [
            "",  # Empty
            "UPPERCASE",  # Uppercase
            "image with spaces",  # Spaces
            "../../../etc/passwd",  # Path traversal
        ]
        
        for image in invalid_images:
            result = validate_docker_image(image)
            assert result is False, f"Docker image '{image}' should be invalid"
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        # Normal input should pass through
        assert sanitize_input("normal_input") == "normal_input"
        assert sanitize_input("test123") == "test123"
        
        # HTML should be escaped
        result = sanitize_input("<script>alert('xss')</script>")
        assert "<script>" not in result or "&lt;script&gt;" in result
    
    def test_validate_email_valid(self):
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "test.email@domain.org",
            "admin@company.com"
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
            "file.txt"
        ]
        
        for path in safe_paths:
            result = validate_path(path)
            assert result is True, f"Path '{path}' should be safe"
    
    def test_validate_path_unsafe(self):
        """Test unsafe path validation."""
        unsafe_paths = [
            "../../../etc/passwd",
            "../../secrets.txt",
            "..\\..\\windows\\system32"
        ]
        
        for path in unsafe_paths:
            result = validate_path(path)
            assert result is False, f"Path '{path}' should be unsafe"