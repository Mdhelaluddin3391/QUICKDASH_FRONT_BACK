from django.urls import path
from .views import (
    InventoryItemListCreateAPIView,
    AddStockAPIView,
    CycleCountAPIView,
    InventoryHistoryAPIView
)

urlpatterns = [
    path("", InventoryItemListCreateAPIView.as_view()),
    path("<int:item_id>/add-stock/", AddStockAPIView.as_view()),
    path("<int:item_id>/cycle-count/", CycleCountAPIView.as_view()),
    path("history/<int:item_id>/", InventoryHistoryAPIView.as_view()),
]