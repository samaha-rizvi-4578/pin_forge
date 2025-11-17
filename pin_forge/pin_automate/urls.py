from django.urls import path, include
from rest_framework import routers

from .views import (
    UserViewSet,
    GroupViewSet,
    StoreViewSet,
    ProductViewSet,
)

# -----------------------------
# DRF ROUTER
# -----------------------------
router = routers.DefaultRouter()

# Auth/User endpoints
router.register(r'users', UserViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')

# Stores
router.register(r'stores', StoreViewSet, basename='store')

# Products (with nested variants)
router.register(r'products', ProductViewSet, basename='product')

# -----------------------------
# URL PATTERNS
# -----------------------------
urlpatterns = [
    path('', include(router.urls)),
]
