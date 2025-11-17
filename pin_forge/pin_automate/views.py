from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from lxml import html
import requests
import json
import os
from django.conf import settings

from .models import Store, Product, Variant
from .serializers import (
    GroupSerializer,
    UserSerializer,
    StoreSerializer,
    ProductWriteSerializer,
    ProductSerializer
)
from .services.product_sync_service import ProductSyncService
from .services.ai_service import AIContentService
from .services.pin_service import PinGeneratorService


# ----------------------------------------
# AUTHENTICATION
# ----------------------------------------
class LoginView(TokenObtainPairView):
    """
    POST /api/login/
    Get access & refresh tokens using username & password.
    """
    pass


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
        return ProductSerializer


# ----------------------------------------
# CUSTOM ACTIONS
# ----------------------------------------

    @action(detail=False, methods=["post"])
    def sync_from_store(self, request):
        """
        Trigger syncing products from connected store (Printify/PrintHive) or fetch from URL.
        """
        store_id = request.data.get("store_id")
        store_url = request.data.get("store_url")

        if not store_id and not store_url:
            return Response(
                {"error": "store_id or store_url is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if store_url:
                # Fetch products from store URL
                product_data = self._fetch_products_from_url(store_url)
                return Response({
                    "message": "Products fetched from URL",
                    "products": product_data
                })
            else:
                # Sync from connected store
                store = Store.objects.get(id=store_id)
                ProductSyncService.sync(store)
                return Response({"message": "Sync started", "store_id": store_id})
        
        except Store.DoesNotExist:
            return Response(
                {"error": "Store not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def _fetch_products_from_url(self, url):
        """
        Fetch product data from a store URL using web scraping.
        """
        try:
            page = requests.get(url, timeout=10)
            page.raise_for_status()
            
            tree = html.fromstring(page.content.decode("utf8"))
            
            # Find all script tags
            all_scripts = tree.xpath('//script/text()')
            print(f"Total scripts found: {len(all_scripts)}")
            
            # Check each script for product data
            for i, script in enumerate(all_scripts):
                if 'product' in script.lower() and '{' in script:
                    print(f"Found product data in script {i}")
                    print(f"Script length: {len(script)}")
                    
                    fi = script.find('{')
                    
                    # Try to find '};' first, then fall back to '}'
                    li = script.rfind('};')
                    if li == -1:
                        li = script.rfind('}')
                    else:
                        li += 2  # Include '};'
                    
                    if li == -1:
                        raise ValueError("Could not find closing brace")
                    
                    print(f"Start index: {fi}, End index: {li}")
                    
                    data = script[fi:li+1]
                    print(f"Extracted data length: {len(data)}")
                    print(f"First 200 chars: {data[:200]}")
                    
                    product_data = json.loads(data)
                    
                    # Save JSON to file
                    os.makedirs('downloads', exist_ok=True)
                    file_path = os.path.join('downloads', 'products.json')
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(product_data, f, indent=2, ensure_ascii=False)
                    print(f"JSON saved to {file_path}")
                    
                    # The JSON structure is {productId: {b: {...}, ...}, ...}
                    # Extract the first product or all products
                    if product_data:
                        # Get the first product's data
                        first_product_id = list(product_data.keys())[0]
                        product = product_data[first_product_id].get('b', {})
                        return product
                    
                    return {}
            
            raise ValueError("Could not find product data in any script tag")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch URL: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse product data: {str(e)}")
