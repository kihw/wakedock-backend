# API WakeDock Backend

## Endpoints disponibles

### Authentification
- `POST /api/auth/login` - Connexion utilisateur
- `POST /api/auth/register` - Inscription utilisateur
- `POST /api/auth/refresh` - Renouvellement du token JWT
- `POST /api/auth/logout` - Déconnexion

### Santé
- `GET /api/health` - Status de santé de l'API
- `GET /api/health/detailed` - Diagnostic détaillé

### Services
- `GET /api/services` - Liste des services Docker
- `POST /api/services/{service_id}/start` - Démarrer un service
- `POST /api/services/{service_id}/stop` - Arrêter un service
- `POST /api/services/{service_id}/restart` - Redémarrer un service

### Système
- `GET /api/system/info` - Informations système
- `GET /api/system/metrics` - Métriques système

### Proxy
- `GET /api/proxy/routes` - Routes Caddy
- `POST /api/proxy/routes` - Ajouter une route
- `DELETE /api/proxy/routes/{route_id}` - Supprimer une route

## Authentification

L'API utilise JWT (JSON Web Tokens) pour l'authentification. Incluez le token dans l'en-tête Authorization :

```
Authorization: Bearer <token>
```

## Configuration

Voir `config.py` pour les paramètres de configuration disponibles.
