-- Elasticsearch & Kibana Credentials

-- Table pour stocker les credentials ELK
CREATE TABLE IF NOT EXISTS elk_credentials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_service_user (service_name, username)
);

-- Elasticsearch credentials par défaut
INSERT INTO elk_credentials (service_name, username, password, url) VALUES
('elasticsearch', 'elastic', 'admin', 'http://localhost:9200')
ON DUPLICATE KEY UPDATE password='admin', url='http://localhost:9200', updated_at=NOW();

-- Kibana credentials (même que Elasticsearch)
INSERT INTO elk_credentials (service_name, username, password, url) VALUES
('kibana', 'elastic', 'admin', 'http://localhost:5601')
ON DUPLICATE KEY UPDATE password='admin', url='http://localhost:5601', updated_at=NOW();
