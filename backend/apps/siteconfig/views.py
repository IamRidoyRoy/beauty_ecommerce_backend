from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import AnnouncementItem, HomepageBanner, SiteBrandingSettings
from .serializers import AnnouncementItemSerializer, HomepageBannerSerializer, SiteBrandingSettingsSerializer

ManagementAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER)
MarketingAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.MARKETING_MANAGER)


def serialize(settings, request):
    return SiteBrandingSettingsSerializer(settings, context={"request": request}).data


class SiteBrandingPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return success(serialize(SiteBrandingSettings.current(), request))


class SiteBrandingAdminView(APIView):
    permission_classes = [ManagementAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return success(serialize(SiteBrandingSettings.current(), request))

    def patch(self, request):
        obj = SiteBrandingSettings.current()
        serializer = SiteBrandingSettingsSerializer(
            obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(serialize(obj, request), "Branding and theme updated.")


class HomepageBannerPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        banners = HomepageBanner.objects.filter(active=True).order_by("slot")
        return success(HomepageBannerSerializer(banners, many=True, context={"request": request}).data)


class HomepageBannerAdminViewSet(ModelViewSet):
    permission_classes = [MarketingAdmin]
    serializer_class = HomepageBannerSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = HomepageBanner.objects.all().order_by("slot")
    pagination_class = None
    http_method_names = ["get", "patch", "head", "options"]


class AnnouncementItemPublicView(APIView):
    permission_classes=[AllowAny]
    def get(self,request):
        rows=AnnouncementItem.objects.filter(active=True).order_by("order","id")
        return success(AnnouncementItemSerializer(rows,many=True,context={"request":request}).data)


class AnnouncementItemAdminViewSet(ModelViewSet):
    permission_classes=[MarketingAdmin]
    serializer_class=AnnouncementItemSerializer
    queryset=AnnouncementItem.objects.all().order_by("order","id")
    pagination_class=None
    http_method_names=["get","post","patch","delete","head","options"]
