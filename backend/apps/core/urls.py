from django.urls import path
from .views import StoreStatusAPIView

urlpatterns = [
    path('store-status/', StoreStatusAPIView.as_view(), name='store-status'),
]