import requests
import json
from datetime import datetime
from django.conf import settings
from .models import TabletDevice, RoomDeviceState, ESP32ButtonConfig
import logging

logger = logging.getLogger(__name__)

class ESP32Controller:
    """Service class to handle ESP32 communication"""
    
    def __init__(self, tablet_device):
        self.tablet = tablet_device
        self.base_url = f"http://{tablet_device.esp32_ip}"
        
        # Get ESP32 configuration from database
        self.config = ESP32ButtonConfig.get_config_for_room(tablet_device.room)
        self.timeout = self.config.timeout_seconds if self.config else 10
    
    def send_command(self, endpoint, params=None):
        """Send HTTP command to ESP32"""
        try:
            # Use configurable endpoint if provided, otherwise use the passed endpoint
            if endpoint == 'status' and hasattr(self.config, 'status_endpoint'):
                endpoint = self.config.status_endpoint.lstrip('/')
            
            url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
            
            if params:
                # Send as GET with query parameters (as per your example)
                response = requests.get(url, params=params, timeout=self.timeout)
            else:
                response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                # Update last ping time
                self.tablet.last_ping = datetime.now()
                self.tablet.save()
                logger.info(f"ESP32 command sent successfully to {self.tablet.esp32_ip}: {url}")
                return True, response.text
            else:
                logger.error(f"ESP32 returned error {response.status_code}: {response.text}")
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to ESP32 at {self.tablet.esp32_ip}")
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to ESP32 at {self.tablet.esp32_ip}")
            return False, "Connection failed"
        except Exception as e:
            logger.error(f"Unexpected error communicating with ESP32: {str(e)}")
            return False, str(e)
    
    def send_post_command(self, endpoint, params=None):
        """Send HTTP POST command to ESP32"""
        try:
            # Use configurable endpoint if provided, otherwise use the passed endpoint
            if endpoint == 'status' and hasattr(self.config, 'status_endpoint'):
                endpoint = self.config.status_endpoint.lstrip('/')
            
            url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
            
            if params:
                # Send as POST with query parameters
                response = requests.post(url, params=params, timeout=self.timeout)
            else:
                response = requests.post(url, timeout=self.timeout)
            
            if response.status_code == 200:
                # Update last ping time
                self.tablet.last_ping = datetime.now()
                self.tablet.save()
                logger.info(f"ESP32 POST command sent successfully to {self.tablet.esp32_ip}: {url}")
                return True, response.text
            else:
                logger.error(f"ESP32 returned error {response.status_code}: {response.text}")
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to ESP32 at {self.tablet.esp32_ip}")
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to ESP32 at {self.tablet.esp32_ip}")
            return False, "Connection failed"
        except Exception as e:
            logger.error(f"Unexpected error communicating with ESP32: {str(e)}")
            return False, str(e)
    
    def get_device_state_esp32(self):
        """Get current device state from ESP32 using getstate endpoint"""
        try:
            success, response = self.send_post_command('getstate')
            if success:
                # Parse the response to extract device states
                # Assuming ESP32 returns JSON with device states
                try:
                    state_data = json.loads(response)
                    return True, state_data
                except json.JSONDecodeError:
                    # If not JSON, return raw response
                    return True, response
            return False, response
        except Exception as e:
            logger.error(f"Error getting ESP32 state: {str(e)}")
            return False, str(e)
    
    def control_light(self, light_type, state=None):
        """Control individual lights with ESP32 specific commands using configurable parameters"""
        try:
            # Check if the light type is enabled in configuration
            enabled_field = f"{light_type}_enabled"
            if hasattr(self.config, enabled_field) and not getattr(self.config, enabled_field):
                return False, f"{light_type} is disabled in configuration"
            
            if light_type in ['front_light', 'back_light']:
                parameter_name = getattr(self.config, f'{light_type}_parameter_name', 'tv')
                
                if state is None:
                    # Get current state first
                    success, current_state = self.get_device_state_esp32()
                    if not success:
                        return False, "Failed to get current state"
                    
                    # Determine current state using dynamic parameter name
                    current_light_state = 0  # Default to off if we can't determine
                    if isinstance(current_state, dict):
                        # Check for parameter name in different cases
                        if parameter_name in current_state:
                            current_light_state = int(current_state[parameter_name])
                        elif parameter_name.upper() in current_state:
                            current_light_state = int(current_state[parameter_name.upper()])
                        elif parameter_name.lower() in current_state:
                            current_light_state = int(current_state[parameter_name.lower()])
                    elif isinstance(current_state, str):
                        # Parse string response if needed
                        current_light_state = 1 if (f'"{parameter_name}":"1"' in current_state or 
                                                   f'"{parameter_name.upper()}":"1"' in current_state or 
                                                   f'"{parameter_name.lower()}":"1"' in current_state or
                                                   f'{parameter_name}=1' in current_state or 
                                                   f'{parameter_name.upper()}=1' in current_state or
                                                   f'{parameter_name.lower()}=1' in current_state) else 0
                    
                    # Toggle the state
                    new_state = 0 if current_light_state == 1 else 1
                else:
                    # Use provided state with configurable commands
                    on_command = getattr(self.config, f'{light_type}_on_command')
                    off_command = getattr(self.config, f'{light_type}_off_command')
                    
                    if state == on_command:
                        new_state = 1
                    elif state == off_command:
                        new_state = 0
                    else:
                        new_state = 1 if state == 'on' else 0
                
                # Send command using configurable endpoint
                endpoint = getattr(self.config, f'{light_type}_endpoint').lstrip('/')
                if endpoint == 'setstate':
                    params = {parameter_name: str(new_state)}
                    return self.send_post_command(endpoint, params)
                else:
                    # Use custom endpoint with configurable commands
                    on_command = getattr(self.config, f'{light_type}_on_command')
                    off_command = getattr(self.config, f'{light_type}_off_command')
                    command = on_command if new_state == 1 else off_command
                    params = {'command': command}
                    return self.send_command(endpoint, params)
            
            elif light_type == 'main_light':
                # Use configurable parameters for main light
                endpoint = self.config.main_light_endpoint.lstrip('/')
                if state is None:
                    state = 'on'  # Default to on if not specified
                
                if state == self.config.main_light_on_command or state == 'on':
                    command = self.config.main_light_on_command
                else:
                    command = self.config.main_light_off_command
                
                # Check if using setstate endpoint for parameter-based commands
                if endpoint == 'setstate':
                    parameter_name = getattr(self.config, 'main_light_parameter_name', 'main')
                    params = {parameter_name: command}
                    return self.send_post_command(endpoint, params)
                else:
                    params = {'command': command}
                    return self.send_command(endpoint, params)
                
            elif light_type == 'sport_light':
                # Use configurable parameters for sport light
                endpoint = self.config.sport_light_endpoint.lstrip('/')
                if state is None:
                    state = 'on'  # Default to on if not specified
                
                if state == self.config.sport_light_on_command or state == 'on':
                    command = self.config.sport_light_on_command
                else:
                    command = self.config.sport_light_off_command
                
                # Check if using setstate endpoint for parameter-based commands
                if endpoint == 'setstate':
                    parameter_name = getattr(self.config, 'sport_light_parameter_name', 'sport')
                    params = {parameter_name: command}
                    return self.send_post_command(endpoint, params)
                else:
                    params = {'command': command}
                    return self.send_command(endpoint, params)
            
            else:
                return False, "Invalid light type"
                
        except Exception as e:
            logger.error(f"Error controlling light {light_type}: {str(e)}")
            return False, str(e)
    
    def control_rgb_light(self, power, red=255, green=255, blue=255, brightness=100):
        """Control RGB lighting using configurable endpoint"""
        if not self.config.rgb_light_enabled:
            return False, "RGB light is disabled in configuration"
        
        endpoint = self.config.rgb_endpoint.lstrip('/')
        params = {
            'rgb': '1' if power else '0',
            'r': str(red),
            'g': str(green), 
            'b': str(blue),
            'brightness': str(brightness)
        }
        
        return self.send_command(endpoint, params)
    
    def control_ac(self, power, mode='cool', temperature=24, fan_speed=1):
        """Control air conditioning using configurable endpoint"""
        if not self.config.ac_enabled:
            return False, "AC is disabled in configuration"
        
        endpoint = self.config.ac_endpoint.lstrip('/')
        params = {
            'ac': '1' if power else '0',
            'mode': mode,
            'temp': str(temperature),
            'fan': str(fan_speed)
        }
        
        return self.send_command(endpoint, params)
    
    def ping_device(self):
        """Ping ESP32 to check if it's online"""
        return self.send_command('ping')
    
    def get_device_status(self):
        """Get current device status from ESP32"""
        return self.send_command('status')

