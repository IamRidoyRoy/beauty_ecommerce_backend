import hashlib, hmac, secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import OTPChallenge, User
from .utils import normalize_phone

def _hash(code): return hmac.new(settings.SECRET_KEY.encode(),code.encode(),hashlib.sha256).hexdigest()
def create_otp(phone, purpose=OTPChallenge.Purpose.LOGIN):
    phone = normalize_phone(phone)
    code=f"{secrets.randbelow(1000000):06d}"
    # Invalidate older unconsumed challenges so only the latest OTP works.
    OTPChallenge.objects.filter(phone=phone, purpose=purpose, consumed_at__isnull=True).update(consumed_at=timezone.now())
    OTPChallenge.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=_hash(code),
        debug_code=code if settings.DEBUG else "",
        expires_at=timezone.now()+timedelta(minutes=5),
    )
    return code  # caller sends via SMS adapter; do not expose in production API
@transaction.atomic
def verify_otp(phone, code, purpose=OTPChallenge.Purpose.LOGIN):
    phone = normalize_phone(phone)
    code = str(code or "").strip()
    challenge=(OTPChallenge.objects.select_for_update().filter(phone=phone,purpose=purpose,consumed_at__isnull=True,expires_at__gt=timezone.now()).order_by("-id").first())
    if not challenge: raise ValidationError({"otp":"OTP expired or not found."})
    challenge.attempts += 1
    if challenge.attempts > 5 or not hmac.compare_digest(challenge.code_hash, _hash(code)):
        challenge.save(update_fields=["attempts"]); raise ValidationError({"otp":"Invalid OTP."})
    challenge.consumed_at=timezone.now(); challenge.save(update_fields=["attempts","consumed_at"])
    user=User.objects.filter(phone=phone,is_active=True).first()
    if user: user.phone_verified=True; user.save(update_fields=["phone_verified"])
    return user
