"""
Service d'audit de sécurité avancé pour WakeDock
Traçabilité complète, chiffrement des logs et détection d'anomalies
"""
import asyncio
import base64
import gzip
import hashlib
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import aiofiles.os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from wakedock.core.config import get_settings
from wakedock.core.database import get_async_session
from wakedock.models.audit import AnomalyDetection, AuditLog, SecurityEvent

logger = logging.getLogger(__name__)

class SecurityEventType(str, Enum):
    """Types d'événements de sécurité"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNMENT = "role_assignment"
    ROLE_REMOVAL = "role_removal"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_ACCESS = "system_access"
    API_ABUSE = "api_abuse"
    BRUTE_FORCE = "brute_force"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class AnomalyType(str, Enum):
    """Types d'anomalies détectées"""
    UNUSUAL_LOGIN_TIME = "unusual_login_time"
    MULTIPLE_FAILED_LOGINS = "multiple_failed_logins"
    UNUSUAL_LOCATION = "unusual_location"
    HIGH_FREQUENCY_REQUESTS = "high_frequency_requests"
    UNUSUAL_DATA_ACCESS = "unusual_data_access"
    PRIVILEGE_USAGE_ANOMALY = "privilege_usage_anomaly"
    SESSION_ANOMALY = "session_anomaly"
    API_PATTERN_ANOMALY = "api_pattern_anomaly"

class SecurityEventData(BaseModel):
    """Modèle pour les données d'événement de sécurité"""
    event_type: SecurityEventType
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    success: bool = True
    details: Dict[str, Any] = {}
    risk_score: int = 0
    metadata: Dict[str, Any] = {}

class AnomalyReport(BaseModel):
    """Rapport d'anomalie détectée"""
    anomaly_type: AnomalyType
    severity: str  # low, medium, high, critical
    confidence: float  # 0.0 - 1.0
    user_id: Optional[int] = None
    description: str
    evidence: Dict[str, Any] = {}
    recommended_actions: List[str] = []

