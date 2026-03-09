from django.urls import path
from .views import (
    CustomerProfileAPIView,
    CustomerAddressListCreateView,      
    CustomerAddressDetailView,          
    CustomerAddressSetDefaultAPIView,
    CustomerAddressDeleteAPIView,
    SupportTicketCreateAPIView,
    SupportTicketListAPIView,
    SupportTicketDetailAPIView
)

urlpatterns = [
    path("me/", CustomerProfileAPIView.as_view(), name="customer-profile"),
    
    path("addresses/", CustomerAddressListCreateView.as_view(), name="address-list-create"), 
    

    path("addresses/<int:pk>/update/", CustomerAddressDetailView.as_view(), name="address-update"), 
    
    path("addresses/<int:address_id>/default/", CustomerAddressSetDefaultAPIView.as_view(), name="address-set-default"), 
    
    path("addresses/<int:address_id>/", CustomerAddressDeleteAPIView.as_view(), name="address-delete"), 
    
    path("tickets/", SupportTicketCreateAPIView.as_view(), name="ticket-create"),
    path("tickets/history/", SupportTicketListAPIView.as_view(), name="ticket-history"),
    path("tickets/<int:id>/", SupportTicketDetailAPIView.as_view(), name="ticket-detail"),
]