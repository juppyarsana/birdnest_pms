# Generated manually

from django.db import migrations

def copy_agent_data(apps, schema_editor):
    """Copy agent data from old field to new field"""
    Reservation = apps.get_model('pms', 'Reservation')
    Agent = apps.get_model('pms', 'Agent')
    
    # Mapping from old agent values to new agent names
    agent_mapping = {
        'direct': 'Direct Booking',
        'booking_com': 'Booking.com',
        'expedia': 'Expedia',
        'agoda': 'Agoda',
        'airbnb': 'Airbnb',
        'travel_agent': 'Travel Agent',
        'corporate': 'Corporate',
        'walk_in': 'Walk-in',
        'phone': 'Phone Booking',
        'other': 'Other',
    }
    
    for reservation in Reservation.objects.all():
        if reservation.agent:
            agent_name = agent_mapping.get(reservation.agent)
            if agent_name:
                try:
                    agent = Agent.objects.get(name=agent_name)
                    reservation.agent_new = agent
                    reservation.save()
                except Agent.DoesNotExist:
                    print(f"Agent '{agent_name}' not found for reservation {reservation.id}")

def reverse_copy_agent_data(apps, schema_editor):
    """Clear agent_new field"""
    Reservation = apps.get_model('pms', 'Reservation')
    Reservation.objects.update(agent_new=None)

class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0028_populate_agents'),
    ]

    operations = [
        migrations.RunPython(copy_agent_data, reverse_copy_agent_data),
    ]