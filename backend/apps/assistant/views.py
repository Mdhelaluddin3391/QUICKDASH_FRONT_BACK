from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from apps.catalog.models import Product
from apps.orders.models import Order
import urllib.parse

class AIAssistantThrottle(UserRateThrottle):
    scope = 'ai_assistant' 

class AIShoppingAssistantView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIAssistantThrottle]

    def post(self, request):
        user_query = (request.data.get("message") or request.data.get("query") or "").lower().strip()
        
        if not user_query:
            return Response({"error": "Query required"}, status=status.HTTP_400_BAD_REQUEST)

        greetings = ['hi', 'hello', 'hey', 'help', 'namaste']
        if user_query in greetings:
            return Response({
                "reply": "Namaste! Main QuickDash ka AI Assistant hoon. Kya main aapko order track karne ya koi product dhoondhne mein madad karoon?",
                "action": None
            })

        if any(word in user_query for word in ['order', 'track', 'status', 'kahan', 'delivery']):
            latest_order = Order.objects.filter(
                user=request.user
            ).exclude(
                status__in=['delivered', 'cancelled', 'failed']
            ).order_by('-created_at').first()

            if latest_order:
                return Response({
                    "reply": f"Apka Order #{latest_order.id} abhi '{latest_order.get_status_display()}' status mein hai. Total Amount: ₹{latest_order.total_amount}.",
                    "action": "track_order",
                    "params": {"order_id": latest_order.id}
                })
            else:
                return Response({
                    "reply": "Apka koi current active order nahi mila. Kya aap apne purane orders dekhna chahte hain?",
                    "action": "view_orders",
                    "params": {}
                })

        try:
            products = Product.objects.filter(
                Q(name__icontains=user_query) | 
                Q(category__name__icontains=user_query),
                is_active=True
            )[:3]

            if products.exists():
                product_names = ", ".join([p.name for p in products])
                reply = f"Mujhe ye products mile hain: {product_names}. Aap inhe search bar mein likh kar khareed sakte hain!"
                return Response({
                    "reply": reply,
                    "action": "search_results",
                    "params": {"query": user_query}
                })
            
          
            whatsapp_number = "916009282670"
            encoded_query = urllib.parse.quote(f"Hi QuickDash Support, mujhe is baare mein madad chahiye: {user_query}")
            wa_link = f"https://wa.me/{whatsapp_number}?text={encoded_query}"
            
            fallback_reply = "Maaf kijiye, mujhe is sawal ka jawab nahi pata. Lekin chinta mat kijiye, humari Support Team aapki madad karegi. Kripya niche diye gaye button par click karke hume WhatsApp par message karein."
            
            return Response({
                "reply": fallback_reply,
                "action": "whatsapp_support",
                "params": {"url": wa_link}
            })
            
        except Exception as e:
            return Response(
                {"reply": "Technical issue aa rahi hai. Kripya thodi der baad try karein."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )