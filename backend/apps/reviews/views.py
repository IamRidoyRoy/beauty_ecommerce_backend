from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.exceptions import ValidationError
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import Review,ReviewImage
from .serializers import ReviewSerializer,AdminReviewSerializer,ReviewImageSerializer
from .services import create_review
class ReviewViewSet(ModelViewSet):
    serializer_class=ReviewSerializer; http_method_names=["get","post","head","options"]; filterset_fields=("product","rating","verified_purchase"); ordering_fields=("created_at","rating")
    def get_permissions(self): return [AllowAny()] if self.request.method=="GET" else [IsAuthenticated()]
    def get_queryset(self):
        if self.action=="upload_images" and self.request.user.is_authenticated:
            return Review.objects.filter(user=self.request.user).select_related("user","product","order_item__order").prefetch_related("images")
        return Review.objects.filter(status=Review.Status.APPROVED).select_related("user","product","order_item__order").prefetch_related("images").order_by("-created_at")
    def perform_create(self,serializer):
        obj=create_review(user=self.request.user,validated_data=serializer.validated_data); serializer.instance=obj
    @action(detail=True,methods=["post"],url_path="images",parser_classes=[MultiPartParser,FormParser])
    def upload_images(self,request,pk=None):
        review=self.get_object(); files=request.FILES.getlist("images")
        if not files: raise ValidationError({"images":"Upload at least one image."})
        if review.images.count()+len(files)>5: raise ValidationError({"images":"Maximum 5 review images."})
        created=[ReviewImage.objects.create(review=review,image=f,order=review.images.count()+i) for i,f in enumerate(files)]
        return success(ReviewImageSerializer(created,many=True,context={"request":request}).data,"Review images uploaded.",201)
ReviewAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.CUSTOMER_SUPPORT)
class AdminReviewViewSet(ModelViewSet): permission_classes=[ReviewAdmin]; serializer_class=AdminReviewSerializer; queryset=Review.objects.select_related("user","product","order_item").prefetch_related("images").order_by("-id"); filterset_fields=("status","verified_purchase","product","rating")
