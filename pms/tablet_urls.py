# Tablet URLs
from django.urls import path
from . import tablet_views

tablet_urlpatterns = [
    # Main tablet interface
    path('tablet/<str:room_number>/', tablet_views.TabletView.as_view(), name='tablet_interface'),
    
    # API endpoints for device control
    path('tablet/api/control/<str:room_number>/', tablet_views.DeviceControlAPI.as_view(), name='tablet_device_control'),
    path('tablet/api/status/<str:room_number>/', tablet_views.device_status_api, name='tablet_device_status'),
    path('tablet/api/esp32-status/<str:room_number>/', tablet_views.esp32_status_api, name='tablet_esp32_status'),
    path('tablet/api/guest/<str:room_number>/', tablet_views.guest_info_api, name='tablet_guest_info'),
    path('tablet/api/attractions/', tablet_views.attractions_api, name='tablet_attractions'),
]