from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from apps.common.admin_utils import register_app_models
from .models import OTPChallenge, User


class UserCreationAdminForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = (
            "phone",
            "email",
            "full_name",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserChangeAdminForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text="Passwords are stored as hashes. Use the Change password action/link to replace it.",
    )

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial.get("password")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm

    list_display = (
        "id",
        "phone",
        "full_name",
        "email",
        "role",
        "phone_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = (
        "role",
        "phone_verified",
        "email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("phone", "email", "full_name")
    ordering = ("-id",)
    readonly_fields = ("uuid", "last_login", "created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("phone", "email", "password")}),
        ("Personal information", {"fields": ("uuid", "full_name", "gender", "date_of_birth")}),
        ("Verification", {"fields": ("phone_verified", "email_verified")}),
        (
            "Role & permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone",
                    "email",
                    "full_name",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "phone",
        "purpose",
        "debug_code",
        "attempts",
        "expires_at",
        "consumed_at",
        "created_at",
    )
    list_filter = ("purpose", "consumed_at")
    search_fields = ("phone",)
    ordering = ("-id",)
    readonly_fields = (
        "phone",
        "purpose",
        "debug_code",
        "code_hash",
        "attempts",
        "expires_at",
        "consumed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        # OTPs must be created through the service so hashing/expiry rules are
        # always applied.
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Address remains available through the generic admin registration.
register_app_models("accounts", exclude={User, OTPChallenge})
