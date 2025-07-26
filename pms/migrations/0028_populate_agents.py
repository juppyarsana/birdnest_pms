# Generated manually

from django.db import migrations

def populate_agents(apps, schema_editor):
    """Populate Agent model with existing hardcoded choices"""
    Agent = apps.get_model('pms', 'Agent')
    
    # Define the agents based on the existing AGENT_CHOICES
    agents_data = [
        {'name': 'Direct Booking', 'display_order': 1},
        {'name': 'Booking.com', 'display_order': 2},
        {'name': 'Expedia', 'display_order': 3},
        {'name': 'Agoda', 'display_order': 4},
        {'name': 'Airbnb', 'display_order': 5},
        {'name': 'Travel Agent', 'display_order': 6},
        {'name': 'Corporate', 'display_order': 7},
        {'name': 'Walk-in', 'display_order': 8},
        {'name': 'Phone Booking', 'display_order': 9},
        {'name': 'Other', 'display_order': 10},
    ]
    
    for agent_data in agents_data:
        Agent.objects.get_or_create(
            name=agent_data['name'],
            defaults={
                'display_order': agent_data['display_order'],
                'is_active': True
            }
        )

def reverse_populate_agents(apps, schema_editor):
    """Remove all agents"""
    Agent = apps.get_model('pms', 'Agent')
    Agent.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0027_add_agent_model'),
    ]

    operations = [
        migrations.RunPython(populate_agents, reverse_populate_agents),
    ]