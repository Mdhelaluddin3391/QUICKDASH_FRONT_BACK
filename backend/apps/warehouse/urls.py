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
    path("", WarehouseListCreateAPIView.as_view()),
    path("find-serviceable/", ServiceableWarehouseAPIView.as_view()),
    path("dashboard/stats/", WarehouseManagerStatsAPIView.as_view()),

    path("tasks/picking/", PickerTaskListView.as_view()),
    path("pick/scan/", ScanPickAPIView.as_view()),
    path("pack/complete/", PackingCompleteAPIView.as_view()),
    path("dispatch/place/", OrderDispatchPlacementAPIView.as_view()),
    path("orders/active/", PickerActiveOrdersAPIView.as_view()),
    
    path("inward/stock/", InwardStockAPIView.as_view()),
    path("bins/", BinListCreateAPIView.as_view()), 
]