import os
import re
import subprocess
import sys
import networkx as nx

# --- CONFIGURATION ---
PROJECT_DIR = "."
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'site-packages', 'bin', 'lib', 'include'}
EXTENSIONS = ('.sh', '.py', '.bash')

def get_my_files():
    """Récupère uniquement VOS fichiers en ignorant les libs."""
    file_list = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for f in files:
            if f.endswith(EXTENSIONS) and f not in ["run_all_dependencies.py", "graph_interactif.py", "generate_graph.py", "generate_auto_graph.py", "w.py", "h.py"]:
                file_list.append(os.path.join(root, f))
    return [os.path.relpath(f, PROJECT_DIR) for f in file_list]

def find_dependencies(file_path, all_my_files_basenames):
    """Cherche uniquement les appels vers VOS fichiers."""
    deps = set()
    pattern = re.compile(r'([\w\d_-]+\.(?:sh|py|bash))')
    try:
        with open(os.path.join(PROJECT_DIR, file_path), 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                matches = pattern.findall(line)
                for m in matches:
                    if m in all_my_files_basenames and m != os.path.basename(file_path):
                        deps.add(m)
    except:
        pass
    return list(deps)

def execute_script(script_path):
    """Exécute un script donné et capture le résultat."""
    print(f"\n--- Exécution de {script_path} ---")
    env = os.environ.copy()
    # Ajoute le répertoire racine du projet au PYTHONPATH pour trouver les modules comme 'ids'
    project_root_abs = os.path.abspath(PROJECT_DIR)
    env['PYTHONPATH'] = project_root_abs + ":" + env.get('PYTHONPATH', '')
    
    try:
        if script_path.endswith('.sh') or script_path.endswith('.bash'):
            command = ['bash', script_path]
        elif script_path.endswith('.py'):
            command = ['python3', script_path]
        else:
            print(f"ERREUR: Format non supporté {script_path}")
            return False

        # Exécution avec le PYTHONPATH modifié
        result = subprocess.run(command, check=True, capture_output=True, text=True, cwd=PROJECT_DIR, env=env)
        print(f"SUCCESS: {script_path} terminé sans erreur.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"ERREUR FATALE: {script_path} a échoué avec le code {e.returncode}.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print(f"ERREUR FATALE: Fichier non trouvé ou non exécutable {script_path}.")
        return False

def main():
    print("Analyse des dépendances en cours...")
    all_scripts_paths = get_my_files()
    all_scripts_basenames = {os.path.basename(f): f for f in all_scripts_paths}
    
    G = nx.DiGraph()

    for script_path in all_scripts_paths:
        script_name = os.path.basename(script_path)
        deps_basenames = find_dependencies(script_path, all_scripts_basenames.keys())
        for dep_basename in deps_basenames:
            G.add_edge(script_name, dep_basename)

    try:
        execution_order_basenames = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        print("ERREUR: Dépendance circulaire détectée. Impossible de déterminer l'ordre d'exécution.")
        sys.exit(1)
        
    execution_order_paths = [all_scripts_basenames[name] for name in execution_order_basenames]

    print(f"Ordre d'exécution détecté : {execution_order_basenames}")
    print("--- Démarrage de l'exécution hiérarchique ---")

    for script_path in execution_order_paths:
        if not execute_script(script_path):
            print(f"\n--- Processus arrêté suite à l'échec de {script_path} ---")
            sys.exit(1)
    
    print("\n=== Toutes les exécutions hiérarchiques terminées avec succès ===")

if __name__ == "__main__":
    main()
