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
    date_filter = request.GET.get('date_filter', '')  # New date filter
    
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

    # Apply date filter
    if date_filter == 'today':
        today = date.today()
        reservations = reservations.filter(
            check_in__lte=today,
            check_out__gt=today
        )
        print(f"Debug: Filtered by today's date, found {len(reservations)} reservations")
    elif date_filter == 'checking_in_today':
        today = date.today()
        reservations = reservations.filter(check_in=today)
        print(f"Debug: Filtered by check-in today, found {len(reservations)} reservations")
    elif date_filter == 'checking_out_today':
        today = date.today()
        reservations = reservations.filter(check_out=today)
        print(f"Debug: Filtered by check-out today, found {len(reservations)} reservations")

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
        'current_date_filter': date_filter,  # New context variable
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
        
        # Check room status and time window for warnings
        room_ready = reservation.room.status == 'vacant_clean'
        time_allowed = settings.is_check_in_allowed(current_time)
        
        # Add warning messages but don't redirect
        if not room_ready:
            print(f"Debug: Room {reservation.room.room_number} is not ready for check-in. Status: {reservation.room.status}")
            messages.warning(
                request,
                f'⚠️ Room {reservation.room.room_number} is not ready for check-in. '
                f'Current status: {reservation.room.get_status_display()}. '
                f'Please ensure the room is cleaned and marked as "Vacant Clean" before proceeding with check-in.'
            )
        
        if not time_allowed:
            print(f"Debug: Check-in not allowed at {current_time}")
            messages.warning(
                request,
                f'⚠️ Check-in is only allowed between {settings.earliest_check_in_time.strftime("%I:%M %p")} '
                f'and {settings.latest_check_in_time.strftime("%I:%M %p")}'
            )
        
        if request.method == 'POST':
            # Only process POST if both room is ready and time is allowed
            if not room_ready:
                messages.error(
                    request,
                    f'Cannot complete check-in: Room {reservation.room.room_number} is not ready. '
                    f'Current status: {reservation.room.get_status_display()}. '
                    f'Please ensure the room is cleaned first.'
                )
                # Re-render the form with error
                form = CheckInGuestForm(request.POST, instance=guest)
            elif not time_allowed:
                messages.error(
                    request,
                    f'Cannot complete check-in: Check-in is only allowed between '
                    f'{settings.earliest_check_in_time.strftime("%I:%M %p")} and '
                    f'{settings.latest_check_in_time.strftime("%I:%M %p")}'
                )
                # Re-render the form with error
                form = CheckInGuestForm(request.POST, instance=guest)
            else:
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
            'latest_check_in': settings.latest_check_in_time.strftime('%I:%M %p'),
            'room_ready': room_ready,
            'time_allowed': time_allowed,
            'can_checkin': room_ready and time_allowed
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
    confirmed_reservations = Reservation.objects.filter(status='confirmed')  # Add this line
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
        'confirmed_reservations': confirmed_reservations,  # Add this line
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
            return redirect('reservations_list')
    else:
        form = ReservationForm(instance=reservation, edit=True)
    return render(request, 'pms/reservation_form.html', {'form': form, 'reservation': reservation, 'editing': True})

