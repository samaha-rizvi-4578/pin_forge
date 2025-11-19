from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from lxml import html
import requests
import json
import os
from rest_framework.permissions import IsAuthenticated
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


# -----------------------------------------------------
# AUTH
# -----------------------------------------------------
class LoginView(TokenObtainPairView):
    """POST /api/login/"""


# -----------------------------------------------------
# USER VIEWSET
# -----------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


# -----------------------------------------------------
# GROUP VIEWSET
# -----------------------------------------------------
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


# -----------------------------------------------------
# STORE VIEWSET
# -----------------------------------------------------
class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# -----------------------------------------------------
# PRODUCT VIEWSET
# -----------------------------------------------------
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.prefetch_related("variants").all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["POST", "PUT", "PATCH"]:
            return ProductWriteSerializer
        return ProductSerializer

    # ------------------------------
    # SYNC ACTION
    # ------------------------------
    @action(detail=False, methods=["post"])
    def sync_from_store(self, request):
        store_id = request.data.get("store_id")
        store_url = request.data.get("store_url")

        if not store_id and not store_url:
            return Response({"error": "store_id or store_url required"}, status=400)

        try:
            if store_url:
                product_data = self._fetch_products_from_url(store_url)
                return Response({"message": "Products fetched", "products": product_data})

            store = Store.objects.get(id=store_id)
            ProductSyncService.sync(store)

            return Response({"message": "Sync started", "store_id": store_id})

        except Store.DoesNotExist:
            return Response({"error": "Store not found"}, status=404)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

    # ------------------------------
    # SCRAPE PRODUCT JSON FROM URL
    # ------------------------------
    def _fetch_products_from_url(self, url):
        try:
            page = requests.get(url, timeout=10)
            page.raise_for_status()

            tree = html.fromstring(page.content.decode("utf8"))
            all_scripts = tree.xpath('//script/text()')

            for script in all_scripts:
                if 'product' in script.lower() and '{' in script:
                    fi = script.find('{')
                    li = script.rfind('};')
                    if li == -1:
                        li = script.rfind('}')
                    else:
                        li += 2

                    data = script[fi:li+1]
                    product_data = json.loads(data)

                    # Save JSON into downloads/products.json
                    save_path = os.path.join(settings.BASE_DIR, "downloads")
                    os.makedirs(save_path, exist_ok=True)
                    file_path = os.path.join(save_path, "products.json")

                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(product_data, f, indent=2, ensure_ascii=False)

                    first_key = list(product_data.keys())[0]
                    return product_data[first_key].get("b", {})

            raise Exception("No valid product JSON found")

        except Exception as e:
            raise Exception(f"Failed to fetch URL: {str(e)}")


    # -----------------------------------------------------
    # READ JSON FROM downloads/products.json
    # -----------------------------------------------------
    def read_products_json(self):
        file_path = os.path.join(settings.BASE_DIR, "downloads", "products.json")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            productKey = "2712286816" # this is from where our products are starting

            if productKey in data:
                try:
                    product_list = data[productKey]['b']['data']
                    return product_list
                except KeyError as e:
                    print(f"eror accessing nested product data: {e}")
                    return e
            else:
                 print(f"Key '{productKey}' not found in the JSON file.")
                 return None
        except FileNotFoundError:
            print("Error: products.json not found.")
            return None

        except json.JSONDecodeError:
            print("Error: JSON file is invalid.")
            return None


    # -----------------------------------------------------
    # STORE PRODUCTS FROM JSON API
    # -----------------------------------------------------
    @action(detail=False, methods=["get", "post"], url_path="storeProductfromJson")
    def storeProductfromJson(self, request):
        data = self.read_products_json()

        if request.method == "GET":
            return Response({"status": "success", "products": data})

        if request.method == "POST":
            if not data:
                return Response({"error": "No data found"}, status=400)

            # If product_data is a dict, convert to list
            if isinstance(data, dict):
                data = [data]

            for product in data:
                p = Product.objects.create(
                    title=product.get("title", "Untitled"),
                    description=product.get("description", ""),
                    price=product.get("price", 0)
                )

                for variant in product.get("variants", []):
                    Variant.objects.create(
                        product=p,
                        color=variant.get("color"),
                        size=variant.get("size"),
                        stock=variant.get("stock", 0)
                    )

            return Response({"message": "Products imported successfully"})
