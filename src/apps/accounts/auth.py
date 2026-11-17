from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension

from .jwt_revocation import is_jti_revoked, is_user_revoked


class FieldOpsJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication backend with server-side revocation checking.

    Rejects tokens whose individual JTI or user identity was invalidated on logout,
    resolving AUTH-074 (immediate revocation of access tokens on session termination).
    """

    def get_validated_token(self, raw_token: bytes):
        token = super().get_validated_token(raw_token)

        jti = token.get("jti")
        if jti and is_jti_revoked(jti):
            raise InvalidToken({"detail": _("Token has been revoked."), "code": "token_revoked"})

        user_id = token.get("user_id")
        iat = token.get("iat")
        if user_id and iat and is_user_revoked(user_id, iat):
            raise InvalidToken({"detail": _("Token has been revoked."), "code": "token_revoked"})

        return token


class FieldOpsJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.auth.FieldOpsJWTAuthentication"
    name = "jwtAuth"

    def get_security_requirement(self, auto_schema):
        return {"jwtAuth": []}

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
