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

class Nationality(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Nationality name (e.g., Indonesian, American)")
    code = models.CharField(max_length=10, unique=True, blank=True, help_text="Optional country code (e.g., ID, US)")
    is_active = models.BooleanField(default=True, help_text="Whether this nationality is available for selection")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Nationality'
        verbose_name_plural = 'Nationalities'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Agent(models.Model):
    """Model for managing booking agents/sources dynamically"""
    name = models.CharField(max_length=100, unique=True, help_text="Name of the booking agent or source")
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which this agent appears in dropdowns")
    is_active = models.BooleanField(default=True, help_text="Whether this agent is currently available for selection")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Payment method name (e.g., Bank Transfer, Cash)")
    code = models.CharField(max_length=20, unique=True, help_text="Internal code for the payment method")
    description = models.TextField(blank=True, help_text="Optional description or instructions")
    is_active = models.BooleanField(default=True, help_text="Whether this payment method is available for selection")
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which to display this payment method")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name

class Room(models.Model):
    ROOM_TYPES = [
        ('garden_view', 'Garden View'),
        ('mountain_view', 'Mountain View'),
    ]
    STATUS_CHOICES = [
        ('vacant_clean', 'Vacant Clean'),
        ('vacant_dirty', 'Vacant Dirty'),
        ('occupied', 'Occupied'),
        ('out_of_order', 'Out of Order'),
        ('maintenance', 'Maintenance'),
        ('out_of_service', 'Out of Service'),
    ]
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='vacant_clean')
    
    # Enhanced room details
    floor = models.PositiveIntegerField(null=True, blank=True, help_text="Floor number")
    max_occupancy = models.PositiveIntegerField(default=2, help_text="Maximum number of guests")
    size_sqm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Room size in square meters")
    amenities = models.TextField(blank=True, help_text="Room amenities (comma-separated)")
    description = models.TextField(blank=True, help_text="Room description")
    
    # Status tracking
    status_changed_at = models.DateTimeField(auto_now=True)
    status_changed_by = models.CharField(max_length=100, blank=True, help_text="Who changed the status")
    status_reason = models.TextField(blank=True, help_text="Reason for status change")
    
    # Maintenance tracking
    maintenance_start_date = models.DateField(null=True, blank=True)
    maintenance_end_date = models.DateField(null=True, blank=True)
    maintenance_notes = models.TextField(blank=True)
    
    # Housekeeping notes
    housekeeping_notes = models.TextField(blank=True, help_text="Special housekeeping instructions")
    last_cleaned = models.DateTimeField(null=True, blank=True)
    
    # Room features
    has_balcony = models.BooleanField(default=False)
    has_ac = models.BooleanField(default=True)
    has_wifi = models.BooleanField(default=True)
    has_tv = models.BooleanField(default=True)
    has_minibar = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        # If the room is marked as out_of_order, maintenance, or out_of_service, do not auto-update
        if self.status in ['out_of_order', 'maintenance', 'out_of_service']:
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
    
    def get_reservation_history(self, limit=10):
        """Get recent reservation history for this room"""
        return Reservation.objects.filter(room=self).order_by('-check_in')[:limit]
    
    def get_occupancy_rate(self, start_date=None, end_date=None):
        """Calculate occupancy rate for a given period"""
        from datetime import date as date_class, timedelta
        
        if not start_date:
            start_date = date_class.today() - timedelta(days=30)
        if not end_date:
            end_date = date_class.today()
            
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return 0
            
        occupied_days = Reservation.objects.filter(
            room=self,
            check_in__lt=end_date,
            check_out__gt=start_date,
            status__in=['confirmed', 'in_house', 'checked_out', 'expected_arrival', 'expected_departure', 'no_show']
        ).count()
        
        return (occupied_days / total_days) * 100
    
    def get_amenities_list(self):
        """Return amenities as a list"""
        if self.amenities:
            return [amenity.strip() for amenity in self.amenities.split(',') if amenity.strip()]
        return []
    
    def set_maintenance(self, start_date, end_date, notes, changed_by):
        """Set room to maintenance status with tracking"""
        self.status = 'maintenance'
        self.maintenance_start_date = start_date
        self.maintenance_end_date = end_date
        self.maintenance_notes = notes
        self.status_changed_by = changed_by
        self.status_reason = f"Maintenance scheduled from {start_date} to {end_date}"
        self.save()
        
        # Create maintenance log entry
        RoomMaintenanceLog.objects.create(
            room=self,
            maintenance_type='scheduled',
            start_date=start_date,
            end_date=end_date,
            notes=notes,
            created_by=changed_by
        )
    
    def set_out_of_order(self, reason, changed_by, end_date=None):
        """Set room to out of order status"""
        self.status = 'out_of_order'
        self.status_changed_by = changed_by
        self.status_reason = reason
        if end_date:
            self.maintenance_end_date = end_date
        self.save()
        
        # Create maintenance log entry
        RoomMaintenanceLog.objects.create(
            room=self,
            maintenance_type='out_of_order',
            start_date=date.today(),
            end_date=end_date,
            notes=reason,
            created_by=changed_by
        )


