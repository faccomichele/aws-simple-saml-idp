"""
SAML IdP Lambda Function for AWS Console SSO
Handles SAML authentication, assertion generation, and AWS Console login
"""
import json
import base64
import os
import io
import re
import zlib
import html as html_utils
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode
from xml.sax.saxutils import escape as xml_escape

import bcrypt
import pyotp
import qrcode
from lxml import etree
from signxml import XMLSigner, methods
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

# Environment variables
ENVIRONMENT = os.environ['ENVIRONMENT']
USERS_TABLE = os.environ['USERS_TABLE']
ROLES_TABLE = os.environ['ROLES_TABLE']
IDP_ENTITY_ID = os.environ['IDP_ENTITY_ID']
IDP_BASE_URL = os.environ['IDP_BASE_URL']
SESSION_DURATION = int(os.environ['SESSION_DURATION'])
SSM_PARAMETER_PREFIX = os.environ['SSM_PARAMETER_PREFIX']
ALLOWED_AWS_ACCOUNTS = json.loads(os.environ.get('ALLOWED_AWS_ACCOUNTS', '[]'))
SAML_PROVIDER_NAME = os.environ.get('SAML_PROVIDER_NAME', 'SimpleSAMLIdP')

# Default ACS URL for backward compatibility
DEFAULT_ACS_URL = 'https://signin.aws.amazon.com/saml'

# Defaults preserving classic AWS Console behaviour
DEFAULT_AUDIENCE = 'urn:amazon:webservices'
DEFAULT_NAMEID_FORMAT = 'urn:oasis:names:tc:SAML:2.0:nameid-format:persistent'

# URL of the static login page (used to hand off SP-initiated AuthnRequests)
LOGIN_PAGE_URL = os.environ.get('LOGIN_PAGE_URL', 'placeholder')

VALID_REQUEST_ID = re.compile(r'[_A-Za-z0-9.\-]{1,256}')

# Attribute prefix for custom SAML attributes
ATTR_PREFIX = 'attr_'

# Attribute mapping table: short names (stored in DynamoDB) -> full SAML attribute names
# This is now loaded from environment variable set by Terraform
try:
    ATTRIBUTE_MAPPING = json.loads(os.environ.get('ATTRIBUTE_MAPPING', '{}'))
except (json.JSONDecodeError, ValueError):
    print("Warning: Failed to load ATTRIBUTE_MAPPING from environment, using empty dict")
    ATTRIBUTE_MAPPING = {}

# Cache for SSM parameters
_ssm_cache = {}


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


# If `IDP_BASE_URL` was configured as the literal 'placeholder', attempt
# to load the real base URL from SSM at `{SSM_PARAMETER_PREFIX}/idp/base/url`.
# This keeps the environment configuration simple while allowing secure
# overrides through SSM Parameter Store.
try:
    if IDP_BASE_URL == 'placeholder':
        ssm_val = get_ssm_parameter('idp/base/url', with_decryption=False)
        if ssm_val:
            IDP_BASE_URL = ssm_val
        else:
            print(f"Warning: SSM parameter {SSM_PARAMETER_PREFIX}/idp/base/url not found; IDP_BASE_URL remains 'placeholder'")
except Exception as e:
    print(f"Error loading IDP_BASE_URL from SSM: {e}")

# If `LOGIN_PAGE_URL` was configured as the literal 'placeholder', fall back to
# the IdP entity ID (which defaults to the CloudFront distribution URL) so the
# SP-initiated flow can redirect users to the hosted login page.
try:
    if LOGIN_PAGE_URL == 'placeholder':
        if isinstance(IDP_ENTITY_ID, str) and IDP_ENTITY_ID.startswith('http'):
            LOGIN_PAGE_URL = IDP_ENTITY_ID.rstrip('/')
        else:
            print("Warning: LOGIN_PAGE_URL not set and IDP_ENTITY_ID is not a URL; SP-initiated login disabled")
except Exception as e:
    print(f"Error loading LOGIN_PAGE_URL: {e}")


