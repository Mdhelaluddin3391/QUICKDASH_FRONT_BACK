# apps/customers/urls.py
from django.urls import path
from django.urls import path
from .views import (
    CustomerProfileAPIView,
    CustomerAddressCreateAPIView,
    CustomerAddressUpdateAPIView, # New
    CustomerAddressSetDefaultAPIView,
    CustomerAddressDeleteAPIView,
    SupportTicketCreateAPIView,
    SupportTicketListAPIView,
    SupportTicketDetailAPIView # New
)

urlpatterns = [
    # Profile
    path("me/", CustomerProfileAPIView.as_view()),
    
    # Address Management
    path("addresses/", CustomerAddressCreateAPIView.as_view()), # GET (List), POST (Create)
    path("addresses/<int:address_id>/update/", CustomerAddressUpdateAPIView.as_view()), # PATCH (Update) - NEW
    path("addresses/<int:address_id>/default/", CustomerAddressSetDefaultAPIView.as_view()), # POST (Set Default)
    path("addresses/<int:address_id>/", CustomerAddressDeleteAPIView.as_view()), # DELETE
    
    # Support
    path("tickets/", SupportTicketCreateAPIView.as_view()), # POST (Create)
    path("tickets/history/", SupportTicketListAPIView.as_view()), # GET (List)
    path("tickets/<int:id>/", SupportTicketDetailAPIView.as_view()), # GET (Detail) - NEW
]