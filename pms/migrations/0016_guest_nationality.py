# Generated by Django 5.2.3 on 2025-07-26 04:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0015_alter_room_room_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='guest',
            name='nationality',
            field=models.CharField(blank=True, help_text="Guest's nationality", max_length=100),
        ),
    ]