def confirm_reservation(request, reservation_id):
    """Confirm a pending reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id, status='pending')
    
    # Check for conflicting pending reservations for the same room and overlapping dates
    conflicting_reservations = Reservation.objects.filter(
        room=reservation.room,
        status='pending',
        check_in__lt=reservation.check_out,
        check_out__gt=reservation.check_in
    ).exclude(id=reservation.id)
    
    # Check for active conflicts that would prevent confirmation
    active_conflicts = Reservation.objects.filter(
        room=reservation.room,
        status__in=['confirmed', 'expected_arrival', 'in_house'],
        check_in__lt=reservation.check_out,
        check_out__gt=reservation.check_in
    )
    
    # Determine if confirmation should be disabled
    has_conflicts = conflicting_reservations.exists() or active_conflicts.exists()
    
    if request.method == 'POST' and not has_conflicts:
        form = ConfirmReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            reservation = form.save()
            reservation.status = 'confirmed'  # Set status manually
            reservation.save()
            # Update room status after confirmation
            reservation.room.update_status()
            messages.success(request, f'Reservation for {reservation.guest.name} has been confirmed successfully!')
            return redirect('dashboard')
    elif request.method == 'POST' and has_conflicts:
        messages.error(request, 'Cannot confirm reservation: There are conflicting reservations for this room and date range.')
        form = ConfirmReservationForm(request.POST, instance=reservation)
    else:
        form = ConfirmReservationForm(instance=reservation)
    
    return render(request, 'pms/confirm_reservation.html', {
        'reservation': reservation, 
        'form': form,
        'conflicting_reservations': conflicting_reservations,
        'active_conflicts': active_conflicts,
        'has_conflicts': has_conflicts
    })

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
    
    # Check if edit mode is requested via URL parameter
    edit_mode = request.GET.get('edit', 'false').lower() == 'true'
    form = None
    
    if request.method == 'POST':
        # Handle in-place editing
        form = ReservationForm(request.POST, instance=reservation, edit=True)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reservation updated successfully!')
            # Preserve the 'from' parameter in redirect
            from_param = request.GET.get('from', '')
            if from_param:
                return redirect(f"{request.path}?from={from_param}")
            return redirect('reservation_detail', reservation_id=reservation.id)
        else:
            # Set edit mode to true when there are validation errors
            edit_mode = True
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    
    # Get available rooms for the room selection dropdown
    # Include current room and other available rooms
    available_rooms = Room.objects.filter(
        status__in=['vacant_clean', 'occupied']
    ).order_by('room_number')
    
    # If editing, we need to check room availability for the date range
    # but exclude the current reservation from the check
    if reservation.status in ['pending', 'confirmed']:
        # Get rooms that are either the current room or available for the dates
        from django.db.models import Q
        available_rooms = Room.objects.filter(
            Q(id=reservation.room.id) |  # Current room
            Q(status='vacant_clean')  # Available rooms
        ).order_by('room_number')
    
    context = {
        'reservation': reservation,
        'available_rooms': available_rooms,
        'auto_edit': edit_mode,
        'form': form,  # Pass form to template for error display
    }
    return render(request, 'pms/reservation_detail.html', context)

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
                    return JsonResponse({'success': True, 'guest_id': guest.id})
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
    
    # Handle GET request: render guests.html with guest list and metrics
    from django.db.models import Count
    
    guests = Guest.objects.all().order_by('-id')
    
    # Calculate metrics
    today = date.today()
    current_month = today.month
    current_year = today.year
    
    # 1. Total guests
    total_guests = guests.count()
    
    # 2. Birthday this month
    birthday_this_month = guests.filter(
        date_of_birth__month=current_month
    ).count()
    
    # 3. Recurring guests (guests with more than 1 reservation)
    recurring_guests = guests.annotate(
        reservation_count=Count('reservation')
    ).filter(reservation_count__gt=1).count()
    
    # 4. Long stay guests (guests who have reservations more than 1 day)
    from django.db.models import F, ExpressionWrapper, IntegerField
    from django.db.models.functions import Extract
    
    long_stay_guests = Guest.objects.filter(
        reservation__in=Reservation.objects.annotate(
            stay_duration=ExpressionWrapper(
                F('check_out') - F('check_in'),
                output_field=IntegerField()
            )
        ).filter(stay_duration__gt=1)
    ).distinct().count()
    
    context = {
        'guests': guests,
        'total_guests': total_guests,
        'birthday_this_month': birthday_this_month,
        'recurring_guests': recurring_guests,
        'long_stay_guests': long_stay_guests,
    }
    
    return render(request, 'pms/guests.html', context)

def guest_detail(request, guest_id):
    """View to display detailed information about a specific guest"""
    from .forms import GuestForm
    from django.contrib import messages
    
    guest = get_object_or_404(Guest, id=guest_id)
    
    # Handle POST request for editing guest information
    if request.method == 'POST':
        form = GuestForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            messages.success(request, 'Guest information updated successfully!')
            return redirect('guest_detail', guest_id=guest.id)
        else:
            messages.error(request, 'Please correct the errors below.')
            # Return to edit mode if there are errors
            edit_mode = True
    else:
        form = GuestForm(instance=guest)
        # Check if edit mode is requested via URL parameter
        edit_mode = request.GET.get('edit', 'false').lower() == 'true'
    
    # Get guest's reservation history with nights calculation
    reservations = Reservation.objects.filter(guest=guest).order_by('-check_in')
    
    # Add nights calculation to each reservation
    for reservation in reservations:
        reservation.nights = (reservation.check_out - reservation.check_in).days
    
    # Calculate guest statistics
    total_reservations = reservations.count()
    completed_stays = reservations.filter(status='completed').count()
    
    # Calculate total nights stayed
    total_nights = 0
    for reservation in reservations.filter(status__in=['completed', 'checked_out']):
        nights = (reservation.check_out - reservation.check_in).days
        total_nights += nights
    
    # Get upcoming reservations
    upcoming_reservations = reservations.filter(
        status__in=['pending', 'confirmed', 'expected_arrival', 'in_house'],
        check_in__gte=date.today()
    )
    
    # Get current reservation (if any)
    current_reservation = reservations.filter(status='in_house').first()
    
    context = {
        'guest': guest,
        'form': form,
        'reservations': reservations,
        'total_reservations': total_reservations,
        'completed_stays': completed_stays,
        'total_nights': total_nights,
        'upcoming_reservations': upcoming_reservations,
        'current_reservation': current_reservation,
        'auto_edit': edit_mode,
    }
    return render(request, 'pms/guest_detail.html', context)

def guest_list_json(request):
    guests = Guest.objects.all().order_by('-id')
    data = [
        {
            "id": g.id, 
            "name": g.name,
            "email": g.email or "",
            "phone": g.phone or ""
        } for g in guests
    ]
    return JsonResponse({"guests": data})

def check_reservation_conflict(request):
    """AJAX endpoint to check for reservation conflicts"""
    if request.method == 'GET':
        room_id = request.GET.get('room_id')
        check_in = request.GET.get('check_in')
        check_out = request.GET.get('check_out')
        current_reservation_id = request.GET.get('current_reservation_id')
        
        if not all([room_id, check_in, check_out]):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        try:
            from datetime import datetime
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            if check_out_date <= check_in_date:
                return JsonResponse({
                    'conflict': True,
                    'message': 'Check-out date must be after check-in date'
                })
            
            # Check for overlapping reservations
            active_statuses = ['confirmed', 'expected_arrival', 'in_house']
            overlapping = Reservation.objects.filter(
                room_id=room_id,
                check_in__lt=check_out_date,
                check_out__gt=check_in_date,
                status__in=active_statuses
            )
            
            # Exclude current reservation if editing
            if current_reservation_id:
                overlapping = overlapping.exclude(id=current_reservation_id)
            
            if overlapping.exists():
                conflicting_reservation = overlapping.first()
                return JsonResponse({
                    'conflict': True,
                    'message': f'Room is already reserved by {conflicting_reservation.guest.name} from {conflicting_reservation.check_in} to {conflicting_reservation.check_out}'
                })
            
            return JsonResponse({'conflict': False})
            
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def check_available_rooms(request):
    """AJAX endpoint to get available rooms for given dates"""
    if request.method == 'GET':
        check_in = request.GET.get('check_in')
        check_out = request.GET.get('check_out')
        
        if not all([check_in, check_out]):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        try:
            from datetime import datetime
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            if check_out_date <= check_in_date:
                return JsonResponse({
                    'error': 'Check-out date must be after check-in date'
                }, status=400)
            
            # Get all rooms
            all_rooms = Room.objects.all()
            
            # Find rooms that have conflicting reservations
            active_statuses = ['confirmed', 'expected_arrival', 'in_house']
            conflicting_room_ids = Reservation.objects.filter(
                check_in__lt=check_out_date,
                check_out__gt=check_in_date,
                status__in=active_statuses
            ).values_list('room_id', flat=True)
            
            # Get available rooms (exclude conflicting ones)
            available_rooms = all_rooms.exclude(id__in=conflicting_room_ids)
            
            # Format response data
            rooms_data = []
            for room in available_rooms:
                rooms_data.append({
                    'id': room.id,
                    'room_number': room.room_number,
                    'room_type': room.room_type,
                    'price_per_night': float(room.rate),
                    'status': room.status
                })
            
            return JsonResponse({
                'available_rooms': rooms_data,
                'total_available': len(rooms_data)
            })
            
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)