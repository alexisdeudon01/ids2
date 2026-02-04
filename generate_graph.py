import os
import re
from graphviz import Digraph

# Configuration
PROJECT_DIR = "."
EXTENSIONS = ('.sh', '.py', '.pl', '.bash')

def get_all_files():
    """Récupère tous les scripts du projet selon les extensions définies."""
    file_list = []
    for root, _, files in os.walk(PROJECT_DIR):
        for f in files:
            if f.endswith(EXTENSIONS) and f != "generate_auto_graph.py":
                file_list.append(f)
    return file_list

def find_dependencies(file_path):
    """Cherche les appels de fichiers locaux dans un script."""
    deps = []
    pattern = re.compile(r'([\w\d_-]+\.(?:sh|py|bash|pl))')
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                matches = pattern.findall(line)
                for m in matches:
                    if m != os.path.basename(file_path):
                        deps.append(m)
    except:
        pass
    return list(set(deps))

def main():
    dot = Digraph(comment='Graphe Global', format='png')
    dot.attr(rankdir='TB')
    
    all_scripts = get_all_files()
    graph = {}
    all_children = set()

    # 1. Construire le dictionnaire des relations
    for script in all_scripts:
        dependencies = find_dependencies(os.path.join(PROJECT_DIR, script))
        # On ne garde que les dépendances qui existent réellement en local
        valid_deps = [d for d in dependencies if d in all_scripts]
        graph[script] = valid_deps
        for d in valid_deps:
            all_children.add(d)

    # 2. Identifier les racines (Fichiers qui ne sont jamais appelés)
    roots = [node for node in all_scripts if node not in all_children]

    if not roots and all_scripts:
        print("Boucle détectée : aucun fichier n'est une racine absolue. Utilisation de tous les fichiers.")
        roots = all_scripts

    # 3. Construire le graphe récursivement à partir des racines
    visited = set()

    def add_to_dot(node):
        if node in visited:
            return
        visited.add(node)
        dot.node(node, node, shape='box', style='filled', fillcolor='lightblue' if node in roots else 'white')
        
        for child in graph.get(node, []):
            dot.edge(node, child)
            add_to_dot(child)

    for root in roots:
        add_to_dot(root)

    # Sauvegarde
    output_name = 'graphe_complet'
    dot.render(output_name, view=True)
    print(f"Graphe généré : {output_name}.png")
    print(f"Racines détectées (en bleu) : {', '.join(roots)}")

if __name__ == "__main__":
    main()
