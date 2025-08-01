from app import db
from datetime import datetime
from enum import Enum

class ApplicationStatus(Enum):
    PENDING = "PENDING"
    REVIEWING_AGAIN = "REVIEWING_AGAIN"
    FBO_REVIEW = "FBO_REVIEW"
    TRANSFER_TO_DM = "TRANSFER_TO_DM"
    DM_REVIEW = "DM_REVIEW"
    TRANSFER_TO_HOD = "TRANSFER_TO_HOD"
    HOD_REVIEW = "HOD_REVIEW"
    TRANSFER_TO_SG = "TRANSFER_TO_SG"
    SG_REVIEW = "SG_REVIEW"
    TRANSFER_TO_CEO = "TRANSFER_TO_CEO"
    CEO_REVIEW = "CEO_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"

class OrganizationApplication(db.Model):
    __tablename__ = 'organization_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('applicants.id'), nullable=False)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    
    organization_name = db.Column(db.String(200), nullable=False)
    acronym = db.Column(db.String(20), nullable=True)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'), nullable=False)
    organization_email = db.Column(db.String(120), nullable=False)
    organization_phone = db.Column(db.String(15), nullable=False)
    
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Certificate info
    certificate_number = db.Column(db.String(50), unique=True, nullable=True)
    certificate_issued_at = db.Column(db.DateTime, nullable=True)
    qr_code_data = db.Column(db.Text, nullable=True)
    
    # Relationships
    cluster_information = db.relationship('ClusterInformation', backref='application', uselist=False, cascade='all, delete-orphan')
    supporting_documents = db.relationship('SupportingDocument', backref='application', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('ApplicationComment', backref='application', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'applicant_id': self.applicant_id,
            'processed_by_id': self.processed_by_id,
            'organization_name': self.organization_name,
            'acronym': self.acronym,
            'district_id': self.district_id,
            'district': self.district.to_dict() if self.district else None,
            'organization_email': self.organization_email,
            'organization_phone': self.organization_phone,
            'status': self.status.value,
            'submitted_at': self.submitted_at.isoformat(),
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'certificate_number': self.certificate_number,
            'certificate_issued_at': self.certificate_issued_at.isoformat() if self.certificate_issued_at else None,
            'applicant': self.applicant.to_dict() if self.applicant else None,
            'processor': self.processor.to_dict() if self.processor else None,
            'comments': [comment.to_dict() for comment in self.comments]
        }
    
    def __repr__(self):
        return f'<OrganizationApplication {self.organization_name} - {self.status.value}>'