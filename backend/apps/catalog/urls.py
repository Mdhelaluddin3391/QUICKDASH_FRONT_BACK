# apps/catalog/urls.py
from django.urls import path
from .views import (
    SkuListAPIView, 
    SkuDetailAPIView, 
    CategoryListAPIView,
    BannerListAPIView, 
    BrandListAPIView, 
    FlashSaleListAPIView, 
    HomeFeedAPIView, 
    GlobalSearchAPIView, 
    SearchSuggestAPIView,
    StorefrontCatalogAPIView
)
from .views import (
    NavbarCategoryAPIView,
    HomeCategoryAPIView,
    SkuListAPIView,
    SkuDetailAPIView,
    GlobalSearchAPIView,
    HomeFeedAPIView,
    BannerListAPIView,
    BrandListAPIView,
    FlashSaleListAPIView
)


urlpatterns = [

    path('categories/parents/', NavbarCategoryAPIView.as_view(), name='navbar-categories'),
    path('categories/children/', HomeCategoryAPIView.as_view(), name='home-categories'),
    # Core Catalog
    path('skus/', SkuListAPIView.as_view()),
    path('skus/<str:id>/', SkuDetailAPIView.as_view()), # Supports ID or Code
    path('categories/', CategoryListAPIView.as_view()),
    path('storefront/', StorefrontCatalogAPIView.as_view()), # Optimized full-store view

    # Discovery & Home
    path('banners/', BannerListAPIView.as_view()),
    path('brands/', BrandListAPIView.as_view()),
    path('flash-sales/', FlashSaleListAPIView.as_view()),
    path('home/feed/', HomeFeedAPIView.as_view()), # Fixed path naming consistency
    
    # Search
    path('search/', GlobalSearchAPIView.as_view()),
    path('search/suggest/', SearchSuggestAPIView.as_view()),
]


