from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, date, time, timedelta
from calendar import monthrange
from .models import Room, Reservation, HotelSettings, Guest
from .forms import ReservationForm, CheckInGuestForm, ConfirmReservationForm
from django.views.decorators.http import require_GET

def reservations_list(request):
    """View to display all reservations with appropriate actions"""
    print("Debug: Accessing reservations list view")
    
    # Get sort and filter parameters from request
    sort_field = request.GET.get('sort', 'check_in')
    sort_direction = request.GET.get('direction', 'desc')
    status_filter = request.GET.get('status', '')
    
    # Get search parameter
    search_query = request.GET.get('search', '').strip()
    
    # Update all reservation statuses before displaying
    reservations = Reservation.objects.all()
    print(f"Debug: Found {len(reservations)} reservations")
    
    for reservation in reservations:
        old_status = reservation.status
        reservation.update_status()
        print(f"Debug: Reservation {reservation.id} status: {old_status} -> {reservation.status}")

    # Apply status filter
    if status_filter:
        reservations = reservations.filter(status=status_filter)
        print(f"Debug: Filtered by status '{status_filter}', found {len(reservations)} reservations")

    # Apply search filter if provided
    if search_query:
        from django.db.models import Q
        reservations = reservations.filter(
            Q(guest__name__icontains=search_query) |
            Q(guest__email__icontains=search_query) |
            Q(room__room_number__icontains=search_query) |
            Q(guest__phone__icontains=search_query)
        )
        print(f"Debug: Filtered by search '{search_query}', found {len(reservations)} reservations")

    # Define valid sort fields and their corresponding model fields
    valid_sort_fields = {
        'id': 'id',
        'guest': 'guest__name',
        'room': 'room__room_number',
        'check_in': 'check_in',
        'check_out': 'check_out',
        'status': 'status',
        'payment_method': 'payment_method'
    }

    # Apply sorting
    if sort_field in valid_sort_fields:
        sort_by = valid_sort_fields[sort_field]
        if sort_direction == 'desc':
            sort_by = f'-{sort_by}'
        reservations = reservations.order_by(sort_by)
    else:
        # Default sort: check-in date closest to today
        today = date.today()
        reservations = reservations.extra(
            select={'date_diff': "ABS(JULIANDAY(date(check_in)) - JULIANDAY(date('%s')))" % today},
            order_by=['date_diff']
        )

    # Get all available statuses for filter dropdown (from model choices)
    all_statuses = [choice[0] for choice in Reservation.STATUS_CHOICES]
    
    context = {
        'reservations': reservations,
        'current_sort': sort_field,
        'current_direction': sort_direction,
        'current_status_filter': status_filter,
        'current_search_query': search_query,
        'all_statuses': all_statuses
    }
    print("Debug: Rendering reservations list template")
    return render(request, 'pms/reservations.html', context)

