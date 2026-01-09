"""Business Central Authentication Provider.

Handles OAuth2 authentication with Azure AD for Business Central API access.
Supports both client credentials (app-to-app) and authorization code flow.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import json
from pathlib import Path


@dataclass
class BCAuthConfig:
    """Configuration for BC authentication.
    
    Attributes:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID
        client_secret: Client secret (for client credentials flow)
        scope: OAuth2 scope (typically the BC API scope)
        environment: BC environment name
    """
    tenant_id: str
    client_id: str
    client_secret: str
    environment: str = "production"
    scope: str = "https://api.businesscentral.dynamics.com/.default"
    authority_url: str = "https://login.microsoftonline.com"
    
    @property
    def token_endpoint(self) -> str:
        """Get the OAuth2 token endpoint."""
        return f"{self.authority_url}/{self.tenant_id}/oauth2/v2.0/token"


@dataclass
class BCToken:
    """OAuth2 access token with expiration tracking."""
    access_token: str
    token_type: str
    expires_in: int
    obtained_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def expires_at(self) -> datetime:
        """When the token expires."""
        return self.obtained_at + timedelta(seconds=self.expires_in)
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5-minute buffer)."""
        buffer = timedelta(minutes=5)
        return datetime.utcnow() >= (self.expires_at - buffer)
    
    @property
    def authorization_header(self) -> str:
        """Get the Authorization header value."""
        return f"{self.token_type} {self.access_token}"


class BCAuthProvider:
    """Authentication provider for Business Central.
    
    Handles:
    - Client credentials OAuth2 flow
    - Token caching and refresh
    - Token persistence (optional)
    
    Usage:
        config = BCAuthConfig(
            tenant_id="your-tenant-id",
            client_id="your-client-id",
            client_secret="your-secret"
        )
        auth = BCAuthProvider(config)
        await auth.authenticate()
        token = auth.get_token()
    """
    
    def __init__(self, config: BCAuthConfig, cache_path: Optional[Path] = None):
        """Initialize auth provider.
        
        Args:
            config: Authentication configuration
            cache_path: Optional path to cache token to disk
        """
        self.config = config
        self.cache_path = cache_path
        self._token: Optional[BCToken] = None
        self._http_client = None  # Will be set to aiohttp session
    
    async def authenticate(self) -> bool:
        """Authenticate with Azure AD and obtain access token.
        
        Returns:
            True if authentication successful
        """
        # Try to load cached token first
        if self._try_load_cached_token():
            return True
        
        # Need to fetch new token
        return await self._fetch_token()
    
    async def _fetch_token(self) -> bool:
        """Fetch a new access token from Azure AD."""
        try:
            import aiohttp
            
            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": self.config.scope,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Token request failed: {response.status} - {error_text}")
                    
                    token_data = await response.json()
                    
                    self._token = BCToken(
                        access_token=token_data["access_token"],
                        token_type=token_data.get("token_type", "Bearer"),
                        expires_in=token_data.get("expires_in", 3600),
                    )
                    
                    # Cache the token
                    self._save_token_to_cache()
                    
                    return True
                    
        except ImportError:
            raise ImportError("aiohttp is required for BC authentication. Install with: pip install aiohttp")
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def get_token(self) -> Optional[BCToken]:
        """Get the current access token.
        
        Returns:
            BCToken if authenticated, None otherwise
        """
        if self._token and not self._token.is_expired:
            return self._token
        return None
    
    def get_authorization_header(self) -> Optional[str]:
        """Get the Authorization header value.
        
        Returns:
            Header value like "Bearer <token>" if authenticated
        """
        token = self.get_token()
        return token.authorization_header if token else None
    
    async def ensure_valid_token(self) -> bool:
        """Ensure we have a valid (non-expired) token.
        
        Refreshes the token if expired.
        
        Returns:
            True if we have a valid token
        """
        if self._token and not self._token.is_expired:
            return True
        return await self._fetch_token()
    
    def _try_load_cached_token(self) -> bool:
        """Try to load a cached token from disk."""
        if not self.cache_path or not self.cache_path.exists():
            return False
        
        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)
            
            token = BCToken(
                access_token=data["access_token"],
                token_type=data["token_type"],
                expires_in=data["expires_in"],
                obtained_at=datetime.fromisoformat(data["obtained_at"]),
            )
            
            if not token.is_expired:
                self._token = token
                return True
            
            return False
            
        except Exception as e:
            print(f"Failed to load cached token: {e}")
            return False
    
    def _save_token_to_cache(self) -> None:
        """Save current token to disk cache."""
        if not self.cache_path or not self._token:
            return
        
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "access_token": self._token.access_token,
                "token_type": self._token.token_type,
                "expires_in": self._token.expires_in,
                "obtained_at": self._token.obtained_at.isoformat(),
            }
            
            with open(self.cache_path, "w") as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Failed to cache token: {e}")
    
    def clear_cache(self) -> None:
        """Clear the token cache."""
        self._token = None
        if self.cache_path and self.cache_path.exists():
            self.cache_path.unlink()
