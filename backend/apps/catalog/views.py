from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Prefetch, OuterRef, Subquery, DecimalField, Q, Sum, F  
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.core.paginator import Paginator
import re
from django.db.models import Case, When, Value, IntegerField
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
from rest_framework.pagination import PageNumberPagination
from django.contrib.gis.geos import Point
from apps.warehouse.models import Warehouse




class SkuPagination(PageNumberPagination):
    page_size = 12




class NavbarCategoryAPIView(APIView):
    """
    Returns ONLY Parent Categories (Level 0) for the top Navbar.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def get(self, request):
        queryset = Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order', 'name')
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
    pagination_class = SkuPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['is_active'] 
    
    search_fields = ['name', 'sku', 'description', 'category__name', 'category__parent__name']
    ordering_fields = ['effective_price', 'created_at']

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category')
        
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

        ordering = self.request.query_params.get('ordering')
        
        lat = self.request.headers.get('X-Location-Lat') or self.request.query_params.get('lat')
        lng = self.request.headers.get('X-Location-Lng') or self.request.query_params.get('lon')
        
        serviceable_warehouses = None
        if lat and lng:
            user_location = Point(float(lng), float(lat), srid=4326)
            serviceable_warehouses = Warehouse.objects.filter(is_active=True, delivery_zone__contains=user_location)

        if ordering in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            if serviceable_warehouses and serviceable_warehouses.exists():
                price_subquery = InventoryItem.objects.filter(
                    sku=OuterRef('sku'),
                    bin__rack__aisle__zone__warehouse__in=serviceable_warehouses
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
        else:
            qs = qs.order_by('-created_at')
            
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        ordering = request.query_params.get('ordering')
        if ordering not in ['price_asc', 'price_desc', 'effective_price', '-effective_price']:
            self._inject_warehouse_prices(response.data, request)
        return response

    def _inject_warehouse_prices(self, data, request):
        results = data.get('results') if isinstance(data, dict) else data
        if not results: return

        skus = [item.get('sku') for item in results]
        if not skus: return

        lat = request.headers.get('X-Location-Lat') or request.query_params.get('lat')
        lng = request.headers.get('X-Location-Lng') or request.query_params.get('lon')

        if lat and lng:
            user_location = Point(float(lng), float(lat), srid=4326)
            serviceable_warehouses = Warehouse.objects.filter(is_active=True, delivery_zone__contains=user_location)
        else:
            warehouse = getattr(request, 'warehouse', None)
            serviceable_warehouses = Warehouse.objects.filter(id=warehouse.id) if warehouse else Warehouse.objects.none()

        if not serviceable_warehouses.exists():
            for item in results:
                item['available_stock'] = 0
                item['delivery_eta'] = 'Unavailable'
                item['has_more_in_mega'] = False
            return

        inventory_items = InventoryItem.objects.filter(
            sku__in=skus,
            bin__rack__aisle__zone__warehouse__in=serviceable_warehouses
        ).select_related('bin__rack__aisle__zone__warehouse')
        
        # SMART STOCK CALCULATION (Dark vs Mega)
        stock_map = {}
        for inv in inventory_items:
            wh_type = inv.warehouse.warehouse_type
            stock = inv.total_stock - inv.reserved_stock
            
            if inv.sku not in stock_map:
                stock_map[inv.sku] = {'express_stock': 0, 'standard_stock': 0, 'sale_price': 0}
                
            if wh_type == 'dark_store':
                stock_map[inv.sku]['express_stock'] += stock
                stock_map[inv.sku]['sale_price'] = inv.price # Dark store price ki priority
            elif wh_type == 'mega':
                stock_map[inv.sku]['standard_stock'] += stock
                if stock_map[inv.sku]['sale_price'] == 0:
                    stock_map[inv.sku]['sale_price'] = inv.price

        for item in results:
            sku = item.get('sku')
            if sku in stock_map:
                sku_info = stock_map[sku]
                exp_stock = sku_info['express_stock']
                std_stock = sku_info['standard_stock']
                
                # Agar dark store me 1 bhi item hai, toh pehle wo dikhao
                if exp_stock > 0:
                    item['available_stock'] = exp_stock
                    item['delivery_type'] = 'dark_store'
                    item['delivery_eta'] = '10 Mins'
                    item['sale_price'] = sku_info['sale_price']
                    item['has_more_in_mega'] = std_stock > 0 # Frontend me tag lagane ke liye (ex: "+ More in 1-2 Days")
                elif std_stock > 0:
                    item['available_stock'] = std_stock
                    item['delivery_type'] = 'mega'
                    item['delivery_eta'] = '1-2 Days'
                    item['sale_price'] = sku_info['sale_price']
                    item['has_more_in_mega'] = False
                else:
                    item['available_stock'] = 0
                    item['delivery_eta'] = 'Out of Stock'
                    item['delivery_type'] = 'unavailable'
                    item['has_more_in_mega'] = False
            else:
                item['available_stock'] = 0
                item['delivery_eta'] = 'Unavailable'
                item['has_more_in_mega'] = False

class SkuDetailAPIView(generics.RetrieveAPIView):
    """
    Product Detail Page.
    Injects Available Stock for the detected Warehouse.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

    def get_object(self):
        lookup_val = self.kwargs.get('id')
        queryset = self.get_queryset()
        
    
        
        obj = None
        
        obj = queryset.filter(sku=lookup_val).first()
        
        if not obj and lookup_val.isdigit():
            obj = queryset.filter(id=int(lookup_val)).first()

        if not obj:
            raise NotFound(f"No Product matches the identifier: {lookup_val}")
            
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        lat = request.headers.get('X-Location-Lat') or request.query_params.get('lat')
        lng = request.headers.get('X-Location-Lng') or request.query_params.get('lon')

        if lat and lng:
            user_location = Point(float(lng), float(lat), srid=4326)
            serviceable_warehouses = Warehouse.objects.filter(is_active=True, delivery_zone__contains=user_location)
        else:
            warehouse = getattr(request, 'warehouse', None)
            serviceable_warehouses = Warehouse.objects.filter(id=warehouse.id) if warehouse else Warehouse.objects.none()

        inventory_items = InventoryItem.objects.filter(
            sku=instance.sku,
            bin__rack__aisle__zone__warehouse__in=serviceable_warehouses
        ).select_related('bin__rack__aisle__zone__warehouse')

        express_stock = 0
        standard_stock = 0
        sale_price = getattr(instance, 'mrp', 0)
        
        for inv in inventory_items:
            wh_type = inv.warehouse.warehouse_type
            stock = inv.total_stock - inv.reserved_stock
            
            if wh_type == 'dark_store':
                express_stock += stock
                sale_price = inv.price
            elif wh_type == 'mega':
                standard_stock += stock
                if express_stock == 0:
                    sale_price = inv.price

        serializer = self.get_serializer(instance)
        data = serializer.data
        
        if express_stock > 0:
            data['available_stock'] = express_stock
            data['delivery_type'] = 'dark_store'
            data['delivery_eta'] = '10 Mins'
            data['has_more_in_mega'] = standard_stock > 0
        elif standard_stock > 0:
            data['available_stock'] = standard_stock
            data['delivery_type'] = 'mega'
            data['delivery_eta'] = '1-2 Days'
            data['has_more_in_mega'] = False
        else:
            data['available_stock'] = 0
            data['delivery_type'] = 'unavailable'
            data['delivery_eta'] = 'Out of Stock'
            data['has_more_in_mega'] = False
        
        data['sale_price'] = sale_price
        if data.get('effective_price') is None:
            data['effective_price'] = sale_price

        return Response(data)

