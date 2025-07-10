from django.shortcuts import render, redirect, get_object_or_404
from .models import Room, Reservation
from .forms import ReservationForm
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta
from calendar import monthrange

def dashboard(request):
    rooms = Room.objects.all()
    today = date.today()

    # Update reservation statuses
    for reservation in Reservation.objects.all():
        reservation.update_status()

    # Sync room statuses
    for room in rooms:
        is_occupied = Reservation.objects.filter(
            room=room,
            check_in__lte=today,
            check_out__gt=today,
            status__in=['confirmed', 'expected_arrival', 'expected_departure']
        ).exists()
        room.status = 'occupied' if is_occupied else 'available'
        room.save()

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
    expected_departures = Reservation.objects.filter(status='expected_departure')
    canceled_reservations = Reservation.objects.filter(status='canceled')
    no_show_reservations = Reservation.objects.filter(status='no_show')
    all_reservations = Reservation.objects.all()

    return render(request, 'pms/dashboard.html', {
        'rooms': rooms,
        'reservations': reservations,
        'pending_reservations': pending_reservations,
        'expected_arrivals': expected_arrivals,
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
    initial_data = {'status': 'pending'}
    if 'check_in' in request.GET:
        initial_data['check_in'] = request.GET['check_in']

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ReservationForm(initial=initial_data)
    return render(request, 'pms/reservation_form.html', {'form': form})

def edit_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST':
        form = ReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ReservationForm(instance=reservation)
    return render(request, 'pms/reservation_edit.html', {'form': form, 'reservation': reservation})

def confirm_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST':
        reservation.status = 'confirmed'
        reservation.save()
        # Trigger room status update
        today = date.today()
        if reservation.check_in <= today < reservation.check_out:
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
        return redirect('dashboard')
    return render(request, 'pms/confirm_reservation.html', {'reservation': reservation})

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