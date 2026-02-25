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
    StorefrontCatalogAPIView,
)

urlpatterns = [
    path('categories/parents/', NavbarCategoryAPIView.as_view(), name='navbar-categories'),
    path('categories/children/', HomeCategoryAPIView.as_view(), name='home-categories'),
    
    path('skus/', SkuListAPIView.as_view()),
    path('skus/<str:id>/', SkuDetailAPIView.as_view()), 
    path('products/<str:id>/', SkuDetailAPIView.as_view()), 
    path('categories/', CategoryListAPIView.as_view()),
    
    path('storefront/', StorefrontCatalogAPIView.as_view()), 
    path('home/feed/', StorefrontCatalogAPIView.as_view()),

    path('banners/', BannerListAPIView.as_view()),
    path('brands/', BrandListAPIView.as_view()),
    path('flash-sales/', FlashSaleListAPIView.as_view()),
    
    path('search/', GlobalSearchAPIView.as_view()),
    path('search/suggest/', SearchSuggestAPIView.as_view()),
]