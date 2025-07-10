from django import forms
from .models import Room, Guest, Reservation
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['guest', 'room', 'check_in', 'check_out', 'status', 'payment_method', 'payment_notes']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        status = cleaned_data.get('status')
        payment_method = cleaned_data.get('payment_method')

        if check_in and check_out and room:
            if check_out <= check_in:
                raise ValidationError("Check-out date must be after check-in date.")

            overlapping = Reservation.objects.filter(
                room=room,
                check_in__lt=check_out,
                check_out__gt=check_in,
                status__in=['confirmed', 'expected_arrival', 'expected_departure']
            ).exclude(id=self.instance.id)

            if overlapping.exists():
                raise ValidationError(f"Room {room.room_number} is already booked for the selected dates.")

        if status in ['confirmed', 'expected_arrival', 'expected_departure'] and not payment_method:
            raise ValidationError("Payment method is required for confirmed or active reservations.")

        return cleaned_data

    def save(self, commit=True):
        reservation = super().save(commit=commit)
        if commit:
            today = date.today()
            if reservation.status in ['confirmed', 'expected_arrival', 'expected_departure'] and reservation.check_in <= today < reservation.check_out:
                reservation.room.status = 'occupied'
            else:
                has_other_active = Reservation.objects.filter(
                    room=reservation.room,
                    check_in__lte=today,
                    check_out__gt=today,
                    status__in=['confirmed', 'expected_arrival', 'expected_departure']
                ).exclude(id=reservation.id).exists()
                reservation.room.status = 'occupied' if has_other_active else 'available'
            reservation.room.save()
        return reservation

class ConfirmReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['payment_method', 'payment_notes']
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].required = True
        self.fields['payment_method'].empty_label = None

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        if not payment_method or payment_method == '':
            raise ValidationError("Please select a payment method for confirmation.")
        return cleaned_data