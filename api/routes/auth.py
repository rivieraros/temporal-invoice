"""OAuth Authentication Routes for Business Central.

Implements:
- GET /api/auth/bc/start - Initiates OAuth flow
- GET /api/auth/bc/callback - Handles OAuth callback
- GET /api/auth/bc/status - Check connection status
- POST /api/auth/bc/disconnect - Revoke connection

Security:
- PKCE for secure authorization code exchange
- Encrypted token storage
- Short-lived access tokens with refresh
- Per-tenant isolation
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

# Configuration from environment
BC_CLIENT_ID = os.getenv("BC_CLIENT_ID", "")
BC_CLIENT_SECRET = os.getenv("BC_CLIENT_SECRET", "")  # Optional for PKCE
BC_REDIRECT_URI = os.getenv("BC_REDIRECT_URI", "http://localhost:8000/api/auth/bc/callback")
BC_DEFAULT_TENANT = os.getenv("BC_DEFAULT_TENANT", "common")  # "common" for multi-tenant
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")

router = APIRouter(prefix="/auth/bc")


# =============================================================================
# Lazy initialization of OAuth components
# =============================================================================

_oauth_provider = None
_token_encryption = None
_token_store = None


def _get_oauth_provider():
    """Get or create OAuth provider (lazy init)."""
    global _oauth_provider, _token_encryption, _token_store
    
    if _oauth_provider is None:
        from connectors.business_central.bc_oauth import BCOAuthConfig, BCOAuthProvider
        
        # Initialize encryption if key provided
        if TOKEN_ENCRYPTION_KEY:
            from core.security import TokenEncryption, FileTokenStore
            _token_encryption = TokenEncryption(TOKEN_ENCRYPTION_KEY)
            _token_store = FileTokenStore(".tokens")
        
        config = BCOAuthConfig(
            client_id=BC_CLIENT_ID,
            tenant_id=BC_DEFAULT_TENANT,
            redirect_uri=BC_REDIRECT_URI,
            client_secret=BC_CLIENT_SECRET or None,
            scopes=[
                "https://api.businesscentral.dynamics.com/.default",
                "offline_access",
            ],
        )
        
        _oauth_provider = BCOAuthProvider(
            config,
            token_encryption=_token_encryption,
            token_store=_token_store,
        )
    
    return _oauth_provider


# =============================================================================
# Request/Response Models
# =============================================================================

class StartAuthRequest(BaseModel):
    """Request to start OAuth flow."""
    tenant_id: Optional[str] = Field(
        None,
        description="Azure AD tenant ID. Leave empty for common endpoint."
    )
    return_url: Optional[str] = Field(
        None,
        description="URL to redirect after successful auth"
    )


class StartAuthResponse(BaseModel):
    """Response with authorization URL."""
    auth_url: str
    session_id: str
    expires_in: int = 600  # 10 minutes


class AuthStatusResponse(BaseModel):
    """OAuth connection status."""
    connected: bool
    tenant_id: Optional[str] = None
    expires_at: Optional[str] = None
    scopes: list = []


class DisconnectResponse(BaseModel):
    """Response after disconnect."""
    success: bool
    message: str


# =============================================================================
# Session Management (server-side)
# =============================================================================

# In-memory session storage (use Redis in production)
_auth_sessions: Dict[str, Dict[str, Any]] = {}


def _store_session(session_id: str, data: Dict[str, Any], ttl_seconds: int = 600) -> None:
    """Store session data server-side."""
    _auth_sessions[session_id] = {
        **data,
        "expires_at": datetime.utcnow() + timedelta(seconds=ttl_seconds),
    }


def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session data."""
    session = _auth_sessions.get(session_id)
    if not session:
        return None
    if datetime.utcnow() > session.get("expires_at", datetime.min):
        del _auth_sessions[session_id]
        return None
    return session


def _clear_session(session_id: str) -> None:
    """Clear session data."""
    if session_id in _auth_sessions:
        del _auth_sessions[session_id]


# =============================================================================
# Routes
# =============================================================================

@router.get("/start", response_model=StartAuthResponse)
async def start_bc_auth(
    tenant_id: Optional[str] = Query(None, description="Azure AD tenant ID"),
    return_url: Optional[str] = Query(None, description="Return URL after auth"),
):
    """Start Business Central OAuth flow.
    
    Redirects the user to Microsoft login. After authentication,
    Microsoft will redirect back to /api/auth/bc/callback.
    
    **Usage:**
    1. Call this endpoint (or redirect user to it)
    2. User logs in to Microsoft
    3. User grants consent
    4. Microsoft redirects to callback
    5. Tokens are stored securely
    
    **For browser redirect:**
    Simply redirect to: GET /api/auth/bc/start?tenant_id=...
    
    **For API usage:**
    Get the auth_url and redirect manually.
    """
    if not BC_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="BC_CLIENT_ID not configured. Set environment variable."
        )
    
    provider = _get_oauth_provider()
    
    # Start OAuth flow
    auth_url, session = provider.start_auth_flow(
        tenant_id=tenant_id,
    )
    
    # Store session server-side
    _store_session(session.session_id, {
        "tenant_id": session.tenant_id,
        "return_url": return_url,
        "state": session.state,
    })
    
    return StartAuthResponse(
        auth_url=auth_url,
        session_id=session.session_id,
    )


