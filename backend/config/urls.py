"""
URL configuration for config project.

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
# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import health_check, AppConfigAPIView

urlpatterns = [
    # Monitoring
    path('', include('django_prometheus.urls')),
    path('health/', health_check),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Core Config
    path('api/config/', AppConfigAPIView.as_view()),

    # API V1 Routes
    path('api/v1/customers/', include('apps.customers.urls')),

    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/auth/customer/', include('apps.customers.urls')), # Customer Profile/Addresses
    
    
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/warehouse/', include('apps.warehouse.urls')),
    path('api/v1/locations/', include('apps.locations.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/delivery/', include('apps.delivery.urls')),
    path('api/v1/riders/', include('apps.riders.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/audit/', include('apps.audit.urls')),
    path('api/v1/assistant/', include('apps.assistant.urls')),


    

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)