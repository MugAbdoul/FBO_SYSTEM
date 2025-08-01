from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt
from app import db
from app.models.admin import AdminRole
from app.models.organization_application import OrganizationApplication, ApplicationStatus
from app.utils.auth import get_current_user, admin_required
from datetime import datetime
import qrcode
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue, darkblue, gray, white, darkgreen, lightgrey
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import base64

from app.utils.responsiveCertificateGenerator import create_enhanced_certificate_pdf

bp = Blueprint('certificates', __name__)


@bp.route('/generate/<int:application_id>', methods=['POST'])
def generate_certificate(application_id):
    try:
        application = OrganizationApplication.query.get_or_404(application_id)
        
        if application.status != ApplicationStatus.APPROVED and application.status != ApplicationStatus.CERTIFICATE_ISSUED:
            return jsonify({'error': 'Application must be approved to generate certificate'}), 400
        
        # Generate QR code for verification
        verification_url = f"http://localhost:3000/verify/{application.certificate_number}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
        
        # Save QR code data to application
        application.qr_code_data = qr_data
        application.status = ApplicationStatus.CERTIFICATE_ISSUED
        if not application.certificate_issued_at:
            application.certificate_issued_at = datetime.utcnow()
        db.session.commit()
        
        # Generate enhanced PDF certificate
        pdf_buffer = create_enhanced_certificate_pdf(application, include_qr=True)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"certificate_{application.certificate_number}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate certificate: {str(e)}'}), 500

@bp.route('/verify/<certificate_number>', methods=['GET'])
def verify_certificate(certificate_number):
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
            'address': f"{application.district.province.name}/{application.district.name}",
            'cluster_of_intervention': application.cluster_information.cluster_of_intervention if application.cluster_information else None,
            'status': 'Active',
            'verification_timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to verify certificate: {str(e)}'}), 500

@bp.route('/download/<int:application_id>', methods=['GET'])
@jwt_required()
def download_certificate(application_id):
    try:
        user = get_current_user()
        application = OrganizationApplication.query.get_or_404(application_id)
        claims = get_jwt() 
        
        # Access control
        if claims.get('type') == 'applicant' and application.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        if application.status != ApplicationStatus.CERTIFICATE_ISSUED:
            return jsonify({'error': 'Certificate not available for download'}), 400
        
        # Generate enhanced PDF certificate
        pdf_buffer = create_enhanced_certificate_pdf(application, include_qr=True)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"certificate_{application.certificate_number}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to download certificate: {str(e)}'}), 500

@bp.route('/preview/<int:application_id>', methods=['GET'])
@jwt_required()
def preview_certificate(application_id):
    """
    Generate a preview version of the certificate (without QR code for draft viewing)
    """
    try:
        user = get_current_user()
        application = OrganizationApplication.query.get_or_404(application_id)
        claims = get_jwt()
        
        # Access control
        if claims.get('type') == 'applicant' and application.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Create preview certificate (without QR code)
        pdf_buffer = create_enhanced_certificate_pdf(application, include_qr=False)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"certificate_preview_{application.certificate_number or 'draft'}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate certificate preview: {str(e)}'}), 500

@bp.route('/bulk-download', methods=['POST'])
@jwt_required()
def bulk_download_certificates():
    """
    Download multiple certificates as a ZIP file
    """
    try:
        from zipfile import ZipFile
        
        data = request.get_json()
        application_ids = data.get('application_ids', [])
        
        if not application_ids:
            return jsonify({'error': 'No applications specified'}), 400
        
        # Create ZIP buffer
        zip_buffer = io.BytesIO()
        
        with ZipFile(zip_buffer, 'w') as zip_file:
            for app_id in application_ids:
                try:
                    application = OrganizationApplication.query.get(app_id)
                    if application and application.status == ApplicationStatus.CERTIFICATE_ISSUED:
                        # Generate PDF for this application
                        pdf_buffer = create_enhanced_certificate_pdf(application, include_qr=True)
                        
                        # Add to ZIP
                        zip_file.writestr(
                            f"certificate_{application.certificate_number}.pdf",
                            pdf_buffer.getvalue()
                        )
                except Exception as e:
                    continue  # Skip failed certificates
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"certificates_bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate bulk download: {str(e)}'}), 500