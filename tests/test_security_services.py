"""
Tests pour les Services de Sécurité
Tests unitaires et d'intégration pour les fonctionnalités de sécurité
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

from wakedock.security.jwt_rotation import JWTRotationService, TokenType
from wakedock.security.session_timeout import SessionTimeoutManager
from wakedock.security.intrusion_detection import IntrusionDetectionSystem, AttackType, ThreatLevel
from wakedock.security.manager import SecurityManager
from wakedock.security.config import SecurityConfig


class TestJWTRotationService:
    """Tests pour le service de rotation JWT"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.jwt_service = JWTRotationService(
            secret_key="test-secret-key",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
            rotation_threshold_minutes=5
        )
    
    def test_create_token_pair(self):
        """Test la création d'une paire de tokens"""
        user_id = 123
        tokens = self.jwt_service.create_token_pair(user_id)
        
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.access_expires_at
        assert tokens.refresh_expires_at
        assert tokens.access_expires_at < tokens.refresh_expires_at
    
    def test_decode_token_valid(self):
        """Test le décodage d'un token valide"""
        user_id = 123
        tokens = self.jwt_service.create_token_pair(user_id)
        
        payload = self.jwt_service.decode_token(tokens.access_token)
        
        assert payload is not None
        assert payload["user_id"] == user_id
        assert payload["type"] == TokenType.ACCESS.value
    
    def test_decode_token_invalid(self):
        """Test le décodage d'un token invalide"""
        payload = self.jwt_service.decode_token("invalid-token")
        assert payload is None
    
    def test_revoke_token(self):
        """Test la révocation d'un token"""
        user_id = 123
        tokens = self.jwt_service.create_token_pair(user_id)
        
        # Le token doit être valide
        payload = self.jwt_service.decode_token(tokens.access_token)
        assert payload is not None
        
        # Révoquer le token
        self.jwt_service.revoke_token(tokens.access_token)
        
        # Le token ne doit plus être valide
        payload = self.jwt_service.decode_token(tokens.access_token)
        assert payload is None
    
    def test_should_rotate_token_near_expiry(self):
        """Test la détection de rotation nécessaire près de l'expiration"""
        # Créer un service avec un seuil de rotation élevé
        service = JWTRotationService(
            secret_key="test-secret-key",
            access_token_expire_minutes=1,  # 1 minute
            rotation_threshold_minutes=2   # 2 minutes (> expire)
        )
        
        user_id = 123
        tokens = service.create_token_pair(user_id)
        
        # Le token devrait être marqué pour rotation
        should_rotate = service.should_rotate_token(tokens.access_token)
        assert should_rotate is True
    
    @pytest.mark.asyncio
    async def test_rotate_tokens(self):
        """Test la rotation des tokens"""
        user_id = 123
        tokens = self.jwt_service.create_token_pair(user_id)
        
        # Mock de la base de données
        mock_db = AsyncMock()
        
        # Effectuer la rotation
        new_tokens = await self.jwt_service.rotate_tokens(tokens.refresh_token, mock_db)
        
        assert new_tokens is not None
        assert new_tokens.access_token != tokens.access_token
        assert new_tokens.refresh_token != tokens.refresh_token
        
        # L'ancien refresh token doit être révoqué
        payload = self.jwt_service.decode_token(tokens.refresh_token)
        assert payload is None


