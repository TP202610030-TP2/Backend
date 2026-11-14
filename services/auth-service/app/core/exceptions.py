from fastapi import HTTPException


class InvalidCredentialsError(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail={"errorCode": "AUTH_001", "message": "Invalid credentials"})


class AccountLockedError(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail={"errorCode": "AUTH_003", "message": "Account is locked or disabled"})


class RateLimitExceededError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=429,
            detail={"errorCode": "AUTH_004", "message": "Too many failed login attempts. Try again in 15 minutes"},
        )


class TokenInvalidError(HTTPException):
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(status_code=401, detail={"errorCode": "AUTH_001", "message": message})


class UserNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=404,
            detail={"errorCode": "RESOURCE_001", "message": "No user is registered with this email"},
        )


class EmailDeliveryError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=503,
            detail={
                "errorCode": "SYSTEM_005",
                "message": "Recovery email could not be sent, please try again later",
            },
        )
