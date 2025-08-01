from app import db
from datetime import datetime

class ApplicationComment(db.Model):
    __tablename__ = 'application_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    performed_by_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('organization_applications.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'performed_by_id': self.performed_by_id,
            'application_id': self.application_id,
            'created_at': self.created_at.isoformat(),
            'performed_by': self.performed_by.to_dict() if self.performed_by else None
        }
    
    def __repr__(self):
        return f'<ApplicationComment {self.id} - App: {self.application_id}>'