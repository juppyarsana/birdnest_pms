from django.db import models

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