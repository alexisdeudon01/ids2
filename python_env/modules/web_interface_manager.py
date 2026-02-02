import logging
import time
import os
import uvicorn
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from base_component import BaseComponent
import multiprocessing
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class WebInterfaceManager(BaseComponent):
    """
    Gère l'interface Web locale (FastAPI) pour le pilotage et l'observabilité.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event)
        self.port = self.get_config('fastapi.port', 8000)
        self.host = self.get_config('fastapi.host', '0.0.0.0')
        self.app = FastAPI(
            title="IDS2 SOC Agent Web Interface",
            description="API de pilotage et d'observabilité pour l'agent IDS2 SOC.",
            version="1.0.0"
        )
        self.app.mount("/static", StaticFiles(directory="web_interface/static"), name="static")
        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self):
        """
        Configure les routes de l'API FastAPI.
        """
        @self.router.get("/", response_class=HTMLResponse)
        async def read_root():
            with open("web_interface/index.html", "r") as f:
                return f.read()

        @self.router.get("/status")
        async def get_status():
            return {
                "cpu_usage": self.shared_state.get('cpu_usage'),
                "ram_usage": self.shared_state.get('ram_usage'),
                "throttling_level": self.shared_state.get('throttling_level'),
                "aws_ready": self.shared_state.get('aws_ready'),
                "vector_ready": self.shared_state.get('vector_ready'),
                "redis_ready": self.shared_state.get('redis_ready'),
                "pipeline_ok": self.shared_state.get('pipeline_ok'),
                "docker_healthy": self.shared_state.get('docker_healthy'),
                "last_error": self.shared_state.get('last_error'),
                "suricata_rules_updated": self.shared_state.get('suricata_rules_updated'),
            }

        @self.router.post("/config")
        async def update_config(new_config: dict):
            try:
                self.config.update_config(new_config)
                self.logger.info("Configuration mise à jour via l'interface Web.")
                return {"message": "Configuration mise à jour avec succès."}
            except Exception as e:
                self.log_error("Échec de la mise à jour de la configuration via l'interface Web", e)
                raise HTTPException(status_code=500, detail=str(e))

        # Ajouter d'autres routes pour le pilotage (redémarrage services, etc.)
        self.app.include_router(self.router)

    def run(self):
        """
        Démarre le serveur Uvicorn pour FastAPI.
        """
        self.logger.info(f"Interface Web (FastAPI) démarrée sur http://{self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    fastapi:
      port: 8000
      host: "127.0.0.1"
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    # Créer un répertoire et un fichier HTML factices pour le test
    os.makedirs('web_interface/static', exist_ok=True)
    with open('web_interface/index.html', 'w') as f:
        f.write("<html><body><h1>Test Web Interface</h1><p>Status: <span id='status'></span></p><script>fetch('/status').then(r=>r.json()).then(data=>document.getElementById('status').innerText=JSON.stringify(data))</script></body></html>")
    with open('web_interface/static/style.css', 'w') as f:
        f.write("body { font-family: sans-serif; }")

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'cpu_usage': 10.0,
            'ram_usage': 20.0,
            'throttling_level': 0,
            'aws_ready': True,
            'vector_ready': True,
            'redis_ready': True,
            'pipeline_ok': True,
            'docker_healthy': True,
            'last_error': '',
            'suricata_rules_updated': True,
        })
        shutdown_event = multiprocessing.Event()

        web_manager = WebInterfaceManager(shared_state, config_mgr, shutdown_event)
        
        process = multiprocessing.Process(target=web_manager.run, name="WebInterfaceProcess")
        process.start()
        
        print(f"Interface Web démarrée sur http://{web_manager.host}:{web_manager.port}")
        print("Accédez à l'interface Web pour vérifier le statut.")
        time.sleep(10) # Laisser le temps au serveur de démarrer et de servir
        
        shutdown_event.set()
        process.join()

    except Exception as e:
        logging.error(f"Erreur lors du test de WebInterfaceManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('web_interface/index.html'):
            os.remove('web_interface/index.html')
        if os.path.exists('web_interface/static/style.css'):
            os.remove('web_interface/static/style.css')
        if os.path.exists('web_interface/static'):
            os.rmdir('web_interface/static')
        if os.path.exists('web_interface'):
            os.rmdir('web_interface')
