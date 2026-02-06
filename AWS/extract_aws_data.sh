#!/usr/bin/env bash
set -euo pipefail

# ============================================
# Extract AWS Data and Generate SQL Seeds
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATAS_DIR="$SCRIPT_DIR/datas"
CONFIG_FILE="$SCRIPT_DIR/../config.json"

mkdir -p "$DATAS_DIR"

echo "🔍 Extracting AWS data..."

# Charger credentials AWS depuis config
AWS_REGION=$(jq -r '.aws_region // "eu-west-1"' "$CONFIG_FILE")
AWS_ACCESS_KEY=$(jq -r '.aws_access_key_id // ""' "$CONFIG_FILE")
AWS_SECRET_KEY=$(jq -r '.aws_secret_access_key // ""' "$CONFIG_FILE")

# Configurer AWS CLI si credentials fournis
if [[ -n "$AWS_ACCESS_KEY" && -n "$AWS_SECRET_KEY" ]]; then
    export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_KEY"
    export AWS_DEFAULT_REGION="$AWS_REGION"
fi

# ============================================
# 1. AWS ACCOUNT INFO
# ============================================
echo "📊 Extracting AWS account info..."
cat > "$DATAS_DIR/01_aws_account.sql" <<'EOF'
-- AWS Account Information
USE ids_db;

INSERT INTO AWS_ACCOUNT (account_id, alias, last_scan) VALUES
EOF

if command -v aws &>/dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "000000000000")
    ACCOUNT_ALIAS=$(aws iam list-account-aliases --query 'AccountAliases[0]' --output text 2>/dev/null || echo "default")
else
    ACCOUNT_ID="000000000000"
    ACCOUNT_ALIAS="default"
fi

cat >> "$DATAS_DIR/01_aws_account.sql" <<EOF
('$ACCOUNT_ID', '$ACCOUNT_ALIAS', NOW())
ON DUPLICATE KEY UPDATE alias='$ACCOUNT_ALIAS', last_scan=NOW();
EOF

echo "✅ AWS account data saved"

# ============================================
# 2. IAM USERS
# ============================================
echo "📊 Extracting IAM users..."
cat > "$DATAS_DIR/02_iam_users.sql" <<'EOF'
-- IAM Users
USE ids_db;

EOF

if command -v aws &>/dev/null && aws iam list-users &>/dev/null; then
    aws iam list-users --query 'Users[*].[Arn,UserName]' --output text 2>/dev/null | while read -r arn username; do
        # Check if user has admin access
        IS_ADMIN=0
        if aws iam list-attached-user-policies --user-name "$username" --query 'AttachedPolicies[?PolicyName==`AdministratorAccess`]' --output text 2>/dev/null | grep -q "AdministratorAccess"; then
            IS_ADMIN=1
        fi
        
        echo "INSERT INTO IAM_USER (user_arn, user_name, is_admin) VALUES" >> "$DATAS_DIR/02_iam_users.sql"
        echo "('$arn', '$username', $IS_ADMIN)" >> "$DATAS_DIR/02_iam_users.sql"
        echo "ON DUPLICATE KEY UPDATE user_name='$username', is_admin=$IS_ADMIN;" >> "$DATAS_DIR/02_iam_users.sql"
    done
    echo "✅ IAM users data saved"
else
    echo "-- No IAM data available" >> "$DATAS_DIR/02_iam_users.sql"
    echo "⚠️  AWS CLI not configured, skipping IAM users"
fi

# ============================================
# 3. API KEYS
# ============================================
echo "📊 Extracting API keys..."
cat > "$DATAS_DIR/03_api_keys.sql" <<'EOF'
-- API Keys
USE ids_db;

EOF

if command -v aws &>/dev/null && aws iam list-users &>/dev/null; then
    aws iam list-users --query 'Users[*].UserName' --output text 2>/dev/null | while read -r username; do
        aws iam list-access-keys --user-name "$username" --query 'AccessKeyMetadata[*].[AccessKeyId,Status,CreateDate]' --output text 2>/dev/null | while read -r key_id status create_date; do
            # Calculate age in days
            CREATE_EPOCH=$(date -d "$create_date" +%s 2>/dev/null || echo 0)
            NOW_EPOCH=$(date +%s)
            AGE_DAYS=$(( (NOW_EPOCH - CREATE_EPOCH) / 86400 ))
            
            # Determine if needs rotation (>90 days)
            NEEDS_ROTATION=0
            if [[ $AGE_DAYS -gt 90 ]]; then
                NEEDS_ROTATION=1
            fi
            
            USER_ARN="arn:aws:iam::$ACCOUNT_ID:user/$username"
            
            echo "INSERT INTO API_KEY (access_key_id, secret_access_key, user_arn, status, age_days, needs_rotation, last_test_date) VALUES" >> "$DATAS_DIR/03_api_keys.sql"
            echo "('$key_id', 'HIDDEN', '$USER_ARN', '$status', $AGE_DAYS, $NEEDS_ROTATION, NOW())" >> "$DATAS_DIR/03_api_keys.sql"
            echo "ON DUPLICATE KEY UPDATE status='$status', age_days=$AGE_DAYS, needs_rotation=$NEEDS_ROTATION, last_test_date=NOW();" >> "$DATAS_DIR/03_api_keys.sql"
        done
    done
    echo "✅ API keys data saved"
