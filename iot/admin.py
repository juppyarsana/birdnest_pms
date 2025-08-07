from django.contrib import admin
from .models import ESP32Device, RoomControls, DeviceLog

@admin.register(ESP32Device)
class ESP32DeviceAdmin(admin.ModelAdmin):
    list_display = ['room', 'ip_address', 'is_online', 'last_seen', 'firmware_version']
    list_filter = ['is_online', 'created_at']
    search_fields = ['room__room_number', 'ip_address', 'mac_address']
    readonly_fields = ['last_seen', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Room Information', {
            'fields': ('room',)
        }),
        ('Device Configuration', {
            'fields': ('ip_address', 'mac_address', 'firmware_version')
        }),
        ('Status', {
            'fields': ('is_online', 'last_seen')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(RoomControls)
class RoomControlsAdmin(admin.ModelAdmin):
    list_display = ['room', 'current_preset', 'main_light_on', 'rgb_light_on', 'ac_on', 'updated_at']
    list_filter = ['current_preset', 'main_light_on', 'rgb_light_on', 'ac_on']
    search_fields = ['room__room_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Room Information', {
            'fields': ('room', 'current_preset')
        }),
        ('Lighting Controls', {
            'fields': ('main_light_on', 'reading_light_on', 'bedside_light_on')
        }),
        ('RGB Lighting', {
            'fields': ('rgb_light_on', 'rgb_brightness', 'rgb_red', 'rgb_green', 'rgb_blue')
        }),
        ('Air Conditioning', {
            'fields': ('ac_on', 'ac_temperature', 'ac_mode', 'ac_fan_speed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(DeviceLog)
class DeviceLogAdmin(admin.ModelAdmin):
    list_display = ['room', 'command', 'success', 'timestamp']
    list_filter = ['success', 'timestamp', 'room']
    search_fields = ['room__room_number', 'command']
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be modified
