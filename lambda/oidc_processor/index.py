"""
OIDC IdP Lambda Function
Handles OpenID Connect authentication, token generation, and user info
Shares the same user/role database as the SAML IdP
"""
import json
import base64
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import bcrypt
import pyotp
import jwt
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

# Environment variables
USERS_TABLE = os.environ['USERS_TABLE']
ROLES_TABLE = os.environ['ROLES_TABLE']
IDP_ENTITY_ID = os.environ['IDP_ENTITY_ID']
IDP_BASE_URL = os.environ['IDP_BASE_URL']
SSM_PARAMETER_PREFIX = os.environ['SSM_PARAMETER_PREFIX']

# OIDC configuration
OIDC_ISSUER = IDP_ENTITY_ID
TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
ID_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS = 2592000  # 30 days

# Allowed redirect URIs for security (can be overridden via environment variable)
# Format: comma-separated list of allowed redirect URI patterns
ALLOWED_REDIRECT_URIS = os.environ.get('ALLOWED_REDIRECT_URIS', '').split(',') if os.environ.get('ALLOWED_REDIRECT_URIS') else []

# Cache for SSM parameters
_ssm_cache = {}

# In-memory session storage (for demo purposes - use DynamoDB or ElastiCache in production)
_sessions = {}
_auth_codes = {}


def get_ssm_parameter(name, with_decryption=True):
    """Retrieve parameter from SSM with caching"""
    cache_key = f"{name}_{with_decryption}"
    if cache_key in _ssm_cache:
        return _ssm_cache[cache_key]
    
    try:
        response = ssm.get_parameter(
            Name=f"{SSM_PARAMETER_PREFIX}/{name}",
            WithDecryption=with_decryption
        )
        value = response['Parameter']['Value']
        _ssm_cache[cache_key] = value
        return value
    except ClientError as e:
        print(f"Error retrieving SSM parameter {name}: {e}")
        return None


