from app import db
from datetime import datetime
from enum import Enum

class  AdminRole(Enum):
    FBO_OFFICER = "FBO_OFFICER"
    DIVISION_MANAGER = "DIVISION_MANAGER"
    HOD = "HOD"
    SECRETARY_GENERAL = "SECRETARY_GENERAL"
    CEO = "CEO"

class Gender(Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(128), nullable=False)
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    phonenumber = db.Column(db.String(15), nullable=False)
    role = db.Column(db.Enum(AdminRole), nullable=False)
    gender = db.Column(db.Enum(Gender), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    processed_applications = db.relationship('OrganizationApplication', backref='processor', lazy=True)
    notifications = db.relationship('Notification', backref='admin', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('ApplicationComment', backref='performed_by', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'phonenumber': self.phonenumber,
            'role': self.role.value,
            'gender': self.gender.value,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Admin {self.email} - {self.role.value}>'