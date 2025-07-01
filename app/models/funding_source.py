from app import db
from enum import Enum

class SourceType(Enum):
    GOVERNMENT = "GOVERNMENT"
    PRIVATE = "PRIVATE"
    INTERNATIONAL = "INTERNATIONAL"
    DONATION = "DONATION"
    INTERNAL = "INTERNAL"

class FundingSource(db.Model):
    __tablename__ = 'funding_sources'
    
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.Enum(SourceType), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_name': self.source_name,
            'source_type': self.source_type.value,
            'description': self.description
        }
    
    def __repr__(self):
        return f'<FundingSource {self.source_name}>'