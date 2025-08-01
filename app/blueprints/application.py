from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db, socketio
from app.models.applicant import Applicant
from app.models.admin import Admin, AdminRole
from app.models.organization_application import OrganizationApplication, ApplicationStatus
from app.models.applicationComment import ApplicationComment
from app.models.provinceAndDistrict import Province, District
from app.models.cluster_information import ClusterInformation
from app.models.supporting_document import SupportingDocument, DocumentType, DOCUMENT_TYPE_INFO
from app.models.notification import Notification, NotificationType
from app.utils.auth import get_current_user, applicant_required, admin_required
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
        required_fields = ['organization_name', 'district_id', 'organization_email', 
                          'organization_phone', 'cluster_of_intervention', 
                          'source_of_fund', 'description']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate district exists
        district = District.query.get(data['district_id'])
        if not district:
            return jsonify({'error': 'Invalid district ID'}), 400
        
        # Create application
        application = OrganizationApplication(
            applicant_id=applicant.id,
            organization_name=data['organization_name'].strip(),
            acronym=data.get('acronym', '').strip() if data.get('acronym') else None,
            district_id=data['district_id'],
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
            'application': application.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create application: {str(e)}'}), 500

@bp.route('/<int:application_id>', methods=['PUT'])
@applicant_required
def update_application(application_id):
    try:
        applicant = get_current_user()
        data = request.get_json()
        
        # Find the application
        application = OrganizationApplication.query.get_or_404(application_id)
        
        # Verify ownership
        if application.applicant_id != applicant.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Verify application is in editable state
        if application.status not in [ApplicationStatus.PENDING, ApplicationStatus.REVIEWING_AGAIN]:
            return jsonify({'error': 'Application cannot be edited in its current state'}), 400
        
        # Validate required fields if they are provided
        required_fields = {
            'organization_name': 'Organization name is required',
            'organization_email': 'Organization email is required',
            'organization_phone': 'Organization phone is required',
        }
        
        for field, error_msg in required_fields.items():
            if field in data and not data[field]:
                return jsonify({'error': error_msg}), 400
        
        # Update application fields if provided
        if 'organization_name' in data:
            application.organization_name = data['organization_name'].strip()
        
        if 'acronym' in data:
            application.acronym = data['acronym'].strip() if data['acronym'] else None
            
        if 'organization_email' in data:
            application.organization_email = data['organization_email'].strip().lower()
            
        if 'organization_phone' in data:
            application.organization_phone = data['organization_phone'].strip()
        
        # Update cluster information if provided
        cluster_info = application.cluster_information
        if cluster_info:
            if 'cluster_of_intervention' in data:
                cluster_info.cluster_of_intervention = data['cluster_of_intervention'].strip()
                
            if 'source_of_fund' in data:
                cluster_info.source_of_fund = data['source_of_fund'].strip()
                
            if 'description' in data:
                cluster_info.description = data['description'].strip()
        
        # Update last modified timestamp
        application.last_modified = datetime.utcnow()
        
        # Add a comment to log the update
        comment = ApplicationComment(
            content=f"Application updated by applicant in response to review feedback.",
            performed_by_id=applicant.id,
            application_id=application.id
        )
        db.session.add(comment)
        
        # Create notification for FBO officers (if status is REVIEWING_AGAIN)
        if application.status == ApplicationStatus.REVIEWING_AGAIN:
            fbo_officers = Admin.query.filter_by(role=AdminRole.FBO_OFFICER, enabled=True).all()
            for officer in fbo_officers:
                notification = Notification(
                    admin_id=officer.id,
                    application_id=application.id,
                    type=NotificationType.STATUS_CHANGE,
                    title='Application Updated',
                    message=f'Application for {application.organization_name} has been updated by the applicant'
                )
                db.session.add(notification)
        
        application.status = ApplicationStatus.PENDING
        
        db.session.commit()
        
        # Send real-time notification to FBO officers if status is REVIEWING_AGAIN
        if application.status == ApplicationStatus.REVIEWING_AGAIN or application.status == ApplicationStatus.PENDING:
            socketio.emit('application_updated', {
                'application_id': application.id,
                'organization_name': application.organization_name,
                'applicant_name': f'{applicant.firstname} {applicant.lastname}'
            }, room='fbo_officers')
        
        # Return updated application
        app_data = application.to_dict()
        app_data['canEdit'] = application.status in [ApplicationStatus.PENDING, ApplicationStatus.REVIEWING_AGAIN]
        app_data['cluster_information'] = application.cluster_information.to_dict() if application.cluster_information else None
        
        return jsonify({
            'message': 'Application updated successfully',
            'application': app_data
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update application: {str(e)}'}), 500
    
@bp.route('/<int:application_id>/comments', methods=['POST'])
@admin_required()
def add_comment(application_id):
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Comment content is required'}), 400
        
        application = OrganizationApplication.query.get_or_404(application_id)
        admin = get_current_user()
        
        comment = ApplicationComment(
            content=content,
            performed_by_id=admin.id,
            application_id=application_id
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'message': 'Comment added successfully',
            'comment': comment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add comment: {str(e)}'}), 500

@bp.route('/<int:application_id>/comments', methods=['GET'])
@jwt_required()
def get_comments(application_id):
    try:
        user = get_current_user()
        claims = get_jwt()
        
        application = OrganizationApplication.query.get_or_404(application_id)
        
        # Check permissions
        if claims.get('type') == 'applicant' and application.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        comments = ApplicationComment.query.filter_by(
            application_id=application_id
        ).order_by(ApplicationComment.created_at.desc()).all()
        
        return jsonify({
            'comments': [comment.to_dict() for comment in comments]
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get comments: {str(e)}'}), 500

@bp.route('/status', methods=['PUT'])
@admin_required()
def update_application_status():
    try:
        data = request.get_json()
        application_id = data.get('application_id')
        new_status = data.get('status')
        comment_content = data.get('comment', '')
        
        if not application_id or not new_status:
            return jsonify({'error': 'Application ID and status required'}), 400
        
        application = OrganizationApplication.query.get_or_404(application_id)
        admin = get_current_user()
        
        # Validate status transition based on admin role
        valid_transitions = {
            AdminRole.FBO_OFFICER: {
                ApplicationStatus.PENDING: [ApplicationStatus.FBO_REVIEW, ApplicationStatus.REVIEWING_AGAIN],
                ApplicationStatus.FBO_REVIEW: [ApplicationStatus.TRANSFER_TO_DM, ApplicationStatus.REVIEWING_AGAIN],
                ApplicationStatus.REVIEWING_AGAIN: [ApplicationStatus.FBO_REVIEW]
            },
            AdminRole.DIVISION_MANAGER: {
                ApplicationStatus.TRANSFER_TO_DM: [ApplicationStatus.DM_REVIEW],
                ApplicationStatus.DM_REVIEW: [ApplicationStatus.TRANSFER_TO_HOD, ApplicationStatus.REVIEWING_AGAIN]
            },
            AdminRole.HOD: {
                ApplicationStatus.TRANSFER_TO_HOD: [ApplicationStatus.HOD_REVIEW],
                ApplicationStatus.HOD_REVIEW: [ApplicationStatus.TRANSFER_TO_SG, ApplicationStatus.REVIEWING_AGAIN]
            },
            AdminRole.SECRETARY_GENERAL: {
                ApplicationStatus.TRANSFER_TO_SG: [ApplicationStatus.SG_REVIEW],
                ApplicationStatus.SG_REVIEW: [ApplicationStatus.TRANSFER_TO_CEO, ApplicationStatus.REJECTED]
            },
            AdminRole.CEO: {
                ApplicationStatus.TRANSFER_TO_CEO: [ApplicationStatus.CEO_REVIEW],
                ApplicationStatus.CEO_REVIEW: [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]
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
        
        # Add comment if provided
        if comment_content.strip():
            comment = ApplicationComment(
                content=comment_content.strip(),
                performed_by_id=admin.id,
                application_id=application.id
            )
            db.session.add(comment)
        
        # If approved, generate certificate number and update status to certificate issued
        if new_status_enum == ApplicationStatus.APPROVED:
            application.certificate_number = f"RGB-{datetime.now().year}-{application.id:06d}"
            application.certificate_issued_at = datetime.utcnow()
            application.status = ApplicationStatus.CERTIFICATE_ISSUED
        
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
            ApplicationStatus.TRANSFER_TO_DM: AdminRole.DIVISION_MANAGER,
            ApplicationStatus.TRANSFER_TO_HOD: AdminRole.HOD,
            ApplicationStatus.TRANSFER_TO_SG: AdminRole.SECRETARY_GENERAL,
            ApplicationStatus.TRANSFER_TO_CEO: AdminRole.CEO
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
            'comment': comment_content
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
        
        if claims.get('type') == 'applicant' and application.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
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



@bp.route('/', methods=['GET'])
@jwt_required()
def get_applications():
    try:
        user = get_current_user()        
        claims = get_jwt()      

        if claims.get('type') == 'applicant':
            # Applicant can only see their own applications
            applications = OrganizationApplication.query.filter_by(applicant_id=user.id).all()
            # Add canEdit field for applicants (they can edit only PENDING and REVIEWING_AGAIN)
            applications_data = []
            for app in applications:
                app_dict = app.to_dict()
                app_dict['canEdit'] = app.status in [ApplicationStatus.PENDING, ApplicationStatus.REVIEWING_AGAIN]
                applications_data.append(app_dict)
            
            return jsonify({
                'applications': applications_data
            })
        
        elif claims.get('type') == 'admin':
            # Define what statuses each admin role can see and edit
            role_permissions = {
                AdminRole.FBO_OFFICER: {
                    'can_view': [
                        ApplicationStatus.REJECTED,
                        ApplicationStatus.PENDING,
                        ApplicationStatus.FBO_REVIEW,
                        ApplicationStatus.REVIEWING_AGAIN,
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW,
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.PENDING,
                        ApplicationStatus.FBO_REVIEW,
                        ApplicationStatus.REVIEWING_AGAIN
                    ]
                },
                AdminRole.DIVISION_MANAGER: {
                    'can_view': [
                        ApplicationStatus.REJECTED,
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW,
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW
                    ]
                },
                AdminRole.HOD: {
                    'can_view': [
                        ApplicationStatus.REJECTED,
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW
                    ]
                },
                AdminRole.SECRETARY_GENERAL: {
                    'can_view': [
                        ApplicationStatus.REJECTED,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW
                    ]
                },
                AdminRole.CEO: {
                    'can_view': [
                        ApplicationStatus.REJECTED,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED,
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ]
                }
            }
            
            if user.role in role_permissions:
                # Get applications that this admin role can view
                viewable_statuses = role_permissions[user.role]['can_view']
                editable_statuses = role_permissions[user.role]['can_edit']
                
                applications = OrganizationApplication.query.filter(
                    OrganizationApplication.status.in_(viewable_statuses)
                ).all()
                
                # Add canEdit field based on current status and admin permissions
                applications_data = []
                for app in applications:
                    app_dict = app.to_dict()
                    app_dict['canEdit'] = app.status in editable_statuses
                    applications_data.append(app_dict)
                
                return jsonify({
                    'applications': applications_data
                })
            else:
                return jsonify({
                    'applications': []
                })
        
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
    except Exception as e:
        return jsonify({'error': f'Failed to get applications: {str(e)}'}), 500

@bp.route('/<int:application_id>', methods=['GET'])
@jwt_required()
def get_application(application_id):
    try:
        user = get_current_user()
        claims = get_jwt() 
        
        application = OrganizationApplication.query.get_or_404(application_id)
        
        # Check if application is rejected (no one can access rejected applications)
        if application.status == ApplicationStatus.REJECTED:
            return jsonify({'error': 'Access denied - Application is rejected'}), 403
        
        # Check permissions
        if claims.get('type') == 'applicant':
            if application.applicant_id != user.id:
                return jsonify({'error': 'Access denied'}), 403
            # Applicant can edit only PENDING and REVIEWING_AGAIN
            can_edit = application.status in [ApplicationStatus.PENDING, ApplicationStatus.REVIEWING_AGAIN]
        
        elif claims.get('type') == 'admin':
            # Define what statuses each admin role can view and edit
            role_permissions = {
                AdminRole.FBO_OFFICER: {
                    'can_view': [
                        ApplicationStatus.PENDING,
                        ApplicationStatus.FBO_REVIEW,
                        ApplicationStatus.REVIEWING_AGAIN,
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW,
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.PENDING,
                        ApplicationStatus.FBO_REVIEW,
                        ApplicationStatus.REVIEWING_AGAIN
                    ]
                },
                AdminRole.DIVISION_MANAGER: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW,
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_DM,
                        ApplicationStatus.DM_REVIEW
                    ]
                },
                AdminRole.HOD: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW,
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_HOD,
                        ApplicationStatus.HOD_REVIEW
                    ]
                },
                AdminRole.SECRETARY_GENERAL: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW,
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_SG,
                        ApplicationStatus.SG_REVIEW
                    ]
                },
                AdminRole.CEO: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_CEO,
                        ApplicationStatus.CEO_REVIEW,
                        ApplicationStatus.APPROVED,
                        ApplicationStatus.CERTIFICATE_ISSUED
                    ]
                }
            }
            
            if user.role not in role_permissions:
                return jsonify({'error': 'Access denied'}), 403
            
            # Check if admin can view this application status
            if application.status not in role_permissions[user.role]['can_view']:
                return jsonify({'error': 'Access denied'}), 403
            
            # Check if admin can edit this application status
            can_edit = application.status in role_permissions[user.role]['can_edit']
        
        else:
            return jsonify({'error': 'Invalid user type'}), 403
        
        # Include related data
        app_data = application.to_dict()
        app_data['canEdit'] = can_edit
        app_data['cluster_information'] = application.cluster_information.to_dict() if application.cluster_information else None
        app_data['supporting_documents'] = [doc.to_dict() for doc in application.supporting_documents]
        
        return jsonify({'application': app_data})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get application: {str(e)}'}), 500

