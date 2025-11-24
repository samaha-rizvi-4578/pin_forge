from django.urls import path, include
from rest_framework import routers
from . import views
from .views import (
    UserViewSet,
    GroupViewSet,
    StoreViewSet,
    ProductViewSet,
    PinTemplateViewSet,
    GeneratedPinViewSet
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
# pintempaltes
router.register(r'pintemplates', PinTemplateViewSet, basename='pintemplate')
# generatedpin
router.register(r'generatedpins', GeneratedPinViewSet, basename='generatedpin')


# -----------------------------
# URL PATTERNS
# -----------------------------
urlpatterns = [
    path("pinterest/start/", views.pinterest_auth_start, name="pinterest_start"),
    path("pinterest/callback/", views.pinterest_auth_callback, name="pinterest_callback"),
    path('', include(router.urls)),
]