class SecurityAuditService:
    """Service d'audit de sécurité avancé avec chiffrement et détection d'anomalies"""
    
    def __init__(self, storage_path: str = "/var/log/wakedock/security"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration de chiffrement
        self._encryption_key = None
        self._setup_encryption()
        
        # Configuration de rétention des logs
        self.log_retention_days = get_settings().SECURITY_LOG_RETENTION_DAYS or 365
        self.compressed_log_retention_days = get_settings().COMPRESSED_LOG_RETENTION_DAYS or 2555  # 7 ans
        
        # Patterns de détection d'anomalies
        self.user_behavior_cache: Dict[int, Dict] = {}
        self.failed_login_attempts: Dict[str, List[datetime]] = {}
        self.api_usage_patterns: Dict[int, Dict] = {}
        
        # Seuils de détection
        self.max_failed_logins = 5
        self.suspicious_request_threshold = 100  # requêtes par minute
        self.unusual_time_threshold = timedelta(hours=2)  # écart par rapport aux heures habituelles
        
        # File d'attente pour le traitement asynchrone
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None
        
        logger.info(f"Service d'audit de sécurité initialisé - Stockage: {self.storage_path}")

    def _setup_encryption(self):
        """Configure le chiffrement pour les logs de sécurité"""
        try:
            settings = get_settings()
            secret_key = settings.SECRET_KEY.encode() if hasattr(settings, 'SECRET_KEY') else b"wakedock-security-key-2025"
            
            # Dériver une clé de chiffrement sécurisée
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"wakedock-security-salt",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret_key))
            self._encryption_key = Fernet(key)
            logger.info("Chiffrement des logs de sécurité configuré")
        except Exception as e:
            logger.error(f"Erreur configuration chiffrement: {e}")
            # Fallback vers une clé par défaut (pour développement uniquement)
            self._encryption_key = Fernet(Fernet.generate_key())

    async def start(self):
        """Démarre le service d'audit de sécurité"""
        if self.processing_task is None or self.processing_task.done():
            self.processing_task = asyncio.create_task(self._process_security_events())
        
        # Démarre la tâche de nettoyage des logs
        asyncio.create_task(self._cleanup_old_logs())
        
        logger.info("Service d'audit de sécurité démarré")

    async def stop(self):
        """Arrête le service d'audit de sécurité"""
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Service d'audit de sécurité arrêté")

    async def log_security_event(self, event_data: SecurityEventData) -> str:
        """
        Enregistre un événement de sécurité avec chiffrement
        Retourne l'ID unique de l'événement
        """
        try:
            # Générer un ID unique pour l'événement
            event_id = self._generate_event_id(event_data)
            
            # Enrichir les données avec des métadonnées
            enriched_data = await self._enrich_event_data(event_data)
            
            # Ajouter à la file d'attente pour traitement asynchrone
            await self.event_queue.put((event_id, enriched_data))
            
            # Détection d'anomalies en temps réel
            await self._detect_anomalies(enriched_data)
            
            return event_id
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'événement de sécurité: {e}")
            raise

    async def _process_security_events(self):
        """Traite les événements de sécurité de manière asynchrone"""
        while True:
            try:
                # Attendre un événement dans la file
                event_id, event_data = await self.event_queue.get()
                
                # Enregistrer en base de données
                await self._save_to_database(event_id, event_data)
                
                # Sauvegarder dans les logs chiffrés
                await self._save_encrypted_log(event_id, event_data)
                
                # Mettre à jour les patterns de comportement
                await self._update_behavior_patterns(event_data)
                
                # Marquer la tâche comme terminée
                self.event_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'événement de sécurité: {e}")

    async def _save_to_database(self, event_id: str, event_data: SecurityEventData):
        """Sauvegarde l'événement en base de données"""
        try:
            async with get_async_session() as session:
                # Créer l'entrée d'audit
                audit_log = AuditLog(
                    event_id=event_id,
                    user_id=event_data.user_id,
                    username=event_data.username,
                    action=event_data.action or event_data.event_type.value,
                    resource=event_data.resource,
                    ip_address=event_data.ip_address,
                    user_agent=event_data.user_agent,
                    success=event_data.success,
                    details=event_data.details,
                    metadata=event_data.metadata,
                    created_at=datetime.utcnow()
                )
                session.add(audit_log)
                
                # Créer l'événement de sécurité
                security_event = SecurityEvent(
                    event_id=event_id,
                    event_type=event_data.event_type.value,
                    severity=self._calculate_severity(event_data),
                    risk_score=event_data.risk_score,
                    user_id=event_data.user_id,
                    ip_address=event_data.ip_address,
                    details=event_data.details,
                    metadata=event_data.metadata,
                    created_at=datetime.utcnow()
                )
                session.add(security_event)
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde base de données: {e}")

    async def _save_encrypted_log(self, event_id: str, event_data: SecurityEventData):
        """Sauvegarde l'événement dans un fichier log chiffré"""
        try:
            # Préparer les données pour le chiffrement
            log_entry = {
                "event_id": event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_data.event_type.value,
                "user_id": event_data.user_id,
                "username": event_data.username,
                "ip_address": event_data.ip_address,
                "user_agent": event_data.user_agent,
                "resource": event_data.resource,
                "action": event_data.action,
                "success": event_data.success,
                "risk_score": event_data.risk_score,
                "details": event_data.details,
                "metadata": event_data.metadata
            }
            
            # Chiffrer les données
            encrypted_data = self._encryption_key.encrypt(json.dumps(log_entry).encode())
            
            # Nom du fichier basé sur la date
            today = datetime.utcnow().strftime("%Y-%m-%d")
            log_file = self.storage_path / f"security-{today}.log"
            
            # Ajouter au fichier log
            async with aiofiles.open(log_file, 'ab') as f:
                await f.write(encrypted_data + b'\n')
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde log chiffré: {e}")

    async def _detect_anomalies(self, event_data: SecurityEventData):
        """Détecte les anomalies dans les événements de sécurité"""
        try:
            anomalies = []
            
            # Détection de tentatives de brute force
            if event_data.event_type == SecurityEventType.LOGIN_FAILURE:
                anomaly = await self._detect_brute_force(event_data)
                if anomaly:
                    anomalies.append(anomaly)
            
            # Détection d'activité à des heures inhabituelles
            if event_data.user_id:
                anomaly = await self._detect_unusual_time_access(event_data)
                if anomaly:
                    anomalies.append(anomaly)
            
            # Détection de fréquence de requêtes anormale
            anomaly = await self._detect_high_frequency_requests(event_data)
            if anomaly:
                anomalies.append(anomaly)
            
            # Enregistrer les anomalies détectées
            for anomaly in anomalies:
                await self._save_anomaly(anomaly)
                
        except Exception as e:
            logger.error(f"Erreur détection anomalies: {e}")

    async def _detect_brute_force(self, event_data: SecurityEventData) -> Optional[AnomalyReport]:
        """Détecte les tentatives de brute force"""
        try:
            ip_key = event_data.ip_address
            current_time = datetime.utcnow()
            
            # Initialiser si nécessaire
            if ip_key not in self.failed_login_attempts:
                self.failed_login_attempts[ip_key] = []
            
            # Ajouter la tentative échouée
            self.failed_login_attempts[ip_key].append(current_time)
            
            # Nettoyer les tentatives anciennes (dernière heure)
            cutoff_time = current_time - timedelta(hours=1)
            self.failed_login_attempts[ip_key] = [
                attempt for attempt in self.failed_login_attempts[ip_key]
                if attempt > cutoff_time
            ]
            
            # Vérifier si le seuil est dépassé
            if len(self.failed_login_attempts[ip_key]) >= self.max_failed_logins:
                return AnomalyReport(
                    anomaly_type=AnomalyType.MULTIPLE_FAILED_LOGINS,
                    severity="high",
                    confidence=0.9,
                    user_id=event_data.user_id,
                    description=f"Détection de {len(self.failed_login_attempts[ip_key])} tentatives de connexion échouées depuis {ip_key}",
                    evidence={
                        "ip_address": ip_key,
                        "failed_attempts": len(self.failed_login_attempts[ip_key]),
                        "time_window": "1 hour",
                        "attempts_timestamps": [t.isoformat() for t in self.failed_login_attempts[ip_key]]
                    },
                    recommended_actions=[
                        "Bloquer temporairement l'adresse IP",
                        "Renforcer l'authentification pour cet utilisateur",
                        "Enquêter sur l'origine des tentatives"
                    ]
                )
                
        except Exception as e:
            logger.error(f"Erreur détection brute force: {e}")
        
        return None

    async def _detect_unusual_time_access(self, event_data: SecurityEventData) -> Optional[AnomalyReport]:
        """Détecte les accès à des heures inhabituelles"""
        try:
            if not event_data.user_id:
                return None
            
            current_time = datetime.utcnow()
            current_hour = current_time.hour
            
            # Récupérer l'historique des heures de connexion de l'utilisateur
            async with get_async_session() as session:
                # Requête pour les 30 derniers jours
                thirty_days_ago = current_time - timedelta(days=30)
                
                result = await session.execute(
                    select(func.extract('hour', AuditLog.created_at))
                    .where(
                        and_(
                            AuditLog.user_id == event_data.user_id,
                            AuditLog.action == 'login',
                            AuditLog.success == True,
                            AuditLog.created_at >= thirty_days_ago
                        )
                    )
                )
                
                usual_hours = [row[0] for row in result.fetchall()]
                
                if usual_hours:
                    # Calculer si l'heure actuelle est inhabituelle
                    hour_counts = {}
                    for hour in usual_hours:
                        hour_counts[hour] = hour_counts.get(hour, 0) + 1
                    
                    # Si l'heure actuelle n'a jamais été utilisée ou très rarement
                    current_hour_count = hour_counts.get(current_hour, 0)
                    total_logins = len(usual_hours)
                    
                    if total_logins > 10 and (current_hour_count / total_logins) < 0.05:
                        return AnomalyReport(
                            anomaly_type=AnomalyType.UNUSUAL_LOGIN_TIME,
                            severity="medium",
                            confidence=0.7,
                            user_id=event_data.user_id,
                            description=f"Connexion à une heure inhabituelle ({current_hour}h) pour l'utilisateur {event_data.username}",
                            evidence={
                                "current_hour": current_hour,
                                "usual_hours_distribution": hour_counts,
                                "frequency_at_current_hour": current_hour_count,
                                "total_historical_logins": total_logins
                            },
                            recommended_actions=[
                                "Vérifier l'identité de l'utilisateur",
                                "Demander une authentification supplémentaire",
                                "Surveiller l'activité de cette session"
                            ]
                        )
                        
        except Exception as e:
            logger.error(f"Erreur détection heure inhabituelle: {e}")
        
        return None

    async def _detect_high_frequency_requests(self, event_data: SecurityEventData) -> Optional[AnomalyReport]:
        """Détecte les requêtes à haute fréquence (potentiel abus API)"""
        try:
            if not event_data.user_id:
                return None
            
            current_time = datetime.utcnow()
            user_id = event_data.user_id
            
            # Initialiser le suivi si nécessaire
            if user_id not in self.api_usage_patterns:
                self.api_usage_patterns[user_id] = {
                    'requests': [],
                    'last_reset': current_time
                }
            
            user_pattern = self.api_usage_patterns[user_id]
            
            # Réinitialiser si plus d'une minute
            if current_time - user_pattern['last_reset'] > timedelta(minutes=1):
                user_pattern['requests'] = []
                user_pattern['last_reset'] = current_time
            
            # Ajouter la requête actuelle
            user_pattern['requests'].append(current_time)
            
            # Vérifier le seuil
            if len(user_pattern['requests']) > self.suspicious_request_threshold:
                return AnomalyReport(
                    anomaly_type=AnomalyType.HIGH_FREQUENCY_REQUESTS,
                    severity="high",
                    confidence=0.95,
                    user_id=user_id,
                    description=f"Détection de {len(user_pattern['requests'])} requêtes en 1 minute pour l'utilisateur {event_data.username}",
                    evidence={
                        "request_count": len(user_pattern['requests']),
                        "time_window": "1 minute",
                        "threshold": self.suspicious_request_threshold,
                        "user_id": user_id,
                        "ip_address": event_data.ip_address
                    },
                    recommended_actions=[
                        "Implémenter un rate limiting",
                        "Suspendre temporairement l'accès API",
                        "Vérifier si c'est un bot ou un script automatisé"
                    ]
                )
                
        except Exception as e:
            logger.error(f"Erreur détection haute fréquence: {e}")
        
        return None

    async def _save_anomaly(self, anomaly: AnomalyReport):
        """Sauvegarde une anomalie détectée"""
        try:
            async with get_async_session() as session:
                anomaly_record = AnomalyDetection(
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity,
                    confidence=anomaly.confidence,
                    user_id=anomaly.user_id,
                    description=anomaly.description,
                    evidence=anomaly.evidence,
                    recommended_actions=anomaly.recommended_actions,
                    resolved=False,
                    created_at=datetime.utcnow()
                )
                session.add(anomaly_record)
                await session.commit()
                
                logger.warning(f"Anomalie détectée: {anomaly.anomaly_type.value} - {anomaly.description}")
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde anomalie: {e}")

    async def _cleanup_old_logs(self):
        """Nettoie les anciens logs selon la politique de rétention"""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Vérifier quotidiennement
                
                current_time = datetime.utcnow()
                
                # Supprimer les logs non compressés anciens
                retention_cutoff = current_time - timedelta(days=self.log_retention_days)
                
                # Compresser les logs avant suppression
                for log_file in self.storage_path.glob("security-*.log"):
                    file_date_str = log_file.stem.replace("security-", "")
                    try:
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                        if file_date < retention_cutoff:
                            # Compresser le fichier
                            compressed_file = log_file.with_suffix('.log.gz')
                            if not compressed_file.exists():
                                await self._compress_log_file(log_file, compressed_file)
                            
                            # Supprimer le fichier original
                            await aiofiles.os.remove(log_file)
                            
                    except ValueError:
                        continue  # Ignorer les fichiers avec format de date invalide
                
                # Supprimer les logs compressés très anciens
                compressed_retention_cutoff = current_time - timedelta(days=self.compressed_log_retention_days)
                
                for compressed_file in self.storage_path.glob("security-*.log.gz"):
                    file_date_str = compressed_file.stem.replace("security-", "").replace(".log", "")
                    try:
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                        if file_date < compressed_retention_cutoff:
                            await aiofiles.os.remove(compressed_file)
                            
                    except ValueError:
                        continue
                        
                logger.info("Nettoyage des logs de sécurité terminé")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur lors du nettoyage des logs: {e}")

    async def _compress_log_file(self, source_file: Path, target_file: Path):
        """Compresse un fichier de log"""
        try:
            async with aiofiles.open(source_file, 'rb') as f_in:
                content = await f_in.read()
            
            compressed_content = gzip.compress(content)
            
            async with aiofiles.open(target_file, 'wb') as f_out:
                await f_out.write(compressed_content)
                
        except Exception as e:
            logger.error(f"Erreur compression fichier {source_file}: {e}")

    def _generate_event_id(self, event_data: SecurityEventData) -> str:
        """Génère un ID unique pour l'événement"""
        timestamp = datetime.utcnow().isoformat()
        data_hash = hashlib.sha256(
            f"{timestamp}{event_data.event_type.value}{event_data.ip_address}".encode()
        ).hexdigest()[:16]
        return f"sec_{data_hash}"

    async def _enrich_event_data(self, event_data: SecurityEventData) -> SecurityEventData:
        """Enrichit les données d'événement avec des métadonnées supplémentaires"""
        # Ajouter des métadonnées de géolocalisation (si disponible)
        if event_data.ip_address and not event_data.ip_address.startswith('127.'):
            # Placeholder pour géolocalisation (à implémenter avec un service externe)
            event_data.metadata['geo_location'] = "Unknown"
        
        # Ajouter l'empreinte de l'user agent
        if event_data.user_agent:
            ua_hash = hashlib.md5(event_data.user_agent.encode()).hexdigest()[:8]
            event_data.metadata['user_agent_hash'] = ua_hash
        
        # Calculer le score de risque
        event_data.risk_score = self._calculate_risk_score(event_data)
        
        return event_data

    def _calculate_risk_score(self, event_data: SecurityEventData) -> int:
        """Calcule un score de risque pour l'événement (0-100)"""
        score = 0
        
        # Score basé sur le type d'événement
        risk_scores = {
            SecurityEventType.LOGIN_FAILURE: 30,
            SecurityEventType.PERMISSION_DENIED: 40,
            SecurityEventType.UNAUTHORIZED_ACCESS: 80,
            SecurityEventType.PRIVILEGE_ESCALATION: 90,
            SecurityEventType.BRUTE_FORCE: 85,
            SecurityEventType.SUSPICIOUS_ACTIVITY: 70,
            SecurityEventType.API_ABUSE: 60,
            SecurityEventType.LOGIN_SUCCESS: 5,
            SecurityEventType.DATA_ACCESS: 10,
            SecurityEventType.DATA_MODIFICATION: 25,
        }
        
        score += risk_scores.get(event_data.event_type, 10)
        
        # Augmenter le score pour les échecs
        if not event_data.success:
            score += 20
        
        # Augmenter le score pour les IP externes
        if event_data.ip_address and not event_data.ip_address.startswith(('127.', '192.168.', '10.')):
            score += 15
        
        return min(score, 100)

    def _calculate_severity(self, event_data: SecurityEventData) -> str:
        """Calcule la sévérité de l'événement"""
        score = event_data.risk_score
        
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    async def get_security_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[SecurityEventType]] = None,
        user_id: Optional[int] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Récupère les événements de sécurité avec filtres"""
        try:
            async with get_async_session() as session:
                query = select(SecurityEvent)
                
                conditions = []
                
                if start_date:
                    conditions.append(SecurityEvent.created_at >= start_date)
                if end_date:
                    conditions.append(SecurityEvent.created_at <= end_date)
                if event_types:
                    conditions.append(SecurityEvent.event_type.in_([et.value for et in event_types]))
                if user_id:
                    conditions.append(SecurityEvent.user_id == user_id)
                if severity:
                    conditions.append(SecurityEvent.severity == severity)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                query = query.order_by(SecurityEvent.created_at.desc()).limit(limit)
                
                result = await session.execute(query)
                events = result.scalars().all()
                
                return [
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "risk_score": event.risk_score,
                        "user_id": event.user_id,
                        "ip_address": event.ip_address,
                        "details": event.details,
                        "metadata": event.metadata,
                        "created_at": event.created_at.isoformat()
                    }
                    for event in events
                ]
                
        except Exception as e:
            logger.error(f"Erreur récupération événements de sécurité: {e}")
            return []

    async def get_anomalies(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Récupère les anomalies détectées avec filtres"""
        try:
            async with get_async_session() as session:
                query = select(AnomalyDetection)
                
                conditions = []
                
                if start_date:
                    conditions.append(AnomalyDetection.created_at >= start_date)
                if end_date:
                    conditions.append(AnomalyDetection.created_at <= end_date)
                if severity:
                    conditions.append(AnomalyDetection.severity == severity)
                if resolved is not None:
                    conditions.append(AnomalyDetection.resolved == resolved)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                query = query.order_by(AnomalyDetection.created_at.desc()).limit(limit)
                
                result = await session.execute(query)
                anomalies = result.scalars().all()
                
                return [
                    {
                        "id": anomaly.id,
                        "anomaly_type": anomaly.anomaly_type,
                        "severity": anomaly.severity,
                        "confidence": anomaly.confidence,
                        "user_id": anomaly.user_id,
                        "description": anomaly.description,
                        "evidence": anomaly.evidence,
                        "recommended_actions": anomaly.recommended_actions,
                        "resolved": anomaly.resolved,
                        "created_at": anomaly.created_at.isoformat(),
                        "resolved_at": anomaly.resolved_at.isoformat() if anomaly.resolved_at else None
                    }
                    for anomaly in anomalies
                ]
                
        except Exception as e:
            logger.error(f"Erreur récupération anomalies: {e}")
            return []

    async def resolve_anomaly(self, anomaly_id: int, resolved_by: int, resolution_notes: str = ""):
        """Marque une anomalie comme résolue"""
        try:
            async with get_async_session() as session:
                anomaly = await session.get(AnomalyDetection, anomaly_id)
                if anomaly:
                    anomaly.resolved = True
                    anomaly.resolved_at = datetime.utcnow()
                    anomaly.resolved_by = resolved_by
                    
                    if resolution_notes:
                        if not anomaly.metadata:
                            anomaly.metadata = {}
                        anomaly.metadata['resolution_notes'] = resolution_notes
                    
                    await session.commit()
                    logger.info(f"Anomalie {anomaly_id} marquée comme résolue par l'utilisateur {resolved_by}")
                    
        except Exception as e:
            logger.error(f"Erreur résolution anomalie {anomaly_id}: {e}")

    async def get_security_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Calcule des métriques de sécurité pour le dashboard"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            async with get_async_session() as session:
                # Compte des événements par type
                events_query = select(
                    SecurityEvent.event_type,
                    func.count(SecurityEvent.id).label('count')
                ).where(
                    SecurityEvent.created_at >= start_date
                ).group_by(SecurityEvent.event_type)
                
                events_result = await session.execute(events_query)
                events_by_type = {row[0]: row[1] for row in events_result}
                
                # Anomalies non résolues
                anomalies_query = select(func.count(AnomalyDetection.id)).where(
                    and_(
                        AnomalyDetection.created_at >= start_date,
                        AnomalyDetection.resolved == False
                    )
                )
                unresolved_anomalies = await session.scalar(anomalies_query)
                
                # Score de risque moyen
                risk_query = select(func.avg(SecurityEvent.risk_score)).where(
                    SecurityEvent.created_at >= start_date
                )
                avg_risk_score = await session.scalar(risk_query) or 0
                
                # Top des IP suspectes
                ip_query = select(
                    SecurityEvent.ip_address,
                    func.count(SecurityEvent.id).label('count'),
                    func.avg(SecurityEvent.risk_score).label('avg_risk')
                ).where(
                    and_(
                        SecurityEvent.created_at >= start_date,
                        SecurityEvent.risk_score > 50
                    )
                ).group_by(SecurityEvent.ip_address).order_by(
                    func.count(SecurityEvent.id).desc()
                ).limit(10)
                
                ip_result = await session.execute(ip_query)
                suspicious_ips = [
                    {
                        "ip_address": row[0],
                        "event_count": row[1],
                        "avg_risk_score": float(row[2])
                    }
                    for row in ip_result
                ]
                
                return {
                    "period_days": days,
                    "events_by_type": events_by_type,
                    "unresolved_anomalies": unresolved_anomalies,
                    "average_risk_score": float(avg_risk_score),
                    "suspicious_ips": suspicious_ips,
                    "total_events": sum(events_by_type.values()),
                    "generated_at": end_date.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Erreur calcul métriques de sécurité: {e}")
            return {}

# Instance globale du service
_security_audit_service: Optional[SecurityAuditService] = None

def get_security_audit_service() -> SecurityAuditService:
    """Factory pour obtenir l'instance du service d'audit de sécurité"""
    global _security_audit_service
    
    if _security_audit_service is None:
        _security_audit_service = SecurityAuditService()
    
    return _security_audit_service
