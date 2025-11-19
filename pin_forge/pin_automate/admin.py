from django.contrib import admin

# Register your models here.
from .models import Store, Product, Variant
admin.site.register(Store)
admin.site.register(Product)
admin.site.register(Variant)

