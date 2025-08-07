from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from pms.models import Room, Reservation
from .models import ESP32Device, RoomControls, DeviceLog, ESP32Configuration
import json
from django.contrib import messages
from django.shortcuts import redirect

def room_access(request):
    """Landing page for room access (old interface)"""
    return render(request, 'iot/room_access.html')

def smart_room_access(request):
    """Smart room access page with modern UI"""
    return render(request, 'iot/smart_room_access.html')

def smart_room_control(request, room_number=None):
    """Smart room control interface with modern UI"""
    if room_number:
        room = get_object_or_404(Room, room_number=room_number)
        # Get current guest info if room is occupied
        current_reservation = None
        guest_name = "Guest"
        
        if room.status == 'occupied':
            current_reservation = Reservation.objects.filter(
                room=room, 
                status='in_house'
            ).first()
            if current_reservation:
                guest_name = current_reservation.guest.name
                
        # Get ESP32 device and configuration for direct control
        esp32, created = ESP32Device.objects.get_or_create(
            room=room,
            defaults={'ip_address': '192.168.1.100'}
        )
        config, created = ESP32Configuration.objects.get_or_create(esp32_device=esp32)
    else:
        # Demo mode - no specific room
        room = None
        guest_name = "Guest Name"
        current_reservation = None
        esp32 = None
        config = None
    
    context = {
        'room': room,
        'room_number': room_number or 'demo',
        'guest_name': guest_name,
        'current_reservation': current_reservation,
        'esp32': esp32,
        'config': config,
    }
    return render(request, 'iot/smart_room_control.html', context)

