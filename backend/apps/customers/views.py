from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework import generics
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .models import SupportTicket, CustomerAddress
from apps.accounts.serializers import UserSerializer
from .serializers import CustomerAddressSerializer, SupportTicketSerializer 
from .services import CustomerService

User = get_user_model()


class CustomerProfileAPIView(APIView):
    """
    Manages Customer Profile & Basic User Details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure profile exists before returning data
        CustomerService.get_or_create_profile(request.user)
        # Return User details (Name, Email, Phone) as the main profile payload
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        """
        Update basic details: First Name, Last Name, Email.
        """
        user = request.user
        data = request.data

        # 1. Email Uniqueness Check (if changing)
        if 'email' in data and data['email'] != user.email:
            if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response(
                    {"error": "Email already in use"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.email = data['email']

        # 2. Update Names
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']

        user.save()
        return Response(UserSerializer(user).data)


class CustomerAddressCreateAPIView(APIView):
    """
    Handles Listing and Creating Customer Addresses.
    Methods: GET (List all), POST (Add new)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all addresses for the logged-in user."""
        profile = CustomerService.get_or_create_profile(request.user)
        # Filter only active (non-deleted) addresses
        addresses = CustomerAddress.objects.filter(customer=profile, is_deleted=False)
        serializer = CustomerAddressSerializer(addresses, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new address."""
        profile = CustomerService.get_or_create_profile(request.user)
        # Log payload for debugging coordinates and ensure serializer receives lat/lng
        logger = logging.getLogger(__name__)
        logger.info(f"CustomerAddressCreateAPIView: incoming payload user={request.user.id} data_keys={list(request.data.keys())}")
        serializer = CustomerAddressSerializer(data=request.data)
        
        if serializer.is_valid():
            # Save address linked to the customer profile
            serializer.save(customer=profile)
            logger.info(f"CustomerAddressCreateAPIView: address created user={request.user.id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(f"CustomerAddressCreateAPIView: invalid payload user={request.user.id} errors={serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomerAddressUpdateAPIView(APIView):
    """
    Customer: Edit an existing address.
    Supports partial updates (PATCH).
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, address_id):
        profile = CustomerService.get_or_create_profile(request.user)
        address = get_object_or_404(
            CustomerAddress, 
            id=address_id, 
            customer=profile, 
            is_deleted=False
        )

        serializer = CustomerAddressSerializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class CustomerAddressSetDefaultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, address_id):
        CustomerService.set_default_address(request.user, address_id)
        return Response({"status": "default address updated"})


class CustomerAddressDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, address_id):
        CustomerService.soft_delete_address(request.user, address_id)
        return Response({"status": "address deleted"}, status=status.HTTP_204_NO_CONTENT)


class SupportTicketCreateAPIView(APIView):
    """
    Allows customers to raise a support ticket for their orders.
    """
    permission_classes = [IsAuthenticated]

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
    """
    Customer: View past support tickets.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
        return Response(SupportTicketSerializer(tickets, many=True).data)


class SupportTicketDetailAPIView(generics.RetrieveAPIView):
    """
    Customer: View details/replies of a specific ticket.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SupportTicketSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user)