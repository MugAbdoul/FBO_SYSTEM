from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt
from app import db, socketio
from app import db
from app.models.organization_application import ApplicationStatus, OrganizationApplication
from app.models.supporting_document import SupportingDocument, DocumentType, DOCUMENT_TYPE_INFO
from app.models.notification import Notification, NotificationType
from app.utils.auth import get_current_user, applicant_required, admin_required
from app.utils.validators import validate_file_upload
from datetime import datetime
import uuid
from io import BytesIO

bp = Blueprint('documents', __name__)

@bp.route('/upload', methods=['POST'])
@applicant_required
def upload_document():
    try:
        applicant = get_current_user()
        
        # Get form data
        application_id = request.form.get('application_id')
        document_type = request.form.get('document_type')
        
        if not application_id or not document_type:
            return jsonify({'error': 'Application ID and document type required'}), 400
        
        # Validate application ownership
        application = OrganizationApplication.query.get_or_404(application_id)
        if application.applicant_id != applicant.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Validate document type
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            return jsonify({'error': 'Invalid document type'}), 400
        
            
        application.status = ApplicationStatus.PENDING
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, message = validate_file_upload(file)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Check if document already exists
        existing_doc = SupportingDocument.query.filter_by(
            application_id=application_id,
            document_type=doc_type_enum
        ).first()
        
        # Read file data
        file_data = file.read()
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        socketio.emit('new_application', {
            'application_id': application.id,
            'applicant_name': f'{applicant.firstname} {applicant.lastname}',
            'organization_name': application.organization_name
        }, room='fbo_officers')
        
        if existing_doc:
            # Update existing document
            existing_doc.filename = filename
            existing_doc.original_filename = file.filename
            existing_doc.document_data = file_data
            existing_doc.content_type = file.content_type
            existing_doc.file_size = len(file_data)
            existing_doc.uploaded_at = datetime.utcnow()
            existing_doc.is_valid = True  # Reset validation status
            existing_doc.validation_comments = None
            document = existing_doc
        else:
            # Create new document
            document = SupportingDocument(
                application_id=application_id,
                document_type=doc_type_enum,
                filename=filename,
                original_filename=file.filename,
                document_data=file_data,
                content_type=file.content_type,
                file_size=len(file_data),
                required=DOCUMENT_TYPE_INFO[doc_type_enum]['required']
            )
            db.session.add(document)
        
        # Update application's document count for ML scoring
        doc_count = SupportingDocument.query.filter_by(application_id=application_id).count()
        if not existing_doc:
            doc_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Document uploaded successfully',
            'document': document.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to upload document: {str(e)}'}), 500

@bp.route('/<int:document_id>', methods=['GET'])
@jwt_required()
def download_document(document_id):
    try:
        user = get_current_user()
        document = SupportingDocument.query.get_or_404(document_id)
        claims = get_jwt()
        
        if claims.get('type') == 'applicant':
            if document.application.applicant_id != user.id:
                return jsonify({'error': 'Access denied'}), 403
        
        # Return file
        return send_file(
            BytesIO(document.document_data),
            as_attachment=True,
            download_name=document.original_filename,
            mimetype=document.content_type
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to download document: {str(e)}'}), 500

@bp.route('/<int:document_id>/validate', methods=['POST'])
@admin_required()
def validate_document(document_id):
    try:
        admin = get_current_user()
        data = request.get_json()
        
        document = SupportingDocument.query.get_or_404(document_id)
        
        is_valid = data.get('is_valid', True)
        comments = data.get('comments', '')
        
        document.is_valid = is_valid
        document.validation_comments = comments
        document.validated_by_id = admin.id
        document.validated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Create notification for applicant if document is invalid
        if not is_valid:
            notification = Notification(
                applicant_id=document.application.applicant_id,
                application_id=document.application_id,
                type=NotificationType.DOCUMENT_REQUEST,
                title='Document Validation Failed',
                message=f'Your {DOCUMENT_TYPE_INFO[document.document_type]["name"]} document needs revision: {comments}'
            )
            db.session.add(notification)
            db.session.commit()
        
        return jsonify({
            'message': 'Document validation updated',
            'document': document.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to validate document: {str(e)}'}), 500

@bp.route('/templates/<document_type>', methods=['GET'])
def get_document_template(document_type):
    """Get PDF template for document type"""
    try:
        # Validate document type
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # For now, return template info
        template_info = {
            'document_type': document_type,
            'name': DOCUMENT_TYPE_INFO[doc_type_enum]['name'],
            'required': DOCUMENT_TYPE_INFO[doc_type_enum]['required'],
            'template_url': f'/static/templates/{document_type.lower()}_template.pdf',
            'guidelines': [
                'Ensure all information is clearly legible',
                'Use official letterhead if applicable',
                'Include all required signatures and stamps',
                'Submit in PDF format for best quality'
            ]
        }
        
        return jsonify({'template': template_info})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get template: {str(e)}'}), 500