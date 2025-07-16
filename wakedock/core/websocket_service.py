"""
Service WebSocket pour le streaming temps réel des métriques de monitoring
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum
import weakref

from wakedock.core.metrics_collector import MetricsCollector, ContainerMetrics, Alert

logger = logging.getLogger(__name__)

class StreamType(Enum):
    """Types de flux WebSocket"""
    METRICS = "metrics"
    ALERTS = "alerts"
    SYSTEM_STATUS = "system_status"

class MessageType(Enum):
    """Types de messages WebSocket"""
    METRICS_UPDATE = "metrics_update"
    ALERT = "alert"
    STATUS_UPDATE = "status_update"
    SUBSCRIPTION_ACK = "subscription_ack"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

class WebSocketMessage:
    """Message WebSocket structuré"""
    
    def __init__(self, message_type: MessageType, data: Any, timestamp: Optional[datetime] = None):
        self.type = message_type
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convertit en JSON"""
        return json.dumps(self.to_dict())

class ClientConnection:
    """Représente une connexion WebSocket client"""
    
    def __init__(self, websocket: WebSocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.subscriptions: Set[StreamType] = set()
        self.filters: Dict[str, Any] = {}
        self.last_ping = datetime.utcnow()
        self.is_active = True
    
    async def send_message(self, message: WebSocketMessage):
        """Envoie un message au client"""
        try:
            await self.websocket.send_text(message.to_json())
        except Exception as e:
            logger.warning(f"Erreur lors de l'envoi du message au client {self.client_id}: {e}")
            self.is_active = False
    
    async def send_error(self, error_message: str):
        """Envoie un message d'erreur"""
        message = WebSocketMessage(MessageType.ERROR, {'message': error_message})
        await self.send_message(message)
    
    def subscribe(self, stream_type: StreamType, filters: Optional[Dict] = None):
        """S'abonne à un flux"""
        self.subscriptions.add(stream_type)
        if filters:
            self.filters[stream_type.value] = filters
        logger.debug(f"Client {self.client_id} s'abonne à {stream_type.value}")
    
    def unsubscribe(self, stream_type: StreamType):
        """Se désabonne d'un flux"""
        self.subscriptions.discard(stream_type)
        self.filters.pop(stream_type.value, None)
        logger.debug(f"Client {self.client_id} se désabonne de {stream_type.value}")
    
    def is_subscribed_to(self, stream_type: StreamType) -> bool:
        """Vérifie si le client est abonné à un flux"""
        return stream_type in self.subscriptions
    
    def matches_filters(self, stream_type: StreamType, data: Dict) -> bool:
        """Vérifie si les données correspondent aux filtres du client"""
        filters = self.filters.get(stream_type.value, {})
        if not filters:
            return True
        
        # Filtre par conteneur
        container_filter = filters.get('container_ids')
        if container_filter:
            container_id = data.get('container_id')
            if container_id not in container_filter:
                return False
        
        # Filtre par service
        service_filter = filters.get('service_names')
        if service_filter:
            service_name = data.get('service_name')
            if service_name not in service_filter:
                return False
        
        # Filtre par niveau d'alerte (pour les alertes)
        if stream_type == StreamType.ALERTS:
            level_filter = filters.get('alert_levels')
            if level_filter:
                alert_level = data.get('level')
                if alert_level not in level_filter:
                    return False
        
        return True

class MetricsWebSocketService:
    """Service WebSocket pour le streaming des métriques"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.clients: Dict[str, ClientConnection] = {}
        self.is_running = False
        
        # Configuration
        self.ping_interval = 30  # secondes
        self.client_timeout = 60  # secondes
        self.max_clients = 100
        
        # Tâches de fond
        self.broadcast_task: Optional[asyncio.Task] = None
        self.ping_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Buffers pour optimiser les broadcasts
        self.metrics_buffer: List[ContainerMetrics] = []
        self.alerts_buffer: List[Alert] = []
        self.buffer_flush_interval = 1  # seconde
        
        # Statistiques
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'errors': 0
        }
    
    async def start(self):
        """Démarre le service WebSocket"""
        if self.is_running:
            return
        
        logger.info("Démarrage du service WebSocket de métriques")
        self.is_running = True
        
        # Démarre les tâches de fond
        self.broadcast_task = asyncio.create_task(self._broadcast_worker())
        self.ping_task = asyncio.create_task(self._ping_worker())
        self.cleanup_task = asyncio.create_task(self._cleanup_worker())
        
        # Enregistre les callbacks pour les métriques
        self.metrics_collector.add_alert_callback(self._on_alert)
    
    async def stop(self):
        """Arrête le service WebSocket"""
        if not self.is_running:
            return
        
        logger.info("Arrêt du service WebSocket de métriques")
        self.is_running = False
        
        # Arrête les tâches
        if self.broadcast_task:
            self.broadcast_task.cancel()
        if self.ping_task:
            self.ping_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Ferme toutes les connexions
        for client in list(self.clients.values()):
            await self._disconnect_client(client.client_id)
        
        # Retire les callbacks
        self.metrics_collector.remove_alert_callback(self._on_alert)
    
    async def handle_client_connection(self, websocket: WebSocket, client_id: str):
        """Gère une nouvelle connexion WebSocket"""
        try:
            # Vérifie la limite de clients
            if len(self.clients) >= self.max_clients:
                await websocket.close(code=1008, reason="Trop de connexions")
                return
            
            # Accepte la connexion
            await websocket.accept()
            
            # Crée le client
            client = ClientConnection(websocket, client_id)
            self.clients[client_id] = client
            
            self.stats['total_connections'] += 1
            self.stats['active_connections'] += 1
            
            logger.info(f"Nouvelle connexion WebSocket: {client_id}")
            
            # Envoie le message de bienvenue
            welcome_message = WebSocketMessage(
                MessageType.STATUS_UPDATE,
                {
                    'status': 'connected',
                    'client_id': client_id,
                    'available_streams': [stream.value for stream in StreamType]
                }
            )
            await client.send_message(welcome_message)
            
            # Gère les messages du client
            await self._handle_client_messages(client)
            
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} déconnecté")
        except Exception as e:
            logger.error(f"Erreur lors de la gestion du client {client_id}: {e}")
            self.stats['errors'] += 1
        finally:
            await self._disconnect_client(client_id)
    
    async def _handle_client_messages(self, client: ClientConnection):
        """Gère les messages reçus d'un client"""
        try:
            while client.is_active and self.is_running:
                # Reçoit le message
                message_text = await client.websocket.receive_text()
                
                try:
                    message_data = json.loads(message_text)
                    await self._process_client_message(client, message_data)
                except json.JSONDecodeError:
                    await client.send_error("Message JSON invalide")
                except Exception as e:
                    logger.warning(f"Erreur lors du traitement du message: {e}")
                    await client.send_error(f"Erreur de traitement: {str(e)}")
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Erreur dans la gestion des messages client {client.client_id}: {e}")
    
    async def _process_client_message(self, client: ClientConnection, message_data: Dict):
        """Traite un message reçu du client"""
        action = message_data.get('action')
        
        if action == 'subscribe':
            stream_type_str = message_data.get('stream_type')
            filters = message_data.get('filters', {})
            
            try:
                stream_type = StreamType(stream_type_str)
                client.subscribe(stream_type, filters)
                
                # Envoie l'ACK
                ack_message = WebSocketMessage(
                    MessageType.SUBSCRIPTION_ACK,
                    {
                        'stream_type': stream_type.value,
                        'subscribed': True,
                        'filters': filters
                    }
                )
                await client.send_message(ack_message)
                
                # Envoie les données récentes si disponibles
                await self._send_recent_data(client, stream_type)
                
            except ValueError:
                await client.send_error(f"Type de flux invalide: {stream_type_str}")
        
        elif action == 'unsubscribe':
            stream_type_str = message_data.get('stream_type')
            
            try:
                stream_type = StreamType(stream_type_str)
                client.unsubscribe(stream_type)
                
                ack_message = WebSocketMessage(
                    MessageType.SUBSCRIPTION_ACK,
                    {
                        'stream_type': stream_type.value,
                        'subscribed': False
                    }
                )
                await client.send_message(ack_message)
                
            except ValueError:
                await client.send_error(f"Type de flux invalide: {stream_type_str}")
        
        elif action == 'ping':
            client.last_ping = datetime.utcnow()
            pong_message = WebSocketMessage(MessageType.PONG, {'timestamp': datetime.utcnow().isoformat()})
            await client.send_message(pong_message)
        
        else:
            await client.send_error(f"Action non reconnue: {action}")
    
    async def _send_recent_data(self, client: ClientConnection, stream_type: StreamType):
        """Envoie les données récentes au client"""
        try:
            if stream_type == StreamType.METRICS:
                # Envoie les métriques récentes (dernières 5 minutes)
                recent_metrics = await self.metrics_collector.get_recent_metrics(hours=0.083, limit=50)
                for metrics in recent_metrics:
                    if client.matches_filters(stream_type, metrics.to_dict()):
                        message = WebSocketMessage(
                            MessageType.METRICS_UPDATE,
                            metrics.to_dict()
                        )
                        await client.send_message(message)
            
            elif stream_type == StreamType.ALERTS:
                # Envoie les alertes récentes (dernière heure)
                recent_alerts = await self.metrics_collector.get_recent_alerts(hours=1, limit=20)
                for alert in recent_alerts:
                    if client.matches_filters(stream_type, alert.to_dict()):
                        message = WebSocketMessage(
                            MessageType.ALERT,
                            alert.to_dict()
                        )
                        await client.send_message(message)
            
            elif stream_type == StreamType.SYSTEM_STATUS:
                # Envoie le statut système
                status_data = {
                    'monitoring_active': self.metrics_collector.is_running,
                    'monitored_containers': len(self.metrics_collector.monitored_containers),
                    'collector_stats': self.metrics_collector.get_stats(),
                    'websocket_stats': self.get_stats()
                }
                message = WebSocketMessage(
                    MessageType.STATUS_UPDATE,
                    status_data
                )
                await client.send_message(message)
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des données récentes: {e}")
    
    async def _disconnect_client(self, client_id: str):
        """Déconnecte un client"""
        client = self.clients.pop(client_id, None)
        if client:
            self.stats['active_connections'] -= 1
            try:
                if not client.websocket.client_state.DISCONNECTED:
                    await client.websocket.close()
            except Exception as e:
                logger.debug(f"Erreur lors de la fermeture de la connexion {client_id}: {e}")
    
    async def _broadcast_worker(self):
        """Worker de diffusion des métriques"""
        while self.is_running:
            try:
                # Récupère les métriques récentes
                recent_metrics = await self.metrics_collector.get_recent_metrics(hours=0.01, limit=100)
                
                # Diffuse les nouvelles métriques
                for metrics in recent_metrics:
                    await self._broadcast_metrics(metrics)
                
                # Diffuse le statut système périodiquement
                await self._broadcast_system_status()
                
                # Attend avant la prochaine diffusion
                await asyncio.sleep(self.buffer_flush_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de diffusion: {e}")
                await asyncio.sleep(self.buffer_flush_interval)
    
    async def _broadcast_metrics(self, metrics: ContainerMetrics):
        """Diffuse les métriques à tous les clients abonnés"""
        if not self.clients:
            return
        
        message = WebSocketMessage(MessageType.METRICS_UPDATE, metrics.to_dict())
        
        # Diffuse aux clients abonnés aux métriques
        disconnected_clients = []
        for client in self.clients.values():
            if client.is_subscribed_to(StreamType.METRICS) and client.matches_filters(StreamType.METRICS, metrics.to_dict()):
                try:
                    await client.send_message(message)
                    self.stats['messages_sent'] += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de l'envoi à {client.client_id}: {e}")
                    disconnected_clients.append(client.client_id)
        
        # Nettoie les clients déconnectés
        for client_id in disconnected_clients:
            await self._disconnect_client(client_id)
    
    async def _on_alert(self, alert: Alert):
        """Callback appelé lors d'une nouvelle alerte"""
        if not self.clients:
            return
        
        message = WebSocketMessage(MessageType.ALERT, alert.to_dict())
        
        # Diffuse aux clients abonnés aux alertes
        disconnected_clients = []
        for client in self.clients.values():
            if client.is_subscribed_to(StreamType.ALERTS) and client.matches_filters(StreamType.ALERTS, alert.to_dict()):
                try:
                    await client.send_message(message)
                    self.stats['messages_sent'] += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de l'envoi d'alerte à {client.client_id}: {e}")
                    disconnected_clients.append(client.client_id)
        
        # Nettoie les clients déconnectés
        for client_id in disconnected_clients:
            await self._disconnect_client(client_id)
    
    async def _broadcast_system_status(self):
        """Diffuse le statut système"""
        if not any(client.is_subscribed_to(StreamType.SYSTEM_STATUS) for client in self.clients.values()):
            return
        
        status_data = {
            'monitoring_active': self.metrics_collector.is_running,
            'monitored_containers': len(self.metrics_collector.monitored_containers),
            'collector_stats': self.metrics_collector.get_stats(),
            'websocket_stats': self.get_stats(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        message = WebSocketMessage(MessageType.STATUS_UPDATE, status_data)
        
        # Diffuse aux clients abonnés au statut
        disconnected_clients = []
        for client in self.clients.values():
            if client.is_subscribed_to(StreamType.SYSTEM_STATUS):
                try:
                    await client.send_message(message)
                    self.stats['messages_sent'] += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de l'envoi de statut à {client.client_id}: {e}")
                    disconnected_clients.append(client.client_id)
        
        # Nettoie les clients déconnectés
        for client_id in disconnected_clients:
            await self._disconnect_client(client_id)
    
    async def _ping_worker(self):
        """Worker de ping pour maintenir les connexions"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                disconnected_clients = []
                
                for client in self.clients.values():
                    # Vérifie le timeout
                    if (current_time - client.last_ping).total_seconds() > self.client_timeout:
                        logger.info(f"Client {client.client_id} en timeout")
                        disconnected_clients.append(client.client_id)
                        continue
                    
                    # Envoie un ping
                    try:
                        ping_message = WebSocketMessage(MessageType.PING, {'timestamp': current_time.isoformat()})
                        await client.send_message(ping_message)
                    except Exception as e:
                        logger.warning(f"Erreur lors du ping à {client.client_id}: {e}")
                        disconnected_clients.append(client.client_id)
                
                # Nettoie les clients déconnectés
                for client_id in disconnected_clients:
                    await self._disconnect_client(client_id)
                
                await asyncio.sleep(self.ping_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de ping: {e}")
                await asyncio.sleep(self.ping_interval)
    
    async def _cleanup_worker(self):
        """Worker de nettoyage"""
        while self.is_running:
            try:
                # Nettoie une fois par minute
                await asyncio.sleep(60)
                
                # Nettoie les clients inactifs
                inactive_clients = [
                    client_id for client_id, client in self.clients.items()
                    if not client.is_active
                ]
                
                for client_id in inactive_clients:
                    await self._disconnect_client(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de nettoyage: {e}")
    
    def get_stats(self) -> Dict:
        """Récupère les statistiques du service"""
        return {
            'is_running': self.is_running,
            'active_connections': len(self.clients),
            'total_connections': self.stats['total_connections'],
            'messages_sent': self.stats['messages_sent'],
            'errors': self.stats['errors'],
            'max_clients': self.max_clients,
            'ping_interval': self.ping_interval,
            'client_timeout': self.client_timeout
        }
    
    async def broadcast_custom_message(self, stream_type: StreamType, data: Dict):
        """Diffuse un message personnalisé"""
        if not self.clients:
            return
        
        # Détermine le type de message approprié
        message_type_map = {
            StreamType.METRICS: MessageType.METRICS_UPDATE,
            StreamType.ALERTS: MessageType.ALERT,
            StreamType.SYSTEM_STATUS: MessageType.STATUS_UPDATE
        }
        
        message_type = message_type_map.get(stream_type, MessageType.STATUS_UPDATE)
        message = WebSocketMessage(message_type, data)
        
        # Diffuse aux clients abonnés
        disconnected_clients = []
        for client in self.clients.values():
            if client.is_subscribed_to(stream_type) and client.matches_filters(stream_type, data):
                try:
                    await client.send_message(message)
                    self.stats['messages_sent'] += 1
                except Exception as e:
                    logger.warning(f"Erreur lors de l'envoi personnalisé à {client.client_id}: {e}")
                    disconnected_clients.append(client.client_id)
        
        # Nettoie les clients déconnectés
        for client_id in disconnected_clients:
            await self._disconnect_client(client_id)
