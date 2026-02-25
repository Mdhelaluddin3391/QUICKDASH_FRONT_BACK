import logging
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from apps.accounts.serializers import UserSerializer
from apps.warehouse.services import WarehouseService
from .models import SupportTicket, CustomerAddress, CustomerProfile
from .serializers import CustomerAddressSerializer, SupportTicketSerializer 
from .services import CustomerService

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomerAddressListCreateView(generics.ListCreateAPIView):
    """
    Addresses Fetch aur Create karne ka sabse badhiya aur chota tareeqa.
    """
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
      
        return CustomerAddress.objects.filter(
            customer__user=self.request.user, 
            is_deleted=False
        ).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        profile = CustomerService.get_or_create_profile(self.request.user)
        
        if serializer.validated_data.get('is_default', False):
            CustomerAddress.objects.filter(customer=profile).update(is_default=False)
            
        serializer.save(customer=profile)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data.get('latitude')
        lng = serializer.validated_data.get('longitude')
        
        wh = WarehouseService.get_nearest_warehouse(lat, lng)
        if not wh:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    "data": serializer.data, 
                    "warning": "Location currently unserviceable"
                }, 
                status=status.HTTP_201_CREATED, 
                headers=headers
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    

class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerAddress.objects.filter(customer__user=self.request.user, is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()


class CustomerProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        CustomerService.get_or_create_profile(request.user)
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        data = request.data

        if 'email' in data and data['email'] != user.email:
            if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response(
                    {"error": "Email already in use"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.email = data['email']

        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']

        user.save()
        return Response(UserSerializer(user).data)


class CustomerAddressSetDefaultAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, address_id):
        CustomerService.set_default_address(request.user, address_id)
        return Response({"status": "default address updated"})


class CustomerAddressDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, address_id):
        CustomerService.soft_delete_address(request.user, address_id)
        return Response({"status": "address deleted"}, status=status.HTTP_204_NO_CONTENT)


class SupportTicketCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            ticket = CustomerService.create_support_ticket(
                user=request.user,
                data=request.data
            )
            return Response({
                "status": "ticket_created",
                "ticket_id": ticket.id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SupportTicketListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
        return Response(SupportTicketSerializer(tickets, many=True).data)


class SupportTicketDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupportTicketSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user)