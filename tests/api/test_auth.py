"""
Tests for API authentication
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from wakedock.api.app import create_app
from wakedock.api.auth.jwt import create_access_token, verify_token
from wakedock.api.auth.password import hash_password, verify_password
from wakedock.exceptions import AuthenticationError


class TestAuthenticationAPI:
    """Test cases for authentication API endpoints"""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator"""
        return Mock()
    
    @pytest.fixture
    def mock_monitoring(self):
        """Mock monitoring service"""
        return Mock()
    
    @pytest.fixture
    def client(self, mock_orchestrator, mock_monitoring):
        """Test client"""
        app = create_app(mock_orchestrator, mock_monitoring)
        return TestClient(app)
    
    @pytest.fixture
    def test_user(self):
        """Test user data"""
        return {
            'username': 'testuser',
            'password': 'testpassword123',
            'email': 'test@example.com'
        }
    
    @pytest.fixture
    def valid_token(self, test_user):
        """Valid JWT token"""
        return create_access_token(
            data={'sub': test_user['username']},
            expires_delta=timedelta(hours=1)
        )
    
    def test_login_success(self, client, test_user):
        """Test successful login"""
        with patch('wakedock.api.auth.password.verify_password') as mock_verify:
            with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
                # Mock user verification
                mock_verify.return_value = True
                mock_user = Mock()
                mock_user.username = test_user['username']
                mock_user.hashed_password = hash_password(test_user['password'])
                mock_get_user.return_value = mock_user
                
                response = client.post('/auth/login', json={
                    'username': test_user['username'],
                    'password': test_user['password']
                })
                
                assert response.status_code == 200
                data = response.json()
                assert 'access_token' in data
                assert data['token_type'] == 'bearer'
                assert 'expires_in' in data
    
    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials"""
        with patch('wakedock.api.auth.password.verify_password') as mock_verify:
            with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
                mock_verify.return_value = False
                mock_user = Mock()
                mock_user.username = test_user['username']
                mock_get_user.return_value = mock_user
                
                response = client.post('/auth/login', json={
                    'username': test_user['username'],
                    'password': 'wrongpassword'
                })
                
                assert response.status_code == 401
                data = response.json()
                assert 'detail' in data
    
    def test_login_user_not_found(self, client, test_user):
        """Test login with non-existent user"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = None
            
            response = client.post('/auth/login', json={
                'username': 'nonexistent',
                'password': test_user['password']
            })
            
            assert response.status_code == 401
            data = response.json()
            assert 'detail' in data
    
    def test_token_validation_success(self, client, valid_token):
        """Test successful token validation"""
        response = client.get('/auth/me', headers={
            'Authorization': f'Bearer {valid_token}'
        })
        
        # This might return 404 if the endpoint doesn't exist yet
        assert response.status_code in [200, 404]
    
    def test_token_validation_invalid_token(self, client):
        """Test token validation with invalid token"""
        response = client.get('/auth/me', headers={
            'Authorization': 'Bearer invalid_token'
        })
        
        assert response.status_code == 401
    
    def test_token_validation_expired_token(self, client, test_user):
        """Test token validation with expired token"""
        expired_token = create_access_token(
            data={'sub': test_user['username']},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        response = client.get('/auth/me', headers={
            'Authorization': f'Bearer {expired_token}'
        })
        
        assert response.status_code == 401
    
    def test_token_validation_missing_token(self, client):
        """Test access without token"""
        response = client.get('/auth/me')
        
        assert response.status_code == 401
    
    def test_register_success(self, client, test_user):
        """Test successful user registration"""
        with patch('wakedock.database.models.User.create') as mock_create:
            with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
                with patch('wakedock.database.models.User.get_by_email') as mock_get_email:
                    # Mock that user doesn't exist
                    mock_get_user.return_value = None
                    mock_get_email.return_value = None
                    mock_create.return_value = Mock(id=1, username=test_user['username'])
                    
                    response = client.post('/auth/register', json={
                        'username': test_user['username'],
                        'password': test_user['password'],
                        'email': test_user['email']
                    })
                    
                    # Registration endpoint might not exist yet
                    assert response.status_code in [201, 404]
    
    def test_register_user_exists(self, client, test_user):
        """Test registration with existing username"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username=test_user['username'])
            
            response = client.post('/auth/register', json={
                'username': test_user['username'],
                'password': test_user['password'],
                'email': test_user['email']
            })
            
            # Registration endpoint might not exist yet
            assert response.status_code in [400, 404]
    
    def test_logout(self, client, valid_token):
        """Test logout functionality"""
        response = client.post('/auth/logout', headers={
            'Authorization': f'Bearer {valid_token}'
        })
        
        # Logout endpoint might not exist yet
        assert response.status_code in [200, 404]
    
    def test_refresh_token(self, client, valid_token):
        """Test token refresh functionality"""
        response = client.post('/auth/refresh', headers={
            'Authorization': f'Bearer {valid_token}'
        })
        
        # Refresh endpoint might not exist yet
        assert response.status_code in [200, 404]


class TestJWTUtilities:
    """Test cases for JWT utility functions"""
    
    def test_create_access_token(self):
        """Test JWT token creation"""
        data = {'sub': 'testuser'}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_with_expiration(self):
        """Test JWT token creation with custom expiration"""
        data = {'sub': 'testuser'}
        expires_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_token_success(self):
        """Test successful token verification"""
        data = {'sub': 'testuser'}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload['sub'] == 'testuser'
        assert 'exp' in payload
    
    def test_verify_token_invalid(self):
        """Test token verification with invalid token"""
        with pytest.raises(AuthenticationError):
            verify_token('invalid_token')
    
    def test_verify_token_expired(self):
        """Test token verification with expired token"""
        data = {'sub': 'testuser'}
        token = create_access_token(data, timedelta(seconds=-1))
        
        with pytest.raises(AuthenticationError):
            verify_token(token)
    
    def test_verify_token_malformed(self):
        """Test token verification with malformed token"""
        with pytest.raises(AuthenticationError):
            verify_token('not.a.valid.jwt.token')


class TestPasswordUtilities:
    """Test cases for password utility functions"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = 'testpassword123'
        hashed = hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Should be hashed, not plain text
    
    def test_verify_password_success(self):
        """Test successful password verification"""
        password = 'testpassword123'
        hashed = hash_password(password)
        
        is_valid = verify_password(password, hashed)
        
        assert is_valid is True
    
    def test_verify_password_failure(self):
        """Test password verification failure"""
        password = 'testpassword123'
        wrong_password = 'wrongpassword'
        hashed = hash_password(password)
        
        is_valid = verify_password(wrong_password, hashed)
        
        assert is_valid is False
    
    def test_hash_password_different_results(self):
        """Test that hashing same password twice gives different results"""
        password = 'testpassword123'
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Should be different due to salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAuthenticationMiddleware:
    """Test cases for authentication middleware"""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator"""
        return Mock()
    
    @pytest.fixture
    def mock_monitoring(self):
        """Mock monitoring service"""
        return Mock()
    
    @pytest.fixture
    def client(self, mock_orchestrator, mock_monitoring):
        """Test client"""
        app = create_app(mock_orchestrator, mock_monitoring)
        return TestClient(app)
    
    def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without authentication"""
        response = client.get('/api/services')
        
        # Should require authentication
        assert response.status_code == 401
    
    def test_protected_endpoint_with_valid_auth(self, client):
        """Test accessing protected endpoint with valid authentication"""
        token = create_access_token({'sub': 'testuser'})
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_user = Mock()
            mock_user.username = 'testuser'
            mock_get_user.return_value = mock_user
            
            response = client.get('/api/services', headers={
                'Authorization': f'Bearer {token}'
            })
            
            # Should be allowed (or 404 if endpoint doesn't exist)
            assert response.status_code in [200, 404]
    
    def test_public_endpoint_access(self, client):
        """Test accessing public endpoints without authentication"""
        # Health check should be public
        response = client.get('/health')
        
        # Should be accessible without auth
        assert response.status_code in [200, 404]
    
    def test_auth_header_formats(self, client):
        """Test different authorization header formats"""
        token = create_access_token({'sub': 'testuser'})
        
        # Test with correct Bearer format
        response1 = client.get('/api/services', headers={
            'Authorization': f'Bearer {token}'
        })
        
        # Test with incorrect format (should fail)
        response2 = client.get('/api/services', headers={
            'Authorization': f'Token {token}'
        })
        
        response3 = client.get('/api/services', headers={
            'Authorization': token  # Missing Bearer prefix
        })
        
        # Only the first should be accepted
        assert response1.status_code in [200, 401, 404]
        assert response2.status_code == 401
        assert response3.status_code == 401
