from django.db import models
from pms.models import Room
import requests
import json
from django.utils import timezone

class ESP32Device(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='esp32')
    ip_address = models.GenericIPAddressField(help_text="ESP32 IP address (e.g., 192.168.1.100)")
    mac_address = models.CharField(max_length=17, unique=True, blank=True, help_text="MAC address of ESP32")
    firmware_version = models.CharField(max_length=20, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    # Add authentication fields
    auth_username = models.CharField(max_length=50, default='admin', help_text="Basic auth username")
    auth_password = models.CharField(max_length=50, default='orcatech', help_text="Basic auth password")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ESP32 Device"
        verbose_name_plural = "ESP32 Devices"
    
    def __str__(self):
        return f"ESP32 - Room {self.room.room_number} ({self.ip_address})"
    
    def send_command(self, endpoint, data=None):
        """Send command to ESP32 device with basic authentication"""
        try:
            url = f"http://{self.ip_address}/{endpoint}"
            
            # Add basic authentication
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
    
    # Main Light (Relay)
    main_light_on = models.BooleanField(default=False)
    
    # RGB Light
    rgb_light_on = models.BooleanField(default=False)
    rgb_brightness = models.IntegerField(default=50, help_text="0-100")
    rgb_red = models.IntegerField(default=255, help_text="0-255")
    rgb_green = models.IntegerField(default=255, help_text="0-255")
    rgb_blue = models.IntegerField(default=255, help_text="0-255")
    
    # AC Controls (IR)
    ac_on = models.BooleanField(default=False)
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
    
    # Reading Light (if separate relay)
    reading_light_on = models.BooleanField(default=False)
    
    # Bedside Light (if separate relay)
    bedside_light_on = models.BooleanField(default=False)
    
    # Current preset
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
    
    def apply_preset(self, preset_name):
        """Apply predefined preset configurations"""
        presets = {
            'dark': {
                'main_light_on': False,
                'rgb_light_on': True,
                'rgb_brightness': 10,
                'rgb_red': 50, 'rgb_green': 50, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': False
            },
            'gloom': {
                'main_light_on': False,
                'rgb_light_on': True,
                'rgb_brightness': 30,
                'rgb_red': 100, 'rgb_green': 100, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': True
            },
            'reading': {
                'main_light_on': True,
                'rgb_light_on': False,
                'reading_light_on': True,
                'bedside_light_on': False
            },
            'bedside': {
                'main_light_on': False,
                'rgb_light_on': True,
                'rgb_brightness': 20,
                'rgb_red': 255, 'rgb_green': 200, 'rgb_blue': 100,
                'reading_light_on': False,
                'bedside_light_on': True
            },
            'normal': {
                'main_light_on': True,
                'rgb_light_on': False,
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
    
    # RGB Light Configuration
    rgb_light_on_endpoint = models.CharField(max_length=100, default='light/rgb/on', help_text='Endpoint for turning RGB light ON')
    rgb_light_off_endpoint = models.CharField(max_length=100, default='light/rgb/off', help_text='Endpoint for turning RGB light OFF')
    rgb_light_color_endpoint = models.CharField(max_length=100, default='light/rgb/color', help_text='Endpoint for RGB color control')
    rgb_light_post_data = models.JSONField(default=dict, blank=True, help_text='Additional POST data for RGB light commands')
    
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
    
    def get_endpoint(self, device_type, action, locker_number=None):
        """Get configured endpoint for device type and action"""
        endpoint_map = {
            'main_light': {
                'on': self.main_light_on_endpoint,
                'off': self.main_light_off_endpoint,
            },
            'rgb_light': {
                'on': self.rgb_light_on_endpoint,
                'off': self.rgb_light_off_endpoint,
                'color': self.rgb_light_color_endpoint,
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
        }
        return endpoint_map.get(device_type, {}).get(action, '')
    
    def get_post_data(self, device_type):
        """Get additional POST data for device type"""
        data_map = {
            'main_light': self.main_light_post_data,
            'rgb_light': self.rgb_light_post_data,
            'ac': self.ac_post_data,
            'reading_light': self.reading_light_post_data,
            'bedside_light': self.bedside_light_post_data,
            'locker': self.locker_post_data,
        }
        return data_map.get(device_type, {})
