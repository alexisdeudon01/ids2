CREATE DATABASE IF NOT EXISTS aws_audit;
USE aws_audit;

CREATE TABLE IF NOT EXISTS AWS_ACCOUNT (
    account_id VARCHAR(12) PRIMARY KEY,
    alias VARCHAR(255),
    last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS IAM_USER (
    user_arn VARCHAR(2048) PRIMARY KEY,
    user_name VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS API_KEY (
    access_key_id VARCHAR(128) PRIMARY KEY,
    secret_access_key VARCHAR(256), -- Public & Private Field
    user_arn VARCHAR(2048),
    status VARCHAR(20),
    age_days INTEGER,
    needs_rotation BOOLEAN,
    last_test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS RESOURCE (
    arn VARCHAR(2048) PRIMARY KEY,
    service_type VARCHAR(50),
    region_code VARCHAR(50),
    meta_data JSON
);
