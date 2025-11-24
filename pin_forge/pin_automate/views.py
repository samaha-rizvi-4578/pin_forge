from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from lxml import html
import requests
import json
import os
import requests
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.http import JsonResponse
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from urllib.parse import urlencode
from .generation.pinGeneration import generate_pin_content
from .models import Store, Product, Variant, PinTemplate, GeneratedPin
from .serializers import (
    GroupSerializer,
    UserSerializer,
    StoreSerializer,
    ProductWriteSerializer,
    ProductSerializer,
    PinTemplateSerializer,
    GeneratedPinSerializer
)
from .services.product_sync_service import ProductSyncService
from .services.ai_service import AIContentService
from .services.pin_service import PinGeneratorService

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode
import secrets
import base64
import requests

from django.utils import timezone
from datetime import timedelta
from .models import PinterestAuth
# -----------------------------------------------------
# Pinterst AUTH
# -----------------------------------------------------
@login_required(login_url='/api/login/')

def pinterest_auth_start(request):
    """
    Redirect the user to Pinterest OAuth authorization page
    """
    client_id = settings.PINTEREST_APP_ID
    redirect_uri = settings.PINTEREST_REDIRECT_URI
    state = secrets.token_urlsafe(16)

    # Save state in session to validate later
    request.session['pinterest_oauth_state'] = state

    scopes = ",".join([
        "pins:write",
        "boards:write",
        "boards:read",
        "pins:read",
        "user_accounts:read",
    ])

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }

    auth_url = f"https://www.pinterest.com/oauth/?{urlencode(params)}"
    return redirect(auth_url)


from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import base64
import requests
from .models import PinterestAuth

@login_required(login_url='/api/login/')

def pinterest_auth_callback(request):
    """
    Handle Pinterest OAuth callback and exchange code for access token
    """
    error = request.GET.get("error")
    if error:
        return JsonResponse({"error": error}, status=400)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User must be logged in"}, status=403)

    code = request.GET.get("code")
    state = request.GET.get("state")
    expected_state = request.session.pop("pinterest_oauth_state", None)

    if not code or state != expected_state:
        return JsonResponse({"error": "Invalid or missing code/state"}, status=400)

    token_url = "https://api.pinterest.com/v5/oauth/token"

    # Pinterest v5 requires HTTP Basic Auth for client credentials
    client_id = settings.PINTEREST_APP_ID
    client_secret = settings.PINTEREST_APP_SECRET
    creds = f"{client_id}:{client_secret}"
    b64_creds = base64.b64encode(creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_creds}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.PINTEREST_REDIRECT_URI
    }

    try:
        resp = requests.post(token_url, headers=headers, data=data, timeout=10)
        resp.raise_for_status()
    except requests.HTTPError:
        return JsonResponse({"error": "token exchange failed", "details": resp.text}, status=resp.status_code)
    except requests.RequestException as e:
        return JsonResponse({"error": "token exchange failed", "details": str(e)}, status=400)

    token_data = resp.json()

    # Save tokens in DB
    expires_at = None
    if token_data.get("expires_in"):
        expires_at = timezone.now() + timedelta(seconds=int(token_data["expires_in"]))

    PinterestAuth.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "scope": token_data.get("scope"),
            "expires_at": expires_at
        }
    )

    return JsonResponse({"status": "connected", "scope": token_data.get("scope")})



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
    # SYNC FROM STORE
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
                    attributes= variant["attributes"],
                    status = "new"
                )
                created_count += 1

            return Response({"message": f"{created_count} products imported successfully"})


# ----------------------------------
# geneate pin view set
# ---------------------------------
# -----------------------------------------------------
class PinTemplateViewSet(viewsets.ModelViewSet):
    queryset = PinTemplate.objects.all()
    serializer_class = PinTemplateSerializer
    permission_classes = [IsAuthenticated]


    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="generatedPin")
    def generatedPin(self, request):
        created_count = 0

        title = "Print Hive"

        # 1. Get store for the logged-in user
        try:
            store = Store.objects.get(name=title, user=request.user)
        except Store.DoesNotExist:
            return Response({"error": f"Store '{title}' not found for this user"}, status=404)

        # 2. Get products and variants
        products = Product.objects.filter(store=store)
        variants = Variant.objects.filter(product__in=products)

        if not variants.exists():
            return Response({"error": "No variants found for this store"}, status=404)

        # 3. Process all variants
        for variant in variants:

            # Skip duplicates
            if PinTemplate.objects.filter(variant=variant).exists():
                print("Skipping existing variant pin:", variant.variant_id)
                continue

            # Call AI
            ai_output = generate_pin_content(
                product_name=variant.product.title,
                attributes=variant.attributes,
                description=variant.product.description
            )
            print(ai_output)

            pin = PinTemplate.objects.create(
                variant=variant,
                title=ai_output.get("title", variant.name),
                description=ai_output.get("description", ""),
                hashtags=ai_output.get("hashtags", ""),
                alt_text=ai_output.get("alt_text", ""),
                ai_prompt_used="auto_generated",
                ai_response_id=""
            )

            created_count += 1

        return Response({"message": f"{created_count} pin templates generated."})



