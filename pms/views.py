from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, date, time, timedelta
from calendar import monthrange
from .models import Room, Reservation, HotelSettings, Guest, PaymentMethod, Agent
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
        'payment_method': 'payment_method__name'
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
        # Modified logic: room is ready if it's vacant_clean OR if it's occupied by this same reservation
        room_is_vacant_clean = reservation.room.status == 'vacant_clean'
        room_occupied_by_this_guest = (
            reservation.room.status == 'occupied' and 
            Reservation.objects.filter(
                room=reservation.room,
                check_in__lte=date.today(),
                check_out__gt=date.today(),
                status='expected_arrival',
                id=reservation.id
            ).exists()
        )
        room_ready = room_is_vacant_clean or room_occupied_by_this_guest
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

    # Current reservations (active today) - Updated for consistency
    actual_room_count = Room.objects.count()  # Use actual room count
    occupied_rooms_today = 0
    
    for room in Room.objects.all():
        is_occupied = Reservation.objects.filter(
            room=room,
            check_in__lte=today,
            check_out__gt=today,  # Don't count check-out day
            status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
        ).exists()
        if is_occupied:
            occupied_rooms_today += 1
    
    daily_occupancy = (occupied_rooms_today / actual_room_count) * 100 if actual_room_count > 0 else 0
    
    # Get reservations for display purposes
    reservations = Reservation.objects.filter(
        check_in__lte=today,
        check_out__gt=today,
        status__in=['confirmed', 'expected_arrival', 'in_house']
    )

    # Weekly occupancy - Updated to match occupancy report logic
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    days_in_week = 7
    actual_room_count = Room.objects.count()
    total_room_nights_week = actual_room_count * days_in_week
    booked_room_nights_week = 0
    
    # Calculate day-by-day for consistency
    for current_date in [week_start + timedelta(days=i) for i in range(days_in_week)]:
        for room in Room.objects.all():
            is_occupied = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,  # Don't count check-out day
                status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
            ).exists()
            if is_occupied:
                booked_room_nights_week += 1
    
    weekly_occupancy = (booked_room_nights_week / total_room_nights_week) * 100 if total_room_nights_week > 0 else 0

    # Monthly occupancy for current month (confirmed/arrival/departure/in_house/checked_out)
    year = today.year
    month = today.month
    days_in_month = monthrange(year, month)[1]
    actual_room_count = Room.objects.count()  # Get actual room count
    total_room_nights = actual_room_count * days_in_month  # Use actual count instead of hardcoded 5
    booked_room_nights = 0
    month_start = date(year, month, 1)
    month_end = month_start + timedelta(days=days_in_month)
    
    # Monthly occupancy - Updated to match occupancy report logic
    for current_date in [month_start + timedelta(days=i) for i in range(days_in_month)]:
        for room in Room.objects.all():
            is_occupied = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,  # Don't count check-out day
                status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
            ).exists()
            if is_occupied:
                booked_room_nights += 1
    sold_room_nights = 0
    for current_date in [month_start + timedelta(days=i) for i in range(days_in_month)]:
        for room in Room.objects.all():
            is_sold = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,  # Don't count check-out day
                status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
            ).exists()
            if is_sold:
                sold_room_nights += 1
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
        'monthly_nights_sold': sold_room_nights,
        'target_occupancy': 80,
        'month_name': today.strftime('%B %Y'),
        'all_reservations': all_reservations
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
    # Only include vacant_clean rooms as available for booking
    available_rooms = Room.objects.filter(
        status='vacant_clean'
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
        'payment_methods': PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name'),
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
    """Enhanced view for comprehensive room management"""
    from .models import Room, RoomMaintenanceLog
    from django.shortcuts import redirect
    from django.contrib import messages
    from datetime import datetime, date
    
    if request.method == 'POST':
        action = request.POST.get('action')
        room_id = request.POST.get('room_id')
        room = get_object_or_404(Room, id=room_id)
        
        if action == 'mark_clean':
            if room.status == 'vacant_dirty':
                room.status = 'vacant_clean'
                room.last_cleaned = datetime.now()
                room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
                room.status_reason = 'Marked as clean by housekeeping'
                room.save()
                messages.success(request, f'Room {room.room_number} marked as clean.')
        
        elif action == 'set_maintenance':
            start_date = request.POST.get('maintenance_start_date')
            end_date = request.POST.get('maintenance_end_date')
            notes = request.POST.get('maintenance_notes', '')
            changed_by = request.user.username if request.user.is_authenticated else 'System'
            
            if start_date:
                # Convert empty string to None for end_date
                end_date = end_date if end_date else None
                room.set_maintenance(start_date, end_date, notes, changed_by)
                messages.success(request, f'Room {room.room_number} scheduled for maintenance.')
        
        elif action == 'set_out_of_order':
            reason = request.POST.get('ooo_reason', '')
            end_date = request.POST.get('ooo_end_date')
            changed_by = request.user.username if request.user.is_authenticated else 'System'
            
            # Convert empty string to None for end_date
            end_date = end_date if end_date else None
            room.set_out_of_order(reason, changed_by, end_date)
            messages.success(request, f'Room {room.room_number} marked as out of order.')
        
        elif action == 'set_out_of_service':
            reason = request.POST.get('oos_reason', '')
            room.status = 'out_of_service'
            room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
            room.status_reason = reason
            room.save()
            messages.success(request, f'Room {room.room_number} marked as out of service.')
        
        elif action == 'return_to_service':
            room.status = 'vacant_clean'
            room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
            room.status_reason = 'Returned to service'
            room.maintenance_start_date = None
            room.maintenance_end_date = None
            room.maintenance_notes = ''
            room.save()
            messages.success(request, f'Room {room.room_number} returned to service.')
        
        elif action == 'update_housekeeping_notes':
            notes = request.POST.get('housekeeping_notes', '')
            room.housekeeping_notes = notes
            room.save()
            messages.success(request, f'Housekeeping notes updated for room {room.room_number}.')
        
        return redirect('rooms_list')
    
    # GET request - display rooms with enhanced information
    rooms = Room.objects.all().order_by('room_number')
    
    # Add additional context for each room
    for room in rooms:
        # Get recent reservations
        room.recent_reservations = room.get_reservation_history(5)
        # Get occupancy rate for last 30 days
        room.occupancy_rate = room.get_occupancy_rate()
        # Get maintenance logs
        room.recent_maintenance = room.maintenance_logs.all()[:3]
        # Check if room has current guest
        today = date.today()
        room.current_guest = room.reservation_set.filter(
            check_in__lte=today,
            check_out__gt=today,
            status='in_house'
        ).first()
    
    # Room statistics
    total_rooms = rooms.count()
    vacant_clean = rooms.filter(status='vacant_clean').count()
    vacant_dirty = rooms.filter(status='vacant_dirty').count()
    occupied = rooms.filter(status='occupied').count()
    maintenance = rooms.filter(status='maintenance').count()
    out_of_order = rooms.filter(status='out_of_order').count()
    out_of_service = rooms.filter(status='out_of_service').count()
    
    context = {
        'rooms': rooms,
        'room_stats': {
            'total': total_rooms,
            'vacant_clean': vacant_clean,
            'vacant_dirty': vacant_dirty,
            'occupied': occupied,
            'maintenance': maintenance,
            'out_of_order': out_of_order,
            'out_of_service': out_of_service,
            'available': vacant_clean,
            'unavailable': maintenance + out_of_order + out_of_service,
        }
    }
    
    return render(request, 'pms/rooms.html', context)


def room_detail(request, room_id):
    """Detailed view for individual room management"""
    room = get_object_or_404(Room, id=room_id)
    
    # Handle POST requests for room status updates
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'mark_clean':
            if room.status == 'vacant_dirty':
                room.status = 'vacant_clean'
                room.last_cleaned = datetime.now()
                room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
                room.status_reason = 'Marked as clean by housekeeping'
                room.save()
                messages.success(request, f'Room {room.room_number} marked as clean.')
        
        elif action == 'set_maintenance':
            start_date = request.POST.get('maintenance_start_date')
            end_date = request.POST.get('maintenance_end_date')
            notes = request.POST.get('maintenance_notes', '')
            changed_by = request.user.username if request.user.is_authenticated else 'System'
            
            if start_date:
                # Convert empty string to None for end_date
                end_date = end_date if end_date else None
                room.set_maintenance(start_date, end_date, notes, changed_by)
                messages.success(request, f'Room {room.room_number} scheduled for maintenance.')
        
        elif action == 'set_out_of_order':
            reason = request.POST.get('ooo_reason', '')
            end_date = request.POST.get('ooo_end_date')
            changed_by = request.user.username if request.user.is_authenticated else 'System'
            
            # Convert empty string to None for end_date
            end_date = end_date if end_date else None
            room.set_out_of_order(reason, changed_by, end_date)
            messages.success(request, f'Room {room.room_number} marked as out of order.')
        
        elif action == 'set_out_of_service':
            reason = request.POST.get('oos_reason', '')
            room.status = 'out_of_service'
            room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
            room.status_reason = reason
            room.save()
            messages.success(request, f'Room {room.room_number} marked as out of service.')
        
        elif action == 'return_to_service':
            room.status = 'vacant_clean'
            room.status_changed_by = request.user.username if request.user.is_authenticated else 'System'
            room.status_reason = 'Returned to service'
            room.maintenance_start_date = None
            room.maintenance_end_date = None
            room.maintenance_notes = ''
            room.save()
            messages.success(request, f'Room {room.room_number} returned to service.')
        
        elif action == 'update_housekeeping_notes':
            notes = request.POST.get('housekeeping_notes', '')
            room.housekeeping_notes = notes
            room.save()
            messages.success(request, f'Housekeeping notes updated for room {room.room_number}.')
        
        return redirect('room_detail', room_id=room.id)
    
    # GET request - Get comprehensive room data
    reservation_history = room.get_reservation_history(20)
    maintenance_logs = room.maintenance_logs.all()
    occupancy_rate_30d = room.get_occupancy_rate()
    occupancy_rate_90d = room.get_occupancy_rate(
        start_date=date.today() - timedelta(days=90)
    )
    
    # Calculate revenue for last 30 and 90 days
    from django.db.models import Sum
    # Include all revenue-generating statuses (no_show typically still generates revenue)
    revenue_statuses = ['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
    revenue_30d = room.reservation_set.filter(
        check_in__gte=date.today() - timedelta(days=30),
        status__in=revenue_statuses
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_90d = room.reservation_set.filter(
        check_in__gte=date.today() - timedelta(days=90),
        status__in=revenue_statuses
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Get current reservation if any
    current_reservation = room.reservation_set.filter(
        check_in__lte=date.today(),
        check_out__gt=date.today(),
        status='in_house'
    ).first()
    
    # Get upcoming reservations
    upcoming_reservations = room.reservation_set.filter(
        check_in__gt=date.today(),
        status__in=['confirmed', 'expected_arrival']
    ).order_by('check_in')[:5]
    
    context = {
        'room': room,
        'reservation_history': reservation_history,
        'maintenance_logs': maintenance_logs,
        'current_reservation': current_reservation,
        'upcoming_reservations': upcoming_reservations,
        'occupancy_30_days': round(occupancy_rate_30d, 1),
        'occupancy_90_days': round(occupancy_rate_90d, 1),
        'revenue_30d': revenue_30d,
        'revenue_90d': revenue_90d,
        'amenities_list': room.get_amenities_list(),
    }
    
    return render(request, 'pms/room_detail.html', context)


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
                    return JsonResponse({
                        'success': True, 
                        'guest_id': guest.id,
                        'guest': {
                            'id': guest.id,
                            'name': guest.name,
                            'email': guest.email or '',
                            'phone': guest.phone or ''
                        }
                    })
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
            
            # Get available rooms (exclude conflicting ones and rooms not available for booking)
            # Rooms must be vacant_clean and not in maintenance/out of order/out of service
            available_rooms = all_rooms.exclude(id__in=conflicting_room_ids).filter(
                status='vacant_clean'
            )
            
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


def reports_home(request):
    """View for reports dashboard/home page"""
    # You can add any summary data here if needed
    context = {
        'page_title': 'Reports Dashboard'
    }
    return render(request, 'pms/reports/reports_home.html', context)



def revenue_report(request):
    """View for generating detailed revenue reports"""
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    room_type = request.GET.get('room_type', '')
    
    # Default to current month if no dates provided
    today = date.today()
    if not start_date_str:
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get reservations in date range
    reservations = Reservation.objects.filter(
        check_in__lte=end_date,
        check_out__gte=start_date,
        status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
    )
    
    if room_type:
        reservations = reservations.filter(room__room_type=room_type)
    
    # Calculate total revenue
    total_revenue = sum(res.total_amount for res in reservations if res.total_amount)
    
    # Calculate occupied room nights and daily revenue
    date_range = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(date_range)]
    
    occupied_nights = 0
    daily_revenue = []
    
    for current_date in dates:
        day_reservations = reservations.filter(
            check_in__lte=current_date,
            check_out__gt=current_date
        )
        day_revenue = 0
        for res in day_reservations:
            if res.total_amount:
                nights = (res.check_out - res.check_in).days
                day_revenue += res.total_amount / nights if nights > 0 else 0
        
        daily_revenue.append({
            'date': current_date,
            'revenue': day_revenue,
            'occupied_rooms': day_reservations.count()
        })
        occupied_nights += day_reservations.count()
    
    # Calculate ADR (Average Daily Rate)
    adr = total_revenue / occupied_nights if occupied_nights > 0 else 0
    
    # Calculate RevPAR (Revenue Per Available Room)
    total_rooms = Room.objects.count()
    available_room_nights = total_rooms * date_range
    revpar = total_revenue / available_room_nights if available_room_nights > 0 else 0
    
    # Revenue by room type
    room_type_revenue = {}
    for room_type_choice, room_type_name in Room.ROOM_TYPES:
        type_reservations = reservations.filter(room__room_type=room_type_choice)
        type_revenue = sum(res.total_amount for res in type_reservations if res.total_amount)
        type_nights = sum((res.check_out - res.check_in).days for res in type_reservations)
        type_adr = type_revenue / type_nights if type_nights > 0 else 0
        
        if type_revenue > 0:  # Only include room types with revenue
            room_type_revenue[room_type_name] = {
                'revenue': type_revenue,
                'nights': type_nights,
                'adr': type_adr
            }
    
    # Revenue by payment method
    payment_method_revenue = {}
    # Get active payment methods from the database
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    for payment_method in payment_methods:
        method_revenue = sum(res.total_amount for res in reservations 
                           if res.payment_method == payment_method and res.total_amount)
        if method_revenue > 0:  # Only include methods with revenue
            payment_method_revenue[payment_method.name] = method_revenue
    
    # Revenue by agent/source
    agent_revenue = {}
    # Get active agents from the database
    agents = Agent.objects.filter(is_active=True)
    for agent in agents:
        agent_rev = sum(res.total_amount for res in reservations 
                       if res.agent == agent and res.total_amount)
        if agent_rev > 0:  # Only include agents with revenue
            agent_revenue[agent.name] = agent_rev
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_revenue': total_revenue,
        'adr': adr,
        'revpar': revpar,
        'occupied_nights': occupied_nights,
        'daily_revenue': daily_revenue,
        'room_type_revenue': room_type_revenue,
        'payment_method_revenue': payment_method_revenue,
        'agent_revenue': agent_revenue,
        'room_types': Room.ROOM_TYPES,
        'selected_room_type': room_type
    }
    
    return render(request, 'pms/reports/revenue_report.html', context)

def occupancy_report(request):
    """View for generating detailed occupancy reports"""
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    room_type = request.GET.get('room_type', '')
    
    # Default to current month if no dates provided
    today = date.today()
    if not start_date_str:
        # Default to first day of current month
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        # Default to last day of current month
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get all rooms, filtered by type if specified
    rooms = Room.objects.all()
    if room_type:
        rooms = rooms.filter(room_type=room_type)
    
    # Calculate date range
    date_range = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(date_range)]
    
    # Initialize data structures
    daily_occupancy = []
    room_occupancy = {}
    total_rooms = rooms.count()
    total_room_nights = total_rooms * date_range
    occupied_room_nights = 0
    
    # Calculate occupancy for each day
    for current_date in dates:
        occupied_rooms = 0
        for room in rooms:
            # Check if room is occupied on this date
            is_occupied = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,
                status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
            ).exists()
            
            if is_occupied:
                occupied_rooms += 1
                # Track occupancy by room
                if room.room_number not in room_occupancy:
                    room_occupancy[room.room_number] = 0
                room_occupancy[room.room_number] += 1
        
        # Calculate daily occupancy percentage
        daily_percentage = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
        occupied_room_nights += occupied_rooms
        
        # Add to daily occupancy list
        daily_occupancy.append({
            'date': current_date,
            'occupied': occupied_rooms,
            'total': total_rooms,
            'percentage': daily_percentage
        })
    
    # Calculate overall occupancy percentage
    overall_occupancy = (occupied_room_nights / total_room_nights * 100) if total_room_nights > 0 else 0
    
    # Calculate occupancy by room type
    room_type_occupancy = {}
    for room_type_choice, room_type_name in Room.ROOM_TYPES:
        type_rooms = rooms.filter(room_type=room_type_choice)
        type_room_count = type_rooms.count()
        if type_room_count > 0:
            type_occupied_nights = 0
            for current_date in dates:
                for room in type_rooms:
                    is_occupied = Reservation.objects.filter(
                        room=room,
                        check_in__lte=current_date,
                        check_out__gt=current_date,
                        status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
                    ).exists()
                    if is_occupied:
                        type_occupied_nights += 1
            
            type_total_nights = type_room_count * date_range
            type_percentage = (type_occupied_nights / type_total_nights * 100) if type_total_nights > 0 else 0
            room_type_occupancy[room_type_name] = {
                'occupied_nights': type_occupied_nights,
                'total_nights': type_total_nights,
                'percentage': type_percentage
            }
    
    # Calculate day of week occupancy
    weekday_occupancy = {i: {'occupied': 0, 'total': 0} for i in range(7)}
    for entry in daily_occupancy:
        weekday = entry['date'].weekday()
        weekday_occupancy[weekday]['occupied'] += entry['occupied']
        weekday_occupancy[weekday]['total'] += entry['total']
    
    # Calculate percentages for weekdays
    for weekday, data in weekday_occupancy.items():
        if data['total'] > 0:
            data['percentage'] = (data['occupied'] / data['total']) * 100
        else:
            data['percentage'] = 0
    
    # Format weekday data for template
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = [{
        'name': weekday_names[i],
        'percentage': weekday_occupancy[i]['percentage']
    } for i in range(7)]
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'daily_occupancy': daily_occupancy,
        'overall_occupancy': overall_occupancy,
        'room_occupancy': sorted([(room, (nights/date_range)*100) for room, nights in room_occupancy.items()], 
                                key=lambda x: x[1], reverse=True),
        'room_type_occupancy': room_type_occupancy,
        'weekday_data': weekday_data,
        'room_types': Room.ROOM_TYPES,
        'selected_room_type': room_type
    }
    
    return render(request, 'pms/reports/occupancy_report.html', context)


