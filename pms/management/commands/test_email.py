from django.core.management.base import BaseCommand
from django.utils import timezone
from pms.models import Reservation
from pms.email_service import email_service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test email notifications for reservations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reservation-id',
            type=int,
            help='Specific reservation ID to test email for'
        )
        parser.add_argument(
            '--notification-type',
            type=str,
            choices=['pending', 'confirmed', 'expected_arrival', 'expected_departure'],
            help='Type of notification to test'
        )
        parser.add_argument(
            '--test-email',
            type=str,
            help='Override email address for testing'
        )

    def handle(self, *args, **options):
        if not email_service.is_configured():
            self.stdout.write(
                self.style.ERROR('Email service is not configured. Please check your environment variables.')
            )
            return

        reservation_id = options.get('reservation_id')
        notification_type = options.get('notification_type', 'pending')
        test_email = options.get('test_email')

        if reservation_id:
            try:
                reservation = Reservation.objects.get(id=reservation_id)
            except Reservation.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Reservation with ID {reservation_id} not found.')
                )
                return
        else:
            # Get the most recent reservation
            reservation = Reservation.objects.order_by('-id').first()
            if not reservation:
                self.stdout.write(
                    self.style.ERROR('No reservations found in the database.')
                )
                return

        # Override email if test email is provided
        original_email = reservation.guest.email
        if test_email:
            reservation.guest.email = test_email

        self.stdout.write(f'Testing {notification_type} notification for reservation {reservation.id}')
        self.stdout.write(f'Guest: {reservation.guest.name}')
        self.stdout.write(f'Email: {reservation.guest.email}')
        self.stdout.write(f'Room: {reservation.room.room_number}')

        # Send test email
        success = email_service.send_reservation_notification(reservation, notification_type)

        # Restore original email
        if test_email:
            reservation.guest.email = original_email

        if success:
            self.stdout.write(
                self.style.SUCCESS(f'Test email sent successfully!')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Failed to send test email. Check logs for details.')
            )