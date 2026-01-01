# apps/warehouse/urls.py
from django.urls import path
from .views import (
    WarehouseListCreateAPIView,
    ServiceableWarehouseAPIView,
    WarehouseManagerStatsAPIView,
    PickerTaskListView,
    ScanPickAPIView,
    PackingCompleteAPIView,
    InwardStockAPIView,
    OrderDispatchPlacementAPIView,
    PickerActiveOrdersAPIView,
    BinListCreateAPIView
)

urlpatterns = [
    # Admin / Public
    path("", WarehouseListCreateAPIView.as_view()),
    path("find-serviceable/", ServiceableWarehouseAPIView.as_view()),
    path("dashboard/stats/", WarehouseManagerStatsAPIView.as_view()),

    # Picker/Packer Workflows
    path("tasks/picking/", PickerTaskListView.as_view()),
    path("pick/scan/", ScanPickAPIView.as_view()),
    path("pack/complete/", PackingCompleteAPIView.as_view()),
    path("dispatch/place/", OrderDispatchPlacementAPIView.as_view()),
    path("orders/active/", PickerActiveOrdersAPIView.as_view()),
    
    # Manager
    path("inward/stock/", InwardStockAPIView.as_view()),
    path("bins/", BinListCreateAPIView.as_view()), # Add this line
]