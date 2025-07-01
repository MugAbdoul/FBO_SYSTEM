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
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(application_bp, url_prefix='/api/applications')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(certificates_bp, url_prefix='/api/certificates')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(public_bp, url_prefix='/api/public')
    
    # Create default admin user
    # @app.before_request
    # def create_default_admin():
    #     from app.models.admin import Admin
    #     from app.utils.auth import hash_password
        
    #     if not Admin.query.filter_by(email='admin@gmail.com').first():
    #         admin = Admin(
    #             email='admin@gmail.com',
    #             password=hash_password('Admin123@'),
    #             firstname='System',
    #             lastname='Administrator',
    #             phonenumber='+250780000000',
    #             role='CEO',
    #             gender='MALE',
    #             enabled=True 
    #         )
    #         db.session.add(admin)
    #         db.session.commit()
    
    return app