from django.conf import settings
import logging
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError,APIException
from .serializers import LoginSerializer, UserSerializer, AddressSerializer, SetPasswordSerializer, jwt_for_user
from .models import Address,User,OTPChallenge
from .services import create_otp,verify_otp
from .utils import normalize_phone,PhoneFormatError
from .throttles import AuthRateThrottle,OTPRateThrottle
from apps.common.responses import success
from apps.notifications.services import queue_notification
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)

class LoginView(APIView):
    permission_classes = [AllowAny]; throttle_classes=[AuthRateThrottle]
    def post(self, request):
        s=LoginSerializer(data=request.data); s.is_valid(raise_exception=True); user=s.validated_data["user"]
        return success({"user": UserSerializer(user).data, "auth": jwt_for_user(user)}, "Login successful.")
class OTPRequestView(APIView):
    permission_classes=[AllowAny]; throttle_classes=[OTPRateThrottle]
    def post(self,request):
        try: phone=normalize_phone(request.data.get("phone",""))
        except PhoneFormatError as exc: raise ValidationError({"phone":str(exc)})
        if not phone or not User.objects.filter(phone=phone,is_active=True).exists(): raise ValidationError({"phone":"Active account not found."})
        code=create_otp(phone,OTPChallenge.Purpose.LOGIN)
        try:
            queue_notification(channel=Notification.Channel.SMS,body=f"Your verification code is {code}",metadata={"phone":phone,"purpose":"login"})
        except Exception as exc:
            # Development must remain usable without Redis/Celery/SMS. The OTP
            # is returned below when DEBUG=True. Production fails explicitly.
            logger.exception("Unable to queue OTP SMS for %s", phone)
            if not settings.DEBUG:
                error = APIException("OTP delivery service is temporarily unavailable.")
                error.status_code = 503
                error.default_code = "OTP_DELIVERY_UNAVAILABLE"
                raise error from exc
        data={"expires_in":300};
        if settings.DEBUG:data["development_otp"]=code
        return success(data,"OTP sent.")
class OTPVerifyView(APIView):
    permission_classes=[AllowAny]; throttle_classes=[AuthRateThrottle]
    def post(self,request):
        try: phone=normalize_phone(request.data.get("phone",""))
        except PhoneFormatError as exc: raise ValidationError({"phone":str(exc)})
        code=str(request.data.get("code","")).strip()
        if len(code) != 6 or not code.isdigit():
            raise ValidationError({"otp":"Enter the 6-digit OTP code."})
        user=verify_otp(phone,code,OTPChallenge.Purpose.LOGIN)
        if not user: raise ValidationError({"phone":"Account not found."})
        return success({"user":UserSerializer(user).data,"auth":jwt_for_user(user)},"Phone verified.")
class GoogleProviderNotConfigured(APIException):
    status_code=501; default_code="GOOGLE_PROVIDER_NOT_CONFIGURED"; default_detail="Configure a GoogleIdentityVerifier provider adapter before using Google sign-in."
class GoogleAuthExtensionView(APIView):
    permission_classes=[AllowAny]
    def post(self,request): raise GoogleProviderNotConfigured()
class MeView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request): return success(UserSerializer(request.user).data)
class SetPasswordView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        s=SetPasswordSerializer(data=request.data,context={"request":request}); s.is_valid(raise_exception=True); request.user.set_password(s.validated_data["new_password"]); request.user.save(update_fields=["password"]); return success(message="Password updated.")
class AddressViewSet(ModelViewSet):
    permission_classes=[IsAuthenticated]; serializer_class=AddressSerializer
    def get_queryset(self): return Address.objects.filter(user=self.request.user).order_by("-is_default","-id")
    def perform_create(self, serializer): serializer.save(user=self.request.user)
