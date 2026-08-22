from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from apps.common.models import TimeStampedModel, UUIDModel
from .utils import normalize_phone

class UserRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    PRODUCT_MANAGER = "product_manager", "Product Manager"
    INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"
    ORDER_MANAGER = "order_manager", "Order Manager"
    CUSTOMER_SUPPORT = "customer_support", "Customer Support"
    MARKETING_MANAGER = "marketing_manager", "Marketing Manager"
    FINANCE_MANAGER = "finance_manager", "Finance Manager"
    CUSTOMER = "customer", "Customer"

class UserManager(BaseUserManager):
    def create_user(self, phone=None, email=None, password=None, **extra_fields):
        if not phone and not email:
            raise ValueError("Phone or email is required.")
        email = self.normalize_email(email) if email else None
        phone = normalize_phone(phone) if phone else None
        user = self.model(phone=phone, email=email, **extra_fields)
        if password: user.set_password(password)
        else: user.set_unusable_password()
        user.save(using=self._db)
        return user
    def create_superuser(self, phone=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True); extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True); extra_fields.setdefault("role", UserRole.SUPER_ADMIN)
        return self.create_user(phone=phone, email=email, password=password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    class Gender(models.TextChoices):
        MALE="male","Male"; FEMALE="female","Female"; OTHER="other","Other"; UNSPECIFIED="unspecified","Unspecified"
    full_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=24, unique=True, null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, default=Gender.UNSPECIFIED)
    date_of_birth = models.DateField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    role = models.CharField(max_length=32, choices=UserRole.choices, default=UserRole.CUSTOMER, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    objects = UserManager()
    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    def __str__(self): return self.phone or self.email or str(self.uuid)

class Address(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=24)
    district = models.CharField(max_length=100)
    thana = models.CharField(max_length=100)
    address = models.TextField()
    label = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    class Meta:
        indexes = [models.Index(fields=["user", "is_default"])]

class OTPChallenge(TimeStampedModel):
    class Purpose(models.TextChoices): LOGIN="login","Login"; VERIFY_PHONE="verify_phone","Verify Phone"
    phone = models.CharField(max_length=24, db_index=True)
    code_hash = models.CharField(max_length=255)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
