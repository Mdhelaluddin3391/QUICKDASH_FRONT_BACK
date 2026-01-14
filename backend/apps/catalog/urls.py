from django.urls import path
from .views import (
    NavbarCategoryAPIView,
    HomeCategoryAPIView,
    SkuListAPIView,
    SkuDetailAPIView,
    CategoryListAPIView,
    BannerListAPIView,
    BrandListAPIView,
    FlashSaleListAPIView,
    GlobalSearchAPIView,
    SearchSuggestAPIView,
    StorefrontCatalogAPIView, # ✅ यहाँ हमने सही नाम इस्तेमाल किया है
)

urlpatterns = [
    # Navigation
    path('categories/parents/', NavbarCategoryAPIView.as_view(), name='navbar-categories'),
    path('categories/children/', HomeCategoryAPIView.as_view(), name='home-categories'),
    
    # Core Catalog
    path('skus/', SkuListAPIView.as_view()),
    path('skus/<str:id>/', SkuDetailAPIView.as_view()), 
    path('categories/', CategoryListAPIView.as_view()),
    
    # Storefront / Home Feed
    path('storefront/', StorefrontCatalogAPIView.as_view()), 
    path('home/feed/', StorefrontCatalogAPIView.as_view()), # ✅ HomeFeedAPIView हटाकर StorefrontCatalogAPIView लगा दिया

    # Discovery
    path('banners/', BannerListAPIView.as_view()),
    path('brands/', BrandListAPIView.as_view()),
    path('flash-sales/', FlashSaleListAPIView.as_view()),
    
    # Search
    path('search/', GlobalSearchAPIView.as_view()),
    path('search/suggest/', SearchSuggestAPIView.as_view()),
]