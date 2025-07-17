#!/usr/bin/env python3
"""
Script d'application des standards v0.6.3 - Nettoyage et standardisation du code
Applique les corrections de manière sûre et méthodique
"""

import os
import subprocess
import re
from typing import List, Tuple

def run_autoflake(file_path: str) -> bool:
    """Applique autoflake pour supprimer les imports inutilisés"""
    try:
        result = subprocess.run([
            'autoflake', 
            '--in-place',
            '--remove-all-unused-imports',
            '--remove-unused-variables',
            '--remove-duplicate-keys',
            file_path
        ], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erreur autoflake sur {file_path}: {e}")
        return False

def run_isort(file_path: str) -> bool:
    """Applique isort pour organiser les imports"""
    try:
        result = subprocess.run([
            'isort', 
            '--profile=black',
            '--line-length=88',
            '--multi-line=3',
            '--trailing-comma',
            '--force-grid-wrap=0',
            '--combine-as',
            '--line-separator=\\n',
            file_path
        ], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erreur isort sur {file_path}: {e}")
        return False

def fix_whitespace_issues(file_path: str) -> bool:
    """Corrige les problèmes d'espaces et de lignes vides"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Supprimer les espaces en fin de ligne
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        
        # Corriger les lignes vides multiples
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Assurer 2 lignes vides avant les classes et fonctions de niveau module
        content = re.sub(r'\n(class [A-Za-z])', r'\n\n\n\\1', content)
        content = re.sub(r'\n(def [a-z_])', r'\n\n\n\\1', content)
        content = re.sub(r'\n(async def [a-z_])', r'\n\n\n\\1', content)
        
        # Nettoyer les multiples lignes vides créées
        content = re.sub(r'\n\n\n+', '\n\n\n', content)
        
        # S'assurer que le fichier se termine par une seule ligne vide
        content = content.rstrip() + '\n'
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur correction espaces sur {file_path}: {e}")
        return False

def fix_line_length(file_path: str) -> bool:
    """Corrige les lignes trop longues de manière basique"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        new_lines = []
        
        for line in lines:
            if len(line.rstrip()) > 88:
                # Corrections simples pour les lignes trop longues
                
                # 1. Casser les imports longs
                if line.strip().startswith('from ') and ' import ' in line:
                    parts = line.split(' import ')
                    if len(parts) == 2 and len(parts[1].strip()) > 40:
                        imports = [imp.strip() for imp in parts[1].split(',')]
                        if len(imports) > 1:
                            new_line = f"{parts[0]} import (\n"
                            for imp in imports:
                                new_line += f"    {imp.strip()},\n"
                            new_line += ")\n"
                            new_lines.append(new_line)
                            modified = True
                            continue
                
                # 2. Casser les chaînes de format longues
                if '.format(' in line and len(line.rstrip()) > 88:
                    # Simple: ajouter \\ à la fin et continuer sur la ligne suivante
                    indent = len(line) - len(line.lstrip())
                    if indent > 0:
                        split_point = line.rfind('.format(')
                        if split_point > 40:
                            line1 = line[:split_point] + ' \\\n'
                            line2 = ' ' * (indent + 4) + line[split_point:]
                            new_lines.extend([line1, line2])
                            modified = True
                            continue
                
                # 3. Casser les conditions longues
                if ' and ' in line or ' or ' in line:
                    indent = len(line) - len(line.lstrip())
                    if ' and ' in line:
                        parts = line.split(' and ')
                        if len(parts) > 1 and len(line.rstrip()) > 88:
                            new_line = parts[0] + ' and \\\n'
                            for i, part in enumerate(parts[1:], 1):
                                if i == len(parts) - 1:
                                    new_line += ' ' * (indent + 4) + part
                                else:
                                    new_line += ' ' * (indent + 4) + part + ' and \\\n'
                            new_lines.append(new_line)
                            modified = True
                            continue
            
            new_lines.append(line)
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur correction longueur sur {file_path}: {e}")
        return False

def fix_bare_except(file_path: str) -> bool:
    """Corrige les except: nus"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer except: par except Exception:
        modified_content = re.sub(
            r'(\s+)except:\s*\n',
            r'\\1except Exception:\n',
            content
        )
        
        if content != modified_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            return True
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur correction except sur {file_path}: {e}")
        return False

def apply_v063_standards(file_path: str) -> Tuple[bool, List[str]]:
    """Applique tous les standards v0.6.3 à un fichier"""
    operations = []
    success = True
    
    print(f"🔧 Traitement: {file_path}")
    
    # 1. Autoflake - suppression imports inutilisés
    if run_autoflake(file_path):
        operations.append("autoflake")
    else:
        success = False
    
    # 2. Corrections manuelles
    if fix_whitespace_issues(file_path):
        operations.append("whitespace")
    else:
        success = False
    
    if fix_line_length(file_path):
        operations.append("line-length")
    else:
        success = False
    
    if fix_bare_except(file_path):
        operations.append("except-fix")
    else:
        success = False
    
    # 3. isort - organisation des imports
    if run_isort(file_path):
        operations.append("isort")
    else:
        success = False
    
    return success, operations

def main():
    """Fonction principale"""
    print("🚀 APPLICATION DES STANDARDS v0.6.3")
    print("====================================")
    
    # Traiter tous les fichiers Python dans wakedock/
    total_files = 0
    success_files = 0
    failed_files = 0
    
    for root, dirs, files in os.walk('wakedock'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_files += 1
                
                success, operations = apply_v063_standards(file_path)
                
                if success:
                    success_files += 1
                    print(f"✅ {file_path} - {', '.join(operations)}")
                else:
                    failed_files += 1
                    print(f"❌ {file_path} - ÉCHEC")
    
    print(f"\n📊 RÉSULTATS v0.6.3:")
    print(f"Total fichiers traités: {total_files}")
    print(f"✅ Succès: {success_files}")
    print(f"❌ Échecs: {failed_files}")
    print(f"🎯 Taux de réussite: {(success_files/total_files)*100:.1f}%")
    
    # Vérification finale avec flake8
    print(f"\n🔍 VÉRIFICATION FINALE...")
    result = subprocess.run([
        'flake8', 'wakedock/', 
        '--max-line-length=88', 
        '--extend-ignore=E203,W503,F401', 
        '--count'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("🎉 AUCUNE VIOLATION flake8 restante!")
    else:
        violations = result.stdout.strip()
        print(f"⚠️  {violations} violations restantes")
    
    return success_files == total_files

if __name__ == "__main__":
    os.chdir('/Docker/code/wakedock-env/wakedock-backend')
    success = main()
    print(f"\n{'🎉 v0.6.3 TERMINÉ AVEC SUCCÈS!' if success else '⚠️  v0.6.3 TERMINÉ AVEC AVERTISSEMENTS'}")
    exit(0 if success else 1)
