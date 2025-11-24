from django.contrib import admin

# Register your models here.
from .models import Store, Product, Variant, PinTemplate, GeneratedPin
admin.site.register(Store)
admin.site.register(Product)
admin.site.register(Variant)
admin.site.register(PinTemplate)
admin.site.register(GeneratedPin)

