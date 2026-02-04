import os
import re
from graphviz import Digraph

# --- CONFIGURATION ---
PROJECT_DIR = "."
# Dossiers à ignorer absolument
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'site-packages', 'bin', 'lib', 'include'}
EXTENSIONS = ('.sh', '.py', '.bash')

def get_my_files():
    """Récupère uniquement VOS fichiers en ignorant les libs."""
    file_list = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        # Filtrage des dossiers exclus
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        
        for f in files:
            if f.endswith(EXTENSIONS) and f != "generate_graph.py":
                file_list.append(f)
    return file_list

def find_dependencies(file_path, all_my_files):
    """Cherche uniquement les appels vers VOS fichiers."""
    deps = []
    # Regex pour capturer les noms de fichiers scripts
    pattern = re.compile(r'([\w\d_-]+\.(?:sh|py|bash))')
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                matches = pattern.findall(line)
                for m in matches:
                    # On ne garde que si c'est un de NOS fichiers et pas soi-même
                    if m in all_my_files and m != os.path.basename(file_path):
                        deps.append(m)
    except:
        pass
    return list(set(deps))

def main():
    dot = Digraph(comment='Architecture IDS2', format='png')
    dot.attr(rankdir='TB', size='20,20') # Taille limitée pour lisibilité
    
    all_scripts = get_my_files()
    graph = {}
    all_children = set()

    # 1. Analyse des relations
    for script in all_scripts:
        # On cherche le chemin complet pour la lecture
        full_path = ""
        for root, _, files in os.walk(PROJECT_DIR):
            if script in files:
                full_path = os.path.join(root, script)
                break
        
        if full_path:
            dependencies = find_dependencies(full_path, all_scripts)
            graph[script] = dependencies
            for d in dependencies:
                all_children.add(d)

    # 2. Identification des points d'entrée (Racines)
    roots = [node for node in all_scripts if node not in all_children]

    # 3. Construction récursive
    visited = set()
    def add_to_dot(node):
        if node in visited: return
        visited.add(node)
        
        # Style : Bleu pour les entrées, Blanc pour les sous-scripts
        color = 'lightblue' if node in roots else 'white'
        dot.node(node, node, shape='box', style='filled', fillcolor=color)
        
        for child in graph.get(node, []):
            dot.edge(node, child)
            add_to_dot(child)

    for root in roots:
        add_to_dot(root)

    output_name = 'mon_architecture_ids2'
    dot.render(output_name, view=False)
    print(f"--- ANALYSE TERMINÉE ---")
    print(f"Fichiers analysés : {len(all_scripts)}")
    print(f"Points d'entrée détectés : {len(roots)}")
    print(f"Image générée : {output_name}.png")

if __name__ == "__main__":
    main()
