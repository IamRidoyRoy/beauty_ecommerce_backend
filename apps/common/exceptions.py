import logging
from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
logger=logging.getLogger(__name__)

def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        return Response({"success": False, "message": "Internal server error.", "errors": {}}, status=500)
    errors = response.data
    message = "Validation failed." if isinstance(exc, ValidationError) else str(getattr(exc, "detail", "Request failed."))
    code = getattr(exc, "default_code", None)
    response.data = {"success": False, "message": message, "errors": errors}
    if code:
        response.data["code"] = code
    return response
