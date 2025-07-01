from flask import Blueprint, request, jsonify
from app.models.organization_application import OrganizationApplication, ApplicationStatus
from app.models.funding_source import FundingSource
from app.models.supporting_document import DOCUMENT_TYPE_INFO
import json

bp = Blueprint('public', __name__)

@bp.route('/verify/<certificate_number>', methods=['GET'])
def verify_certificate(certificate_number):
    """Public endpoint to verify certificates"""
    try:
        application = OrganizationApplication.query.filter_by(
            certificate_number=certificate_number
        ).first()
        
        if not application:
            return jsonify({
                'valid': False,
                'message': 'Certificate not found'
            }), 404
        
        if application.status != ApplicationStatus.CERTIFICATE_ISSUED:
            return jsonify({
                'valid': False,
                'message': 'Certificate not issued'
            }), 400
        
        return jsonify({
            'valid': True,
            'certificate_number': application.certificate_number,
            'organization_name': application.organization_name,
            'applicant_name': f"{application.applicant.title} {application.applicant.firstname} {application.applicant.lastname}",
            'issued_date': application.certificate_issued_at.isoformat(),
            'address': application.address,
            'cluster_of_intervention': application.cluster_information.cluster_of_intervention if application.cluster_information else None
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to verify certificate: {str(e)}'}), 500

@bp.route('/statistics', methods=['GET'])
def get_public_statistics():
    """Get public statistics about the system"""
    try:
        stats = {
            'total_applications': OrganizationApplication.query.count(),
            'approved_applications': OrganizationApplication.query.filter_by(status=ApplicationStatus.APPROVED).count(),
            'certificates_issued': OrganizationApplication.query.filter_by(status=ApplicationStatus.CERTIFICATE_ISSUED).count(),
            'active_organizations': OrganizationApplication.query.filter(
                OrganizationApplication.status.in_([ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED])
            ).count()
        }
        
        return jsonify({'statistics': stats})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get statistics: {str(e)}'}), 500

@bp.route('/funding-sources', methods=['GET'])
def get_funding_sources():
    """Get available funding sources for organizations"""
    try:
        sources = FundingSource.query.all()
        return jsonify({
            'funding_sources': [source.to_dict() for source in sources]
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get funding sources: {str(e)}'}), 500

@bp.route('/document-requirements', methods=['GET'])
def get_document_requirements():
    """Get document requirements for applications"""
    try:
        requirements = []
        for doc_type, info in DOCUMENT_TYPE_INFO.items():
            requirements.append({
                'document_type': doc_type.value,
                'name': info['name'],
                'required': info['required'],
                'description': f"Please provide {info['name'].lower()}"
            })
        
        return jsonify({'requirements': requirements})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get document requirements: {str(e)}'}), 500

@bp.route('/faq', methods=['GET'])
def get_faq():
    """Get frequently asked questions"""
    try:
        # In a real implementation, this would come from a database
        faq_data = [
            {
                'category': 'General',
                'questions': [
                    {
                        'question': 'What is the RGB Church Authorization Portal?',
                        'answer': 'The RGB Church Authorization Portal is the official digital platform for religious organizations to apply for and obtain authorization from Rwanda Governance Board to operate legally in Rwanda.'
                    },
                    {
                        'question': 'Who needs to apply for religious organization authorization?',
                        'answer': 'All religious organizations, churches, faith-based organizations, and spiritual groups that want to operate officially in Rwanda must obtain authorization from RGB.'
                    }
                ]
            },
            {
                'category': 'Application Process',
                'questions': [
                    {
                        'question': 'How long does the review process take?',
                        'answer': 'The typical review process takes 2-4 weeks, depending on the completeness of your application and current volume. You will receive notifications about status updates throughout the process.'
                    },
                    {
                        'question': 'What documents do I need to submit?',
                        'answer': 'Required documents include: Organization committee names and CVs, District certificate, Land UPI and church photos, organizational doctrine, annual action plan, proof of payment, and partnership documents (if applicable).'
                    }
                ]
            }
        ]
        
        return jsonify({'faq': faq_data})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get FAQ: {str(e)}'}), 500

@bp.route('/contact', methods=['POST'])
def submit_contact_form():
    """Submit contact form"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'subject', 'message']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # In a real implementation, you would:
        # 1. Save the contact form to database
        # 2. Send email notification to support team
        # 3. Send confirmation email to user
        
        # For now, just return success
        return jsonify({
            'message': 'Contact form submitted successfully. We will get back to you soon.'
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to submit contact form: {str(e)}'}), 500