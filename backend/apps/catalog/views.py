from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Prefetch, OuterRef, Subquery, DecimalField, Q, Sum, F  
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import Category, Product, Banner, Brand, FlashSale
from .serializers import (
    CategorySerializer, ProductSerializer, BannerSerializer, 
    BrandSerializer, FlashSaleSerializer, 
    SimpleCategorySerializer, NavigationCategorySerializer, HomeCategorySerializer
)
from rest_framework.exceptions import NotFound
from django.db.models import Q
from apps.warehouse.services import WarehouseService
from apps.inventory.models import InventoryItem

# ==============================================================================
# PUBLIC CATALOG APIS
# Authentication classes empty to allow Guest Browsing
# ==============================================================================

class NavbarCategoryAPIView(APIView):
    """
    Returns ONLY Parent Categories (Level 0) for the top Navbar.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        queryset = Category.objects.filter(is_active=True, parent__isnull=True).order_by('name')
        serializer = NavigationCategorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class HomeCategoryAPIView(APIView):
    """
    Returns Level 1 Categories for 'Shop by Category'.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        queryset = Category.objects.filter(
            is_active=True, 
            parent__isnull=False,        
            parent__parent__isnull=True  
        ).select_related('parent').order_by('parent__name', 'name')

        serializer = HomeCategorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class SkuListAPIView(generics.ListAPIView):
    """
    Listing Page (Search/Category).
    Supports sorting by Price which requires Warehouse Context.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['category__slug', 'is_active'] 
    search_fields = ['name', 'sku', 'description', 'category__name']
    ordering_fields = ['effective_price', 'created_at']

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category')
        
        # Filters
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

        # Sorting Logic
        ordering = self.request.query_params.get('ordering')
        warehouse = getattr(self.request, 'warehouse', None) # From Middleware

        if ordering in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            # Subquery to get price from Inventory based on Warehouse
            if warehouse:
                price_subquery = InventoryItem.objects.filter(
                    sku=OuterRef('sku'),
                    bin__rack__aisle__zone__warehouse=warehouse
                ).values('price')[:1]
            else:
                # Fallback: Just take any price (or 0)
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
        else:
            qs = qs.order_by('-created_at')
            
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Inject prices if not sorted by price (manual injection is faster for pagination)
        ordering = request.query_params.get('ordering')
        if ordering not in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            self._inject_warehouse_prices(response.data, request)
        return response

    def _inject_warehouse_prices(self, data, request):
        warehouse = getattr(request, 'warehouse', None)
        if not warehouse: return

        results = data.get('results') if isinstance(data, dict) else data
        if not results: return

        skus = [item.get('sku') for item in results]
        if not skus: return

        # Batch fetch prices
        inventory_prices = InventoryItem.objects.filter(
            sku__in=skus,
            bin__rack__aisle__zone__warehouse=warehouse
        ).values('sku', 'price')
        
        price_map = {item['sku']: item['price'] for item in inventory_prices}

        for item in results:
            sku = item.get('sku')
            if sku in price_map:
                item['sale_price'] = price_map[sku] # Frontend expects 'sale_price'

class SkuDetailAPIView(generics.RetrieveAPIView):
    """
    Product Detail Page.
    Injects Available Stock for the detected Warehouse.
    Fixed: Supports numeric SKUs correctly.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

    def get_object(self):
        # Support lookup by ID or SKU
        lookup_val = self.kwargs.get('id')
        queryset = self.get_queryset()
        
        # FIX: Check for numeric SKU vs ID ambiguity
        # Pehle SKU match karein, phir ID match karein
        
        obj = None
        
        # 1. Try finding by SKU (Priority for Barcodes)
        obj = queryset.filter(sku=lookup_val).first()
        
        # 2. If not found and value is numeric, try finding by Database ID
        if not obj and lookup_val.isdigit():
            # Use Q object to be safe or explicit ID check
            obj = queryset.filter(id=int(lookup_val)).first()

        if not obj:
            raise NotFound(f"No Product matches the identifier: {lookup_val}")
            
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        warehouse = getattr(request, 'warehouse', None)
        
        available_stock = 0
        # FIX: Product model has 'mrp', not 'price'. 
        # Using getattr to be safe, defaulting to mrp.
        sale_price = getattr(instance, 'mrp', 0) 

        if warehouse:
            # 1. Get Stock
            stock_data = InventoryItem.objects.filter(
                sku=instance.sku, 
                bin__rack__aisle__zone__warehouse=warehouse
            ).aggregate(total_stock=Sum('total_stock'), reserved=Sum('reserved_stock'))
            
            t_stock = stock_data.get('total_stock') or 0
            r_stock = stock_data.get('reserved') or 0 # Fix: aggregate key might be 'reserved' or 'reserved_stock' based on your query
            
            # Agar upar Sum('reserved_stock') use kiya hai bina keyword ke to key 'reserved_stock__sum' hogi
            # Safety ke liye hum direct keys use kar rahe hain jo aggregate mein define ki hain
            available_stock = t_stock - (stock_data.get('reserved') or 0)

            # 2. Get Price from Inventory (Store specific price)
            inv_item = InventoryItem.objects.filter(
                sku=instance.sku,
                bin__rack__aisle__zone__warehouse=warehouse
            ).first()
            if inv_item:
                sale_price = inv_item.price

        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Inject dynamic fields
        data['available_stock'] = available_stock
        data['sale_price'] = sale_price
        
        # Ensure effective_price is set for frontend consistency
        if data.get('effective_price') is None:
            data['effective_price'] = sale_price

        return Response(data)

