from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin, PickingTask
from apps.warehouse.services import WarehouseOperationsService
from apps.inventory.models import InventoryItem
from apps.orders.models import Order
from apps.utils.exceptions import BusinessLogicException

User = get_user_model()

class WarehouseOperationsTestCase(TestCase):
    def setUp(self):
        # Setup Topology
        self.wh = Warehouse.objects.create(
            name="Dark Store 1", code="DS1", warehouse_type="dark_store",
            city="Mumbai", state="MH", location="POINT(72.8777 19.0760)"
        )
        self.user = User.objects.create_user(phone="+919999999999", password="pass")
        
        # Bin Setup
        zone = StorageZone.objects.create(warehouse=self.wh, name="Z1")
        aisle = Aisle.objects.create(zone=zone, number="A1")
        rack = Rack.objects.create(aisle=aisle, number="R1")
        self.bin = Bin.objects.create(rack=rack, bin_code="MUM-Z1-B1")

    def test_inward_stock_putaway(self):
        result = WarehouseOperationsService.inward_stock_putaway(
            warehouse_id=self.wh.id,
            barcode="SKU-ABC",
            quantity=50,
            bin_code="MUM-Z1-B1",
            user=self.user
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["new_total"], 50)
        
        item = InventoryItem.objects.get(sku="SKU-ABC", bin=self.bin)
        self.assertEqual(item.total_stock, 50)

    def test_picking_flow(self):
        # 1. Setup Data
        item = InventoryItem.objects.create(
            bin=self.bin, sku="ITEM-X", product_name="X", total_stock=10, price=100
        )
        order = Order.objects.create(
            user=self.user, warehouse=self.wh, status="confirmed", 
            delivery_type="express", total_amount=100
        )
        order.items.create(sku="ITEM-X", product_name="X", quantity=2, price=100)

        # 2. Generate Tasks
        WarehouseOperationsService.generate_picking_tasks(order)
        task = PickingTask.objects.get(order=order)
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.target_bin, item)

        # 3. Scan & Pick
        msg = WarehouseOperationsService.scan_pick(
            task_id=task.id,
            picker_user=self.user,
            scanned_bin_code="MUM-Z1-B1",
            scanned_barcode="ITEM-X"
        )
        
        self.assertEqual(msg, "Order Packed") # Last item picked -> Packed
        
        task.refresh_from_db()
        self.assertEqual(task.status, "picked")
        
        order.refresh_from_db()
        self.assertEqual(order.status, "packed")

    def test_scan_wrong_bin(self):
        # Setup task
        item = InventoryItem.objects.create(bin=self.bin, sku="Y", total_stock=5)
        order = Order.objects.create(user=self.user, warehouse=self.wh, status="confirmed", total_amount=10, delivery_type="express")
        order.items.create(sku="Y", quantity=1, price=10)
        task = PickingTask.objects.create(
            order=order, item_sku="Y", quantity_to_pick=1, target_bin=item
        )

        with self.assertRaises(BusinessLogicException):
            WarehouseOperationsService.scan_pick(task.id, self.user, "WRONG-BIN", "Y")