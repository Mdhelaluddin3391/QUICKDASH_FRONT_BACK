from django.test import TestCase
from unittest.mock import patch, MagicMock
from decimal import Decimal
from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.payments.services import PaymentService
from apps.payments.refund_services import RefundService
from django.contrib.auth import get_user_model
from apps.warehouse.models import Warehouse

User = get_user_model()

class PaymentServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999999", password="pass")
        self.wh = Warehouse.objects.create(name="W", code="W", location="POINT(0 0)")
        self.order = Order.objects.create(
            user=self.user, warehouse=self.wh, total_amount=Decimal("500.00"),
            status="created", delivery_type="express"
        )

    @patch("apps.payments.services.client.order.create")
    def test_create_payment_success(self, mock_razorpay):
        mock_razorpay.return_value = {"id": "order_rp_123"}
        
        payment = PaymentService.create_payment(self.order)
        
        self.assertEqual(payment.provider_order_id, "order_rp_123")
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(payment.status, "created")

    def test_mark_paid_success(self):
        payment = Payment.objects.create(
            order=self.order, amount=500, provider_order_id="order_rp_123", status="created"
        )
        
        # Verify trigger_delivery is called using captureOnCommitCallbacks
        with patch("apps.payments.services.PaymentService._trigger_delivery") as mock_trigger:
            with self.captureOnCommitCallbacks(execute=True): # <--- FIXED
                PaymentService.mark_paid(payment.id, "pay_123", "order_rp_123")
            
            mock_trigger.assert_called_once()
            
        payment.refresh_from_db()
        self.assertEqual(payment.status, "paid")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "confirmed")

class RefundServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999999")
        self.wh = Warehouse.objects.create(name="W", code="W", location="POINT(0 0)")
        self.order = Order.objects.create(user=self.user, warehouse=self.wh, total_amount=100, status="cancelled", delivery_type="express")
        self.payment = Payment.objects.create(
            order=self.order, amount=100, status="paid", provider_payment_id="pay_123"
        )

    @patch("apps.payments.refund_services.razorpay.Client")
    def test_initiate_refund(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.payment.refund.return_value = {"id": "rfnd_123"}
        mock_client_cls.return_value = mock_client
        
        refund = RefundService.initiate_refund(self.payment)
        
        self.assertEqual(refund.status, "initiated")
        self.assertEqual(refund.provider_refund_id, "rfnd_123")