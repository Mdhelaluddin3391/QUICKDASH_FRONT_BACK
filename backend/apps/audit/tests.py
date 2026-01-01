from django.test import TestCase
from apps.audit.models import AuditLog
from django.contrib.auth import get_user_model

User = get_user_model()

class AuditLogTestCase(TestCase):
    def test_immutability(self):
        user = User.objects.create_user(phone="+919999999999")
        log = AuditLog.objects.create(
            user=user, action="test_action", reference_id="REF123"
        )
        
        log.action = "tampered"
        with self.assertRaises(RuntimeError):
            log.save()