# Generated manually to remove unique constraint from mac_address field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iot', '0006_make_auth_optional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='esp32device',
            name='mac_address',
            field=models.CharField(blank=True, help_text='MAC address of ESP32 (optional)', max_length=17, null=True),
        ),
    ]