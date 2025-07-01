from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from app import db
from app.models.organization_application import OrganizationApplication, ApplicationStatus
from app.models.applicant import Applicant
from app.utils.auth import admin_required, get_current_user
from datetime import datetime, timedelta
from sqlalchemy import func, case, extract, or_
import pandas as pd
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
from collections import defaultdict
import uuid
import os
import logging

# Configure logger
logger = logging.getLogger(__name__)

bp = Blueprint('reports', __name__)

# -----------------------------------------------------------------------------
# Report Statistics Endpoint
# -----------------------------------------------------------------------------

@bp.route('/stats', methods=['GET'])
@admin_required()
def get_report_stats():
    """Get overview statistics for reports dashboard"""
    try:
        return jsonify(get_dashboard_statistics())
    except Exception as e:
        logger.error(f"Error fetching report statistics: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to fetch report statistics: {str(e)}'}), 500

def get_dashboard_statistics():
    """Collect and organize all statistics for the dashboard"""
    # Overall statistics
    overall_stats = get_overall_statistics()
    
    # Status distribution
    status_distribution = get_status_distribution()
    
    # Monthly trends
    monthly_trends = get_monthly_trends()
    
    # Risk distribution
    risk_distribution = get_risk_distribution()
    
    # Processing time by stage
    processing_time = get_processing_time()
    
    # Applications by nationality
    nationality_distribution = get_nationality_distribution()
    
    # Applications by age group
    age_distribution = get_age_distribution()
    
    # Application success rate by risk score
    risk_success_rate = get_risk_success_rate()
    
    return {
        'overview': overall_stats,
        'status_distribution': status_distribution,
        'monthly_trends': monthly_trends,
        'risk_distribution': risk_distribution,
        'processing_time': processing_time,
        'nationality_distribution': nationality_distribution,
        'age_distribution': age_distribution,
        'risk_success_rate': risk_success_rate
    }

def get_overall_statistics():
    """Get overall application statistics"""
    total_applications = OrganizationApplication.query.count()
    approved = OrganizationApplication.query.filter(
    or_(
        OrganizationApplication.status == ApplicationStatus.APPROVED,
        OrganizationApplication.status == ApplicationStatus.CERTIFICATE_ISSUED
    )
).count()
    rejected = OrganizationApplication.query.filter_by(status=ApplicationStatus.REJECTED).count()
    
    pending_statuses = [
        ApplicationStatus.PENDING, 
        ApplicationStatus.UNDER_REVIEW, 
        ApplicationStatus.DM_REVIEW,
        ApplicationStatus.HOD_REVIEW,
        ApplicationStatus.SG_REVIEW,
        ApplicationStatus.CEO_REVIEW
    ]
    
    pending = OrganizationApplication.query.filter(
        OrganizationApplication.status.in_(pending_statuses)
    ).count()
    
    certificates_issued = OrganizationApplication.query.filter_by(
        status=ApplicationStatus.CERTIFICATE_ISSUED
    ).count()
    
    return {
        'total_applications': total_applications,
        'approved': approved,
        'rejected': rejected,
        'pending': pending,
        'certificates_issued': certificates_issued
    }

def get_status_distribution():
    """Get application status distribution"""
    status_counts = db.session.query(
        OrganizationApplication.status,
        func.count(OrganizationApplication.id)
    ).group_by(OrganizationApplication.status).all()
    
    return {status.value: count for status, count in status_counts}

def get_monthly_trends():
    """Get monthly application trends for the last 12 months"""
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)
    
    monthly_data = db.session.query(
        func.date_trunc('month', OrganizationApplication.submitted_at).label('month'),
        func.count(OrganizationApplication.id).label('count')
    ).filter(OrganizationApplication.submitted_at >= twelve_months_ago)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    return [
        {
            'month': month.strftime('%b %Y'),
            'count': count
        } for month, count in monthly_data
    ]

def get_risk_distribution():
    """Get risk score distribution"""
    risk_data = db.session.query(
        case(
            (OrganizationApplication.risk_score < 40, 'Low Risk'),
            (OrganizationApplication.risk_score < 70, 'Medium Risk'),
            else_='High Risk'
        ).label('risk_category'),
        func.count(OrganizationApplication.id).label('count')
    ).group_by('risk_category').all()
    
    return [
        {
            'name': category,
            'value': count,
            'color': '#10B981' if category == 'Low Risk' else 
                     '#F59E0B' if category == 'Medium Risk' else '#EF4444'
        } for category, count in risk_data
    ]

def get_processing_time():
    """Get average processing time by stage"""
    # For simplicity, estimating average processing times
    # In a real app, you'd track timestamps for each stage transition
    processing_stages = ['DM_REVIEW', 'HOD_REVIEW', 'SG_REVIEW', 'CEO_REVIEW']
    stage_time = {
        'DM_REVIEW': 3.2,
        'HOD_REVIEW': 2.1,
        'SG_REVIEW': 1.5,
        'CEO_REVIEW': 1.2
    }
    
    return [
        {
            'stage': stage.replace('_', ' ').title(),
            'avgDays': stage_time[stage]
        } for stage in processing_stages
    ]

def get_nationality_distribution():
    """Get application distribution by nationality"""
    nationality_data = db.session.query(
        Applicant.nationality,
        func.count(OrganizationApplication.id).label('count')
    ).join(OrganizationApplication, OrganizationApplication.applicant_id == Applicant.id)\
     .group_by(Applicant.nationality)\
     .order_by(func.count(OrganizationApplication.id).desc())\
     .limit(10)\
     .all()
     
    return [
        {
            'nationality': nationality,
            'count': count
        } for nationality, count in nationality_data
    ]

def get_age_distribution():
    """Get application distribution by age group"""
    current_year = datetime.utcnow().year
    age_data = db.session.query(
        case(
            (current_year - extract('year', Applicant.date_of_birth) < 25, 'Under 25'),
            (current_year - extract('year', Applicant.date_of_birth) < 35, '25-34'),
            (current_year - extract('year', Applicant.date_of_birth) < 45, '35-44'),
            (current_year - extract('year', Applicant.date_of_birth) < 55, '45-54'),
            else_='55 and Above'
        ).label('age_group'),
        func.count(OrganizationApplication.id).label('count')
    ).join(OrganizationApplication, OrganizationApplication.applicant_id == Applicant.id)\
     .group_by('age_group')\
     .all()
     
    return [
        {
            'age_group': age_group,
            'count': count
        } for age_group, count in age_data
    ]

def get_risk_success_rate():
    """Get application success rate by risk score range"""
    risk_success_data = db.session.query(
        case(
            (OrganizationApplication.risk_score < 33, '0-33'),
            (OrganizationApplication.risk_score < 66, '34-66'),
            else_='67-100'
        ).label('risk_range'),
        func.count(case(
            (OrganizationApplication.status == ApplicationStatus.APPROVED, 1),
            (OrganizationApplication.status == ApplicationStatus.CERTIFICATE_ISSUED, 1),
            else_=None
        )).label('approved'),
        func.count(OrganizationApplication.id).label('total')
    ).group_by('risk_range').all()
    
    return [
        {
            'risk_range': risk_range,
            'success_rate': (approved / total) * 100 if total > 0 else 0,
            'total': total
        } for risk_range, approved, total in risk_success_data
    ]

# -----------------------------------------------------------------------------
# Report Generation Endpoint
# -----------------------------------------------------------------------------

@bp.route('/generate', methods=['POST'])
@admin_required()
def generate_report():
    """Generate a downloadable report based on parameters"""
    try:
        # Get and validate request data
        data = request.get_json()
        report_params = validate_report_parameters(data)
        
        # Query applications
        applications = query_applications(
            report_params['start_date'], 
            report_params['end_date'], 
            report_params['status']
        )
        
        # Generate report in requested format
        report_generator = ReportGeneratorFactory.create_generator(
            report_params['report_format'],
            applications,
            report_params['report_type'],
            report_params['start_date'],
            report_params['end_date'],
            report_params['status']
        )
        
        file_obj = report_generator.generate()
        
        # Generate unique filename
        filename_base = f"{report_params['report_type']}_{report_params['start_date'].strftime('%Y%m%d')}_{report_params['end_date'].strftime('%Y%m%d')}"
        unique_id = uuid.uuid4().hex[:8]
        filepath = f"app/static/reports/{filename_base}_{unique_id}.{report_params['report_format']}"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save file temporarily
        with open(filepath, 'wb') as f:
            f.write(file_obj.getvalue())
        
        # Return downloadable file
        return send_file(
            io.BytesIO(file_obj.getvalue()),
            mimetype=report_generator.mime_type,
            as_attachment=True,
            download_name=f"{filename_base}.{report_params['report_format']}"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid report parameters: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to generate report: {str(e)}'}), 500

def validate_report_parameters(data):
    """Validate and process report parameters"""
    report_type = data.get('reportType', 'summary')
    report_format = data.get('format', 'pdf')
    
    # Validate report type
    valid_report_types = ['summary', 'detailed', 'analytics', 'compliance', 'demographic']
    if report_type not in valid_report_types:
        raise ValueError(f"Invalid report type. Must be one of: {', '.join(valid_report_types)}")
    
    # Validate report format
    valid_formats = ['pdf', 'excel', 'csv']
    if report_format not in valid_formats:
        raise ValueError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
    
    # Process dates
    try:
        start_date = datetime.strptime(data.get('startDate', ''), '%Y-%m-%d') if data.get('startDate') else None
        end_date = datetime.strptime(data.get('endDate', ''), '%Y-%m-%d') if data.get('endDate') else None
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")
    
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    
    if not end_date:
        end_date = datetime.utcnow()
    
    # Process status filter
    status = data.get('status', '')
    
    return {
        'report_type': report_type,
        'report_format': report_format,
        'start_date': start_date,
        'end_date': end_date + timedelta(days=1),  # Add one day to include the full end day
        'status': status
    }

def query_applications(start_date, end_date, status_filter=None):
    """Query applications based on date range and optional status filter"""
    query = OrganizationApplication.query.filter(
        OrganizationApplication.submitted_at >= start_date,
        OrganizationApplication.submitted_at < end_date
    )
    
    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = ApplicationStatus(status_filter)
            query = query.filter(OrganizationApplication.status == status_enum)
        except ValueError:
            logger.warning(f"Invalid status filter: {status_filter}")
            pass
    
    return query.all()

# -----------------------------------------------------------------------------
# Report Generator Factory
# -----------------------------------------------------------------------------

class ReportGeneratorFactory:
    """Factory for creating report generators based on format"""
    
    @staticmethod
    def create_generator(report_format, applications, report_type, start_date, end_date, status_filter):
        """Create and return appropriate report generator"""
        if report_format == 'pdf':
            return PDFReportGenerator(applications, report_type, start_date, end_date, status_filter)
        elif report_format == 'excel':
            return ExcelReportGenerator(applications, report_type, start_date, end_date, status_filter)
        elif report_format == 'csv':
            return CSVReportGenerator(applications, report_type, start_date, end_date, status_filter)
        else:
            raise ValueError(f"Unsupported report format: {report_format}")

# -----------------------------------------------------------------------------
# Report Generator Base Class
# -----------------------------------------------------------------------------

class ReportGenerator:
    """Base class for report generators"""
    
    def __init__(self, applications, report_type, start_date, end_date, status_filter):
        self.applications = applications
        self.report_type = report_type
        self.start_date = start_date
        self.end_date = end_date
        self.status_filter = status_filter
        self.mime_type = None
    
    def generate(self):
        """Generate report (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement generate()")

# -----------------------------------------------------------------------------
# PDF Report Generator
# -----------------------------------------------------------------------------

class PDFReportGenerator(ReportGenerator):
    """Generates PDF reports"""
    
    def __init__(self, applications, report_type, start_date, end_date, status_filter):
        super().__init__(applications, report_type, start_date, end_date, status_filter)
        self.mime_type = 'application/pdf'
    
    def generate(self):
        """Generate PDF report based on report type"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add report header
        elements.extend(self._create_header())
        
        # Add report content based on type
        content_generator = ReportContentFactory.create_generator(self.report_type)
        elements.extend(content_generator.generate_pdf_content(self.applications))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def _create_header(self):
        """Create report header elements"""
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,  # Center
            spaceAfter=12
        )
        
        # Add report title
        title_map = {
            'summary': "Application Summary Report",
            'detailed': "Detailed Application Report",
            'analytics': "Analytics Report",
            'compliance': "Compliance Report",
            'demographic': "Demographic Report"
        }
        title = title_map.get(self.report_type, f"{self.report_type.title()} Report")
        elements.append(Paragraph(title, title_style))
        
        # Add date range and filters
        date_style = ParagraphStyle(
            'DateRange',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,  # Center
            spaceAfter=16
        )
        
        date_text = f"Period: {self.start_date.strftime('%d %b %Y')} to {(self.end_date - timedelta(days=1)).strftime('%d %b %Y')}"
        if self.status_filter:
            date_text += f" | Status Filter: {self.status_filter}"
        
        elements.append(Paragraph(date_text, date_style))
        elements.append(Spacer(1, 12))
        
        return elements

