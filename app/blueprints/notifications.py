from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app import db, socketio
from app.models.notification import Notification, NotificationType
from app.models.admin import Admin
from app.models.applicant import Applicant
from app.utils.auth import get_current_user
from datetime import datetime

bp = Blueprint('notifications', __name__)

@bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications for current user"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        # Build query based on user type
        if claims.get('type') == 'applicant':
            notifications = Notification.query.filter_by(applicant_id=user.id)
        elif claims.get('type') == 'admin':
            notifications = Notification.query.filter_by(admin_id=user.id)
        else:
            return jsonify({'error': 'Invalid user type'}), 400
        
        # Apply filters
        unread_only = request.args.get('unread_only', False, type=bool)
        if unread_only:
            notifications = notifications.filter_by(is_read=False)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        notifications = notifications.order_by(
            Notification.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'notifications': [notification.to_dict() for notification in notifications.items],
            'pagination': {
                'page': notifications.page,
                'pages': notifications.pages,
                'per_page': notifications.per_page,
                'total': notifications.total
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get notifications: {str(e)}'}), 500

@bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        notification = Notification.query.get_or_404(notification_id)
        
        # Check ownership
        if claims.get('type') == 'applicant' and notification.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        elif claims.get('type') == 'admin' and notification.admin_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Mark as read
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Notification marked as read',
            'notification': notification.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to mark notification as read: {str(e)}'}), 500

@bp.route('/mark-all-read', methods=['PUT'])
@jwt_required()
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        # Build query based on user type
        if claims.get('type') == 'applicant':
            notifications = Notification.query.filter_by(
                applicant_id=user.id,
                is_read=False
            )
        elif claims.get('type') == 'admin':
            notifications = Notification.query.filter_by(
                admin_id=user.id,
                is_read=False
            )
        else:
            return jsonify({'error': 'Invalid user type'}), 400
        
        # Mark all as read
        count = notifications.update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        
        return jsonify({
            'message': f'Marked {count} notifications as read'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to mark notifications as read: {str(e)}'}), 500

@bp.route('/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_notification(notification_id):
    """Delete a notification"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        notification = Notification.query.get_or_404(notification_id)
        
        # Check ownership
        if claims.get('type') == 'applicant' and notification.applicant_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        elif claims.get('type') == 'admin' and notification.admin_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Delete notification
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'message': 'Notification deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete notification: {str(e)}'}), 500

@bp.route('/send', methods=['POST'])
@jwt_required()
def send_notification():
    """Send a notification (admin only)"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        # Only admins can send notifications
        if claims.get('type') != 'admin':
            return jsonify({'error': 'Only admins can send notifications'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'message', 'type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate notification type
        try:
            notification_type = NotificationType(data['type'])
        except ValueError:
            return jsonify({'error': 'Invalid notification type'}), 400
        
        # Create notification
        notification_data = {
            'type': notification_type,
            'title': data['title'],
            'message': data['message']
        }
        
        # Handle recipient(s)
        if 'applicant_id' in data:
            notification_data['applicant_id'] = data['applicant_id']
        elif 'admin_id' in data:
            notification_data['admin_id'] = data['admin_id']
        elif 'application_id' in data:
            notification_data['application_id'] = data['application_id']
        else:
            return jsonify({'error': 'No recipient specified'}), 400
        
        notification = Notification(**notification_data)
        db.session.add(notification)
        db.session.commit()
        
        # Send real-time notification
        if notification.applicant_id:
            socketio.emit('new_notification', notification.to_dict(), 
                         room=f'applicant_{notification.applicant_id}')
        elif notification.admin_id:
            socketio.emit('new_notification', notification.to_dict(), 
                         room=f'admin_{notification.admin_id}')
        
        return jsonify({
            'message': 'Notification sent successfully',
            'notification': notification.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to send notification: {str(e)}'}), 500

@bp.route('/broadcast', methods=['POST'])
@jwt_required()
def broadcast_notification():
    """Broadcast notification to all users of a type (admin only)"""
    try:
        user = get_current_user()
        claims = get_jwt()
        
        # Only admins can broadcast notifications
        if claims.get('type') != 'admin':
            return jsonify({'error': 'Only admins can broadcast notifications'}), 403
        
        # Only CEO and Secretary General can broadcast
        if user.role.value not in ['CEO', 'SECRETARY_GENERAL']:
            return jsonify({'error': 'Insufficient permissions to broadcast'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'message', 'recipient_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        recipient_type = data['recipient_type']  # 'all', 'applicants', 'admins'
        title = data['title']
        message = data['message']
        
        notifications_created = 0
        
        # Create notifications for recipients
        if recipient_type in ['all', 'applicants']:
            applicants = Applicant.query.filter_by(enabled=True).all()
            for applicant in applicants:
                notification = Notification(
                    applicant_id=applicant.id,
                    type=NotificationType.STATUS_CHANGE,
                    title=title,
                    message=message
                )
                db.session.add(notification)
                notifications_created += 1
        
        if recipient_type in ['all', 'admins']:
            admins = Admin.query.filter_by(enabled=True).all()
            for admin in admins:
                if admin.id != user.id:  # Don't send to self
                    notification = Notification(
                        admin_id=admin.id,
                        type=NotificationType.STATUS_CHANGE,
                        title=title,
                        message=message
                    )
                    db.session.add(notification)
                    notifications_created += 1
        
        db.session.commit()
        
        # Send real-time notifications
        socketio.emit('broadcast_notification', {
            'title': title,
            'message': message,
            'type': 'broadcast'
        }, broadcast=True)
        
        return jsonify({
            'message': f'Broadcast sent to {notifications_created} recipients'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to broadcast notification: {str(e)}'}), 500