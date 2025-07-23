from django.db import models
from datetime import date, datetime, time
from django.core.exceptions import ValidationError

class HotelSettings(models.Model):
    earliest_check_in_time = models.TimeField(default=time(14, 0))  # Default 2 PM
    latest_check_in_time = models.TimeField(default=time(22, 0))   # Default 10 PM
    check_in_grace_period = models.IntegerField(default=0, help_text="Grace period in minutes")
    
    class Meta:
        verbose_name = 'Hotel Settings'
        verbose_name_plural = 'Hotel Settings'

    def __str__(self):
        return f"Hotel Settings (Check-in: {self.earliest_check_in_time.strftime('%I:%M %p')} - {self.latest_check_in_time.strftime('%I:%M %p')})"

    def clean(self):
        if self.earliest_check_in_time >= self.latest_check_in_time:
            raise ValidationError("Earliest check-in time must be before latest check-in time")

    def is_check_in_allowed(self, current_time=None):
        if current_time is None:
            current_time = datetime.now().time()
        
        # Add grace period to the comparison
        if self.check_in_grace_period:
            from datetime import timedelta
            current_datetime = datetime.combine(date.today(), current_time)
            current_time = (current_datetime + timedelta(minutes=self.check_in_grace_period)).time()
        
        return self.earliest_check_in_time <= current_time <= self.latest_check_in_time

    @classmethod
    def get_settings(cls):
        settings = cls.objects.first()
        if not settings:
            settings = cls.objects.create()
        return settings

