import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import pandas as pd
import os

class ApplicationRiskScorer:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_names = [
            'organization_name_length',
            'has_acronym',
            'phone_format_valid',
            'email_domain_type',
            'address_length',
            'num_documents',
            'applicant_age',
            'civil_status_encoded',
            'gender_encoded'
        ]
        self.is_trained = False
        
    def _generate_training_data(self):
        """Generate synthetic training data for the model"""
        np.random.seed(42)
        n_samples = 1000
        
        data = []
        for _ in range(n_samples):
            # Generate features
            org_name_len = np.random.randint(10, 100)
            has_acronym = np.random.choice([0, 1])
            phone_valid = np.random.choice([0, 1], p=[0.1, 0.9])
            email_domain = np.random.choice([0, 1, 2])  # 0=gmail, 1=org, 2=gov
            address_len = np.random.randint(20, 200)
            num_docs = np.random.randint(4, 8)
            applicant_age = np.random.randint(25, 70)
            civil_status = np.random.randint(0, 5)
            gender = np.random.randint(0, 2)
            
            # Generate risk score (0-100)
            # Lower risk for: valid phone, org/gov email, more docs, middle age
            risk_score = 50
            if not phone_valid:
                risk_score += 20
            if email_domain == 0:  # gmail
                risk_score += 10
            elif email_domain == 2:  # gov
                risk_score -= 15
            if num_docs < 6:
                risk_score += 15
            if applicant_age < 30 or applicant_age > 60:
                risk_score += 10
            
            # Add some randomness
            risk_score += np.random.normal(0, 10)
            risk_score = max(0, min(100, risk_score))
            
            # Convert to binary classification (high risk > 70)
            is_high_risk = 1 if risk_score > 70 else 0
            
            data.append([
                org_name_len, has_acronym, phone_valid, email_domain,
                address_len, num_docs, applicant_age, civil_status, gender,
                is_high_risk, risk_score
            ])
        
        columns = self.feature_names + ['is_high_risk', 'risk_score']
        return pd.DataFrame(data, columns=columns)
    
    def train_model(self):
        """Train the risk scoring model"""
        # Generate training data
        df = self._generate_training_data()
        
        # Prepare features and target
        X = df[self.feature_names]
        y = df['is_high_risk']
        
        # Train model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        
        self.is_trained = True
        print("Model trained successfully!")
    
    def _extract_features(self, application_data):
        """Extract features from application data"""
        try:
            features = []
            
            # Organization name length
            features.append(len(application_data.get('organization_name', '')))
            
            # Has acronym
            features.append(1 if application_data.get('acronym') else 0)
            
            # Phone format validation
            phone = application_data.get('organization_phone', '')
            phone_valid = 1 if phone.startswith('+') and len(phone) > 10 else 0
            features.append(phone_valid)
            
            # Email domain type
            email = application_data.get('organization_email', '')
            if '@gmail.com' in email or '@yahoo.com' in email:
                email_domain = 0  # Personal
            elif '.gov.' in email or '.org' in email:
                email_domain = 2  # Official
            else:
                email_domain = 1  # Organization
            features.append(email_domain)
            
            # Address length
            features.append(len(application_data.get('address', '')))
            
            # Number of documents
            features.append(application_data.get('num_documents', 0))
            
            # Applicant age (calculated from date_of_birth)
            from datetime import datetime
            dob = application_data.get('applicant', {}).get('date_of_birth')
            if dob:
                if isinstance(dob, str):
                    dob = datetime.strptime(dob, '%Y-%m-%d').date()
                age = (datetime.now().date() - dob).days // 365
            else:
                age = 35  # Default age
            features.append(age)
            
            # Civil status encoded
            civil_status_map = {'SINGLE': 0, 'MARRIED': 1, 'DIVORCED': 2, 'WIDOWED': 3, 'SEPARATED': 4}
            civil_status = application_data.get('applicant', {}).get('civil_status', 'SINGLE')
            features.append(civil_status_map.get(civil_status, 0))
            
            # Gender encoded
            gender_map = {'MALE': 0, 'FEMALE': 1}
            gender = application_data.get('applicant', {}).get('gender', 'MALE')
            features.append(gender_map.get(gender, 0))
            
            return features
        except Exception as e:
            print(f"Error extracting features: {e}")
            # Return default features if extraction fails
            return [50, 0, 1, 1, 100, 6, 35, 0, 0]
    
    def predict_risk(self, application_data):
        """Predict risk score for an application"""
        if not self.is_trained:
            self.train_model()
        
        try:
            features = self._extract_features(application_data)
            features_array = np.array(features).reshape(1, -1)
            
            # Get probability of high risk
            risk_probability = self.model.predict_proba(features_array)[0][1]
            risk_score = risk_probability * 100
            
            # Get prediction
            is_high_risk = self.model.predict(features_array)[0]
            
            # Get feature importance for this prediction
            feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
            
            return {
                'risk_score': round(risk_score, 2),
                'is_high_risk': bool(is_high_risk),
                'risk_level': 'HIGH' if risk_score > 70 else 'MEDIUM' if risk_score > 40 else 'LOW',
                'feature_importance': feature_importance,
                'recommendation': self._get_recommendation(risk_score)
            }
        except Exception as e:
            print(f"Error predicting risk: {e}")
            # Return default prediction if error occurs
            return {
                'risk_score': 50.0,
                'is_high_risk': False,
                'risk_level': 'MEDIUM',
                'feature_importance': {},
                'recommendation': 'Standard review process recommended'
            }
    
    def _get_recommendation(self, risk_score):
        """Get recommendation based on risk score"""
        if risk_score > 80:
            return "High risk - Requires thorough manual review and additional verification"
        elif risk_score > 60:
            return "Medium-high risk - Enhanced review and document verification recommended"
        elif risk_score > 40:
            return "Medium risk - Standard review process with careful document check"
        elif risk_score > 20:
            return "Low-medium risk - Standard review process"
        else:
            return "Low risk - Fast-track review possible"

# Global instance
risk_scorer = ApplicationRiskScorer()