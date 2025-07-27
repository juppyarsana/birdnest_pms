from django.contrib import admin
from .models import (
    Room, Guest, Reservation, HotelSettings, Nationality, PaymentMethod, Agent,
    EmailNotificationSettings, EmailLog, TabletDevice, RoomDeviceState, 
    AttractionInfo, TabletContent, ESP32ButtonConfig
)
from django.contrib.humanize.templatetags.humanize import intcomma

class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'display_rate', 'status')

    def display_rate(self, obj):
        return f"Rp {intcomma(obj.rate)}"
    display_rate.short_description = 'Rate'

class NationalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    list_editable = ('is_active',)
    ordering = ('name',)

class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'display_order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'display_order', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', 'name')

class GuestAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'get_nationality', 'id_type', 'id_number')
    search_fields = ('name', 'email', 'phone', 'nationality__name', 'id_number')
    list_filter = ('nationality', 'id_type')
    
    def get_nationality(self, obj):
        return obj.nationality.name if obj.nationality else '-'
    get_nationality.short_description = 'Nationality'
    get_nationality.admin_order_field = 'nationality__name'

class ReservationAdmin(admin.ModelAdmin):
    list_display = ('guest', 'room', 'check_in', 'check_out', 'agent', 'status')
    list_filter = ('status', 'agent', 'check_in', 'check_out')
    search_fields = ('guest__name', 'room__room_number')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Update status for all reservations before displaying
        for reservation in queryset:
            reservation.update_status()
        return queryset

class HotelSettingsAdmin(admin.ModelAdmin):
    list_display = ('get_check_in_window', 'check_in_grace_period')
    
    def get_check_in_window(self, obj):
        return f"{obj.earliest_check_in_time.strftime('%I:%M %p')} - {obj.latest_check_in_time.strftime('%I:%M %p')}"
    get_check_in_window.short_description = 'Check-in Window'

    def has_add_permission(self, request):
        # Only allow one settings instance
        return not HotelSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the settings
        return False


class EmailNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'email_notifications_enabled', 'hotel_name', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Global Settings', {
            'fields': ('email_notifications_enabled',)
        }),
        ('Notification Types', {
            'fields': (
                'send_pending_notifications',
                'send_confirmed_notifications', 
                'send_expected_arrival_notifications',
                'send_expected_departure_notifications'
            )
        }),
        ('Hotel Information', {
            'fields': ('hotel_name', 'hotel_contact', 'hotel_address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not EmailNotificationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the settings
        return False


class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'notification_type', 'recipient_email', 'status', 'sent_at')
    list_filter = ('status', 'notification_type', 'sent_at')
    search_fields = ('reservation__guest__name', 'recipient_email', 'reservation__room__room_number')
    readonly_fields = ('reservation', 'notification_type', 'recipient_email', 'status', 'error_message', 'sent_at')
    ordering = ('-sent_at',)
    
    def has_add_permission(self, request):
        # Email logs are created automatically
        return False
    
    def has_change_permission(self, request, obj=None):
        # Email logs should not be editable
        return False


# Tablet and IoT Device Admin
class TabletDeviceAdmin(admin.ModelAdmin):
    list_display = ('tablet_id', 'room', 'esp32_ip', 'is_active', 'last_ping', 'created_at')
    list_filter = ('is_active', 'created_at', 'last_ping')
    search_fields = ('tablet_id', 'room__room_number', 'esp32_ip')
    list_editable = ('is_active',)
    readonly_fields = ('last_ping', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('room', 'tablet_id', 'esp32_ip', 'is_active')
        }),
        ('Status', {
            'fields': ('last_ping',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class RoomDeviceStateAdmin(admin.ModelAdmin):
    list_display = ('room', 'get_lights_status', 'get_rgb_status', 'get_ac_status', 'last_updated')
    list_filter = ('last_updated', 'ac_power', 'rgb_light')
    search_fields = ('room__room_number',)
    readonly_fields = ('last_updated',)
    
    fieldsets = (
        ('Room', {
            'fields': ('room',)
        }),
        ('Lighting Controls', {
            'fields': ('front_light', 'back_light', 'main_light', 'sport_light')
        }),
        ('RGB Lighting', {
            'fields': ('rgb_light', 'rgb_color', 'rgb_brightness')
        }),
        ('Air Conditioning', {
            'fields': ('ac_power', 'ac_mode', 'ac_temperature', 'ac_fan_speed')
        }),
        ('Status', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )
    
    def get_lights_status(self, obj):
        lights = []
        if obj.front_light: lights.append('Front')
        if obj.back_light: lights.append('Back')
        if obj.main_light: lights.append('Main')
        if obj.sport_light: lights.append('Sport')
        return ', '.join(lights) if lights else 'All Off'
    get_lights_status.short_description = 'Active Lights'
    
    def get_rgb_status(self, obj):
        if obj.rgb_light:
            return f"ON ({obj.rgb_color}, {obj.rgb_brightness}%)"
        return "OFF"
    get_rgb_status.short_description = 'RGB Status'
    
    def get_ac_status(self, obj):
        if obj.ac_power:
            return f"ON ({obj.ac_mode.upper()}, {obj.ac_temperature}°C)"
        return "OFF"
    get_ac_status.short_description = 'AC Status'


class AttractionInfoAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'distance_km', 'estimated_time', 'priority', 'is_active')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('priority', 'is_active')
    ordering = ('-priority', 'distance_km')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'category', 'is_active', 'priority')
        }),
        ('Location & Timing', {
            'fields': ('distance_km', 'estimated_time')
        }),
        ('Media & Links', {
            'fields': ('image_url', 'website_url')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ESP32ButtonConfig)
class ESP32ButtonConfigAdmin(admin.ModelAdmin):
    list_display = ['room', 'front_light_enabled', 'back_light_enabled', 'main_light_enabled', 'sport_light_enabled']
    list_filter = ['front_light_enabled', 'back_light_enabled', 'main_light_enabled', 'sport_light_enabled']
    search_fields = ['room__room_number']
    
    fieldsets = (
        ('Room', {
            'fields': ('room',)
        }),
        ('Front Light Configuration', {
            'fields': (
                'front_light_enabled',
                'front_light_endpoint',
                'front_light_parameter_name',
                'front_light_on_command',
                'front_light_off_command'
            ),
            'classes': ('collapse',)
        }),
        ('Back Light Configuration', {
            'fields': (
                'back_light_enabled',
                'back_light_endpoint',
                'back_light_parameter_name',
                'back_light_on_command',
                'back_light_off_command'
            ),
            'classes': ('collapse',)
        }),
        ('Main Light Configuration', {
            'fields': (
                'main_light_enabled',
                'main_light_endpoint',
                'main_light_parameter_name',
                'main_light_on_command',
                'main_light_off_command'
            ),
            'classes': ('collapse',)
        }),
        ('Sport Light Configuration', {
            'fields': (
                'sport_light_enabled',
                'sport_light_endpoint',
                'sport_light_parameter_name',
                'sport_light_on_command',
                'sport_light_off_command'
            ),
            'classes': ('collapse',)
        }),
        ('RGB Light Configuration', {
            'fields': ('rgb_light_enabled', 'rgb_endpoint'),
            'classes': ('collapse',)
        }),
        ('AC Configuration', {
            'fields': ('ac_enabled', 'ac_endpoint'),
            'classes': ('collapse',)
        }),
        ('General Settings', {
            'fields': ('status_endpoint', 'timeout_seconds'),
            'classes': ('collapse',)
        }),
    )
    
    def get_enabled_buttons(self, obj):
        enabled = []
        if obj.front_light_enabled: enabled.append('Front Light')
        if obj.back_light_enabled: enabled.append('Back Light')
        if obj.main_light_enabled: enabled.append('Main Light')
        if obj.sport_light_enabled: enabled.append('Sport Light')
        if obj.rgb_light_enabled: enabled.append('RGB')
        if obj.ac_enabled: enabled.append('AC')
        return ', '.join(enabled) if enabled else 'None'
    get_enabled_buttons.short_description = 'Enabled Controls'


class TabletContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'get_target_rooms', 'is_active', 'priority', 'created_at')
    list_filter = ('content_type', 'is_active', 'created_at', 'start_date', 'end_date')
    search_fields = ('title', 'content')
    list_editable = ('priority', 'is_active')
    filter_horizontal = ('target_rooms',)
    ordering = ('-priority', '-created_at')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'content', 'content_type', 'is_active', 'priority')
        }),
        ('Targeting', {
            'fields': ('target_rooms',),
            'description': 'Leave empty to show on all tablets'
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date'),
            'description': 'Optional: Set date range for when this content should be displayed'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_target_rooms(self, obj):
        rooms = obj.target_rooms.all()
        if rooms:
            return ', '.join([room.room_number for room in rooms[:3]]) + ('...' if rooms.count() > 3 else '')
        return 'All Rooms'
    get_target_rooms.short_description = 'Target Rooms'


admin.site.register(Room, RoomAdmin)
admin.site.register(Nationality, NationalityAdmin)
admin.site.register(PaymentMethod, PaymentMethodAdmin)
admin.site.register(Agent, AgentAdmin)
admin.site.register(Guest, GuestAdmin)
admin.site.register(Reservation, ReservationAdmin)
admin.site.register(HotelSettings, HotelSettingsAdmin)
admin.site.register(EmailNotificationSettings, EmailNotificationSettingsAdmin)
admin.site.register(EmailLog, EmailLogAdmin)

# Register tablet models
admin.site.register(TabletDevice, TabletDeviceAdmin)
admin.site.register(RoomDeviceState, RoomDeviceStateAdmin)
admin.site.register(AttractionInfo, AttractionInfoAdmin)
admin.site.register(TabletContent, TabletContentAdmin)