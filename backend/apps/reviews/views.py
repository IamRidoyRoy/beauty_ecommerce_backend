from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from apps.orders.models import OrderItem

from .models import Review, ReviewImage
from .serializers import (
    AdminReviewSerializer,
    EligibleReviewItemSerializer,
    REVIEWABLE_ORDER_STATUSES,
    ReviewImageSerializer,
    ReviewSerializer,
)
from .services import create_review


class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ("product", "rating", "verified_purchase")
    ordering_fields = ("created_at", "rating")

    def get_permissions(self):
        if self.action in {"mine", "eligible", "upload_images", "create"}:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        base = Review.objects.select_related(
            "user", "product", "order_item__order"
        ).prefetch_related("images", "product__images")

        if self.action in {"mine", "upload_images"} and self.request.user.is_authenticated:
            return base.filter(user=self.request.user).order_by("-created_at")

        return base.filter(status=Review.Status.APPROVED).order_by("-created_at")

    def perform_create(self, serializer):
        obj = create_review(
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = obj

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return success(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], url_path="eligible")
    def eligible(self, request):
        queryset = (
            OrderItem.objects.filter(
                order__user=request.user,
                order__order_status__in=REVIEWABLE_ORDER_STATUSES,
            )
            .exclude(reviews__user=request.user)
            .select_related("order", "product", "variant")
            .prefetch_related("product__images")
            .order_by("-order__created_at", "id")
        )
        page = self.paginate_queryset(queryset)
        context = self.get_serializer_context()
        if page is not None:
            serializer = EligibleReviewItemSerializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)
        serializer = EligibleReviewItemSerializer(queryset, many=True, context=context)
        return success(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="images",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_images(self, request, pk=None):
        review = self.get_object()
        files = request.FILES.getlist("images")
        if not files:
            raise ValidationError({"images": "Upload at least one image."})
        if review.images.count() + len(files) > 5:
            raise ValidationError({"images": "Maximum 5 review images."})
        start = review.images.count()
        created = [
            ReviewImage.objects.create(review=review, image=file, order=start + index)
            for index, file in enumerate(files)
        ]
        return success(
            ReviewImageSerializer(created, many=True, context={"request": request}).data,
            "Review images uploaded.",
            201,
        )


ReviewAdmin = role_permission(
    UserRole.SUPER_ADMIN,
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.CUSTOMER_SUPPORT,
)


class AdminReviewViewSet(ModelViewSet):
    permission_classes = [ReviewAdmin]
    serializer_class = AdminReviewSerializer
    queryset = (
        Review.objects.select_related("user", "product", "order_item", "order_item__order")
        .prefetch_related("images", "product__images")
        .order_by("-id")
    )
    filterset_fields = ("status", "verified_purchase", "product", "rating")
    search_fields = (
        "product__name",
        "product__sku",
        "order_item__sku_snapshot",
        "order_item__order__order_number",
        "user__full_name",
        "user__phone",
        "title",
        "comment",
    )
    ordering_fields = ("created_at", "rating")
