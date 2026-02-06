-- EC2 Instances
USE ids_db;

INSERT INTO ec2_instances (instance_id, region, instance_type, public_ip, private_ip, state, elk_deployed) VALUES
('i-074bd2f1b2c075192', 'eu-west-1', 't3.medium', '18.203.88.25', '172.31.21.23', 'running', 1)
ON DUPLICATE KEY UPDATE instance_type='t3.medium', public_ip='18.203.88.25', private_ip='172.31.21.23', state='running', elk_deployed=1, updated_at=NOW();
