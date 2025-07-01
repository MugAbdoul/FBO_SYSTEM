from app import db
from datetime import datetime
from enum import Enum

class NotificationType(Enum):
    STATUS_CHANGE = "STATUS_CHANGE"
    DOCUMENT_REQUEST = "DOCUMENT_REQUEST"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    REMINDER = "REMINDER"
    CERTIFICATE_READY = "CERTIFICATE_READY"

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('applicants.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    application_id = db.Column(db.Integer, db.ForeignKey('organization_applications.id'), nullable=True)
    
    type = db.Column(db.Enum(NotificationType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'applicant_id': self.applicant_id,
            'admin_id': self.admin_id,
            'application_id': self.application_id,
            'type': self.type.value,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None
        }
    
    def __repr__(self):
        return f'<Notification {self.title}>'