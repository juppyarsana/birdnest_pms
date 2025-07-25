# Generated by Django 5.2.3 on 2025-07-26 05:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0016_guest_nationality'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guest',
            name='nationality',
            field=models.CharField(blank=True, choices=[('', 'Select Nationality'), ('indonesian', 'Indonesian'), ('american', 'American'), ('australian', 'Australian'), ('british', 'British'), ('canadian', 'Canadian'), ('chinese', 'Chinese'), ('dutch', 'Dutch'), ('french', 'French'), ('german', 'German'), ('indian', 'Indian'), ('japanese', 'Japanese'), ('malaysian', 'Malaysian'), ('singaporean', 'Singaporean'), ('south_korean', 'South Korean'), ('thai', 'Thai'), ('vietnamese', 'Vietnamese'), ('other', 'Other')], help_text="Guest's nationality", max_length=100),
        ),
    ]
