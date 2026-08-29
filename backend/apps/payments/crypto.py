from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class PaymentConfigEncryptionError(ValueError):
    pass


def _fernet() -> Fernet:
    configured = str(getattr(settings, "PAYMENT_CONFIG_ENCRYPTION_KEY", "") or "").strip()
    if configured:
        try:
            return Fernet(configured.encode())
        except Exception:
            # Also accept a normal passphrase and derive a valid Fernet key.
            material = configured.encode()
    else:
        # Development/backward-compatible fallback. Production should set a
        # dedicated PAYMENT_CONFIG_ENCRYPTION_KEY so payment credentials do not
        # depend on SECRET_KEY rotation.
        material = str(settings.SECRET_KEY).encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)


def encrypt_json(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return _fernet().encrypt(payload).decode()


def decrypt_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        raw = _fernet().decrypt(value.encode())
        decoded = json.loads(raw.decode())
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise PaymentConfigEncryptionError("Unable to decrypt payment gateway configuration.") from exc
    return decoded if isinstance(decoded, dict) else {}