def forecast_report(request):
    """View for generating forecast and trends analysis with industry best practices"""
    from django.db.models import Count, Avg, Sum, Q
    from collections import defaultdict
    import calendar
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    forecast_period = request.GET.get('forecast_period', '30')  # Default 30 days
    
    # Industry best practice: Dynamic historical period based on forecast length
    today = date.today()
    forecast_days = int(forecast_period)
    
    # Calculate optimal historical period (3-5x forecast period, minimum 90 days)
    if forecast_days <= 30:
        # Short-term forecast: 1 year history optimal
        optimal_history_days = max(365, forecast_days * 4)
    elif forecast_days <= 90:
        # Medium-term forecast: 2 years history optimal  
        optimal_history_days = max(730, forecast_days * 4)
    else:
        # Long-term forecast: 3 years history optimal
        optimal_history_days = max(1095, forecast_days * 3)
    
    if not start_date_str:
        # Use optimal historical period
        start_date = today - timedelta(days=optimal_history_days)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        end_date = today
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Calculate forecast end date
    forecast_end_date = today + timedelta(days=forecast_days)
    
    # Calculate actual historical period used
    historical_days = (end_date - start_date).days
    
    # Get historical data for analysis
    historical_reservations = Reservation.objects.filter(
        check_in__range=[start_date, end_date],
        status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
    )
    
    # Monthly trends analysis (last 12 months)
    monthly_trends = []
    for i in range(12):
        month_start = today.replace(day=1) - timedelta(days=30*i)
        month_start = month_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        month_reservations = Reservation.objects.filter(
            check_in__range=[month_start, month_end],
            status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
        )
        
        month_revenue = float(sum(r.total_amount for r in month_reservations))
        month_nights = sum((r.check_out - r.check_in).days for r in month_reservations)
        
        # Calculate occupancy for the month
        total_rooms = Room.objects.count()
        days_in_month = (month_end - month_start).days + 1
        total_room_nights = total_rooms * days_in_month
        occupancy_rate = (month_nights / total_room_nights * 100) if total_room_nights > 0 else 0
        
        monthly_trends.append({
            'month': month_start.strftime('%b %Y'),
            'month_date': month_start,
            'reservations': month_reservations.count(),
            'revenue': month_revenue,
            'nights': month_nights,
            'occupancy': occupancy_rate,
            'adr': month_revenue / month_nights if month_nights > 0 else 0
        })
    
    monthly_trends.reverse()  # Show oldest to newest
    
    # Seasonal analysis (by quarter)
    seasonal_data = {}
    quarters = {
        'Q1': [1, 2, 3],
        'Q2': [4, 5, 6], 
        'Q3': [7, 8, 9],
        'Q4': [10, 11, 12]
    }
    
    for quarter, months in quarters.items():
        quarter_reservations = historical_reservations.filter(
            check_in__month__in=months
        )
        quarter_revenue = float(sum(r.total_amount for r in quarter_reservations))
        quarter_nights = sum((r.check_out - r.check_in).days for r in quarter_reservations)
        
        seasonal_data[quarter] = {
            'reservations': quarter_reservations.count(),
            'revenue': quarter_revenue,
            'nights': quarter_nights,
            'avg_adr': quarter_revenue / quarter_nights if quarter_nights > 0 else 0
        }
    
    # Day of week analysis
    weekday_analysis = {}
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for i, day_name in enumerate(weekday_names):
        day_reservations = [r for r in historical_reservations if r.check_in.weekday() == i]
        day_revenue = float(sum(r.total_amount for r in day_reservations))
        
        weekday_analysis[day_name] = {
            'reservations': len(day_reservations),
            'revenue': day_revenue,
            'avg_revenue': day_revenue / len(day_reservations) if day_reservations else 0
        }
    
    # Calculate forecast metrics based on historical trends with enhanced confidence
    # Use adaptive moving average based on forecast period
    if forecast_days <= 30:
        # Short-term: Use last 2-3 months
        recent_months = monthly_trends[-2:] if len(monthly_trends) >= 2 else monthly_trends
    elif forecast_days <= 90:
        # Medium-term: Use last 3-6 months
        recent_months = monthly_trends[-4:] if len(monthly_trends) >= 4 else monthly_trends
    else:
        # Long-term: Use last 6-12 months
        recent_months = monthly_trends[-8:] if len(monthly_trends) >= 8 else monthly_trends
    
    avg_monthly_reservations = sum(m['reservations'] for m in recent_months) / len(recent_months) if recent_months else 0
    avg_monthly_revenue = sum(m['revenue'] for m in recent_months) / len(recent_months) if recent_months else 0
    avg_monthly_occupancy = sum(m['occupancy'] for m in recent_months) / len(recent_months) if recent_months else 0
    
    # Project forecast for the selected period
    forecast_multiplier = forecast_days / 30  # Scale based on forecast period
    
    # Enhanced confidence calculation based on industry standards
    def calculate_confidence_level(historical_days, forecast_days, data_points):
        # Rule: Historical data should be 3-5x forecast period
        ratio = historical_days / forecast_days if forecast_days > 0 else 0
        
        # Data quality based on number of months with data
        data_quality = min(data_points / 12, 1.0)  # Normalize to 12 months
        
        if ratio >= 5 and data_quality >= 0.75:
            return 'High'
        elif ratio >= 3 and data_quality >= 0.5:
            return 'Medium'  
        elif ratio >= 2 and data_quality >= 0.25:
            return 'Low'
        else:
            return 'Very Low'
    
    # Seasonal adjustment for glamping business
    current_month = today.month
    forecast_month = forecast_end_date.month
    
    # Define seasonal patterns for glamping
    peak_season = [6, 7, 8, 12]      # Jun, Jul, Aug, Dec
    shoulder_season = [4, 5, 9, 10]   # Apr, May, Sep, Oct  
    low_season = [1, 2, 3, 11]       # Jan, Feb, Mar, Nov
    
    base_confidence = calculate_confidence_level(historical_days, forecast_days, len(recent_months))
    
    # Adjust confidence based on seasonal patterns
    seasonal_adjustment = 0
    if current_month in peak_season and forecast_month in peak_season:
        seasonal_adjustment = 0.1  # Higher confidence in peak-to-peak
    elif current_month in low_season and forecast_month in peak_season:
        seasonal_adjustment = -0.1  # Lower confidence crossing seasons
    
    confidence_levels = ['Very Low', 'Low', 'Medium', 'High']
    current_index = confidence_levels.index(base_confidence)
    
    if seasonal_adjustment > 0 and current_index < len(confidence_levels) - 1:
        adjusted_confidence = confidence_levels[current_index + 1]
    elif seasonal_adjustment < 0 and current_index > 0:
        adjusted_confidence = confidence_levels[current_index - 1]
    else:
        adjusted_confidence = base_confidence
    
    forecast_metrics = {
        'period_days': forecast_days,
        'end_date': forecast_end_date,
        'projected_reservations': int(avg_monthly_reservations * forecast_multiplier),
        'projected_revenue': avg_monthly_revenue * forecast_multiplier,
        'projected_occupancy': avg_monthly_occupancy,
        'confidence_level': adjusted_confidence,
        'historical_days': historical_days,
        'data_quality': len(recent_months),
        'seasonal_context': 'Peak Season' if forecast_month in peak_season else 'Shoulder Season' if forecast_month in shoulder_season else 'Low Season'
    }
    
    # Growth rate analysis
    if len(monthly_trends) >= 2:
        recent_revenue = monthly_trends[-1]['revenue']
        previous_revenue = monthly_trends[-2]['revenue']
        revenue_growth = ((recent_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
        
        recent_occupancy = monthly_trends[-1]['occupancy']
        previous_occupancy = monthly_trends[-2]['occupancy']
        occupancy_growth = recent_occupancy - previous_occupancy
    else:
        revenue_growth = 0
        occupancy_growth = 0
    
    # Key performance indicators
    total_rooms = Room.objects.count()
    current_month_start = today.replace(day=1)
    current_month_reservations = Reservation.objects.filter(
        check_in__gte=current_month_start,
        check_in__lt=today,
        status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
    )
    
    current_month_revenue = float(sum(r.total_amount for r in current_month_reservations))
    current_month_nights = sum((r.check_out - r.check_in).days for r in current_month_reservations)
    
    # Upcoming reservations (next 30 days)
    upcoming_reservations = Reservation.objects.filter(
        check_in__range=[today, today + timedelta(days=30)],
        status__in=['confirmed', 'expected_arrival']
    )
    
    upcoming_revenue = float(sum(r.total_amount for r in upcoming_reservations))
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'forecast_period': forecast_period,
        'forecast_end_date': forecast_end_date,
        'monthly_trends': monthly_trends,
        'seasonal_data': seasonal_data,
        'weekday_analysis': weekday_analysis,
        'forecast_metrics': forecast_metrics,
        'revenue_growth': revenue_growth,
        'occupancy_growth': occupancy_growth,
        'current_month_revenue': current_month_revenue,
        'current_month_reservations': current_month_reservations.count(),
        'upcoming_reservations': upcoming_reservations.count(),
        'upcoming_revenue': upcoming_revenue,
        'total_rooms': total_rooms,
    }
    
    return render(request, 'pms/reports/forecast_report.html', context)


def operational_report(request):
    """View for generating operational reports - housekeeping, maintenance, and operational KPIs"""
    from django.db.models import Count, Q, Avg
    from collections import defaultdict
    
    # Get date range parameters (consistent with other reports)
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    # Default to current week if no dates provided
    today = date.today()
    if not start_date_str:
        # Default to start of current week (Monday)
        start_date = today - timedelta(days=today.weekday())
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        # Default to end of current week (Sunday)
        end_date = start_date + timedelta(days=6)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Calculate date range
    date_range = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(date_range)]
    
    # Room Status Overview
    room_status_counts = {}
    for status_code, status_name in Room.STATUS_CHOICES:
        count = Room.objects.filter(status=status_code).count()
        room_status_counts[status_name] = count
    
    total_rooms = Room.objects.count()
    
    # Housekeeping Metrics
    rooms_needing_cleaning = Room.objects.filter(status='vacant_dirty').count()
    rooms_out_of_order = Room.objects.filter(status='out_of_order').count()
    rooms_in_maintenance = Room.objects.filter(status='maintenance').count()
    rooms_ready = Room.objects.filter(status='vacant_clean').count()
    
    # Calculate housekeeping efficiency
    housekeeping_efficiency = (rooms_ready / total_rooms * 100) if total_rooms > 0 else 0
    
    # Today's Operations (for the most recent date in range)
    latest_date = end_date
    today_arrivals = Reservation.objects.filter(
        check_in=latest_date,
        status__in=['confirmed', 'expected_arrival', 'in_house']
    ).select_related('guest', 'room')
    
    today_departures = Reservation.objects.filter(
        check_out=latest_date,
        status__in=['in_house', 'expected_departure', 'checked_out']
    ).select_related('guest', 'room')
    
    # Period Operations Summary (for entire date range)
    period_arrivals = Reservation.objects.filter(
        check_in__range=[start_date, end_date],
        status__in=['confirmed', 'expected_arrival', 'in_house', 'checked_out']
    )
    
    period_departures = Reservation.objects.filter(
        check_out__range=[start_date, end_date],
        status__in=['in_house', 'expected_departure', 'checked_out']
    )
    
    # Check-in/Check-out Performance for the period
    checked_in_period = Reservation.objects.filter(
        check_in__range=[start_date, end_date],
        status__in=['in_house', 'checked_out']
    ).count()
    
    checked_out_period = Reservation.objects.filter(
        check_out__range=[start_date, end_date],
        status='checked_out'
    ).count()
    
    # No-shows and cancellations for the period
    no_shows_period = Reservation.objects.filter(
        check_in__range=[start_date, end_date],
        status='no_show'
    ).count()
    
    cancellations_period = Reservation.objects.filter(
        check_in__range=[start_date, end_date],
        status='canceled'
    ).count()
    
    # Calculate operational KPIs for the period
    total_expected_arrivals = period_arrivals.count()
    total_expected_departures = period_departures.count()
    
    arrival_completion_rate = (checked_in_period / total_expected_arrivals * 100) if total_expected_arrivals > 0 else 0
    departure_completion_rate = (checked_out_period / total_expected_departures * 100) if total_expected_departures > 0 else 0
    no_show_rate = (no_shows_period / total_expected_arrivals * 100) if total_expected_arrivals > 0 else 0
    
    # Room Turnover Analysis for the period
    rooms_turned_over = Room.objects.filter(
        reservation__check_out__range=[start_date, end_date],
        reservation__status='checked_out'
    ).distinct().count()
    
    # Daily Operational Trends for the selected period
    daily_trends = []
    for current_date in dates:
        daily_arrivals = Reservation.objects.filter(
            check_in=current_date,
            status__in=['confirmed', 'expected_arrival', 'in_house', 'checked_out']
        ).count()
        
        daily_departures = Reservation.objects.filter(
            check_out=current_date,
            status__in=['in_house', 'expected_departure', 'checked_out']
        ).count()
        
        daily_no_shows = Reservation.objects.filter(
            check_in=current_date,
            status='no_show'
        ).count()
        
        daily_trends.append({
            'date': current_date,
            'arrivals': daily_arrivals,
            'departures': daily_departures,
            'no_shows': daily_no_shows
        })
    
    # Room Type Performance
    room_type_performance = {}
    for room_type_code, room_type_name in Room.ROOM_TYPES:
        type_rooms = Room.objects.filter(room_type=room_type_code)
        type_total = type_rooms.count()
        type_occupied = type_rooms.filter(status='occupied').count()
        type_dirty = type_rooms.filter(status='vacant_dirty').count()
        type_maintenance = type_rooms.filter(status__in=['maintenance', 'out_of_order']).count()
        
        room_type_performance[room_type_name] = {
            'total': type_total,
            'occupied': type_occupied,
            'dirty': type_dirty,
            'maintenance': type_maintenance,
            'ready': type_total - type_occupied - type_dirty - type_maintenance
        }
    
    # Payment Method Analysis for the period
    payment_method_stats = defaultdict(int)
    period_reservations = Reservation.objects.filter(
        check_in__range=[start_date, end_date]
    ).select_related('payment_method')
    
    for reservation in period_reservations:
        if reservation.payment_method:
            payment_method_stats[reservation.payment_method.name] += 1
        else:
            payment_method_stats['Not Specified'] += 1
    
    # Agent Performance for the period
    agent_stats = defaultdict(int)
    for reservation in period_reservations:
        if reservation.agent:
            agent_stats[reservation.agent.name] += 1
        else:
            agent_stats['Direct Booking'] += 1
    
    # Critical Alerts
    alerts = []
    
    # High number of dirty rooms
    if rooms_needing_cleaning > total_rooms * 0.3:  # More than 30% dirty
        alerts.append({
            'type': 'warning',
            'message': f'High number of rooms needing cleaning: {rooms_needing_cleaning} rooms'
        })
    
    # Rooms out of order
    if rooms_out_of_order > 0:
        alerts.append({
            'type': 'danger',
            'message': f'{rooms_out_of_order} room(s) are out of order'
        })
    
    # High no-show rate
    if no_show_rate > 10:  # More than 10% no-show rate
        alerts.append({
            'type': 'warning',
            'message': f'High no-show rate: {no_show_rate:.1f}%'
        })
    
    # Low housekeeping efficiency
    if housekeeping_efficiency < 70:  # Less than 70% rooms ready
        alerts.append({
            'type': 'warning',
            'message': f'Low housekeeping efficiency: {housekeeping_efficiency:.1f}% rooms ready'
        })
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'room_status_counts': room_status_counts,
        'total_rooms': total_rooms,
        'rooms_needing_cleaning': rooms_needing_cleaning,
        'rooms_out_of_order': rooms_out_of_order,
        'rooms_in_maintenance': rooms_in_maintenance,
        'rooms_ready': rooms_ready,
        'housekeeping_efficiency': housekeeping_efficiency,
        'today_arrivals': today_arrivals,
        'today_departures': today_departures,
        'checked_in_period': checked_in_period,
        'checked_out_period': checked_out_period,
        'no_shows_period': no_shows_period,
        'cancellations_period': cancellations_period,
        'total_expected_arrivals': total_expected_arrivals,
        'total_expected_departures': total_expected_departures,
        'arrival_completion_rate': arrival_completion_rate,
        'departure_completion_rate': departure_completion_rate,
        'no_show_rate': no_show_rate,
        'rooms_turned_over': rooms_turned_over,
        'daily_trends': daily_trends,
        'room_type_performance': room_type_performance,
        'payment_method_stats': dict(payment_method_stats),
        'agent_stats': dict(agent_stats),
        'alerts': alerts,
    }
    
    return render(request, 'pms/reports/operational_report.html', context)