# -----------------------------------------------------------------------------
# Excel Report Generator
# -----------------------------------------------------------------------------

class ExcelReportGenerator(ReportGenerator):
    """Generates Excel reports"""
    
    def __init__(self, applications, report_type, start_date, end_date, status_filter):
        super().__init__(applications, report_type, start_date, end_date, status_filter)
        self.mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def generate(self):
        """Generate Excel report based on report type"""
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        
        # Add different sheets based on report type
        content_generator = ReportContentFactory.create_generator(self.report_type)
        content_generator.generate_excel_content(
            workbook, 
            self.applications, 
            self.start_date, 
            self.end_date, 
            self.status_filter
        )
        
        workbook.close()
        buffer.seek(0)
        return buffer

# -----------------------------------------------------------------------------
# CSV Report Generator
# -----------------------------------------------------------------------------

class CSVReportGenerator(ReportGenerator):
    """Generates CSV reports"""
    
    def __init__(self, applications, report_type, start_date, end_date, status_filter):
        super().__init__(applications, report_type, start_date, end_date, status_filter)
        self.mime_type = 'text/csv'
    
    def generate(self):
        """Generate CSV report based on report type"""
        buffer = io.BytesIO()
        
        # Create DataFrame based on report type
        if self.report_type == 'summary':
            df = pd.DataFrame([
                {
                    'ID': app.id,
                    'Organization Name': app.organization_name,
                    'Status': app.status.value,
                    'Submitted Date': app.submitted_at.strftime('%Y-%m-%d'),
                    'Risk Score': app.risk_score
                } for app in self.applications
            ])
        elif self.report_type == 'detailed':
            df = pd.DataFrame([
                {
                    'ID': app.id,
                    'Organization Name': app.organization_name,
                    'Acronym': app.acronym,
                    'Email': app.organization_email,
                    'Phone': app.organization_phone,
                    'Address': app.address,
                    'Status': app.status.value,
                    'Submitted Date': app.submitted_at.strftime('%Y-%m-%d'),
                    'Last Modified': app.last_modified.strftime('%Y-%m-%d') if app.last_modified else '',
                    'Risk Score': app.risk_score,
                    'Certificate Number': app.certificate_number or '',
                    'Certificate Issued': app.certificate_issued_at.strftime('%Y-%m-%d') if app.certificate_issued_at else '',
                    'Applicant Name': f"{app.applicant.firstname} {app.applicant.lastname}" if app.applicant else '',
                    'Applicant Email': app.applicant.email if app.applicant else '',
                    'Comments': app.comments or ''
                } for app in self.applications
            ])
        elif self.report_type == 'analytics':
            # Group by status
            status_counts = defaultdict(int)
            for app in self.applications:
                status_counts[app.status.value] += 1
                
            # Create risk category counts
            risk_categories = {
                'Low Risk (0-39)': len([app for app in self.applications if app.risk_score < 40]),
                'Medium Risk (40-69)': len([app for app in self.applications if 40 <= app.risk_score < 70]),
                'High Risk (70-100)': len([app for app in self.applications if app.risk_score >= 70])
            }
            
            # Combine into a single DataFrame
            df1 = pd.DataFrame([{'Status': k, 'Count': v} for k, v in status_counts.items()])
            df2 = pd.DataFrame([{'Risk Category': k, 'Count': v} for k, v in risk_categories.items()])
            
            # Concatenate with a separator
            df = pd.concat([
                df1, 
                pd.DataFrame([{'Status': 'RISK CATEGORIES BELOW', 'Count': ''}]),
                df2.rename(columns={'Risk Category': 'Status'})
            ])
        elif self.report_type == 'compliance':
            df = pd.DataFrame([
                {
                    'ID': app.id,
                    'Organization Name': app.organization_name,
                    'Risk Score': app.risk_score,
                    'Risk Category': 'High Risk' if app.risk_score >= 70 else 
                                   'Medium Risk' if app.risk_score >= 40 else 'Low Risk',
                    'Status': app.status.value,
                    'Submitted Date': app.submitted_at.strftime('%Y-%m-%d'),
                    'Comments': app.comments or ''
                } for app in self.applications
            ])
        elif self.report_type == 'demographic':
            # For demographics, we need to extract unique applicants
            applicant_ids = set()
            unique_applicants = []
            
            for app in self.applications:
                if app.applicant and app.applicant_id not in applicant_ids:
                    applicant_ids.add(app.applicant_id)
                    unique_applicants.append(app.applicant)
            
            current_year = datetime.utcnow().year
            df = pd.DataFrame([
                {
                    'Name': f"{app.firstname} {app.lastname}",
                    'Gender': app.gender.value if app.gender else '',
                    'Nationality': app.nationality,
                    'Age': current_year - app.date_of_birth.year if app.date_of_birth else None,
                    'Age Group': get_age_group(app.date_of_birth, current_year) if app.date_of_birth else '',
                    'Civil Status': app.civil_status.value.replace('_', ' ').title() if app.civil_status else ''
                } for app in unique_applicants
            ])
        else:
            # Default columns for other report types
            df = pd.DataFrame([
                {
                    'ID': app.id,
                    'Organization Name': app.organization_name,
                    'Status': app.status.value,
                    'Submitted Date': app.submitted_at.strftime('%Y-%m-%d'),
                    'Risk Score': app.risk_score
                } for app in self.applications
            ])
        
        # Write to CSV
        df.to_csv(buffer, index=False, encoding='utf-8')
        buffer.seek(0)
        return buffer

def get_age_group(date_of_birth, current_year):
    """Helper function to determine age group"""
    if not date_of_birth:
        return ''
    
    age = current_year - date_of_birth.year
    if age < 25:
        return 'Under 25'
    elif age < 35:
        return '25-34'
    elif age < 45:
        return '35-44'
    elif age < 55:
        return '45-54'
    else:
        return '55 and Above'

# -----------------------------------------------------------------------------
# Report Content Factory
# -----------------------------------------------------------------------------

class ReportContentFactory:
    """Factory for creating report content generators"""
    
    @staticmethod
    def create_generator(report_type):
        """Create and return appropriate report content generator"""
        if report_type == 'summary':
            return SummaryReportContent()
        elif report_type == 'detailed':
            return DetailedReportContent()
        elif report_type == 'analytics':
            return AnalyticsReportContent()
        elif report_type == 'compliance':
            return ComplianceReportContent()
        elif report_type == 'demographic':
            return DemographicReportContent()
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

# -----------------------------------------------------------------------------
# Report Content Base Class
# -----------------------------------------------------------------------------

