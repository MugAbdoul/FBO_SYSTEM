from app import db
from datetime import datetime
from enum import Enum

class DocumentType(Enum):
    ORGANIZATION_COMMITTEE_NAMES_CVS = "ORGANIZATION_COMMITTEE_NAMES_CVS"
    DISTRICT_CERTIFICATE = "DISTRICT_CERTIFICATE"
    LAND_UPI_PHOTOS = "LAND_UPI_PHOTOS"
    ORGANIZATIONAL_DOCTRINE = "ORGANIZATIONAL_DOCTRINE"
    ANNUAL_ACTION_PLAN = "ANNUAL_ACTION_PLAN"
    PROOF_OF_PAYMENT = "PROOF_OF_PAYMENT"
    PARTNERSHIP_DOCUMENT = "PARTNERSHIP_DOCUMENT"
    PASTOR_DOCUMENT = "PASTOR_DOCUMENT"
    
DOCUMENT_TYPE_INFO = {
    DocumentType.ORGANIZATION_COMMITTEE_NAMES_CVS: {
        'name': 'Names and CVs of Organization Committee',
        'required': True
    },
    DocumentType.DISTRICT_CERTIFICATE: {
        'name': 'District Certificate',
        'required': True
    },
    DocumentType.LAND_UPI_PHOTOS: {
        'name': 'Land UPI and Photos of the Church',
        'required': True
    },
    DocumentType.ORGANIZATIONAL_DOCTRINE: {
        'name': 'Organizational Doctrine',
        'required': True
    },
    DocumentType.ANNUAL_ACTION_PLAN: {
        'name': 'Annual Action Plan',
        'required': True
    },
    DocumentType.PROOF_OF_PAYMENT: {
        'name': 'Proof of Payment',
        'required': True
    },
    DocumentType.PARTNERSHIP_DOCUMENT: {
        'name': 'Partnership Document',
        'required': False
    },
    DocumentType.PASTOR_DOCUMENT: {
        'name': 'Pastor Document (CV, Ordination Letter, etc.)',
        'required': True
    }
}

class SupportingDocument(db.Model):
    __tablename__ = 'supporting_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('organization_applications.id'), nullable=False)
    
    document_type = db.Column(db.Enum(DocumentType), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    document_data = db.Column(db.LargeBinary, nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    required = db.Column(db.Boolean, nullable=False)
    
    # Validation status
    is_valid = db.Column(db.Boolean, default=True)
    validation_comments = db.Column(db.Text, nullable=True)
    validated_by_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    validated_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'document_type': self.document_type.value,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'content_type': self.content_type,
            'file_size': self.file_size,
            'uploaded_at': self.uploaded_at.isoformat(),
            'required': self.required,
            'is_valid': self.is_valid,
            'validation_comments': self.validation_comments,
            'validated_by_id': self.validated_by_id,
            'validated_at': self.validated_at.isoformat() if self.validated_at else None
        }
    
    def __repr__(self):
        return f'<SupportingDocument {self.filename} - {self.document_type.value}>'