def booking_sources_report(request):
    """View for generating booking sources and channel performance reports"""
    
    def calculate_performance_score(conversion_rate, booking_count, revenue, total_bookings, total_revenue):
        """
        Calculate a comprehensive performance score based on multiple factors:
        - Conversion Rate (40% weight)
        - Volume Significance (30% weight) 
        - Revenue Contribution (20% weight)
        - Statistical Reliability (10% weight)
        """
        # Convert decimal values to float to avoid type errors
        revenue = float(revenue) if revenue else 0
        total_revenue = float(total_revenue) if total_revenue else 0
        
        # Conversion Rate Score (0-100)
        conversion_score = min(conversion_rate, 100)
        
        # Volume Significance Score (0-100)
        # Higher booking count gets higher score, with diminishing returns
        volume_percentage = (booking_count / total_bookings * 100) if total_bookings > 0 else 0
        volume_score = min(volume_percentage * 2, 100)  # Scale up to make volume more impactful
        
        # Revenue Contribution Score (0-100)
        revenue_percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0
        revenue_score = min(revenue_percentage * 1.5, 100)  # Scale up revenue impact
        
        # Statistical Reliability Score (0-100)
        # Penalize very small sample sizes
        if booking_count >= 10:
            reliability_score = 100
        elif booking_count >= 5:
            reliability_score = 80
        elif booking_count >= 3:
            reliability_score = 60
        elif booking_count >= 2:
            reliability_score = 40
        else:
            reliability_score = 20  # Single booking gets low reliability
        
        # Weighted average
        final_score = (
            conversion_score * 0.4 +
            volume_score * 0.3 +
            revenue_score * 0.2 +
            reliability_score * 0.1
        )
        
        return final_score
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    agent_filter = request.GET.get('agent', '')
    
    # Default to current month if no dates provided
    today = date.today()
    if not start_date_str:
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get reservations in date range
    reservations = Reservation.objects.filter(
        check_in__gte=start_date,
        check_in__lte=end_date
    )
    
    if agent_filter:
        reservations = reservations.filter(agent__id=agent_filter)
    
    total_reservations = reservations.count()
    
    # Calculate Potential Revenue (all bookings regardless of status)
    potential_revenue = sum(res.total_amount for res in reservations if res.total_amount)
    
    # Calculate Actual Revenue (only revenue-generating statuses, including no_show since they typically still pay)
    actual_revenue_statuses = ['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
    actual_revenue = sum(
        res.total_amount for res in reservations.filter(status__in=actual_revenue_statuses) 
        if res.total_amount
    )
    
    # Agent/Source Performance Analysis
    agent_performance = {}
    agents = Agent.objects.filter(is_active=True)
    
    for agent in agents:
        agent_reservations = reservations.filter(agent=agent)
        agent_count = agent_reservations.count()
        
        # Calculate both potential and actual revenue for this agent
        agent_potential_revenue = sum(res.total_amount for res in agent_reservations if res.total_amount)
        agent_actual_revenue = sum(
            res.total_amount for res in agent_reservations.filter(status__in=actual_revenue_statuses) 
            if res.total_amount
        )
        
        agent_nights = sum((res.check_out - res.check_in).days for res in agent_reservations)
        
        # Calculate conversion metrics (no_show now counts as confirmed since they generate revenue)
        confirmed_reservations = agent_reservations.filter(
            status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
        ).count()
        canceled_reservations = agent_reservations.filter(status='canceled').count()
        no_show_reservations = agent_reservations.filter(status='no_show').count()
        
        conversion_rate = (confirmed_reservations / agent_count * 100) if agent_count > 0 else 0
        cancellation_rate = (canceled_reservations / agent_count * 100) if agent_count > 0 else 0
        no_show_rate = (no_show_reservations / agent_count * 100) if agent_count > 0 else 0
        
        # Calculate average booking value and ADR based on actual revenue
        avg_booking_value = agent_actual_revenue / agent_count if agent_count > 0 else 0
        adr = agent_actual_revenue / agent_nights if agent_nights > 0 else 0
        
        if agent_count > 0:  # Only include agents with bookings
            # Calculate performance score based on multiple factors
            performance_score = calculate_performance_score(
                conversion_rate, agent_count, agent_actual_revenue, 
                total_reservations, actual_revenue
            )
            
            agent_performance[agent.name] = {
                'agent_id': agent.id,
                'reservations': agent_count,
                'potential_revenue': agent_potential_revenue,
                'actual_revenue': agent_actual_revenue,
                'revenue': agent_actual_revenue,  # Keep for backward compatibility
                'nights': agent_nights,
                'conversion_rate': conversion_rate,
                'cancellation_rate': cancellation_rate,
                'no_show_rate': no_show_rate,
                'avg_booking_value': avg_booking_value,
                'adr': adr,
                'market_share': (agent_count / total_reservations * 100) if total_reservations > 0 else 0,
                'revenue_share': (agent_actual_revenue / actual_revenue * 100) if actual_revenue > 0 else 0,
                'potential_revenue_share': (agent_potential_revenue / potential_revenue * 100) if potential_revenue > 0 else 0,
                'performance_score': performance_score
            }
    
    # Handle reservations without agent
    no_agent_reservations = reservations.filter(agent__isnull=True)
    no_agent_count = no_agent_reservations.count()
    if no_agent_count > 0:
        no_agent_potential_revenue = sum(res.total_amount for res in no_agent_reservations if res.total_amount)
        no_agent_actual_revenue = sum(
            res.total_amount for res in no_agent_reservations.filter(status__in=actual_revenue_statuses) 
            if res.total_amount
        )
        no_agent_nights = sum((res.check_out - res.check_in).days for res in no_agent_reservations)
        
        confirmed_no_agent = no_agent_reservations.filter(
            status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
        ).count()
        canceled_no_agent = no_agent_reservations.filter(status='canceled').count()
        no_show_no_agent = no_agent_reservations.filter(status='no_show').count()
        
        direct_conversion_rate = (confirmed_no_agent / no_agent_count * 100) if no_agent_count > 0 else 0
        
        # Calculate performance score for direct bookings
        direct_performance_score = calculate_performance_score(
            direct_conversion_rate, no_agent_count, no_agent_actual_revenue,
            total_reservations, actual_revenue
        )
        
        agent_performance['Direct/Unspecified'] = {
            'agent_id': None,
            'reservations': no_agent_count,
            'potential_revenue': no_agent_potential_revenue,
            'actual_revenue': no_agent_actual_revenue,
            'revenue': no_agent_actual_revenue,  # Keep for backward compatibility
            'nights': no_agent_nights,
            'conversion_rate': direct_conversion_rate,
            'cancellation_rate': (canceled_no_agent / no_agent_count * 100) if no_agent_count > 0 else 0,
            'no_show_rate': (no_show_no_agent / no_agent_count * 100) if no_agent_count > 0 else 0,
            'avg_booking_value': no_agent_actual_revenue / no_agent_count if no_agent_count > 0 else 0,
            'adr': no_agent_actual_revenue / no_agent_nights if no_agent_nights > 0 else 0,
            'market_share': (no_agent_count / total_reservations * 100) if total_reservations > 0 else 0,
            'revenue_share': (no_agent_actual_revenue / actual_revenue * 100) if actual_revenue > 0 else 0,
            'potential_revenue_share': (no_agent_potential_revenue / potential_revenue * 100) if potential_revenue > 0 else 0,
            'performance_score': direct_performance_score
        }
    
    # Sort by revenue (descending)
    sorted_agent_performance = sorted(agent_performance.items(), key=lambda x: x[1]['revenue'], reverse=True)
    
    # Monthly booking trends by source
    monthly_trends = {}
    for i in range(6):  # Last 6 months
        if today.month - i > 0:
            month_start = today.replace(day=1, month=today.month - i)
        else:
            year_offset = (i - today.month) // 12 + 1
            month_offset = (i - today.month) % 12
            new_month = 12 - month_offset if month_offset > 0 else 12
            month_start = today.replace(day=1, year=today.year - year_offset, month=new_month)
        
        last_day = monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)
        
        month_reservations = Reservation.objects.filter(
            check_in__gte=month_start,
            check_in__lte=month_end
        )
        
        month_label = month_start.strftime('%b %Y')
        monthly_trends[month_label] = {}
        
        for agent in agents:
            agent_month_count = month_reservations.filter(agent=agent).count()
            if agent_month_count > 0:
                monthly_trends[month_label][agent.name] = agent_month_count
        
        # Direct bookings
        direct_month_count = month_reservations.filter(agent__isnull=True).count()
        if direct_month_count > 0:
            monthly_trends[month_label]['Direct/Unspecified'] = direct_month_count
    
    # Reverse to show oldest to newest
    monthly_trends = dict(reversed(list(monthly_trends.items())))
    
    # Top performing sources summary
    top_by_revenue = sorted_agent_performance[:5] if len(sorted_agent_performance) >= 5 else sorted_agent_performance
    top_by_volume = sorted(agent_performance.items(), key=lambda x: x[1]['reservations'], reverse=True)[:5]
    
    # Calculate overall metrics
    overall_conversion_rate = 0
    overall_cancellation_rate = 0
    overall_no_show_rate = 0
    
    if total_reservations > 0:
        confirmed_total = reservations.filter(
            status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
        ).count()
        canceled_total = reservations.filter(status='canceled').count()
        no_show_total = reservations.filter(status='no_show').count()
        
        overall_conversion_rate = (confirmed_total / total_reservations * 100)
        overall_cancellation_rate = (canceled_total / total_reservations * 100)
        overall_no_show_rate = (no_show_total / total_reservations * 100)
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_reservations': total_reservations,
        'potential_revenue': potential_revenue,
        'actual_revenue': actual_revenue,
        'total_revenue': potential_revenue,  # Keep for backward compatibility
        'agent_performance': sorted_agent_performance,
        'monthly_trends': monthly_trends,
        'top_by_revenue': top_by_revenue,
        'top_by_volume': top_by_volume,
        'overall_conversion_rate': overall_conversion_rate,
        'overall_cancellation_rate': overall_cancellation_rate,
        'overall_no_show_rate': overall_no_show_rate,
        'agents': agents,
        'selected_agent': agent_filter
    }
    
    return render(request, 'pms/reports/booking_sources_report.html', context)


