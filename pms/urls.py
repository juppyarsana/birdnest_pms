from django.urls import path
from django.shortcuts import render
from .views import (
    dashboard, create_reservation, calendar_data,
    checkin_reservation, confirm_reservation,
    checkout_reservation, cancel_reservation, edit_reservation,
    reservations_list, reservation_detail, rooms_list,
    guests, guest_detail, guest_list_json, check_reservation_conflict,
    check_available_rooms
)

def calendar_view(request):
    print("Debug: Accessing calendar view")
    response = render(request, 'pms/calendar.html')
    print("Debug: Calendar view response status:", response.status_code)
    return response

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('reservation/new/', create_reservation, name='create_reservation'),
    path('calendar/data/', calendar_data, name='calendar_data'),
    path('calendar/', calendar_view, name='calendar'),
    # Reservation management URLs
    path('reservations/', reservations_list, name='reservations_list'),
    path('reservations/<int:reservation_id>/', reservation_detail, name='reservation_detail'),
    path('reservations/<int:reservation_id>/confirm/', confirm_reservation, name='confirm_reservation'),
    path('reservations/<int:reservation_id>/checkin/', checkin_reservation, name='checkin_reservation'),
    path('reservations/<int:reservation_id>/checkout/', checkout_reservation, name='checkout_reservation'),
    path('reservations/<int:reservation_id>/cancel/', cancel_reservation, name='cancel_reservation'),
    path('reservations/<int:reservation_id>/edit/', edit_reservation, name='edit_reservation'),
    path('rooms/', rooms_list, name='rooms_list'),
    path('guests/', guests, name='guests'),
    path('guests/<int:guest_id>/', guest_detail, name='guest_detail'),
    path('guests/json/', guest_list_json, name='guest_list_json'),
    path('api/check-conflict/', check_reservation_conflict, name='check_reservation_conflict'),
    path('api/check-available-rooms/', check_available_rooms, name='check_available_rooms'),
]

print("Debug: URL patterns loaded:")
for pattern in urlpatterns:
    print(f"Debug: {pattern.name} -> {pattern.pattern}")