class RoomMaintenanceLog(models.Model):
    MAINTENANCE_TYPES = [
        ('scheduled', 'Scheduled Maintenance'),
        ('emergency', 'Emergency Repair'),
        ('out_of_order', 'Out of Order'),
        ('deep_cleaning', 'Deep Cleaning'),
        ('renovation', 'Renovation'),
        ('inspection', 'Inspection'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='maintenance_logs')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    notes = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vendor = models.CharField(max_length=100, blank=True, help_text="Maintenance vendor/contractor")
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.room.room_number} - {self.get_maintenance_type_display()} ({self.start_date})"

class Guest(models.Model):
    ID_TYPE_CHOICES = [
        ('', 'Select ID Type'),
        ('passport', 'Passport'),
        ('ktp', 'KTP (Indonesian ID)'),
        ('drivers_license', 'Driver\'s License'),
        ('national_id', 'National ID Card'),
        ('sim', 'SIM (Indonesian Driver\'s License)'),
        ('visa', 'Visa'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    id_type = models.CharField(max_length=50, choices=ID_TYPE_CHOICES, blank=True, help_text="Type of identification document")
    id_number = models.CharField(max_length=50, blank=True)
    nationality = models.ForeignKey(Nationality, on_delete=models.SET_NULL, null=True, blank=True, help_text="Guest's nationality")
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
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    check_in = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out = models.DateField()
    num_guests = models.PositiveIntegerField(default=1)
    terms_accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True, help_text="Payment method used for this reservation")
    payment_notes = models.TextField(blank=True, default='')  # New field
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, help_text="Booking agent/source for this reservation")
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
        
        # Only update status for non-terminal states
        if self.status in ['checked_out', 'canceled', 'no_show']:
            return
        
        # Handle no-shows: If check-in date has passed and status is still 'confirmed' or 'expected_arrival'
        if (self.check_in < today and 
            self.status in ['confirmed', 'expected_arrival']):
            self.status = 'no_show'
            self.save()
            return
    
        # Handle expected_arrival: If today is check-in date and status is confirmed
        if self.status == 'confirmed' and self.check_in == today:
            self.status = 'expected_arrival'
            self.save()
            return
        
        # Handle expected_departure: If today is check-out date and status is in_house
        if self.status == 'in_house' and self.check_out == today:
            self.status = 'expected_departure'
            self.save()
            return

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


class EmailNotificationSettings(models.Model):
    """Model to store email notification settings in the database"""
    email_notifications_enabled = models.BooleanField(
        default=False,
        help_text="Enable or disable email notifications globally"
    )
    send_pending_notifications = models.BooleanField(
        default=True,
        help_text="Send email when reservation is created with pending status"
    )
    send_confirmed_notifications = models.BooleanField(
        default=True,
        help_text="Send email when reservation is confirmed"
    )
    send_expected_arrival_notifications = models.BooleanField(
        default=True,
        help_text="Send email when guest is expected to arrive"
    )
    send_expected_departure_notifications = models.BooleanField(
        default=True,
        help_text="Send email when guest is expected to depart"
    )
    
    # Email template customization
    hotel_name = models.CharField(
        max_length=200,
        default="Bird Nest PMS",
        help_text="Hotel name to display in emails"
    )
    hotel_contact = models.CharField(
        max_length=200,
        blank=True,
        help_text="Hotel contact information for emails"
    )
    hotel_address = models.TextField(
        blank=True,
        help_text="Hotel address for emails"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Notification Settings"
        verbose_name_plural = "Email Notification Settings"
    
    def __str__(self):
        status = "Enabled" if self.email_notifications_enabled else "Disabled"
        return f"Email Notifications - {status}"
    
    @classmethod
    def get_settings(cls):
        """Get or create email settings"""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'email_notifications_enabled': False,
                'hotel_name': 'Bird Nest PMS'
            }
        )
        return settings


