import time
import secrets
import jwt
from fastapi import Request, HTTPException, status, Header
from src.utils.config import settings

COOKIE_NAME = "admin_session"
TOKEN_EXPIRATION_SECONDS = 60 * 60 * 24 * 7  # 7 days

def verify_admin_password(password: str) -> bool:
    """Verifies the provided admin password using constant-time comparison."""
    expected_password = settings.effective_admin_password
    if not expected_password:
        return False
    return secrets.compare_digest(password.strip(), expected_password.strip())

def create_admin_token() -> str:
    """Creates a signed JWT admin session token."""
    now = int(time.time())
    payload = {
        "sub": "admin",
        "iat": now,
        "exp": now + TOKEN_EXPIRATION_SECONDS
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_admin_token(token: str) -> dict:
    """Decodes and validates an admin JWT token."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])

def get_token_from_request(request: Request, authorization: str = None) -> str | None:
    """Extracts the admin token from cookie or Authorization header."""
    # 1. Check HTTP-only cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # 2. Check Authorization header
    auth_header = authorization or request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None

async def get_current_admin(
    request: Request,
    x_secret_token: str = Header(None, alias="X-Secret-Token")
) -> dict:
    """
    FastAPI dependency requiring valid admin authentication.
    Accepts JWT cookie, Bearer token, or X-Secret-Token matching settings.SECRET_TOKEN.
    """
    # Allow system secret token (e.g. for external monitoring/scripts)
    if x_secret_token and settings.SECRET_TOKEN and secrets.compare_digest(x_secret_token, settings.SECRET_TOKEN):
        return {"sub": "admin", "type": "secret_token"}

    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )

    try:
        payload = decode_admin_token(token)
        if payload.get("sub") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token subject"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin session token"
        )

async def get_current_admin_optional(request: Request) -> dict | None:
    """
    Optional admin check that returns decoded token payload or None without throwing 401.
    Used for page routers that display a login form if unauthenticated.
    """
    token = get_token_from_request(request)
    if not token:
        return None
    try:
        payload = decode_admin_token(token)
        if payload.get("sub") == "admin":
            return payload
    except Exception:
        pass
    return None
