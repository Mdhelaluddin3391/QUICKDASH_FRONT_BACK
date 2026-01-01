# apps/accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.core.cache import cache

class SecureJWTAuthentication(JWTAuthentication):
    """
    Extends JWT Authentication to support:
    1. Forceful Logout (Revocation via Redis Blocklist)
    2. Device Locking (Optional future scope)
    """
    def get_validated_token(self, raw_token):
        try:
            validated_token = super().get_validated_token(raw_token)
        except InvalidToken:
            raise InvalidToken("Token is invalid or expired")

        # Check for Revocation (Blocklist)
        jti = validated_token.get('jti')
        if jti and cache.get(f"blocklist:{jti}"):
            raise AuthenticationFailed("This session has been logged out.")
            
        return validated_token