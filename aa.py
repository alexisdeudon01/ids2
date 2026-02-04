import os
import json
import networkx as nx
from anthropic import Anthropic
from pyvis.network import Network

# Configuration
client = Anthropic(api_key="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")
ROOT_DIR = "/home/tor/Downloads/ids2"

class AIAnalyzer:
    def __init__(self):
        self.G = nx.DiGraph()

    def ask_claude(self, file_name, content):
        prompt = f"""
        Analyse ce fichier ({file_name}) et identifie les dépendances vers d'autres fichiers locaux.
        Extensions possibles : .py, .sh, .yml, .dockerfile, .service.
        
        Réponds UNIQUEMENT au format JSON suivant :
        {{"dependencies": [{{"target": "nom_du_fichier", "action": "import/execute/copy/requires"}}]}}
        Si aucune dépendance, réponds {{"dependencies": []}}.
        
        CONTENU DU FICHIER :
        {content}
        """
        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            # Extraction du JSON dans la réponse
            response_text = message.content[0].text
            return json.loads(response_text)
        except Exception as e:
            print(f"Erreur IA sur {file_name}: {e}")
            return {"dependencies": []}

    def run(self):
        for root, _, files in os.walk(ROOT_DIR):
            for file in files:
                if file.endswith(('.py', '.sh', '.yml', '.yaml', '.service', 'Dockerfile')):
                    path = os.path.join(root, file)
                    with open(path, 'r', errors='ignore') as f:
                        content = f.read()[:4000] # On limite pour les tokens
                    
                    print(f"🧠 Claude analyse : {file}...")
                    result = self.ask_claude(file, content)
                    
                    self.G.add_node(file)
                    for dep in result.get("dependencies", []):
                        self.G.add_edge(file, dep['target'], label=dep['action'], title=dep['action'])

        # --- Post-traitement Intelligent ---
        # 1. Supprimer les fichiers orphelins
        self.G.remove_nodes_from([n for n, d in self.G.degree() if d == 0])
        
        # 2. Trouver Roots et Cycles
        roots = [n for n, d in self.G.in_degree() if d == 0]
        
        # 3. Rendu HTML Interactif avec barre de recherche
        net = Network(height="850px", width="100%", directed=True, bgcolor="#1a1a1a", font_color="white")
        net.from_nx(self.G)
        
        # Options visuelles et barre de recherche native
        net.set_options("""
        {
          "nodes": { "font": { "size": 18 } },
          "physics": { "forceAtlas2Based": { "gravitationalConstant": -100 }, "solver": "forceAtlas2Based" },
          "interaction": { "navigationButtons": true, "multiselect": true, "keyboard": true }
        }
        """)
        
        # Activation du menu de recherche et config
        net.show_buttons(filter_=['nodes', 'edges', 'physics'])
        net.save_graph("ai_dependency_map.html")
        
        print(f"\n✅ Analyse terminée. Roots : {roots}")

if __name__ == "__main__":
    analyzer = AIAnalyzer()
    analyzer.run()
