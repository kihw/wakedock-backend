# Monitoring Temps Réel - Documentation

## Vue d'ensemble

Le système de monitoring temps réel de WakeDock fournit une surveillance continue des performances des conteneurs Docker avec des alertes automatiques et un streaming WebSocket pour les interfaces utilisateur.

## Architecture

### Composants Principaux

1. **MetricsCollector** - Collecte les métriques des conteneurs
2. **WebSocketService** - Service de streaming temps réel
3. **MonitoringAPI** - API REST pour la gestion et les requêtes
4. **MonitoringDashboard** - Interface React pour la visualisation

### Flux de Données

```
Docker Stats API → MetricsCollector → Stockage Local + WebSocket → Frontend Dashboard
                                   ↓
                               Système d'Alertes
```

## Installation et Configuration

### Dépendances Backend

```bash
# Déjà incluses dans requirements.txt
aiofiles>=23.0.0
aiosqlite>=0.19.0
websockets>=11.0.0
```

### Configuration

```python
# Configuration des seuils par défaut
THRESHOLDS = {
    "cpu_percent": {"warning": 70.0, "critical": 90.0},
    "memory_percent": {"warning": 80.0, "critical": 95.0},
    "network_rx": {"warning": 100MB/s, "critical": 500MB/s},
    "network_tx": {"warning": 100MB/s, "critical": 500MB/s}
}

# Configuration du collecteur
COLLECTION_INTERVAL = 5  # secondes
RETENTION_DAYS = 7       # jours
STORAGE_PATH = "/var/log/wakedock/metrics"
```

## API REST

### Endpoints Principaux

#### Statut du Monitoring

```http
GET /api/v1/monitoring/status
```

**Réponse:**
```json
{
  "monitoring": {
    "is_running": true,
    "monitored_containers": 5,
    "collection_interval": 5,
    "retention_days": 7
  },
  "websocket": {
    "active_connections": 2,
    "total_connections": 15,
    "messages_sent": 1250
  }
}
```

#### Démarrage/Arrêt

```http
POST /api/v1/monitoring/start
POST /api/v1/monitoring/stop
```

#### Récupération des Métriques

```http
GET /api/v1/monitoring/metrics?container_id=abc123&hours=1&limit=1000
```

**Paramètres:**
- `container_id` (optionnel) - ID du conteneur spécifique
- `service_name` (optionnel) - Nom du service Docker Compose
- `hours` (défaut: 1) - Nombre d'heures à récupérer
- `limit` (défaut: 1000) - Limite de résultats

**Réponse:**
```json
[
  {
    "container_id": "abc123",
    "container_name": "web-server",
    "service_name": "web",
    "timestamp": "2025-01-16T10:30:00Z",
    "cpu_percent": 25.5,
    "memory_usage": 536870912,
    "memory_limit": 1073741824,
    "memory_percent": 50.0,
    "network_rx_bytes": 1048576,
    "network_tx_bytes": 2097152,
    "pids": 15
  }
]
```

#### Requête Avancée

```http
POST /api/v1/monitoring/metrics/query
Content-Type: application/json

{
  "container_id": "abc123",
  "service_name": "web",
  "hours": 24,
  "limit": 5000
}
```

#### Alertes

```http
GET /api/v1/monitoring/alerts?level=critical&hours=24
```

**Réponse:**
```json
[
  {
    "container_id": "abc123",
    "container_name": "web-server",
    "timestamp": "2025-01-16T10:30:00Z",
    "level": "critical",
    "metric_type": "cpu_percent",
    "value": 95.0,
    "threshold": 90.0,
    "message": "CPU critique: 95.0% (seuil: 90%)"
  }
]
```

#### Configuration des Seuils

```http
GET /api/v1/monitoring/thresholds
PUT /api/v1/monitoring/thresholds/cpu_percent
Content-Type: application/json

{
  "metric_type": "cpu_percent",
  "warning_threshold": 75.0,
  "critical_threshold": 90.0,
  "enabled": true
}
```

