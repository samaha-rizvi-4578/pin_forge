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
                # extract fields for store
                name = product_data.get("title", "Untitled Store")
                url = store_url
                store, created = Store.objects.get_or_create(
                    user = request.user,
                    url = url,
                    name = name
                )
                message = "Store fetched and created" if created else "Store already exists"
                return Response({"message": message, "products": product_data})

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
            # print(all_scripts)
            for script in all_scripts:
                # print(script)
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
            
            first_key = list(data.keys())[0]

            b_value = data[first_key].get('b', {})

                # Ensure b_value is a dict with 'data'
            if isinstance(b_value, dict) and 'data' in b_value:
                data_list = b_value['data']
                if isinstance(data_list, list) and len(data_list) > 0:
                    first_product = data_list[0]
                    title = first_product.get("title", "Untitled")
                else:
                    title = "Untitled"
            else:
                title = "Untitled"
            productKey = "2712286816" # this is from where our products are starting

            if productKey in data:
                try:
                    product_list = data[productKey]['b'].get('data', [])
                    if not isinstance(product_list, list):
                        product_list = [product_list]
                    return product_list, title
                except KeyError as e:
                    print(f"eror accessing nested product data: {e}")
                    return e
            else:
                 print(f"Key '{productKey}' not found in the JSON file.")
                 return None, title
        except FileNotFoundError:
            print("Error: products.json not found.")
            return None, "Untitled"

        except json.JSONDecodeError:
            print("Error: JSON file is invalid.")
            return None, "Untitled"


    # -----------------------------------------------------
    # extract variants 
    # -----------------------------------------------------
    def extractOptions(self, product):
        colors = []
        sizes = []

        for option in product.get("options", []):
            if option.get("type") == "color":
                for item in option.get("items", []):
                    colors.append({
                        "id": item.get("id"),
                        "label": item.get("label"),
                        "hex": item.get("values", [None])[0]
                    })

            if option.get("type") == "size":
                for item in option.get("items", []):
                    sizes.append({
                        "id": item.get("id"),
                        "label": item.get("label")
                    })

        return colors, sizes

    # -----------------------------------------------------
    # generate variants from mextracted variants
    # -----------------------------------------------------

    def generateVariants(self, colors, sizes, price):
        variants = []

        for color in colors:
            for size in sizes:
                variants.append({
                    "name": f"{color['label']}-{size['label']}",
                    "variant_id": f"{color['id']}-{size['id']}",
                    "price": price,
                    "attributes": {
                        "color": color.get("label"),
                        "hex": color.get("hex"),
                        "size": size.get("label")
                    }
                })

        return variants

    # -----------------------------------------------------
    # STORE PRODUCTS FROM JSON API
    # -----------------------------------------------------
    @action(detail=False, methods=["get", "post"], url_path="storeProductfromJson")
    def storeProductfromJson(self, request):
        data, title = self.read_products_json()

        if request.method == "GET":
            return Response({"status": "success", "products": data})

        if request.method == "POST":
            if not data:
                return Response({"error": "No data found"}, status=400)
            try:
                store = Store.objects.get(
                    # name = title,
                    name = "Print Hive",
                    user = request.user
                )
            except Store.DoesNotExist:
                return Response({"error": f"Store {title} not found for this user"})
            created_count = 0
            for product in data:
                # craete product
                title=product.get("title", "Untitled")
                description=product.get("description", "")
                url = store.url + product.get("path", "")
                main_image=product.get("image", "")
                product_id = product.get("id")
                print('/n',created_count, title, description)
                
                # if exist then skip
                if Product.objects.filter(product_id = product_id).exists():
                    print("skiping existing product", product_id)
                    continue
                p = Product.objects.create(
                    title=title,
                    product_id = product_id,
                    description=description,
                    store = store,
                    url = url,
                    main_image = main_image,
                    status = "new"
                )

                #  ok for varainsts => colro and size will be list of dicts so taht we can concatenate them for each different variant 
                # extract colors and sizes
                colors, sizes = self.extractOptions(product)
                price=product["default_variant"].get("retail_price", 0)
                variants = self.generateVariants(colors, sizes, price/100)
                for variant in variants:
                    # skip if variant exist
                    if Variant.objects.filter(product = p, variant_id = variant["variant_id"]).exists():
                        print("skipping exisitng variants: ", variant["variant_id"])
                        continue

                    Variant.objects.create(
                    product=p,
                    variant_id = variant["variant_id"],
                    name = variant["name"],
                    price=variant["price"],
                    attributes= variant["attributes"]
                )
                created_count += 1

            return Response({"message": f"{created_count} products imported successfully"})


# 
                    # print('/nVariant: ',variant)
                    # flag = Variant.objects.get(
                    # product_id = product.get("id")
                    # variant_id
                    # )
                    # if (empty(flag)){
                    # continue;
                    # }