@router.get("/start-redirect")
async def start_bc_auth_redirect(
    tenant_id: Optional[str] = Query(None),
    return_url: Optional[str] = Query(None),
):
    """Start OAuth and immediately redirect to Microsoft login.
    
    Use this endpoint when you want automatic redirect (e.g., from a button).
    """
    result = await start_bc_auth(tenant_id, return_url)
    return RedirectResponse(url=result.auth_url, status_code=302)


@router.get("/callback")
async def bc_auth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    session_state: Optional[str] = Query(None),  # Azure includes this
):
    """OAuth callback endpoint.
    
    Microsoft redirects here after user authentication.
    This endpoint exchanges the authorization code for tokens.
    
    **Note:** This is called by Microsoft, not by your frontend directly.
    """
    provider = _get_oauth_provider()
    
    # Handle error from Microsoft
    if error:
        error_msg = f"{error}: {error_description or 'Unknown error'}"
        # Could redirect to error page
        raise HTTPException(status_code=400, detail=error_msg)
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    # Find the session that matches this state
    session = None
    session_id = None
    for sid, sdata in list(_auth_sessions.items()):
        if sdata.get("state") == state:
            session = sdata
            session_id = sid
            break
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired session. Please start the auth flow again."
        )
    
    # Get the OAuth flow session from provider
    flow_session = provider.get_pending_flow(session_id)
    if not flow_session:
        raise HTTPException(
            status_code=400,
            detail="Auth flow expired. Please try again."
        )
    
    # Validate callback
    is_valid, flow_session, error_msg = provider.validate_callback(
        session_id=session_id,
        state=state,
        code=code,
        error=error,
        error_description=error_description,
    )
    
    if not is_valid:
        _clear_session(session_id)
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Exchange code for tokens
    tokens = await provider.complete_auth_flow(flow_session, code)
    
    if not tokens:
        _clear_session(session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Token exchange failed: {flow_session.error}"
        )
    
    # Clean up session
    return_url = session.get("return_url")
    _clear_session(session_id)
    
    # Redirect to return URL or show success
    if return_url:
        # Add success indicator
        separator = "&" if "?" in return_url else "?"
        return RedirectResponse(
            url=f"{return_url}{separator}bc_connected=true",
            status_code=302
        )
    
    # No return URL - show success message
    return {
        "success": True,
        "message": "Business Central connected successfully!",
        "tenant_id": flow_session.tenant_id,
        "expires_at": tokens.expires_at.isoformat(),
    }


@router.get("/status", response_model=AuthStatusResponse)
async def get_bc_auth_status(
    tenant_id: str = Query(..., description="Tenant ID to check"),
):
    """Check if Business Central is connected for a tenant.
    
    Returns connection status and token expiration info.
    """
    provider = _get_oauth_provider()
    
    tokens = await provider.get_valid_token(tenant_id)
    
    if not tokens:
        return AuthStatusResponse(connected=False)
    
    return AuthStatusResponse(
        connected=True,
        tenant_id=tenant_id,
        expires_at=tokens.expires_at.isoformat(),
        scopes=tokens.scope.split(" ") if tokens.scope else [],
    )


@router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect_bc(
    tenant_id: str = Query(..., description="Tenant ID to disconnect"),
):
    """Disconnect Business Central for a tenant.
    
    Removes stored tokens. User will need to re-authenticate.
    """
    provider = _get_oauth_provider()
    
    success = await provider.disconnect(tenant_id)
    
    return DisconnectResponse(
        success=success,
        message="Disconnected from Business Central" if success else "Not connected",
    )


@router.get("/refresh")
async def refresh_bc_token(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """Manually refresh the access token.
    
    Normally tokens are auto-refreshed, but this can be used
    to proactively refresh before a long operation.
    """
    provider = _get_oauth_provider()
    
    tokens = await provider.refresh_tokens(tenant_id)
    
    if not tokens:
        raise HTTPException(
            status_code=401,
            detail="Token refresh failed. Re-authentication required."
        )
    
    return {
        "success": True,
        "expires_at": tokens.expires_at.isoformat(),
    }


# =============================================================================
# Configuration Endpoint (for setup verification)
# =============================================================================

@router.get("/config")
async def get_bc_auth_config():
    """Get OAuth configuration (non-sensitive).
    
    Useful for verifying setup and debugging.
    """
    return {
        "client_id_configured": bool(BC_CLIENT_ID),
        "client_secret_configured": bool(BC_CLIENT_SECRET),
        "redirect_uri": BC_REDIRECT_URI,
        "default_tenant": BC_DEFAULT_TENANT,
        "encryption_configured": bool(TOKEN_ENCRYPTION_KEY),
        "scopes": [
            "https://api.businesscentral.dynamics.com/.default",
            "offline_access",
        ],
    }
