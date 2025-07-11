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
        ('available', 'Available'),
        ('occupied', 'Occupied'),
    ]
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')

    def __str__(self):
        return f"Room {self.room_number}"

    def update_status(self, date=None):
        """Update room status based on reservations.
        A room is occupied if there's an active reservation for the given date."""
        from django.db.models import Q
        if date is None:
            date = date.today()
        
        # Check if there are any active reservations for this room on the given date
        is_occupied = Reservation.objects.filter(
            Q(room=self) &
            Q(check_in__lte=date) &
            Q(check_out__gt=date) &  # Use > instead of >= for check_out
            Q(status__in=['confirmed', 'checked_in', 'expected_arrival', 'expected_departure'])
        ).exists()

        self.status = 'occupied' if is_occupied else 'available'
        self.save()

    def is_available(self, check_in, check_out):
        """Check if room is available for the given date range."""
        from django.db.models import Q
        
        # A room is available if there are no overlapping active reservations
        overlapping = Reservation.objects.filter(
            Q(room=self) &
            Q(check_in__lt=check_out) &  # New booking starts before existing booking ends
            Q(check_out__gt=check_in) &  # New booking ends after existing booking starts
            Q(status__in=['confirmed', 'checked_in', 'expected_arrival', 'expected_departure'])
        ).exists()
        
        return not overlapping

class Guest(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
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
        ('checked_in', 'Checked In'),
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

    def __str__(self):
        return f"{self.guest.name} - {self.room.room_number} ({self.status})"

    def update_status(self):
        """Automatically update status based on current date."""
        today = date.today()
        
        # Handle no-shows: If check-in date has passed and status is still 'confirmed' or 'expected_arrival'
        if (self.check_in < today and 
            self.status in ['confirmed', 'expected_arrival']):
            self.status = 'no_show'
            self.save()
            return

        # Only confirmed reservations can become expected_arrival or expected_departure
        if self.status == 'confirmed':
            if self.check_in == today:
                self.status = 'expected_arrival'
            elif self.check_out == today:
                self.status = 'expected_departure'
            self.save()

    def has_overlap(self):
        """Check if there are any overlapping reservations for the same room.
        A room can be booked on another reservation's check-out date."""
        overlapping = Reservation.objects.filter(
            room=self.room,
            check_in__lt=self.check_out,  # Changed from check_in__lte to check_in__lt
            check_out__gt=self.check_in   # Changed from check_out__gte to check_out__gt
        ).exclude(pk=self.pk)  # Exclude current reservation when updating
        
        return overlapping.exists()

    def clean(self):
        """Validate the reservation."""
        from django.core.exceptions import ValidationError
        
        # Ensure check_out is after check_in
        if self.check_out and self.check_in and self.check_out <= self.check_in:
            raise ValidationError('Check-out date must be after check-in date')
        
        # Check for overlapping reservations
        if self.has_overlap():
            raise ValidationError('This room is already reserved for these dates')
        
        super().clean()

    def save(self, *args, **kwargs):
        """Override save to enforce validation."""
        self.full_clean()
        super().save(*args, **kwargs)