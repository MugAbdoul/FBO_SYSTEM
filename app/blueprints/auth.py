import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models.applicant import Applicant, CivilStatus, Gender
from app.models.admin import Admin, AdminRole
from app.utils.auth import hash_password, check_password, get_current_user
from app.utils.validators import validate_email, validate_phone, validate_nid_passport, validate_password, validate_date
from datetime import datetime

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'firstname', 'lastname', 'nid_or_passport', 
                          'phonenumber', 'nationality', 'date_of_birth', 'gender', 
                          'civil_status', 'title']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate email
        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if email already exists
        if Applicant.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Validate password
        is_valid, message = validate_password(data['password'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Validate phone
        if not validate_phone(data['phonenumber']):
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Validate NID/Passport
        if not validate_nid_passport(data['nid_or_passport']):
            return jsonify({'error': 'Invalid NID or Passport format'}), 400
        
        # Check if NID/Passport already exists
        if Applicant.query.filter_by(nid_or_passport=data['nid_or_passport']).first():
            return jsonify({'error': 'NID or Passport already registered'}), 400
        
        # Validate date of birth
        if not validate_date(data['date_of_birth']):
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate enums
        try:
            gender = Gender(data['gender'].upper())
            civil_status = CivilStatus(data['civil_status'].upper())
        except ValueError:
            return jsonify({'error': 'Invalid gender or civil status'}), 400
        
        # Create new applicant
        applicant = Applicant(
            email=data['email'].lower(),
            password=hash_password(data['password']),
            firstname=data['firstname'].strip(),
            lastname=data['lastname'].strip(),
            nid_or_passport=data['nid_or_passport'].strip(),
            phonenumber=data['phonenumber'].strip(),
            nationality=data['nationality'].strip(),
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
            gender=gender,
            civil_status=civil_status,
            title=data['title'].strip()
        )
        
        db.session.add(applicant)
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(
            identity={'id': applicant.id, 'type': 'applicant'}
        )
        
        return jsonify({
            'message': 'Registration successful',
            'access_token': access_token,
            'user': applicant.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password required'}), 400

        # Check if it's an applicant
        applicant = Applicant.query.filter_by(email=data['email'].lower()).first()
        if applicant and applicant.enabled and check_password(data['password'], applicant.password):
            identity = json.dumps({'id': str(applicant.id), 'type': 'applicant'})
            access_token = create_access_token(identity=identity, additional_claims={"type": "applicant"})
            return jsonify({
                'access_token': access_token,
                'user': applicant.to_dict(),
                'user_type': 'applicant'
            })

        # Check if it's an admin
        admin = Admin.query.filter_by(email=data['email'].lower()).first()
        if admin and admin.enabled and check_password(data['password'], admin.password):
            identity = json.dumps({'id': str(admin.id), 'type': 'admin'})
            access_token = create_access_token(identity=identity, additional_claims={"type": "admin"})
            return jsonify({
                'access_token': access_token,
                'user': admin.to_dict(),
                'user_type': 'admin'
            })

        return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get profile: {str(e)}'}), 500

@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update allowed fields
        if isinstance(user, Applicant):
            allowed_fields = ['firstname', 'lastname', 'phonenumber', 'nationality', 'title']
            for field in allowed_fields:
                if field in data and data[field]:
                    setattr(user, field, data[field].strip())
        
        elif isinstance(user, Admin):
            allowed_fields = ['firstname', 'lastname', 'phonenumber']
            for field in allowed_fields:
                if field in data and data[field]:
                    setattr(user, field, data[field].strip())
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update profile: {str(e)}'}), 500

@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'Current password and new password required'}), 400
        
        # Verify current password
        if not check_password(data['current_password'], user.password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Update password
        user.password = hash_password(data['new_password'])
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to change password: {str(e)}'}), 500