class EmailLog(models.Model):
    """Model to log email sending attempts"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    
    reservation = models.ForeignKey(
        'Reservation',
        on_delete=models.CASCADE,
        related_name='email_logs'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('expected_arrival', 'Expected Arrival'),
            ('expected_departure', 'Expected Departure'),
        ]
    )
    recipient_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.notification_type} - {self.recipient_email} - {self.status}"


# Tablet and IoT Device Models
class TabletDevice(models.Model):
    """Model to manage tablet devices and their ESP32 controllers"""
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='tablet')
    tablet_id = models.CharField(max_length=50, unique=True, help_text="Unique identifier for the tablet")
    esp32_ip = models.GenericIPAddressField(help_text="IP address of the ESP32 controller")
    is_active = models.BooleanField(default=True)
    last_ping = models.DateTimeField(null=True, blank=True, help_text="Last successful ping to ESP32")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tablet Device"
        verbose_name_plural = "Tablet Devices"

    def __str__(self):
        return f"Tablet {self.tablet_id} - Room {self.room.room_number}"


class RoomDeviceState(models.Model):
    """Model to track the current state of room devices (lights, AC, etc.)"""
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='device_state')
    
    # Light controls
    front_light = models.BooleanField(default=False)
    back_light = models.BooleanField(default=False)
    main_light = models.BooleanField(default=False)
    sport_light = models.BooleanField(default=False)
    
    # RGB light controls
    rgb_light = models.BooleanField(default=False)
    rgb_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Hex color code")
    rgb_brightness = models.IntegerField(default=100, help_text="Brightness percentage (0-100)")
    
    # AC controls
    ac_power = models.BooleanField(default=False)
    ac_mode = models.CharField(
        max_length=10,
        choices=[
            ('cool', 'Cool'),
            ('heat', 'Heat'),
            ('fan', 'Fan'),
            ('auto', 'Auto'),
        ],
        default='cool'
    )
    ac_temperature = models.IntegerField(default=24, help_text="Temperature in Celsius")
    ac_fan_speed = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('auto', 'Auto'),
        ],
        default='auto'
    )
    
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Room Device State"
        verbose_name_plural = "Room Device States"

    def __str__(self):
        return f"Device State - Room {self.room.room_number}"


class ESP32ButtonConfig(models.Model):
    """Model to configure ESP32 button parameters for each room"""
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='esp32_config')
    
    # Front Light Button Configuration
    front_light_enabled = models.BooleanField(default=True, help_text="Enable/disable front light button")
    front_light_endpoint = models.CharField(max_length=100, default='/front_light', help_text="ESP32 endpoint for front light")
    front_light_parameter_name = models.CharField(max_length=50, default='tv', help_text="Parameter name for front light (e.g., tv, light, relay1)")
    front_light_on_command = models.CharField(max_length=50, default='on', help_text="Command to turn on front light")
    front_light_off_command = models.CharField(max_length=50, default='off', help_text="Command to turn off front light")
    
    # Back Light Button Configuration
    back_light_enabled = models.BooleanField(default=True, help_text="Enable/disable back light button")
    back_light_endpoint = models.CharField(max_length=100, default='/back_light', help_text="ESP32 endpoint for back light")
    back_light_parameter_name = models.CharField(max_length=50, default='tv', help_text="Parameter name for back light (e.g., tv, light, relay2)")
    back_light_on_command = models.CharField(max_length=50, default='on', help_text="Command to turn on back light")
    back_light_off_command = models.CharField(max_length=50, default='off', help_text="Command to turn off back light")
    
    # Main Light Button Configuration
    main_light_enabled = models.BooleanField(default=True, help_text="Enable/disable main light button")
    main_light_endpoint = models.CharField(max_length=100, default='/main_light', help_text="ESP32 endpoint for main light")
    main_light_parameter_name = models.CharField(max_length=50, default='main', help_text="Parameter name for main light (e.g., main, light, relay3)")
    main_light_on_command = models.CharField(max_length=50, default='on', help_text="Command to turn on main light")
    main_light_off_command = models.CharField(max_length=50, default='off', help_text="Command to turn off main light")
    
    # Sport Light Button Configuration
    sport_light_enabled = models.BooleanField(default=True, help_text="Enable/disable sport light button")
    sport_light_endpoint = models.CharField(max_length=100, default='/sport_light', help_text="ESP32 endpoint for sport light")
    sport_light_parameter_name = models.CharField(max_length=50, default='sport', help_text="Parameter name for sport light (e.g., sport, light, relay4)")
    sport_light_on_command = models.CharField(max_length=50, default='on', help_text="Command to turn on sport light")
    sport_light_off_command = models.CharField(max_length=50, default='off', help_text="Command to turn off sport light")
    
    # RGB Light Configuration
    rgb_light_enabled = models.BooleanField(default=True, help_text="Enable/disable RGB light controls")
    rgb_endpoint = models.CharField(max_length=100, default='/rgb', help_text="ESP32 endpoint for RGB light")
    
    # AC Configuration
    ac_enabled = models.BooleanField(default=True, help_text="Enable/disable AC controls")
    ac_endpoint = models.CharField(max_length=100, default='/ac', help_text="ESP32 endpoint for AC")
    
    # General ESP32 Settings
    status_endpoint = models.CharField(max_length=100, default='/status', help_text="ESP32 endpoint to get device status")
    timeout_seconds = models.IntegerField(default=5, help_text="Request timeout in seconds")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ESP32 Button Configuration"
        verbose_name_plural = "ESP32 Button Configurations"

    def __str__(self):
        return f"ESP32 Config - Room {self.room.room_number}"

    @classmethod
    def get_config_for_room(cls, room):
        """Get or create ESP32 configuration for a room"""
        config, created = cls.objects.get_or_create(
            room=room,
            defaults={
                'front_light_enabled': True,
                'front_light_endpoint': '/front_light',
                'front_light_on_command': 'on',
                'front_light_off_command': 'off',
                'back_light_enabled': True,
                'back_light_endpoint': '/back_light',
                'back_light_on_command': 'on',
                'back_light_off_command': 'off',
                'main_light_enabled': True,
                'main_light_endpoint': '/main_light',
                'main_light_on_command': 'on',
                'main_light_off_command': 'off',
                'sport_light_enabled': True,
                'sport_light_endpoint': '/sport_light',
                'sport_light_on_command': 'on',
                'sport_light_off_command': 'off',
                'rgb_light_enabled': True,
                'rgb_endpoint': '/rgb',
                'ac_enabled': True,
                'ac_endpoint': '/ac',
                'status_endpoint': '/status',
                'timeout_seconds': 5,
            }
        )
        return config


class AttractionInfo(models.Model):
    """Model to store information about local attractions"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(
        max_length=50,
        choices=[
            ('nature', 'Nature'),
            ('culture', 'Culture'),
            ('adventure', 'Adventure'),
            ('dining', 'Dining'),
            ('shopping', 'Shopping'),
            ('wellness', 'Wellness'),
        ]
    )
    distance_km = models.FloatField(help_text="Distance from hotel in kilometers")
    estimated_time = models.CharField(max_length=50, help_text="Estimated travel time")
    image_url = models.URLField(blank=True, help_text="URL to attraction image")
    website_url = models.URLField(blank=True, help_text="Official website URL")
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Display priority (higher numbers shown first)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attraction Info"
        verbose_name_plural = "Attraction Info"
        ordering = ['-priority', 'distance_km']

    def __str__(self):
        return f"{self.name} ({self.category})"


class TabletContent(models.Model):
    """Model to manage dynamic content displayed on tablets"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    content_type = models.CharField(
        max_length=20,
        choices=[
            ('welcome', 'Welcome Message'),
            ('announcement', 'Announcement'),
            ('promotion', 'Promotion'),
            ('service', 'Service Info'),
            ('emergency', 'Emergency Info'),
        ]
    )
    target_rooms = models.ManyToManyField(Room, blank=True, help_text="Leave empty to show on all tablets")
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0, help_text="Display priority (higher numbers shown first)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tablet Content"
        verbose_name_plural = "Tablet Content"
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.content_type})"

    def is_currently_active(self):
        """Check if content should be displayed based on date range"""
        from django.utils import timezone
        now = timezone.now()
        
        if not self.is_active:
            return False
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True