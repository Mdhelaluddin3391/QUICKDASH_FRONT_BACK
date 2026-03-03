from django.urls import path
from .views import StoreStatusAPIView, AdminWarehouseSelectView, SetAdminWarehouseView

urlpatterns = [
    path('store-status/', StoreStatusAPIView.as_view(), name='store-status'),
    
    # Core Admin Warehouse Flow
    path('admin-select-warehouse/', AdminWarehouseSelectView.as_view(), name='admin_select_warehouse'),
    path('admin-set-warehouse/<int:warehouse_id>/', SetAdminWarehouseView.as_view(), name='admin_set_warehouse'),
]