#### Conteneurs Monitorés

```http
GET /api/v1/monitoring/containers
```

**Réponse:**
```json
{
  "containers": [
    {
      "container_id": "abc123",
      "container_name": "web-server",
      "service_name": "web",
      "last_update": "2025-01-16T10:30:00Z",
      "cpu_percent": 25.5,
      "memory_percent": 50.0,
      "network_rx_mb": 1.0,
      "network_tx_mb": 2.0
    }
  ]
}
```

## WebSocket API

### Connexion

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/monitoring/ws');
```

### Messages

#### Abonnement aux Métriques

```json
{
  "action": "subscribe",
  "stream_type": "metrics",
  "filters": {
    "container_ids": ["abc123", "def456"],
    "service_names": ["web", "db"]
  }
}
```

#### Abonnement aux Alertes

```json
{
  "action": "subscribe",
  "stream_type": "alerts",
  "filters": {
    "alert_levels": ["warning", "critical"]
  }
}
```

#### Abonnement au Statut Système

```json
{
  "action": "subscribe",
  "stream_type": "system_status"
}
```

### Messages Reçus

#### Mise à Jour de Métriques

```json
{
  "type": "metrics_update",
  "timestamp": "2025-01-16T10:30:00Z",
  "data": {
    "container_id": "abc123",
    "cpu_percent": 25.5,
    "memory_percent": 50.0,
    // ... autres métriques
  }
}
```

#### Alerte

```json
{
  "type": "alert",
  "timestamp": "2025-01-16T10:30:00Z",
  "data": {
    "level": "critical",
    "message": "CPU critique: 95.0%",
    "container_name": "web-server"
  }
}
```

## Interface Frontend

### Composant MonitoringDashboard

```tsx
import MonitoringDashboard from '@/components/monitoring/MonitoringDashboard';

function App() {
  return <MonitoringDashboard />;
}
```

### Fonctionnalités

- **Métriques en temps réel** - CPU, mémoire, réseau
- **Graphiques historiques** - Courbes de performance
- **Alertes visuelles** - Notifications en temps réel
- **Filtrage par conteneur** - Vue spécifique ou globale
- **Export de données** - Sauvegarde JSON
- **Contrôles de monitoring** - Start/Stop/Configuration

### Utilisation

1. Le dashboard se connecte automatiquement via WebSocket
2. S'abonne aux flux de métriques et d'alertes
3. Affiche les données en temps réel avec mise à jour automatique
4. Permet la configuration des seuils d'alerte
5. Exporte les données historiques

## Stockage des Données

### Format de Fichiers

#### Métriques (`metrics_YYYY-MM-DD.jsonl`)

```json
{"container_id":"abc123","timestamp":"2025-01-16T10:30:00Z","cpu_percent":25.5}
{"container_id":"def456","timestamp":"2025-01-16T10:30:01Z","cpu_percent":15.2}
```

#### Alertes (`alerts_YYYY-MM-DD.jsonl`)

```json
{"container_id":"abc123","level":"warning","message":"CPU élevé","timestamp":"2025-01-16T10:30:00Z"}
```

### Rétention

- **Métriques**: 7 jours par défaut (configurable)
- **Alertes**: 7 jours par défaut (configurable)
- **Nettoyage automatique**: Une fois par jour

## Performance et Optimisation

### Collecte de Métriques

- **Intervalle**: 5 secondes (configurable)
- **Traitement asynchrone**: Évite le blocage
- **Bufferisation**: Optimise les écritures disque
- **Gestion d'erreurs**: Continue malgré les conteneurs défaillants

### WebSocket

- **Ping/Pong**: Maintient les connexions
- **Filtrage côté serveur**: Réduit le trafic
- **Limite de clients**: 100 connexions simultanées
- **Timeout automatique**: 60 secondes d'inactivité

### Stockage

- **Format JSONL**: Efficace pour l'append
- **Rotation des fichiers**: 50MB maximum par fichier
- **Compression**: Gzip des anciens fichiers (à implémenter)

## Monitoring et Troubleshooting

### Logs du Système

```python
import logging
logger = logging.getLogger('wakedock.monitoring')