class ReportContent:
    """Base class for report content generators"""
    
    def generate_pdf_content(self, applications):
        """Generate PDF report content (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement generate_pdf_content()")
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate Excel report content (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement generate_excel_content()")
    
    def _create_heading_style(self):
        """Create a standardized heading style for PDF reports"""
        styles = getSampleStyleSheet()
        return ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.darkblue
        )
    
    def _create_subheading_style(self):
        """Create a standardized subheading style for PDF reports"""
        styles = getSampleStyleSheet()
        return ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.darkblue
        )
    
    def _create_standard_table_style(self, alternating_colors=True):
        """Create a standardized table style for PDF reports"""
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        if alternating_colors:
            style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lavender, colors.lightblue]))
        
        return TableStyle(style)
    
    def _create_excel_formats(self, workbook):
        """Create standardized formats for Excel reports"""
        formats = {
            'title': workbook.add_format({
                'bold': True, 
                'font_size': 16, 
                'font_color': '#0047AB',
                'align': 'center',
                'valign': 'vcenter',
                'border': 0
            }),
            'subtitle': workbook.add_format({
                'italic': True,
                'align': 'center'
            }),
            'header': workbook.add_format({
                'bold': True, 
                'bg_color': '#0047AB', 
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            }),
            'cell': workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            }),
            'alt_row': workbook.add_format({
                'border': 1,
                'bg_color': '#E6E6FA',
                'align': 'center',
                'valign': 'vcenter'
            }),
            'section': workbook.add_format({
                'bold': True, 
                'font_size': 12, 
                'font_color': '#0047AB',
                'bottom': 1,
                'bottom_color': '#0047AB'
            }),
            'high_risk': workbook.add_format({
                'border': 1,
                'bg_color': '#FFCCCC',
                'align': 'center',
                'valign': 'vcenter'
            }),
            'medium_risk': workbook.add_format({
                'border': 1,
                'bg_color': '#FFFFCC',
                'align': 'center',
                'valign': 'vcenter'
            }),
            'low_risk': workbook.add_format({
                'border': 1,
                'bg_color': '#CCFFCC',
                'align': 'center',
                'valign': 'vcenter'
            })
        }
        
        return formats

# -----------------------------------------------------------------------------
# Summary Report Content
# -----------------------------------------------------------------------------

class SummaryReportContent(ReportContent):
    """Generates content for summary reports"""
    
    def generate_pdf_content(self, applications):
        elements = []
        styles = getSampleStyleSheet()
        
        # Get standardized styles
        heading_style = self._create_heading_style()
        table_style = self._create_standard_table_style()
        
        # Overview statistics
        elements.append(Paragraph("Application Overview", heading_style))
        
        total = len(applications)
        status_counts = defaultdict(int)
        for app in applications:
            status_counts[app.status.value] += 1
        
        data = [['Metric', 'Count']]
        data.append(['Total Applications', total])
        for status, count in status_counts.items():
            data.append([f'{status.replace("_", " ").title()}', count])
        
        table = Table(data, colWidths=[300, 100])
        table.setStyle(table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 24))
        
        # Application listing with improved styling
        elements.append(Paragraph("Recent Applications", heading_style))
        
        # Sort by submission date (newest first)
        sorted_apps = sorted(applications, key=lambda x: x.submitted_at, reverse=True)
        
        # Take the 15 most recent
        recent_apps = sorted_apps[:15]
        
        data = [['ID', 'Organization', 'Status', 'Submitted Date', 'Risk Score']]
        
        for app in recent_apps:
            data.append([
                str(app.id),
                app.organization_name,
                app.status.value.replace('_', ' ').title(),
                app.submitted_at.strftime('%Y-%m-%d'),
                f"{app.risk_score:.1f}"
            ])
        
        if len(recent_apps) == 0:
            data.append(['No applications found', '', '', '', ''])
        
        table = Table(data, colWidths=[40, 200, 100, 100, 60])
        table.setStyle(table_style)
        
        elements.append(table)
        
        return elements
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate summary report in Excel format"""
        worksheet = workbook.add_worksheet('Summary')
        
        # Get standardized Excel formats
        formats = self._create_excel_formats(workbook)
        
        # Center the title
        worksheet.merge_range('A1:F1', 'Application Summary Report', formats['title'])
        worksheet.merge_range('A2:F2', f'Period: {start_date.strftime("%d %b %Y")} to {(end_date - timedelta(days=1)).strftime("%d %b %Y")}', formats['subtitle'])
        
        if status_filter:
            worksheet.merge_range('A3:F3', f'Status Filter: {status_filter}', formats['subtitle'])
            current_row = 4
        else:
            current_row = 3
        
        # Status distribution
        current_row += 1
        worksheet.write(current_row, 0, 'Status Distribution', formats['section'])
        current_row += 1
        
        status_counts = defaultdict(int)
        for app in applications:
            status_counts[app.status.value] += 1
        
        worksheet.write(current_row, 0, 'Status', formats['header'])
        worksheet.write(current_row, 1, 'Count', formats['header'])
        
        current_row += 1
        for i, (status, count) in enumerate(status_counts.items()):
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            worksheet.write(current_row, 0, status.replace('_', ' ').title(), format_to_use)
            worksheet.write(current_row, 1, count, format_to_use)
            current_row += 1
        
        # Recent applications
        current_row += 2
        worksheet.write(current_row, 0, 'Recent Applications', formats['section'])
        current_row += 1
        
        # Headers
        columns = ['ID', 'Organization Name', 'Status', 'Submitted Date', 'Risk Score']
        for col, header in enumerate(columns):
            worksheet.write(current_row, col, header, formats['header'])
        
        # Sort by submission date (newest first)
        sorted_apps = sorted(applications, key=lambda x: x.submitted_at, reverse=True)
        
        # Write data with alternating row colors
        current_row += 1
        for i, app in enumerate(sorted_apps[:30]):  # Show top 30
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            
            worksheet.write(current_row, 0, app.id, format_to_use)
            worksheet.write(current_row, 1, app.organization_name, format_to_use)
            worksheet.write(current_row, 2, app.status.value.replace('_', ' ').title(), format_to_use)
            worksheet.write(current_row, 3, app.submitted_at.strftime('%Y-%m-%d'), format_to_use)
            
            # Color-code risk scores
            risk_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#E6E6FA' if i % 2 == 0 else 'white',
                'font_color': 'green' if app.risk_score < 40 else 
                             'orange' if app.risk_score < 70 else 'red'
            })
            
            worksheet.write(current_row, 4, app.risk_score, risk_format)
            current_row += 1
        
        # Auto-adjust column widths
        worksheet.set_column(0, 0, 10)
        worksheet.set_column(1, 1, 40)
        worksheet.set_column(2, 2, 20)
        worksheet.set_column(3, 3, 15)
        worksheet.set_column(4, 4, 12)
        
        # Add a chart for status distribution
        chart = workbook.add_chart({'type': 'pie'})
        
        # Add status data to a separate area for the chart
        chart_data_row = current_row + 2
        worksheet.write(chart_data_row, 0, 'Status', formats['header'])
        worksheet.write(chart_data_row, 1, 'Count', formats['header'])
        
        chart_data_row += 1
        for status, count in status_counts.items():
            worksheet.write(chart_data_row, 0, status.replace('_', ' ').title())
            worksheet.write(chart_data_row, 1, count)
            chart_data_row += 1
        
        chart.add_series({
            'name': 'Status Distribution',
            'categories': f'=Summary!$A${current_row + 3}:$A${chart_data_row}',
            'values': f'=Summary!$B${current_row + 3}:$B${chart_data_row}',
            'data_labels': {'percentage': True}
        })
        
        chart.set_title({'name': 'Application Status Distribution'})
        chart.set_style(10)
        worksheet.insert_chart(current_row + 2, 3, chart, {'x_scale': 1.5, 'y_scale': 1.5})

# -----------------------------------------------------------------------------
# Detailed Report Content
# -----------------------------------------------------------------------------

