import logging
from django.conf import settings
from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
logger=logging.getLogger(__name__)

def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        errors = {}
        # Local development should expose enough information to debug a 500.
        # Production keeps the generic response and never leaks internals.
        if settings.DEBUG:
            errors = {"detail": str(exc), "exception": exc.__class__.__name__}
        return Response({"success": False, "message": "Internal server error.", "errors": errors}, status=500)
    errors = response.data
    message = "Validation failed." if isinstance(exc, ValidationError) else str(getattr(exc, "detail", "Request failed."))
    code = getattr(exc, "default_code", None)
    response.data = {"success": False, "message": message, "errors": errors}
    if code:
        response.data["code"] = code
    return response