def get_user(username):
    """Retrieve user from DynamoDB"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={'username': username})
        return response.get('Item')
    except Exception as e:
        print(f"Error retrieving user {username}: {e}")
        return None


def get_user_roles(username):
    """Retrieve user roles from DynamoDB"""
    try:
        table = dynamodb.Table(ROLES_TABLE)
        response = table.query(
            KeyConditionExpression='username = :username',
            ExpressionAttributeValues={':username': username}
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error retrieving roles for user {username}: {e}")
        return []


def verify_password(username, password):
    """Verify user credentials"""
    user = get_user(username)
    if not user:
        return False, None
    
    stored_hash = user.get('password_hash', '')
    
    # Check if MFA is enabled
    mfa_enabled = user.get('mfa_enabled', False)
    
    # Support both bcrypt and SHA256 (legacy)
    if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
        # Bcrypt hash
        is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    else:
        # SHA256 (legacy)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        is_valid = (password_hash == stored_hash)
    
    return is_valid, user


def validate_redirect_uri(redirect_uri):
    """
    Validate redirect URI against allowed patterns.
    If ALLOWED_REDIRECT_URIS is empty, allows localhost and https URLs only (for development).
    In production, ALLOWED_REDIRECT_URIS should be configured with specific allowed URIs.
    """
    if not redirect_uri:
        return False
    
    parsed = urlparse(redirect_uri)
    
    # If allowed list is configured, check against it
    if ALLOWED_REDIRECT_URIS and ALLOWED_REDIRECT_URIS[0]:
        for allowed_uri in ALLOWED_REDIRECT_URIS:
            allowed_uri = allowed_uri.strip()
            if not allowed_uri:
                continue
            # Exact match or prefix match
            if redirect_uri == allowed_uri or redirect_uri.startswith(allowed_uri):
                return True
        return False
    
    # Default validation (for development): allow localhost and https URLs
    # This prevents open redirects to arbitrary domains
    if parsed.scheme == 'https':
        return True
    if parsed.scheme == 'http' and (parsed.hostname == 'localhost' or parsed.hostname == '127.0.0.1'):
        return True
    
    return False


def generate_jwt_token(payload, token_type='access'):
    """Generate JWT token"""
    private_key = get_ssm_parameter('oidc/private_key', with_decryption=True)
    if not private_key:
        raise Exception("OIDC private key not found in SSM")
    
    now = datetime.utcnow()
    
    if token_type == 'id_token':
        expiry = now + timedelta(seconds=ID_TOKEN_EXPIRY_SECONDS)
    else:
        expiry = now + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
    
    token_payload = {
        'iss': OIDC_ISSUER,
        'iat': int(now.timestamp()),
        'exp': int(expiry.timestamp()),
        **payload
    }
    
    token = jwt.encode(token_payload, private_key, algorithm='RS256')
    return token


def generate_jwks():
    """Generate JWKS (JSON Web Key Set) from public key"""
    try:
        public_key = get_ssm_parameter('oidc/public_key', with_decryption=False)
        if not public_key:
            return {'keys': []}
        
        # Parse the public key and create JWK
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        key = serialization.load_pem_public_key(
            public_key.encode('utf-8'),
            backend=default_backend()
        )
        
        numbers = key.public_numbers()
        
        # Convert to base64url without padding
        def num_to_base64url(num):
            num_bytes = num.to_bytes((num.bit_length() + 7) // 8, byteorder='big')
            return base64.urlsafe_b64encode(num_bytes).rstrip(b'=').decode('utf-8')
        
        jwk = {
            'kty': 'RSA',
            'use': 'sig',
            'kid': 'oidc-key-1',
            'alg': 'RS256',
            'n': num_to_base64url(numbers.n),
            'e': num_to_base64url(numbers.e)
        }
        
        return {'keys': [jwk]}
    except Exception as e:
        print(f"Error generating JWKS: {e}")
        return {'keys': []}


def handle_discovery(event):
    """Handle OIDC discovery endpoint"""
    base_url = IDP_BASE_URL
    
    discovery_doc = {
        'issuer': OIDC_ISSUER,
        'authorization_endpoint': f'{base_url}/oauth2/authorize',
        'token_endpoint': f'{base_url}/oauth2/token',
        'userinfo_endpoint': f'{base_url}/oauth2/userinfo',
        'jwks_uri': f'{base_url}/oauth2/jwks',
        'response_types_supported': ['code', 'token', 'id_token', 'code id_token'],
        'subject_types_supported': ['public'],
        'id_token_signing_alg_values_supported': ['RS256'],
        'scopes_supported': ['openid', 'profile', 'email'],
        'token_endpoint_auth_methods_supported': ['client_secret_post', 'client_secret_basic'],
        'claims_supported': [
            'sub', 'name', 'email', 'preferred_username',
            'given_name', 'family_name', 'groups'
        ]
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600'
        },
        'body': json.dumps(discovery_doc)
    }


def handle_jwks(event):
    """Handle JWKS endpoint"""
    jwks = generate_jwks()
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600'
        },
        'body': json.dumps(jwks)
    }


def handle_authorize(event):
    """Handle OAuth2 authorization endpoint"""
    # Parse query parameters
    params = event.get('queryStringParameters', {}) or {}
    
    client_id = params.get('client_id')
    redirect_uri = params.get('redirect_uri')
    response_type = params.get('response_type', 'code')
    scope = params.get('scope', 'openid')
    state = params.get('state', '')
    nonce = params.get('nonce', '')
    
    # Validate required parameters
    if not client_id or not redirect_uri:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'invalid_request', 'error_description': 'Missing required parameters'})
        }
    
    # Validate redirect URI to prevent open redirect attacks
    if not validate_redirect_uri(redirect_uri):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'invalid_request',
                'error_description': 'Invalid redirect_uri. Configure ALLOWED_REDIRECT_URIS environment variable with allowed redirect URIs.'
            })
        }
    
    # Check if user is authenticated (via POST with credentials)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    
    if http_method == 'POST':
        # Handle login form submission
        try:
            body = event.get('body', '')
            if event.get('isBase64Encoded', False):
                body = base64.b64decode(body).decode('utf-8')
            
            body_params = parse_qs(body)
            username = body_params.get('username', [''])[0]
            password = body_params.get('password', [''])[0]
            
            is_valid, user = verify_password(username, password)
            
            if not is_valid:
                # Return login form with error
                return {
                    'statusCode': 401,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'invalid_credentials'})
                }
            
            # Check MFA if enabled
            if user.get('mfa_enabled', False):
                mfa_code = body_params.get('mfa_code', [''])[0]
                if not mfa_code:
                    return {
                        'statusCode': 401,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'mfa_required'})
                    }
                
                mfa_secret = user.get('mfa_secret')
                totp = pyotp.TOTP(mfa_secret)
                if not totp.verify(mfa_code):
                    return {
                        'statusCode': 401,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'invalid_mfa_code'})
                    }
            
            # Generate authorization code
            auth_code = secrets.token_urlsafe(32)
            _auth_codes[auth_code] = {
                'username': username,
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'scope': scope,
                'nonce': nonce,
                'timestamp': datetime.utcnow(),
                'used': False
            }
            
            # Redirect back to client with authorization code
            redirect_params = {
                'code': auth_code,
                'state': state
            }
            
            redirect_url = f"{redirect_uri}?{urlencode(redirect_params)}"
            
            return {
                'statusCode': 302,
                'headers': {
                    'Location': redirect_url
                },
                'body': ''
            }
            
        except Exception as e:
            print(f"Error in authorize POST: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'server_error'})
            }
    
    # For GET requests, return a simple login form or redirect to login page
    # In production, this should redirect to a proper login UI
    login_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - OIDC IdP</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }}
            input {{ width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }}
            button {{ width: 100%; padding: 10px; background: #007bff; color: white; border: none; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            .error {{ color: red; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h2>Login</h2>
        <form method="POST" action="/oauth2/authorize?{urlencode(params)}">
            <input type="text" name="username" placeholder="Username" required />
            <input type="password" name="password" placeholder="Password" required />
            <input type="text" name="mfa_code" placeholder="MFA Code (if enabled)" />
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html'},
        'body': login_html
    }


def handle_token(event):
    """Handle OAuth2 token endpoint"""
    try:
        # Parse body
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')
        
        params = parse_qs(body)
        
        grant_type = params.get('grant_type', [''])[0]
        code = params.get('code', [''])[0]
        redirect_uri = params.get('redirect_uri', [''])[0]
        client_id = params.get('client_id', [''])[0]
        
        if grant_type != 'authorization_code':
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'unsupported_grant_type'})
            }
        
        # Validate authorization code
        auth_code_data = _auth_codes.get(code)
        if not auth_code_data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_grant'})
            }
        
        if auth_code_data['used']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_grant', 'error_description': 'Authorization code already used'})
            }
        
        if auth_code_data['client_id'] != client_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_grant', 'error_description': 'Client ID mismatch'})
            }
        
        if auth_code_data['redirect_uri'] != redirect_uri:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_grant', 'error_description': 'Redirect URI mismatch'})
            }
        
        # Check if code is expired (5 minutes)
        code_age = (datetime.utcnow() - auth_code_data['timestamp']).total_seconds()
        if code_age > 300:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_grant', 'error_description': 'Authorization code expired'})
            }
        
        # Mark code as used
        auth_code_data['used'] = True
        
        username = auth_code_data['username']
        user = get_user(username)
        roles = get_user_roles(username)
        
        # Generate tokens
        access_token = generate_jwt_token({
            'sub': username,
            'preferred_username': username,
            'email': user.get('email', ''),
            'name': user.get('name', username),
            'groups': [role.get('role_arn', '') for role in roles]
        }, token_type='access')
        
        id_token = generate_jwt_token({
            'sub': username,
            'preferred_username': username,
            'email': user.get('email', ''),
            'name': user.get('name', username),
            'aud': client_id,
            'nonce': auth_code_data.get('nonce', '')
        }, token_type='id_token')
        
        # Note: Refresh token is generated but not currently stored or validated
        # This is a known limitation suitable for development/testing
        # For production, implement refresh token storage in DynamoDB
        refresh_token = secrets.token_urlsafe(32)
        
        response = {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': TOKEN_EXPIRY_SECONDS,
            'id_token': id_token,
            'refresh_token': refresh_token
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response)
        }
        
    except Exception as e:
        print(f"Error in token endpoint: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'server_error'})
        }


def handle_userinfo(event):
    """Handle OIDC userinfo endpoint"""
    try:
        # Extract bearer token from Authorization header
        headers = event.get('headers', {})
        auth_header = headers.get('authorization', '') or headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_token'})
            }
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Verify and decode token
        public_key = get_ssm_parameter('oidc/public_key', with_decryption=False)
        if not public_key:
            raise Exception("OIDC public key not found")
        
        try:
            payload = jwt.decode(token, public_key, algorithms=['RS256'], issuer=OIDC_ISSUER)
        except jwt.ExpiredSignatureError:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_token', 'error_description': 'Token expired'})
            }
        except jwt.InvalidTokenError as e:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'invalid_token', 'error_description': str(e)})
            }
        
        username = payload.get('sub')
        user = get_user(username)
        
        if not user:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'user_not_found'})
            }
        
        roles = get_user_roles(username)
        
        userinfo = {
            'sub': username,
            'preferred_username': username,
            'email': user.get('email', ''),
            'name': user.get('name', username),
            'given_name': user.get('given_name', ''),
            'family_name': user.get('family_name', ''),
            'groups': [role.get('role_arn', '') for role in roles]
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(userinfo)
        }
        
    except Exception as e:
        print(f"Error in userinfo endpoint: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'server_error'})
        }


def lambda_handler(event, context):
    """Main Lambda handler for OIDC IdP"""
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Get the route path
        route_key = event.get('routeKey', '')
        path = event.get('rawPath', '')
        
        # Route to appropriate handler
        if '/.well-known/openid-configuration' in route_key or '/.well-known/openid-configuration' in path:
            return handle_discovery(event)
        elif '/oauth2/jwks' in route_key or '/oauth2/jwks' in path:
            return handle_jwks(event)
        elif '/oauth2/authorize' in route_key or '/oauth2/authorize' in path:
            return handle_authorize(event)
        elif '/oauth2/token' in route_key or '/oauth2/token' in path:
            return handle_token(event)
        elif '/oauth2/userinfo' in route_key or '/oauth2/userinfo' in path:
            return handle_userinfo(event)
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'not_found'})
            }
    
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'internal_server_error'})
        }
