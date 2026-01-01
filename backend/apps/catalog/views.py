# apps/catalog/views.py
from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.db.models import Prefetch, OuterRef, Subquery, DecimalField, Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Case, When, F # Ensure these imports exist if needed, usually Q and OuterRef are enough based on your existing code.
from .models import Category, Product, Banner, Brand, FlashSale
from .serializers import (
    CategorySerializer, ProductSerializer, BannerSerializer, 
    BrandSerializer, FlashSaleSerializer, 
    SimpleCategorySerializer,
)
from .serializers import (
    NavigationCategorySerializer, HomeCategorySerializer,
    ProductSerializer, BannerSerializer, BrandSerializer, FlashSaleSerializer,
    CategorySerializer
)
from apps.warehouse.services import WarehouseService
from apps.inventory.models import InventoryItem

# ==============================================================================
# PUBLIC CATALOG APIS
# Note: authentication_classes = [] is added to prevent 401 errors
# if the frontend sends an invalid/expired token to these public pages.
# ==============================================================================
class NavbarCategoryAPIView(APIView):
    """
    Returns ONLY Parent Categories (Level 0) for the top Navbar.
    Logic: parent IS NULL.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        queryset = Category.objects.filter(is_active=True, parent__isnull=True).order_by('name')
        serializer = NavigationCategorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)



class HomeCategoryAPIView(APIView):
    """
    Returns ONLY Level 1 Categories (Direct Children) for 'Shop by Category'.
    Logic: parent IS NOT NULL AND parent's parent IS NULL.
    This prevents showing grandchildren (Level 2+) on the home page.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        queryset = Category.objects.filter(
            is_active=True, 
            parent__isnull=False,        # Must be a child
            parent__parent__isnull=True  # Must be a child of a Root
        ).select_related('parent').order_by('parent__name', 'name')

        serializer = HomeCategorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    


class SkuListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['category__slug', 'is_active'] 
    search_fields = ['name', 'sku', 'description', 'category__name']
    ordering_fields = ['effective_price', 'created_at']

    def get_queryset(self):
        # 1. Base Query - Lightweight
        qs = Product.objects.filter(is_active=True).select_related('category')
        
        # 2. Basic Filters (Category & Brand)
        # Filters pehle lagayein taaki database ko kam data scan karna pade
        category_slug = self.request.query_params.get('category__slug')
        if category_slug:
            qs = qs.filter(
                Q(category__slug=category_slug) | 
                Q(category__parent__slug=category_slug)
            )

        brands = self.request.query_params.get('brand')
        if brands:
            brand_ids = [b for b in brands.split(',') if b.strip().isdigit()]
            if brand_ids:
                qs = qs.filter(brand_id__in=brand_ids)

        # 3. PERFORMANCE OPTIMIZATION LOGIC
        # Hum heavy Price Calculation sirf tab karenge jab user PRICE se sort kar raha ho.
        ordering = self.request.query_params.get('ordering')
        warehouse_id = self.request.query_params.get('warehouse_id')

        if ordering in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            # Heavy Path: Sorting ke liye DB level par price calculate karna zaroori hai
            if warehouse_id:
                price_subquery = InventoryItem.objects.filter(
                    sku=OuterRef('sku'),
                    bin__rack__aisle__zone__warehouse_id=warehouse_id
                ).values('price')[:1]
            else:
                price_subquery = InventoryItem.objects.filter(
                    sku=OuterRef('sku')
                ).values('price')[:1]

            qs = qs.annotate(
                effective_price=Subquery(
                    price_subquery, 
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
            
            if ordering in ['price_asc', 'effective_price']:
                qs = qs.order_by('effective_price')
            else:
                qs = qs.order_by('-effective_price')
                
        elif ordering == 'newest':
            qs = qs.order_by('-created_at')
        else:
            # Default sorting (Fastest path)
            qs = qs.order_by('-created_at')
            
        return qs

    def list(self, request, *args, **kwargs):
        """
        Overridden List Method:
        Agar database level par price calculate nahi kiya gaya (kyunki fast path liya),
        toh hum pagination hone ke BAAD sirf visible 20 items ka price inject karenge.
        """
        response = super().list(request, *args, **kwargs)
        
        ordering = request.query_params.get('ordering')
        
        # Agar price sorting use nahi hui, toh manual injection karein
        if ordering not in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            self._inject_warehouse_prices(response.data, request)
            
        return response

    def _inject_warehouse_prices(self, data, request):
        """
        Helper function to fetch prices for just the paginated results efficiently.
        """
        warehouse_id = request.query_params.get('warehouse_id')
        
        # Pagination structure check (DRF usually returns dict with 'results')
        results = data.get('results') if isinstance(data, dict) else data
        
        if not results or not warehouse_id:
            return

        # 1. Get SKUs from the current page only (Max 20 SKUs)
        skus = [item.get('sku') for item in results]

        if not skus:
            return

        # 2. Fetch prices for these specific SKUs in one fast query
        inventory_prices = InventoryItem.objects.filter(
            sku__in=skus,
            bin__rack__aisle__zone__warehouse_id=warehouse_id
        ).values('sku', 'price')
        
        # Create a dictionary for O(1) lookup: {'SKU123': 100.00, ...}
        price_map = {item['sku']: item['price'] for item in inventory_prices}

        # 3. Update the response data directly
        for item in results:
            sku = item.get('sku')
            if sku in price_map:
                real_price = price_map[sku]
                item['effective_price'] = real_price
                # Agar frontend 'sale_price' use kar raha hai toh usse bhi update karein
                item['sale_price'] = real_price

class SkuDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

    def get_object(self):
        lookup_val = self.kwargs.get('id')
        queryset = self.get_queryset()
        
        # Support fetching by ID or SKU
        if lookup_val.isdigit():
            filter_kwargs = {'id': int(lookup_val)}
        else:
            filter_kwargs = {'sku': lookup_val}

        obj = generics.get_object_or_404(queryset, **filter_kwargs)
        return obj


class StorefrontCatalogAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <--- FIX

    @extend_schema(
        parameters=[
            OpenApiParameter("lat", OpenApiTypes.DOUBLE, required=True),
            OpenApiParameter("lon", OpenApiTypes.DOUBLE, required=True),
            OpenApiParameter("city", OpenApiTypes.STR, required=True),
        ],
    )
    def get(self, request):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        city = request.query_params.get("city")

        if not all([lat, lon, city]):
            return Response({"error": "Location details required"}, status=400)

        warehouse = WarehouseService.find_nearest_serviceable_warehouse(lat, lon, city)
        if not warehouse:
            return Response({"serviceable": False, "message": "No store nearby"}, status=200)

        inventory_qs = InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse=warehouse,
            total_stock__gt=0
        )

        categories = Category.objects.filter(is_active=True).prefetch_related("products")

        stock_map = {
            item.sku: {
                "price": item.price,
                "available_stock": item.available_stock,
                "id": item.id
            } 
            for item in inventory_qs
        }

        response_data = []
        for cat in categories:
            cat_data = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "icon": cat.icon.url if cat.icon else None, # Fixed icon mapping
                "products": []
            }
            has_products = False
            for prod in cat.products.all():
                if prod.sku in stock_map:
                    stock_info = stock_map[prod.sku]
                    cat_data["products"].append({
                        "id": prod.id,
                        "name": prod.name,
                        "image": prod.image.url if prod.image else None,
                        "sku": prod.sku,
                        "mrp": prod.mrp,
                        "selling_price": stock_info['price'],
                        "available_stock": stock_info['available_stock']
                    })
                    has_products = True
            
            if has_products:
                response_data.append(cat_data)

        return Response({
            "serviceable": True,
            "warehouse_id": warehouse.id,
            "categories": response_data
        })


class GlobalSearchAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    
    def get(self, request):
        query = request.query_params.get("q", "").strip() or request.query_params.get("search", "").strip()
        brand_id = request.query_params.get("brand") 
        
        if len(query) < 2 and not brand_id:
            return Response([])

        products = Product.objects.filter(is_active=True).select_related('category')

        if brand_id:
            products = products.filter(brand_id=brand_id)
        
        if query:
            products = products.filter(
                Q(name__icontains=query) | 
                Q(sku__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query)
            )

        products = products[:40]
        return Response(ProductSerializer(products, many=True, context={'request': request}).data)

class SearchSuggestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <--- FIX
    
    def get(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2: return Response([])
        
        product_results = Product.objects.filter(name__icontains=query, is_active=True)[:5]
        brand_results = Brand.objects.filter(name__icontains=query, is_active=True)[:3]
        
        data = []
        for p in product_results:
            data.append({"text": p.name, "type": "Product", "url": f"/product.html?code={p.sku}"}) # Changed to SKU
            
        for b in brand_results:
            data.append({"text": f"Brand: {b.name}", "type": "Brand", "url": f"/search_results.html?brand={b.id}"})
            
        return Response(data)


class HomeFeedAPIView(APIView):
    """
    Restored HomeFeed API but using correct Category models.
    Fetches some categories and displays their products.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        # Simply return some active categories with products
        # Using Navigation serializer for the section headers
        categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by('id')[:5]
        
        feed_data = []
        for cat in categories:
            # Get products for this category (or its children)
            products = Product.objects.filter(
                Q(category=cat) | Q(category__parent=cat),
                is_active=True
            ).select_related('category')[:10]
            
            if products:
                feed_data.append({
                    "category_name": cat.name,
                    "slug": cat.slug,
                    "products": ProductSerializer(products, many=True, context={'request': request}).data
                })

        return Response({
            "sections": feed_data,
            "has_next": False 
        })


class BannerListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = BannerSerializer
    queryset = Banner.objects.filter(is_active=True)

class BrandListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = BrandSerializer
    queryset = Brand.objects.filter(is_active=True)


class FlashSaleListAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        now = timezone.now()
        sales = FlashSale.objects.filter(is_active=True, end_time__gt=now).select_related('product')
        return Response(FlashSaleSerializer(sales, many=True, context={'request': request}).data)

class CategoryListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <--- FIX
    serializer_class = SimpleCategorySerializer 
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('name')