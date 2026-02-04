import os
import re
import plotly.graph_objects as go
import networkx as nx
import pandas as pd

# --- CONFIGURATION (Identique au précédent pour le filtrage) ---
PROJECT_DIR = "."
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'site-packages', 'bin', 'lib', 'include'}
EXTENSIONS = ('.sh', '.py', '.bash')

def get_my_files():
    file_list = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for f in files:
            if f.endswith(EXTENSIONS) and f not in ["generate_interactive_graph.py", "generate_graph.py", "generate_auto_graph.py"]:
                file_list.append(os.path.join(root, f)) # Garder le chemin complet pour l'unicité

    # Normaliser les chemins pour avoir des noms de nœuds propres
    return [os.path.relpath(f, PROJECT_DIR) for f in file_list]

def find_dependencies(file_path, all_my_files_basenames):
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

def main():
    all_scripts_paths = get_my_files()
    all_scripts_basenames = [os.path.basename(f) for f in all_scripts_paths]
    G = nx.DiGraph()

    for script_path in all_scripts_paths:
        script_name = os.path.basename(script_path)
        deps = find_dependencies(script_path, all_scripts_basenames)
        for dep in deps:
            G.add_edge(script_name, dep)

    # Utiliser un algorithme de layout pour positionner les nœuds
    pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42) # Layout for positioning

    # Préparer les données pour Plotly
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    node_text = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        # Texte affiché au survol (hover)
        node_text.append(f'{node}<br>Liens sortants: {G.out_degree(node)}<br>Liens entrants: {G.in_degree(node)}')

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            showscale=False,
            color='lightblue',
            size=10,
            line_width=2),
        text=list(G.nodes()), # Nom du fichier sous le cercle
        textposition="bottom center"
        )
    
    node_trace.text = node_text

    fig = go.Figure(data=[edge_trace, node_trace],
                 layout=go.Layout(
                    title='<br>Graphe interactif des dépendances de ids2',
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    annotations=,
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )
    
    fig.write_html("graph_interactif.html")
    print("Fichier 'graph_interactif.html' généré dans votre dossier. Ouvrez-le dans votre navigateur.")


if __name__ == "__main__":
    main()
