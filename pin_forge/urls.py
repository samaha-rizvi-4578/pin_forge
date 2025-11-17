from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
path('api/', include('pin_forge.pin_automate.urls')),
from pin_forge.pin_automate.views import (
    UserViewSet, GroupViewSet, StoreViewSet, ProductViewSet, LoginView
)

# include_docs_urls requires `coreapi` to be installed; create docs view
# defensively so missing optional dependencies don't break management commands.
try:
    from rest_framework.documentation import include_docs_urls
except Exception:
    include_docs_urls = None


# DRF API documentation
API_TITLE = "PinForge API"
API_DESCRIPTION = "API for PrintHive automation, product sync, AI content, and Pinterest pins."

schema_view = get_schema_view(title=API_TITLE)

# Build docs view only if include_docs_urls is available and coreapi is present.
docs_view = None
if include_docs_urls is not None:
    try:
        docs_view = include_docs_urls(title=API_TITLE, description=API_DESCRIPTION)
    except Exception:
        docs_view = None

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'stores', StoreViewSet)
router.register(r'products', ProductViewSet)

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # Login endpoint
    path('api/login/', LoginView.as_view(), name='login'),

    # Other endpoints
    path('api/', include(router.urls)),

    # Optional DRF Auth (login/logout for browsable API)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # API schema and optional docs
    path('api/schema/', schema_view, name='api-schema'),
]

# Add docs URL only when the docs view was created successfully
if docs_view is not None:
    urlpatterns += [
        path('api/docs/', docs_view),
    ]