class DetailedReportContent(ReportContent):
    """Generates content for detailed reports"""
    
    def generate_pdf_content(self, applications):
        elements = []
        styles = getSampleStyleSheet()
        
        # Get standardized styles
        heading_style = self._create_heading_style()
        subheading_style = self._create_subheading_style()
        table_style = self._create_standard_table_style(alternating_colors=False)
        
        # Add header
        elements.append(Paragraph("Application Details", heading_style))
        elements.append(Spacer(1, 12))
        
        # Sort by submission date (newest first)
        sorted_apps = sorted(applications, key=lambda x: x.submitted_at, reverse=True)
        
        # Limit to first 10 applications for PDF
        display_apps = sorted_apps[:10]
        
        if not display_apps:
            elements.append(Paragraph("No applications found for the selected period.", styles['Normal']))
            return elements
        
        # Create detailed info for each application
        for i, app in enumerate(display_apps):
            # Add page break after each application (except the first)
            if i > 0:
                elements.append(PageBreak())
            
            # Application header with ID and name
            app_header = f"Application #{app.id}: {app.organization_name}"
            elements.append(Paragraph(app_header, subheading_style))
            elements.append(Spacer(1, 6))
            
            # Basic info
            basic_info = [
                ['Attribute', 'Value'],
                ['Status', app.status.value.replace('_', ' ').title()],
                ['Acronym', app.acronym or 'N/A'],
                ['Email', app.organization_email],
                ['Phone', app.organization_phone],
                ['Address', app.address],
                ['Submitted Date', app.submitted_at.strftime('%Y-%m-%d %H:%M')],
                ['Last Modified', app.last_modified.strftime('%Y-%m-%d %H:%M') if app.last_modified else 'N/A'],
                ['Risk Score', f"{app.risk_score:.1f}"],
                ['Certificate Number', app.certificate_number or 'Not Issued'],
                ['Certificate Issued Date', app.certificate_issued_at.strftime('%Y-%m-%d') if app.certificate_issued_at else 'N/A']
            ]
            
            # Create enhanced table style with colored background for attribute column
            detail_table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
            
            table = Table(basic_info, colWidths=[150, 350])
            table.setStyle(detail_table_style)
            
            elements.append(table)
            elements.append(Spacer(1, 12))
            
            # Applicant info
            if app.applicant:
                elements.append(Paragraph("Applicant Information", subheading_style))
                elements.append(Spacer(1, 6))
                
                applicant_info = [
                    ['Attribute', 'Value'],
                    ['Name', f"{app.applicant.title} {app.applicant.firstname} {app.applicant.lastname}"],
                    ['Email', app.applicant.email],
                    ['Phone', app.applicant.phonenumber],
                    ['Nationality', app.applicant.nationality],
                    ['ID/Passport', app.applicant.nid_or_passport],
                    ['Gender', app.applicant.gender.value if app.applicant.gender else 'N/A'],
                    ['Date of Birth', app.applicant.date_of_birth.strftime('%Y-%m-%d') if app.applicant.date_of_birth else 'N/A'],
                    ['Civil Status', app.applicant.civil_status.value.replace('_', ' ').title() if app.applicant.civil_status else 'N/A']
                ]
                
                table = Table(applicant_info, colWidths=[150, 350])
                table.setStyle(detail_table_style)
                
                elements.append(table)
            
            # Comments section if available
            if app.comments:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Comments", subheading_style))
                elements.append(Spacer(1, 6))
                
                comment_style = ParagraphStyle(
                    'Comment',
                    parent=styles['Normal'],
                    leftIndent=10,
                    rightIndent=10,
                    borderWidth=1,
                    borderColor=colors.grey,
                    borderPadding=10,
                    backColor=colors.whitesmoke
                )
                
                elements.append(Paragraph(app.comments, comment_style))
        
        # Add a note if there are more applications
        if len(sorted_apps) > 10:
            elements.append(Spacer(1, 24))
            note_style = ParagraphStyle(
                'Note',
                parent=styles['Italic'],
                textColor=colors.darkgrey,
                alignment=1  # Center
            )
            elements.append(Paragraph(f"Showing 10 of {len(sorted_apps)} applications. Download Excel report for complete data.", note_style))
        
        return elements
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate detailed report in Excel format"""
        worksheet = workbook.add_worksheet('Detailed Report')
        
        # Get standardized Excel formats
        formats = self._create_excel_formats(workbook)
        
        # Add title and filters with improved formatting
        worksheet.merge_range('A1:R1', 'Detailed Application Report', formats['title'])
        worksheet.merge_range('A2:R2', f'Period: {start_date.strftime("%d %b %Y")} to {(end_date - timedelta(days=1)).strftime("%d %b %Y")}', formats['subtitle'])
        
        row = 2
        if status_filter:
            worksheet.merge_range('A3:R3', f'Status Filter: {status_filter}', formats['subtitle'])
            row += 1
        
        # Headers
        row += 2
        columns = [
            'ID', 'Organization Name', 'Acronym', 'Email', 'Phone', 'Address',
            'Status', 'Submitted Date', 'Last Modified', 'Risk Score',
            'Certificate Number', 'Certificate Issued Date',
            'Applicant Name', 'Applicant Email', 'Applicant Phone',
            'Nationality', 'Gender', 'Comments'
        ]
        
        for col, header in enumerate(columns):
            worksheet.write(row, col, header, formats['header'])
        
        # Sort by submission date (newest first)
        sorted_apps = sorted(applications, key=lambda x: x.submitted_at, reverse=True)
        
        # Write data with alternating row colors
        row += 1
        for i, app in enumerate(sorted_apps):
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            
            # Determine risk format
            risk_format = formats['high_risk'] if app.risk_score >= 70 else \
                         formats['medium_risk'] if app.risk_score >= 40 else \
                         formats['low_risk']
            
            worksheet.write(row, 0, app.id, format_to_use)
            worksheet.write(row, 1, app.organization_name, format_to_use)
            worksheet.write(row, 2, app.acronym or '', format_to_use)
            worksheet.write(row, 3, app.organization_email, format_to_use)
            worksheet.write(row, 4, app.organization_phone, format_to_use)
            worksheet.write(row, 5, app.address, format_to_use)
            worksheet.write(row, 6, app.status.value.replace('_', ' ').title(), format_to_use)
            worksheet.write(row, 7, app.submitted_at.strftime('%Y-%m-%d'), format_to_use)
            worksheet.write(row, 8, app.last_modified.strftime('%Y-%m-%d') if app.last_modified else '', format_to_use)
            worksheet.write(row, 9, app.risk_score, risk_format)
            worksheet.write(row, 10, app.certificate_number or '', format_to_use)
            worksheet.write(row, 11, app.certificate_issued_at.strftime('%Y-%m-%d') if app.certificate_issued_at else '', format_to_use)
            
            # Applicant info
            if app.applicant:
                worksheet.write(row, 12, f"{app.applicant.firstname} {app.applicant.lastname}", format_to_use)
                worksheet.write(row, 13, app.applicant.email, format_to_use)
                worksheet.write(row, 14, app.applicant.phonenumber, format_to_use)
                worksheet.write(row, 15, app.applicant.nationality, format_to_use)
                worksheet.write(row, 16, app.applicant.gender.value if app.applicant.gender else '', format_to_use)
            else:
                for col in range(12, 17):
                    worksheet.write(row, col, '', format_to_use)
            
            # Use a special format for comments with text wrapping
            comment_format = workbook.add_format({
                'border': 1,
                'text_wrap': True,
                'valign': 'top',
                'bg_color': '#E6E6FA' if i % 2 == 0 else 'white'
            })
            
            worksheet.write(row, 17, app.comments or '', comment_format)
            row += 1
        
        # Auto-adjust column widths
        column_widths = [10, 35, 15, 30, 15, 35, 20, 15, 15, 12, 20, 15, 25, 25, 15, 20, 15, 50]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Add a second sheet with application details in a more readable format
        details_sheet = workbook.add_worksheet('Application Details')
        
        # Add title
        details_sheet.merge_range('A1:E1', 'Detailed Application Information', formats['title'])
        
        # Add applications one by one in a vertical format
        row = 3
        for app in sorted_apps[:20]:  # Limit to 20 applications for readability
            # Application header
            details_sheet.merge_range(f'A{row}:E{row}', f"Application #{app.id}: {app.organization_name}", formats['section'])
            row += 1
            
            # Basic info headers
            details_sheet.write(row, 0, 'Attribute', formats['header'])
            details_sheet.write(row, 1, 'Value', formats['header'])
            details_sheet.merge_range(f'C{row}:E{row}', '', formats['header'])
            row += 1
            
            # Basic info data
            basic_info = [
                ['Status', app.status.value.replace('_', ' ').title()],
                ['Acronym', app.acronym or 'N/A'],
                ['Email', app.organization_email],
                ['Phone', app.organization_phone],
                ['Address', app.address],
                ['Submitted Date', app.submitted_at.strftime('%Y-%m-%d %H:%M')],
                ['Last Modified', app.last_modified.strftime('%Y-%m-%d %H:%M') if app.last_modified else 'N/A'],
                ['Risk Score', f"{app.risk_score:.1f}"],
                ['Certificate Number', app.certificate_number or 'Not Issued'],
                ['Certificate Issued Date', app.certificate_issued_at.strftime('%Y-%m-%d') if app.certificate_issued_at else 'N/A']
            ]
            
            for i, (attr, value) in enumerate(basic_info):
                format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                attr_format = workbook.add_format({
                    'border': 1,
                    'bg_color': '#E6E6FA',
                    'align': 'right',
                    'bold': True
                })
                
                details_sheet.write(row, 0, attr, attr_format)
                details_sheet.write(row, 1, value, format_to_use)
                details_sheet.merge_range(f'C{row}:E{row}', '', format_to_use)
                row += 1
            
            # Applicant info if available
            if app.applicant:
                row += 1
                details_sheet.merge_range(f'A{row}:E{row}', "Applicant Information", formats['section'])
                row += 1
                
                details_sheet.write(row, 0, 'Attribute', formats['header'])
                details_sheet.write(row, 1, 'Value', formats['header'])
                details_sheet.merge_range(f'C{row}:E{row}', '', formats['header'])
                row += 1
                
                applicant_info = [
                    ['Name', f"{app.applicant.title} {app.applicant.firstname} {app.applicant.lastname}"],
                    ['Email', app.applicant.email],
                    ['Phone', app.applicant.phonenumber],
                    ['Nationality', app.applicant.nationality],
                    ['ID/Passport', app.applicant.nid_or_passport],
                    ['Gender', app.applicant.gender.value if app.applicant.gender else 'N/A'],
                    ['Date of Birth', app.applicant.date_of_birth.strftime('%Y-%m-%d') if app.applicant.date_of_birth else 'N/A'],
                    ['Civil Status', app.applicant.civil_status.value.replace('_', ' ').title() if app.applicant.civil_status else 'N/A']
                ]
                
                for i, (attr, value) in enumerate(applicant_info):
                    format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                    attr_format = workbook.add_format({
                        'border': 1,
                        'bg_color': '#E6E6FA',
                        'align': 'right',
                        'bold': True
                    })
                    
                    details_sheet.write(row, 0, attr, attr_format)
                    details_sheet.write(row, 1, value, format_to_use)
                    details_sheet.merge_range(f'C{row}:E{row}', '', format_to_use)
                    row += 1
            
            # Comments if available
            if app.comments:
                row += 1
                details_sheet.merge_range(f'A{row}:E{row}', "Comments", formats['section'])
                row += 1
                
                comment_format = workbook.add_format({
                    'border': 1,
                    'text_wrap': True,
                    'valign': 'top',
                    'align': 'left',
                    'indent': 1
                })
                
                details_sheet.merge_range(f'A{row}:E{row}', app.comments, comment_format)
                row += 3  # Add extra space after comments
            else:
                row += 2  # Add space between applications
        
        # Set column widths for details sheet
        details_sheet.set_column('A:A', 20)
        details_sheet.set_column('B:B', 40)
        details_sheet.set_column('C:E', 15)

# -----------------------------------------------------------------------------
# Analytics Report Content
# -----------------------------------------------------------------------------

class AnalyticsReportContent(ReportContent):
    """Generates content for analytics reports"""
    
    def generate_pdf_content(self, applications):
        elements = []
        styles = getSampleStyleSheet()
        
        # Get standardized styles
        heading_style = self._create_heading_style()
        subheading_style = self._create_subheading_style()
        table_style = self._create_standard_table_style()
        
        # Add header
        elements.append(Paragraph("Analytics Report", heading_style))
        elements.append(Spacer(1, 12))
        
        # Basic statistics
        total = len(applications)
        
        if total == 0:
            elements.append(Paragraph("No applications found in the selected period.", styles['Normal']))
            return elements
        
        status_counts = defaultdict(int)
        risk_scores = []
        submission_dates = []
        
        for app in applications:
            status_counts[app.status.value] += 1
            risk_scores.append(app.risk_score)
            submission_dates.append(app.submitted_at)
        
        # Overall statistics
        elements.append(Paragraph("Overall Statistics", subheading_style))
        elements.append(Spacer(1, 6))
        
        data = [['Metric', 'Value']]
        data.append(['Total Applications', total])
        data.append(['Average Risk Score', f"{sum(risk_scores)/total:.2f}" if risk_scores else "N/A"])
        data.append(['Highest Risk Score', f"{max(risk_scores):.2f}" if risk_scores else "N/A"])
        data.append(['Lowest Risk Score', f"{min(risk_scores):.2f}" if risk_scores else "N/A"])
        
        table = Table(data, colWidths=[200, 250])
        table.setStyle(table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 16))
        
        # Status distribution
        elements.append(Paragraph("Status Distribution", subheading_style))
        elements.append(Spacer(1, 6))
        
        data = [['Status', 'Count', 'Percentage']]
        for status, count in status_counts.items():
            data.append([
                status.replace('_', ' ').title(),
                count,
                f"{(count/total)*100:.1f}%"
            ])
        
        table = Table(data, colWidths=[200, 125, 125])
        table.setStyle(table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # Create a chart for status distribution
        fig, ax = plt.subplots(figsize=(7, 5))
        statuses = [s.replace('_', ' ').title() for s in status_counts.keys()]
        counts = list(status_counts.values())
        
        ax.bar(statuses, counts, color='skyblue')
        ax.set_title('Application Status Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('Status', fontsize=12)
        ax.set_ylabel('Count', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Add grid lines and styling
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Add value labels on top of bars
        for i, v in enumerate(counts):
            ax.text(i, v + 0.5, str(v), ha='center', fontweight='bold')
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300)
        img_buffer.seek(0)
        
        elements.append(Image(img_buffer, width=400, height=300))
        elements.append(Spacer(1, 16))
        
        # Risk score distribution
        if risk_scores:
            elements.append(Paragraph("Risk Score Distribution", subheading_style))
            elements.append(Spacer(1, 6))
            
            # Risk category counts
            risk_categories = {
                'Low Risk (0-39)': len([score for score in risk_scores if score < 40]),
                'Medium Risk (40-69)': len([score for score in risk_scores if 40 <= score < 70]),
                'High Risk (70-100)': len([score for score in risk_scores if score >= 70])
            }
            
            data = [['Risk Category', 'Count', 'Percentage']]
            for category, count in risk_categories.items():
                data.append([
                    category,
                    count,
                    f"{(count/total)*100:.1f}%"
                ])
            
            # Create table with risk-appropriate colors
            table = Table(data, colWidths=[200, 125, 125])
            risk_table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Add risk-specific colors
                ('BACKGROUND', (0, 1), (-1, 1), colors.lightgreen),
                ('BACKGROUND', (0, 2), (-1, 2), colors.lightyellow),
                ('BACKGROUND', (0, 3), (-1, 3), colors.lightpink)
            ])
            
            table.setStyle(risk_table_style)
            elements.append(table)
            elements.append(Spacer(1, 12))
            
            # Histogram of risk scores
            fig, ax = plt.subplots(figsize=(7, 5))
            
            # Enhanced histogram with KDE
            sns.histplot(risk_scores, bins=10, kde=True, color='skyblue', edgecolor='black', ax=ax)
            ax.set_title('Risk Score Distribution', fontsize=14, fontweight='bold')
            ax.set_xlabel('Risk Score', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            
            # Add grid lines and styling
            ax.grid(axis='y', linestyle='--', alpha=0.7)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Add vertical lines for risk categories
            ax.axvline(x=40, color='green', linestyle='--', label='Low/Medium Threshold')
            ax.axvline(x=70, color='red', linestyle='--', label='Medium/High Threshold')
            ax.legend()
            
            plt.tight_layout()
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300)
            img_buffer.seek(0)
            
            elements.append(Image(img_buffer, width=400, height=300))
            elements.append(Spacer(1, 16))
            
            # Monthly trend analysis
            elements.append(Paragraph("Monthly Application Trend", subheading_style))
            elements.append(Spacer(1, 6))
            
            # Group by month
            month_data = defaultdict(int)
            for date in submission_dates:
                month_key = date.strftime('%Y-%m')
                month_data[month_key] += 1
            
            # Sort by month
            sorted_months = sorted(month_data.items())
            
            if sorted_months:
                # Create line chart of monthly trends
                fig, ax = plt.subplots(figsize=(8, 5))
                
                months = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m, _ in sorted_months]
                counts = [count for _, count in sorted_months]
                
                ax.plot(months, counts, marker='o', linestyle='-', linewidth=2, markersize=8, color='blue')
                
                ax.set_title('Monthly Application Submissions', fontsize=14, fontweight='bold')
                ax.set_xlabel('Month', fontsize=12)
                ax.set_ylabel('Number of Applications', fontsize=12)
                
                # Add grid lines and styling
                ax.grid(axis='y', linestyle='--', alpha=0.7)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                
                # Add value labels
                for i, v in enumerate(counts):
                    ax.text(i, v + 0.3, str(v), ha='center', fontweight='bold')
                
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png', dpi=300)
                img_buffer.seek(0)
                
                elements.append(Image(img_buffer, width=450, height=300))
        
        return elements
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate analytics report in Excel format"""
        worksheet = workbook.add_worksheet('Analytics')
        
        # Get standardized Excel formats
        formats = self._create_excel_formats(workbook)
        
        # Add title and filters
        worksheet.merge_range('A1:F1', 'Analytics Report', formats['title'])
        worksheet.merge_range('A2:F2', f'Period: {start_date.strftime("%d %b %Y")} to {(end_date - timedelta(days=1)).strftime("%d %b %Y")}', formats['subtitle'])
        
        row = 2
        if status_filter:
            worksheet.merge_range('A3:F3', f'Status Filter: {status_filter}', formats['subtitle'])
            row += 1
        
        if not applications:
            worksheet.write(row + 2, 0, 'No applications found in the selected period.')
            return
        
        # Overall statistics
        row += 2
        worksheet.write(row, 0, 'Overall Statistics', formats['section'])
        row += 1
        
        # Headers
        worksheet.write(row, 0, 'Metric', formats['header'])
        worksheet.write(row, 1, 'Value', formats['header'])
        
        # Calculate statistics
        total = len(applications)
        risk_scores = [app.risk_score for app in applications]
        avg_risk = sum(risk_scores) / total if risk_scores else 0
        
        # Write data with alternating row colors
        metrics = [
            ('Total Applications', total),
            ('Average Risk Score', f"{avg_risk:.2f}"),
            ('Highest Risk Score', f"{max(risk_scores):.2f}" if risk_scores else 'N/A'),
            ('Lowest Risk Score', f"{min(risk_scores):.2f}" if risk_scores else 'N/A')
        ]
        
        row += 1
        for i, (metric, value) in enumerate(metrics):
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            worksheet.write(row, 0, metric, format_to_use)
            worksheet.write(row, 1, value, format_to_use)
            row += 1
        
        # Status distribution
        row += 2
        worksheet.write(row, 0, 'Status Distribution', formats['section'])
        row += 1
        
        # Headers
        worksheet.write(row, 0, 'Status', formats['header'])
        worksheet.write(row, 1, 'Count', formats['header'])
        worksheet.write(row, 2, 'Percentage', formats['header'])
        
        # Calculate status counts
        status_counts = defaultdict(int)
        for app in applications:
            status_counts[app.status.value] += 1
        
        # Write data
        row += 1
        status_row_start = row
        for i, (status, count) in enumerate(status_counts.items()):
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            worksheet.write(row, 0, status.replace('_', ' ').title(), format_to_use)
            worksheet.write(row, 1, count, format_to_use)
            worksheet.write(row, 2, f"{(count/total)*100:.1f}%", format_to_use)
            row += 1
        status_row_end = row - 1
        
        # Risk score distribution
        row += 2
        worksheet.write(row, 0, 'Risk Score Distribution', formats['section'])
        row += 1
        
        # Headers
        worksheet.write(row, 0, 'Risk Category', formats['header'])
        worksheet.write(row, 1, 'Count', formats['header'])
        worksheet.write(row, 2, 'Percentage', formats['header'])
        
        # Calculate risk categories
        risk_categories = {
            'Low Risk (0-39)': len([app for app in applications if app.risk_score < 40]),
            'Medium Risk (40-69)': len([app for app in applications if 40 <= app.risk_score < 70]),
            'High Risk (70-100)': len([app for app in applications if app.risk_score >= 70])
        }
        
        # Write data
        row += 1
        risk_row_start = row
        risk_formats = [formats['low_risk'], formats['medium_risk'], formats['high_risk']]
        for i, (category, count) in enumerate(risk_categories.items()):
            worksheet.write(row, 0, category, risk_formats[i])
            worksheet.write(row, 1, count, risk_formats[i])
            worksheet.write(row, 2, f"{(count/total)*100:.1f}%", risk_formats[i])
            row += 1
        risk_row_end = row - 1
        
        # Monthly trend data
        row += 2
        worksheet.write(row, 0, 'Monthly Application Trends', formats['section'])
        row += 1
        
        # Group by month
        month_data = defaultdict(int)
        for app in applications:
            month_key = app.submitted_at.strftime('%Y-%m')
            month_data[month_key] += 1
        
        # Sort by month
        sorted_months = sorted(month_data.items())
        
        # Headers
        worksheet.write(row, 0, 'Month', formats['header'])
        worksheet.write(row, 1, 'Applications', formats['header'])
        
        # Write data
        row += 1
        month_row_start = row
        for i, (month_key, count) in enumerate(sorted_months):
            format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
            year, month = month_key.split('-')
            month_name = datetime(int(year), int(month), 1).strftime('%b %Y')
            worksheet.write(row, 0, month_name, format_to_use)
            worksheet.write(row, 1, count, format_to_use)
            row += 1
        month_row_end = row - 1
        
        # Add charts
        
        # 1. Status Distribution Pie Chart
        chart1 = workbook.add_chart({'type': 'pie'})
        chart1.add_series({
            'name': 'Status Distribution',
            'categories': f'=Analytics!$A${status_row_start}:$A${status_row_end}',
            'values': f'=Analytics!$B${status_row_start}:$B${status_row_end}',
            'data_labels': {'percentage': True, 'category': True, 'separator': '\n'}
        })
        chart1.set_title({'name': 'Application Status Distribution'})
        chart1.set_style(10)
        
        # 2. Risk Distribution Pie Chart
        chart2 = workbook.add_chart({'type': 'pie'})
        chart2.add_series({
            'name': 'Risk Distribution',
            'categories': f'=Analytics!$A${risk_row_start}:$A${risk_row_end}',
            'values': f'=Analytics!$B${risk_row_start}:$B${risk_row_end}',
            'data_labels': {'percentage': True, 'category': True, 'separator': '\n'},
            'points': [
                {'fill': {'color': '#CCFFCC'}},  # Low risk - light green
                {'fill': {'color': '#FFFFCC'}},  # Medium risk - light yellow
                {'fill': {'color': '#FFCCCC'}}   # High risk - light red
            ]
        })
        chart2.set_title({'name': 'Risk Score Distribution'})
        chart2.set_style(10)
        
        # 3. Monthly Trend Line Chart
        if sorted_months:
            chart3 = workbook.add_chart({'type': 'line'})
            chart3.add_series({
                'name': 'Monthly Applications',
                'categories': f'=Analytics!$A${month_row_start}:$A${month_row_end}',
                'values': f'=Analytics!$B${month_row_start}:$B${month_row_end}',
                'marker': {'type': 'circle', 'size': 8},
                'data_labels': {'value': True}
            })
            chart3.set_title({'name': 'Monthly Application Trends'})
            chart3.set_x_axis({'name': 'Month'})
            chart3.set_y_axis({'name': 'Number of Applications'})
            chart3.set_style(42)
            
            # Insert charts
            worksheet.insert_chart('E5', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
            worksheet.insert_chart('E22', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
            worksheet.insert_chart('E39', chart3, {'x_scale': 1.5, 'y_scale': 1.5})
        else:
            # Insert just the first two charts if no monthly data
            worksheet.insert_chart('E5', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
            worksheet.insert_chart('E22', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # Auto-adjust column widths
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        
        # Add a Risk Metrics sheet
        risk_sheet = workbook.add_worksheet('Risk Metrics')
        
        # Add title
        risk_sheet.merge_range('A1:F1', 'Risk Score Analysis', formats['title'])
        
        # Headers for risk score data
        row = 3
        risk_sheet.write(row, 0, 'ID', formats['header'])
        risk_sheet.write(row, 1, 'Organization', formats['header'])
        risk_sheet.write(row, 2, 'Risk Score', formats['header'])
        risk_sheet.write(row, 3, 'Risk Category', formats['header'])
        risk_sheet.write(row, 4, 'Status', formats['header'])
        
        # Sort applications by risk score (highest first)
        sorted_by_risk = sorted(applications, key=lambda x: x.risk_score, reverse=True)
        
        # Write data
        row += 1
        for i, app in enumerate(sorted_by_risk):
            risk_category = 'High Risk' if app.risk_score >= 70 else 'Medium Risk' if app.risk_score >= 40 else 'Low Risk'
            risk_format = formats['high_risk'] if app.risk_score >= 70 else formats['medium_risk'] if app.risk_score >= 40 else formats['low_risk']
            
            risk_sheet.write(row, 0, app.id, formats['cell'])
            risk_sheet.write(row, 1, app.organization_name, formats['cell'])
            risk_sheet.write(row, 2, app.risk_score, risk_format)
            risk_sheet.write(row, 3, risk_category, risk_format)
            risk_sheet.write(row, 4, app.status.value.replace('_', ' ').title(), formats['cell'])
            row += 1
        
        # Add a histogram of risk scores
        histogram_chart = workbook.add_chart({'type': 'column'})
        
        # Create risk score histogram data
        risk_ranges = ['0-10', '11-20', '21-30', '31-40', '41-50', '51-60', '61-70', '71-80', '81-90', '91-100']
        risk_bins = [0] * 10
        
        for app in applications:
            bin_index = min(int(app.risk_score // 10), 9)  # Handle score of 100
            risk_bins[bin_index] += 1
        
        # Write histogram data
        histogram_row = row + 2
        risk_sheet.write(histogram_row, 0, 'Risk Range', formats['header'])
        risk_sheet.write(histogram_row, 1, 'Count', formats['header'])
        
        histogram_row += 1
        histogram_start = histogram_row
        for i, (range_label, count) in enumerate(zip(risk_ranges, risk_bins)):
            risk_sheet.write(histogram_row, 0, range_label, formats['cell'])
            risk_sheet.write(histogram_row, 1, count, formats['cell'])
            histogram_row += 1
        histogram_end = histogram_row - 1
        
        # Add histogram chart
        histogram_chart.add_series({
            'name': 'Risk Score Distribution',
            'categories': f'=Risk Metrics!$A${histogram_start}:$A${histogram_end}',
            'values': f'=Risk Metrics!$B${histogram_start}:$B${histogram_end}',
            'data_labels': {'value': True},
            'gradient': {'colors': ['#CCFFCC', '#FFCCCC']}
        })
        
        histogram_chart.set_title({'name': 'Risk Score Distribution'})
        histogram_chart.set_x_axis({'name': 'Risk Score Range'})
        histogram_chart.set_y_axis({'name': 'Number of Applications'})
        histogram_chart.set_style(42)
        
        risk_sheet.insert_chart('D3', histogram_chart, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # Set column widths
        risk_sheet.set_column('A:A', 10)
        risk_sheet.set_column('B:B', 40)
        risk_sheet.set_column('C:C', 15)
        risk_sheet.set_column('D:D', 15)
        risk_sheet.set_column('E:E', 20)

# -----------------------------------------------------------------------------
# Compliance Report Content
# -----------------------------------------------------------------------------

class ComplianceReportContent(ReportContent):
    """Generates content for compliance reports"""
    
    def generate_pdf_content(self, applications):
        elements = []
        styles = getSampleStyleSheet()
        
        # Get standardized styles
        heading_style = self._create_heading_style()
        subheading_style = self._create_subheading_style()
        
        # Add header
        elements.append(Paragraph("Compliance Report", heading_style))
        elements.append(Spacer(1, 12))
        
        # Basic statistics
        total = len(applications)
        
        if total == 0:
            elements.append(Paragraph("No applications found in the selected period.", styles['Normal']))
            return elements
        
        # Group by risk category
        high_risk = [app for app in applications if app.risk_score >= 70]
        medium_risk = [app for app in applications if 40 <= app.risk_score < 70]
        low_risk = [app for app in applications if app.risk_score < 40]
        
        # Overall compliance statistics
        elements.append(Paragraph("Risk Assessment Overview", subheading_style))
        elements.append(Spacer(1, 6))
        
        # Create enhanced table style with risk-appropriate colors
        risk_table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Risk-specific colors
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightpink),
            ('BACKGROUND', (0, 2), (-1, 2), colors.lightyellow),
            ('BACKGROUND', (0, 3), (-1, 3), colors.lightgreen)
        ])
        
        data = [['Risk Category', 'Count', 'Percentage']]
        data.append(['High Risk (70-100)', len(high_risk), f"{(len(high_risk)/total)*100:.1f}%"])
        data.append(['Medium Risk (40-69)', len(medium_risk), f"{(len(medium_risk)/total)*100:.1f}%"])
        data.append(['Low Risk (0-39)', len(low_risk), f"{(len(low_risk)/total)*100:.1f}%"])
        
        table = Table(data, colWidths=[200, 125, 125])
        table.setStyle(risk_table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 16))
        
        # Risk distribution pie chart
        fig, ax = plt.subplots(figsize=(7, 5))
        
        labels = ['High Risk', 'Medium Risk', 'Low Risk']
        sizes = [len(high_risk), len(medium_risk), len(low_risk)]
        colors = ['#FF9999', '#FFCC99', '#99CC99']
        explode = (0.1, 0, 0)  # Explode high risk slice
        
        wedges, texts, autotexts = ax.pie(
            sizes, 
            explode=explode, 
            labels=labels, 
            colors=colors,
            autopct='%1.1f%%',
            shadow=True, 
            startangle=90,
            textprops={'fontsize': 12, 'fontweight': 'bold'}
        )
        
        # Equal aspect ratio ensures that pie is drawn as a circle
        ax.axis('equal')
        ax.set_title('Risk Distribution', fontsize=14, fontweight='bold')
        
        # Set text color to ensure readability
        for text in texts:
            text.set_color('black')
        for autotext in autotexts:
            autotext.set_color('black')
            
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300)
        img_buffer.seek(0)
        
        elements.append(Image(img_buffer, width=350, height=270))
        elements.append(Spacer(1, 16))
        
        # High risk applications
        if high_risk:
            elements.append(Paragraph("High Risk Applications", subheading_style))
            elements.append(Spacer(1, 6))
            
            high_risk_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ])
            
            # Sort high risk applications by risk score (highest first)
            sorted_high_risk = sorted(high_risk, key=lambda x: x.risk_score, reverse=True)
            
            data = [['ID', 'Organization', 'Risk Score', 'Status', 'Submitted Date']]
            for app in sorted_high_risk[:10]:  # Limit to 10 for readability
                data.append([
                    str(app.id),
                    app.organization_name,
                    f"{app.risk_score:.1f}",
                    app.status.value.replace('_', ' ').title(),
                    app.submitted_at.strftime('%Y-%m-%d')
                ])
            
            table = Table(data, colWidths=[40, 200, 70, 100, 90])
            table.setStyle(high_risk_style)
            
            elements.append(table)
            
            # Add note if more than 10 high risk applications
            if len(high_risk) > 10:
                note_style = ParagraphStyle(
                    'Note',
                    parent=styles['Italic'],
                    textColor=colors.darkgrey,
                    fontSize=9,
                    alignment=1  # Center
                )
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"Showing 10 of {len(high_risk)} high risk applications.", note_style))
            
            elements.append(Spacer(1, 16))
        
        # Success rate by risk category
        elements.append(Paragraph("Approval Rate by Risk Category", subheading_style))
        elements.append(Spacer(1, 6))
        
        high_approved = len([app for app in high_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        medium_approved = len([app for app in medium_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        low_approved = len([app for app in low_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        
        data = [['Risk Category', 'Total', 'Approved', 'Approval Rate']]
        data.append([
            'High Risk (70-100)', 
            len(high_risk), 
            high_approved, 
            f"{(high_approved/len(high_risk))*100:.1f}%" if high_risk else "N/A"
        ])
        data.append([
            'Medium Risk (40-69)', 
            len(medium_risk), 
            medium_approved, 
            f"{(medium_approved/len(medium_risk))*100:.1f}%" if medium_risk else "N/A"
        ])
        data.append([
            'Low Risk (0-39)', 
            len(low_risk), 
            low_approved, 
            f"{(low_approved/len(low_risk))*100:.1f}%" if low_risk else "N/A"
        ])
        
        table = Table(data, colWidths=[150, 100, 100, 100])
        table.setStyle(risk_table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 16))
        
        # Bar chart of approval rates
        fig, ax = plt.subplots(figsize=(7, 5))
        
        categories = ['High Risk', 'Medium Risk', 'Low Risk']
        approval_rates = [
            (high_approved/len(high_risk))*100 if high_risk else 0,
            (medium_approved/len(medium_risk))*100 if medium_risk else 0,
            (low_approved/len(low_risk))*100 if low_risk else 0
        ]
        
        bar_colors = ['#FF9999', '#FFCC99', '#99CC99']
        
        bars = ax.bar(categories, approval_rates, color=bar_colors)
        ax.set_title('Approval Rate by Risk Category', fontsize=14, fontweight='bold')
        ax.set_xlabel('Risk Category', fontsize=12)
        ax.set_ylabel('Approval Rate (%)', fontsize=12)
        ax.set_ylim(0, 100)
        
        # Add grid lines and styling
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Add data labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2., 
                height + 2,
                f'{height:.1f}%',
                ha='center', 
                va='bottom',
                fontweight='bold'
            )
            
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300)
        img_buffer.seek(0)
        
        elements.append(Image(img_buffer, width=400, height=300))
        
        return elements
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate compliance report in Excel format"""
        worksheet = workbook.add_worksheet('Compliance')
        
        # Get standardized Excel formats
        formats = self._create_excel_formats(workbook)
        
        # Add title and filters
        worksheet.merge_range('A1:E1', 'Compliance Report', formats['title'])
        worksheet.merge_range('A2:E2', f'Period: {start_date.strftime("%d %b %Y")} to {(end_date - timedelta(days=1)).strftime("%d %b %Y")}', formats['subtitle'])
        
        row = 2
        if status_filter:
            worksheet.merge_range('A3:E3', f'Status Filter: {status_filter}', formats['subtitle'])
            row += 1
        
        if not applications:
            worksheet.write(row + 2, 0, 'No applications found in the selected period.')
            return
        
        # Risk assessment overview
        row += 2
        worksheet.write(row, 0, 'Risk Assessment Overview', formats['section'])
        row += 1
        
        # Group by risk category
        high_risk = [app for app in applications if app.risk_score >= 70]
        medium_risk = [app for app in applications if 40 <= app.risk_score < 70]
        low_risk = [app for app in applications if app.risk_score < 40]
        total = len(applications)
        
        # Headers
        worksheet.write(row, 0, 'Risk Category', formats['header'])
        worksheet.write(row, 1, 'Count', formats['header'])
        worksheet.write(row, 2, 'Percentage', formats['header'])
        
        # Write data with color coding
        row += 1
        risk_overview_start = row
        
        worksheet.write(row, 0, 'High Risk (70-100)', formats['high_risk'])
        worksheet.write(row, 1, len(high_risk), formats['high_risk'])
        worksheet.write(row, 2, f"{(len(high_risk)/total)*100:.1f}%" if total > 0 else "0.0%", formats['high_risk'])
        row += 1
        
        worksheet.write(row, 0, 'Medium Risk (40-69)', formats['medium_risk'])
        worksheet.write(row, 1, len(medium_risk), formats['medium_risk'])
        worksheet.write(row, 2, f"{(len(medium_risk)/total)*100:.1f}%" if total > 0 else "0.0%", formats['medium_risk'])
        row += 1
        
        worksheet.write(row, 0, 'Low Risk (0-39)', formats['low_risk'])
        worksheet.write(row, 1, len(low_risk), formats['low_risk'])
        worksheet.write(row, 2, f"{(len(low_risk)/total)*100:.1f}%" if total > 0 else "0.0%", formats['low_risk'])
        row += 1
        
        risk_overview_end = row - 1
        
        # High risk applications detail
        if high_risk:
            row += 2
            worksheet.write(row, 0, 'High Risk Applications', formats['section'])
            row += 1
            
            # Headers
            columns = ['ID', 'Organization Name', 'Risk Score', 'Status', 'Submitted Date', 'Comments']
            for col, header in enumerate(columns):
                worksheet.write(row, col, header, formats['header'])
            
            # Sort by risk score (highest first)
            sorted_apps = sorted(high_risk, key=lambda x: x.risk_score, reverse=True)
            
            # Write data with high risk formatting
            row += 1
            for app in sorted_apps:
                worksheet.write(row, 0, app.id, formats['high_risk'])
                worksheet.write(row, 1, app.organization_name, formats['high_risk'])
                worksheet.write(row, 2, app.risk_score, formats['high_risk'])
                worksheet.write(row, 3, app.status.value.replace('_', ' ').title(), formats['high_risk'])
                worksheet.write(row, 4, app.submitted_at.strftime('%Y-%m-%d'), formats['high_risk'])
                
                # Use text wrapping for comments
                comment_format = workbook.add_format({
                    'border': 1,
                    'bg_color': '#FFCCCC',
                    'text_wrap': True,
                    'valign': 'top',
                    'align': 'left'
                })
                
                worksheet.write(row, 5, app.comments or '', comment_format)
                row += 1
        
        # Approval rate by risk category
        row += 2
        worksheet.write(row, 0, 'Approval Rate by Risk Category', formats['section'])
        row += 1
        
        # Headers
        worksheet.write(row, 0, 'Risk Category', formats['header'])
        worksheet.write(row, 1, 'Total', formats['header'])
        worksheet.write(row, 2, 'Approved', formats['header'])
        worksheet.write(row, 3, 'Approval Rate', formats['header'])
        row += 1
        
        approval_data_start = row
        
        high_approved = len([app for app in high_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        medium_approved = len([app for app in medium_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        low_approved = len([app for app in low_risk if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]])
        
        worksheet.write(row, 0, 'High Risk (70-100)', formats['high_risk'])
        worksheet.write(row, 1, len(high_risk), formats['high_risk'])
        worksheet.write(row, 2, high_approved, formats['high_risk'])
        worksheet.write(row, 3, f"{(high_approved/len(high_risk))*100:.1f}%" if high_risk else "N/A", formats['high_risk'])
        row += 1
        
        worksheet.write(row, 0, 'Medium Risk (40-69)', formats['medium_risk'])
        worksheet.write(row, 1, len(medium_risk), formats['medium_risk'])
        worksheet.write(row, 2, medium_approved, formats['medium_risk'])
        worksheet.write(row, 3, f"{(medium_approved/len(medium_risk))*100:.1f}%" if medium_risk else "N/A", formats['medium_risk'])
        row += 1
        
        worksheet.write(row, 0, 'Low Risk (0-39)', formats['low_risk'])
        worksheet.write(row, 1, len(low_risk), formats['low_risk'])
        worksheet.write(row, 2, low_approved, formats['low_risk'])
        worksheet.write(row, 3, f"{(low_approved/len(low_risk))*100:.1f}%" if low_risk else "N/A", formats['low_risk'])
        row += 1
        
        approval_data_end = row - 1
        
        # Add charts
        
        # 1. Risk Distribution Pie Chart
        chart1 = workbook.add_chart({'type': 'pie'})
        chart1.add_series({
            'name': 'Risk Distribution',
            'categories': f'=Compliance!$A${risk_overview_start}:$A${risk_overview_end}',
            'values': f'=Compliance!$B${risk_overview_start}:$B${risk_overview_end}',
            'data_labels': {'percentage': True, 'category': True, 'separator': '\n'},
            'points': [
                {'fill': {'color': '#FFCCCC'}},  # High risk - light red
                {'fill': {'color': '#FFFFCC'}},  # Medium risk - light yellow
                {'fill': {'color': '#CCFFCC'}}   # Low risk - light green
            ]
        })
        chart1.set_title({'name': 'Risk Distribution'})
        chart1.set_style(10)
        
        # 2. Approval Rate Bar Chart
        chart2 = workbook.add_chart({'type': 'column'})
        chart2.add_series({
            'name': 'Approval Rate',
            'categories': f'=Compliance!$A${approval_data_start}:$A${approval_data_end}',
            'values': f'=Compliance!$D${approval_data_start}:$D${approval_data_end}',
            'data_labels': {'value': True, 'num_format': '0.0%'},
            'points': [
                {'fill': {'color': '#FFCCCC'}},  # High risk - light red
                {'fill': {'color': '#FFFFCC'}},  # Medium risk - light yellow
                {'fill': {'color': '#CCFFCC'}}   # Low risk - light green
            ]
        })
        chart2.set_title({'name': 'Approval Rate by Risk Category'})
        chart2.set_y_axis({'name': 'Approval Rate', 'min': 0, 'max': 1, 'num_format': '0%'})
        chart2.set_x_axis({'name': 'Risk Category'})
        chart2.set_style(42)
        
        # Insert charts
        worksheet.insert_chart('G5', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
        worksheet.insert_chart('G22', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # Auto-adjust column widths
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 40)
        
        # Add Risk Analysis Detail sheet
        risk_sheet = workbook.add_worksheet('Risk Analysis')
        
        # Add title
        risk_sheet.merge_range('A1:F1', 'Risk Analysis Detail', formats['title'])
        
        # Add all applications with risk score details
        row = 3
        risk_sheet.write(row, 0, 'All Applications by Risk Score', formats['section'])
        row += 1
        
        # Headers
        columns = ['ID', 'Organization Name', 'Risk Score', 'Risk Category', 'Status', 'Approval']
        for col, header in enumerate(columns):
            risk_sheet.write(row, col, header, formats['header'])
        
        # Sort all applications by risk score (highest first)
        sorted_by_risk = sorted(applications, key=lambda x: x.risk_score, reverse=True)
        
        # Write data
        row += 1
        for app in sorted_by_risk:
            # Determine risk category and format
            risk_category = 'High Risk' if app.risk_score >= 70 else 'Medium Risk' if app.risk_score >= 40 else 'Low Risk'
            risk_format = formats['high_risk'] if app.risk_score >= 70 else formats['medium_risk'] if app.risk_score >= 40 else formats['low_risk']
            
            # Determine if approved
            is_approved = app.status in [ApplicationStatus.APPROVED, ApplicationStatus.CERTIFICATE_ISSUED]
            approval_text = 'Approved' if is_approved else 'Not Approved'
            
            risk_sheet.write(row, 0, app.id, formats['cell'])
            risk_sheet.write(row, 1, app.organization_name, formats['cell'])
            risk_sheet.write(row, 2, app.risk_score, risk_format)
            risk_sheet.write(row, 3, risk_category, risk_format)
            risk_sheet.write(row, 4, app.status.value.replace('_', ' ').title(), formats['cell'])
            
            # Format approval with color
            approval_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#CCFFCC' if is_approved else '#FFCCCC'
            })
            
            risk_sheet.write(row, 5, approval_text, approval_format)
            row += 1
        
        # Set column widths for risk analysis sheet
        risk_sheet.set_column('A:A', 10)
        risk_sheet.set_column('B:B', 40)
        risk_sheet.set_column('C:C', 12)
        risk_sheet.set_column('D:D', 15)
        risk_sheet.set_column('E:E', 20)
        risk_sheet.set_column('F:F', 15)

# -----------------------------------------------------------------------------
# Demographic Report Content
# -----------------------------------------------------------------------------

class DemographicReportContent(ReportContent):
    """Generates content for demographic reports"""
    
    def generate_pdf_content(self, applications):
        elements = []
        styles = getSampleStyleSheet()
        
        # Get standardized styles
        heading_style = self._create_heading_style()
        subheading_style = self._create_subheading_style()
        table_style = self._create_standard_table_style()
        
        # Add header
        elements.append(Paragraph("Demographic Report", heading_style))
        elements.append(Spacer(1, 12))
        
        if not applications:
            elements.append(Paragraph("No applications found in the selected period.", styles['Normal']))
            return elements
        
        # Get unique applicants
        applicant_ids = set()
        unique_applications = []
        
        for app in applications:
            if app.applicant_id not in applicant_ids:
                applicant_ids.add(app.applicant_id)
                unique_applications.append(app)
        
        if not unique_applications:
            elements.append(Paragraph("No applicant data found in the selected period.", styles['Normal']))
            return elements
        
        # Gender distribution
        gender_counts = defaultdict(int)
        for app in unique_applications:
            if app.applicant and app.applicant.gender:
                gender_counts[app.applicant.gender.value] += 1
        
        if gender_counts:
            elements.append(Paragraph("Gender Distribution", subheading_style))
            elements.append(Spacer(1, 6))
            
            data = [['Gender', 'Count', 'Percentage']]
            total = sum(gender_counts.values())
            
            for gender, count in gender_counts.items():
                data.append([
                    gender.title(),
                    count,
                    f"{(count/total)*100:.1f}%"
                ])
            
            table = Table(data, colWidths=[150, 125, 125])
            table.setStyle(table_style)
            
            elements.append(table)
            
            # Gender pie chart
            fig, ax = plt.subplots(figsize=(7, 5))
            
            labels = [gender.title() for gender in gender_counts.keys()]
            sizes = list(gender_counts.values())
            colors = sns.color_palette('pastel')[0:len(gender_counts)]
            
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                colors=colors,
                autopct='%1.1f%%',
                shadow=False, 
                startangle=90,
                textprops={'fontsize': 12}
            )
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            ax.axis('equal')
            ax.set_title('Gender Distribution', fontsize=14, fontweight='bold')
            
            # Set text color to ensure readability
            for text in texts:
                text.set_color('black')
            for autotext in autotexts:
                autotext.set_color('black')
                
            plt.tight_layout()
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300)
            img_buffer.seek(0)
            
            elements.append(Spacer(1, 12))
            elements.append(Image(img_buffer, width=350, height=270))
            elements.append(Spacer(1, 16))
        
        # Nationality distribution
        nationality_counts = defaultdict(int)
        for app in unique_applications:
            if app.applicant and app.applicant.nationality:
                nationality_counts[app.applicant.nationality] += 1
        
        if nationality_counts:
            elements.append(Paragraph("Nationality Distribution", subheading_style))
            elements.append(Spacer(1, 6))
            
            # Sort by count (descending)
            sorted_nationalities = sorted(nationality_counts.items(), key=lambda x: x[1], reverse=True)
            
            data = [['Nationality', 'Count', 'Percentage']]
            total = sum(nationality_counts.values())
            
            # Top 10 nationalities
            for nationality, count in sorted_nationalities[:10]:
                data.append([
                    nationality,
                    count,
                    f"{(count/total)*100:.1f}%"
                ])
            
            # Add "Others" category if there are more than 10 nationalities
            if len(sorted_nationalities) > 10:
                others_count = sum(count for _, count in sorted_nationalities[10:])
                data.append([
                    'Others',
                    others_count,
                    f"{(others_count/total)*100:.1f}%"
                ])
            
            table = Table(data, colWidths=[150, 125, 125])
            table.setStyle(table_style)
            
            elements.append(table)
            
            # Horizontal bar chart for nationalities
            if sorted_nationalities:
                fig, ax = plt.subplots(figsize=(8, 5))
                
                # Limit to top 10 for visualization
                top_nationalities = sorted_nationalities[:10]
                
                nationalities = [nat for nat, _ in top_nationalities]
                counts = [count for _, count in top_nationalities]
                
                # Reverse lists for bottom-to-top display
                nationalities.reverse()
                counts.reverse()
                
                # Create horizontal bar chart
                bars = ax.barh(nationalities, counts, color=sns.color_palette('husl', len(top_nationalities)))
                
                ax.set_title('Top 10 Nationalities', fontsize=14, fontweight='bold')
                ax.set_xlabel('Number of Applicants', fontsize=12)
                
                # Remove y-axis label as it's self-explanatory
                ax.set_ylabel('')
                
                # Add grid lines and styling
                ax.grid(axis='x', linestyle='--', alpha=0.7)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                
                # Add data labels
                for i, bar in enumerate(bars):
                    width = bar.get_width()
                    percentage = (width / total) * 100
                    ax.text(
                        width + 0.3, 
                        bar.get_y() + bar.get_height()/2,
                        f'{width} ({percentage:.1f}%)',
                        va='center',
                        fontweight='bold'
                    )
                
                plt.tight_layout()
                
                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png', dpi=300)
                img_buffer.seek(0)
                
                elements.append(Spacer(1, 12))
                elements.append(Image(img_buffer, width=400, height=300))
                elements.append(Spacer(1, 16))
        
        # Age distribution
        current_year = datetime.utcnow().year
        age_groups = defaultdict(int)
        
        for app in unique_applications:
            if app.applicant and app.applicant.date_of_birth:
                age = current_year - app.applicant.date_of_birth.year
                if age < 25:
                    age_groups['Under 25'] += 1
                elif age < 35:
                    age_groups['25-34'] += 1
                elif age < 45:
                    age_groups['35-44'] += 1
                elif age < 55:
                    age_groups['45-54'] += 1
                else:
                    age_groups['55 and Above'] += 1
        
        if age_groups:
            elements.append(Paragraph("Age Distribution", subheading_style))
            elements.append(Spacer(1, 6))
            
            data = [['Age Group', 'Count', 'Percentage']]
            total = sum(age_groups.values())
            
            # Ensure age groups are in order
            age_order = ['Under 25', '25-34', '35-44', '45-54', '55 and Above']
            
            for age_group in age_order:
                count = age_groups.get(age_group, 0)
                data.append([
                    age_group,
                    count,
                    f"{(count/total)*100:.1f}%" if total > 0 else "0.0%"
                ])
            
            table = Table(data, colWidths=[150, 125, 125])
            table.setStyle(table_style)
            
            elements.append(table)
            
            # Age distribution bar chart
            fig, ax = plt.subplots(figsize=(8, 5))
            
            age_labels = age_order
            age_counts = [age_groups.get(group, 0) for group in age_order]
            
            # Create bar chart with a pleasant color palette
            bars = ax.bar(age_labels, age_counts, color=sns.color_palette('viridis', len(age_labels)))
            
            ax.set_title('Age Distribution', fontsize=14, fontweight='bold')
            ax.set_xlabel('Age Group', fontsize=12)
            ax.set_ylabel('Number of Applicants', fontsize=12)
            
            # Add grid lines and styling
            ax.grid(axis='y', linestyle='--', alpha=0.7)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Add data labels
            for i, bar in enumerate(bars):
                height = bar.get_height()
                percentage = (height / total) * 100
                ax.text(
                    bar.get_x() + bar.get_width()/2., 
                    height + 0.3,
                    f'{height} ({percentage:.1f}%)',
                    ha='center',
                    fontweight='bold'
                )
            
            plt.tight_layout()
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300)
            img_buffer.seek(0)
            
            elements.append(Spacer(1, 12))
            elements.append(Image(img_buffer, width=400, height=300))
        
        return elements
    
    def generate_excel_content(self, workbook, applications, start_date, end_date, status_filter):
        """Generate demographic report in Excel format"""
        worksheet = workbook.add_worksheet('Demographics')
        
        # Get standardized Excel formats
        formats = self._create_excel_formats(workbook)
        
        # Add title and filters
        worksheet.merge_range('A1:F1', 'Demographic Report', formats['title'])
        worksheet.merge_range('A2:F2', f'Period: {start_date.strftime("%d %b %Y")} to {(end_date - timedelta(days=1)).strftime("%d %b %Y")}', formats['subtitle'])
        
        row = 2
        if status_filter:
            worksheet.merge_range('A3:F3', f'Status Filter: {status_filter}', formats['subtitle'])
            row += 1
        
        if not applications:
            worksheet.write(row + 2, 0, 'No applications found in the selected period.')
            return
        
        # Get unique applicants
        applicant_ids = set()
        unique_applications = []
        
        for app in applications:
            if app.applicant_id not in applicant_ids and app.applicant:
                applicant_ids.add(app.applicant_id)
                unique_applications.append(app)
        
        if not unique_applications:
            worksheet.write(row + 2, 0, 'No applicant data found in the selected period.')
            return
        
        # Gender distribution
        row += 2
        worksheet.write(row, 0, 'Gender Distribution', formats['section'])
        row += 1
        
        gender_counts = defaultdict(int)
        for app in unique_applications:
            if app.applicant and app.applicant.gender:
                gender_counts[app.applicant.gender.value] += 1
        
        if gender_counts:
            # Headers
            worksheet.write(row, 0, 'Gender', formats['header'])
            worksheet.write(row, 1, 'Count', formats['header'])
            worksheet.write(row, 2, 'Percentage', formats['header'])
            
            # Calculate total
            total = sum(gender_counts.values())
            
            # Write data
            row += 1
            gender_row_start = row
            for i, (gender, count) in enumerate(gender_counts.items()):
                format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                worksheet.write(row, 0, gender.title(), format_to_use)
                worksheet.write(row, 1, count, format_to_use)
                worksheet.write(row, 2, f"{(count/total)*100:.1f}%", format_to_use)
                row += 1
            gender_row_end = row - 1
        else:
            worksheet.write(row, 0, 'No gender data available.')
            row += 1
        
        # Nationality distribution
        row += 2
        worksheet.write(row, 0, 'Nationality Distribution', formats['section'])
        row += 1
        
        nationality_counts = defaultdict(int)
        for app in unique_applications:
            if app.applicant and app.applicant.nationality:
                nationality_counts[app.applicant.nationality] += 1
        
        if nationality_counts:
            # Headers
            worksheet.write(row, 0, 'Nationality', formats['header'])
            worksheet.write(row, 1, 'Count', formats['header'])
            worksheet.write(row, 2, 'Percentage', formats['header'])
            
            # Calculate total
            total = sum(nationality_counts.values())
            
            # Sort by count (descending)
            sorted_nationalities = sorted(nationality_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Write data
            row += 1
            nationality_row_start = row
            for i, (nationality, count) in enumerate(sorted_nationalities):
                format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                worksheet.write(row, 0, nationality, format_to_use)
                worksheet.write(row, 1, count, format_to_use)
                worksheet.write(row, 2, f"{(count/total)*100:.1f}%", format_to_use)
                row += 1
            nationality_row_end = row - 1
        else:
            worksheet.write(row, 0, 'No nationality data available.')
            row += 1
        
        # Age distribution
        row += 2
        worksheet.write(row, 0, 'Age Distribution', formats['section'])
        row += 1
        
        current_year = datetime.utcnow().year
        age_groups = defaultdict(int)
        
        for app in unique_applications:
            if app.applicant and app.applicant.date_of_birth:
                age = current_year - app.applicant.date_of_birth.year
                if age < 25:
                    age_groups['Under 25'] += 1
                elif age < 35:
                    age_groups['25-34'] += 1
                elif age < 45:
                    age_groups['35-44'] += 1
                elif age < 55:
                    age_groups['45-54'] += 1
                else:
                    age_groups['55 and Above'] += 1
        
        if age_groups:
            # Headers
            worksheet.write(row, 0, 'Age Group', formats['header'])
            worksheet.write(row, 1, 'Count', formats['header'])
            worksheet.write(row, 2, 'Percentage', formats['header'])
            
            # Calculate total
            total = sum(age_groups.values())
            
            # Write data in age order
            row += 1
            age_row_start = row
            age_order = ['Under 25', '25-34', '35-44', '45-54', '55 and Above']
            
            for i, age_group in enumerate(age_order):
                count = age_groups.get(age_group, 0)
                format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                worksheet.write(row, 0, age_group, format_to_use)
                worksheet.write(row, 1, count, format_to_use)
                worksheet.write(row, 2, f"{(count/total)*100:.1f}%" if total > 0 else "0.0%", format_to_use)
                row += 1
            age_row_end = row - 1
        else:
            worksheet.write(row, 0, 'No age data available.')
            row += 1
        
        # Add charts
        
        # 1. Gender Pie Chart
        if gender_counts:
            chart1 = workbook.add_chart({'type': 'pie'})
            chart1.add_series({
                'name': 'Gender Distribution',
                'categories': f'=Demographics!$A${gender_row_start}:$A${gender_row_end}',
                'values': f'=Demographics!$B${gender_row_start}:$B${gender_row_end}',
                'data_labels': {'percentage': True, 'category': True, 'separator': '\n'}
            })
            chart1.set_title({'name': 'Gender Distribution'})
            chart1.set_style(10)
            worksheet.insert_chart('E5', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 2. Top Nationalities Bar Chart
        if nationality_counts and len(sorted_nationalities) > 0:
            chart2 = workbook.add_chart({'type': 'bar'})
            
            # Use only top 10 nationalities for the chart
            top_n = min(10, len(sorted_nationalities))
            
            chart2.add_series({
                'name': 'Nationality Distribution',
                'categories': f'=Demographics!$A${nationality_row_start}:$A${nationality_row_start + top_n - 1}',
                'values': f'=Demographics!$B${nationality_row_start}:$B${nationality_row_start + top_n - 1}',
                'data_labels': {'value': True}
            })
            
            chart2.set_title({'name': 'Top 10 Nationalities'})
            chart2.set_x_axis({'name': 'Number of Applicants'})
            chart2.set_y_axis({'name': 'Nationality'})
            chart2.set_style(42)
            worksheet.insert_chart('E22', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 3. Age Distribution Column Chart
        if age_groups:
            chart3 = workbook.add_chart({'type': 'column'})
            chart3.add_series({
                'name': 'Age Distribution',
                'categories': f'=Demographics!$A${age_row_start}:$A${age_row_end}',
                'values': f'=Demographics!$B${age_row_start}:$B${age_row_end}',
                'data_labels': {'value': True}
            })
            
            chart3.set_title({'name': 'Age Distribution'})
            chart3.set_x_axis({'name': 'Age Group'})
            chart3.set_y_axis({'name': 'Number of Applicants'})
            chart3.set_style(42)
            worksheet.insert_chart('E39', chart3, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # Set column widths
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        
        # Add applicant details sheet
        details_sheet = workbook.add_worksheet('Applicant Details')
        
        # Add title
        details_sheet.merge_range('A1:G1', 'Applicant Details', formats['title'])
        
        # Headers
        row = 3
        columns = [
            'ID', 'Name', 'Email', 'Phone', 'Nationality', 'Gender', 
            'Age', 'Age Group', 'Civil Status', 'Organization'
        ]
        
        for col, header in enumerate(columns):
            details_sheet.write(row, col, header, formats['header'])
        
        # Write data
        row += 1
        for i, app in enumerate(unique_applications):
            if app.applicant:
                format_to_use = formats['alt_row'] if i % 2 == 0 else formats['cell']
                
                # Calculate age and age group
                age = None
                age_group = ''
                if app.applicant.date_of_birth:
                    age = current_year - app.applicant.date_of_birth.year
                    if age < 25:
                        age_group = 'Under 25'
                    elif age < 35:
                        age_group = '25-34'
                    elif age < 45:
                        age_group = '35-44'
                    elif age < 55:
                        age_group = '45-54'
                    else:
                        age_group = '55 and Above'
                
                details_sheet.write(row, 0, app.applicant_id, format_to_use)
                details_sheet.write(row, 1, f"{app.applicant.firstname} {app.applicant.lastname}", format_to_use)
                details_sheet.write(row, 2, app.applicant.email, format_to_use)
                details_sheet.write(row, 3, app.applicant.phonenumber, format_to_use)
                details_sheet.write(row, 4, app.applicant.nationality, format_to_use)
                details_sheet.write(row, 5, app.applicant.gender.value if app.applicant.gender else '', format_to_use)
                details_sheet.write(row, 6, age, format_to_use)
                details_sheet.write(row, 7, age_group, format_to_use)
                details_sheet.write(row, 8, app.applicant.civil_status.value.replace('_', ' ').title() if app.applicant.civil_status else '', format_to_use)
                details_sheet.write(row, 9, app.organization_name, format_to_use)
                
                row += 1
        
        # Set column widths for details sheet
        details_sheet.set_column('A:A', 10)
        details_sheet.set_column('B:B', 25)
        details_sheet.set_column('C:C', 30)
        details_sheet.set_column('D:D', 15)
        details_sheet.set_column('E:E', 20)
        details_sheet.set_column('F:F', 15)
        details_sheet.set_column('G:G', 10)
        details_sheet.set_column('H:H', 15)
        details_sheet.set_column('I:I', 15)
        details_sheet.set_column('J:J', 40)