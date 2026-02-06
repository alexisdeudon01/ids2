-- API Keys

INSERT INTO API_KEY (access_key_id, secret_access_key, user_arn, status, age_days, needs_rotation, last_test_date) VALUES
('AKIATCKATQFAEIIQBTXP', 'HIDDEN', 'arn:aws:iam::211125764416:user/alexis', 'Active', 0, 0, NOW())
ON DUPLICATE KEY UPDATE status='Active', age_days=0, needs_rotation=0, last_test_date=NOW();
