-- IAM Users
USE ids_db;

INSERT INTO IAM_USER (user_arn, user_name, is_admin) VALUES
('arn:aws:iam::211125764416:user/alexis', 'alexis', 1)
ON DUPLICATE KEY UPDATE user_name='alexis', is_admin=1;
