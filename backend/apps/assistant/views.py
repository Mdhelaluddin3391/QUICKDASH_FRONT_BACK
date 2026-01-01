# apps/assistant/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from apps.catalog.models import Product
from apps.orders.models import Order # NEW: Order model import

class AIAssistantThrottle(UserRateThrottle):
    scope = 'ai_assistant' 

class AIShoppingAssistantView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIAssistantThrottle]

    def post(self, request):
        user_query = (request.data.get("message") or request.data.get("query") or "").lower()
        
        if not user_query:
            return Response({"error": "Query required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. ORDER TRACKING LOGIC (New Feature)
        # Check for keywords like "order", "track", "status", "kahan"
        if any(word in user_query for word in ['order', 'track', 'status', 'kahan', 'delivery']):
            latest_order = Order.objects.filter(
                user=request.user
            ).exclude(
                status__in=['delivered', 'cancelled', 'failed']
            ).order_by('-created_at').first()

            if latest_order:
                return Response({
                    "reply": f"Apka Order #{latest_order.id} abhi '{latest_order.get_status_display()}' hai. Total Amount: {latest_order.total_amount}.",
                    "action": "track_order",
                    "params": {"order_id": latest_order.id}
                })
            else:
                return Response({
                    "reply": "Apka koi active order nahi mila. Kya aap purane orders dekhna chahenge?",
                    "action": "view_orders",
                    "params": {}
                })

        # 2. PRODUCT SEARCH LOGIC (Existing)
        try:
            products = Product.objects.filter(
                Q(name__icontains=user_query) | 
                Q(category__name__icontains=user_query),
                is_active=True
            )[:3]

            if products.exists():
                product_names = ", ".join([p.name for p in products])
                reply = f"Mujhe ye products mile: {product_names}. Check them out!"
                return Response({
                    "reply": reply,
                    "action": "search_results",
                    "params": {"query": user_query}
                })
            
            return Response({
                "reply": f"Maaf kijiye, mujhe '{user_query}' ke liye kuch nahi mila. Try searching for 'Milk' or 'Bread'.",
                "action": None
            })
            
        except Exception as e:
            return Response(
                {"reply": "Technical issue. Please try browsing the catalog."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )