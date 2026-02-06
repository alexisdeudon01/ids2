-- Deployment Configuration
USE ids_db;

INSERT INTO deployment_config (
    aws_region, elk_ip, elastic_password, pi_host, pi_user, 
    pi_password, sudo_password, remote_dir, mirror_interface, ssh_key_path
) VALUES (
    'eu-west-1', '192.168.178.66', 'admin', 'sinik', 'pi',
    'pi', 'pi', '/opt/ids2', 'eth0', '/home/tor/.ssh/pi_key'
);
