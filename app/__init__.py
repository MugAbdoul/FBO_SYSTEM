from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*")

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_room')
def on_join(room):
    join_room(room)
    print(f"User joined room: {room}")

@socketio.on('leave_room')
def on_leave(room):
    leave_room(room)
    print(f"User left room: {room}")

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        'postgresql://postgres:1324@localhost/rgb_church_portal'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-string')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "DELETE","POST", "PUT", "PATCH","OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)
    app.config['CORS_HEADERS'] = 'Content-Type'
    app.url_map.strict_slashes = False

    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    # CORS(app)
    socketio.init_app(app)


    # Register blueprints
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.application import bp as application_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.documents import bp as documents_bp
    from app.blueprints.notifications import bp as notifications_bp
    from app.blueprints.certificates import bp as certificates_bp
    from app.blueprints.public import bp as public_bp
    from app.blueprints.reports import bp as reports_bp
    from app.blueprints.provinceAndDistrict import bp as provinceAndDistrict_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(application_bp, url_prefix='/api/application')
    app.register_blueprint(provinceAndDistrict_bp, url_prefix='/api/provinces')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(certificates_bp, url_prefix='/api/certificates')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(public_bp, url_prefix='/api/public')
    
    # Create default admin user
    @app.before_request
    def create_default_admin():
        from app.models.admin import Admin
        from app.utils.auth import hash_password
        
        if not Admin.query.filter_by(email='ceo@gmail.com').first():
            admin = Admin(
                email='ceo@gmail.com',
                password=hash_password('Mugisha12@'),
                firstname='System',
                lastname='Administrator',
                phonenumber='+250780000000',
                role='CEO',
                gender='MALE',
                enabled=True 
            )
            db.session.add(admin)
            db.session.commit()

        seed_rwanda_locations()
    

    def seed_rwanda_locations():
        """Seed Rwanda provinces and districts data"""

        from app.models.provinceAndDistrict import Province, District
        
        # Check if data already exists
        if Province.query.first():
            return
        
        # Rwanda provinces and districts data
        rwanda_data = {
            'Kigali City': {
                'code': 'KC',
                'districts': [
                    {'name': 'Gasabo', 'code': 'GAS'},
                    {'name': 'Kicukiro', 'code': 'KIC'},
                    {'name': 'Nyarugenge', 'code': 'NYA'}
                ]
            },
            'Northern Province': {
                'code': 'NP',
                'districts': [
                    {'name': 'Burera', 'code': 'BUR'},
                    {'name': 'Gakenke', 'code': 'GAK'},
                    {'name': 'Gicumbi', 'code': 'GIC'},
                    {'name': 'Musanze', 'code': 'MUS'},
                    {'name': 'Rulindo', 'code': 'RUL'}
                ]
            },
            'Southern Province': {
                'code': 'SP',
                'districts': [
                    {'name': 'Gisagara', 'code': 'GIS'},
                    {'name': 'Huye', 'code': 'HUY'},
                    {'name': 'Kamonyi', 'code': 'KAM'},
                    {'name': 'Muhanga', 'code': 'MUH'},
                    {'name': 'Nyamagabe', 'code': 'NYM'},
                    {'name': 'Nyanza', 'code': 'NYZ'},
                    {'name': 'Nyaruguru', 'code': 'NYR'},
                    {'name': 'Ruhango', 'code': 'RUH'}
                ]
            },
            'Eastern Province': {
                'code': 'EP',
                'districts': [
                    {'name': 'Bugesera', 'code': 'BUG'},
                    {'name': 'Gatsibo', 'code': 'GAT'},
                    {'name': 'Kayonza', 'code': 'KAY'},
                    {'name': 'Kirehe', 'code': 'KIR'},
                    {'name': 'Ngoma', 'code': 'NGO'},
                    {'name': 'Nyagatare', 'code': 'NYG'},
                    {'name': 'Rwamagana', 'code': 'RWA'}
                ]
            },
            'Western Province': {
                'code': 'WP',
                'districts': [
                    {'name': 'Karongi', 'code': 'KAR'},
                    {'name': 'Ngororero', 'code': 'NGR'},
                    {'name': 'Nyabihu', 'code': 'NYB'},
                    {'name': 'Nyamasheke', 'code': 'NYS'},
                    {'name': 'Rubavu', 'code': 'RUB'},
                    {'name': 'Rusizi', 'code': 'RUS'},
                    {'name': 'Rutsiro', 'code': 'RUT'}
                ]
            }
        }
        
        # Create provinces and districts
        for province_name, province_data in rwanda_data.items():
            # Create province
            province = Province(name=province_name, code=province_data['code'])
            db.session.add(province)
            db.session.flush()  # To get the province ID
            
            # Create districts for this province
            for district_data in province_data['districts']:
                district = District(
                    name=district_data['name'],
                    code=district_data['code'],
                    province_id=province.id
                )
                db.session.add(district)
        
        db.session.commit()
        print("Rwanda provinces and districts seeded successfully!")
        
    
    return app