CREATE DATABASE IF NOT EXISTS ids_db;
USE ids_db;

CREATE TABLE IF NOT EXISTS AWS_ACCOUNT (
    account_id VARCHAR(12) PRIMARY KEY,
    alias VARCHAR(255),
    last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS IAM_USER (
    user_arn VARCHAR(768) PRIMARY KEY,
    user_name VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS API_KEY (
    access_key_id VARCHAR(128) PRIMARY KEY,
    secret_access_key VARCHAR(256), -- Public & Private Field
    user_arn VARCHAR(768),
    status VARCHAR(20),
    age_days INTEGER,
    needs_rotation BOOLEAN,
    last_test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS RESOURCE (
    arn VARCHAR(768) PRIMARY KEY,
    service_type VARCHAR(50),
    region_code VARCHAR(50),
    meta_data JSON
);

-- Tables IDS (déployées sur Raspberry Pi)
CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    severity INT NOT NULL,
    signature TEXT NOT NULL,
    src_ip VARCHAR(45),
    dest_ip VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    cpu_percent DECIMAL(5,2),
    memory_percent DECIMAL(5,2),
    disk_percent DECIMAL(5,2),
    temperature DECIMAL(5,2),
    INDEX idx_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS deployment_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aws_region VARCHAR(50),
    elk_ip VARCHAR(45),
    elastic_password VARCHAR(255),
    pi_host VARCHAR(255),
    pi_user VARCHAR(50),
    pi_password VARCHAR(255),
    sudo_password VARCHAR(255),
    remote_dir VARCHAR(500),
    mirror_interface VARCHAR(50),
    ssh_key_path VARCHAR(500),
    INDEX idx_created (created_at)
);

CREATE TABLE IF NOT EXISTS ec2_instances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    instance_id VARCHAR(50) UNIQUE NOT NULL,
    region VARCHAR(50) NOT NULL,
    instance_type VARCHAR(50),
    public_ip VARCHAR(45),
    private_ip VARCHAR(45),
    state VARCHAR(20),
    elk_deployed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_state (state),
    INDEX idx_updated (updated_at)
);

-- Table pour Elasticsearch & Kibana credentials
CREATE TABLE IF NOT EXISTS elk_credentials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    url VARCHAR(500),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_service_user (service_name, username),
    INDEX idx_service (service_name)
);
