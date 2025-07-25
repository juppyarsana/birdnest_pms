# Generated by Django 5.2.3 on 2025-07-26 06:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0025_remove_old_payment_method_field'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reservation',
            name='payment_method_new',
        ),
        migrations.AddField(
            model_name='reservation',
            name='payment_method',
            field=models.ForeignKey(blank=True, help_text='Payment method used for this reservation', null=True, on_delete=django.db.models.deletion.SET_NULL, to='pms.paymentmethod'),
        ),
    ]
