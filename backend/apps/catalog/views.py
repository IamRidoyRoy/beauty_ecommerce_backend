from django.db.models import Q
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
    filterset_fields=("product_type","status","brand","category","featured","new_arrival","bestseller","trending"); search_fields=("name","sku","barcode")
    @action(detail=True,methods=["post"])
    def publish(self,request,pk=None): return success(ProductAdminSerializer(publish_product(product=self.get_object())).data,"Product published.")
class AdminVariantViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=VariantAdminSerializer
    queryset=ProductVariant.objects.select_related("product").prefetch_related("attributes__attribute").order_by("-id"); filterset_fields=("product","is_active"); search_fields=("sku","barcode","product__name")
class AdminCategoryViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=CategorySerializer; queryset=Category.objects.select_related("parent").all()
class AdminBrandViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=BrandSerializer; queryset=Brand.objects.all()
class AdminImageViewSet(ModelViewSet):
    permission_classes=[CatalogAdmin]; serializer_class=ProductImageSerializer; parser_classes=[MultiPartParser,FormParser]; queryset=ProductImage.objects.select_related("product","variant").all()
    @action(detail=True,methods=["post"],url_path="set-primary")
    def primary(self,request,pk=None): return success(ProductImageSerializer(set_primary_image(image=self.get_object()),context={"request":request}).data,"Primary image updated.")
    @action(detail=False,methods=["post"],url_path="reorder")
    def reorder(self,request):
        product=Product.objects.get(pk=request.data.get("product")); reorder_images(product=product,ordered_ids=request.data.get("image_ids",[])); return success(message="Images reordered.")
class BulkImageUploadView(APIView):
    permission_classes=[CatalogAdmin]; parser_classes=[MultiPartParser,FormParser]
    def post(self,request):
        product=Product.objects.get(pk=request.data.get("product")); variant_id=request.data.get("variant") or None
        variant=ProductVariant.objects.filter(pk=variant_id,product=product).first() if variant_id else None
        if variant_id and not variant: raise ValidationError({"variant":"Invalid variant for product."})
        files=request.FILES.getlist("images"); created=[]
        for i,f in enumerate(files): created.append(ProductImage.objects.create(product=product,variant=variant,image=f,order=i))
        return success(ProductImageSerializer(created,many=True,context={"request":request}).data,"Images uploaded.",201)

class AdminAttributeViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=AttributeAdminSerializer; queryset=Attribute.objects.all().order_by("display_order","name")
class AdminAttributeValueViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=AttributeValueAdminSerializer; queryset=AttributeValue.objects.select_related("attribute").all(); filterset_fields=("attribute",); search_fields=("value","slug")
class AdminClaimViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=ClaimAdminSerializer; queryset=Claim.objects.all(); filterset_fields=("active",); search_fields=("name",)
class AdminProductClaimViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=ProductClaimAdminSerializer; queryset=ProductClaim.objects.select_related("product","claim","reviewed_by").all(); filterset_fields=("product","claim","is_verified","active")
class AdminBeautyProfileViewSet(ModelViewSet): permission_classes=[CatalogAdmin]; serializer_class=BeautyProfileAdminSerializer; queryset=ProductBeautyProfile.objects.prefetch_related("skin_types","hair_types","concerns","ingredients").all(); filterset_fields=("product",)