else
    echo "-- No API keys data available" >> "$DATAS_DIR/03_api_keys.sql"
    echo "⚠️  Skipping API keys"
fi

# ============================================
# 4. EC2 INSTANCES
# ============================================
echo "📊 Extracting EC2 instances..."
cat > "$DATAS_DIR/04_ec2_instances.sql" <<'EOF'
-- EC2 Instances
USE ids_db;

EOF

if command -v aws &>/dev/null; then
    # Get all regions
    REGIONS=$(aws ec2 describe-regions --query 'Regions[*].RegionName' --output text 2>/dev/null || echo "$AWS_REGION")
    
    for region in $REGIONS; do
        aws ec2 describe-instances --region "$region" \
            --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,PublicIpAddress,PrivateIpAddress,State.Name]' \
            --output text 2>/dev/null | while read -r instance_id instance_type public_ip private_ip state; do
            
            # Check if it's an ELK instance (has tag Project=ids2)
            HAS_ELK=0
            if aws ec2 describe-tags --region "$region" --filters "Name=resource-id,Values=$instance_id" "Name=key,Values=Project" --query 'Tags[?Value==`ids2`]' --output text 2>/dev/null | grep -q "ids2"; then
                HAS_ELK=1
            fi
            
            echo "INSERT INTO ec2_instances (instance_id, region, instance_type, public_ip, private_ip, state, elk_deployed) VALUES" >> "$DATAS_DIR/04_ec2_instances.sql"
            echo "('$instance_id', '$region', '$instance_type', '$public_ip', '$private_ip', '$state', $HAS_ELK)" >> "$DATAS_DIR/04_ec2_instances.sql"
            echo "ON DUPLICATE KEY UPDATE instance_type='$instance_type', public_ip='$public_ip', private_ip='$private_ip', state='$state', elk_deployed=$HAS_ELK, updated_at=NOW();" >> "$DATAS_DIR/04_ec2_instances.sql"
        done
    done
    echo "✅ EC2 instances data saved"
else
    echo "-- No EC2 data available" >> "$DATAS_DIR/04_ec2_instances.sql"
    echo "⚠️  Skipping EC2 instances"
fi

# ============================================
# 5. ELASTICSEARCH & KIBANA CREDENTIALS
# ============================================
echo "📊 Creating Elasticsearch/Kibana credentials..."
cat > "$DATAS_DIR/05_elk_credentials.sql" <<'EOF'
-- Elasticsearch & Kibana Credentials
USE ids_db;

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
EOF

echo "✅ ELK credentials saved"

# ============================================
# 6. DEPLOYMENT CONFIG FROM config.json
# ============================================
echo "📊 Extracting deployment config..."
ELASTIC_PASSWORD=$(jq -r '.elastic_password // "admin"' "$CONFIG_FILE")
PI_HOST=$(jq -r '.pi_host // "sinik"' "$CONFIG_FILE")
PI_IP=$(jq -r '.pi_ip // "192.168.178.66"' "$CONFIG_FILE")
PI_USER=$(jq -r '.pi_user // "pi"' "$CONFIG_FILE")
PI_PASSWORD=$(jq -r '.pi_password // "pi"' "$CONFIG_FILE")
SUDO_PASSWORD=$(jq -r '.sudo_password // "pi"' "$CONFIG_FILE")
REMOTE_DIR=$(jq -r '.remote_dir // "/opt/ids2"' "$CONFIG_FILE")
MIRROR_INTERFACE=$(jq -r '.mirror_interface // "eth0"' "$CONFIG_FILE")
SSH_KEY_PATH=$(jq -r '.ssh_key_path // "/home/tor/.ssh/pi_key"' "$CONFIG_FILE")

cat > "$DATAS_DIR/06_deployment_config.sql" <<EOF
-- Deployment Configuration
USE ids_db;

INSERT INTO deployment_config (
    aws_region, elk_ip, elastic_password, pi_host, pi_user, 
    pi_password, sudo_password, remote_dir, mirror_interface, ssh_key_path
) VALUES (
    '$AWS_REGION', '$PI_IP', '$ELASTIC_PASSWORD', '$PI_HOST', '$PI_USER',
    '$PI_PASSWORD', '$SUDO_PASSWORD', '$REMOTE_DIR', '$MIRROR_INTERFACE', '$SSH_KEY_PATH'
);
EOF

echo "✅ Deployment config saved"

# ============================================
# SUMMARY
# ============================================
echo ""
echo "============================================"
echo "✅ AWS Data Extraction Complete!"
echo "============================================"
echo ""
echo "Generated SQL files in $DATAS_DIR:"
ls -lh "$DATAS_DIR"/*.sql 2>/dev/null || echo "No SQL files generated"
echo ""
echo "Files will be automatically loaded when MySQL container starts."
echo ""
echo "To view a file:"
echo "  cat $DATAS_DIR/01_aws_account.sql"