class GeneratedPinViewSet(viewsets.ModelViewSet):
    queryset = GeneratedPin.objects.all()
    serializer_class = GeneratedPinSerializer
    permission_classes = [IsAuthenticated]
    boards = {"Aesthetic Cozy Outfits" : "904590343844451063",
              "Casual Women’s Graphic Tees":"904590343844479634",
              "Custom Hoodies": "904590343844551606",
              "Programmer Humor T-Shirts": "904590343844474181"}

    def get_user_access_token(self, user):
        pa = PinterestAuth.objects.filter(user=user).first()
        if not pa:
            raise Exception("Pinterest not connected for this user")

        if pa.expires_at and pa.expires_at < timezone.now() + timedelta(minutes=5):
            pa = self.refresh_pinterest_token(pa)

        return pa.access_token

    def refresh_pinterest_token(self, pa: PinterestAuth):
        token_url = "https://api.pinterest.com/v5/oauth/token"
        client_id = settings.PINTEREST_APP_ID
        client_secret = settings.PINTEREST_APP_SECRET
        b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {b64}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": pa.refresh_token,
        }
        resp = requests.post(token_url, headers=headers, data=data, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
        pa.access_token = token_data.get("access_token")
        pa.refresh_token = token_data.get("refresh_token", pa.refresh_token)
        expires_in = token_data.get("expires_in")
        pa.expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None
        pa.scope = token_data.get("scope", pa.scope)
        pa.save()
        return pa

    SANDBOX_BASE_URL = "https://api-sandbox.pinterest.com/v5/"

    def pinterest_request(self, user, method, endpoint, data=None):
        token = self.get_user_access_token(user)
        url = f"{self.SANDBOX_BASE_URL}{endpoint}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        if method.upper() == "GET":
            return requests.get(url, headers=headers, params=data)
        elif method.upper() == "POST":
            return requests.post(url, headers=headers, json=data)
        raise Exception("Unsupported method")



    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # ------------------------------------------------------
    # SAVE GENERATED PIN FROM PinTemplate
    # ------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="savePin")
    def save_pin(self, request):

        created_count = 0
        store_title = "Print Hive"

        # 1. Validate store
        try:
            store = Store.objects.get(name=store_title, user=request.user)
        except Store.DoesNotExist:
            return Response(
                {"error": f"Store '{store_title}' not found for this user"},
                status=404
            )

        # 2. Get products + variants
        products = Product.objects.filter(store=store)
        variants = Variant.objects.filter(product__in=products)

        # 3. Pin templates for those variants
        pins = PinTemplate.objects.filter(variant__in=variants)

        if not pins.exists():
            return Response({"error": "No pin templates found"}, status=404)

        # 4. Create GeneratedPin for each template
        for pin in pins:

            # Skip duplicates
            if GeneratedPin.objects.filter(pin_template=pin).exists():
                continue

            GeneratedPin.objects.create(
                final_image = pin['variant']["product"]["image"],
                pin_template=pin,
                title=pin.title,
                description=pin.description,
                board=self.boards["asthetic cozy outfits"],   # you can change if needed
                status="draft",
                pinterest_pin_id = pin, # abhichagne akrna hai 
                ai_prompt_used="auto_generated"
            )

            created_count += 1

        return Response({"message": f"{created_count} generated pins saved."})


    # # =====================================================
    # # 🔥 Pinterest API Helper
    # # =====================================================
    # def pinterest_request(self, method, endpoint, token, data=None):
    #     url = f"https://api.pinterest.com/v5/{endpoint}"

    #     headers = {
    #         "Authorization": f"Bearer {token}",
    #         "Content-Type": "application/json"
    #     }

    #     if method == "GET":
    #         return requests.get(url, headers=headers, params=data)
    #     elif method == "POST":
    #         return requests.post(url, headers=headers, json=data)

    #     return None


    # ------------------------------------------------------
    # GET PINTEREST BOARDS
    # ------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="pinterest/boards")
    def get_pinterest_boards(self, request):
        access_token = settings.PINTEREST_ACCESS_TOKEN

        response = self.pinterest_request(
            method="GET",
            endpoint="boards",
            token=access_token
        )

        return Response(response.json(), status=response.status_code)


    # ------------------------------------------------------
    # CREATE A PINTEREST BOARD
    # ------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="pinterest/createBoard")
    def create_pinterest_board(self, request):
        access_token = settings.PINTEREST_ACCESS_TOKEN
        board_name = request.data.get("name")

        if not board_name:
            return Response({"error": "Board name is required"}, status=400)

        payload = {"name": board_name}

        response = self.pinterest_request(
            method="POST",
            endpoint="boards",
            token=access_token,
            data=payload
        )

        return Response(response.json(), status=response.status_code)


    # ------------------------------------------------------
    # POST A PIN TO PINTEREST
    # ------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="pinterest/postPin")
    def post_pin(self, request):
        access_token = settings.PINTEREST_ACCESS_TOKEN

        board_id = request.data.get("board_id")
        title = request.data.get("title")
        description = request.data.get("description")
        media_url = request.data.get("media_url")  # image URL
        link = request.data.get("link")
        dominant_color = request.data.get("dominant_color")
        alt_text = request.data.get("alt_text")

        if not all([board_id, title, media_url]):
            return Response({"error": "board_id, title, media_url required"}, status=400)

        payload = {
            "board_id": board_id,
            "title": title,
            "description": description,
            "alt_text": alt_text,
            "dominant_color": dominant_color,
            "link": link,
            "media_source": {
                "source_type": "image_url",
                "url": media_url
            }
        }



        response = self.pinterest_request(
            request.user,
            method="POST",
            endpoint="pins",
            data=payload
        )

        return Response(response.json(), status=response.status_code)



