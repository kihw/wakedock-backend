# Système d'Alertes et Notifications WakeDock

## Vue d'ensemble

Le système d'alertes et notifications de WakeDock permet de surveiller automatiquement vos conteneurs Docker et d'envoyer des notifications en temps réel lorsque des seuils critiques sont atteints.

## Architecture

### Composants principaux

1. **AlertsService** : Service principal de gestion des alertes
2. **NotificationTarget** : Configuration des canaux de notification  
3. **AlertRule** : Règles de déclenchement d'alertes
4. **AlertInstance** : Instance d'alerte déclenchée
5. **API Routes** : Endpoints REST pour la gestion
6. **Dashboard React** : Interface de gestion des alertes

### Workflow d'alertes

```mermaid
graph TD
    A[Collecte Métriques] --> B[Évaluation Règles]
    B --> C{Seuil Dépassé?}
    C -->|Non| A
    C -->|Oui| D[Création Alerte]
    D --> E[Envoi Notifications]
    E --> F[Escalade Auto]
    F --> G[Résolution/Acquittement]
```

## Configuration

### Variables d'environnement

```env
# Configuration des alertes
WAKEDOCK_ALERTS_ENABLED=true
WAKEDOCK_ALERTS_STORAGE_PATH=/var/log/wakedock/alerts
WAKEDOCK_ALERTS_EVALUATION_INTERVAL=30

# Configuration SMTP pour notifications email
WAKEDOCK_SMTP_HOST=smtp.example.com
WAKEDOCK_SMTP_PORT=587
WAKEDOCK_SMTP_USERNAME=alerts@example.com
WAKEDOCK_SMTP_PASSWORD=password
WAKEDOCK_SMTP_TLS=true
WAKEDOCK_SMTP_SENDER_NAME=WakeDock Alerts
```

### Démarrage du service

```python
from wakedock.core.alerts_service import AlertsService
from wakedock.core.metrics_collector import MetricsCollector

# Initialisation
metrics_collector = MetricsCollector(docker_client)
alerts_service = AlertsService(
    metrics_collector=metrics_collector,
    storage_path="/var/log/wakedock/alerts"
)

# Démarrage
await alerts_service.start()
```

## Utilisation

### 1. Configuration des cibles de notification

#### Email
```python
email_target = NotificationTarget(
    channel=NotificationChannel.EMAIL,
    name="Admin Email",
    enabled=True,
    email_address="admin@example.com"
)

await alerts_service.add_notification_target(email_target)
```

#### Slack
```python
slack_target = NotificationTarget(
    channel=NotificationChannel.SLACK,
    name="DevOps Channel",
    enabled=True,
    slack_webhook_url="https://hooks.slack.com/services/...",
    slack_channel="#alerts"
)

await alerts_service.add_notification_target(slack_target)
```

#### Webhook
```python
webhook_target = NotificationTarget(
    channel=NotificationChannel.WEBHOOK,
    name="Monitoring System",
    enabled=True,
    webhook_url="https://monitoring.example.com/webhook",
    webhook_headers={
        "Authorization": "Bearer token123",
        "Content-Type": "application/json"
    }
)

await alerts_service.add_notification_target(webhook_target)
```

#### Discord
```python
discord_target = NotificationTarget(
    channel=NotificationChannel.DISCORD,
    name="Server Alerts",
    enabled=True,
    discord_webhook_url="https://discord.com/api/webhooks/..."
)

await alerts_service.add_notification_target(discord_target)
```

#### Microsoft Teams
```python
teams_target = NotificationTarget(
    channel=NotificationChannel.TEAMS,
    name="IT Team",
    enabled=True,
    teams_webhook_url="https://outlook.office.com/webhook/..."
)

await alerts_service.add_notification_target(teams_target)
```

#### Telegram
```python
telegram_target = NotificationTarget(
    channel=NotificationChannel.TELEGRAM,
    name="Admin Bot",
    enabled=True,
    telegram_bot_token="1234567890:ABC-DEF...",
    telegram_chat_id="-1001234567890"
)

await alerts_service.add_notification_target(telegram_target)
```

### 2. Création de règles d'alertes

#### Alerte CPU critique
```python
cpu_rule = AlertRule(
    rule_id="high_cpu_usage",
    name="High CPU Usage",
    description="Alert when container CPU exceeds 80%",
    enabled=True,
    
    # Conditions de déclenchement
    metric_type="cpu_percent",
    threshold_value=80.0,
    comparison_operator=">",
    duration_minutes=5,
    
    # Filtres (optionnels)
    container_filters={"name": "web-.*"},  # Regex sur le nom
    service_filters=["web", "api"],
    
    # Configuration
    severity=AlertSeverity.HIGH,
    notification_targets=["email_admin", "slack_devops"],
    
    # Escalade
    escalation_enabled=True,
    escalation_delay_minutes=30,
    escalation_targets={
        EscalationLevel.LEVEL_1: ["email_admin"],
        EscalationLevel.LEVEL_2: ["slack_devops", "email_manager"],
        EscalationLevel.LEVEL_3: ["email_cto", "teams_emergency"]
    },
    
    # Suppression des doublons
    suppression_enabled=True,
    suppression_duration_minutes=60,
    grouping_keys=["service_name", "metric_type"]
)

await alerts_service.add_alert_rule(cpu_rule)
```

