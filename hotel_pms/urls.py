from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from pms.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pms.urls', namespace=None)),  # Include PMS app URLs at root
]

print("Debug: Root URL patterns loaded")
for pattern in urlpatterns:
    print(f"Debug: Pattern: {pattern}")
    if hasattr(pattern, 'url_patterns'):
        print("Debug: Included URL patterns:")
        for url in pattern.url_patterns:
            print(f"Debug: -> Pattern: {url.pattern}")