# Niveaux de log utiles
logger.info("Monitoring started")
logger.warning("Container connection lost")
logger.error("Failed to collect metrics")
```

### Métriques de Santé

```http
GET /api/v1/monitoring/statistics
```

**Indicateurs clés:**
- Taux de collecte réussie
- Latence moyenne des requêtes
- Nombre d'alertes par heure
- Utilisation mémoire du collecteur

### Problèmes Courants

#### Le monitoring ne démarre pas

1. Vérifier les permissions Docker
2. Vérifier l'espace disque disponible
3. Consulter les logs d'erreur

#### Perte de connexion WebSocket

1. Vérifier la configuration du reverse proxy
2. Ajuster les timeouts
3. Vérifier les limites de connexions

#### Métriques manquantes

1. Vérifier que les conteneurs sont actifs
2. Vérifier les permissions de lecture Docker
3. Consulter les logs du collecteur

## Tests

### Tests Unitaires

```bash
# Tests du collecteur
pytest tests/test_realtime_monitoring.py::TestMetricsCollector -v

# Tests WebSocket
pytest tests/test_realtime_monitoring.py::TestWebSocketService -v

# Tests d'intégration
pytest tests/test_realtime_monitoring.py::TestMonitoringIntegration -v
```

### Tests d'API

```bash
# Tests des routes REST
pytest tests/test_monitoring_api.py -v
```

### Tests Frontend

```bash
# Tests du dashboard
npm test -- MonitoringDashboard.test.tsx
```

## Configuration Avancée

### Variables d'Environnement

```bash
# Collecteur
WAKEDOCK_METRICS_INTERVAL=5
WAKEDOCK_METRICS_RETENTION_DAYS=7
WAKEDOCK_METRICS_STORAGE_PATH=/var/log/wakedock/metrics

# WebSocket
WAKEDOCK_WS_MAX_CLIENTS=100
WAKEDOCK_WS_PING_INTERVAL=30
WAKEDOCK_WS_CLIENT_TIMEOUT=60

# Seuils par défaut
WAKEDOCK_CPU_WARNING_THRESHOLD=70.0
WAKEDOCK_CPU_CRITICAL_THRESHOLD=90.0
WAKEDOCK_MEMORY_WARNING_THRESHOLD=80.0
WAKEDOCK_MEMORY_CRITICAL_THRESHOLD=95.0
```

### Configuration Programmatique

```python
from wakedock.core.metrics_collector import MetricsCollector, MetricType

# Personnaliser les seuils
collector.update_threshold(
    MetricType.CPU_PERCENT,
    warning=85.0,
    critical=95.0,
    enabled=True
)

# Ajouter des callbacks d'alerte
async def custom_alert_handler(alert):
    # Envoyer notification Slack, email, etc.
    pass

collector.add_alert_callback(custom_alert_handler)
```

## Sécurité

### Authentification WebSocket

- Utiliser les tokens JWT pour l'authentification
- Valider les permissions par conteneur
- Implémenter rate limiting

### Protection des Données

- Chiffrer les métriques sensibles
- Anonymiser les données personnelles
- Audit trail des accès

### Réseau

- Utiliser HTTPS/WSS en production
- Configurer CORS correctement
- Firewall pour les ports WebSocket

## Évolutions Futures

### Version 0.2.3 - Alertes Avancées

- Notifications par email/Slack
- Corrélation d'alertes
- Escalade automatique
- Maintenance programmée

### Version 0.2.4 - Analytics

- Prédiction de tendances
- Détection d'anomalies
- Rapports automatisés
- Dashboards personnalisables

### Version 0.3.x - Multi-Host

- Monitoring distribué
- Agrégation cross-cluster
- Haute disponibilité
- Réplication des données
