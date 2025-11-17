from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Store, Product, Variant
from .serializers import (
    GroupSerializer,
    UserSerializer,
    StoreSerializer,
    ProductWriteSerializer,
    ProductReadSerializer
)
from .services.product_sync_service import ProductSyncService
from .services.ai_service import AIContentService
from .services.pin_service import PinGeneratorService


# ----------------------------------------
# USER & GROUP VIEWSETS
# ----------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------------------
# STORE VIEWSET
# ----------------------------------------
class StoreViewSet(viewsets.ModelViewSet):
    """
    CRUD for user stores (PrintHive/Printify).
    """
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Hook for additional processing when a store is created.
        """
        serializer.save()


# ----------------------------------------
# PRODUCT VIEWSET
# ----------------------------------------
class ProductViewSet(viewsets.ModelViewSet):
    """
    Product CRUD + Nested Variant support + AI content + Pin generation.
    """
    queryset = Product.objects.prefetch_related("variants").all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """
        Use write serializer for POST/PUT/PATCH, read serializer for GET.
        """
        if self.request.method in ["POST", "PUT", "PATCH"]:
            return ProductWriteSerializer
        return ProductReadSerializer


# ----------------------------------------
# CUSTOM ACTIONS
# ----------------------------------------

    @action(detail=False, methods=["post"])
    def sync_from_store(self, request):
        """
        Trigger syncing products from connected store (Printify/PrintHive)
        """
        store_id = request.data.get("store_id")

        if not store_id:
            return Response({"error": "store_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"error": "Store not found"}, status=status.HTTP_404_NOT_FOUND)

        ProductSyncService.sync(store)
        return Response({"message": "Sync started", "store_id": store_id})


    @action(detail=True, methods=["post"])
    def generate_ai_content(self, request, pk=None):
        """
        Generate AI-based title & description for a product.
        """
        product = self.get_object()
        ai_result = AIContentService.generate_product_content(product)
        return Response(ai_result)


    @action(detail=True, methods=["post"])
    def generate_pins(self, request, pk=None):
        """
        Generate draft pins for the product (default 10).
        """
        product = self.get_object()
        count = int(request.data.get("pins", 10))
        pin_list = PinGeneratorService.generate(product, count)
        return Response({"pins": pin_list})
