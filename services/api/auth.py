"""SEVER API — authentication.

Two modes, controlled by AUTH_MODE:
- "disabled" (default): every request is treated as the dev user. Used for
  local development and the pre-Cognito beta.
- "cognito": requests must carry "Authorization: Bearer <JWT>" signed by the
  Cognito user pool identified by COGNITO_REGION / COGNITO_USER_POOL_ID /
  COGNITO_APP_CLIENT_ID. Tokens are verified against Cognito's JWKS.
"""

import os
from functools import lru_cache

from fastapi import HTTPException, Request

DEV_USER = {"sub": "dev-user", "email": "dev@sever.local"}


@lru_cache(maxsize=1)
def _jwks_client():
    import jwt

    region = os.environ["COGNITO_REGION"]
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    return jwt.PyJWKClient(jwks_url)


def _verify_cognito_token(token: str) -> dict:
    import jwt

    region = os.environ["COGNITO_REGION"]
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    client_id = os.environ["COGNITO_APP_CLIENT_ID"]
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},  # access tokens carry client_id, not aud
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    if claims.get("client_id") != client_id and claims.get("aud") != client_id:
        raise HTTPException(status_code=401, detail="token not issued for this app")
    if claims.get("token_use") not in ("access", "id"):
        raise HTTPException(status_code=401, detail="wrong token type")
    return {"sub": claims["sub"], "email": claims.get("email", "")}


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: resolves the authenticated user for a request."""
    if os.environ.get("AUTH_MODE", "disabled") != "cognito":
        return DEV_USER

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return _verify_cognito_token(header.removeprefix("Bearer "))