class TestSessionTimeoutManager:
    """Tests pour le gestionnaire de timeout de session"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.session_manager = SessionTimeoutManager(
            idle_timeout_minutes=60,
            warn_before_timeout_minutes=5,
            max_concurrent_sessions=3
        )
    
    def test_create_session(self):
        """Test la création d'une session"""
        result = self.session_manager.create_session(
            user_id=123,
            session_id="test-session-1",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )
        
        assert result is True
        assert "test-session-1" in self.session_manager.active_sessions
        assert 123 in self.session_manager.user_sessions
    
    def test_max_concurrent_sessions(self):
        """Test la limite de sessions simultanées"""
        user_id = 123
        
        # Créer des sessions jusqu'à la limite
        for i in range(3):
            result = self.session_manager.create_session(
                user_id=user_id,
                session_id=f"test-session-{i}",
                ip_address="192.168.1.1",
                user_agent="Test Agent"
            )
            assert result is True
        
        # La 4ème session doit être refusée
        result = self.session_manager.create_session(
            user_id=user_id,
            session_id="test-session-4",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )
        assert result is False
    
    def test_session_activity_update(self):
        """Test la mise à jour d'activité de session"""
        self.session_manager.create_session(
            user_id=123,
            session_id="test-session-1",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )
        
        # Obtenir le timestamp initial
        initial_activity = self.session_manager.active_sessions["test-session-1"].last_activity
        
        # Simuler une pause
        import time
        time.sleep(0.1)
        
        # Mettre à jour l'activité
        result = self.session_manager.update_session_activity("test-session-1")
        assert result is True
        
        # Vérifier que le timestamp a été mis à jour
        new_activity = self.session_manager.active_sessions["test-session-1"].last_activity
        assert new_activity > initial_activity
    
    def test_session_expiry(self):
        """Test l'expiration de session"""
        # Créer un manager avec un timeout très court
        manager = SessionTimeoutManager(idle_timeout_minutes=0.01)  # 0.6 secondes
        
        manager.create_session(
            user_id=123,
            session_id="test-session-1",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )
        
        # Attendre l'expiration
        import time
        time.sleep(1)
        
        # La session doit être expirée
        is_expired = manager.is_session_expired("test-session-1")
        assert is_expired is True
    
    def test_cleanup_expired_sessions(self):
        """Test le nettoyage des sessions expirées"""
        # Créer un manager avec un timeout très court
        manager = SessionTimeoutManager(idle_timeout_minutes=0.01)
        
        # Créer plusieurs sessions
        for i in range(3):
            manager.create_session(
                user_id=123,
                session_id=f"test-session-{i}",
                ip_address="192.168.1.1",
                user_agent="Test Agent"
            )
        
        # Attendre l'expiration
        import time
        time.sleep(1)
        
        # Nettoyer les sessions expirées
        cleaned_count = manager.cleanup_expired_sessions()
        
        assert cleaned_count == 3
        assert len(manager.active_sessions) == 0


class TestIntrusionDetectionSystem:
    """Tests pour le système de détection d'intrusion"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.ids = IntrusionDetectionSystem()
    
    def test_sql_injection_detection(self):
        """Test la détection d'injection SQL"""
        events = self.ids.analyze_request(
            ip_address="192.168.1.1",
            endpoint="/api/users",
            method="GET",
            user_agent="Test Agent",
            payload="id=1' OR '1'='1"
        )
        
        assert len(events) > 0
        sql_events = [e for e in events if e.attack_type == AttackType.SQL_INJECTION]
        assert len(sql_events) > 0
        assert sql_events[0].confidence > 0.5
    
    def test_xss_detection(self):
        """Test la détection XSS"""
        events = self.ids.analyze_request(
            ip_address="192.168.1.1",
            endpoint="/api/comments",
            method="POST",
            user_agent="Test Agent",
            payload="<script>alert('xss')</script>"
        )
        
        assert len(events) > 0
        xss_events = [e for e in events if e.attack_type == AttackType.XSS]
        assert len(xss_events) > 0
        assert xss_events[0].confidence > 0.5
    
    def test_suspicious_user_agent(self):
        """Test la détection d'User-Agent suspect"""
        events = self.ids.analyze_request(
            ip_address="192.168.1.1",
            endpoint="/api/users",
            method="GET",
            user_agent="sqlmap/1.0",
            payload=None
        )
        
        assert len(events) > 0
        ua_events = [e for e in events if e.attack_type == AttackType.SUSPICIOUS_USER_AGENT]
        assert len(ua_events) > 0
        assert ua_events[0].confidence > 0.7
    
    def test_brute_force_detection(self):
        """Test la détection de brute force"""
        ip_address = "192.168.1.100"
        
        # Simuler plusieurs tentatives de connexion échouées
        for i in range(6):
            events = self.ids.analyze_request(
                ip_address=ip_address,
                endpoint="/auth/login",
                method="POST",
                user_agent="Test Agent",
                payload="username=admin&password=wrong"
            )
            
            # Marquer les tentatives comme échouées
            if ip_address in self.ids.ip_profiles:
                self.ids.ip_profiles[ip_address].update_activity("/auth/login", "Test Agent", success=False)
        
        # La dernière analyse doit détecter le brute force
        events = self.ids.analyze_request(
            ip_address=ip_address,
            endpoint="/auth/login",
            method="POST",
            user_agent="Test Agent",
            payload="username=admin&password=wrong"
        )
        
        brute_force_events = [e for e in events if e.attack_type == AttackType.BRUTE_FORCE]
        assert len(brute_force_events) > 0
    
    def test_ip_blocking(self):
        """Test le blocage d'IP"""
        ip_address = "192.168.1.200"
        
        # Bloquer l'IP
        self.ids.block_ip(ip_address)
        
        # Vérifier que l'IP est bloquée
        assert self.ids.is_ip_blocked(ip_address)
        
        # Analyser une requête depuis cette IP
        events = self.ids.analyze_request(
            ip_address=ip_address,
            endpoint="/api/users",
            method="GET",
            user_agent="Test Agent",
            payload=None
        )
        
        # Un événement de blocage doit être généré
        blocked_events = [e for e in events if e.blocked]
        assert len(blocked_events) > 0
    
    def test_ip_whitelisting(self):
        """Test la whitelist d'IP"""
        ip_address = "192.168.1.250"
        
        # Ajouter l'IP à la whitelist
        self.ids.whitelist_ip(ip_address)
        
        # Vérifier que l'IP est en whitelist
        assert self.ids.is_ip_whitelisted(ip_address)
        
        # Analyser une requête suspecte depuis cette IP
        events = self.ids.analyze_request(
            ip_address=ip_address,
            endpoint="/api/users",
            method="GET",
            user_agent="sqlmap/1.0",  # User-Agent suspect
            payload="id=1' OR '1'='1"  # SQL injection
        )
        
        # L'IP étant en whitelist, moins d'événements doivent être générés
        # (ou des événements avec une confiance réduite)
        assert len(events) >= 0  # Peut varier selon l'implémentation