def generate_saml_metadata():
    """Generate SAML metadata XML"""
    certificate = get_ssm_parameter('saml/certificate', with_decryption=False)
    if not certificate:
        certificate = "CERTIFICATE_NOT_CONFIGURED"
    
    # Remove PEM headers/footers and whitespace
    cert_clean = certificate.replace('-----BEGIN CERTIFICATE-----', '')
    cert_clean = cert_clean.replace('-----END CERTIFICATE-----', '')
    cert_clean = ''.join(cert_clean.split())
    
    sso_url = f"{IDP_BASE_URL}/sso"
    
    metadata = f'''<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
                  xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
                  entityID="{IDP_ENTITY_ID}">
  <IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <KeyDescriptor use="signing">
      <ds:KeyInfo>
        <ds:X509Data>
          <ds:X509Certificate>{cert_clean}</ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </KeyDescriptor>
    <SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                        Location="{sso_url}"/>
    <SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                        Location="{sso_url}"/>
  </IDPSSODescriptor>
</EntityDescriptor>'''
    
    return metadata


def generate_saml_response(username, role_arn, acs_url, session_duration=SESSION_DURATION,
                           custom_attributes=None, audience=None, name_id=None,
                           name_id_format=None, in_response_to=None):
    """
    Generate SAML Response for SAML-enabled applications
    
    Supports dynamic attribute generation based on custom_attributes dict.
    Attributes with 'attr_' prefix in custom_attributes are mapped to full SAML attribute names.
    
    Args:
        username: User identifier
        role_arn: AWS IAM role ARN (optional, only for AWS Console)
        acs_url: Assertion Consumer Service URL
        session_duration: Session duration in seconds
        custom_attributes: Dict of custom attributes with 'attr_' prefix keys
        audience: Intended audience (SP entity ID); defaults to 'urn:amazon:webservices'
        name_id: Value used for the NameID element; defaults to username
        name_id_format: NameID format URI; defaults to the persistent format
        in_response_to: AuthnRequest ID when answering an SP-initiated login
    """
    now = datetime.utcnow()
    not_before = now - timedelta(minutes=5)
    not_on_or_after = now + timedelta(seconds=session_duration)
    
    audience = audience or DEFAULT_AUDIENCE
    name_id_format = name_id_format or DEFAULT_NAMEID_FORMAT
    name_id_value = name_id or username
    
    # XML-escape all externally sourced values interpolated into the document
    esc_entity_id = xml_escape(IDP_ENTITY_ID)
    esc_acs_url = xml_escape(acs_url)
    esc_audience = xml_escape(audience)
    esc_name_id = xml_escape(name_id_value)
    esc_name_id_format = xml_escape(name_id_format)
    in_response_to_attr = f' InResponseTo="{xml_escape(in_response_to)}"' if in_response_to else ''
    
    # Initialize variables for AWS-specific attributes
    principal_arn = None
    account_id = None
    
    # Only process role_arn if provided and it's an AWS ARN
    if role_arn and role_arn.startswith('arn:aws:iam::'):
        # Extract account ID and role name from ARN
        # Format: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME
        arn_parts = role_arn.split(':')
        
        # Validate ARN format
        if len(arn_parts) < 6 or arn_parts[0] != 'arn' or arn_parts[2] != 'iam':
            raise ValueError(f"Invalid IAM role ARN format: {role_arn}")
        
        account_id = arn_parts[4]
        role_path = arn_parts[5] if len(arn_parts) > 5 else ''
        
        if not role_path.startswith('role/'):
            raise ValueError(f"ARN does not specify a role: {role_arn}")
        
        role_name = role_path.split('/')[-1]
        
        # Build principal ARN (for the SAML provider in the target account)
        principal_arn = f"arn:aws:iam::{account_id}:saml-provider/{SAML_PROVIDER_NAME}"
    
    # Generate unique IDs
    response_id = f"_{''.join(f'{b:02x}' for b in os.urandom(20))}"
    assertion_id = f"_{''.join(f'{b:02x}' for b in os.urandom(20))}"
    
    # Format timestamps
    issue_instant = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    not_before_str = not_before.strftime('%Y-%m-%dT%H:%M:%SZ')
    not_on_or_after_str = not_on_or_after.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Build AttributeStatement dynamically based on custom_attributes
    attributes_xml = []
    saml_attributes = dict(custom_attributes or {})

    if role_arn and not role_arn.startswith('arn:aws:iam::') and 'attr_role' not in saml_attributes:
        role_value = role_arn.rsplit(':', 1)[-1]
        if role_value:
            saml_attributes['attr_role'] = role_value
    
    # Process custom attributes with 'attr_' prefix
    if saml_attributes:
        for key, value in saml_attributes.items():
            if key.startswith(ATTR_PREFIX):
                # Check if we have a mapping for this attribute
                if key in ATTRIBUTE_MAPPING:
                    attr_name = ATTRIBUTE_MAPPING[key]
                    
                    # Handle special case for AWS Role attribute
                    if key == 'attr_aws_role' and role_arn and principal_arn:
                        # For AWS Role, combine role_arn and principal_arn
                        attr_value = f"{role_arn},{principal_arn}"
                    elif key == 'attr_aws_role_session_name':
                        # Use username as RoleSessionName
                        attr_value = username
                    elif key == 'attr_aws_session_duration':
                        # Use the provided value or default session duration
                        attr_value = str(value) if value else str(session_duration)
                    else:
                        # Use the value as-is
                        attr_value = str(value)
                    
                    # Build attribute XML
                    attr_xml = f'''      <saml:Attribute Name="{attr_name}">
        <saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xsi:type="xs:string">{xml_escape(attr_value)}</saml:AttributeValue>
      </saml:Attribute>'''
                    attributes_xml.append(attr_xml)
                else:
                    # For unknown attributes, use the key without 'attr_' prefix as the attribute name
                    attr_name = key[len(ATTR_PREFIX):]
                    attr_value = str(value)
                    attr_xml = f'''      <saml:Attribute Name="{attr_name}">
        <saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xsi:type="xs:string">{xml_escape(attr_value)}</saml:AttributeValue>
      </saml:Attribute>'''
                    attributes_xml.append(attr_xml)
    
    # If no custom attributes provided but role_arn exists, add default AWS attributes for backward compatibility
    if not attributes_xml and role_arn and principal_arn:
        attributes_xml.append(f'''      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/RoleSessionName">
        <saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xsi:type="xs:string">{username}</saml:AttributeValue>
      </saml:Attribute>''')
        attributes_xml.append(f'''      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/Role">
        <saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xsi:type="xs:string">{role_arn},{principal_arn}</saml:AttributeValue>
      </saml:Attribute>''')
        attributes_xml.append(f'''      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/SessionDuration">
        <saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xsi:type="xs:string">{session_duration}</saml:AttributeValue>
      </saml:Attribute>''')
    
    # Join all attributes
    attribute_statement = '\n'.join(attributes_xml) if attributes_xml else ''
    
    # SAML Response template with dynamic AttributeStatement
    saml_response = f'''<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                     xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                     ID="{response_id}"
                     Version="2.0"
                     IssueInstant="{issue_instant}"
                     Destination="{esc_acs_url}">
  <saml:Issuer>{esc_entity_id}</saml:Issuer>
  <samlp:Status>
    <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
  </samlp:Status>
  <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                  ID="{assertion_id}"
                  Version="2.0"
                  IssueInstant="{issue_instant}">
    <saml:Issuer>{esc_entity_id}</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="{esc_name_id_format}">{esc_name_id}</saml:NameID>
      <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
        <saml:SubjectConfirmationData NotOnOrAfter="{not_on_or_after_str}"
                                     Recipient="{esc_acs_url}"{in_response_to_attr}/>
      </saml:SubjectConfirmation>
    </saml:Subject>
    <saml:Conditions NotBefore="{not_before_str}"
                    NotOnOrAfter="{not_on_or_after_str}">
      <saml:AudienceRestriction>
        <saml:Audience>{esc_audience}</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AuthnStatement AuthnInstant="{issue_instant}"
                        SessionNotOnOrAfter="{not_on_or_after_str}">
      <saml:AuthnContext>
        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport</saml:AuthnContextClassRef>
      </saml:AuthnContext>
    </saml:AuthnStatement>
    <saml:AttributeStatement>
{attribute_statement}
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>'''
    
    # === Signing Logic ===
    try:
        # 1. Parse the generated XML string
        root = etree.fromstring(saml_response.encode('utf-8'))

        # 2. Retrieve credentials from SSM
        # Ensure your private key is stored in SSM without PEM headers or newlines if possible,
        # or handle formatting here. signxml expects a PEM-formatted string or bytes.
        private_key = get_ssm_parameter('saml/private_key', with_decryption=True)
        certificate = get_ssm_parameter('saml/certificate', with_decryption=False)
        
        if not private_key:
            print("Error: saml/private_key not found in SSM")
            raise Exception("SSM parameter saml/private_key is missing")

        # 3. Locate the Assertion element to sign
        ns = {'saml': 'urn:oasis:names:tc:SAML:2.0:assertion'}
        assertion = root.find('.//saml:Assertion', ns)
        
        if assertion is None:
            raise Exception("Malformed SAML: Assertion element not found")

        # 4. Sign the Assertion
        # AWS requires Enveloped Signature, RSA-SHA256, and Exclusive Canonicalization
        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"
        )
        
        signed_assertion = signer.sign(
            assertion,
            key=private_key,
            cert=certificate
        )

        # 5. Replace the unsigned assertion with the signed one
        assertion.getparent().replace(assertion, signed_assertion)
        
        # 6. Return the signed XML string
        return etree.tostring(root, encoding='unicode')

    except Exception as e:
        print(f"Error signing SAML response: {e}")
        # In case of signing failure, we re-raise to avoid sending unsigned/invalid SAML
        raise


