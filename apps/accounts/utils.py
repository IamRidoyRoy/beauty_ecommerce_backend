import re
class PhoneFormatError(ValueError): pass

def normalize_phone(value):
    value=(value or "").strip()
    if not value:return value
    plus=value.startswith("+"); digits=re.sub(r"\D","",value)
    if digits.startswith("880") and len(digits)==13: return f"+{digits}"
    if digits.startswith("01") and len(digits)==11: return f"+88{digits}"
    if plus and 8 <= len(digits) <= 15: return f"+{digits}"
    if 8 <= len(digits) <= 15: return digits
    raise PhoneFormatError("Enter a valid phone number.")
