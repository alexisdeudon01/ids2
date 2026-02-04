import os
import re
import sys

# Configuration identique pour ignorer les dossiers de librairies
PROJECT_DIR = "."
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'site-packages', 'bin', 'lib', 'include', 'dist', 'build'}

def get_my_files():
    file_list = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for f in files:
            # Ignorez ici les noms de vos scripts de test pour l'analyse
            if f.endswith('.py') and f not in ["identify_deps_fixed.py", "identify_deps.py", "w.py", "kl.py"]:
                file_list.append(os.path.join(root, f))
    return [os.path.relpath(f, PROJECT_DIR) for f in file_list]

def extract_external_imports(file_path):
    external_imports = set()
    
    pattern = re.compile(r'^\s*(?:from|import)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            matches = pattern.findall(content)
            for match in matches:
                # Filtrer les imports standard de Python, vos imports locaux ('ids', 'webapp')
                is_builtin = match in sys.builtin_module_names
                is_standard_library = match in ['os', 'sys', 're', 'json', 'logging', 'unittest', 'pytest', 'subprocess']
                is_local_module = match.startswith('ids') or match.startswith('webapp')

                if not is_builtin and not is_standard_library and not is_local_module:
                    external_imports.add(match)
    except Exception as e:
        print(f"Erreur lecture {file_path}: {e}")
        
    return external_imports

def main():
    print("Analyse des imports Python dans le code source...")
    all_files = get_my_files()
    all_external_imports = set()
    
    for file_path in all_files:
        imports = extract_external_imports(file_path)
        all_external_imports.update(imports)

    print("\n--- Dépendances externes potentielles trouvées ---")
    if all_external_imports:
        sorted_imports = sorted(list(all_external_imports))
        for lib in sorted_imports:
            print(f"- {lib}")
        
        print("\nSuggestions de contenu pour requirements.txt :")
        for lib in sorted_imports:
            print(f"{lib}") # Liste les noms, sans version figée pour l'instant
    else:
        print("Aucune dépendance externe claire trouvée dans votre code source.")

if __name__ == "__main__":
    main()
