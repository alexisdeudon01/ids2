import os
import re
import json
import hashlib
import networkx as nx
from anthropic import Anthropic
from pyvis.network import Network

# --- CONFIGURATION ---
ANTHROPIC_KEY = "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"
ROOT_DIR = "/home/tor/Downloads/ids2"
CACHE_FILE = "analysis_cache.json"

client = Anthropic(api_key=ANTHROPIC_KEY)

class IntelligentAnalyzer:
    def __init__(self):
        self.G = nx.DiGraph()
        self.cache = self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)

    def get_file_hash(self, content):
        return hashlib.md5(content.encode()).hexdigest()

    def ask_claude(self, file_name, content):
        file_hash = self.get_file_hash(content)
        
        # Retourne le cache si le fichier n'a pas changé
        if file_name in self.cache and self.cache[file_name]['hash'] == file_hash:
            return self.cache[file_name]['data']

        prompt = f"""
        Analyze this file ({file_name}) and list local file dependencies.
        Return ONLY a JSON object: {{"deps": [{{"file": "name", "type": "import/exec/copy"}}]}}
        If no dependencies, return {{"deps": []}}.
        
        CONTENT:
        {content[:3000]}
        """
        
        try:
            # ID CORRIGÉ : claude-3-5-sonnet-latest
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Nettoyage de la réponse pour extraire le JSON
            raw_text = message.content[0].text
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            data = json.loads(json_match.group(0)) if json_match else {"deps": []}
            
            # Mise en cache
            self.cache[file_name] = {'hash': file_hash, 'data': data}
            return data
        except Exception as e:
            print(f"❌ Erreur sur {file_name}: {e}")
            return {"deps": []}

    def run(self):
        files_to_scan = []
        for root, _, files in os.walk(ROOT_DIR):
            for file in files:
                if file.endswith(('.py', '.sh', '.yml', '.yaml', '.service', 'Dockerfile')):
                    files_to_scan.append(os.path.join(root, file))

        for path in files_to_scan:
            name = os.path.basename(path)
            print(f"🧠 Analyse IA : {name}...")
            
            with open(path, 'r', errors='ignore') as f:
                content = f.read()
            
            result = self.ask_claude(name, content)
            self.G.add_node(name)
            
            for d in result.get("deps", []):
                self.G.add_edge(name, d['file'], label=d['type'], title=f"Action: {d['type']}")

        self.save_cache()
        self.visualize()

    def visualize(self):
        # Suppression des orphelins
        self.G.remove_nodes_from([n for n, d in self.G.degree() if d == 0])
        
        net = Network(height="850px", width="100%", directed=True, bgcolor="#1a1a1a", font_color="white")
        net.from_nx(self.G)
        
        # Configuration avec barre de recherche (filter_menu)
        net.set_options("""
        {
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "tooltipDelay": 100
          },
          "physics": {
            "forceAtlas2Based": { "gravitationalConstant": -80 },
            "solver": "forceAtlas2Based"
          }
        }
        """)
        
        # Affiche la barre de recherche et les contrôles
        net.show_buttons(filter_=['nodes', 'edges', 'physics'])
        net.save_graph("dependency_map_ai.html")
        print("\n✨ Graphe généré : dependency_map_ai.html")

if __name__ == "__main__":
    analyzer = IntelligentAnalyzer()
    analyzer.run()

