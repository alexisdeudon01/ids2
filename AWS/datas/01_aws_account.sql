-- AWS Account Information

INSERT INTO AWS_ACCOUNT (account_id, alias, last_scan) VALUES
('211125764416', 'None', NOW())
ON DUPLICATE KEY UPDATE alias='None', last_scan=NOW();
