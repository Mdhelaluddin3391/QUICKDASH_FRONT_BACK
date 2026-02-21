# apps/riders/urls.py
from django.urls import path
from .views import (
    MyRiderProfileAPIView,
    RiderAvailabilityAPIView,
    RiderEarningsAPIView,
    AdminCreateRiderProfileAPIView,
    AdminAssignWarehouseAPIView,
    RiderDocumentUploadAPIView,
    RiderPayoutListAPIView,
    RiderLocationUpdateAPIView
)

urlpatterns = [
    # Rider App
    path("me/", MyRiderProfileAPIView.as_view()),
    path("availability/", RiderAvailabilityAPIView.as_view()),
    path("earnings/", RiderEarningsAPIView.as_view()),
    
    # Admin

    path("admin/create/", AdminCreateRiderProfileAPIView.as_view()),
    path("admin/<int:rider_id>/assign-warehouse/", AdminAssignWarehouseAPIView.as_view()),
    path("documents/", RiderDocumentUploadAPIView.as_view()),
    path("payouts/", RiderPayoutListAPIView.as_view()), # Add this line
    path("location/", RiderLocationUpdateAPIView.as_view()),
]