@bp.route('/stats', methods=['GET'])
@admin_required()
def get_application_stats():
    try:
        admin = get_current_user()
        
        # Define what statuses each admin role can view for stats
        role_view_permissions = {
            AdminRole.FBO_OFFICER: [
                ApplicationStatus.PENDING,
                ApplicationStatus.FBO_REVIEW,
                ApplicationStatus.REVIEWING_AGAIN,
                ApplicationStatus.TRANSFER_TO_DM,
                ApplicationStatus.DM_REVIEW,
                ApplicationStatus.TRANSFER_TO_HOD,
                ApplicationStatus.HOD_REVIEW,
                ApplicationStatus.TRANSFER_TO_SG,
                ApplicationStatus.SG_REVIEW,
                ApplicationStatus.TRANSFER_TO_CEO,
                ApplicationStatus.CEO_REVIEW,
                ApplicationStatus.APPROVED,
                ApplicationStatus.CERTIFICATE_ISSUED
            ],
            AdminRole.DIVISION_MANAGER: [
                ApplicationStatus.TRANSFER_TO_DM,
                ApplicationStatus.DM_REVIEW,
                ApplicationStatus.TRANSFER_TO_HOD,
                ApplicationStatus.HOD_REVIEW,
                ApplicationStatus.TRANSFER_TO_SG,
                ApplicationStatus.SG_REVIEW,
                ApplicationStatus.TRANSFER_TO_CEO,
                ApplicationStatus.CEO_REVIEW,
                ApplicationStatus.APPROVED,
                ApplicationStatus.CERTIFICATE_ISSUED
            ],
            AdminRole.HOD: [
                ApplicationStatus.TRANSFER_TO_HOD,
                ApplicationStatus.HOD_REVIEW,
                ApplicationStatus.TRANSFER_TO_SG,
                ApplicationStatus.SG_REVIEW,
                ApplicationStatus.TRANSFER_TO_CEO,
                ApplicationStatus.CEO_REVIEW,
                ApplicationStatus.APPROVED,
                ApplicationStatus.CERTIFICATE_ISSUED
            ],
            AdminRole.SECRETARY_GENERAL: [
                ApplicationStatus.TRANSFER_TO_SG,
                ApplicationStatus.SG_REVIEW,
                ApplicationStatus.TRANSFER_TO_CEO,
                ApplicationStatus.CEO_REVIEW,
                ApplicationStatus.APPROVED,
                ApplicationStatus.CERTIFICATE_ISSUED
            ],
            AdminRole.CEO: [
                ApplicationStatus.TRANSFER_TO_CEO,
                ApplicationStatus.CEO_REVIEW,
                ApplicationStatus.APPROVED,
                ApplicationStatus.CERTIFICATE_ISSUED
            ]
        }
        
        # Get statistics based on admin role
        stats = {}
        
        if admin.role in role_view_permissions:
            viewable_statuses = role_view_permissions[admin.role]
            
            # Total applications this admin can see
            stats['total_applications'] = OrganizationApplication.query.filter(
                OrganizationApplication.status.in_(viewable_statuses)
            ).count()
            
            # Applications by status (only for statuses this admin can see)
            status_counts = {}
            for status in viewable_statuses:
                count = OrganizationApplication.query.filter_by(status=status).count()
                status_counts[status.value] = count
            stats['by_status'] = status_counts
            
            # Role-specific stats
            role_edit_permissions = {
                AdminRole.FBO_OFFICER: [ApplicationStatus.PENDING, ApplicationStatus.FBO_REVIEW, ApplicationStatus.REVIEWING_AGAIN],
                AdminRole.DIVISION_MANAGER: [ApplicationStatus.TRANSFER_TO_DM, ApplicationStatus.DM_REVIEW],
                AdminRole.HOD: [ApplicationStatus.TRANSFER_TO_HOD, ApplicationStatus.HOD_REVIEW],
                AdminRole.SECRETARY_GENERAL: [ApplicationStatus.TRANSFER_TO_SG, ApplicationStatus.SG_REVIEW],
                AdminRole.CEO: [ApplicationStatus.TRANSFER_TO_CEO, ApplicationStatus.CEO_REVIEW, ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]
            }
            
            if admin.role in role_edit_permissions:
                stats['pending_my_action'] = OrganizationApplication.query.filter(
                    OrganizationApplication.status.in_(role_edit_permissions[admin.role])
                ).count()
            
            # For CEO, add comprehensive stats
            if admin.role == AdminRole.CEO:
                stats['approved'] = OrganizationApplication.query.filter_by(status=ApplicationStatus.APPROVED).count()
                stats['certificate_issued'] = OrganizationApplication.query.filter_by(status=ApplicationStatus.CERTIFICATE_ISSUED).count()
                
                # Applications by district (for CEO only)
                from sqlalchemy import func
                district_stats = db.session.query(
                    District.name,
                    func.count(OrganizationApplication.id).label('count')
                ).join(
                    OrganizationApplication, District.id == OrganizationApplication.district_id
                ).filter(
                    OrganizationApplication.status.in_(viewable_statuses)
                ).group_by(District.name).all()
                
                stats['by_district'] = [
                    {'district': row.name, 'count': row.count} 
                    for row in district_stats
                ]
                
                # Applications by month (last 12 months)
                from sqlalchemy import extract
                monthly_stats = db.session.query(
                    extract('month', OrganizationApplication.submitted_at).label('month'),
                    extract('year', OrganizationApplication.submitted_at).label('year'),
                    func.count(OrganizationApplication.id).label('count')
                ).filter(
                    OrganizationApplication.submitted_at >= datetime.now() - timedelta(days=365),
                    OrganizationApplication.status.in_(viewable_statuses)
                ).group_by('year', 'month').all()
                
                stats['monthly'] = [
                    {
                        'month': int(row.month),
                        'year': int(row.year),
                        'count': row.count
                    } for row in monthly_stats
                ]
        
        return jsonify({'stats': stats})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get application stats: {str(e)}'}), 500

