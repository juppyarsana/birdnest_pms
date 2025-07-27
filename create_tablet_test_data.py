#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_pms.settings')
django.setup()

from pms.models import Room, TabletDevice, AttractionInfo, TabletContent, RoomDeviceState
from django.utils import timezone

def create_test_data():
    print("Creating test data for tablet interface...")
    
    # Create some attractions
    attractions = [
        {
            'name': 'Mount Batur Sunrise Trek',
            'category': 'adventure',
            'description': 'Experience the breathtaking sunrise from the summit of Mount Batur volcano.',
            'distance_km': 15.2,
            'estimated_time': '6 hours',
            'image_url': '/static/images/mount_batur.jpg',
            'website_url': 'https://mountbatur.com',
            'priority': 5
        },
        {
            'name': 'Kintamani Highland View',
            'category': 'nature',
            'description': 'Panoramic views of Lake Batur and Mount Batur from Kintamani plateau.',
            'distance_km': 5.0,
            'estimated_time': '2 hours',
            'image_url': '/static/images/kintamani_view.jpg',
            'website_url': '',
            'priority': 4
        },
        {
            'name': 'Toya Devasya Hot Springs',
            'category': 'wellness',
            'description': 'Natural hot springs with stunning lake views for relaxation.',
            'distance_km': 8.5,
            'estimated_time': '3 hours',
            'image_url': '/static/images/hot_springs.jpg',
            'website_url': 'https://toyadevasya.com',
            'priority': 3
        },
        {
            'name': 'Tegallalang Rice Terraces',
            'category': 'culture',
            'description': 'Beautiful traditional rice terraces showcasing Balinese agriculture.',
            'distance_km': 25.0,
            'estimated_time': '4 hours',
            'image_url': '/static/images/rice_terraces.jpg',
            'website_url': '',
            'priority': 2
        }
    ]
    
    for attraction_data in attractions:
        attraction, created = AttractionInfo.objects.get_or_create(
            name=attraction_data['name'],
            defaults=attraction_data
        )
        if created:
            print(f"Created attraction: {attraction.name}")
        else:
            print(f"Attraction already exists: {attraction.name}")
    
    # Create tablet content
    content_items = [
        {
            'title': 'Welcome to Bird Nest Glamping',
            'content': 'Experience luxury camping with stunning views of Mount Batur and Lake Batur. Enjoy our premium amenities and personalized service.',
            'content_type': 'welcome',
            'is_active': True
        },
        {
            'title': 'Breakfast Service',
            'content': 'Complimentary breakfast is served from 7:00 AM to 10:00 AM at our main dining area. Please let us know about any dietary requirements.',
            'content_type': 'announcement',
            'is_active': True
        },
        {
            'title': 'Check-out Information',
            'content': 'Check-out time is 12:00 PM. Late check-out is available upon request (additional charges may apply). Please contact reception for assistance.',
            'content_type': 'info',
            'is_active': True
        }
    ]
    
    for content_data in content_items:
        content, created = TabletContent.objects.get_or_create(
            title=content_data['title'],
            defaults=content_data
        )
        if created:
            print(f"Created content: {content.title}")
        else:
            print(f"Content already exists: {content.title}")
    
    # Try to get an existing room or create a test room
    try:
        room = Room.objects.first()
        if not room:
            print("No rooms found in database. Please create rooms through the admin interface first.")
            return
        
        # Create tablet device for the room
        tablet, created = TabletDevice.objects.get_or_create(
            room=room,
            defaults={
                'tablet_id': f'TABLET_{room.room_number}',
                'esp32_ip': '192.168.1.64',
                'is_active': True,
                'last_ping': timezone.now()
            }
        )
        if created:
            print(f"Created tablet device for room: {room.room_number}")
        else:
            print(f"Tablet device already exists for room: {room.room_number}")
        
        # Create initial device state
        device_state, created = RoomDeviceState.objects.get_or_create(
            room=room,
            defaults={
                'front_light': False,
                'back_light': False,
                'main_light': True,
                'sport_light': False,
                'rgb_light': False,
                'rgb_color': '#FFFFFF',
                'rgb_brightness': 50,
                'ac_power': True,
                'ac_mode': 'cool',
                'ac_temperature': 24,
                'ac_fan_speed': 'medium'
            }
        )
        if created:
            print(f"Created device state for room: {room.room_number}")
        else:
            print(f"Device state already exists for room: {room.room_number}")
            
        print(f"\nTest data created successfully!")
        print(f"You can now access the tablet interface at:")
        print(f"http://127.0.0.1:8000/tablet/{room.room_number}/")
        
    except Exception as e:
        print(f"Error creating test data: {e}")

if __name__ == '__main__':
    create_test_data()