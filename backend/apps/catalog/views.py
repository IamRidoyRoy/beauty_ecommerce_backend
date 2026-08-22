from django.db import transaction
from django.db.models import Q, Max
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet,ModelViewSet
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import *
from .serializers import *
from .selectors import product_list_queryset,product_detail_queryset
from .filters import ProductFilter
from .services import publish_product,set_primary_image,reorder_images

CatalogAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.PRODUCT_MANAGER)
class ProductViewSet(ReadOnlyModelViewSet):
    permission_classes=[AllowAny]; lookup_field="slug"; filterset_class=ProductFilter; search_fields=("name","sku","brand__name","category__name"); ordering_fields=("created_at","base_price","name")
    def get_queryset(self): return product_detail_queryset() if self.action=="retrieve" else product_list_queryset()
    def get_serializer_class(self): return ProductDetailSerializer if self.action=="retrieve" else ProductListSerializer
    @action(detail=False,methods=["get"],url_path="search")
    def search(self,request): return self.list(request)
class CategoryViewSet(ReadOnlyModelViewSet):
    permission_classes=[AllowAny]; serializer_class=CategorySerializer; queryset=Category.objects.filter(active=True).select_related("parent")
class BrandViewSet(ReadOnlyModelViewSet):
    permission_classes=[AllowAny]; serializer_class=BrandSerializer; queryset=Brand.objects.filter(active=True)

class WishlistView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request): return success(ProductListSerializer(product_list_queryset().filter(wishlisted_by__user=request.user),many=True,context={"request":request}).data)
    def post(self,request):
        product=Product.objects.get(pk=request.data.get("product")); WishlistItem.objects.get_or_create(user=request.user,product=product)
        from apps.common.models import AnalyticsEvent
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.WISHLIST,user=request.user,product_id_ref=product.id)
        return success(message="Added to wishlist.",status=201)
    def delete(self,request): WishlistItem.objects.filter(user=request.user,product_id=request.data.get("product")).delete(); return success(message="Removed from wishlist.")

class AdminProductViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=ProductAdminSerializer
    queryset=Product.objects.all().select_related("brand","category").prefetch_related("variants","images").order_by("-id")
    filterset_fields=("product_type","status","brand","category","featured","new_arrival","bestseller","trending"); search_fields=("name","sku","barcode","brand__name","category__name","variants__sku"); ordering_fields=("id","created_at","updated_at","base_price","name")
    @action(detail=True,methods=["post"])
    def publish(self,request,pk=None): return success(ProductAdminSerializer(publish_product(product=self.get_object())).data,"Product published.")
class AdminVariantViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=VariantAdminSerializer
    queryset=ProductVariant.objects.select_related("product").prefetch_related("attributes__attribute").order_by("-id"); filterset_fields=("product","is_active"); search_fields=("sku","barcode","product__name")
class AdminCategoryViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=CategorySerializer; queryset=Category.objects.select_related("parent").all(); search_fields=("name","slug","description"); filterset_fields=("active","parent"); ordering_fields=("name","order","created_at")
class AdminBrandViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=BrandSerializer; queryset=Brand.objects.all(); search_fields=("name","slug","country"); filterset_fields=("active","featured","country"); ordering_fields=("name","created_at")
class AdminImageViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=ProductImageSerializer; parser_classes=[MultiPartParser,FormParser]; queryset=ProductImage.objects.select_related("product","variant").all(); filterset_fields=("product","variant","image_type","is_primary"); search_fields=("alt_text","product__name","variant__sku")

    @transaction.atomic
    def perform_destroy(self,instance):
        product_id,variant_id,was_primary=instance.product_id,instance.variant_id,instance.is_primary
        instance.delete()
        if was_primary:
            replacement=ProductImage.objects.filter(product_id=product_id,variant_id=variant_id).order_by("order","id").first()
            if replacement:
                replacement.is_primary=True
                replacement.save(update_fields=["is_primary","updated_at"])

    @action(detail=True,methods=["post"],url_path="set-primary")
    def primary(self,request,pk=None): return success(ProductImageSerializer(set_primary_image(image=self.get_object()),context={"request":request}).data,"Primary image updated.")
    @action(detail=False,methods=["post"],url_path="reorder")
    def reorder(self,request):
        product=Product.objects.get(pk=request.data.get("product")); reorder_images(product=product,ordered_ids=request.data.get("image_ids",[])); return success(message="Images reordered.")
