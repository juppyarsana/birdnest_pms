def calculate_occupancy_for_period(start_date, end_date, rooms=None):
    """Calculate occupancy percentage for a given period using standardized logic"""
    if rooms is None:
        rooms = Room.objects.all()
    
    total_rooms = rooms.count()
    if total_rooms == 0:
        return 0
    
    date_range = (end_date - start_date).days + 1
    total_room_nights = total_rooms * date_range
    occupied_room_nights = 0
    
    for current_date in [start_date + timedelta(days=i) for i in range(date_range)]:
        for room in rooms:
            is_occupied = Reservation.objects.filter(
                room=room,
                check_in__lte=current_date,
                check_out__gt=current_date,
                status__in=['confirmed', 'expected_arrival', 'expected_departure', 'in_house', 'checked_out', 'no_show']
            ).exists()
            if is_occupied:
                occupied_room_nights += 1
    
    return (occupied_room_nights / total_room_nights) * 100