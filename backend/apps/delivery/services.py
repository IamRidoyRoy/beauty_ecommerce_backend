from dataclasses import dataclass
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import City, DeliveryModule, Thana


@dataclass(frozen=True)
class DeliveryQuote:
    district: City
    thana: Thana
    module: DeliveryModule
    charge: Decimal


def resolve_delivery_quote(*, district: City, thana: Thana) -> DeliveryQuote:
    if thana.city_id != district.id:
        raise ValidationError({"thana": "Selected thana does not belong to the selected district."})
    if not district.active:
        raise ValidationError({"district": "Selected district is not available for delivery."})
    if not thana.active:
        raise ValidationError({"thana": "Selected thana is not available for delivery."})

    module = thana.delivery_module or district.delivery_module
    if not module.active:
        raise ValidationError({"delivery": "Delivery is currently unavailable for this area."})

    return DeliveryQuote(
        district=district,
        thana=thana,
        module=module,
        charge=module.charge,
    )