def authenticate_user(username, password):
    """Authenticate user against DynamoDB"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={'username': username})
        
        if 'Item' not in response:
            return False
        
        user = response['Item']
        
        # Verify password using bcrypt
        # The password hash is stored as a string in DynamoDB, so we need to encode it to bytes
        stored_hash = user.get('password_hash')
        if not stored_hash:
            return False

        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return True
        
        return False
    except Exception as e:
        print(f"Authentication error: {e}")
        return False


def get_user(username):
    """Get user details from DynamoDB"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={'username': username})
        
        if 'Item' not in response:
            return None
        
        return response['Item']
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None


def verify_mfa_token(secret, token):
    """Verify TOTP token against the secret"""
    try:
        totp = pyotp.TOTP(secret)
        # Allow 1 interval before/after for clock skew
        return totp.verify(token, valid_window=1)
    except Exception as e:
        print(f"MFA verification error: {e}")
        return False


def generate_mfa_secret():
    """Generate a new MFA secret"""
    return pyotp.random_base32()


def generate_qr_code(username, secret):
    """Generate QR code for MFA setup"""
    try:
        # Create provisioning URI for Google Authenticator
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=f"{username} ({ENVIRONMENT})",
            issuer_name=IDP_ENTITY_ID.removeprefix('https://').removeprefix('http://')
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return img_base64
    except Exception as e:
        print(f"QR code generation error: {e}")
        return None


