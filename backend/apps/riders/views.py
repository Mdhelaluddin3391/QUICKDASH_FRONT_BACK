from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import RiderDocument
from .serializers import RiderDocumentSerializer
from apps.delivery.services import StorageService 
from .models import RiderProfile
from .serializers import (
    RiderProfileSerializer, 
    RiderBootstrapSerializer, 
    RiderEarningSerializer,
    RiderAvailabilitySerializer
)
from .services import RiderService
from apps.warehouse.models import Warehouse
from .models import RiderPayout
from rest_framework import status, serializers


class MyRiderProfileAPIView(APIView):
    """
    Rider App Home: Returns full profile, warehouse context, and status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'rider_profile'):
            return Response({"error": "User is not a registered rider"}, status=status.HTTP_403_FORBIDDEN)

        profile = request.user.rider_profile
        return Response(RiderBootstrapSerializer(profile).data)


class RiderAvailabilityAPIView(APIView):
    """
    Toggle Online/Offline status.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RiderAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)

        available = serializer.validated_data["is_available"]
        profile = request.user.rider_profile
        
        RiderService.set_availability(profile, available)
        
        return Response({
            "status": "availability updated", 
            "is_available": available
        })


class RiderEarningsAPIView(APIView):
    """
    Ledger history for the rider.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)

        profile = request.user.rider_profile
        qs = profile.earnings.all().order_by("-created_at")
        return Response(RiderEarningSerializer(qs, many=True).data)


class AdminCreateRiderProfileAPIView(APIView):
    """
    Admin: Promote a user to Rider.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get("user_id")
        user_model = RiderProfile._meta.get_field("user").remote_field.model
        user = get_object_or_404(user_model, id=user_id)

        profile = RiderService.create_rider_profile(user)
        return Response(RiderProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class AdminAssignWarehouseAPIView(APIView):
    """
    Admin: Link Rider to a Warehouse.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, rider_id):
        warehouse_id = request.data.get("warehouse_id")
        
        rider = get_object_or_404(RiderProfile, id=rider_id)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)

        RiderService.assign_warehouse(rider, warehouse)
        return Response({"status": "warehouse assigned"})



class RiderDocumentUploadAPIView(APIView):
    """
    Rider: Submit KYC Document Info (after S3 upload).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "Not a rider"}, status=403)
        
        docs = RiderDocument.objects.filter(rider=request.user.rider_profile)
        return Response(RiderDocumentSerializer(docs, many=True).data)

    def post(self, request):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "Not a rider"}, status=403)

        doc_type = request.data.get("doc_type")
        file_key = request.data.get("file_key") 

        if not doc_type or not file_key:
            return Response({"error": "Missing fields"}, status=400)

       

        doc, created = RiderDocument.objects.update_or_create(
            rider=request.user.rider_profile,
            doc_type=doc_type,
            defaults={
                "file_key": file_key,
                "status": "pending"
            }
        )
        
        return Response(RiderDocumentSerializer(doc).data)


class RiderPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderPayout
        fields = '__all__'

class RiderPayoutListAPIView(APIView):
    """
    Rider: View settlement/payout history.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=403)
        
        payouts = RiderPayout.objects.filter(rider=request.user.rider_profile).order_by("-created_at")
        return Response(RiderPayoutSerializer(payouts, many=True).data)
    




class RiderLocationUpdateAPIView(APIView):
    """
    Rider App: Updates the rider's current GPS location.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not hasattr(request.user, 'rider_profile'):
            return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)

        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if lat is not None and lng is not None:
            profile = request.user.rider_profile
           
            profile.current_lat = lat  
            profile.current_lng = lng
            profile.save()
            
            return Response({"status": "Location updated successfully"})
            
        return Response({"error": "Missing coordinates"}, status=status.HTTP_400_BAD_REQUEST)