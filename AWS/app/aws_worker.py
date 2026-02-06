import boto3
from datetime import datetime, timezone

class AWSWorker:
    def __init__(self, db_manager):
        self.db = db_manager
        self.session = boto3.Session()

    def sync_all(self):
        conn = self.db.get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        
        # 1. Sync Users & Keys
        iam = self.session.client('iam')
        users = iam.list_users()['Users']
        for u in users:
            cursor.execute("REPLACE INTO IAM_USER (user_arn, user_name) VALUES (%s, %s)", (u['Arn'], u['UserName']))
            
            keys = iam.list_access_keys(UserName=u['UserName'])['AccessKeyMetadata']
            for k in keys:
                age = (now - k['CreateDate']).days
                cursor.execute("""
                    REPLACE INTO API_KEY (access_key_id, user_arn, status, age_days, needs_rotation)
                    VALUES (%s, %s, %s, %s, %s)
                """, (k['AccessKeyId'], u['Arn'], k['Status'], age, age > 90))
        
        conn.commit()
        cursor.close()
        conn.close()
