from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.db import models
from datetime import date
import json
import logging
from .models import Room, Reservation, TabletDevice, RoomDeviceState, AttractionInfo, TabletContent
from .tablet_service import ESP32Controller, TabletService

def hex_to_rgb(hex_color):
    """Convert hex color to RGB values"""
    if not hex_color or hex_color == '#000000':
        return 0, 0, 0
    
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return 0, 0, 0
    
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return 0, 0, 0

def get_weather_info():
    """Get weather information - placeholder implementation"""
    # TODO: Implement actual weather API integration
    return {
        'temperature': '24°C',
        'condition': 'Partly Cloudy',
        'humidity': '65%',
        'location': 'Kintamani, Bali'
    }

class TabletView(View):
    """Main tablet interface view"""
    
    def get(self, request, room_number):
        """Render tablet interface for specific room"""
        room = get_object_or_404(Room, room_number=room_number)
        tablet = TabletService.get_room_tablet(room)
        
        if not tablet:
            return render(request, 'tablet/no_device.html', {'room': room})
        
        # Get current reservation
        current_reservation = room.reservation_set.filter(
            check_in__lte=date.today(),
            check_out__gt=date.today(),
            status__in=['in_house', 'expected_departure']
        ).first()
        
        # Get device state
        device_state = TabletService.get_device_state(tablet)
        
        # Get attractions
        attractions = AttractionInfo.objects.filter(is_active=True).order_by('category', '-priority')
        attractions_by_category = {}
        for attraction in attractions:
            if attraction.category not in attractions_by_category:
                attractions_by_category[attraction.category] = []
            attractions_by_category[attraction.category].append(attraction)
        
        # Get tablet content
        today = date.today()
        tablet_content = TabletContent.objects.filter(
            is_active=True
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=today)
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).order_by('-priority', '-created_at')
        
        # Get ESP32 configuration for dynamic parameter names
        from .models import ESP32ButtonConfig
        esp32_config = ESP32ButtonConfig.get_config_for_room(room)
        
        context = {
            'room': room,
            'tablet': tablet,
            'current_reservation': current_reservation,
            'device_state': device_state,
            'attractions_by_category': attractions_by_category,
            'tablet_content': tablet_content,
            'esp32_config': esp32_config,
            'guest_name': current_reservation.guest.name if current_reservation else None,
            'check_out_date': current_reservation.check_out if current_reservation else None,
            'weather_info': get_weather_info(),  # We'll implement this
        }
        
        return render(request, 'tablet/main_interface.html', context)

