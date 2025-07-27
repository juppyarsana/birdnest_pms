# Generated manually to add parameter name fields for main light and sport light

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0036_add_parameter_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='esp32buttonconfig',
            name='main_light_parameter_name',
            field=models.CharField(default='main', help_text='Parameter name for main light (e.g., main, light, relay3)', max_length=50),
        ),
        migrations.AddField(
            model_name='esp32buttonconfig',
            name='sport_light_parameter_name',
            field=models.CharField(default='sport', help_text='Parameter name for sport light (e.g., sport, light, relay4)', max_length=50),
        ),
    ]