#### Alerte mémoire critique
```python
memory_rule = AlertRule(
    rule_id="high_memory_usage",
    name="High Memory Usage",
    description="Alert when container memory exceeds 90%",
    metric_type="memory_percent",
    threshold_value=90.0,
    comparison_operator=">",
    duration_minutes=3,
    severity=AlertSeverity.CRITICAL,
    notification_targets=["email_admin", "slack_devops"]
)

await alerts_service.add_alert_rule(memory_rule)
```

#### Alerte réseau
```python
network_rule = AlertRule(
    rule_id="high_network_traffic",
    name="High Network Traffic",
    description="Alert when network traffic exceeds 1GB/hour",
    metric_type="network_total_bytes",
    threshold_value=1073741824,  # 1GB en bytes
    comparison_operator=">",
    duration_minutes=60,
    severity=AlertSeverity.MEDIUM,
    notification_targets=["email_admin"]
)

await alerts_service.add_alert_rule(network_rule)
```

### 3. Gestion des alertes

#### Acquittement d'une alerte
```python
success = await alerts_service.acknowledge_alert(
    alert_id="alert_123",
    acknowledged_by="admin_user"
)
```

#### Récupération des alertes actives
```python
active_alerts = alerts_service.get_active_alerts()
for alert in active_alerts:
    print(f"Alerte: {alert.rule_name}")
    print(f"Conteneur: {alert.container_name}")
    print(f"Sévérité: {alert.severity}")
    print(f"Valeur: {alert.current_value}")
```

#### Historique des alertes
```python
history = await alerts_service.get_alerts_history(days=7)
```

### 4. Test des notifications

```python
# Test d'une cible de notification
success = await alerts_service.test_notification_target("email_admin")
```

## API REST

### Endpoints principaux

#### Règles d'alertes
- `GET /api/v1/alerts/rules` - Liste des règles
- `POST /api/v1/alerts/rules` - Création d'une règle
- `GET /api/v1/alerts/rules/{rule_id}` - Détails d'une règle
- `PUT /api/v1/alerts/rules/{rule_id}` - Mise à jour
- `DELETE /api/v1/alerts/rules/{rule_id}` - Suppression
- `POST /api/v1/alerts/rules/{rule_id}/test` - Test d'une règle

#### Cibles de notification
- `GET /api/v1/alerts/targets` - Liste des cibles
- `POST /api/v1/alerts/targets` - Création d'une cible
- `POST /api/v1/alerts/targets/{target_id}/test` - Test d'une cible

#### Alertes
- `GET /api/v1/alerts/active` - Alertes actives
- `GET /api/v1/alerts/history` - Historique
- `POST /api/v1/alerts/acknowledge/{alert_id}` - Acquittement
- `POST /api/v1/alerts/bulk-action` - Actions en lot

#### Statistiques
- `GET /api/v1/alerts/stats` - Statistiques globales
- `GET /api/v1/alerts/metrics` - Métriques temporelles

#### Service
- `GET /api/v1/alerts/service/status` - Statut du service
- `POST /api/v1/alerts/service/restart` - Redémarrage

### Exemples d'utilisation API

#### Création d'une règle via API
```bash
curl -X POST "http://localhost:8000/api/v1/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High CPU Alert",
    "description": "Alert when CPU exceeds 80%",
    "metric_type": "cpu_percent",
    "threshold_value": 80.0,
    "comparison_operator": ">",
    "duration_minutes": 5,
    "severity": "high",
    "notification_targets": ["email_admin"]
  }'
```

#### Création d'une cible email
```bash
curl -X POST "http://localhost:8000/api/v1/alerts/targets" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "name": "Admin Email",
    "enabled": true,
    "email_address": "admin@example.com"
  }'
```

#### Acquittement d'une alerte
```bash
curl -X POST "http://localhost:8000/api/v1/alerts/acknowledge/alert_123" \
  -H "Content-Type: application/json" \
  -d '{
    "acknowledged_by": "admin_user"
  }'
```

## Interface Web

Le dashboard React offre une interface complète pour :

### Vue d'ensemble
- Statistiques globales des alertes
- Répartition par sévérité et état
- Règles les plus déclenchées
- Conteneurs les plus affectés

### Gestion des alertes actives
- Liste des alertes en cours
- Filtrage par sévérité, règle, conteneur
- Acquittement direct
- Actions en lot

### Configuration des règles
- Création/modification de règles
- Test des règles avec des données simulées
- Activation/désactivation
- Configuration de l'escalade

### Gestion des notifications
- Configuration des canaux
- Test des notifications
- Historique des envois

### Historique et rapports
- Historique complet des alertes
- Export en JSON/CSV
- Métriques et tendances

## Bonnes pratiques

### 1. Configuration des seuils

