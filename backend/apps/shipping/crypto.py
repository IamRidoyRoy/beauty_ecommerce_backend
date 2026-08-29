from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CourierConfigEncryptionError(ValueError):
    pass


def _fernet() -> Fernet:
    configured = str(getattr(settings, "COURIER_CONFIG_ENCRYPTION_KEY", "") or "").strip()
    if configured:
        try:
            return Fernet(configured.encode())
        except Exception:
            key = base64.urlsafe_b64encode(hashlib.sha256(configured.encode()).digest())
            return Fernet(key)
    fallback = str(getattr(settings, "PAYMENT_CONFIG_ENCRYPTION_KEY", "") or getattr(settings, "SECRET_KEY", ""))
    key = base64.urlsafe_b64encode(hashlib.sha256(fallback.encode()).digest())
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
        parsed = json.loads(raw.decode())
        return parsed if isinstance(parsed, dict) else {}
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise CourierConfigEncryptionError("Unable to decrypt courier configuration.") from exc
