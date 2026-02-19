#!/bin/bash
# Upload OIDC JWT keys to AWS SSM Parameter Store

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/../certs"

# Configuration
PROJECT_NAME="${PROJECT_NAME:-simple-saml-idp}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Check if keys exist
if [ ! -f "${CERTS_DIR}/oidc-private-key.pem" ] || [ ! -f "${CERTS_DIR}/oidc-public-key.pem" ]; then
    echo "Error: OIDC keys not found in ${CERTS_DIR}"
    echo "Please run ./scripts/generate-oidc-keys.sh first"
    exit 1
fi

echo "Uploading OIDC JWT keys to SSM Parameter Store..."

# Upload private key (SecureString for encryption)
aws ssm put-parameter \
    --name "/${PROJECT_NAME}/${ENVIRONMENT}/oidc/private_key" \
    --value "$(cat ${CERTS_DIR}/oidc-private-key.pem)" \
    --type SecureString \
    --overwrite \
    --region "${AWS_REGION}"

echo "✓ Private key uploaded to /${PROJECT_NAME}/${ENVIRONMENT}/oidc/private_key"

# Upload public key (String type)
aws ssm put-parameter \
    --name "/${PROJECT_NAME}/${ENVIRONMENT}/oidc/public_key" \
    --value "$(cat ${CERTS_DIR}/oidc-public-key.pem)" \
    --type String \
    --overwrite \
    --region "${AWS_REGION}"

echo "✓ Public key uploaded to /${PROJECT_NAME}/${ENVIRONMENT}/oidc/public_key"

echo ""
echo "OIDC JWT keys uploaded successfully!"
echo ""
