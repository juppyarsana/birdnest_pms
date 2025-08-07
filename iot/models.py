from django.db import models
from pms.models import Room
import requests
import json
from django.utils import timezone

class ESP32Device(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='esp32')
    ip_address = models.GenericIPAddressField(help_text="ESP32 IP address (e.g., 192.168.1.100)")
    mac_address = models.CharField(max_length=17, blank=True, null=True, help_text="MAC address of ESP32 (optional)")
    firmware_version = models.CharField(max_length=20, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    # Add authentication fields (optional)
    auth_username = models.CharField(max_length=50, blank=True, null=True, help_text="Basic auth username (optional)")
    auth_password = models.CharField(max_length=50, blank=True, null=True, help_text="Basic auth password (optional)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ESP32 Device"
        verbose_name_plural = "ESP32 Devices"
    
    def __str__(self):
        return f"ESP32 - Room {self.room.room_number} ({self.ip_address})"
    
    def send_command(self, endpoint, data=None):
        """Send command to ESP32 device with optional basic authentication"""
        try:
            url = f"http://{self.ip_address}/{endpoint}"
            
            # Add basic authentication only if credentials are provided
            auth = None
            if self.auth_username and self.auth_password:
                from requests.auth import HTTPBasicAuth
                auth = HTTPBasicAuth(self.auth_username, self.auth_password)
            
            response = requests.post(url, json=data, timeout=5, auth=auth)
            
            if response.status_code == 200:
                self.is_online = True
                self.last_seen = timezone.now()
                self.save(update_fields=['is_online', 'last_seen'])
                return True, response.json() if response.content else {}
            else:
                return False, {"error": f"HTTP {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            self.is_online = False
            self.save(update_fields=['is_online'])
            return False, {"error": str(e)}
    
    def get_status(self):
        """Get current device status"""
        try:
            url = f"http://{self.ip_address}/api/room/{self.room.room_number}/status"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                self.is_online = True
                self.last_seen = timezone.now()
                self.save(update_fields=['is_online', 'last_seen'])
                return response.json()
            else:
                self.is_online = False
                self.save(update_fields=['is_online'])
                return {}
                
        except requests.exceptions.RequestException:
            self.is_online = False
            self.save(update_fields=['is_online'])
            return {}

class RoomControls(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='controls')
    
    # Lighting Controls
    main_light_on = models.BooleanField(default=False)
    outdoor_lights_on = models.BooleanField(default=False)
    spot_light_on = models.BooleanField(default=False)
    
    # RGB/Mood Light Controls
    rgb_light_on = models.BooleanField(default=False)
    mood_light_on = models.BooleanField(default=False)
    rgb_brightness = models.IntegerField(default=50, help_text="0-100")
    rgb_red = models.IntegerField(default=255, help_text="0-255")
    rgb_green = models.IntegerField(default=255, help_text="0-255")
    rgb_blue = models.IntegerField(default=255, help_text="0-255")
    
    # Color Picker Position (for mood light color slider)
    color_slider_position = models.FloatField(default=50.0, help_text="0.0-100.0")
    
    # AC/Cooling Controls
    ac_on = models.BooleanField(default=False)
    cooling_on = models.BooleanField(default=False)
    ac_temperature = models.IntegerField(default=24, help_text="16-30°C")
    ac_mode = models.CharField(
        max_length=10, 
        default='cool', 
        choices=[
            ('cool', 'Cool'), 
            ('heat', 'Heat'), 
            ('fan', 'Fan'), 
            ('dry', 'Dry')
        ]
    )
    ac_fan_speed = models.CharField(
        max_length=10, 
        default='auto',
        choices=[
            ('low', 'Low'), 
            ('med', 'Medium'), 
            ('high', 'High'), 
            ('auto', 'Auto')
        ]
    )
    
    # Additional Light Controls
    reading_light_on = models.BooleanField(default=False)
    bedside_light_on = models.BooleanField(default=False)
    
    # Scene Controls
    current_scene = models.CharField(
        max_length=20, 
        default='bright',
        choices=[
            ('bright', 'Bright'),
            ('dark', 'Dark'),
            ('gloomy', 'Gloomy'),
            ('movie', 'Movie'),
        ]
    )
    
    # Alarm Settings
    alarm_enabled = models.BooleanField(default=False)
    alarm_hour = models.IntegerField(default=7, help_text="0-23")
    alarm_minute = models.IntegerField(default=0, help_text="0-59")
    
    # Legacy preset support (for backward compatibility)
    current_preset = models.CharField(
        max_length=20, 
        default='normal',
        choices=[
            ('normal', 'Normal'),
            ('dark', 'Dark'),
            ('gloom', 'Gloom'),
            ('reading', 'Reading'),
            ('bedside', 'Bedside'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Room Controls"
        verbose_name_plural = "Room Controls"
    
    def __str__(self):
        return f"Controls - Room {self.room.room_number}"
    
    def apply_scene(self, scene_name):
        """Apply predefined scene configurations for smart room control"""
        scenes = {
            'bright': {
                'main_light_on': True,
                'outdoor_lights_on': True,
                'spot_light_on': True,
                'mood_light_on': False,
                'rgb_light_on': False,
                'reading_light_on': True,
                'bedside_light_on': False
            },
            'dark': {
                'main_light_on': False,
                'outdoor_lights_on': False,
                'spot_light_on': False,
                'mood_light_on': True,
                'rgb_light_on': True,
                'rgb_brightness': 10,
                'rgb_red': 50, 'rgb_green': 50, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': False
            },
            'gloomy': {
                'main_light_on': False,
                'outdoor_lights_on': True,
                'spot_light_on': False,
                'mood_light_on': True,
                'rgb_light_on': True,
                'rgb_brightness': 30,
                'rgb_red': 100, 'rgb_green': 100, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': True
            },
            'movie': {
                'main_light_on': False,
                'outdoor_lights_on': False,
                'spot_light_on': False,
                'mood_light_on': True,
                'rgb_light_on': True,
                'rgb_brightness': 5,
                'rgb_red': 255, 'rgb_green': 100, 'rgb_blue': 0,
                'reading_light_on': False,
                'bedside_light_on': False
            }
        }
        
        if scene_name in scenes:
            scene = scenes[scene_name]
            for key, value in scene.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.current_scene = scene_name
            self.save()
            return True
        return False

    def apply_preset(self, preset_name):
        """Apply predefined preset configurations (legacy support)"""
        presets = {
            'dark': {
                'main_light_on': False,
                'rgb_light_on': True,
                'mood_light_on': True,
                'rgb_brightness': 10,
                'rgb_red': 50, 'rgb_green': 50, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': False
            },
            'gloom': {
                'main_light_on': False,
                'rgb_light_on': True,
                'mood_light_on': True,
                'rgb_brightness': 30,
                'rgb_red': 100, 'rgb_green': 100, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': True
            },
            'reading': {
                'main_light_on': True,
                'rgb_light_on': False,
                'mood_light_on': False,
                'reading_light_on': True,
                'bedside_light_on': False
            },
            'bedside': {
                'main_light_on': False,
                'rgb_light_on': True,
                'mood_light_on': True,
                'rgb_brightness': 20,
                'rgb_red': 255, 'rgb_green': 200, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': True
            },
            'normal': {
                'main_light_on': True,
                'rgb_light_on': False,
                'mood_light_on': False,
                'reading_light_on': False,
                'bedside_light_on': False
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            for key, value in preset.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.current_preset = preset_name
            self.save()
            return True
        return False
    
    def get_rgb_hex_color(self):
        """Convert RGB values to hex color"""
        return f"#{self.rgb_red:02x}{self.rgb_green:02x}{self.rgb_blue:02x}"
    
    def get_alarm_time_formatted(self):
        """Get formatted alarm time string"""
        return f"{self.alarm_hour:02d}:{self.alarm_minute:02d}"
    
    def set_alarm_time(self, hour, minute):
        """Set alarm time with validation"""
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            self.alarm_hour = hour
            self.alarm_minute = minute
            self.save()
            return True
        return False
    
    def get_color_from_slider_position(self):
        """Convert slider position to RGB color values"""
        # Convert slider position (0-100) to hue (0-360)
        hue = (self.color_slider_position / 100) * 360
        
        # Convert HSV to RGB (simplified for mood lighting)
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue/360, 1.0, 1.0)
        
        self.rgb_red = int(r * 255)
        self.rgb_green = int(g * 255)
        self.rgb_blue = int(b * 255)
        
        return self.get_rgb_hex_color()
    
    def set_temperature_safe(self, temperature):
        """Set temperature with safety bounds"""
        if 16 <= temperature <= 30:
            self.ac_temperature = temperature
            self.save()
            return True
        return False
    
    def get_all_lights_status(self):
        """Get status of all lighting controls"""
        return {
            'main_light': self.main_light_on,
            'outdoor_lights': self.outdoor_lights_on,
            'spot_light': self.spot_light_on,
            'mood_light': self.mood_light_on,
            'rgb_light': self.rgb_light_on,
            'reading_light': self.reading_light_on,
            'bedside_light': self.bedside_light_on,
        }
    
    def turn_off_all_lights(self):
        """Turn off all lighting controls"""
        self.main_light_on = False
        self.outdoor_lights_on = False
        self.spot_light_on = False
        self.mood_light_on = False
        self.rgb_light_on = False
        self.reading_light_on = False
        self.bedside_light_on = False
        self.save()

class DeviceLog(models.Model):
    """Log device commands and responses"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='device_logs')
    command = models.CharField(max_length=100)
    success = models.BooleanField()
    response_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Device Log"
        verbose_name_plural = "Device Logs"
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} Room {self.room.room_number} - {self.command}"

class ESP32Configuration(models.Model):
    """Configuration for ESP32 device endpoints and commands"""
    esp32_device = models.OneToOneField(ESP32Device, on_delete=models.CASCADE, related_name='configuration')
    
    # Main Light Configuration
    main_light_on_endpoint = models.CharField(max_length=100, default='light/main/on', help_text='Endpoint for turning main light ON')
    main_light_off_endpoint = models.CharField(max_length=100, default='light/main/off', help_text='Endpoint for turning main light OFF')
    main_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for main light commands')
    
    # Outdoor Lights Configuration
    outdoor_lights_on_endpoint = models.CharField(max_length=100, default='light/outdoor/on', help_text='Endpoint for turning outdoor lights ON')
    outdoor_lights_off_endpoint = models.CharField(max_length=100, default='light/outdoor/off', help_text='Endpoint for turning outdoor lights OFF')
    outdoor_lights_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for outdoor lights commands')
    
    # Spot Light Configuration
    spot_light_on_endpoint = models.CharField(max_length=100, default='light/spot/on', help_text='Endpoint for turning spot light ON')
    spot_light_off_endpoint = models.CharField(max_length=100, default='light/spot/off', help_text='Endpoint for turning spot light OFF')
    spot_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for spot light commands')
    
    # RGB Light Configuration
    rgb_light_on_endpoint = models.CharField(max_length=100, default='light/rgb/on', help_text='Endpoint for turning RGB light ON')
    rgb_light_off_endpoint = models.CharField(max_length=100, default='light/rgb/off', help_text='Endpoint for turning RGB light OFF')
    rgb_light_color_endpoint = models.CharField(max_length=100, default='light/rgb/color', help_text='Endpoint for RGB color control')
    rgb_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for RGB light commands')
    
    # Mood Light Configuration
    mood_light_on_endpoint = models.CharField(max_length=100, default='light/mood/on', help_text='Endpoint for turning mood light ON')
    mood_light_off_endpoint = models.CharField(max_length=100, default='light/mood/off', help_text='Endpoint for turning mood light OFF')
    mood_light_color_endpoint = models.CharField(max_length=100, default='light/mood/color', help_text='Endpoint for mood light color control')
    mood_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for mood light commands')
    
    # AC Configuration
    ac_power_endpoint = models.CharField(max_length=100, default='ac/power', help_text='Endpoint for AC power control')
    ac_temperature_endpoint = models.CharField(max_length=100, default='ac/temperature', help_text='Endpoint for AC temperature control')
    ac_mode_endpoint = models.CharField(max_length=100, default='ac/mode', help_text='Endpoint for AC mode control')
    ac_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for AC commands')
    
    # Reading Light Configuration
    reading_light_on_endpoint = models.CharField(max_length=100, default='light/reading/on', help_text='Endpoint for turning reading light ON')
    reading_light_off_endpoint = models.CharField(max_length=100, default='light/reading/off', help_text='Endpoint for turning reading light OFF')
    reading_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for reading light commands')
    
    # Bedside Light Configuration
    bedside_light_on_endpoint = models.CharField(max_length=100, default='light/bedside/on', help_text='Endpoint for turning bedside light ON')
    bedside_light_off_endpoint = models.CharField(max_length=100, default='light/bedside/off', help_text='Endpoint for turning bedside light OFF')
    bedside_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for bedside light commands')
    
    # Locker Configuration
    locker_endpoint = models.CharField(max_length=100, default='open/{locker_number}', help_text='Endpoint for locker control (use {locker_number} placeholder)')
    locker_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for locker commands')
    
    # Alarm Configuration
    alarm_set_endpoint = models.CharField(max_length=100, default='alarm/set', help_text='Endpoint for setting alarm')
    alarm_enable_endpoint = models.CharField(max_length=100, default='alarm/enable', help_text='Endpoint for enabling alarm')
    alarm_disable_endpoint = models.CharField(max_length=100, default='alarm/disable', help_text='Endpoint for disabling alarm')
    alarm_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for alarm commands')
    
    # Scene Configuration
    scene_endpoint = models.CharField(max_length=100, default='scene/{scene_name}', help_text='Endpoint for scene control (use {scene_name} placeholder)')
    scene_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for scene commands')
    
    # Custom Endpoints (for additional devices)
    custom_endpoint_1 = models.CharField(max_length=100, blank=True, help_text='Custom endpoint 1')
    custom_endpoint_1_data = models.JSONField(default=dict, blank=True, help_text='POST data for custom endpoint 1')
    custom_endpoint_1_name = models.CharField(max_length=50, blank=True, help_text='Display name for custom endpoint 1')
    
    custom_endpoint_2 = models.CharField(max_length=100, blank=True, help_text='Custom endpoint 2')
    custom_endpoint_2_data = models.JSONField(default=dict, blank=True, help_text='POST data for custom endpoint 2')
    custom_endpoint_2_name = models.CharField(max_length=50, blank=True, help_text='Display name for custom endpoint 2')
    
    custom_endpoint_3 = models.CharField(max_length=100, blank=True, help_text='Custom endpoint 3')
    custom_endpoint_3_data = models.JSONField(default=dict, blank=True, help_text='POST data for custom endpoint 3')
    custom_endpoint_3_name = models.CharField(max_length=50, blank=True, help_text='Display name for custom endpoint 3')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ESP32 Configuration"
        verbose_name_plural = "ESP32 Configurations"
    
    def __str__(self):
        return f"Config - {self.esp32_device}"
    
    def get_endpoint(self, device_type, action, locker_number=None, scene_name=None):
        """Get configured endpoint for device type and action"""
        endpoint_map = {
            'main_light': {
                'on': self.main_light_on_endpoint,
                'off': self.main_light_off_endpoint,
            },
            'outdoor_lights': {
                'on': self.outdoor_lights_on_endpoint,
                'off': self.outdoor_lights_off_endpoint,
            },
            'spot_light': {
                'on': self.spot_light_on_endpoint,
                'off': self.spot_light_off_endpoint,
            },
            'rgb_light': {
                'on': self.rgb_light_on_endpoint,
                'off': self.rgb_light_off_endpoint,
                'color': self.rgb_light_color_endpoint,
            },
            'mood_light': {
                'on': self.mood_light_on_endpoint,
                'off': self.mood_light_off_endpoint,
                'color': self.mood_light_color_endpoint,
            },
            'ac': {
                'power': self.ac_power_endpoint,
                'temperature': self.ac_temperature_endpoint,
                'mode': self.ac_mode_endpoint,
            },
            'reading_light': {
                'on': self.reading_light_on_endpoint,
                'off': self.reading_light_off_endpoint,
            },
            'bedside_light': {
                'on': self.bedside_light_on_endpoint,
                'off': self.bedside_light_off_endpoint,
            },
            'locker': {
                'open': self.locker_endpoint.format(locker_number=locker_number) if locker_number else self.locker_endpoint,
            },
            'alarm': {
                'set': self.alarm_set_endpoint,
                'enable': self.alarm_enable_endpoint,
                'disable': self.alarm_disable_endpoint,
            },
            'scene': {
                'set': self.scene_endpoint.format(scene_name=scene_name) if scene_name else self.scene_endpoint,
            },
        }
        return endpoint_map.get(device_type, {}).get(action, '')
    
    def get_post_data(self, device_type):
        """Get additional POST data for device type"""
        data_map = {
            'main_light': self.main_light_post_data,
            'outdoor_lights': self.outdoor_lights_post_data,
            'spot_light': self.spot_light_post_data,
            'rgb_light': self.rgb_light_post_data,
            'mood_light': self.mood_light_post_data,
            'ac': self.ac_post_data,
            'reading_light': self.reading_light_post_data,
            'bedside_light': self.bedside_light_post_data,
            'locker': self.locker_post_data,
            'alarm': self.alarm_post_data,
            'scene': self.scene_post_data,
        }
        return data_map.get(device_type, {})
