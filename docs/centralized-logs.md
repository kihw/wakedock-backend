# Système de Logs Centralisé

## Vue d'ensemble

Le système de logs centralisé de WakeDock fournit une solution complète pour la collecte, l'indexation, la recherche et la visualisation des logs de conteneurs Docker. Il permet un monitoring en temps réel avec des capacités de filtrage avancées et d'export.

## Architecture

### Composants principaux

1. **LogCollector** : Service de collecte des logs des conteneurs
2. **LogSearchService** : Service d'indexation et de recherche
3. **API Routes** : Points d'accès REST pour l'interface web
4. **Interface Web** : Composant React pour la visualisation

### Flux de données

```
Conteneurs Docker → LogCollector → Stockage fichiers → LogSearchService → Index SQLite → API → Interface Web
```

## Fonctionnalités

### Collecte de logs

- **Surveillance automatique** : Détection et surveillance automatique des conteneurs
- **Parsing intelligent** : Extraction automatique du niveau de log et des métadonnées
- **Mise en tampon** : Système de buffer pour optimiser les performances
- **Rotation automatique** : Gestion automatique de la rotation des fichiers de logs

### Recherche et filtrage

- **Recherche textuelle** : Recherche full-text dans les messages de logs
- **Filtrage avancé** : Par conteneur, service, niveau, période temporelle
- **Indexation SQLite** : Index optimisé pour des recherches rapides
- **Statistiques** : Analyses et métriques sur les logs

### Interface utilisateur

- **Visualisation temps réel** : Streaming des logs en direct
- **Filtres interactifs** : Interface intuitive pour affiner les recherches
- **Export multiple** : Export en JSON, CSV, TXT
- **Statistiques visuelles** : Tableaux de bord avec métriques clés

## Installation et Configuration

### Dépendances

```bash
# Backend
pip install aiosqlite aiofiles

# Base de données pour l'indexation
sqlite3
```

### Configuration

```python
# Configuration dans settings.py
CENTRALIZED_LOGS = {
    "storage_path": "/var/log/wakedock/containers",
    "db_path": "/var/log/wakedock/logs_index.db",
    "max_log_size": 100 * 1024 * 1024,  # 100MB
    "rotation_count": 5,
    "buffer_size": 1000,
    "flush_interval": 10  # secondes
}
```

## Utilisation

### Démarrage des services

```python
from wakedock.core.log_collector import LogCollector
from wakedock.core.log_search_service import LogSearchService
from wakedock.core.docker_manager import DockerManager

# Initialisation
docker_manager = DockerManager()
log_collector = LogCollector(docker_manager)
search_service = LogSearchService()

# Démarrage
await log_collector.start()
await search_service.start()
```

### API Usage

#### Recherche de logs

```bash
# Recherche textuelle
GET /api/v1/logs/search?query=error&limit=100

# Filtrage par conteneur
GET /api/v1/logs/search?container_id=abc123&level=error

# Recherche complexe (POST)
POST /api/v1/logs/search
{
  "query": "database connection",
  "container_id": "web-app",
  "level": "error",
  "start_time": "2024-01-01T00:00:00",
  "end_time": "2024-01-01T23:59:59",
  "limit": 500
}
```

#### Streaming temps réel

```bash
# Stream des logs en temps réel
GET /api/v1/logs/stream?follow=true&level=warn
```

#### Export de logs

```bash
# Export en différents formats
POST /api/v1/logs/export
{
  "format": "csv",
  "container_id": "web-app",
  "start_time": "2024-01-01T00:00:00",
  "limit": 10000
}
```

#### Statistiques

```bash
# Statistiques globales
GET /api/v1/logs/statistics

# Statut du collecteur
GET /api/v1/logs/status

# Statut de l'index
GET /api/v1/logs/index/status
```

### Interface Web

L'interface web est accessible via le composant `CentralizedLogsViewer` :

```tsx
import CentralizedLogsViewer from '@/components/logs/CentralizedLogsViewer';

function LogsPage() {
  return <CentralizedLogsViewer />;
}
```

## Modèles de données

### LogEntry

```python
@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel  # TRACE, DEBUG, INFO, WARN, ERROR, FATAL
    container_id: str
    container_name: str
    service_name: Optional[str]
    message: str
    source: str = "stdout"
    metadata: Dict = None
```

### Réponses API

#### LogSearchResponse

```json
{
  "logs": [LogEntry],
  "total_found": 1234,
  "search_time_ms": 45,
  "has_more": true
}
```

#### LogStatistics

