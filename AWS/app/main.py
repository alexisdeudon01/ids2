import time, os
from database import DBManager
from aws_worker import AWSWorker

def run_orchestrator():
    db = DBManager(os.getenv('DB_HOST'), 'root', os.getenv('DB_PASS'), os.getenv('DB_NAME'))
    worker = AWSWorker(db)
    
    print("🚀 Starting AWS Audit Loop (Every 10 minutes)...")
    
    while True:
        try:
            print(f"--- Scan Start: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            worker.sync_all()
            print("✅ Sync Successful.")
        except Exception as e:
            print(f"❌ Error during sync: {e}")
        
        time.sleep(600)

if __name__ == "__main__":
    run_orchestrator()