class TabletService:
    """Service class for tablet operations"""
    
    @staticmethod
    def get_room_tablet(room):
        """Get tablet device for a room"""
        try:
            return TabletDevice.objects.get(room=room, is_active=True)
        except TabletDevice.DoesNotExist:
            return None
    
    @staticmethod
    def get_device_state(tablet):
        """Get or create device state for tablet"""
        state, created = RoomDeviceState.objects.get_or_create(room=tablet.room)
        return state
    
    @staticmethod
    def update_device_state(tablet, device_type, **kwargs):
        """Update device state and send command to ESP32"""
        state = TabletService.get_device_state(tablet)
        controller = ESP32Controller(tablet)
        
        success = False
        message = ""
        
        try:
            if device_type == 'light':
                light_type = kwargs.get('light_type')
                new_state = kwargs.get('state')
                
                # For ESP32 lights (front_light, back_light), don't update database state
                # since ESP32 handles the state internally
                if light_type in ['front_light', 'back_light']:
                    # Send command to ESP32 (it will handle the toggle internally)
                    success, message = controller.control_light(light_type, new_state)
                else:
                    # For other lights, update database state
                    if new_state is not None:
                        # Convert string state to boolean
                        if isinstance(new_state, str):
                            boolean_state = new_state.lower() == 'on'
                        else:
                            boolean_state = bool(new_state)
                        
                        setattr(state, light_type, boolean_state)
                        state.save()
                    
                    # Send command to ESP32
                    success, message = controller.control_light(light_type, new_state)
                
            elif device_type == 'rgb':
                # Update database state
                state.rgb_light = kwargs.get('power', state.rgb_light)
                
                # Handle RGB color - convert individual RGB values to hex color
                red = kwargs.get('red', 255)
                green = kwargs.get('green', 255)
                blue = kwargs.get('blue', 255)
                if red is not None and green is not None and blue is not None:
                    state.rgb_color = f"#{red:02x}{green:02x}{blue:02x}"
                
                state.rgb_brightness = kwargs.get('brightness', state.rgb_brightness)
                state.save()
                
                # Send command to ESP32
                success, message = controller.control_rgb_light(
                    state.rgb_light,
                    red,
                    green, 
                    blue,
                    state.rgb_brightness
                )
                
            elif device_type == 'ac':
                # Update database state
                state.ac_power = kwargs.get('power', state.ac_power)
                state.ac_mode = kwargs.get('mode', state.ac_mode)
                state.ac_temperature = kwargs.get('temperature', state.ac_temperature)
                state.ac_fan_speed = kwargs.get('fan_speed', state.ac_fan_speed)
                state.save()
                
                # Send command to ESP32
                success, message = controller.control_ac(
                    state.ac_power,
                    state.ac_mode,
                    state.ac_temperature,
                    state.ac_fan_speed
                )
            
            if success:
                state.last_command_sent = datetime.now()
                state.save()
                
        except Exception as e:
            logger.error(f"Error updating device state: {str(e)}")
            success = False
            message = str(e)
        
        return success, message, state
    
    @staticmethod
    def ping_all_devices():
        """Ping all active tablet devices to check connectivity"""
        tablets = TabletDevice.objects.filter(is_active=True)
        results = []
        
        for tablet in tablets:
            controller = ESP32Controller(tablet)
            success, message = controller.ping_device()
            results.append({
                'tablet': tablet,
                'success': success,
                'message': message
            })
        
        return results