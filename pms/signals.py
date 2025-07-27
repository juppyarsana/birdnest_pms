from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Reservation
from .email_service import email_service
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Reservation)
def store_previous_status(sender, instance, **kwargs):
    """Store the previous status before saving to detect status changes"""
    if instance.pk:
        try:
            previous = Reservation.objects.get(pk=instance.pk)
            cache.set(f'reservation_previous_status_{instance.pk}', previous.status, timeout=300)
        except Reservation.DoesNotExist:
            pass

@receiver(post_save, sender=Reservation)
def send_reservation_notification(sender, instance, created, **kwargs):
    """Send email notification when reservation status changes"""
    
    # Get previous status from cache
    previous_status = cache.get(f'reservation_previous_status_{instance.pk}')
    current_status = instance.status
    
    # Clear the cache
    if instance.pk:
        cache.delete(f'reservation_previous_status_{instance.pk}')
    
    # Determine if we should send an email
    should_send_email = False
    notification_type = None
    
    if created and current_status == 'pending':
        # New reservation created with pending status
        should_send_email = True
        notification_type = 'pending'
    elif previous_status and previous_status != current_status:
        # Status changed
        if current_status in ['pending', 'confirmed', 'expected_arrival', 'expected_departure']:
            should_send_email = True
            notification_type = current_status
    
    # Send email if conditions are met
    if should_send_email and notification_type:
        try:
            success = email_service.send_reservation_notification(instance, notification_type)
            if success:
                logger.info(f"Email notification sent for reservation {instance.id} - {notification_type}")
            else:
                logger.warning(f"Failed to send email notification for reservation {instance.id} - {notification_type}")
        except Exception as e:
            logger.error(f"Error sending email notification for reservation {instance.id}: {str(e)}")