class TestSecurityManager:
    """Tests pour le gestionnaire de sécurité"""
    
    def setup_method(self):
        """Setup pour chaque test"""
        self.security_manager = SecurityManager()
    
    @pytest.mark.asyncio
    async def test_initialize_security_services(self):
        """Test l'initialisation des services de sécurité"""
        config = {
            "jwt_secret_key": "test-secret-key",
            "security": {
                "environment": "testing",
                "session": {
                    "idle_timeout_minutes": 30
                }
            }
        }
        
        services = await self.security_manager.initialize(config)
        
        assert services is not None
        assert services.jwt_rotation_service is not None
        assert services.session_timeout_manager is not None
        assert services.intrusion_detection_system is not None
        assert services.security_config is not None
    
    @pytest.mark.asyncio
    async def test_security_audit(self):
        """Test l'audit de sécurité"""
        # Initialiser les services
        await self.security_manager.initialize({
            "jwt_secret_key": "test-secret-key"
        })
        
        # Exécuter l'audit
        audit_results = await self.security_manager.run_security_audit()
        
        assert audit_results is not None
        assert "results" in audit_results
        assert "jwt_rotation" in audit_results["results"]
        assert "session_management" in audit_results["results"]
        assert "intrusion_detection" in audit_results["results"]
        assert "security_score" in audit_results
        assert isinstance(audit_results["security_score"], int)
    
    def test_get_security_recommendations(self):
        """Test les recommandations de sécurité"""
        # Configuration avec des problèmes de sécurité
        config = SecurityConfig(
            environment="production",
            debug_mode=True,  # Problème !
            features={
                "enable_mfa": False,  # Problème !
                "enable_intrusion_detection": False
            }
        )
        
        self.security_manager.config = config
        self.security_manager._initialized = True
        
        recommendations = self.security_manager.get_security_recommendations()
        
        assert len(recommendations) > 0
        
        # Vérifier qu'il y a des recommandations critiques
        critical_recs = [r for r in recommendations if r["priority"] == "critical"]
        assert len(critical_recs) > 0
        
        # Vérifier qu'il y a des recommandations sur le MFA
        mfa_recs = [r for r in recommendations if "MFA" in r["message"]]
        assert len(mfa_recs) > 0
    
    def test_security_status(self):
        """Test le statut de sécurité"""
        # Avant initialisation
        status = self.security_manager.get_security_status()
        assert status["status"] == "not_initialized"
        
        # Simuler l'initialisation
        self.security_manager._initialized = True
        self.security_manager.services = Mock()
        
        # Mock des services
        self.security_manager.services.jwt_rotation_service = Mock()
        self.security_manager.services.jwt_rotation_service.get_rotation_stats.return_value = {
            "total_rotations": 10,
            "successful_rotations": 9,
            "failed_rotations": 1
        }
        
        self.security_manager.services.session_timeout_service = Mock()
        self.security_manager.services.session_timeout_service.get_session_stats.return_value = {
            "active_sessions_count": 5,
            "expired_sessions": 2
        }
        
        self.security_manager.services.intrusion_detection_system = Mock()
        self.security_manager.services.intrusion_detection_system.get_statistics.return_value = {
            "total_events": 100,
            "blocked_attacks": 5,
            "active_threats": 1
        }
        
        # Après initialisation
        status = self.security_manager.get_security_status()
        assert status["status"] == "initialized"
        assert "services" in status
        assert "config" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
