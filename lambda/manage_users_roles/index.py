"""
Lambda Function for Managing Users and Roles in DynamoDB
Handles creation and update of users and role mappings.
"""
import json
import os
import bcrypt
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
USERS_TABLE = os.environ.get('USERS_TABLE', 'simple-saml-idp-users-dev')
ROLES_TABLE = os.environ.get('ROLES_TABLE', 'simple-saml-idp-roles-dev')

# Default ACS URL for backward compatibility
DEFAULT_ACS_URL = 'https://signin.aws.amazon.com/saml'

# Bcrypt rounds with validation (safe range: 10-15)
try:
    BCRYPT_ROUNDS = int(os.environ.get('BCRYPT_ROUNDS', '12'))
    if BCRYPT_ROUNDS < 10 or BCRYPT_ROUNDS > 15:
        print(f"Warning: BCRYPT_ROUNDS={BCRYPT_ROUNDS} is outside safe range (10-15). Using default of 12.")
        BCRYPT_ROUNDS = 12
except ValueError:
    print("Warning: Invalid BCRYPT_ROUNDS value. Using default of 12.")
    BCRYPT_ROUNDS = 12


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for user and role management operations.
    
    Event structure:
    {
        "operation": "create_user" | "update_user" | "create_role" | "update_role",
        "data": {
            // User fields for user operations
            // Role fields for role operations
        }
    }
    """
    # Log only non-sensitive metadata from the event
    operation = event.get('operation')
    username = None
    data_field = event.get('data')
    if isinstance(data_field, dict):
        username = data_field.get('username')
    log_payload = {
        "operation": operation,
        "username": username,
    }
    print(f"Received event metadata: {json.dumps(log_payload)}")
    
    try:
        operation = event.get('operation')
        data = event.get('data', {})
        
        if not operation:
            return error_response("Missing 'operation' field", 400)
        
        if not data:
            return error_response("Missing 'data' field", 400)
        
        # Route to appropriate handler
        if operation == 'create_user':
            return create_user(data)
        elif operation == 'update_user':
            return update_user(data)
        elif operation == 'create_role':
            return create_role(data)
        elif operation == 'update_role':
            return update_role(data)
        else:
            return error_response(f"Invalid operation: {operation}", 400)
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


def create_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new user in DynamoDB.
    
    Required fields:
    - username: string
    - password: string (will be hashed)
    
    Optional fields:
    - email: string (defaults to username@example.com)
    - first_name: string (derived from username if not provided)
    - last_name: string (derived from username if not provided)
    - enabled: boolean (defaults to true)
    """
    try:
        # Validate required fields
        username = data.get('username')
        password = data.get('password')
        
        if not username:
            return error_response("Missing required field: username", 400)
        if not password:
            return error_response("Missing required field: password", 400)
        
        # Generate password hash using bcrypt
        # bcrypt automatically handles salting and uses a secure algorithm
        # Using configurable work factor (default: 12) for balance between security and performance
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode('utf-8')
        
        # Derive names from username if not provided
        email = data.get('email', f"{username}@example.com")
        
        if '.' in username:
            # Split username into first and last name (handle multiple dots by taking first and rest)
            parts = username.split('.', 1)
            first_name_default = parts[0].capitalize()
            last_name_default = parts[1].replace('.', ' ').title() if len(parts) > 1 else "User"
        else:
            first_name_default = username.capitalize()
            last_name_default = "User"
        
        first_name = data.get('first_name', first_name_default)
        last_name = data.get('last_name', last_name_default)
        enabled = data.get('enabled', True)
        
        # Get DynamoDB table
        table = dynamodb.Table(USERS_TABLE)
        
        # Check if user already exists
        try:
            response = table.get_item(Key={'username': username})
            if 'Item' in response:
                return error_response(f"User '{username}' already exists", 409)
        except ClientError as e:
            print(f"Error checking existing user: {e}")
        
        # Create user item
        item = {
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'first_name': first_name,
            'last_name': last_name,
            'enabled': enabled,
            'created_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        # Put item in DynamoDB
        table.put_item(Item=item)
        
        # Remove password_hash from response for security
        response_item = item.copy()
        response_item.pop('password_hash')
        
        print("Successfully created user")
        return success_response(f"User '{username}' created successfully", response_item)
        
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        print(f"Error creating user: {e}")
        return error_response(f"Error creating user: {str(e)}", 500)


def update_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing user in DynamoDB.
    
    Required fields:
    - username: string
    
    Optional fields (at least one should be provided):
    - password: string (will be hashed)
    - email: string
    - first_name: string
    - last_name: string
    - enabled: boolean
    """
    try:
        # Validate required fields
        username = data.get('username')
        
        if not username:
            return error_response("Missing required field: username", 400)
        
        # Get DynamoDB table
        table = dynamodb.Table(USERS_TABLE)
        
        # Check if user exists
        try:
            response = table.get_item(Key={'username': username})
            if 'Item' not in response:
                return error_response(f"User '{username}' not found", 404)
        except ClientError as e:
            print(f"Error checking user: {e}")
            return error_response(f"Database error: {str(e)}", 500)
        
        # Build update expression
        update_expressions = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Handle password update
        if 'password' in data:
            password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode('utf-8')
            update_expressions.append("#ph = :ph")
            expression_attribute_names['#ph'] = 'password_hash'
            expression_attribute_values[':ph'] = password_hash
        
        # Handle other field updates
        field_mappings = {
            'email': 'email',
            'first_name': 'first_name',
            'last_name': 'last_name',
            'enabled': 'enabled'
        }
        
        for field, attr_name in field_mappings.items():
            if field in data:
                placeholder = f"#{field}"
                value_placeholder = f":{field}"
                update_expressions.append(f"{placeholder} = {value_placeholder}")
                expression_attribute_names[placeholder] = attr_name
                expression_attribute_values[value_placeholder] = data[field]
        
        if not update_expressions:
            return error_response("No fields to update", 400)
        
        # Add updated_at timestamp
        update_expressions.append("#ua = :ua")
        expression_attribute_names['#ua'] = 'updated_at'
        expression_attribute_values[':ua'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        update_expression = "SET " + ", ".join(update_expressions)
        
        # Update item in DynamoDB
        response = table.update_item(
            Key={'username': username},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'
        )
        
        # Remove password_hash from response for security
        updated_item = response['Attributes']
        if 'password_hash' in updated_item:
            updated_item.pop('password_hash')
        
        print("Successfully updated user")
        return success_response(f"User '{username}' updated successfully", updated_item)
        
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        print(f"Error updating user: {e}")
        return error_response(f"Error updating user: {str(e)}", 500)


def create_role(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new role mapping in DynamoDB.
    
    Required fields:
    - username: string
    
    Optional fields:
    - role_arn: string (e.g., arn:aws:iam::123456789012:role/AdminRole, required for AWS Console)
    - account_name: string (defaults to extracted account ID or empty)
    - acs_url: string (defaults to "https://signin.aws.amazon.com/saml")
    - description: string (defaults to "Role access for {username}")
    - attr_*: any custom SAML attributes with 'attr_' prefix
    """
    try:
        # Validate required fields
        username = data.get('username')
        role_arn = data.get('role_arn', '')
        
        if not username:
            return error_response("Missing required field: username", 400)
        
        if not role_arn:
            return error_response("Missing required field: role_arn. For non-AWS applications, use a descriptive identifier (e.g., 'grafana:viewer')", 400)
        
        # Validate role ARN format only if it's an AWS ARN
        account_id = ''
        if role_arn.startswith('arn:aws:iam::'):
            # Extract account ID from AWS ARN
            try:
                account_id = role_arn.split(':')[4]
            except IndexError:
                return error_response("Invalid AWS role_arn format. Cannot extract account ID", 400)
        
        # Set defaults
        account_name = data.get('account_name', account_id if account_id else 'Custom Application')
        acs_url = data.get('acs_url', DEFAULT_ACS_URL)
        description = data.get('description', f"Role access for {username}")
        
        # Get DynamoDB table
        table = dynamodb.Table(ROLES_TABLE)
        
        # Check if role mapping already exists
        try:
            response = table.get_item(Key={'username': username, 'role_arn': role_arn})
            if 'Item' in response:
                return error_response(f"Role mapping for user '{username}' and role '{role_arn}' already exists", 409)
        except ClientError as e:
            print(f"Error checking existing role: {e}")
        
        # Create role item with standard fields
        item = {
            'username': username,
            'role_arn': role_arn,
            'account_name': account_name,
            'account_id': account_id,
            'acs_url': acs_url,
            'description': description,
            'created_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        # Add any custom attributes with 'attr_' prefix from the input data
        for key, value in data.items():
            if key.startswith('attr_'):
                item[key] = value
        
        # Put item in DynamoDB
        table.put_item(Item=item)
        
        print("Successfully created role mapping")
        return success_response(f"Role mapping created successfully", item)
        
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        print(f"Error creating role: {e}")
        return error_response(f"Error creating role: {str(e)}", 500)


def update_role(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing role mapping in DynamoDB.
    
    Required fields:
    - username: string
    - role_arn: string
    
    Optional fields (at least one should be provided):
    - account_name: string
    - acs_url: string
    - description: string
    """
    try:
        # Validate required fields
        username = data.get('username')
        role_arn = data.get('role_arn')
        
        if not username:
            return error_response("Missing required field: username", 400)
        if not role_arn:
            return error_response("Missing required field: role_arn", 400)
        
        # Get DynamoDB table
        table = dynamodb.Table(ROLES_TABLE)
        
        # Check if role mapping exists
        try:
            response = table.get_item(Key={'username': username, 'role_arn': role_arn})
            if 'Item' not in response:
                return error_response(f"Role mapping for user '{username}' and role '{role_arn}' not found", 404)
        except ClientError as e:
            print(f"Error checking role: {e}")
            return error_response(f"Database error: {str(e)}", 500)
        
        # Build update expression
        update_expressions = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Handle standard field updates
        field_mappings = {
            'account_name': 'account_name',
            'acs_url': 'acs_url',
            'description': 'description'
        }
        
        for field, attr_name in field_mappings.items():
            if field in data:
                placeholder = f"#{field}"
                value_placeholder = f":{field}"
                update_expressions.append(f"{placeholder} = {value_placeholder}")
                expression_attribute_names[placeholder] = attr_name
                expression_attribute_values[value_placeholder] = data[field]
        
        # Handle custom attributes with 'attr_' prefix
        attr_counter = 0
        for key, value in data.items():
            if key.startswith('attr_'):
                placeholder = f"#attr{attr_counter}"
                value_placeholder = f":attr{attr_counter}"
                update_expressions.append(f"{placeholder} = {value_placeholder}")
                expression_attribute_names[placeholder] = key
                expression_attribute_values[value_placeholder] = value
                attr_counter += 1
        
        if not update_expressions:
            return error_response("No fields to update", 400)
        
        # Add updated_at timestamp
        update_expressions.append("#ua = :ua")
        expression_attribute_names['#ua'] = 'updated_at'
        expression_attribute_values[':ua'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        update_expression = "SET " + ", ".join(update_expressions)
        
        # Update item in DynamoDB
        response = table.update_item(
            Key={'username': username, 'role_arn': role_arn},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'
        )
        
        updated_item = response['Attributes']
        
        print("Successfully updated role mapping")
        return success_response(f"Role mapping updated successfully", updated_item)
        
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        print(f"Error updating role: {e}")
        return error_response(f"Error updating role: {str(e)}", 500)


def success_response(message: str, data: Any = None) -> Dict[str, Any]:
    """Generate a success response"""
    response = {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'message': message,
            'data': data
        })
    }
    return response


def error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """Generate an error response"""
    response = {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }
    return response
