"""OAuth 2.0 Authorization Code Flow with PKCE for Business Central.

Implements secure user-delegated authentication:
- PKCE (Proof Key for Code Exchange) for security
- Refresh token management
- Encrypted token storage
- Auto-refresh on expiration

This is the recommended flow for interactive applications where
a user needs to grant access to their Business Central data.
"""

import base64
import hashlib
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class OAuthState(str, Enum):
    """OAuth flow states."""
    PENDING = "pending"      # Flow started, waiting for callback
    COMPLETED = "completed"  # Tokens obtained
    FAILED = "failed"        # Flow failed
    EXPIRED = "expired"      # Flow timed out


@dataclass
class PKCEChallenge:
    """PKCE code verifier and challenge."""
    verifier: str       # Random string, kept secret
    challenge: str      # SHA256 hash of verifier
    method: str = "S256"
    
    @classmethod
    def generate(cls) -> "PKCEChallenge":
        """Generate a new PKCE challenge.
        
        Uses 64 random bytes (86 chars base64url) as recommended.
        """
        # Generate random verifier (43-128 chars as per RFC 7636)
        verifier_bytes = secrets.token_bytes(64)
        verifier = base64.urlsafe_b64encode(verifier_bytes).decode('utf-8').rstrip('=')
        
        # Create S256 challenge
        challenge_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(challenge_hash).decode('utf-8').rstrip('=')
        
        return cls(verifier=verifier, challenge=challenge)


@dataclass
class OAuthFlowSession:
    """Tracks an in-progress OAuth flow.
    
    Stored server-side to validate callbacks and prevent CSRF.
    """
    session_id: str         # Random ID for this flow
    tenant_id: str          # Azure AD tenant
    pkce: PKCEChallenge     # PKCE challenge/verifier
    state: str              # CSRF protection token
    redirect_uri: str       # Callback URL
    scopes: List[str]       # Requested scopes
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: OAuthState = OAuthState.PENDING
    error: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Flow expires after 10 minutes."""
        return datetime.utcnow() > (self.created_at + timedelta(minutes=10))


@dataclass
class BCOAuthConfig:
    """Configuration for OAuth Authorization Code flow.
    
    Unlike BCAuthConfig (client credentials), this doesn't need client_secret
    when using PKCE flow (recommended for public clients).
    """
    client_id: str
    tenant_id: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=lambda: [
        "https://api.businesscentral.dynamics.com/.default",
        "offline_access",  # Required for refresh tokens
    ])
    authority_url: str = "https://login.microsoftonline.com"
    
    # Optional: For confidential clients (web apps with backend)
    client_secret: Optional[str] = None
    
    @property
    def authorize_endpoint(self) -> str:
        return f"{self.authority_url}/{self.tenant_id}/oauth2/v2.0/authorize"
    
    @property
    def token_endpoint(self) -> str:
        return f"{self.authority_url}/{self.tenant_id}/oauth2/v2.0/token"


@dataclass
class OAuthTokens:
    """OAuth tokens with expiration tracking."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    obtained_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def expires_at(self) -> datetime:
        return self.obtained_at + timedelta(seconds=self.expires_in)
    
    @property
    def is_expired(self) -> bool:
        """Check if access token expired (5 min buffer)."""
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))
    
    @property
    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "obtained_at": self.obtained_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthTokens":
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope", ""),
            obtained_at=datetime.fromisoformat(data["obtained_at"]) if "obtained_at" in data else datetime.utcnow(),
        )


