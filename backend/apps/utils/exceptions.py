from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

class BusinessLogicException(Exception):
    """
    Base class for domain-specific errors (e.g., StockOut, PromoInvalid).
    These are expected operational errors, not 500s.
    """
    def __init__(self, message, code="invalid_request"):
        self.message = message
        self.code = code
        super().__init__(message)

def custom_exception_handler(exc, context):
    """
    Custom DRF Exception Handler.
    Maps BusinessLogicException to HTTP 400 with a standard error structure.
    """
    response = exception_handler(exc, context)

    if isinstance(exc, BusinessLogicException):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "type": "BusinessLogicError"
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if response is not None and response.status_code == 400:
        if "error" not in response.data:
            response.data = {
                "error": {
                    "code": "validation_error",
                    "details": response.data
                }
            }

    return response