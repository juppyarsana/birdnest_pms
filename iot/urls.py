from django.urls import path
from . import views

app_name = 'iot'

urlpatterns = [
    # Landing page for room access
    path('', views.room_access, name='room_access'),
    
    # Main tablet interface
    path('room/<str:room_number>/', views.room_control, name='room_control'),
    path('room/<str:room_number>/config/', views.esp32_configuration, name='esp32_configuration'),
    
    # API endpoints
    path('api/room/<str:room_number>/devices/', views.get_device_states, name='device_states'),
    path('api/room/<str:room_number>/control/', views.control_device, name='control_device'),
    path('api/room/<str:room_number>/preset/', views.apply_preset, name='apply_preset'),
]