#!/usr/bin/env python
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_pms.settings')
django.setup()

from pms.models import Room, ESP32ButtonConfig

def create_default_config():
    try:
        room = Room.objects.get(room_number='Garuda')
        config, created = ESP32ButtonConfig.objects.get_or_create(
            room=room,
            defaults={
                'status_endpoint': 'status',
                'timeout_seconds': 10,
                'front_light_enabled': True,
                'front_light_endpoint': 'setstate',
                'front_light_on_command': '1',
                'front_light_off_command': '0',
                'back_light_enabled': True,
                'back_light_endpoint': 'setstate',
                'back_light_on_command': '1',
                'back_light_off_command': '0',
                'main_light_enabled': True,
                'main_light_endpoint': 'control',
                'main_light_on_command': 'main_on',
                'main_light_off_command': 'main_off',
                'sport_light_enabled': True,
                'sport_light_endpoint': 'control',
                'sport_light_on_command': 'sport_on',
                'sport_light_off_command': 'sport_off',
                'rgb_light_enabled': True,
                'rgb_endpoint': 'control',
                'ac_enabled': True,
                'ac_endpoint': 'control'
            }
        )
        print(f'ESP32ButtonConfig for Garuda room: {"created" if created else "already exists"}')
        print(f'Configuration ID: {config.id}')
        print(f'Status endpoint: {config.status_endpoint}')
        print(f'Timeout: {config.timeout_seconds} seconds')
        
    except Room.DoesNotExist:
        print('Garuda room not found!')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    create_default_config()