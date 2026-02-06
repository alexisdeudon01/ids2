import paramiko

class SSHManager:
    def __init__(self, host, user, key_path):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.host = host
        self.user = user
        self.key_path = key_path

    def execute_test(self):
        """Test connection to an EC2 instance"""
        try:
            self.client.connect(self.host, username=self.user, key_filename=self.key_path, timeout=10)
            stdin, stdout, stderr = self.client.exec_command('uptime')
            result = stdout.read().decode()
            self.client.close()
            return f"Success: {result.strip()}"
        except Exception as e:
            return f"Failed: {str(e)}"
