import json
import bcrypt
import logging
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt, verify_jwt_in_request
from app.models.applicant import Applicant
from app.models.admin import Admin, AdminRole

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_identity(identity):
    if isinstance(identity, str):
        try:
            identity = json.loads(identity)
        except json.JSONDecodeError:
            return None
    return identity


def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed):
    """Check if password matches the hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def get_current_user():
    try:
        # Get the user ID from token identity (now it's a string)
        user_id = get_jwt_identity()
        
        # Get additional claims
        claims = get_jwt()
        user_type = claims.get('type')
        
        # Convert string ID back to integer
        if user_id and user_id.isdigit():
            user_id = int(user_id)
        
        if user_type == 'applicant':
            from app.models.applicant import Applicant
            return Applicant.query.get(user_id)
        elif user_type == 'admin':
            from app.models.admin import Admin
            return Admin.query.get(user_id)
        else:
            return None
    except Exception as e:
        return None


def admin_required(roles=None):
    """Decorator to require admin authentication with optional role restriction"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_identity(get_jwt_identity())
            claims = get_jwt()

            logger.debug(f"[Admin Required] ID: {user_id}, Type: {claims.get('type')}")

            if claims.get('type') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403

            admin = Admin.query.get(int(user_id))
            if not admin or not admin.enabled:
                return jsonify({'error': 'Admin not found or disabled'}), 403

            if roles and admin.role not in roles:
                return jsonify({'error': f'Required roles: {[r.value for r in roles]}'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def applicant_required(f):
    """Decorator to require applicant authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_identity(get_jwt_identity())
        claims = get_jwt()      


        if claims.get('type') != 'applicant':
            return jsonify({'error': 'Applicant access required'}), 403

        applicant = Applicant.query.get(int(user_id))
        if not applicant or not applicant.enabled:
            return jsonify({'error': 'Applicant not found or disabled'}), 403

        return f(*args, **kwargs)
    return decorated_function
