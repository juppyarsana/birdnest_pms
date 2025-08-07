from django.urls import path
from . import views

app_name = 'iot'

urlpatterns = [
    # Main landing page - redirects to smart interface
    path('', views.smart_room_access, name='room_access'),
    
    # Legacy room access page (backup)
    path('legacy/', views.room_access, name='legacy_room_access'),
    
    # Smart room access page (new modern UI)
    path('smart/', views.smart_room_access, name='smart_room_access'),
    path('smart/<str:room_number>/', views.smart_room_control, name='smart_room_control_room'),
    path('smart/<str:room_number>/config/', views.smart_room_config, name='smart_room_config'),
    
    # Main tablet interface (existing)
    path('room/<str:room_number>/', views.room_control, name='room_control'),
    path('room/<str:room_number>/config/', views.esp32_configuration, name='esp32_configuration'),
    
    # API endpoints
    path('api/room/<str:room_number>/devices/', views.get_device_states, name='device_states'),
    path('api/room/<str:room_number>/control/', views.control_device, name='control_device'),
    path('api/room/<str:room_number>/preset/', views.apply_preset, name='apply_preset'),
]