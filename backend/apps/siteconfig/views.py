from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import SiteBrandingSettings
from .serializers import SiteBrandingSettingsSerializer

ManagementAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER)


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