```json
{
  "total_logs": 50000,
  "level_distribution": {
    "info": 35000,
    "warn": 10000,
    "error": 5000
  },
  "container_distribution": {
    "web-app": 30000,
    "database": 20000
  },
  "service_distribution": {
    "frontend": 25000,
    "backend": 25000
  },
  "timeline": {
    "2024-01-01 10:00:00": 1000,
    "2024-01-01 11:00:00": 1200
  }
}
```

## Performance et optimisation

### Indexation

- **Index SQLite** : Utilise SQLite pour l'indexation avec des index optimisés
- **Termes de recherche** : Extraction et indexation des termes significatifs
- **Filtrage des stop words** : Suppression des mots courants pour optimiser la taille
- **Indexation incrémentale** : Mise à jour automatique de l'index

### Stockage

- **Format JSONL** : Un log par ligne pour un parsing efficace
- **Rotation automatique** : Limite la taille des fichiers individuels
- **Compression** : Support pour la compression des anciens logs

### Mise en cache

- **Buffer en mémoire** : Tampon pour réduire les I/O disque
- **Flush périodique** : Vidage automatique des buffers
- **Batch processing** : Traitement par lots pour l'indexation

## Monitoring et maintenance

### Métriques

```python
# Statistiques du collecteur
collector_stats = collector.get_stats()
# {
#   'is_running': True,
#   'monitored_containers': 15,
#   'active_tasks': 15,
#   'buffered_logs': 2500,
#   'log_files': 45,
#   'storage_path': '/var/log/wakedock/containers'
# }

# Statistiques de l'index
index_stats = await search_service.get_index_stats()
# {
#   'total_indexed_logs': 100000,
#   'unique_search_terms': 15000,
#   'database_size_bytes': 50000000,
#   'is_running': True
# }
```

### Maintenance

```bash
# Reconstruction de l'index
POST /api/v1/logs/index/rebuild

# Nettoyage des anciens logs
DELETE /api/v1/logs/logs?days=30&dry_run=false
```

## Sécurité

### Contrôle d'accès

- **Authentification** : Intégration avec le système d'auth WakeDock
- **Autorisation** : Contrôle d'accès basé sur les rôles
- **Filtrage par conteneur** : Limitation de l'accès aux logs selon les permissions

### Données sensibles

- **Masquage automatique** : Détection et masquage des données sensibles
- **Rétention configurée** : Politiques de rétention automatique
- **Audit trail** : Traçabilité des accès aux logs

## Dépannage

### Problèmes courants

1. **Collecteur ne démarre pas**
   - Vérifier les permissions sur le répertoire de stockage
   - Contrôler la connexion Docker

2. **Indexation lente**
   - Vérifier l'espace disque disponible
   - Augmenter la taille des batches d'indexation

3. **Recherches lentes**
   - Reconstruire l'index si corrompu
   - Optimiser les requêtes de filtrage

4. **Logs manquants**
   - Vérifier que les conteneurs sont surveillés
   - Contrôler les logs d'erreur du collecteur

### Logs de diagnostic

```python
import logging
logging.getLogger('wakedock.core.log_collector').setLevel(logging.DEBUG)
logging.getLogger('wakedock.core.log_search_service').setLevel(logging.DEBUG)
```

## Exemples d'utilisation

### Surveillance des erreurs

```python
# Recherche d'erreurs récentes
async def check_recent_errors():
    search_service = get_search_service()
    results = await search_service.search_logs(
        level=LogLevel.ERROR,
        start_time=datetime.now() - timedelta(hours=1),
        limit=100
    )
    return results
```

### Export pour analyse

```python
# Export pour analyse externe
async def export_logs_for_analysis():
    request = ExportRequest(
        format="json",
        start_time=datetime.now() - timedelta(days=7),
        limit=50000
    )
    # ... traitement de l'export
```

### Alertes basées sur les logs

```python
# Système d'alerte
async def monitor_error_rate():
    stats = await search_service.get_log_statistics(
        start_time=datetime.now() - timedelta(minutes=5)
    )
    error_count = stats['level_distribution'].get('error', 0)
    if error_count > 10:
        send_alert(f"Taux d'erreur élevé: {error_count} erreurs")
```

## Roadmap

### Version actuelle (0.2.1)
- ✅ Collecte de logs centralisée
- ✅ Indexation et recherche
- ✅ Interface web de visualisation
- ✅ Export multiple formats
- ✅ Streaming temps réel

### Versions futures
- **0.2.2** : Alertes automatiques
- **0.2.3** : Intégration avec systèmes externes (Elasticsearch, Grafana)
- **0.2.4** : Machine learning pour détection d'anomalies
- **0.3.x** : Analyse prédictive et recommandations