- **CPU** : 80% pour HIGH, 90% pour CRITICAL
- **Mémoire** : 85% pour HIGH, 95% pour CRITICAL
- **Disque** : 80% pour MEDIUM, 90% pour HIGH
- **Réseau** : Adapter selon l'usage attendu

### 2. Durée avant déclenchement

- **Alertes critiques** : 2-5 minutes
- **Alertes importantes** : 5-10 minutes
- **Alertes informatives** : 10-30 minutes

### 3. Escalade

```python
escalation_targets = {
    EscalationLevel.LEVEL_1: ["email_admin", "slack_ops"],
    EscalationLevel.LEVEL_2: ["email_manager", "slack_leads"],
    EscalationLevel.LEVEL_3: ["email_oncall", "teams_emergency"]
}
```

### 4. Suppression des doublons

- Activer pour éviter le spam
- Durée de 30-60 minutes selon le type d'alerte
- Grouper par service et type de métrique

### 5. Filtres de conteneurs

```python
# Production seulement
container_filters = {"name": "prod-.*"}

# Services critiques
service_filters = ["web", "api", "database"]

# Exclusion des conteneurs temporaires
container_filters = {"name": "^(?!temp-|test-).*"}
```

## Dépannage

### Problèmes courants

#### Les alertes ne se déclenchent pas
1. Vérifier que le service est démarré
2. Contrôler les logs du service
3. Vérifier les filtres de conteneurs
4. Tester les seuils avec des métriques actuelles

#### Notifications non reçues
1. Tester la cible de notification
2. Vérifier la configuration (SMTP, webhooks)
3. Contrôler les logs d'envoi
4. Vérifier les filtres anti-spam

#### Performance dégradée
1. Réduire la fréquence d'évaluation
2. Optimiser les filtres de conteneurs
3. Limiter l'historique des métriques
4. Configurer la suppression des doublons

### Logs et monitoring

```python
# Activation des logs debug
import logging
logging.getLogger("wakedock.core.alerts_service").setLevel(logging.DEBUG)

# Métriques du service
stats = alerts_service.get_service_stats()
print(f"Alertes actives: {stats['active_alerts_count']}")
print(f"Règles configurées: {stats['alert_rules_count']}")
```

### Configuration de monitoring

```yaml
# prometheus.yml
- job_name: 'wakedock-alerts'
  static_configs:
    - targets: ['localhost:8000']
  metrics_path: '/api/v1/alerts/metrics'
```

## Intégrations

### Intégration avec Grafana

```json
{
  "dashboard": {
    "title": "WakeDock Alerts",
    "panels": [
      {
        "title": "Active Alerts",
        "type": "stat",
        "targets": [
          {
            "expr": "wakedock_active_alerts_total"
          }
        ]
      },
      {
        "title": "Alert Rate",
        "type": "graph", 
        "targets": [
          {
            "expr": "rate(wakedock_alerts_triggered_total[5m])"
          }
        ]
      }
    ]
  }
}
```

### Intégration avec PagerDuty

```python
pagerduty_target = NotificationTarget(
    channel=NotificationChannel.WEBHOOK,
    name="PagerDuty",
    webhook_url="https://events.pagerduty.com/v2/enqueue",
    webhook_headers={
        "Authorization": "Token token=YOUR_INTEGRATION_KEY",
        "Content-Type": "application/json"
    }
)
```

### Intégration avec Datadog

```python
datadog_target = NotificationTarget(
    channel=NotificationChannel.WEBHOOK,
    name="Datadog",
    webhook_url="https://api.datadoghq.com/api/v1/events",
    webhook_headers={
        "DD-API-KEY": "YOUR_API_KEY",
        "Content-Type": "application/json"
    }
)
```

## Sécurité

### Authentification des webhooks

```python
# Ajout d'un token d'authentification
webhook_target = NotificationTarget(
    channel=NotificationChannel.WEBHOOK,
    name="Secure Webhook",
    webhook_url="https://api.example.com/alerts",
    webhook_headers={
        "Authorization": "Bearer SECRET_TOKEN",
        "X-API-Key": "API_KEY"
    }
)
```

### Chiffrement des données sensibles

Les tokens et mots de passe sont automatiquement chiffrés dans la configuration stockée.

### Validation des entrées

Toutes les entrées utilisateur sont validées avec Pydantic pour éviter les injections.

## Performances

### Optimisations recommandées

1. **Indexation des métriques** : Index sur container_id et timestamp
2. **Rotation des logs** : Archivage automatique après 30 jours
3. **Cache des règles** : Mise en cache des évaluations fréquentes
4. **Batch des notifications** : Regroupement des notifications similaires

### Métriques de performance

- Temps d'évaluation des règles : < 100ms
- Temps d'envoi des notifications : < 5s
- Utilisation mémoire : < 200MB
- Débit maximum : 1000 métriques/seconde

Cette documentation fournit une base complète pour l'utilisation du système d'alertes WakeDock. Pour des cas d'usage spécifiques, consultez les exemples dans le code ou contactez l'équipe de développement.
