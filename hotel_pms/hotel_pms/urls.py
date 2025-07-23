from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from pms.views import calendar_data

urlpatterns = [
    path('admin/', admin.site.urls),
    path('calendar/', lambda request: render(request, 'pms/calendar.html'), name='calendar'),
    path('calendar/data/', calendar_data, name='calendar_data'),
    path('', include('pms.urls')),  # Include all PMS URLs
]