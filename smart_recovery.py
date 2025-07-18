#!/usr/bin/env python3
"""
Script de récupération intelligente des fichiers corrompus
Préserve les fichiers que vous avez corrigés manuellement avec succès
"""
import os
import subprocess
import ast

def check_file_syntax(file_path):
    """Vérifie la syntaxe d'un fichier Python"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        return True, None
    except Exception as e:
        return False, str(e)

def git_restore_file(file_path):
    """Restaure un fichier depuis git"""
    try:
        result = subprocess.run(
            ['git', 'restore', file_path],
            capture_output=True,
            text=True,
            cwd='/Docker/code/wakedock-env/wakedock-backend'
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    """Fonction principale de récupération"""
    os.chdir('/Docker/code/wakedock-env/wakedock-backend')
    
    # Fichiers avec erreurs de syntaxe (d'après notre analyse)
    problematic_files = [
        'wakedock/metrics.py',
        'wakedock/config.py',
        'wakedock/main.py',
        'wakedock/logging.py',
        'wakedock/database/cli.py',
        'wakedock/database/database.py',
        'wakedock/database/migrations/env.py',
        'wakedock/security/rate_limit.py',
        'wakedock/security/validation.py',
        'wakedock/core/compose_validator.py',
        'wakedock/core/performance_monitor.py',
        'wakedock/core/dashboard_service.py',
        'wakedock/core/pagination.py',
        'wakedock/core/rbac_service.py',
        'wakedock/core/cicd_service.py',
        'wakedock/core/docker_manager.py',
        'wakedock/core/security_audit_service.py',
        'wakedock/core/log_optimization_service.py',
        'wakedock/core/swarm_service.py',
        'wakedock/core/metrics_collector.py',
        'wakedock/core/dependency_manager.py',
        'wakedock/core/notification_service.py',
        'wakedock/core/config.py',
        'wakedock/core/alerts_service.py',
        'wakedock/core/cache.py',
        'wakedock/core/env_manager.py',
        'wakedock/core/dependencies.py',
        'wakedock/core/compose_deployment.py',
        'wakedock/core/environment_service.py',
        'wakedock/core/logging_config.py',
        'wakedock/core/validation.py',
        'wakedock/core/advanced_analytics.py',
        'wakedock/core/mobile_optimization_service.py',
        'wakedock/core/api_optimization.py',
        'wakedock/core/log_search_service.py',
        'wakedock/core/health.py',
        'wakedock/core/caddy.py',
        'wakedock/core/user_profile_service.py',
        'wakedock/core/log_collector.py',
        'wakedock/core/compose_parser.py',
        'wakedock/core/database.py',
        'wakedock/core/auto_deployment_service.py',
        'wakedock/core/alerts_dependencies.py',
        'wakedock/core/auth_service.py',
        'wakedock/core/base_service.py',
        'wakedock/core/network_manager.py',
        'wakedock/core/websocket_service.py',
        'wakedock/core/exceptions.py',
        'wakedock/core/monitoring.py',
        'wakedock/core/responses.py',
        'wakedock/core/middleware.py',
        # API routes avec erreurs
        'wakedock/api/app.py',
        'wakedock/api/middleware.py',
        'wakedock/api/auth/jwt.py',
        'wakedock/api/auth/models.py',
        'wakedock/api/auth/dependencies.py',
        'wakedock/api/auth/routes.py',
        'wakedock/api/auth/password.py',
        'wakedock/api/routes/services.py',
        'wakedock/api/routes/alerts.py',
        'wakedock/api/routes/auth.py',
        'wakedock/api/routes/logs.py',
        'wakedock/api/routes/mobile_api.py',
        'wakedock/api/routes/notification_api.py',
        'wakedock/api/routes/logs_optimization.py',
        'wakedock/api/routes/compose_stacks.py',
        'wakedock/api/routes/auto_deployment.py',
        'wakedock/api/routes/system.py',
        'wakedock/api/routes/health.py',
        'wakedock/api/routes/logs_optimization_fixed.py',
        'wakedock/api/routes/security_audit.py',
        'wakedock/api/routes/env_files.py',
        'wakedock/api/routes/analytics.py',
        'wakedock/api/routes/environment.py',
        'wakedock/api/routes/centralized_logs.py',
        'wakedock/api/routes/container_logs.py',
        'wakedock/api/routes/proxy.py',
        'wakedock/api/routes/dashboard_api.py',
        'wakedock/api/routes/monitoring.py',
        # Models avec erreurs
        'wakedock/models/security.py',
        'wakedock/models/notification.py',
        'wakedock/models/deployment.py',
        'wakedock/models/user.py',
        'wakedock/models/cicd.py',
        # Utils avec erreurs
        'wakedock/utils/validation.py',
        'wakedock/templates/loading.py'
    ]
    
    print("🔧 RÉCUPÉRATION INTELLIGENTE DES FICHIERS")
    print("==========================================")
    
    restored_count = 0
    failed_count = 0
    skipped_count = 0
    
    for file_path in problematic_files:
        if not os.path.exists(file_path):
            print(f"⚠️  {file_path} n'existe pas")
            continue
            
        # Vérifier d'abord si le fichier a encore des erreurs
        is_valid, error = check_file_syntax(file_path)
        
        if is_valid:
            print(f"✅ {file_path} - DÉJÀ OK (conservé)")
            skipped_count += 1
            continue
        
        print(f"🔄 Restauration de {file_path}...")
        
        if git_restore_file(file_path):
            # Vérifier que la restauration a corrigé le problème
            is_valid_after, _ = check_file_syntax(file_path)
            if is_valid_after:
                print(f"✅ {file_path} - RESTAURÉ ET OK")
                restored_count += 1
            else:
                print(f"⚠️  {file_path} - RESTAURÉ MAIS TOUJOURS DES ERREURS")
                failed_count += 1
        else:
            print(f"❌ {file_path} - ÉCHEC RESTAURATION")
            failed_count += 1
    
    print(f"\n📊 RÉSULTATS DE LA RÉCUPÉRATION:")
    print(f"✅ Fichiers restaurés avec succès: {restored_count}")
    print(f"🔄 Fichiers déjà OK (conservés): {skipped_count}")
    print(f"❌ Échecs: {failed_count}")
    
    # Vérification finale
    print(f"\n🔍 VÉRIFICATION FINALE...")
    total_files = 0
    success_files = 0
    
    for root, dirs, files in os.walk('wakedock'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                is_valid, _ = check_file_syntax(file_path)
                if is_valid:
                    success_files += 1
    
    success_rate = (success_files / total_files) * 100 if total_files > 0 else 0
    print(f"📈 TAUX DE RÉUSSITE FINAL: {success_rate:.1f}% ({success_files}/{total_files})")
    
    return success_rate > 95  # Objectif: plus de 95% de fichiers OK

if __name__ == "__main__":
    success = main()
    print(f"\n{'🎉 RÉCUPÉRATION RÉUSSIE!' if success else '⚠️  RÉCUPÉRATION PARTIELLE'}")
    exit(0 if success else 1)
