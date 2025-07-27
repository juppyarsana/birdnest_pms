# Generated manually to add parameter name fields to ESP32ButtonConfig

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0035_esp32buttonconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='esp32buttonconfig',
            name='front_light_parameter_name',
            field=models.CharField(default='tv', help_text='Parameter name for front light (e.g., tv, light, relay1)', max_length=50),
        ),
        migrations.AddField(
            model_name='esp32buttonconfig',
            name='back_light_parameter_name',
            field=models.CharField(default='tv', help_text='Parameter name for back light (e.g., tv, light, relay2)', max_length=50),
        ),
    ]