from rest_framework.exceptions import PermissionDenied


class PlanLimitReached(PermissionDenied):
    default_detail = "Plan limit reached"
    default_code = "plan_limit_reached"

    def __init__(self, limit_name, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
            
        dict_detail = {
            "code": code,
            "detail": detail,
            "limit": limit_name
        }
        super().__init__(detail=dict_detail, code=code)


from rest_framework.exceptions import APIException
from rest_framework import status

class IdempotencyConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The idempotency key was already used for another request."
    default_code = "idempotency_conflict"
    
    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
            
        dict_detail = {
            "code": code,
            "detail": detail
        }
        super().__init__(detail=dict_detail, code=code)


class PaymentAdapterError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Payment adapter checkout creation failed."
    default_code = "payment_adapter_error"
    
    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
            
        dict_detail = {
            "code": code,
            "detail": detail
        }
        super().__init__(detail=dict_detail, code=code)

