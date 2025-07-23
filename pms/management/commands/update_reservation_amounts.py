from django.core.management.base import BaseCommand
from pms.models import Reservation

class Command(BaseCommand):
    help = 'Update total_amount for existing reservations'
    
    def handle(self, *args, **options):
        reservations = Reservation.objects.filter(total_amount__isnull=True)
        updated = 0
        
        for reservation in reservations:
            if reservation.room and reservation.check_in and reservation.check_out:
                nights = (reservation.check_out - reservation.check_in).days
                if nights > 0:
                    reservation.base_amount = reservation.room.rate * nights
                    reservation.total_amount = reservation.base_amount - reservation.discount_amount
                    reservation.save()
                    updated += 1
        
        self.stdout.write(f'Updated {updated} reservations')