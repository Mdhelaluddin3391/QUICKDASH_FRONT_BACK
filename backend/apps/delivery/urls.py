from django.urls import path
from .views import (
    AdminAssignDeliveryAPIView,
    MyDeliveriesAPIView,
    DeliveryCompleteAPIView,
    RiderLocationPingAPIView,
    GenerateUploadURLAPIView,
    RiderAcceptDeliveryAPIView,
    HandoverVerificationAPIView
)

urlpatterns = [
    path("admin/assign/", AdminAssignDeliveryAPIView.as_view()),

    path("me/", MyDeliveriesAPIView.as_view()),
    path("<int:delivery_id>/respond/", RiderAcceptDeliveryAPIView.as_view()), # Accept/Reject
    path("<int:delivery_id>/complete/", DeliveryCompleteAPIView.as_view()),
    
    path('verify-handover/', HandoverVerificationAPIView.as_view(), name='verify-handover'),
    path("handover/verify/", HandoverVerificationAPIView.as_view()),
    path("location/ping/<int:order_id>/", RiderLocationPingAPIView.as_view()),
    path("proof/generate-url/<int:order_id>/", GenerateUploadURLAPIView.as_view()),
]