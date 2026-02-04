import os
import re
import json
import networkx as nx
from pyvis.network import Network

class FullDependencyAnalyzer:
    def __init__(self, root_dir):
        self.root_dir = os.path.abspath(root_dir)
        self.G = nx.DiGraph()
        
        # Patterns d'extraction par type de fichier
        self.rules = {
            '.py': [(r'^(?:from|import)\s+([\w\.]+)', "IMPORT")],
            '.sh': [
                (r'(?:source|\.)\s+([\w\.\/-]+)', "SOURCE"),
                (r'(?:bash|sh|python3?)\s+([\w\.\/-]+)', "EXECUTE")
            ],
            'Dockerfile': [
                (r'FROM\s+([\w\.\/:-]+)', "BASE_IMAGE"),
                (r'COPY\s+([\w\.\/-]+)', "COPY_FILE"),
                (r'RUN\s+[\.\/]*([\w\.\/-]+\.sh)', "EXECUTE")
            ],
            '.yml': [
                (r'image:\s+([\w\.\/:-]+)', "USE_IMAGE"),
                (r'dockerfile:\s+([\w\.\/-]+)', "BUILD_FROM"),
                (r'env_file:\s+([\w\.\/-]+)', "LOAD_ENV")
            ],
            '.yaml': [
                (r'image:\s+([\w\.\/:-]+)', "USE_IMAGE"),
                (r'dockerfile:\s+([\w\.\/-]+)', "BUILD_FROM")
            ],
            '.service': [
                (r'ExecStart=.*?([\w\.\/-]+)', "START_PROCESS"),
                (r'Requires=([\w\.-]+)', "REQUIRES")
            ]
        }

    def scan(self):
        print(f"🔍 Analyse récursive de : {self.root_dir}...")
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1]
                
                # Ajout du noeud (on garde le nom de fichier pour la clarté)
                self.G.add_node(file, type=ext if ext else "no-ext")
                
                # Sélection de la règle (par extension ou nom complet)
                active_rules = self.rules.get(ext) or self.rules.get(file)
                
                if active_rules:
                    try:
                        with open(file_path, 'r', errors='ignore') as f:
                            content = f.read()
                            for pattern, action in active_rules:
                                matches = re.findall(pattern, content, re.MULTILINE)
                                for m in matches:
                                    target = os.path.basename(m).replace('.py', '')
                                    if target:
                                        self.G.add_edge(file, target, label=action, title=f"Action: {action}")
                    except Exception as e:
                        print(f"⚠️ Erreur sur {file}: {e}")

    def generate_interactive_html(self, output_file="dependency_map.html"):
        # 1. Nettoyage : suppression des fichiers totalement isolés
        isolated = [n for n, d in self.G.degree() if d == 0]
        self.G.remove_nodes_from(isolated)

        # 2. Analyse de structure
        roots = [n for n, d in self.G.in_degree() if d == 0]
        cycles = list(nx.simple_cycles(self.G))
        coupling = {n: d for n, d in self.G.in_degree()} # Score de criticité

        # 3. Configuration du graphe Pyvis
        net = Network(height="850px", width="100%", directed=True, bgcolor="#1e1e1e", font_color="white")
        
        for node in self.G.nodes():
            score = coupling.get(node, 0)
            is_root = node in roots
            in_cycle = any(node in c for c in cycles)
            
            # Style visuel
            color = "#ff4d4d" if is_root else "#4d94ff"
            if in_cycle: color = "#f1c40f" # Jaune pour les redondances/cycles
            
            size = 20 + (score * 8) # Taille basée sur le couplage
            
            tooltip = (f"<b>Fichier:</b> {node}<br>"
                       f"<b>Couplage entrant:</b> {score}<br>"
                       f"<b>Status:</b> {'Root' if is_root else 'Dépendance'}<br>"
                       f"{'⚠️ FAIT PARTIE D UN CYCLE' if in_cycle else ''}")
            
            net.add_node(node, label=node, size=size, color=color, title=tooltip)

        net.from_nx(self.G)

        # 4. Activation de la barre de recherche et du panneau de contrôle
        net.show_buttons(filter_=['physics', 'nodes', 'edges'])
        
        # Injection de script personnalisé pour la recherche (Pyvis natif)
        # Note: Pyvis inclut déjà une option de recherche via l'interface
        
        net.save_graph(output_file)
        
        print("\n" + "="*30)
        print(f"✅ TERMINÉ !")
        print(f"📊 Fichier généré : {output_file}")
        print(f"🚀 Racines (Point d'entrée) : {roots}")
        print(f"♻️ Cycles détectés : {len(cycles)}")
        print("="*30)

if __name__ == "__main__":
    # Analyse le répertoire courant
    scanner = FullDependencyAnalyzer('.')
    scanner.scan()
    scanner.generate_interactive_html()