def save_mfa_secret(username, secret):
    """Save MFA secret to DynamoDB"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        table.update_item(
            Key={'username': username},
            UpdateExpression='SET mfa_secret = :secret, updated_at = :updated',
            ExpressionAttributeValues={
                ':secret': secret,
                ':updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        )
        return True
    except Exception as e:
        print(f"Error saving MFA secret: {e}")
        return False


def clear_mfa_secret(username):
    """Clear MFA secret from DynamoDB (for reset)"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        table.update_item(
            Key={'username': username},
            UpdateExpression='REMOVE mfa_secret SET updated_at = :updated',
            ExpressionAttributeValues={
                ':updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        )
        return True
    except Exception as e:
        print(f"Error clearing MFA secret: {e}")
        return False


def get_user_roles(username):
    """Get available AWS roles for a user"""
    try:
        table = dynamodb.Table(ROLES_TABLE)
        response = table.query(
            KeyConditionExpression='username = :username',
            ExpressionAttributeValues={':username': username}
        )
        
        roles = []
        for item in response.get('Items', []):
            role_arn = item.get('role_arn')
            
            # Skip invalid ARNs
            if not role_arn or ':' not in role_arn:
                print(f"Skipping invalid role ARN: {role_arn}")
                continue
            
            arn_parts = role_arn.split(':')
            
            if role_arn.startswith('arn:aws:'):
                # AWS IAM role ARN: validate format and apply the account allowlist
                if len(arn_parts) < 6 or arn_parts[0] != 'arn' or arn_parts[2] != 'iam':
                    print(f"Skipping malformed role ARN: {role_arn}")
                    continue
                
                account_id = arn_parts[4]
                
                # Filter by allowed accounts if configured
                if ALLOWED_AWS_ACCOUNTS and account_id not in ALLOWED_AWS_ACCOUNTS:
                    continue
                
                # Extract role name safely
                role_path = arn_parts[5] if len(arn_parts) > 5 else ''
                role_name = role_path.split('/')[-1] if '/' in role_path else role_path
            else:
                # Application pseudo-role (e.g. 'grafana:viewer') for non-AWS SaaS apps
                account_id = item.get('account_id', '')
                role_name = arn_parts[-1] if len(arn_parts) > 1 else role_arn
            
            roles.append({
                'role_arn': role_arn,
                'account_id': account_id,
                'role_name': role_name,
                'account_name': item.get('account_name', 'Unknown'),
                'description': item.get('description', ''),
                'acs_url': item.get('acs_url', DEFAULT_ACS_URL),
                'groups': [g.strip() for g in str(item.get('groups', '')).split(',') if g.strip()]
            })
        
        return roles
    except Exception as e:
        print(f"Error fetching roles: {e}")
        return []


def create_html_response(content, status_code=200):
    """Create HTML response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        },
        'body': content
    }


def create_error_html(message, status_code=400):
    """Create a minimal HTML error page"""
    safe_message = html_utils.escape(message, quote=True)
    content = f'''<!DOCTYPE html>
<html>
<head>
    <title>SSO Error</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             text-align: center; padding-top: 3rem;">
    <h1>Single Sign-On Error</h1>
    <p>{safe_message}</p>
    <p><a href="/">Back to login</a></p>
</body>
</html>'''
    return create_html_response(content, status_code)


def create_json_response(data, status_code=200):
    """Create JSON response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data)
    }


