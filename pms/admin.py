from django.contrib import admin
from .models import Room, Guest, Reservation, HotelSettings, Nationality, PaymentMethod, Agent
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

admin.site.register(Room, RoomAdmin)
admin.site.register(Nationality, NationalityAdmin)
admin.site.register(PaymentMethod, PaymentMethodAdmin)
admin.site.register(Agent, AgentAdmin)
admin.site.register(Guest, GuestAdmin)
admin.site.register(Reservation, ReservationAdmin)
admin.site.register(HotelSettings, HotelSettingsAdmin)