class StorefrontCatalogAPIView(APIView):
    """
    Home Page Feed with Infinite Scroll Support.
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
            OpenApiParameter("page", OpenApiTypes.INT, required=False, description="Page number for infinite scroll"),
        ],
    )
    def get(self, request):
        lat = request.headers.get('X-Location-Lat') or request.query_params.get("lat")
        lon = request.headers.get('X-Location-Lng') or request.query_params.get("lon")
        city = request.query_params.get("city", "")

        serviceable_warehouses = Warehouse.objects.none()
        if lat and lon:
            user_location = Point(float(lon), float(lat), srid=4326)
            serviceable_warehouses = Warehouse.objects.filter(is_active=True, delivery_zone__contains=user_location)

        if not serviceable_warehouses.exists():
            return Response({"serviceable": False, "message": "Location not serviceable"}, status=200)

        skus_in_stock = InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse__in=serviceable_warehouses,
            total_stock__gt=F('reserved_stock')
        ).values_list('sku', flat=True).distinct()

        all_categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order', 'name')
        
        page_number = request.query_params.get('page', 1)
        paginator = Paginator(all_categories, 4)
        
        try:
            page_obj = paginator.page(page_number)
        except Exception:
            return Response({
                "serviceable": True,
                "categories": [],
                "has_next": False
            })

        feed = []
        for cat in page_obj:
            price_subquery = InventoryItem.objects.filter(
                sku=OuterRef('sku'),
                bin__rack__aisle__zone__warehouse__in=serviceable_warehouses
            ).values('price')[:1]

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
                
                inventory_qs = InventoryItem.objects.filter(
                    sku__in=[p['sku'] for p in p_data],
                    bin__rack__aisle__zone__warehouse__in=serviceable_warehouses
                ).select_related('bin__rack__aisle__zone__warehouse')
                
                stock_map = {}
                for inv in inventory_qs:
                    wh_type = inv.warehouse.warehouse_type
                    stock = inv.total_stock - inv.reserved_stock
                    
                    if inv.sku not in stock_map:
                        stock_map[inv.sku] = {'express_stock': 0, 'standard_stock': 0}
                        
                    if wh_type == 'dark_store':
                        stock_map[inv.sku]['express_stock'] += stock
                    elif wh_type == 'mega':
                        stock_map[inv.sku]['standard_stock'] += stock
                
                for p in p_data: 
                    sku_info = stock_map.get(p['sku'], {'express_stock': 0, 'standard_stock': 0})
                    exp_stock = sku_info['express_stock']
                    std_stock = sku_info['standard_stock']
                    
                    if exp_stock > 0:
                        p['available_stock'] = exp_stock
                        p['delivery_type'] = 'dark_store'
                        p['delivery_eta'] = '10 Mins'
                        p['has_more_in_mega'] = std_stock > 0
                    elif std_stock > 0:
                        p['available_stock'] = std_stock
                        p['delivery_type'] = 'mega'
                        p['delivery_eta'] = '1-2 Days'
                        p['has_more_in_mega'] = False
                    else:
                        p['available_stock'] = 0
                        p['delivery_type'] = 'unavailable'
                        p['delivery_eta'] = 'Out of Stock'
                        p['has_more_in_mega'] = False
                    
                    if p.get('effective_price') is None:
                        p['effective_price'] = p.get('mrp')
                        p['sale_price'] = p.get('mrp')

                feed.append({
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "icon": request.build_absolute_uri(cat.icon) if cat.icon and not str(cat.icon).startswith('http') else cat.icon,
                    "products": p_data
                })

        return Response({
            "serviceable": True,
            "categories": feed,
            "has_next": page_obj.has_next()
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
            words = re.findall(r'\w+', query)
            for word in words:
                products = products.filter(
                    Q(name__icontains=word) | 
                    Q(sku__icontains=word) |
                    Q(description__icontains=word) |
                    Q(category__name__icontains=word) |
                    Q(category__parent__name__icontains=word)
                )
            
            products = products.annotate(
                relevance=Case(
                    When(name__iexact=query, then=Value(1)),
                    When(sku__iexact=query, then=Value(2)),
                    When(name__istartswith=query, then=Value(3)),
                    When(name__icontains=query, then=Value(4)),
                    When(description__icontains=query, then=Value(5)),
                    When(category__name__icontains=query, then=Value(6)),
                    When(category__parent__name__icontains=query, then=Value(7)),
                    default=Value(8),
                    output_field=IntegerField()
                )
            ).order_by('relevance', '-created_at')

        products = products[:40]
        return Response(ProductSerializer(products, many=True, context={'request': request}).data)

class SearchSuggestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < 2: return Response([])
        
        words = re.findall(r'\w+', query)
        
        product_results = Product.objects.filter(is_active=True).select_related('category')
        brand_results = Brand.objects.filter(is_active=True)
        
        for word in words:
            product_results = product_results.filter(
                Q(name__icontains=word) | 
                Q(description__icontains=word) | 
                Q(category__name__icontains=word) | 
                Q(category__parent__name__icontains=word) | 
                Q(sku__icontains=word)
            )
            brand_results = brand_results.filter(name__icontains=word)
            
        product_results = product_results.annotate(
            relevance=Case(
                When(name__istartswith=query, then=Value(1)), 
                When(name__icontains=query, then=Value(2)),
                When(description__icontains=query, then=Value(3)), 
                default=Value(4), 
                output_field=IntegerField()
            )
        ).order_by('relevance')[:5]
        
        brand_results = brand_results[:3]
        
        data = []
        
        for b in brand_results:
            logo_url = request.build_absolute_uri(b.logo.url) if b.logo else None
            data.append({
                "text": b.name, 
                "type": "Brand", 
                "image": logo_url,
                "url": f"/search_results.html?brand={b.id}"
            })
            
        for p in product_results:
            image_url = None
            if hasattr(p, 'image') and p.image:
                image_url = request.build_absolute_uri(p.image.url)
            elif hasattr(p, 'images') and p.images.exists() and p.images.first().image:
                image_url = request.build_absolute_uri(p.images.first().image.url)
                
            data.append({
                "text": p.name, 
                "type": p.category.name if p.category else "Product", 
                "price": getattr(p, 'mrp', None), 
                "image": image_url,
                "url": f"/product.html?code={p.sku}"
            })
            
        return Response(data)

class BannerListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = BannerSerializer
    queryset = Banner.objects.filter(is_active=True)
    pagination_class = None

class BrandListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    serializer_class = BrandSerializer
    queryset = Brand.objects.filter(is_active=True)
    pagination_class = None

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
    pagination_class = None
    
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('name')