@method_decorator(csrf_exempt, name='dispatch')
class DeviceControlAPI(View):
    """API for controlling room devices"""
    
    def post(self, request, room_number):
        """Handle device control commands"""
        try:
            room = get_object_or_404(Room, room_number=room_number)
            tablet = TabletService.get_room_tablet(room)
            
            if not tablet:
                return JsonResponse({'success': False, 'message': 'No tablet device found for this room'})
            
            data = json.loads(request.body)
            device_type = data.get('device_type')
            
            if device_type == 'light':
                success, message, state = TabletService.update_device_state(
                    tablet, 
                    'light',
                    light_type=data.get('light_type'),
                    state=data.get('state')
                )
                
            elif device_type == 'rgb':
                success, message, state = TabletService.update_device_state(
                    tablet,
                    'rgb',
                    power=data.get('power'),
                    red=data.get('red'),
                    green=data.get('green'),
                    blue=data.get('blue'),
                    brightness=data.get('brightness')
                )
                
            elif device_type == 'ac':
                success, message, state = TabletService.update_device_state(
                    tablet,
                    'ac',
                    power=data.get('power'),
                    mode=data.get('mode'),
                    temperature=data.get('temperature'),
                    fan_speed=data.get('fan_speed')
                )
            else:
                return JsonResponse({'success': False, 'message': 'Invalid device type'})
            
            # Convert RGB color for response
            rgb_red, rgb_green, rgb_blue = hex_to_rgb(state.rgb_color)
            
            return JsonResponse({
                'success': success,
                'message': message,
                'device_state': {
                    'front_light': state.front_light,
                    'back_light': state.back_light,
                    'main_light': state.main_light,
                    'sport_light': state.sport_light,
                    'rgb_light_on': state.rgb_light,
                    'rgb_red': rgb_red,
                    'rgb_green': rgb_green,
                    'rgb_blue': rgb_blue,
                    'rgb_brightness': state.rgb_brightness,
                    'ac_power': state.ac_power,
                    'ac_mode': state.ac_mode,
                    'ac_temperature': state.ac_temperature,
                    'ac_fan_speed': state.ac_fan_speed,
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

@require_http_methods(["GET"])
def esp32_status_api(request, room_number):
    """Get current ESP32 device status directly from hardware"""
    try:
        room = get_object_or_404(Room, room_number=room_number)
        tablet = TabletService.get_room_tablet(room)
        
        if not tablet:
            return JsonResponse({'success': False, 'message': 'No tablet device found'})
        
        from .tablet_service import ESP32Controller
        controller = ESP32Controller(tablet)
        
        # Get status from ESP32
        success, esp32_state = controller.get_device_state_esp32()
        
        if success:
            return JsonResponse({
                'success': True,
                'esp32_state': esp32_state,
                'esp32_ip': tablet.esp32_ip,
                'last_ping': tablet.last_ping.isoformat() if tablet.last_ping else None
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': f'Failed to get ESP32 status: {esp32_state}',
                'esp32_ip': tablet.esp32_ip
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_http_methods(["GET"])
def device_status_api(request, room_number):
    """Get current device status"""
    try:
        room = get_object_or_404(Room, room_number=room_number)
        tablet = TabletService.get_room_tablet(room)
        
        if not tablet:
            return JsonResponse({'success': False, 'message': 'No tablet device found'})
        
        device_state = TabletService.get_device_state(tablet)
        
        # Convert RGB color for response
        rgb_red, rgb_green, rgb_blue = hex_to_rgb(device_state.rgb_color)
        
        return JsonResponse({
            'success': True,
            'device_state': {
                'front_light': device_state.front_light,
                'back_light': device_state.back_light,
                'main_light': device_state.main_light,
                'sport_light': device_state.sport_light,
                'rgb_light_on': device_state.rgb_light,
                'rgb_red': rgb_red,
                'rgb_green': rgb_green,
                'rgb_blue': rgb_blue,
                'rgb_brightness': device_state.rgb_brightness,
                'ac_power': device_state.ac_power,
                'ac_mode': device_state.ac_mode,
                'ac_temperature': device_state.ac_temperature,
                'ac_fan_speed': device_state.ac_fan_speed,
                'last_updated': device_state.last_updated.isoformat(),
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_http_methods(["GET"])
def guest_info_api(request, room_number):
    """Get current guest information for the room"""
    try:
        room = get_object_or_404(Room, room_number=room_number)
        
        # Get current reservation
        current_reservation = room.reservation_set.filter(
            check_in__lte=date.today(),
            check_out__gt=date.today(),
            status__in=['in_house', 'expected_departure']
        ).first()
        
        if not current_reservation:
            return JsonResponse({
                'success': True,
                'has_guest': False,
                'message': 'No current guest in this room'
            })
        
        guest = current_reservation.guest
        
        return JsonResponse({
            'success': True,
            'has_guest': True,
            'guest_info': {
                'name': guest.name,
                'check_in': current_reservation.check_in.isoformat(),
                'check_out': current_reservation.check_out.isoformat(),
                'nights': (current_reservation.check_out - current_reservation.check_in).days,
                'room_type': room.get_room_type_display(),
                'total_amount': float(current_reservation.total_amount),
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_http_methods(["GET"])
def attractions_api(request):
    """Get local attractions information"""
    try:
        attractions = AttractionInfo.objects.filter(is_active=True).order_by('category', '-priority')
        
        attractions_data = []
        for attraction in attractions:
            attractions_data.append({
                'name': attraction.name,
                'category': attraction.category,
                'description': attraction.description,
                'distance_km': float(attraction.distance_km),
                'estimated_duration': attraction.estimated_duration,
                'contact_info': attraction.contact_info,
                'website': attraction.website,
                'price_range': attraction.price_range,
                'opening_hours': attraction.opening_hours,
                'tips': attraction.tips,
            })
        
        return JsonResponse({
            'success': True,
            'attractions': attractions_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})