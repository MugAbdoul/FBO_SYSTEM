from app import db
from datetime import datetime
from enum import Enum

class CivilStatus(Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    SEPARATED = "SEPARATED"

class Gender(Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class Applicant(db.Model):
    __tablename__ = 'applicants'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(128), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    nid_or_passport = db.Column(db.String(20), unique=True, nullable=False)
    phonenumber = db.Column(db.String(15), nullable=False)
    nationality = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.Enum(Gender), nullable=False)
    civil_status = db.Column(db.Enum(CivilStatus), nullable=False)
    title = db.Column(db.String(10), nullable=False)  # Mr, Mrs, Ms, Dr, etc.
    
    # Relationships
    applications = db.relationship('OrganizationApplication', backref='applicant', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='applicant', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'nid_or_passport': self.nid_or_passport,
            'phonenumber': self.phonenumber,
            'nationality': self.nationality,
            'date_of_birth': self.date_of_birth.isoformat(),
            'gender': self.gender.value,
            'civil_status': self.civil_status.value,
            'title': self.title
        }
    
    def __repr__(self):
        return f'<Applicant {self.email}>'