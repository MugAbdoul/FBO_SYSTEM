import re
from datetime import datetime
from flask import current_app

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    pattern = r'^\+?[1-9]\d{1,14}$'
    return re.match(pattern, phone) is not None

def validate_nid_passport(nid_passport):
    """Validate NID or Passport format"""
    # Rwanda NID format: 16 digits
    # Passport: alphanumeric, 6-10 characters
    if nid_passport.isdigit() and len(nid_passport) == 16:
        return True
    if re.match(r'^[A-Z0-9]{6,10}$', nid_passport.upper()):
        return True
    return False

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def validate_file_upload(file):
    """Validate uploaded file"""
    if not file:
        return False, "No file provided"
    
    if file.filename == '':
        return False, "No file selected"
    
    # Check file extension
    allowed_extensions = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}
    if not ('.' in file.filename and 
            file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
    
    # Check file size (max 16MB)
    max_size = current_app.config['MAX_CONTENT_LENGTH']
    if hasattr(file, 'content_length') and file.content_length > max_size:
        return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"
    
    return True, "File is valid"

def validate_date(date_string):
    """Validate date format (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False