def handle_metadata(event):
    """Handle SAML metadata request"""
    metadata = generate_saml_metadata()
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/xml',
            'Cache-Control': 'public, max-age=3600'
        },
        'body': metadata
    }


def handle_login(event):
    """Handle login request and return available roles or MFA setup requirement"""
    try:
        body = event.get('body', '')
        if event.get('isBase64Encoded'):
            body = base64.b64decode(body).decode('utf-8')
        
        params = parse_qs(body)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]
        mfa_token = params.get('mfa_token', [''])[0]
        
        if not username or not password:
            return create_json_response({
                'success': False,
                'error': 'Username and password required'
            }, 400)
        
        # Authenticate user
        if not authenticate_user(username, password):
            return create_json_response({
                'success': False,
                'error': 'Invalid credentials'
            }, 401)
        
        # Get user details to check MFA status
        user = get_user(username)
        if not user:
            return create_json_response({
                'success': False,
                'error': 'User not found'
            }, 404)
        
        mfa_secret = user.get('mfa_secret')
        
        # If MFA is not set up, indicate that setup is needed
        if not mfa_secret:
            return create_json_response({
                'success': True,
                'username': username,
                'mfa_required': False,
                'mfa_setup_needed': True
            })
        
        # If MFA is set up but token not provided, request it
        if not mfa_token:
            return create_json_response({
                'success': True,
                'username': username,
                'mfa_required': True,
                'mfa_setup_needed': False
            })
        
        # Verify MFA token
        if not verify_mfa_token(mfa_secret, mfa_token):
            return create_json_response({
                'success': False,
                'error': 'Invalid MFA token'
            }, 401)
        
        # Get available roles
        roles = get_user_roles(username)
        
        if not roles:
            return create_json_response({
                'success': False,
                'error': 'No roles available for this user'
            }, 403)
        
        return create_json_response({
            'success': True,
            'username': username,
            'mfa_required': False,
            'mfa_setup_needed': False,
            'roles': roles
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return create_json_response({
            'success': False,
            'error': 'Internal server error'
        }, 500)


def parse_authn_request(saml_request_b64):
    """
    Decode a base64/DEFLATE encoded AuthnRequest (HTTP-Redirect binding) and
    extract its core fields. Falls back to plain base64 XML for HTTP-POST
    binding requests.
    """
    raw = base64.b64decode(saml_request_b64)
    try:
        xml_bytes = zlib.decompress(raw, -15)
    except zlib.error:
        xml_bytes = raw
    
    root = etree.fromstring(xml_bytes)
    
    protocol_ns = '{urn:oasis:names:tc:SAML:2.0:protocol}'
    assertion_ns = '{urn:oasis:names:tc:SAML:2.0:assertion}'
    
    if root.tag != f'{protocol_ns}AuthnRequest':
        raise ValueError('SAMLRequest is not an AuthnRequest')
    
    request_id = root.get('ID', '') or ''
    acs_url = root.get('AssertionConsumerServiceURL', '') or ''
    
    issuer_element = root.find(f'{assertion_ns}Issuer')
    issuer = issuer_element.text.strip() if issuer_element is not None and issuer_element.text else ''
    
    return request_id, acs_url, issuer


def handle_sp_initiated_request(saml_request, relay_state=''):
    """
    Handle an SP-initiated AuthnRequest: validate it and redirect the browser
    to the login page with the request context preserved in the URL fragment.
    The context is later POSTed back to /sso together with the credentials.
    """
    try:
        request_id, acs_url, issuer = parse_authn_request(saml_request)
    except Exception as e:
        print(f"Failed to parse AuthnRequest: {e}")
        return create_error_html('Invalid SAML authentication request', 400)
    
    print(f"Received AuthnRequest{f' from issuer {issuer}' if issuer else ''}")
    
    if not VALID_REQUEST_ID.fullmatch(request_id):
        return create_error_html('Invalid authentication request identifier', 400)
    
    if not acs_url.lower().startswith('https://'):
        return create_error_html('Only HTTPS assertion consumer URLs are supported', 400)
    
    if not LOGIN_PAGE_URL or not LOGIN_PAGE_URL.startswith('http'):
        return create_error_html('Login page URL is not configured', 500)
    
    context = {
        'sp_acs': acs_url,
        'in_response_to': request_id,
        'relay_state': relay_state or ''
    }
    login_page = LOGIN_PAGE_URL.rstrip('/') + '/'
    return {
        'statusCode': 302,
        'headers': {
            'Location': f'{login_page}#{urlencode(context)}',
            'Cache-Control': 'no-store'
        },
        'body': ''
    }


def handle_sso(event):
    """
    Handle SSO requests. Two flows are supported on this endpoint:
    - SP-initiated: a request carrying a SAMLRequest parameter redirects the
      browser to the login page with the request context.
    - IdP-initiated / portal: a POST carrying username and role_arn generates
      the signed SAML response for the selected role.
    """
    try:
        params = {}
        
        body = event.get('body', '')
        if body:
            if event.get('isBase64Encoded'):
                body = base64.b64decode(body).decode('utf-8')
            params.update(parse_qs(body, keep_blank_values=True))
        
        query_string_params = event.get('queryStringParameters') or {}
        for key, value in query_string_params.items():
            params.setdefault(key, [value])
        
        def get_param(name):
            values = params.get(name, [''])
            return values[0] if values else ''
        
        saml_request = get_param('SAMLRequest')
        if saml_request:
            return handle_sp_initiated_request(saml_request, get_param('RelayState'))
        
        username = get_param('username')
        role_arn = get_param('role_arn')
        acs_url = get_param('acs_url')
        sp_acs_url = get_param('sp_acs')
        in_response_to = get_param('in_response_to')
        relay_state = get_param('relay_state')
        
        if not username or not role_arn:
            return create_error_html('Invalid request parameters', 400)
        
        # Fetch role data for custom attributes, audience and NameID configuration
        try:
            table = dynamodb.Table(ROLES_TABLE)
            response = table.get_item(
                Key={
                    'username': username,
                    'role_arn': role_arn
                }
            )
            role_data = response.get('Item', {})
        except Exception as e:
            print(f"Error fetching role data: {e}")
            role_data = {}
        
        if not acs_url:
            # Fetch ACS URL from DynamoDB when not provided (backward compatibility)
            if not role_data:
                return create_error_html('Role not found for user', 404)
            acs_url = role_data.get('acs_url', DEFAULT_ACS_URL)
        
        audience = role_data.get('audience') or DEFAULT_AUDIENCE
        name_id_format = role_data.get('nameid_format') or DEFAULT_NAMEID_FORMAT
        
        # RelayState resolution: a request-provided value (SP-initiated passthrough)
        # always wins; otherwise use the role-record value for IdP-initiated logins.
        # The value is used verbatim - trailing spaces are significant because
        # providers like Grafana compare RelayState byte-for-byte.
        if not relay_state:
            relay_state = str(role_data.get('relay_state') or '')
        
        # Resolve the NameID value: use the user's email when the configured
        # format is an email address format
        user = get_user(username) or {}
        email = user.get('email') or role_data.get('attr_email') or ''
        if 'emailaddress' in name_id_format.lower() and email:
            name_id_value = email
        else:
            name_id_value = username
        
        custom_attributes = {k: v for k, v in role_data.items() if k.startswith(ATTR_PREFIX)}
        
        # Groups are used for portal grouping only and are never emitted via SAML;
        # strip any legacy attr_groups attribute as well
        custom_attributes.pop('attr_groups', None)
        
        # Merge profile attributes from the user record for application roles;
        # explicit role-level attributes take precedence. AWS roles keep their
        # legacy behaviour (default Role/RoleSessionName/SessionDuration).
        if user and not role_arn.startswith('arn:aws:'):
            if email and 'attr_email' not in custom_attributes:
                custom_attributes['attr_email'] = email
            full_name = ' '.join(
                part for part in (user.get('first_name', ''), user.get('last_name', '')) if part
            )
            if full_name and 'attr_display_name' not in custom_attributes and 'attr_name' not in custom_attributes:
                custom_attributes['attr_display_name'] = full_name
        
        # SP-initiated validation: the response must be sent to the ACS requested
        # by the service provider, using a role registered for that application
        effective_acs_url = sp_acs_url or acs_url
        if sp_acs_url:
            stored_acs_url = role_data.get('acs_url') or acs_url
            if stored_acs_url != sp_acs_url:
                return create_error_html('Selected role is not authorized for this application', 403)
        
        if in_response_to and not VALID_REQUEST_ID.fullmatch(in_response_to):
            return create_error_html('Invalid authentication request identifier', 400)
        
        if not effective_acs_url.lower().startswith('https://'):
            return create_error_html('Only HTTPS assertion consumer URLs are supported', 400)
        
        # Generate SAML response with the role's ACS URL and custom attributes
        saml_response = generate_saml_response(
            username,
            role_arn,
            effective_acs_url,
            custom_attributes=custom_attributes,
            audience=audience,
            name_id=name_id_value,
            name_id_format=name_id_format,
            in_response_to=in_response_to or None
        )
        saml_encoded = base64.b64encode(saml_response.encode('utf-8')).decode('utf-8')
        
        relay_state_input = ''
        if relay_state:
            relay_state_input = (
                f'<input type="hidden" name="RelayState" value="{html_utils.escape(relay_state, quote=True)}"/>'
            )
        
        # Create HTML auto-submit form
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>SAML SSO</title>
</head>
<body onload="document.forms[0].submit()">
    <form method="POST" action="{html_utils.escape(effective_acs_url, quote=True)}">
        <input type="hidden" name="SAMLResponse" value="{saml_encoded}"/>
        {relay_state_input}
        <noscript>
            <p>JavaScript is disabled. Click the button below to continue.</p>
            <input type="submit" value="Continue"/>
        </noscript>
    </form>
    <p>Redirecting to application...</p>
</body>
</html>'''
        
        return create_html_response(html_content)
        
    except Exception as e:
        print(f"SSO error: {e}")
        return create_error_html('Failed to generate SAML response', 500)


def handle_mfa_setup(event):
    """Handle MFA setup request and return QR code"""
    try:
        body = event.get('body', '')
        if event.get('isBase64Encoded'):
            body = base64.b64decode(body).decode('utf-8')
        
        params = parse_qs(body)
        username = params.get('username', [''])[0]
        
        if not username:
            return create_json_response({
                'success': False,
                'error': 'Username required'
            }, 400)
        
        # Verify user exists
        user = get_user(username)
        if not user:
            return create_json_response({
                'success': False,
                'error': 'User not found'
            }, 404)
        
        # Generate new MFA secret
        secret = generate_mfa_secret()
        
        # Generate QR code
        qr_code = generate_qr_code(username, secret)
        if not qr_code:
            return create_json_response({
                'success': False,
                'error': 'Failed to generate QR code'
            }, 500)
        
        # Return QR code and secret for display
        # The secret will be saved only after successful verification
        return create_json_response({
            'success': True,
            'qr_code': qr_code,
            'temp_secret': secret  # Temporary secret for verification
        })
        
    except Exception as e:
        print(f"MFA setup error: {e}")
        return create_json_response({
            'success': False,
            'error': 'Internal server error'
        }, 500)


def handle_mfa_verify(event):
    """Handle MFA token verification and save secret if valid"""
    try:
        body = event.get('body', '')
        if event.get('isBase64Encoded'):
            body = base64.b64decode(body).decode('utf-8')
        
        params = parse_qs(body)
        username = params.get('username', [''])[0]
        token = params.get('token', [''])[0]
        temp_secret = params.get('temp_secret', [''])[0]  # For new setup
        
        if not username or not token:
            return create_json_response({
                'success': False,
                'error': 'Username and token required'
            }, 400)
        
        # Get user to retrieve MFA secret
        user = get_user(username)
        if not user:
            return create_json_response({
                'success': False,
                'error': 'User not found'
            }, 404)
        
        mfa_secret = user.get('mfa_secret')
        
        # Determine which secret to use for verification
        secret_to_verify = None
        is_new_setup = False
        
        if temp_secret:
            # New setup - verify against temporary secret
            secret_to_verify = temp_secret
            is_new_setup = True
        elif mfa_secret:
            # Existing MFA - verify against stored secret
            secret_to_verify = mfa_secret
        else:
            return create_json_response({
                'success': False,
                'error': 'MFA not configured'
            }, 400)
        
        # Verify the token
        if not verify_mfa_token(secret_to_verify, token):
            return create_json_response({
                'success': False,
                'error': 'Invalid MFA token'
            }, 401)
        
        # If this is a new setup, save the secret now that it's verified
        if is_new_setup:
            if not save_mfa_secret(username, temp_secret):
                return create_json_response({
                    'success': False,
                    'error': 'Failed to save MFA configuration'
                }, 500)
        
        return create_json_response({
            'success': True,
            'message': 'MFA verification successful'
        })
        
    except Exception as e:
        print(f"MFA verify error: {e}")
        return create_json_response({
            'success': False,
            'error': 'Internal server error'
        }, 500)


def lambda_handler(event, context):
    """Main Lambda handler"""
    print(f"Event: {json.dumps(event)}")
    
    # Extract route information
    request_context = event.get('requestContext', {})
    http = request_context.get('http', {})
    method = http.get('method', '')
    path = http.get('path', '')
    
    # Strip stage from path if present (fixes issue with API Gateway stages)
    stage = request_context.get('stage', '$default')
    if stage != '$default' and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1:]
    
    # Route handling
    if method == 'GET' and path == '/metadata':
        return handle_metadata(event)
    elif method == 'POST' and path == '/login':
        return handle_login(event)
    elif path == '/sso' and method in ('GET', 'POST'):
        return handle_sso(event)
    elif method == 'POST' and path == '/mfa/setup':
        return handle_mfa_setup(event)
    elif method == 'POST' and path == '/mfa/verify':
        return handle_mfa_verify(event)
    else:
        return create_json_response({
            'error': 'Not found'
        }, 404)
