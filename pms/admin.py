from django.contrib import admin
from .models import Room, Guest, Reservation, HotelSettings
from django.contrib.humanize.templatetags.humanize import intcomma

class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'display_rate', 'status')

    def display_rate(self, obj):
        return f"Rp {intcomma(obj.rate)}"
    display_rate.short_description = 'Rate'

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

admin.site.register(Room, RoomAdmin)
admin.site.register(Guest)
admin.site.register(Reservation)
admin.site.register(HotelSettings, HotelSettingsAdmin)