import time
from django.core.cache import cache

# Match SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] (15 minutes = 900 seconds)
JWT_REVOCATION_TIMEOUT = 900


def revoke_token_jti(jti: str, timeout: int = JWT_REVOCATION_TIMEOUT) -> None:
    """Blacklist an individual access token's JTI in cache for its remaining lifetime."""
    if jti:
        cache.set(f"jwt_revoked:jti:{jti}", True, timeout=timeout)


def is_jti_revoked(jti: str) -> bool:
    """Return True if the specific access token JTI has been blacklisted."""
    if not jti:
        return False
    return bool(cache.get(f"jwt_revoked:jti:{jti}"))


def revoke_user_tokens(user_id, timeout: int = JWT_REVOCATION_TIMEOUT) -> None:
    """Record revocation timestamp for a user so all previously issued access tokens are invalid."""
    if user_id:
        cache.set(f"jwt_revoked:user:{user_id}", time.time(), timeout=timeout)


def is_user_revoked(user_id, iat: int | float) -> bool:
    """Return True if the token was issued at or before the user's latest logout revocation timestamp."""
    if not user_id or not iat:
        return False
    revoked_at = cache.get(f"jwt_revoked:user:{user_id}")
    if revoked_at is None:
        return False
    return float(iat) <= float(revoked_at)
