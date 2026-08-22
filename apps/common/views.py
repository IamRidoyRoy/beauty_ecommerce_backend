from django.conf import settings
from django.core.management import call_command
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from apps.accounts.models import UserRole
from .models import AnalyticsEvent
from .permissions import role_permission
from .responses import success
class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta: model=AnalyticsEvent; fields=("event_type","session_token","cart_token","product_id_ref","metadata")
class AnalyticsEventView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        s=AnalyticsEventSerializer(data=request.data); s.is_valid(raise_exception=True); s.save(user=request.user if request.user.is_authenticated else None); return success(message="Event recorded.",status=201)
DemoAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN)
class DemoImportView(APIView):
    permission_classes=[DemoAdmin]
    def post(self,request):
        if not settings.DEBUG: raise PermissionDenied("Demo import is available only in development.")
        call_command("seed_full_demo")
        return success(message="Demo data imported.")