class BCOAuthProvider:
    """OAuth 2.0 Authorization Code flow with PKCE for Business Central.
    
    Provides secure user-delegated authentication without needing to
    store client secrets on the client side.
    
    Flow:
    1. Admin clicks "Connect Business Central"
    2. start_auth_flow() generates PKCE and returns auth URL
    3. User completes Microsoft login
    4. Microsoft redirects to callback with auth code
    5. complete_auth_flow() exchanges code for tokens
    6. Tokens stored encrypted, auto-refreshed as needed
    
    Usage:
        config = BCOAuthConfig(
            client_id="your-app-id",
            tenant_id="customer-tenant-id",
            redirect_uri="https://yourapp/api/auth/bc/callback"
        )
        provider = BCOAuthProvider(config)
        
        # Step 1: Start flow
        auth_url, session = provider.start_auth_flow()
        # Redirect user to auth_url
        
        # Step 2: Handle callback (after user logs in)
        tokens = await provider.complete_auth_flow(session, auth_code)
        
        # Step 3: Use tokens (auto-refreshes)
        header = await provider.get_authorization_header(tenant_id)
    """
    
    def __init__(
        self,
        config: BCOAuthConfig,
        token_encryption: Optional["TokenEncryption"] = None,
        token_store: Optional["TokenStore"] = None,
    ):
        """Initialize OAuth provider.
        
        Args:
            config: OAuth configuration
            token_encryption: Encryption for tokens at rest
            token_store: Storage backend for tokens
        """
        self.config = config
        self._encryption = token_encryption
        self._store = token_store
        
        # In-progress auth flows (session_id -> OAuthFlowSession)
        self._pending_flows: Dict[str, OAuthFlowSession] = {}
        
        # In-memory token cache (for when no store configured)
        self._tokens: Dict[str, OAuthTokens] = {}
    
    def start_auth_flow(
        self,
        tenant_id: Optional[str] = None,
        additional_scopes: Optional[List[str]] = None,
    ) -> Tuple[str, OAuthFlowSession]:
        """Start an OAuth authorization flow.
        
        Args:
            tenant_id: Override tenant (for multi-tenant apps)
            additional_scopes: Extra scopes beyond default
            
        Returns:
            Tuple of (authorization_url, session)
            The session should be stored server-side until callback
        """
        # Generate PKCE challenge
        pkce = PKCEChallenge.generate()
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Session ID
        session_id = secrets.token_urlsafe(16)
        
        # Build scopes
        scopes = list(self.config.scopes)
        if additional_scopes:
            scopes.extend(additional_scopes)
        
        # Create session
        use_tenant = tenant_id or self.config.tenant_id
        session = OAuthFlowSession(
            session_id=session_id,
            tenant_id=use_tenant,
            pkce=pkce,
            state=state,
            redirect_uri=self.config.redirect_uri,
            scopes=scopes,
        )
        
        # Store session
        self._pending_flows[session_id] = session
        
        # Build authorization URL
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": pkce.method,
        }
        
        # Use tenant-specific endpoint if provided
        base_url = self.config.authority_url
        auth_endpoint = f"{base_url}/{use_tenant}/oauth2/v2.0/authorize"
        auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
        
        return auth_url, session
    
    def get_pending_flow(self, session_id: str) -> Optional[OAuthFlowSession]:
        """Get a pending flow by session ID."""
        session = self._pending_flows.get(session_id)
        if session and session.is_expired:
            session.status = OAuthState.EXPIRED
            del self._pending_flows[session_id]
            return None
        return session
    
    def validate_callback(
        self,
        session_id: str,
        state: str,
        code: Optional[str],
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ) -> Tuple[bool, Optional[OAuthFlowSession], Optional[str]]:
        """Validate OAuth callback parameters.
        
        Args:
            session_id: Session ID from cookie/state
            state: State parameter from callback
            code: Authorization code (if successful)
            error: Error code (if failed)
            error_description: Error description
            
        Returns:
            Tuple of (is_valid, session, error_message)
        """
        session = self.get_pending_flow(session_id)
        
        if not session:
            return False, None, "Invalid or expired session"
        
        if session.state != state:
            session.status = OAuthState.FAILED
            session.error = "State mismatch - possible CSRF attack"
            return False, session, session.error
        
        if error:
            session.status = OAuthState.FAILED
            session.error = f"{error}: {error_description or 'Unknown error'}"
            return False, session, session.error
        
        if not code:
            session.status = OAuthState.FAILED
            session.error = "No authorization code received"
            return False, session, session.error
        
        return True, session, None
    
    async def complete_auth_flow(
        self,
        session: OAuthFlowSession,
        authorization_code: str,
    ) -> Optional[OAuthTokens]:
        """Exchange authorization code for tokens.
        
        Args:
            session: The OAuth flow session
            authorization_code: Code from callback
            
        Returns:
            OAuthTokens if successful, None otherwise
        """
        try:
            import aiohttp
            
            # Build token request
            data = {
                "client_id": self.config.client_id,
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": session.redirect_uri,
                "code_verifier": session.pkce.verifier,
            }
            
            # Add client secret if configured (confidential client)
            if self.config.client_secret:
                data["client_secret"] = self.config.client_secret
            
            # Token endpoint for the tenant
            token_endpoint = f"{self.config.authority_url}/{session.tenant_id}/oauth2/v2.0/token"
            
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        session.status = OAuthState.FAILED
                        session.error = f"Token exchange failed: {error_text}"
                        return None
                    
                    token_data = await response.json()
            
            tokens = OAuthTokens(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope", ""),
            )
            
            # Store tokens
            await self._store_tokens(session.tenant_id, tokens)
            
            # Mark flow complete
            session.status = OAuthState.COMPLETED
            
            # Clean up pending flow
            if session.session_id in self._pending_flows:
                del self._pending_flows[session.session_id]
            
            return tokens
            
        except ImportError:
            raise ImportError("aiohttp required: pip install aiohttp")
        except Exception as e:
            session.status = OAuthState.FAILED
            session.error = str(e)
            return None
    
    async def refresh_tokens(self, tenant_id: str) -> Optional[OAuthTokens]:
        """Refresh expired access token using refresh token.
        
        Args:
            tenant_id: Tenant to refresh tokens for
            
        Returns:
            New tokens if successful
        """
        tokens = await self._get_stored_tokens(tenant_id)
        
        if not tokens or not tokens.refresh_token:
            return None
        
        try:
            import aiohttp
            
            data = {
                "client_id": self.config.client_id,
                "grant_type": "refresh_token",
                "refresh_token": tokens.refresh_token,
                "scope": tokens.scope or " ".join(self.config.scopes),
            }
            
            if self.config.client_secret:
                data["client_secret"] = self.config.client_secret
            
            token_endpoint = f"{self.config.authority_url}/{tenant_id}/oauth2/v2.0/token"
            
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Token refresh failed: {error_text}")
                        # Refresh token might be expired - need re-auth
                        return None
                    
                    token_data = await response.json()
            
            new_tokens = OAuthTokens(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                # New refresh token (if provided) or keep old one
                refresh_token=token_data.get("refresh_token", tokens.refresh_token),
                scope=token_data.get("scope", tokens.scope),
            )
            
            await self._store_tokens(tenant_id, new_tokens)
            return new_tokens
            
        except Exception as e:
            print(f"Token refresh error: {e}")
            return None
    
    async def get_valid_token(self, tenant_id: str) -> Optional[OAuthTokens]:
        """Get a valid (non-expired) token, refreshing if needed.
        
        Args:
            tenant_id: Tenant to get token for
            
        Returns:
            Valid tokens, or None if not available/refresh failed
        """
        tokens = await self._get_stored_tokens(tenant_id)
        
        if not tokens:
            return None
        
        if not tokens.is_expired:
            return tokens
        
        # Token expired, try refresh
        return await self.refresh_tokens(tenant_id)
    
    async def get_authorization_header(self, tenant_id: str) -> Optional[str]:
        """Get Authorization header for API calls.
        
        Automatically refreshes if expired.
        
        Returns:
            "Bearer <token>" or None if not authenticated
        """
        tokens = await self.get_valid_token(tenant_id)
        return tokens.authorization_header if tokens else None
    
    async def disconnect(self, tenant_id: str) -> bool:
        """Disconnect a tenant (revoke/delete tokens).
        
        Args:
            tenant_id: Tenant to disconnect
            
        Returns:
            True if tokens were deleted
        """
        # Remove from cache
        if tenant_id in self._tokens:
            del self._tokens[tenant_id]
        
        # Remove from store
        if self._store:
            return await self._store.delete(tenant_id, "business_central")
        
        return True
    
    async def is_connected(self, tenant_id: str) -> bool:
        """Check if a tenant has valid (or refreshable) tokens."""
        tokens = await self.get_valid_token(tenant_id)
        return tokens is not None
    
    # =========================================================================
    # Token Storage (encrypted)
    # =========================================================================
    
    async def _store_tokens(self, tenant_id: str, tokens: OAuthTokens) -> None:
        """Store tokens (encrypted if encryption configured)."""
        # Always cache in memory
        self._tokens[tenant_id] = tokens
        
        if self._store and self._encryption:
            from core.security.token_store import StoredToken
            
            # Encrypt token data
            encrypted = self._encryption.encrypt(
                tokens.to_dict(),
                tenant_id=tenant_id,
            )
            
            stored = StoredToken(
                tenant_id=tenant_id,
                connector_type="business_central",
                encrypted_token=encrypted,
                scopes=tokens.scope.split(" ") if tokens.scope else [],
                expires_at=tokens.expires_at,
            )
            
            await self._store.store(stored)
    
    async def _get_stored_tokens(self, tenant_id: str) -> Optional[OAuthTokens]:
        """Retrieve tokens (decrypting if needed)."""
        # Check memory cache first
        if tenant_id in self._tokens:
            return self._tokens[tenant_id]
        
        # Check persistent store
        if self._store and self._encryption:
            stored = await self._store.get(tenant_id, "business_central")
            
            if stored:
                try:
                    token_data = self._encryption.decrypt(stored.encrypted_token)
                    tokens = OAuthTokens.from_dict(token_data)
                    
                    # Cache in memory
                    self._tokens[tenant_id] = tokens
                    return tokens
                except Exception as e:
                    print(f"Failed to decrypt tokens: {e}")
                    return None
        
        return None