@bp.route('/workflow', methods=['GET'])
@jwt_required()
def get_workflow_info():
    """Get application workflow information"""
    try:
        workflow = {
            'statuses': [status.value for status in ApplicationStatus],
            'role_permissions': {
                AdminRole.FBO_OFFICER.value: {
                    'can_view': [
                        ApplicationStatus.PENDING.value,
                        ApplicationStatus.FBO_REVIEW.value,
                        ApplicationStatus.REVIEWING_AGAIN.value,
                        ApplicationStatus.TRANSFER_TO_DM.value,
                        ApplicationStatus.DM_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_HOD.value,
                        ApplicationStatus.HOD_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_SG.value,
                        ApplicationStatus.SG_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ],
                    'can_edit': [
                        ApplicationStatus.PENDING.value,
                        ApplicationStatus.FBO_REVIEW.value,
                        ApplicationStatus.REVIEWING_AGAIN.value
                    ]
                },
                AdminRole.DIVISION_MANAGER.value: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_DM.value,
                        ApplicationStatus.DM_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_HOD.value,
                        ApplicationStatus.HOD_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_SG.value,
                        ApplicationStatus.SG_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_DM.value,
                        ApplicationStatus.DM_REVIEW.value
                    ]
                },
                AdminRole.HOD.value: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_HOD.value,
                        ApplicationStatus.HOD_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_SG.value,
                        ApplicationStatus.SG_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_HOD.value,
                        ApplicationStatus.HOD_REVIEW.value
                    ]
                },
                AdminRole.SECRETARY_GENERAL.value: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_SG.value,
                        ApplicationStatus.SG_REVIEW.value,
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_SG.value,
                        ApplicationStatus.SG_REVIEW.value
                    ]
                },
                AdminRole.CEO.value: {
                    'can_view': [
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ],
                    'can_edit': [
                        ApplicationStatus.TRANSFER_TO_CEO.value,
                        ApplicationStatus.CEO_REVIEW.value,
                        ApplicationStatus.APPROVED.value,
                        ApplicationStatus.CERTIFICATE_ISSUED.value
                    ]
                }
            }
        }
        
        return jsonify({'workflow': workflow})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get workflow info: {str(e)}'}), 500