from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from pms.views import calendar_data

urlpatterns = [
    path('admin/', admin.site.urls),
    path('calendar/', lambda request: render(request, 'pms/calendar.html'), name='calendar'),
    path('calendar/data/', calendar_data, name='calendar_data'),
    path('', include('pms.urls')),
    path('iot/', include('iot.urls')),
]

print("Debug: Root URL patterns loaded")
for pattern in urlpatterns:
    print(f"Debug: Pattern: {pattern}")
    if hasattr(pattern, 'url_patterns'):
        print("Debug: Included URL patterns:")
        for url in pattern.url_patterns:
            print(f"Debug: -> Pattern: {url.pattern}")