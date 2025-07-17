#!/usr/bin/env python3
"""
Script rapide pour vérifier l'état de la syntaxe des fichiers Python
"""
import os
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

def main():
    """Fonction principale"""
    wakedock_dir = "wakedock"
    
    if not os.path.exists(wakedock_dir):
        print(f"❌ Répertoire {wakedock_dir} non trouvé")
        return
    
    total_files = 0
    success_files = 0
    error_files = 0
    error_list = []
    
    # Parcourir tous les fichiers Python
    for root, dirs, files in os.walk(wakedock_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                is_valid, error = check_file_syntax(file_path)
                
                if is_valid:
                    success_files += 1
                    print(f"✅ {file_path}")
                else:
                    error_files += 1
                    error_list.append((file_path, error))
                    print(f"❌ {file_path}: {error[:80]}...")
    
    # Résumé
    print(f"\n📊 RÉSUMÉ SYNTAXE:")
    print(f"Total fichiers Python: {total_files}")
    print(f"✅ Fichiers OK: {success_files}")
    print(f"❌ Fichiers avec erreurs: {error_files}")
    
    if total_files > 0:
        success_rate = (success_files / total_files) * 100
        print(f"🎯 Taux de réussite: {success_rate:.1f}%")
    
    if error_files > 0:
        print(f"\n🔧 FICHIERS À CORRIGER:")
        for file_path, error in error_list[:10]:  # Limiter à 10 erreurs
            print(f"   • {file_path}")
    
    return error_files == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