def room_control(request, room_number):
    """Main tablet interface for room controls"""
    room = get_object_or_404(Room, room_number=room_number)
    controls, created = RoomControls.objects.get_or_create(room=room)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={'ip_address': '192.168.1.100'}  # Default IP, should be configured
    )
    
    # Get current guest info if room is occupied
    current_reservation = None
    guest_name = "Guest"
    
    if room.status == 'occupied':
        current_reservation = Reservation.objects.filter(
            room=room, 
            status='in_house'
        ).first()
        if current_reservation:
            guest_name = current_reservation.guest.name.split()[0]  # First name only
    
    # Get recent device logs
    recent_logs = DeviceLog.objects.filter(room=room)[:10]
    
    context = {
        'room': room,
        'controls': controls,
        'esp32': esp32,
        'current_reservation': current_reservation,
        'guest_name': guest_name,
        'recent_logs': recent_logs,
        'preset_choices': RoomControls._meta.get_field('current_preset').choices,
    }
    return render(request, 'iot/room_control.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def control_device(request, room_number):
    """API endpoint to control devices"""
    room = get_object_or_404(Room, room_number=room_number)
    controls, created = RoomControls.objects.get_or_create(room=room)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={
            'ip_address': '10.207.155.39',  # Updated to your ESP32 IP
            'auth_username': 'admin',
            'auth_password': 'orcatech'
        }
    )
    
    try:
        data = json.loads(request.body)
        device_type = data.get('device_type')
        action = data.get('action')
        value = data.get('value')
        
        success = False
        response_data = {}
        command_sent = ""
        
        if device_type == 'main_light':
            if action == 'toggle':
                controls.main_light_on = not controls.main_light_on
                endpoint = f"light/main/{'on' if controls.main_light_on else 'off'}"
                command_sent = f"Main Light {'ON' if controls.main_light_on else 'OFF'}"
                success, response_data = esp32.send_command(endpoint)
                
        elif device_type == 'rgb_light':
            if action == 'toggle':
                controls.rgb_light_on = not controls.rgb_light_on
                endpoint = f"light/rgb/{'on' if controls.rgb_light_on else 'off'}"
                command_sent = f"RGB Light {'ON' if controls.rgb_light_on else 'OFF'}"
                success, response_data = esp32.send_command(endpoint)
            elif action == 'color':
                controls.rgb_red = value.get('red', controls.rgb_red)
                controls.rgb_green = value.get('green', controls.rgb_green)
                controls.rgb_blue = value.get('blue', controls.rgb_blue)
                controls.rgb_brightness = value.get('brightness', controls.rgb_brightness)
                endpoint = "light/rgb/color"
                color_data = {
                    'red': controls.rgb_red,
                    'green': controls.rgb_green,
                    'blue': controls.rgb_blue,
                    'brightness': controls.rgb_brightness
                }
                command_sent = f"RGB Color: R{controls.rgb_red} G{controls.rgb_green} B{controls.rgb_blue} Brightness{controls.rgb_brightness}%"
                success, response_data = esp32.send_command(endpoint, color_data)
                
        elif device_type == 'ac':
            if action == 'toggle':
                controls.ac_on = not controls.ac_on
                endpoint = "ac/power"
                ac_data = {'power': controls.ac_on}
                command_sent = f"AC {'ON' if controls.ac_on else 'OFF'}"
                success, response_data = esp32.send_command(endpoint, ac_data)
            elif action == 'temperature':
                controls.ac_temperature = value
                endpoint = "ac/temperature"
                temp_data = {'temperature': controls.ac_temperature}
                command_sent = f"AC Temperature: {controls.ac_temperature}°C"
                success, response_data = esp32.send_command(endpoint, temp_data)
                
        elif device_type == 'reading_light':
            if action == 'toggle':
                controls.reading_light_on = not controls.reading_light_on
                endpoint = f"light/reading/{'on' if controls.reading_light_on else 'off'}"
                command_sent = f"Reading Light {'ON' if controls.reading_light_on else 'OFF'}"
                success, response_data = esp32.send_command(endpoint)
                
        elif device_type == 'bedside_light':
            if action == 'toggle':
                controls.bedside_light_on = not controls.bedside_light_on
                endpoint = f"light/bedside/{'on' if controls.bedside_light_on else 'off'}"
                command_sent = f"Bedside Light {'ON' if controls.bedside_light_on else 'OFF'}"
                success, response_data = esp32.send_command(endpoint)
        
        elif device_type == 'locker':
            if action == 'open':
                locker_number = value.get('locker_number', 1) if isinstance(value, dict) else 1
                endpoint = f"open/{locker_number}"
                command_sent = f"Open Locker {locker_number}"
                success, response_data = esp32.send_command(endpoint)
        
        # Log the command
        DeviceLog.objects.create(
            room=room,
            command=command_sent,
            success=success,
            response_data=response_data if success else None,
            error_message=response_data.get('error', '') if not success else ''
        )
        
        if success:
            controls.save()
            
        return JsonResponse({
            'success': success,
            'data': response_data,
            'command': command_sent,
            'current_state': {
                'main_light_on': controls.main_light_on,
                'rgb_light_on': controls.rgb_light_on,
                'rgb_color': controls.get_rgb_hex_color(),
                'rgb_brightness': controls.rgb_brightness,
                'ac_on': controls.ac_on,
                'ac_temperature': controls.ac_temperature,
                'reading_light_on': controls.reading_light_on,
                'bedside_light_on': controls.bedside_light_on,
                'current_preset': controls.current_preset,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def apply_preset(request, room_number):
    """Apply preset configuration"""
    room = get_object_or_404(Room, room_number=room_number)
    controls, created = RoomControls.objects.get_or_create(room=room)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={'ip_address': '192.168.1.100'}
    )
    
    try:
        data = json.loads(request.body)
        preset_name = data.get('preset')
        
        if controls.apply_preset(preset_name):
            # Send all commands to ESP32 based on preset
            commands = []
            
            if preset_name == 'dark':
                commands = [
                    ('light/main/off', None, 'Main Light OFF'),
                    ('light/rgb/color', {'red': 50, 'green': 50, 'blue': 100, 'brightness': 10}, 'RGB Dark Blue'),
                    ('light/reading/off', None, 'Reading Light OFF'),
                    ('light/bedside/off', None, 'Bedside Light OFF')
                ]
            elif preset_name == 'gloom':
                commands = [
                    ('light/main/off', None, 'Main Light OFF'),
                    ('light/rgb/color', {'red': 100, 'green': 100, 'blue': 100, 'brightness': 30}, 'RGB Dim White'),
                    ('light/reading/off', None, 'Reading Light OFF'),
                    ('light/bedside/on', None, 'Bedside Light ON')
                ]
            elif preset_name == 'reading':
                commands = [
                    ('light/main/on', None, 'Main Light ON'),
                    ('light/rgb/off', None, 'RGB Light OFF'),
                    ('light/reading/on', None, 'Reading Light ON'),
                    ('light/bedside/off', None, 'Bedside Light OFF')
                ]
            elif preset_name == 'bedside':
                commands = [
                    ('light/main/off', None, 'Main Light OFF'),
                    ('light/rgb/color', {'red': 255, 'green': 200, 'blue': 100, 'brightness': 20}, 'RGB Warm White'),
                    ('light/reading/off', None, 'Reading Light OFF'),
                    ('light/bedside/on', None, 'Bedside Light ON')
                ]
            elif preset_name == 'normal':
                commands = [
                    ('light/main/on', None, 'Main Light ON'),
                    ('light/rgb/off', None, 'RGB Light OFF'),
                    ('light/reading/off', None, 'Reading Light OFF'),
                    ('light/bedside/off', None, 'Bedside Light OFF')
                ]
            
            success_count = 0
            failed_commands = []
            
            for endpoint, cmd_data, description in commands:
                success, response = esp32.send_command(endpoint, cmd_data)
                
                # Log each command
                DeviceLog.objects.create(
                    room=room,
                    command=f"Preset {preset_name.title()}: {description}",
                    success=success,
                    response_data=response if success else None,
                    error_message=response.get('error', '') if not success else ''
                )
                
                if success:
                    success_count += 1
                else:
                    failed_commands.append(description)
            
            return JsonResponse({
                'success': success_count == len(commands),
                'preset': preset_name,
                'commands_sent': success_count,
                'total_commands': len(commands),
                'failed_commands': failed_commands,
                'current_state': {
                    'main_light_on': controls.main_light_on,
                    'rgb_light_on': controls.rgb_light_on,
                    'rgb_color': controls.get_rgb_hex_color(),
                    'rgb_brightness': controls.rgb_brightness,
                    'ac_on': controls.ac_on,
                    'ac_temperature': controls.ac_temperature,
                    'reading_light_on': controls.reading_light_on,
                    'bedside_light_on': controls.bedside_light_on,
                    'current_preset': controls.current_preset,
                }
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid preset'}, status=400)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def get_device_states(request, room_number):
    """Get current device states"""
    room = get_object_or_404(Room, room_number=room_number)
    controls, created = RoomControls.objects.get_or_create(room=room)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={'ip_address': '192.168.1.100'}
    )
    
    # Get live status from ESP32 (optional)
    live_status = esp32.get_status()
    
    return JsonResponse({
        'room_number': room.room_number,
        'room_type': room.get_room_type_display(),
        'controls': {
            'main_light_on': controls.main_light_on,
            'rgb_light_on': controls.rgb_light_on,
            'rgb_color': {
                'red': controls.rgb_red,
                'green': controls.rgb_green,
                'blue': controls.rgb_blue,
                'hex': controls.get_rgb_hex_color(),
                'brightness': controls.rgb_brightness
            },
            'ac_on': controls.ac_on,
            'ac_temperature': controls.ac_temperature,
            'ac_mode': controls.ac_mode,
            'ac_fan_speed': controls.ac_fan_speed,
            'reading_light_on': controls.reading_light_on,
            'bedside_light_on': controls.bedside_light_on,
            'current_preset': controls.current_preset,
        },
        'esp32_online': esp32.is_online,
        'esp32_last_seen': esp32.last_seen.isoformat() if esp32.last_seen else None,
        'live_status': live_status
    })


def esp32_configuration(request, room_number):
    """Configuration page for ESP32 device endpoints"""
    room = get_object_or_404(Room, room_number=room_number)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={
            'ip_address': '192.168.1.100'
        }
    )
    config, created = ESP32Configuration.objects.get_or_create(esp32_device=esp32)
    
    if request.method == 'POST':
        import json as json_module
        
        # Update ESP32 device settings
        esp32.ip_address = request.POST.get('ip_address', esp32.ip_address)
        esp32.auth_username = request.POST.get('auth_username', esp32.auth_username)
        esp32.auth_password = request.POST.get('auth_password', esp32.auth_password)
        esp32.save()
        
        # Helper function to parse JSON data
        def parse_json_field(field_name, default={}):
            try:
                data = request.POST.get(field_name, '{}')
                return json_module.loads(data) if data.strip() else default
            except json_module.JSONDecodeError:
                return default
        
        # Update configuration
        config.main_light_on_endpoint = request.POST.get('main_light_on_endpoint', config.main_light_on_endpoint)
        config.main_light_off_endpoint = request.POST.get('main_light_off_endpoint', config.main_light_off_endpoint)
        config.main_light_post_data = parse_json_field('main_light_post_data', config.main_light_post_data)
        
        config.rgb_light_on_endpoint = request.POST.get('rgb_light_on_endpoint', config.rgb_light_on_endpoint)
        config.rgb_light_off_endpoint = request.POST.get('rgb_light_off_endpoint', config.rgb_light_off_endpoint)
        config.rgb_light_color_endpoint = request.POST.get('rgb_light_color_endpoint', config.rgb_light_color_endpoint)
        config.rgb_light_post_data = parse_json_field('rgb_light_post_data', config.rgb_light_post_data)
        
        config.ac_power_endpoint = request.POST.get('ac_power_endpoint', config.ac_power_endpoint)
        config.ac_temperature_endpoint = request.POST.get('ac_temperature_endpoint', config.ac_temperature_endpoint)
        config.ac_mode_endpoint = request.POST.get('ac_mode_endpoint', config.ac_mode_endpoint)
        config.ac_post_data = parse_json_field('ac_post_data', config.ac_post_data)
        
        config.locker_endpoint = request.POST.get('locker_endpoint', config.locker_endpoint)
        config.locker_post_data = parse_json_field('locker_post_data', config.locker_post_data)
        
        config.reading_light_on_endpoint = request.POST.get('reading_light_on_endpoint', config.reading_light_on_endpoint)
        config.reading_light_off_endpoint = request.POST.get('reading_light_off_endpoint', config.reading_light_off_endpoint)
        config.reading_light_post_data = parse_json_field('reading_light_post_data', config.reading_light_post_data)
        
        config.bedside_light_on_endpoint = request.POST.get('bedside_light_on_endpoint', config.bedside_light_on_endpoint)
        config.bedside_light_off_endpoint = request.POST.get('bedside_light_off_endpoint', config.bedside_light_off_endpoint)
        config.bedside_light_post_data = parse_json_field('bedside_light_post_data', config.bedside_light_post_data)
        
        # Custom endpoints
        config.custom_endpoint_1 = request.POST.get('custom_endpoint_1', config.custom_endpoint_1)
        config.custom_endpoint_1_name = request.POST.get('custom_endpoint_1_name', config.custom_endpoint_1_name)
        config.custom_endpoint_1_data = parse_json_field('custom_endpoint_1_data', config.custom_endpoint_1_data)
        
        config.custom_endpoint_2 = request.POST.get('custom_endpoint_2', config.custom_endpoint_2)
        config.custom_endpoint_2_name = request.POST.get('custom_endpoint_2_name', config.custom_endpoint_2_name)
        config.custom_endpoint_2_data = parse_json_field('custom_endpoint_2_data', config.custom_endpoint_2_data)
        
        config.custom_endpoint_3 = request.POST.get('custom_endpoint_3', config.custom_endpoint_3)
        config.custom_endpoint_3_name = request.POST.get('custom_endpoint_3_name', config.custom_endpoint_3_name)
        config.custom_endpoint_3_data = parse_json_field('custom_endpoint_3_data', config.custom_endpoint_3_data)
        
        config.save()
        messages.success(request, 'ESP32 configuration updated successfully!')
        return redirect('iot:esp32_configuration', room_number=room_number)
    
    context = {
        'room': room,
        'esp32': esp32,
        'config': config,
    }
    return render(request, 'iot/esp32_configuration.html', context)


def smart_room_config(request, room_number):
    """Modern configuration page for smart room system"""
    room = get_object_or_404(Room, room_number=room_number)
    esp32, created = ESP32Device.objects.get_or_create(
        room=room,
        defaults={
            'ip_address': '192.168.1.100'
        }
    )
    config, created = ESP32Configuration.objects.get_or_create(esp32_device=esp32)
    
    # Get current guest info if room is occupied
    current_reservation = None
    guest_name = "Guest"
    
    if room.status == 'occupied':
        current_reservation = Reservation.objects.filter(
            room=room, 
            status__in=['confirmed', 'checked_in'],
            check_in__lte=timezone.now().date(),
            check_out__gte=timezone.now().date()
        ).first()
        
        if current_reservation:
            guest_name = current_reservation.guest.first_name
    
    if request.method == 'POST':
        import json as json_module
        from django.contrib import messages
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"POST request received for room {room_number}")
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        logger.info(f"POST data values: {dict(request.POST)}")
        
        try:
            # Update ESP32 device settings
            old_ip = esp32.ip_address
            old_username = esp32.auth_username
            
            esp32.ip_address = request.POST.get('ip_address', esp32.ip_address)
            esp32.auth_username = request.POST.get('auth_username', esp32.auth_username)
            esp32.auth_password = request.POST.get('auth_password', esp32.auth_password)
            esp32.save()
            logger.info(f"ESP32 device updated: IP changed from {old_ip} to {esp32.ip_address}, Auth={esp32.auth_username}")
        except Exception as e:
            logger.error(f"Error updating ESP32 device: {e}")
            messages.error(request, f'Error updating device settings: {e}')
            # Don't redirect on error, just continue to render the page
        
        # Helper function to parse JSON data
        def parse_json_field(field_name, default={}):
            try:
                data = request.POST.get(field_name, '{}')
                return json_module.loads(data) if data.strip() else default
            except json_module.JSONDecodeError:
                return default
        
        # Update configuration endpoints - Lighting Controls
        config.outdoor_lights_on_endpoint = request.POST.get('outdoor_lights_on_endpoint', config.outdoor_lights_on_endpoint)
        config.outdoor_lights_off_endpoint = request.POST.get('outdoor_lights_off_endpoint', config.outdoor_lights_off_endpoint)
        config.main_light_on_endpoint = request.POST.get('main_light_on_endpoint', config.main_light_on_endpoint)
        config.main_light_off_endpoint = request.POST.get('main_light_off_endpoint', config.main_light_off_endpoint)
        config.spot_light_on_endpoint = request.POST.get('spot_light_on_endpoint', config.spot_light_on_endpoint)
        config.spot_light_off_endpoint = request.POST.get('spot_light_off_endpoint', config.spot_light_off_endpoint)
        
        # Mood Lighting
        config.mood_light_on_endpoint = request.POST.get('mood_light_on_endpoint', config.mood_light_on_endpoint)
        config.mood_light_off_endpoint = request.POST.get('mood_light_off_endpoint', config.mood_light_off_endpoint)
        config.mood_light_color_endpoint = request.POST.get('mood_light_color_endpoint', config.mood_light_color_endpoint)
        
        # Scene Controls (generic endpoint)
        config.scene_endpoint = request.POST.get('scene_endpoint', config.scene_endpoint)
        
        # AC Controls
        config.ac_power_endpoint = request.POST.get('ac_power_endpoint', config.ac_power_endpoint)
        config.ac_temperature_endpoint = request.POST.get('ac_temperature_endpoint', config.ac_temperature_endpoint)
        config.ac_mode_endpoint = request.POST.get('ac_mode_endpoint', config.ac_mode_endpoint)
        
        # Alarm Controls
        config.alarm_set_endpoint = request.POST.get('alarm_set_endpoint', config.alarm_set_endpoint)
        config.alarm_enable_endpoint = request.POST.get('alarm_enable_endpoint', config.alarm_enable_endpoint)
        config.alarm_disable_endpoint = request.POST.get('alarm_disable_endpoint', config.alarm_disable_endpoint)
        
        # Custom endpoints
        config.custom_endpoint_1 = request.POST.get('custom_endpoint_1', config.custom_endpoint_1)
        config.custom_endpoint_1_name = request.POST.get('custom_endpoint_1_name', config.custom_endpoint_1_name)
        config.custom_endpoint_2 = request.POST.get('custom_endpoint_2', config.custom_endpoint_2)
        config.custom_endpoint_2_name = request.POST.get('custom_endpoint_2_name', config.custom_endpoint_2_name)
        config.custom_endpoint_3 = request.POST.get('custom_endpoint_3', config.custom_endpoint_3)
        config.custom_endpoint_3_name = request.POST.get('custom_endpoint_3_name', config.custom_endpoint_3_name)
        
        try:
            config.save()
            logger.info(f"Configuration saved successfully for room {room_number}")
            messages.success(request, 'Smart room configuration updated successfully!')
            # Don't redirect immediately, just render the page with success message
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            messages.error(request, f'Error saving configuration: {e}')
    
    context = {
        'room': room,
        'esp32': esp32,
        'config': config,
        'guest_name': guest_name,
        'current_reservation': current_reservation,
    }
    return render(request, 'iot/smart_room_config.html', context)
