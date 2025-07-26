from .models import Guest, Reservation, Nationality, PaymentMethod

# Form for completing guest data during check-in
from django import forms

class CheckInGuestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional except for required ones
        for field in self.fields.values():
            field.required = False
        # Set required fields
        self.fields['name'].required = True
        self.fields['email'].required = True
        self.fields['id_type'].required = True
        self.fields['id_number'].required = True
        
        # Set nationality queryset to only active nationalities
        self.fields['nationality'].queryset = Nationality.objects.filter(is_active=True).order_by('name')
        self.fields['nationality'].empty_label = "Select Nationality"

    class Meta:
        model = Guest
        fields = [
            'name', 'email', 'phone', 'id_type', 'id_number', 'nationality', 'date_of_birth',
            'address', 'emergency_contact_name', 'emergency_contact_phone'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'id_type': forms.Select(attrs={'class': 'form-select'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
from django import forms
from .models import Room, Guest, Reservation, PaymentMethod
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date

class ReservationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        # 'edit' kwarg determines if this is for editing
        self.is_edit = kwargs.pop('edit', False)
        super().__init__(*args, **kwargs)
        
        # Set payment method queryset to only active payment methods
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        self.fields['payment_method'].empty_label = "Select Payment Method"
        
        # Apply Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        if not self.is_edit:
            # Remove status, payment_method, and payment_notes fields for creation
            self.fields.pop('status')
            self.fields.pop('payment_method')
            self.fields.pop('payment_notes')
        else:
            # Only show payment_notes when editing
            pass

    class Meta:
        model = Reservation
        fields = ['guest', 'room', 'check_in', 'check_out', 'agent', 'status', 'payment_method', 'payment_notes']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'check_out': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'agent': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'guest': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        status = cleaned_data.get('status') if self.is_edit else 'pending'
        payment_method = cleaned_data.get('payment_method') if self.is_edit else None

        if check_in and check_out:
            # Ensure check_out is after check_in
            if check_out <= check_in:
                raise ValidationError('Check-out date must be after check-in date')

        if room and check_in and check_out:
            # Check for overlapping reservations
            active_statuses = ['confirmed', 'in_house', 'expected_arrival']
            overlapping = Reservation.objects.filter(
                room=room,
                check_in__lt=check_out,
                check_out__gt=check_in,
                status__in=active_statuses
            )
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise ValidationError(f"Room {room.room_number} is already booked for the selected dates.")

        if self.is_edit and status in ['confirmed', 'expected_arrival', 'expected_departure'] and not payment_method:
            raise ValidationError("Payment method is required for confirmed or active reservations.")

        return cleaned_data

class GuestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional except name
        for field in self.fields.values():
            field.required = False
        self.fields['name'].required = True
        
        # Set nationality queryset to only active nationalities
        self.fields['nationality'].queryset = Nationality.objects.filter(is_active=True).order_by('name')
        self.fields['nationality'].empty_label = "Select Nationality"

    class Meta:
        model = Guest
        fields = [
            'name', 'email', 'phone', 'id_type', 'id_number', 'nationality', 'date_of_birth',
            'address', 'emergency_contact_name', 'emergency_contact_phone'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'id_type': forms.Select(attrs={'class': 'form-select'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check for duplicate email, excluding current instance
            existing = Guest.objects.filter(email=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('A guest with this email already exists.')
        return email



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
        # Set payment method queryset to only active payment methods
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        self.fields['payment_method'].required = True
        self.fields['payment_method'].empty_label = None

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        if not payment_method:
            raise ValidationError("Please select a payment method for confirmation.")
        return cleaned_data