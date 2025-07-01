from app import db

class ClusterInformation(db.Model):
    __tablename__ = 'cluster_information'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('organization_applications.id'), nullable=False)
    
    cluster_of_intervention = db.Column(db.String(200), nullable=False)
    source_of_fund = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'cluster_of_intervention': self.cluster_of_intervention,
            'source_of_fund': self.source_of_fund,
            'description': self.description
        }
    
    def __repr__(self):
        return f'<ClusterInformation {self.cluster_of_intervention}>'