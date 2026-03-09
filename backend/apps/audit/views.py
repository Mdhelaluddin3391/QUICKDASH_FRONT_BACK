from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.pagination import PageNumberPagination
from .models import AuditLog
from .serializers import AuditLogSerializer

class AuditPagination(PageNumberPagination):
    page_size = 50
    max_page_size = 100

class AuditLogListAPIView(APIView):
    """
    Admin View for System Audit Logs.
    """
    permission_classes = [IsAdminUser]
    pagination_class = AuditPagination

    def get(self, request):
        qs = AuditLog.objects.select_related('user').all().order_by("-created_at")

        ref_id = request.query_params.get('reference_id')
        if ref_id:
            qs = qs.filter(reference_id=ref_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        if page is not None:
            serializer = AuditLogSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = AuditLogSerializer(qs, many=True)
        return Response(serializer.data)