class StorefrontCatalogAPIView(APIView):
    """
    Home Page Feed.
    Returns products available in the detected Warehouse.
    Prioritizes Middleware resolved warehouse (via Headers) over Query Params.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    @extend_schema(
        parameters=[
            OpenApiParameter("X-Location-Lat", OpenApiTypes.DOUBLE, location=OpenApiParameter.HEADER, description="User Latitude"),
            OpenApiParameter("X-Location-Lng", OpenApiTypes.DOUBLE, location=OpenApiParameter.HEADER, description="User Longitude"),
            OpenApiParameter("lat", OpenApiTypes.DOUBLE, required=False, description="Fallback Latitude"),
            OpenApiParameter("lon", OpenApiTypes.DOUBLE, required=False, description="Fallback Longitude"),
            OpenApiParameter("city", OpenApiTypes.STR, required=False),
        ],
    )
    def get(self, request):
        # 1. Resolve Warehouse (Middleware Priority)
        warehouse = getattr(request, 'warehouse', None)
        
        # Fallback if Middleware didn't find it
        if not warehouse:
            lat = request.query_params.get("lat")
            lon = request.query_params.get("lon")
            if lat and lon:
                warehouse = WarehouseService.get_nearest_warehouse(lat, lon)

        if not warehouse:
            return Response({"serviceable": False, "message": "Location not serviceable"}, status=200)

        # 2. Get Products (SKUs) In Stock
        skus_in_stock = InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse=warehouse,
            total_stock__gt=F('reserved_stock')
        ).values_list('sku', flat=True).distinct()

        # 3. Build Categories Feed
        categories = Category.objects.filter(is_active=True, parent__isnull=True)[:6]
        
        feed = []
        for cat in categories:
            # --- Price Subquery Setup ---
            price_subquery = InventoryItem.objects.filter(
                sku=OuterRef('sku'),
                bin__rack__aisle__zone__warehouse=warehouse
            ).values('price')[:1]

            # Fetch products
            products = Product.objects.filter(
                Q(category=cat) | Q(category__parent=cat),
                sku__in=skus_in_stock,
                is_active=True
            ).annotate(
                effective_price=Subquery(
                    price_subquery, 
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )[:6]

            if products.exists():
                p_data = ProductSerializer(products, many=True, context={'request': request}).data
                
                # Consistency Injection
                for p in p_data: 
                    p['available_stock'] = 10 # Just a flag for Frontend
                    if p.get('effective_price') is None:
                        p['effective_price'] = p.get('mrp')
                        p['sale_price'] = p.get('mrp')

                # ✅ FIXED ICON URL LOGIC
                icon_url = None
                if cat.icon:
                    if cat.icon.startswith('http'):
                        icon_url = cat.icon
                    else:
                        icon_url = request.build_absolute_uri(cat.icon)

                feed.append({
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "icon": icon_url, # Ab ye safe hai
                    "products": p_data
                })

        return Response({
            "serviceable": True,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "categories": feed
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
        # Warehouse Price Injection logic can be added here similar to SkuListAPIView
        return Response(ProductSerializer(products, many=True, context={'request': request}).data)

class SearchSuggestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    
    def get(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2: return Response([])
        
        product_results = Product.objects.filter(name__icontains=query, is_active=True)[:5]
        brand_results = Brand.objects.filter(name__icontains=query, is_active=True)[:3]
        
        data = []
        for p in product_results:
            data.append({"text": p.name, "type": "Product", "url": f"/product.html?code={p.sku}"})
            
        for b in brand_results:
            data.append({"text": f"Brand: {b.name}", "type": "Brand", "url": f"/search_results.html?brand={b.id}"})
            
        return Response(data)


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
    authentication_classes = [] 
    serializer_class = SimpleCategorySerializer 
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('name')