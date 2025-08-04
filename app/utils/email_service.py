# In app/utils/email_service.py

from flask import current_app
from flask_mail import Message
from app import mail

def send_email(recipient, subject, body, html=None):
    """
    Send an email to the specified recipient.
    
    Args:
        recipient (str): Email address of the recipient
        subject (str): Subject of the email
        body (str): Plain text body of the email
        html (str, optional): HTML body of the email. Defaults to None.
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            html=html,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False