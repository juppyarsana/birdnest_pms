from django.db import models
from datetime import date

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

class Guest(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.name

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('expected_arrival', 'Expected Arrival'),
        ('expected_departure', 'Expected Departure'),
        ('canceled', 'Canceled'),
        ('no_show', 'No-Show'),
    ]
    PAYMENT_METHODS = [
        ('', 'Not Specified'),  # Empty choice for pending reservations
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
    ]
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    check_in = models.DateField()
    check_out = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, blank=True, default='')

    def __str__(self):
        return f"{self.guest.name} - {self.room.room_number} ({self.status})"

    def update_status(self):
        """Automatically update status based on current date."""
        today = date.today()
        if self.status in ['pending', 'confirmed']:
            if self.check_in == today:
                self.status = 'expected_arrival'
            elif self.check_out == today:
                self.status = 'expected_departure'
        self.save()