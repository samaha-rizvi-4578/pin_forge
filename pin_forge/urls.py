from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from rest_framework.schemas import get_schema_view
from rest_framework.documentation import include_docs_urls

from pin_forge.pin_automate import views


# DRF API documentation
API_TITLE = "PinForge API"
API_DESCRIPTION = "API for PrintHive automation, product sync, AI content, and Pinterest pins."

schema_view = get_schema_view(title=API_TITLE)

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # Pin Automate App API
    path('api/', include('pin_forge.pin_automate.urls')),

    # Optional DRF Auth (login/logout for browsable API)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # API schema and docs
    path('api/schema/', schema_view, name='api-schema'),
    path('api/docs/', include_docs_urls(title=API_TITLE, description=API_DESCRIPTION)),
]