class Room(models.Model):
    ROOM_TYPES = [
        ('single', 'Single'),
        ('double', 'Double'),
        ('suite', 'Suite'),
    ]
    STATUS_CHOICES = [
        ('vacant_clean', 'Vacant Clean'),
        ('vacant_dirty', 'Vacant Dirty'),
        ('occupied', 'Occupied'),
        ('out_of_order', 'Out of Order'),
        ('maintenance', 'Maintenance'),
    ]
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='vacant_clean')

    def __str__(self):
        return f"Room {self.room_number}"

    # Room status logic
    def update_status(self, date=None):
        """Update room status based on reservations.
        A room is occupied if there's an active reservation for the given date."""
        from django.db.models import Q
        from datetime import date as date_class
        
        if date is None:
            date = date_class.today()
        
        # If the room is marked as vacant_dirty, do not auto-update
        if self.status == 'vacant_dirty':
            self.save()
            return
        # If the room is marked as out_of_order or maintenance, do not auto-update
        if self.status in ['out_of_order', 'maintenance']:
            self.save()
            return
        # Check if there are any active reservations for this room on the given date
        is_occupied = Reservation.objects.filter(
            Q(room=self) &
            Q(check_in__lte=date) &
            Q(check_out__gt=date) &
            Q(status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure'])
        ).exists()
        
        if is_occupied:
            self.status = 'occupied'
        else:
            if self.status != 'vacant_dirty':
                self.status = 'vacant_clean'
        self.save()

    def is_available(self, check_in, check_out):
        """Check if room is available for the given date range."""
        from django.db.models import Q
        # A room is available if there are no overlapping active reservations
        overlapping = Reservation.objects.filter(
            Q(room=self) &
            Q(check_in__lt=check_out) &  # New booking starts before existing booking ends
            Q(check_out__gt=check_in) &  # New booking ends after existing booking starts
            Q(status__in=['confirmed', 'in_house', 'expected_arrival'])
        ).exists()
        # Room must also be vacant_clean to be bookable
        return not overlapping and self.status == 'vacant_clean'

class Guest(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    id_type = models.CharField(max_length=50, blank=True)  # e.g., Passport, KTP, etc.
    id_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.name

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('expected_arrival', 'Expected Arrival'),
        ('in_house', 'In House'),
        ('expected_departure', 'Expected Departure'),
        ('checked_out', 'Checked Out'),
        ('canceled', 'Canceled'),
        ('no_show', 'No-Show'),
    ]
    PAYMENT_METHODS = [
        ('', 'Not Specified'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
    ]
    AGENT_CHOICES = [
        ('direct', 'Direct Booking'),
        ('booking_com', 'Booking.com'),
        ('expedia', 'Expedia'),
        ('agoda', 'Agoda'),
        ('airbnb', 'Airbnb'),
        ('travel_agent', 'Travel Agent'),
        ('corporate', 'Corporate'),
        ('walk_in', 'Walk-in'),
        ('phone', 'Phone Booking'),
        ('other', 'Other'),
    ]
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    check_in = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out = models.DateField()
    num_guests = models.PositiveIntegerField(default=1)
    terms_accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, blank=True, default='')
    payment_notes = models.TextField(blank=True, default='')  # New field
    agent = models.CharField(max_length=20, choices=AGENT_CHOICES, default='direct', help_text='Source/agent where this reservation came from')
    created_at = models.DateTimeField(auto_now_add=True)  # Reservation creation timestamp
    cancellation_reason = models.TextField(blank=True, default='')  # Reason for cancellation
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Final amount after discounts, taxes, and fees")
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Base room rate before discounts")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total discount applied")

    def __str__(self):
        return f"{self.guest.name} - {self.room.room_number} ({self.status})"

    def update_status(self):
        """Automatically update status based on current date."""
        today = date.today()
        print(f"Debug: Updating status for reservation {self.id}")
        print(f"Debug: Current status: {self.status}")
        print(f"Debug: Check-in date: {self.check_in}, Today: {today}")
        
        # Only update status for non-terminal states
        if self.status in ['checked_out', 'canceled', 'no_show']:
            print(f"Debug: Status is terminal, no update needed")
            return
        
        # Handle no-shows: If check-in date has passed and status is still 'confirmed' or 'expected_arrival'
        if (self.check_in < today and 
            self.status in ['confirmed', 'expected_arrival']):
            print(f"Debug: Marking as no-show")
            self.status = 'no_show'
            self.save()
            return
    
        # Handle expected_arrival: If today is check-in date and status is confirmed
        if self.status == 'confirmed' and self.check_in == today:
            print(f"Debug: Marking as expected arrival")
            self.status = 'expected_arrival'
            self.save()
            return
        
        # Handle expected_departure: If today is check-out date and status is in_house
        if self.status == 'in_house' and self.check_out == today:
            print(f"Debug: Marking as expected departure")
            self.status = 'expected_departure'
            self.save()
            return
        
        print(f"Debug: No status update needed")

    def has_overlap(self):
        """Check if there are any overlapping active reservations for the same room."""
        active_statuses = ['confirmed', 'in_house', 'expected_arrival']
        overlapping = Reservation.objects.filter(
            room=self.room,
            check_in__lt=self.check_out,
            check_out__gt=self.check_in,
            status__in=active_statuses
        ).exclude(pk=self.pk)
        return overlapping.exists()

    def clean(self):
        """Validate the reservation."""
        from django.core.exceptions import ValidationError
        # Ensure check_out is after check_in
        if self.check_out and self.check_in and self.check_out <= self.check_in:
            raise ValidationError('Check-out date must be after check-in date')
        # Check for overlapping active reservations
        if self.has_overlap():
            raise ValidationError('This room is already reserved for these dates')
        
        super().clean()

    def calculate_total_amount(self):
        """Calculate total amount based on room rate, nights, discounts, etc."""
        if not self.room or not self.check_in or not self.check_out:
            return 0
        
        nights = (self.check_out - self.check_in).days
        base_total = self.room.rate * nights
        final_total = base_total - self.discount_amount
        
        return max(final_total, 0)  # Ensure non-negative
    
    def save(self, *args, **kwargs):
        # Auto-calculate total_amount if not set
        if self.total_amount is None:
            self.base_amount = self.room.rate * (self.check_out - self.check_in).days if self.room and self.check_in and self.check_out else 0
            self.total_amount = self.calculate_total_amount()
        super().save(*args, **kwargs)