# Generated by Django 5.2.3 on 2025-07-23 11:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0013_reservation_agent'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='base_amount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Base room rate before discounts', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Total discount applied', max_digits=10),
        ),
        migrations.AddField(
            model_name='reservation',
            name='total_amount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Final amount after discounts, taxes, and fees', max_digits=10, null=True),
        ),
    ]
