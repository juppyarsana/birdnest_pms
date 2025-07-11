from .models import Reservation
from .forms import CheckInGuestForm
from django.shortcuts import get_object_or_404, render, redirect

def reservations_list(request):
    """View to display all reservations with appropriate actions"""
    reservations = Reservation.objects.all().order_by('-check_in')
    return render(request, 'pms/reservations.html', {'reservations': reservations})

# View for check-in process
def checkin_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, status='expected_arrival')
    guest = reservation.guest
    if request.method == 'POST':
        form = CheckInGuestForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            reservation.status = 'checked_in'
            reservation.save()
            # Update room status after check-in
            reservation.room.update_status()
            return redirect('dashboard')
    else:
        form = CheckInGuestForm(instance=guest)
    return render(request, 'pms/checkin.html', {'reservation': reservation, 'form': form})
from django.shortcuts import render, redirect, get_object_or_404
from .models import Room, Reservation
from .forms import ReservationForm
from .forms import ConfirmReservationForm  # Ensure this line is present
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta
from calendar import monthrange


def dashboard(request):
    rooms = Room.objects.all()
    today = date.today()

    # Update reservation statuses and mark no-shows
    no_show_updated = False
    for reservation in Reservation.objects.all():
        old_status = reservation.status
        reservation.update_status()
        # If a reservation was marked as no-show, update room status
        if old_status != 'no_show' and reservation.status == 'no_show':
            no_show_updated = True
            reservation.room.update_status(today)

    # Update room statuses
    if no_show_updated:
        for room in rooms:
            room.update_status(today)

    # Current reservations (active today, confirmed/arrival/departure)
    reservations = Reservation.objects.filter(
        check_in__lte=today,
        check_out__gt=today,
        status__in=['confirmed', 'expected_arrival', 'expected_departure']
    )
    daily_occupancy = (len(reservations) / 5) * 100

    # Monthly occupancy for current month (confirmed/arrival/departure)
    year = today.year
    month = today.month
    days_in_month = monthrange(year, month)[1]
    total_room_nights = 5 * days_in_month
    booked_room_nights = 0
    month_start = date(year, month, 1)
    month_end = month_start + timedelta(days=days_in_month)
    monthly_reservations = Reservation.objects.filter(
        check_in__lt=month_end,
        check_out__gt=month_start,
        status__in=['confirmed', 'expected_arrival', 'expected_departure']
    )
    for res in monthly_reservations:
        start = max(res.check_in, month_start)
        end = min(res.check_out, month_end)
        booked_room_nights += (end - start).days
    monthly_occupancy = (booked_room_nights / total_room_nights) * 100 if total_room_nights > 0 else 0

    # Filter reservations by status
    pending_reservations = Reservation.objects.filter(status='pending')
    expected_arrivals = Reservation.objects.filter(status='expected_arrival')
    checked_in_reservations = Reservation.objects.filter(status='checked_in')
    expected_departures = Reservation.objects.filter(status='expected_departure')
    canceled_reservations = Reservation.objects.filter(status='canceled')
    no_show_reservations = Reservation.objects.filter(status='no_show')
    all_reservations = Reservation.objects.all()

    return render(request, 'pms/dashboard.html', {
        'rooms': rooms,
        'reservations': reservations,
        'pending_reservations': pending_reservations,
        'expected_arrivals': expected_arrivals,
        'checked_in_reservations': checked_in_reservations,
        'expected_departures': expected_departures,
        'canceled_reservations': canceled_reservations,
        'no_show_reservations': no_show_reservations,
        'daily_occupancy': daily_occupancy,
        'monthly_occupancy': monthly_occupancy,
        'target_occupancy': 80,
        'month_name': today.strftime('%B %Y'),
        'all_reservations': all_reservations
    })

def create_reservation(request):
    initial_data = {}
    if 'check_in' in request.GET:
        initial_data['check_in'] = request.GET['check_in']

    if request.method == 'POST':
        form = ReservationForm(request.POST, edit=False)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ReservationForm(initial=initial_data, edit=False)
    return render(request, 'pms/reservation_form.html', {'form': form})

def edit_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST':
        form = ReservationForm(request.POST, instance=reservation, edit=True)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ReservationForm(instance=reservation, edit=True)
    return render(request, 'pms/reservation_edit.html', {'form': form, 'reservation': reservation})

def confirm_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST':
        form = ConfirmReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            reservation = form.save()
            reservation.status = 'confirmed'  # Set status manually
            reservation.save()
            # Update room status after confirmation
            reservation.room.update_status()
            return redirect('dashboard')
    else:
        form = ConfirmReservationForm(instance=reservation)
    return render(request, 'pms/confirm_reservation.html', {'reservation': reservation, 'form': form})

def calendar_data(request):
    reservations = Reservation.objects.all()
    events = []
    for reservation in reservations:
        colors = {
            'pending': '#808080',  # Gray
            'confirmed': '#28a745',  # Green
            'expected_arrival': '#007bff',  # Blue
            'expected_departure': '#ffc107',  # Yellow
            'canceled': '#dc3545',  # Red
            'no_show': '#6c757d',  # Dark gray
        }
        events.append({
            'id': reservation.id,
            'title': f"{reservation.guest.name} - {reservation.room.room_number} ({reservation.status})",
            'start': reservation.check_in.isoformat(),
            'end': reservation.check_out.isoformat(),
            'color': colors.get(reservation.status, '#28a745'),
        })
    return JsonResponse(events, safe=False)

def reservations_list(request):
    """View to display all reservations with appropriate actions"""
    reservations = Reservation.objects.all().order_by('-check_in')
    return render(request, 'pms/reservations.html', {'reservations': reservations})

def confirm_reservation(request, reservation_id):
    """Confirm a pending reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id, status='pending')
    if request.method == 'POST':
        form = ConfirmReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.status = 'confirmed'
            reservation.save()
            return redirect('reservations_list')
    else:
        form = ConfirmReservationForm(instance=reservation)
    return render(request, 'pms/confirm_reservation.html', {'form': form, 'reservation': reservation})

def checkout_reservation(request, reservation_id):
    """Check out a guest"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if reservation.status in ['checked_in', 'expected_departure']:
        reservation.status = 'completed'
        reservation.save()
        # Update room status
        reservation.room.update_status()
        return redirect('reservations_list')
    return redirect('reservations_list')

def cancel_reservation(request, reservation_id):
    """Cancel a reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST' and reservation.status not in ['completed', 'cancelled', 'no_show']:
        reservation.status = 'cancelled'
        reservation.save()
        # Update room status
        reservation.room.update_status()
    return redirect('reservations_list')

def edit_reservation(request, reservation_id):
    """Edit a reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST':
        form = ReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
            return redirect('reservations_list')
    else:
        form = ReservationForm(instance=reservation)
    return render(request, 'pms/reservation_form.html', {'form': form, 'editing': True})