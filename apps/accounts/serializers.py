from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Address
from .utils import normalize_phone,PhoneFormatError

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id","uuid","full_name","email","phone","gender","date_of_birth","email_verified","phone_verified","role")
        read_only_fields = ("uuid","email_verified","phone_verified","role")

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("id","name","phone","district","thana","address","label","is_default")
    def validate_phone(self,value):
        try: return normalize_phone(value)
        except PhoneFormatError as exc: raise serializers.ValidationError(str(exc))

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)
    def validate(self, attrs):
        ident = attrs["identifier"]
        try: phone_ident = None if "@" in ident else normalize_phone(ident)
        except PhoneFormatError: phone_ident = None
        user = (User.objects.filter(phone=phone_ident).first() if phone_ident else None) or User.objects.filter(email__iexact=ident).first()
        if not user or not user.check_password(attrs["password"]) or not user.is_active:
            raise serializers.ValidationError({"identifier": "Invalid credentials."})
        attrs["user"] = user
        return attrs

def jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}

class SetPasswordSerializer(serializers.Serializer):
    new_password=serializers.CharField(write_only=True,min_length=8)
    def validate_new_password(self,value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value,self.context.get("request").user if self.context.get("request") else None); return value