def guest_analytics(request):
    """View for generating detailed guest analytics reports"""
    from django.db.models import Count, Avg, Q, F
    from collections import defaultdict
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    # Default to current month if no dates provided
    today = date.today()
    if not start_date_str:
        # Default to first day of current month
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        # Default to last day of current month
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get reservations in the date range
    reservations = Reservation.objects.filter(
        check_in__gte=start_date,
        check_in__lte=end_date
    ).select_related('guest', 'room')
    
    # Basic guest statistics
    total_guests = reservations.count()
    unique_guests = reservations.values('guest').distinct().count()
    repeat_guests = total_guests - unique_guests
    repeat_guest_rate = (repeat_guests / total_guests * 100) if total_guests > 0 else 0
    
    # Calculate average length of stay
    avg_los = 0
    if reservations.exists():
        total_nights = sum([(res.check_out - res.check_in).days for res in reservations])
        avg_los = total_nights / total_guests if total_guests > 0 else 0
    
    # Guest demographics by nationality
    nationality_counts = defaultdict(int)
    for reservation in reservations:
        if reservation.guest.nationality:
            nationality_counts[reservation.guest.nationality] += 1
        else:
            nationality_counts['Not Specified'] += 1
    
    # Convert to sorted list for display
    nationality_data = sorted(nationality_counts.items(), key=lambda x: x[1], reverse=True)[:10]  # Top 10 nationalities
    
    # Booking patterns by day of week
    weekday_bookings = defaultdict(int)
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for reservation in reservations:
        weekday = reservation.check_in.weekday()
        weekday_bookings[weekday] += 1
    
    weekday_data = [{
        'name': weekday_names[i],
        'bookings': weekday_bookings[i]
    } for i in range(7)]
    
    # Length of stay distribution
    los_distribution_dict = defaultdict(int)
    for reservation in reservations:
        nights = (reservation.check_out - reservation.check_in).days
        if nights == 1:
            los_distribution_dict['1 night'] += 1
        elif nights == 2:
            los_distribution_dict['2 nights'] += 1
        elif nights <= 4:
            los_distribution_dict['3-4 nights'] += 1
        elif nights <= 7:
            los_distribution_dict['5-7 nights'] += 1
        else:
            los_distribution_dict['8+ nights'] += 1
    
    # Convert to regular dict for template
    los_distribution = dict(los_distribution_dict)
    
    # Room type preferences
    room_type_preferences = defaultdict(int)
    for reservation in reservations:
        room_type_preferences[reservation.room.get_room_type_display()] += 1
    
    room_type_data = sorted(room_type_preferences.items(), key=lambda x: x[1], reverse=True)
    
    # Payment method analysis
    payment_method_dict = defaultdict(int)
    for reservation in reservations:
        if reservation.payment_method:
            payment_method_dict[reservation.payment_method.name] += 1
        else:
            payment_method_dict['Not Specified'] += 1
    
    # Convert to sorted list for display but keep as dict for template iteration
    payment_method_data = sorted(payment_method_dict.items(), key=lambda x: x[1], reverse=True)
    
    # Agent/Source analysis
    agent_dict = defaultdict(int)
    for reservation in reservations:
        if reservation.agent:
            agent_dict[reservation.agent.name] += 1
        else:
            agent_dict['Not Specified'] += 1
    
    # Convert to sorted list for display
    agent_data = sorted(agent_dict.items(), key=lambda x: x[1], reverse=True)
    
    # Monthly booking trends (for the past 12 months)
    monthly_trends = []
    for i in range(12):
        # Calculate the month by going back i months from today
        if today.month - i > 0:
            month_start = today.replace(day=1, month=today.month - i)
        else:
            # Handle year rollover
            year_offset = (i - today.month) // 12 + 1
            month_offset = (i - today.month) % 12
            new_month = 12 - month_offset if month_offset > 0 else 12
            month_start = today.replace(day=1, year=today.year - year_offset, month=new_month)
        
        # Calculate month end using monthrange
        last_day = monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)
        
        month_bookings = Reservation.objects.filter(
            check_in__gte=month_start,
            check_in__lte=month_end
        ).count()
        
        monthly_trends.append({
            'month': month_start.strftime('%b %Y'),
            'bookings': month_bookings
        })
    
    monthly_trends.reverse()  # Show oldest to newest
    
    # Top guests by number of stays
    top_guests = (
        Guest.objects
        .annotate(stay_count=Count('reservation'))
        .filter(stay_count__gt=0)
        .order_by('-stay_count')[:10]
    )
    
    # Guest satisfaction metrics (based on status completion)
    completed_stays = reservations.filter(status='checked_out').count()
    canceled_stays = reservations.filter(status='canceled').count()
    no_shows = reservations.filter(status='no_show').count()
    
    completion_rate = (completed_stays / total_guests * 100) if total_guests > 0 else 0
    cancellation_rate = (canceled_stays / total_guests * 100) if total_guests > 0 else 0
    no_show_rate = (no_shows / total_guests * 100) if total_guests > 0 else 0
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_guests': total_guests,
        'unique_guests': unique_guests,
        'repeat_guests': repeat_guests,
        'repeat_guest_rate': repeat_guest_rate,
        'avg_los': avg_los,
        'nationality_data': nationality_data,
        'weekday_data': weekday_data,
        'los_distribution': los_distribution,
        'room_type_data': room_type_data,
        'payment_method_data': payment_method_data,
        'agent_data': agent_data,
        'monthly_trends': monthly_trends,
        'top_guests': top_guests,
        'completion_rate': completion_rate,
        'cancellation_rate': cancellation_rate,
        'no_show_rate': no_show_rate,
    }
    
    return render(request, 'pms/reports/guest_analytics.html', context)

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
    # Only include vacant_clean rooms as available for booking
    available_rooms = Room.objects.filter(
        status='vacant_clean'
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
    
    # Get available agents for the agent selection dropdown
    agents = Agent.objects.filter(is_active=True).order_by('display_order', 'name')
    
    context = {
        'reservation': reservation,
        'available_rooms': available_rooms,
        'agents': agents,
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
                    return JsonResponse({
                        'success': True, 
                        'guest_id': guest.id,
                        'guest': {
                            'id': guest.id,
                            'name': guest.name,
                            'email': guest.email or '',
                            'phone': guest.phone or ''
                        }
                    })
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
            
            # Get available rooms (exclude conflicting ones and rooms not available for booking)
            # Rooms must be vacant_clean and not in maintenance/out of order/out of service
            available_rooms = all_rooms.exclude(id__in=conflicting_room_ids).filter(
                status='vacant_clean'
            )
            
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


def occupancy_report(request):
    """View for generating detailed occupancy reports"""
    # Get date range parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    room_type = request.GET.get('room_type', '')
    
    # Default to current month if no dates provided
    today = date.today()
    if not start_date_str:
        # Default to first day of current month
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        # Default to last day of current month
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get all rooms, filtered by type if specified
    rooms = Room.objects.all()
    if room_type:
        rooms = rooms.filter(room_type=room_type)
    
    # Calculate date range
    date_range = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(date_range)]
    
    # Initialize data structures
    daily_occupancy = []
    room_occupancy = {}
    total_rooms = rooms.count()
    total_room_nights = total_rooms * date_range
    occupied_room_nights = 0
    
    # Calculate occupancy for each day
    for current_date in dates:
        occupied_rooms = 0
        for room in rooms:
            # Check if room is occupied on this date
            is_occupied = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,
                status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
            ).exists()
            
            if is_occupied:
                occupied_rooms += 1
                # Track occupancy by room
                if room.room_number not in room_occupancy:
                    room_occupancy[room.room_number] = 0
                room_occupancy[room.room_number] += 1
        
        # Calculate daily occupancy percentage
        daily_percentage = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
        occupied_room_nights += occupied_rooms
        
        # Add to daily occupancy list
        daily_occupancy.append({
            'date': current_date,
            'occupied': occupied_rooms,
            'total': total_rooms,
            'percentage': daily_percentage
        })
    
    # Calculate overall occupancy percentage
    overall_occupancy = (occupied_room_nights / total_room_nights * 100) if total_room_nights > 0 else 0
    
    # Calculate occupancy by room type
    room_type_occupancy = {}
    for room_type_choice, room_type_name in Room.ROOM_TYPES:
        type_rooms = rooms.filter(room_type=room_type_choice)
        type_room_count = type_rooms.count()
        if type_room_count > 0:
            type_occupied_nights = 0
            for current_date in dates:
                for room in type_rooms:
                    is_occupied = Reservation.objects.filter(
                        room=room,
                        check_in__lte=current_date,
                        check_out__gt=current_date,
                        status__in=['confirmed', 'in_house', 'expected_arrival', 'expected_departure', 'checked_out', 'no_show']
                    ).exists()
                    if is_occupied:
                        type_occupied_nights += 1
            
            type_total_nights = type_room_count * date_range
            type_percentage = (type_occupied_nights / type_total_nights * 100) if type_total_nights > 0 else 0
            room_type_occupancy[room_type_name] = {
                'occupied_nights': type_occupied_nights,
                'total_nights': type_total_nights,
                'percentage': type_percentage
            }
    
    # Calculate day of week occupancy
    weekday_occupancy = {i: {'occupied': 0, 'total': 0} for i in range(7)}
    for entry in daily_occupancy:
        weekday = entry['date'].weekday()
        weekday_occupancy[weekday]['occupied'] += entry['occupied']
        weekday_occupancy[weekday]['total'] += entry['total']
    
    # Calculate percentages for weekdays
    for weekday, data in weekday_occupancy.items():
        if data['total'] > 0:
            data['percentage'] = (data['occupied'] / data['total']) * 100
        else:
            data['percentage'] = 0
    
    # Format weekday data for template
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = [{
        'name': weekday_names[i],
        'percentage': weekday_occupancy[i]['percentage']
    } for i in range(7)]
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'daily_occupancy': daily_occupancy,
        'overall_occupancy': overall_occupancy,
        'room_occupancy': sorted([(room, (nights/date_range)*100) for room, nights in room_occupancy.items()], 
                                key=lambda x: x[1], reverse=True),
        'room_type_occupancy': room_type_occupancy,
        'weekday_data': weekday_data,
        'room_types': Room.ROOM_TYPES,
        'selected_room_type': room_type
    }
    
    return render(request, 'pms/reports/occupancy_report.html', context)