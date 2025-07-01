from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db, socketio
from app.models.applicant import Applicant
from app.models.admin import Admin, AdminRole
from app.models.organization_application import OrganizationApplication, ApplicationStatus
from app.models.cluster_information import ClusterInformation
from app.models.supporting_document import SupportingDocument, DocumentType, DOCUMENT_TYPE_INFO
from app.models.notification import Notification, NotificationType
from app.utils.auth import get_current_user, applicant_required, admin_required
from app.ml.application_scorer import risk_scorer
from datetime import datetime, timedelta
import uuid

bp = Blueprint('application', __name__)

@bp.route('/', methods=['POST'])
@applicant_required
def create_application():
    try:
        applicant = get_current_user()
        data = request.get_json()
        
        
        # Validate required fields
        required_fields = ['organization_name', 'address', 'organization_email', 
                          'organization_phone', 'cluster_of_intervention', 
                          'source_of_fund', 'description']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create application
        application = OrganizationApplication(
            applicant_id=applicant.id,
            organization_name=data['organization_name'].strip(),
            acronym=data.get('acronym', '').strip() if data.get('acronym') else None,
            address=data['address'].strip(),
            organization_email=data['organization_email'].strip().lower(),
            organization_phone=data['organization_phone'].strip(),
            status=ApplicationStatus.PENDING
        )
        
        db.session.add(application)
        db.session.flush()  # Get the ID
        
        # Create cluster information
        cluster_info = ClusterInformation(
            application_id=application.id,
            cluster_of_intervention=data['cluster_of_intervention'].strip(),
            source_of_fund=data['source_of_fund'].strip(),
            description=data['description'].strip()
        )
        
        db.session.add(cluster_info)
        
        # Calculate ML risk score
        application_data = {
            'organization_name': application.organization_name,
            'acronym': application.acronym,
            'organization_phone': application.organization_phone,
            'organization_email': application.organization_email,
            'address': application.address,
            'num_documents': 0,  # Will be updated when documents are uploaded
            'applicant': applicant.to_dict()
        }
        
        ml_prediction = risk_scorer.predict_risk(application_data)
        application.risk_score = float(ml_prediction['risk_score'])
        application.ml_predictions = ml_prediction
    
        print("++++++++++++++++++++++++++++++++")
        print(ml_prediction['risk_score'])
        print(ml_prediction)
        print("++++++++++++++++++++++++++++++++")
        db.session.commit()
        
        # Create notification for FBO Officers
        fbo_officers = Admin.query.filter_by(role=AdminRole.FBO_OFFICER, enabled=True).all()
        for officer in fbo_officers:
            notification = Notification(
                admin_id=officer.id,
                application_id=application.id,
                type=NotificationType.STATUS_CHANGE,
                title='New Application Submitted',
                message=f'New application from {applicant.firstname} {applicant.lastname} for {application.organization_name}'
            )
            db.session.add(notification)
        
        db.session.commit()
        
        # Send real-time notification
        socketio.emit('new_application', {
            'application_id': application.id,
            'applicant_name': f'{applicant.firstname} {applicant.lastname}',
            'organization_name': application.organization_name
        }, room='fbo_officers')
        
        return jsonify({
            'message': 'Application created successfully',
            'application': application.to_dict(),
            'ml_prediction': ml_prediction
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create application: {str(e)}'}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
def get_applications():
    try:
        user = get_current_user()        
        claims = get_jwt()      

        if claims.get('type') == 'applicant':
            # Applicant can only see their own applications
            applications = OrganizationApplication.query.filter_by(applicant_id=user.id).all()
        
        elif claims.get('type') == 'admin':
            # Admin sees applications based on their role and status
            if user.role == AdminRole.FBO_OFFICER:
                applications = OrganizationApplication.query.filter(
                    OrganizationApplication.status.in_([
                        ApplicationStatus.PENDING, 
                        ApplicationStatus.UNDER_REVIEW,
                        ApplicationStatus.MISSING_DOCUMENTS
                    ])
                ).all()
            
            elif user.role == AdminRole.DIVISION_MANAGER:
                applications = OrganizationApplication.query.filter_by(
                    status=ApplicationStatus.DRAFT
                ).all()
            
            elif user.role == AdminRole.HOD:
                applications = OrganizationApplication.query.filter_by(
                    status=ApplicationStatus.DM_REVIEW
                ).all()
            
            elif user.role == AdminRole.SECRETARY_GENERAL:
                applications = OrganizationApplication.query.filter_by(
                    status=ApplicationStatus.HOD_REVIEW
                ).all()
            
            elif user.role == AdminRole.CEO:
                applications = OrganizationApplication.query.filter_by(
                    status=ApplicationStatus.SG_REVIEW
                ).all()
            
            else:
                applications = []
        
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
        return jsonify({
            'applications': [app.to_dict() for app in applications]
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get applications: {str(e)}'}), 500

@bp.route('/<int:application_id>', methods=['GET'])
@jwt_required()
def get_application(application_id):
    try:
        user = get_current_user()
        claims = get_jwt() 
        
        application = OrganizationApplication.query.get_or_404(application_id)
        
        # Check permissions
        # if claims.get('type') == 'applicant' and application.applicant_id != user.id:
        #     return jsonify({'error': 'Access denied'}), 403
        
        # Include related data
        app_data = application.to_dict()
        app_data['cluster_information'] = application.cluster_information.to_dict() if application.cluster_information else None
        app_data['supporting_documents'] = [doc.to_dict() for doc in application.supporting_documents]
        
        return jsonify({'application': app_data})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get application: {str(e)}'}), 500

@bp.route('/status', methods=['PUT'])
@admin_required()
def update_application_status():
    try:
        data = request.get_json()
        application_id = data.get('application_id')
        new_status = data.get('status')
        comments = data.get('comments', '')
        
        if not application_id or not new_status:
            return jsonify({'error': 'Application ID and status required'}), 400
        
        application = OrganizationApplication.query.get_or_404(application_id)
        admin = get_current_user()
        
        # Validate status transition based on admin role
        valid_transitions = {
            AdminRole.FBO_OFFICER: {
                ApplicationStatus.PENDING: [ApplicationStatus.UNDER_REVIEW, ApplicationStatus.MISSING_DOCUMENTS, ApplicationStatus.DRAFT],
                ApplicationStatus.UNDER_REVIEW: [ApplicationStatus.MISSING_DOCUMENTS, ApplicationStatus.DRAFT],
                ApplicationStatus.MISSING_DOCUMENTS: [ApplicationStatus.UNDER_REVIEW, ApplicationStatus.DRAFT]
            },
            AdminRole.DIVISION_MANAGER: {
                ApplicationStatus.DRAFT: [ApplicationStatus.DM_REVIEW, ApplicationStatus.MISSING_DOCUMENTS]
            },
            AdminRole.HOD: {
                ApplicationStatus.DM_REVIEW: [ApplicationStatus.HOD_REVIEW, ApplicationStatus.MISSING_DOCUMENTS]
            },
            AdminRole.SECRETARY_GENERAL: {
                ApplicationStatus.HOD_REVIEW: [ApplicationStatus.SG_REVIEW, ApplicationStatus.REJECTED]
            },
            AdminRole.CEO: {
                ApplicationStatus.SG_REVIEW: [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]
            }
        }
        
        try:
            new_status_enum = ApplicationStatus(new_status)
        except ValueError:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Check if transition is valid
        if admin.role not in valid_transitions:
            return jsonify({'error': 'No permission to update status'}), 403
        
        if application.status not in valid_transitions[admin.role]:
            return jsonify({'error': f'Cannot update application in {application.status.value} status'}), 400
        
        if new_status_enum not in valid_transitions[admin.role][application.status]:
            return jsonify({'error': f'Invalid status transition from {application.status.value} to {new_status}'}), 400
        
        # Update application
        old_status = application.status
        application.status = new_status_enum
        application.processed_by_id = admin.id
        application.last_modified = datetime.utcnow()
        if comments:
            application.comments = comments
        
        # If approved, generate certificate number
        if new_status_enum == ApplicationStatus.APPROVED:
            application.certificate_number = f"RGB-{datetime.now().year}-{application.id:06d}"
            application.certificate_issued_at = datetime.utcnow()
        
        db.session.commit()
        
        # Create notification for applicant
        notification = Notification(
            applicant_id=application.applicant_id,
            application_id=application.id,
            type=NotificationType.STATUS_CHANGE,
            title=f'Application Status Updated',
            message=f'Your application for {application.organization_name} has been updated to {new_status_enum.value}'
        )
        db.session.add(notification)
        
        # Create notification for next role if status moved forward
        next_role_map = {
            ApplicationStatus.DRAFT: AdminRole.DIVISION_MANAGER,
            ApplicationStatus.DM_REVIEW: AdminRole.HOD,
            ApplicationStatus.HOD_REVIEW: AdminRole.SECRETARY_GENERAL,
            ApplicationStatus.SG_REVIEW: AdminRole.CEO
        }
        
        if new_status_enum in next_role_map:
            next_admins = Admin.query.filter_by(role=next_role_map[new_status_enum], enabled=True).all()
            for next_admin in next_admins:
                notification = Notification(
                    admin_id=next_admin.id,
                    application_id=application.id,
                    type=NotificationType.STATUS_CHANGE,
                    title='Application Ready for Review',
                    message=f'Application for {application.organization_name} is ready for your review'
                )
                db.session.add(notification)
        
        db.session.commit()
        
        # Send real-time notifications
        socketio.emit('status_update', {
            'application_id': application.id,
            'old_status': old_status.value,
            'new_status': new_status_enum.value,
            'comments': comments
        }, room=f'applicant_{application.applicant_id}')
        
        return jsonify({
            'message': 'Application status updated successfully',
            'application': application.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update application status: {str(e)}'}), 500

@bp.route('/<int:application_id>/documents/requirements', methods=['GET'])
@jwt_required()
def get_document_requirements(application_id):
    try:
        application = OrganizationApplication.query.get_or_404(application_id)
        
        # Get current user and check permissions
        user = get_current_user()
        claims = get_jwt() 
        
        # if claims.get('type') == 'applicant' and application.applicant_id != user.id:
        #     return jsonify({'error': 'Access denied'}), 403
        
        # Get all document types and their requirements
        requirements = []
        for doc_type, info in DOCUMENT_TYPE_INFO.items():
            # Check if document is already uploaded
            existing_doc = SupportingDocument.query.filter_by(
                application_id=application_id,
                document_type=doc_type
            ).first()
            
            requirements.append({
                'document_type': doc_type.value,
                'name': info['name'],
                'required': info['required'],
                'uploaded': existing_doc is not None,
                'document_id': existing_doc.id if existing_doc else None,
                'is_valid': existing_doc.is_valid if existing_doc else None,
                'validation_comments': existing_doc.validation_comments if existing_doc else None
            })
        
        return jsonify({'requirements': requirements})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get document requirements: {str(e)}'}), 500

@bp.route('/stats', methods=['GET'])
@admin_required()
def get_application_stats():
    try:
        admin = get_current_user()
        
        # Get statistics based on admin role
        stats = {}
        
        if admin.role == AdminRole.CEO:
            # CEO can see all stats
            stats['total_applications'] = OrganizationApplication.query.count()
            stats['pending_review'] = OrganizationApplication.query.filter_by(status=ApplicationStatus.SG_REVIEW).count()
            stats['approved'] = OrganizationApplication.query.filter_by(status=ApplicationStatus.APPROVED).count()
            stats['rejected'] = OrganizationApplication.query.filter_by(status=ApplicationStatus.REJECTED).count()
            
            # Applications by status
            status_counts = {}
            for status in ApplicationStatus:
                count = OrganizationApplication.query.filter_by(status=status).count()
                status_counts[status.value] = count
            stats['by_status'] = status_counts
            
            # Applications by month (last 12 months)
            from sqlalchemy import func, extract
            monthly_stats = db.session.query(
                extract('month', OrganizationApplication.submitted_at).label('month'),
                extract('year', OrganizationApplication.submitted_at).label('year'),
                func.count(OrganizationApplication.id).label('count')
            ).filter(
                OrganizationApplication.submitted_at >= datetime.now() - timedelta(days=365)
            ).group_by('year', 'month').all()
            
            stats['monthly'] = [
                {
                    'month': int(row.month),
                    'year': int(row.year),
                    'count': row.count
                } for row in monthly_stats
            ]
            
        else:
            # Other roles see limited stats
            role_status_map = {
                AdminRole.FBO_OFFICER: [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW, ApplicationStatus.MISSING_DOCUMENTS],
                AdminRole.DIVISION_MANAGER: [ApplicationStatus.DRAFT],
                AdminRole.HOD: [ApplicationStatus.DM_REVIEW],
                AdminRole.SECRETARY_GENERAL: [ApplicationStatus.HOD_REVIEW]
            }
            
            if admin.role in role_status_map:
                stats['pending_review'] = OrganizationApplication.query.filter(
                    OrganizationApplication.status.in_(role_status_map[admin.role])
                ).count()
        
        return jsonify({'stats': stats})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get application stats: {str(e)}'}), 500