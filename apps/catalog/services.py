from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Product, ProductImage

@transaction.atomic
def publish_product(*, product):
    product=Product.objects.select_for_update().get(pk=product.pk)
    if product.product_type==Product.ProductType.SIMPLE:
        if not product.sku: raise ValidationError({"sku":"SKU is required for simple products."})
        if product.variants.exists(): raise ValidationError({"variants":"Simple products cannot have variants."})
    else:
        if not product.variants.filter(is_active=True).exists(): raise ValidationError({"variants":"At least one active variant is required before publishing."})
    product.status=Product.Status.ACTIVE; product.published_at=product.published_at or timezone.now()
    product.save(update_fields=["status","published_at","updated_at"])
    return product

@transaction.atomic
def set_primary_image(*, image):
    ProductImage.objects.filter(product=image.product,variant=image.variant,is_primary=True).exclude(pk=image.pk).update(is_primary=False)
    if not image.is_primary:
        image.is_primary=True; image.save(update_fields=["is_primary","updated_at"])
    return image

def reorder_images(*, product, ordered_ids):
    images={x.id:x for x in ProductImage.objects.filter(product=product,id__in=ordered_ids)}
    if len(images)!=len(set(ordered_ids)): raise ValidationError({"images":"Invalid image list."})
    for i,image_id in enumerate(ordered_ids): images[image_id].order=i
    ProductImage.objects.bulk_update(images.values(),["order"])
