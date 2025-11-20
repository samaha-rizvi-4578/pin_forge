from django.contrib.auth.models import Group, User
from rest_framework import serializers
from .models import (
    Store,
    Product,
    Variant,
    PinTemplate,
    GeneratedPin,
    PinterestAuth,
)


# ----------------------------------------
# USER + GROUP SERIALIZERS
# ----------------------------------------
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["id", "url", "username", "email", "groups"]
        read_only_fields = ["id"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


# ----------------------------------------
# STORE
# ----------------------------------------
class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = "__all__"
        read_only_fields = ["user", "connected", "created_at", "updated_at"]


# ----------------------------------------
# VARIANT - READ
# ----------------------------------------
class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# ----------------------------------------
# PRODUCT - READ (nested)
# ----------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, read_only=True)
    store = StoreSerializer(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# ----------------------------------------
# VARIANT - WRITE (nested)
# ----------------------------------------
class VariantWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = [
            "id",
            "variant_id",
            "name",
            "price",
            "image",
            "attributes",
            "status",
        ]
        extra_kwargs = {
            "id": {"read_only": False, "required": False},
        }


# ----------------------------------------
# PRODUCT - WRITE (nested)
# ----------------------------------------
class ProductWriteSerializer(serializers.ModelSerializer):
    variants = VariantWriteSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "store",
            "product_id",
            "title",
            "description",
            "url",
            "main_image",
            "status",
            "variants",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        variants_data = validated_data.pop("variants")
        product = Product.objects.create(**validated_data)

        for variant_data in variants_data:
            Variant.objects.create(product=product, **variant_data)

        return product

    def update(self, instance, validated_data):
        variants_data = validated_data.pop("variants", None)

        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if variants_data is not None:
            existing_ids = [v.get("id") for v in variants_data if v.get("id")]
            instance.variants.exclude(id__in=existing_ids).delete()

            for v_data in variants_data:
                if "id" in v_data:
                    variant_obj = Variant.objects.get(id=v_data["id"])
                    for key, value in v_data.items():
                        setattr(variant_obj, key, value)
                    variant_obj.save()
                else:
                    Variant.objects.create(product=instance, **v_data)

        return instance


# ----------------------------------------
# PIN TEMPLATE
# ----------------------------------------
class PinTemplateSerializer(serializers.ModelSerializer):
    variant = VariantSerializer(read_only=True)

    class Meta:
        model = PinTemplate
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# ----------------------------------------
# GENERATED PIN
# ----------------------------------------
class GeneratedPinSerializer(serializers.ModelSerializer):
    variant = VariantSerializer(read_only=True)
    pin_template = PinTemplateSerializer(read_only=True)

    class Meta:
        model = GeneratedPin
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "pinterest_pin_id",
            "error_message",
            "posted_at",
        ]


# ----------------------------------------
# PINTEREST AUTH
# ----------------------------------------
class PinterestAuthSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = PinterestAuth
        fields = "__all__"
        read_only_fields = ["id", "created_at"]
