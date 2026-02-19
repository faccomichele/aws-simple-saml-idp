#!/bin/bash
# Build Lambda functions and layers with dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "Building Lambda functions and layers..."

# Function to build a Lambda layer
build_layer() {
    local LAMBDA_NAME=$1
    local LAMBDA_DIR="${PROJECT_ROOT}/lambda/${LAMBDA_NAME}"
    local LAYER_DIR="${LAMBDA_DIR}/python"
    local LAYER_ZIP="${PROJECT_ROOT}/lambda/${LAMBDA_NAME}-layer.zip"
    
    echo ""
    echo "Building layer for ${LAMBDA_NAME}..."
    
    # Clean up old layer directory
    rm -rf "${LAYER_DIR}"
    mkdir -p "${LAYER_DIR}"
    
    # Install dependencies into layer directory
    if [ -f "${LAMBDA_DIR}/requirements.txt" ]; then
        pip3 install -r "${LAMBDA_DIR}/requirements.txt" -t "${LAYER_DIR}" --upgrade
    fi
    
    # Create layer zip
    cd "${LAMBDA_DIR}"
    rm -f "${LAYER_ZIP}"
    zip -r "${LAYER_ZIP}" python/ -q
    
    # Clean up layer directory
    rm -rf "${LAYER_DIR}"
    
    echo "✓ Layer built: ${LAYER_ZIP}"
}

# Function to build a Lambda function
build_function() {
    local LAMBDA_NAME=$1
    local LAMBDA_DIR="${PROJECT_ROOT}/lambda/${LAMBDA_NAME}"
    local FUNCTION_ZIP="${PROJECT_ROOT}/lambda/${LAMBDA_NAME}.zip"
    
    echo ""
    echo "Building function ${LAMBDA_NAME}..."
    
    # Create function zip (just the index.py)
    cd "${LAMBDA_DIR}"
    rm -f "${FUNCTION_ZIP}"
    zip -j "${FUNCTION_ZIP}" index.py -q
    
    echo "✓ Function built: ${FUNCTION_ZIP}"
}

# Build SAML Processor
build_layer "saml_processor"
build_function "saml_processor"

# Build User/Role Manager
build_layer "manage_users_roles"
build_function "manage_users_roles"

# Build OIDC Processor
build_layer "oidc_processor"
build_function "oidc_processor"

echo ""
echo "All Lambda functions and layers built successfully!"
echo ""