# View for check-in process
def checkin_reservation(request, reservation_id):
    """View for check-in process with time restrictions"""
    try:
        reservation = get_object_or_404(Reservation, id=reservation_id)
        print(f"Debug: Found reservation {reservation_id} with status {reservation.status}")
        
        # Update reservation status before proceeding
        old_status = reservation.status
        reservation.update_status()
        print(f"Debug: Status updated from {old_status} to {reservation.status}")
        
        if reservation.status != 'expected_arrival':
            print(f"Debug: Invalid status for check-in: {reservation.status}")
            messages.error(request, 'This reservation cannot be checked in at this time.')
            return redirect('reservations_list')
        
        guest = reservation.guest
        settings = HotelSettings.get_settings()
        current_time = datetime.now().time()
        
        # Check if current time is within allowed check-in window
        if not settings.is_check_in_allowed(current_time):
            print(f"Debug: Check-in not allowed at {current_time}")
            messages.warning(
                request,
                f'Check-in is only allowed between {settings.earliest_check_in_time.strftime("%I:%M %p")} '
                f'and {settings.latest_check_in_time.strftime("%I:%M %p")}'
            )
            return redirect('reservations_list')
        
        if request.method == 'POST':
            print("Debug: Processing POST request")
            form = CheckInGuestForm(request.POST, instance=guest)
            if form.is_valid():
                print("Debug: Form is valid, saving guest info")
                form.save()
                reservation.status = 'in_house'
                reservation.check_in_time = current_time
                reservation.save()
                # Update room status after check-in
                reservation.room.update_status()
                messages.success(request, f'Successfully checked in {guest.name}')
                return redirect('dashboard')
            else:
                print(f"Debug: Form validation errors: {form.errors}")
        else:
            print("Debug: Initializing GET request form")
            form = CheckInGuestForm(instance=guest)
        
        context = {
            'reservation': reservation,
            'form': form,
            'earliest_check_in': settings.earliest_check_in_time.strftime('%I:%M %p'),
            'latest_check_in': settings.latest_check_in_time.strftime('%I:%M %p')
        }
        print("Debug: Rendering check-in form")
        response = render(request, 'pms/checkin.html', context)
        print("Debug: Response status code:", response.status_code)
        return response
    except Exception as e:
        print(f"Debug: Error occurred: {str(e)}")
        print(f"Debug: Error type: {type(e).__name__}")
        import traceback
        print(f"Debug: Traceback: {traceback.format_exc()}")
        messages.error(request, 'An error occurred during check-in')
        return redirect('reservations_list')

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

    # Current reservations (active today, confirmed/arrival/in_house only)
    reservations = Reservation.objects.filter(
        check_in__lte=today,
        check_out__gt=today,
        status__in=['confirmed', 'expected_arrival', 'in_house']
    )
    daily_occupancy = (len(reservations) / 5) * 100

    # Weekly occupancy for current week (confirmed/arrival/departure/in_house/checked_out)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    days_in_week = 7
    total_room_nights_week = 5 * days_in_week
    booked_room_nights_week = 0
    weekly_reservations = Reservation.objects.filter(
        check_in__lt=week_end,
        check_out__gt=week_start,
        status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
    )
    for res in weekly_reservations:
        start = max(res.check_in, week_start)
        end = min(res.check_out, week_end)
        booked_room_nights_week += (end - start).days
    weekly_occupancy = (booked_room_nights_week / total_room_nights_week) * 100 if total_room_nights_week > 0 else 0

    # Monthly occupancy for current month (confirmed/arrival/departure/in_house/checked_out)
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
        status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
    )
    for res in monthly_reservations:
        start = max(res.check_in, month_start)
        end = min(res.check_out, month_end)
        booked_room_nights += (end - start).days
    monthly_occupancy = (booked_room_nights / total_room_nights) * 100 if total_room_nights > 0 else 0

    # Filter reservations by status
    pending_reservations = Reservation.objects.filter(status='pending')
    expected_arrivals = Reservation.objects.filter(status='expected_arrival')
    checked_in_reservations = Reservation.objects.filter(status='in_house')
    expected_departures = Reservation.objects.filter(status='expected_departure')
    canceled_reservations = Reservation.objects.filter(status='canceled')
    no_show_reservations = Reservation.objects.filter(status='no_show')
    checked_out_reservations = Reservation.objects.filter(status='checked_out')
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
        'checked_out_reservations': checked_out_reservations,
        'daily_occupancy': daily_occupancy,
        'weekly_occupancy': weekly_occupancy,
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
    """Confirm a pending reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id, status='pending')
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
            'pending': '#FF9800',  # Orange (Pending)
            'confirmed': '#9C27B0',  # Purple (Confirmed)
            'expected_arrival': '#4CAF50',  # Green (Expected Arrival)
            'in_house': '#673AB7',  # Deep Purple (In House)
            'expected_departure': '#2196F3',  # Blue (Expected Departure)
            'checked_out': '#00bcd4',  # Cyan (Checked Out)
            'canceled': '#795548',  # Brown (Canceled)
            'no_show': '#F44336',  # Red (No Show)
        }
        events.append({
            'id': reservation.id,
            'title': f"{reservation.guest.name} - {reservation.room.room_number} ({reservation.status})",
            'start': reservation.check_in.isoformat(),
            'end': reservation.check_out.isoformat(),
            'color': colors.get(reservation.status, '#9C27B0'),
        })
    return JsonResponse(events, safe=False)

def reservation_detail(request, reservation_id):
    """View to display detailed information about a specific reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    return render(request, 'pms/reservation_detail.html', {'reservation': reservation})

def checkout_reservation(request, reservation_id):
    """Check out a guest"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST' and reservation.status in ['in_house', 'expected_departure']:
        reservation.status = 'checked_out'
        reservation.save()
        # Update room status with today's date
        today = date.today()
        reservation.room.status = 'vacant_dirty'
        reservation.room.save()
        reservation.room.update_status(today)
        return redirect('reservations_list')
    return redirect('reservations_list')

def cancel_reservation(request, reservation_id):
    """Cancel a reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    if request.method == 'POST' and reservation.status not in ['completed', 'canceled', 'no_show']:
        reason = request.POST.get('cancellation_reason', '').strip()
        reservation.status = 'canceled'
        reservation.cancellation_reason = reason
        reservation.save()
        # Set room status to vacant_dirty so it can be cleaned before rebooking
        reservation.room.status = 'vacant_dirty'
        reservation.room.save()
        reservation.room.update_status()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'status': 'canceled', 'reason': reason})
        return redirect('reservations_list')
    return render(request, 'pms/cancel_reservation.html', {'reservation': reservation})

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

def rooms_list(request):
    """View for housekeeping to update room statuses"""
    from .models import Room
    from django.shortcuts import redirect
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        room = Room.objects.get(id=room_id)
        # Only allow changing from vacant_dirty to vacant_clean
        if room.status == 'vacant_dirty':
            room.status = 'vacant_clean'
            room.save()
        return redirect('rooms_list')
    rooms = Room.objects.all()
    return render(request, 'pms/rooms.html', {'rooms': rooms})


def guests(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        id_type = request.POST.get('id_type', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '').strip()
        address = request.POST.get('address', '').strip()
        emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        if name:
            guest = Guest(
                name=name,
                email=email,
                phone=phone,
                id_type=id_type,
                id_number=id_number,
                address=address,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_phone=emergency_contact_phone
            )
            if date_of_birth:
                guest.date_of_birth = date_of_birth
            try:
                guest.save()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
            except Exception as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                from django.contrib import messages
                messages.error(request, f"Could not add guest: {str(e)}")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Name is required.'})
            from django.contrib import messages
            messages.error(request, "Name is required.")
        from django.shortcuts import redirect
        return redirect('guests')
    # Handle GET request: render guests.html with guest list
    guests = Guest.objects.all().order_by('-id')
    return render(request, 'pms/guests.html', {'guests': guests})

def guest_list_json(request):
    guests = Guest.objects.all().order_by('-id')
    data = [
        {"id": g.id, "name": g.name} for g in guests
    ]
    return JsonResponse({"guests": data})