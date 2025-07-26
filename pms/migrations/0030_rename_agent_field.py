# Generated migration to rename agent_new to agent and remove old agent field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0029_copy_agent_data'),
    ]

    operations = [
        # Remove the old agent field
        migrations.RemoveField(
            model_name='reservation',
            name='agent',
        ),
        # Rename agent_new to agent
        migrations.RenameField(
            model_name='reservation',
            old_name='agent_new',
            new_name='agent',
        ),
    ]