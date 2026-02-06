import mysql.connector

class DBManager:
    def __init__(self, host, user, password, database):
        self.config = {'host': host, 'user': user, 'password': password, 'database': database}

    def get_conn(self):
        return mysql.connector.connect(**self.config)

    def test_connection(self):
        try:
            conn = self.get_conn()
            conn.close()
            return True
        except: return False
