#!/bin/bash
# Generate RSA keys for OIDC JWT signing
# This script creates a private key and public key for signing JWT tokens

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/../certs"

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"

echo "Generating OIDC JWT signing keys..."

# Generate private key
openssl genrsa -out "${CERTS_DIR}/oidc-private-key.pem" 2048

# Generate public key from private key
openssl rsa -in "${CERTS_DIR}/oidc-private-key.pem" -pubout -out "${CERTS_DIR}/oidc-public-key.pem"

echo ""
echo "OIDC JWT keys generated successfully!"
echo "Private key: ${CERTS_DIR}/oidc-private-key.pem"
echo "Public key: ${CERTS_DIR}/oidc-public-key.pem"
echo ""
echo "Next steps:"
echo "1. Upload keys to SSM Parameter Store using:"
echo "   ./scripts/upload-oidc-keys.sh"
echo ""
