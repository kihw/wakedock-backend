# Déploiement WakeDock Backend

## Déploiement Docker

### Build de l'image
```bash
docker build -t wakedock-backend .
```

### Lancement avec Docker Compose
```bash
docker-compose up -d
```

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|---------|
| `DATABASE_URL` | URL de la base de données | `postgresql://...` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379` |
| `JWT_SECRET_KEY` | Clé secrète JWT | `your-secret-key` |
| `LOG_LEVEL` | Niveau de log | `INFO` |
| `CORS_ORIGINS` | Origines CORS autorisées | `["*"]` |

## Production

### Optimisations recommandées

1. **Base de données** : Utiliser PostgreSQL avec pool de connexions
2. **Cache** : Configurer Redis pour le cache
3. **Logs** : Centraliser avec un système de logs externe
4. **Monitoring** : Activer les métriques Prometheus
5. **Sécurité** : Configurer HTTPS et CORS appropriés

### Health checks

Le service expose plusieurs endpoints de santé :
- `/health` - Check de base
- `/health/detailed` - Diagnostic complet
- `/metrics` - Métriques Prometheus

### Backup

Sauvegarder régulièrement :
- Base de données PostgreSQL
- Configuration Caddy
- Logs applicatifs
