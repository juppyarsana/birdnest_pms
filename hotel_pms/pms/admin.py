from django.contrib import admin
from .models import Room, Guest, Reservation
from django.contrib.humanize.templatetags.humanize import intcomma

class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'display_rate', 'status')

    def display_rate(self, obj):
        return f"Rp {intcomma(obj.rate)}"
    display_rate.short_description = 'Rate'

admin.site.register(Room, RoomAdmin)
admin.site.register(Guest)
admin.site.register(Reservation)