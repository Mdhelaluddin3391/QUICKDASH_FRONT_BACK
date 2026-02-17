# apps/customers/urls.py
from django.urls import path
from .views import (
    CustomerProfileAPIView,
    CustomerAddressListCreateView,      # Naya View (GET List aur POST Create ke liye)
    CustomerAddressDetailView,          # Naya View (PATCH Update ke liye)
    CustomerAddressSetDefaultAPIView,
    CustomerAddressDeleteAPIView,
    SupportTicketCreateAPIView,
    SupportTicketListAPIView,
    SupportTicketDetailAPIView
)

urlpatterns = [
    # Profile
    path("me/", CustomerProfileAPIView.as_view(), name="customer-profile"),
    
    # Address Management
    # 1. Naya address add karne aur sabhi address dekhne ke liye (GET, POST)
    path("addresses/", CustomerAddressListCreateView.as_view(), name="address-list-create"), 
    
    # 2. Existing address ko update karne ke liye (PATCH)
    # Note: DRF generic views default 'pk' (Primary Key) use karte hain, isliye <int:pk> lagaya hai
    path("addresses/<int:pk>/update/", CustomerAddressDetailView.as_view(), name="address-update"), 
    
    # 3. Address ko default set karne ke liye (POST)
    path("addresses/<int:address_id>/default/", CustomerAddressSetDefaultAPIView.as_view(), name="address-set-default"), 
    
    # 4. Address ko delete karne ke liye (DELETE)
    path("addresses/<int:address_id>/", CustomerAddressDeleteAPIView.as_view(), name="address-delete"), 
    
    # Support
    path("tickets/", SupportTicketCreateAPIView.as_view(), name="ticket-create"),
    path("tickets/history/", SupportTicketListAPIView.as_view(), name="ticket-history"),
    path("tickets/<int:id>/", SupportTicketDetailAPIView.as_view(), name="ticket-detail"),
]