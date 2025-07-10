"""
URL configuration for hotel_pms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render  # Add this import
from pms.views import dashboard, create_reservation, calendar_data, edit_reservation, confirm_reservation

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('reservation/new/', create_reservation, name='create_reservation'),
    path('calendar/data/', calendar_data, name='calendar_data'),
    path('calendar/', lambda request: render(request, 'pms/calendar.html'), name='calendar'),
    path('reservation/edit/<int:reservation_id>/', edit_reservation, name='edit_reservation'),
    path('reservation/confirm/<int:reservation_id>/', confirm_reservation, name='confirm_reservation'),
]