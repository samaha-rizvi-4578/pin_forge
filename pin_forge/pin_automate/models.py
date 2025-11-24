from django.db import models
from django.contrib.auth.models import User


class Store(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stores")
    name = models.CharField(max_length=255, null=True, blank=True)
    url = models.URLField()
    connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or "Unnamed Store"


class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="products")
    product_id = models.CharField(max_length=255)  # from printify/shopify/etc.
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    url = models.URLField()  # link to your product page
    main_image = models.URLField(null=True, blank=True)
    status = models.CharField(max_length=100)  # draft, active, archived
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    variant_id = models.CharField(max_length=255)

    name = models.CharField(max_length=255)  # e.g. "Black - Large"
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    image = models.URLField(null=True, blank=True)
    attributes = models.JSONField(default=dict)  # color, size, etc.
    status = models.CharField(max_length=100, default="new")  # draft, active, archived

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.title} - {self.name}"


class PinTemplate(models.Model):
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="pin_templates")

    title = models.CharField(max_length=500)
    description = models.TextField()
    hashtags = models.TextField(null=True, blank=True)
    alt_text = models.TextField(null=True, blank=True)

    ai_prompt_used = models.TextField(null=True, blank=True)
    ai_response_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Template for {self.variant.name}"


class GeneratedPin(models.Model):
    pin_template = models.ForeignKey(PinTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    final_image = models.URLField()
    title = models.CharField(max_length=500)
    description = models.TextField()
    board = models.CharField(max_length=255, null=True, blank=True)  # Pinterest board ID

    status = models.CharField(
        max_length=50,
        choices=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("posted", "Posted"),
            ("failed", "Failed")
        ],
        default="draft"
    )

    pinterest_pin_id = models.CharField(max_length=255, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Generated Pin - {self.title}"


class PinterestAuth(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pinterest Auth - {self.user.username}"
