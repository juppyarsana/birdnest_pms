import os
import requests
import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class EmailService:
    """
    Email service using Mailgun API for sending reservation notifications.
    Can be enabled/disabled via environment variables or database settings.
    """
    
    def __init__(self):
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.from_email = os.getenv('MAILGUN_FROM_EMAIL', f'noreply@{self.mailgun_domain}')
        
    def get_db_settings(self):
        """Get email settings from database"""
        try:
            from .models import EmailNotificationSettings
            return EmailNotificationSettings.get_settings()
        except Exception as e:
            logger.error(f"Error getting database settings: {str(e)}")
            return None
        
    def is_configured(self) -> bool:
        """Check if Mailgun is properly configured"""
        return bool(self.mailgun_api_key and self.mailgun_domain)
    
    def is_enabled(self, notification_type: str = None) -> bool:
        """Check if email notifications are enabled globally and for specific type"""
        # Check environment variable first
        env_enabled = os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'False').lower() in ['true', '1']
        
        # Check database settings
        db_settings = self.get_db_settings()
        if db_settings:
            db_enabled = db_settings.email_notifications_enabled
            
            # Check specific notification type
            if notification_type and db_enabled:
                type_mapping = {
                    'pending': db_settings.send_pending_notifications,
                    'confirmed': db_settings.send_confirmed_notifications,
                    'expected_arrival': db_settings.send_expected_arrival_notifications,
                    'expected_departure': db_settings.send_expected_departure_notifications,
                }
                return type_mapping.get(notification_type, True)
            
            return db_enabled
        
        return env_enabled
    
    def log_email_attempt(self, reservation, notification_type: str, recipient_email: str, status: str, error_message: str = ""):
        """Log email sending attempt to database"""
        try:
            from .models import EmailLog
            EmailLog.objects.create(
                reservation=reservation,
                notification_type=notification_type,
                recipient_email=recipient_email,
                status=status,
                error_message=error_message
            )
        except Exception as e:
            logger.error(f"Error logging email attempt: {str(e)}")
    
    def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """
        Send email using Mailgun API
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text content (optional, will be generated from HTML if not provided)
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("Email service not configured. Skipping email send.")
            return False
            
        if not to_email:
            logger.warning("No recipient email provided. Skipping email send.")
            return False
            
        if not text_content:
            text_content = strip_tags(html_content)
            
        try:
            response = requests.post(
                f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages",
                auth=("api", self.mailgun_api_key),
                data={
                    "from": self.from_email,
                    "to": to_email,
                    "subject": subject,
                    "text": text_content,
                    "html": html_content
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email to {to_email}. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    def send_reservation_notification(self, reservation, notification_type: str) -> bool:
        """
        Send reservation notification email
        
        Args:
            reservation: Reservation model instance
            notification_type: Type of notification ('pending', 'confirmed', 'expected_arrival', 'expected_departure')
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured():
            self.log_email_attempt(reservation, notification_type, reservation.guest.email or "", "skipped", "Email service not configured")
            return False
            
        if not self.is_enabled(notification_type):
            self.log_email_attempt(reservation, notification_type, reservation.guest.email or "", "skipped", "Email notifications disabled")
            return False
            
        if not reservation.guest.email:
            logger.warning(f"No email address for guest {reservation.guest.name}. Skipping notification.")
            self.log_email_attempt(reservation, notification_type, "", "skipped", "No email address provided")
            return False
            
        # Email subject mapping
        subject_mapping = {
            'pending': f'Reservation Confirmation Pending - {reservation.room}',
            'confirmed': f'Reservation Confirmed - {reservation.room}',
            'expected_arrival': f'Welcome! Your Arrival is Expected Today - {reservation.room}',
            'expected_departure': f'Check-out Reminder - {reservation.room}'
        }
        
        subject = subject_mapping.get(notification_type, f'Reservation Update - {reservation.room}')
        
        # Get hotel information from database settings or fallback to Django settings
        db_settings = self.get_db_settings()
        if db_settings:
            hotel_name = db_settings.hotel_name
            hotel_contact = db_settings.hotel_contact
            hotel_address = db_settings.hotel_address
        else:
            hotel_name = getattr(settings, 'HOTEL_NAME', 'Bird Nest PMS')
            hotel_contact = getattr(settings, 'HOTEL_CONTACT', '')
            hotel_address = getattr(settings, 'HOTEL_ADDRESS', '')
        
        # Prepare context for email template
        context = {
            'reservation': reservation,
            'guest': reservation.guest,
            'room': reservation.room,
            'notification_type': notification_type,
            'hotel_name': hotel_name,
            'hotel_contact': hotel_contact,
            'hotel_address': hotel_address,
        }
        
        try:
            # Render email template
            html_content = render_to_string(f'pms/emails/reservation_{notification_type}.html', context)
            text_content = render_to_string(f'pms/emails/reservation_{notification_type}.txt', context)
            
            success = self.send_email(
                to_email=reservation.guest.email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            # Log the attempt
            status = "success" if success else "failed"
            error_message = "" if success else "Failed to send via Mailgun API"
            self.log_email_attempt(reservation, notification_type, reservation.guest.email, status, error_message)
            
            return success
            
        except Exception as e:
            error_message = f"Error preparing email: {str(e)}"
            logger.error(f"Error preparing email for reservation {reservation.id}: {error_message}")
            self.log_email_attempt(reservation, notification_type, reservation.guest.email, "failed", error_message)
            return False

# Global instance
email_service = EmailService()