class BulkImageUploadView(APIView):
    permission_classes=[CatalogAdmin]; parser_classes=[MultiPartParser,FormParser]

    @transaction.atomic
    def post(self,request):
        product=Product.objects.filter(pk=request.data.get("product")).first()
        if not product:
            raise ValidationError({"product":"A valid product is required."})

        variant_id=request.data.get("variant") or None
        variant=ProductVariant.objects.filter(pk=variant_id,product=product).first() if variant_id else None
        if variant_id and not variant:
            raise ValidationError({"variant":"Invalid variant for product."})

        files=request.FILES.getlist("images")
        if not files:
            raise ValidationError({"images":"Select at least one image."})

        primary_index_raw=request.data.get("primary_index")
        primary_index=None
        if primary_index_raw not in (None, ""):
            try:
                primary_index=int(primary_index_raw)
            except (TypeError,ValueError):
                raise ValidationError({"primary_index":"Primary image index must be an integer."})
            if primary_index < 0 or primary_index >= len(files):
                raise ValidationError({"primary_index":"Primary image index is outside the uploaded image list."})

        scope=ProductImage.objects.select_for_update().filter(product=product,variant=variant)
        # If this is the first gallery upload, make the first image the feature image
        # even when the client did not explicitly send primary_index.
        if primary_index is None and not scope.filter(is_primary=True).exists():
            primary_index=0

        if primary_index is not None:
            scope.filter(is_primary=True).update(is_primary=False)

        max_order=scope.aggregate(max_order=Max("order"))["max_order"]
        start_order=(max_order if max_order is not None else -1)+1
        created=[]
        for i,file_obj in enumerate(files):
            created.append(ProductImage.objects.create(
                product=product,
                variant=variant,
                image=file_obj,
                image_type=ProductImage.ImageType.GALLERY,
                alt_text=product.name,
                order=start_order+i,
                is_primary=(i==primary_index),
            ))

        return success(
            ProductImageSerializer(created,many=True,context={"request":request}).data,
            "Images uploaded.",
            201,
        )

class AdminAttributeViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=AttributeAdminSerializer; queryset=Attribute.objects.all().order_by("display_order","name"); search_fields=("name","slug"); ordering_fields=("display_order","name")
class AdminAttributeValueViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=AttributeValueAdminSerializer; queryset=AttributeValue.objects.select_related("attribute").all(); filterset_fields=("attribute",); search_fields=("value","slug")
class AdminClaimViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=ClaimAdminSerializer; queryset=Claim.objects.all(); filterset_fields=("active",); search_fields=("name",)
class AdminProductClaimViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=ProductClaimAdminSerializer; queryset=ProductClaim.objects.select_related("product","claim","reviewed_by").all(); filterset_fields=("product","claim","is_verified","active")
class AdminBeautyProfileViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=BeautyProfileAdminSerializer; queryset=ProductBeautyProfile.objects.prefetch_related("skin_types","hair_types","concerns","ingredients").all(); filterset_fields=("product",)

class AdminSkinTypeViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=SkinTypeAdminSerializer; queryset=SkinType.objects.all().order_by("name"); search_fields=("name","slug")
class AdminHairTypeViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=HairTypeAdminSerializer; queryset=HairType.objects.all().order_by("name"); search_fields=("name","slug")
class AdminConcernViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=ConcernAdminSerializer; queryset=Concern.objects.all().order_by("name"); search_fields=("name","slug","concern_type"); filterset_fields=("concern_type",)
class AdminIngredientViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=IngredientAdminSerializer; queryset=Ingredient.objects.all().order_by("name"); search_fields=("name","slug","description")
