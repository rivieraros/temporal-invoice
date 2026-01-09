"""Secure token storage backends.

Provides different storage backends for encrypted OAuth tokens:
- InMemoryTokenStore: For development/testing
- FileTokenStore: For single-server deployments
- (Future) DatabaseTokenStore: For production multi-server
- (Future) RedisTokenStore: For distributed caching
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.security.encryption import EncryptedToken, TokenEncryption


@dataclass
class StoredToken:
    """Token record with metadata."""
    tenant_id: str
    connector_type: str  # e.g., "business_central"
    encrypted_token: EncryptedToken
    scopes: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    user_id: Optional[str] = None  # If using delegated permissions
    
    def is_access_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if access token is expired or will expire soon.
        
        Args:
            buffer_seconds: Consider expired if within this many seconds
        """
        if not self.expires_at:
            return True
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=buffer_seconds))
    
    def is_refresh_expired(self) -> bool:
        """Check if refresh token is expired."""
        if not self.refresh_expires_at:
            return False  # Assume not expired if not set
        return datetime.utcnow() >= self.refresh_expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "connector_type": self.connector_type,
            "encrypted_token": self.encrypted_token.to_dict(),
            "scopes": self.scopes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "refresh_expires_at": self.refresh_expires_at.isoformat() if self.refresh_expires_at else None,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "user_id": self.user_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredToken":
        return cls(
            tenant_id=data["tenant_id"],
            connector_type=data["connector_type"],
            encrypted_token=EncryptedToken.from_dict(data["encrypted_token"]),
            scopes=data.get("scopes", []),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            refresh_expires_at=datetime.fromisoformat(data["refresh_expires_at"]) if data.get("refresh_expires_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            user_id=data.get("user_id"),
        )


class TokenStore(ABC):
    """Abstract base class for token storage."""
    
    @abstractmethod
    async def store(self, token: StoredToken) -> None:
        """Store an encrypted token."""
        pass
    
    @abstractmethod
    async def get(self, tenant_id: str, connector_type: str) -> Optional[StoredToken]:
        """Retrieve a stored token."""
        pass
    
    @abstractmethod
    async def delete(self, tenant_id: str, connector_type: str) -> bool:
        """Delete a stored token."""
        pass
    
    @abstractmethod
    async def list_tenants(self, connector_type: str) -> List[str]:
        """List all tenant IDs with stored tokens for a connector type."""
        pass
    
    async def update_last_used(self, tenant_id: str, connector_type: str) -> None:
        """Update the last_used_at timestamp."""
        token = await self.get(tenant_id, connector_type)
        if token:
            token.last_used_at = datetime.utcnow()
            await self.store(token)


class InMemoryTokenStore(TokenStore):
    """In-memory token storage for development/testing.
    
    WARNING: Tokens are lost on restart. Use only for development.
    """
    
    def __init__(self):
        self._tokens: Dict[str, StoredToken] = {}
        self._lock = threading.Lock()
    
    def _key(self, tenant_id: str, connector_type: str) -> str:
        return f"{connector_type}:{tenant_id}"
    
    async def store(self, token: StoredToken) -> None:
        with self._lock:
            key = self._key(token.tenant_id, token.connector_type)
            self._tokens[key] = token
    
    async def get(self, tenant_id: str, connector_type: str) -> Optional[StoredToken]:
        with self._lock:
            key = self._key(tenant_id, connector_type)
            return self._tokens.get(key)
    
    async def delete(self, tenant_id: str, connector_type: str) -> bool:
        with self._lock:
            key = self._key(tenant_id, connector_type)
            if key in self._tokens:
                del self._tokens[key]
                return True
            return False
    
    async def list_tenants(self, connector_type: str) -> List[str]:
        with self._lock:
            prefix = f"{connector_type}:"
            return [
                key.split(":", 1)[1]
                for key in self._tokens
                if key.startswith(prefix)
            ]


class FileTokenStore(TokenStore):
    """File-based token storage with encryption.
    
    Stores encrypted tokens as JSON files, one per tenant/connector pair.
    Suitable for single-server deployments.
    
    Directory structure:
        {base_path}/
            business_central/
                {tenant_id}.json
            other_connector/
                {tenant_id}.json
    """
    
    def __init__(self, base_path: str = ".tokens"):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        
        # Set restrictive permissions on token directory
        try:
            os.chmod(self._base_path, 0o700)
        except OSError:
            pass  # Windows doesn't support chmod the same way
    
    def _token_path(self, tenant_id: str, connector_type: str) -> Path:
        connector_dir = self._base_path / connector_type
        connector_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize tenant_id for filename
        safe_tenant = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant_id)
        return connector_dir / f"{safe_tenant}.json"
    
    async def store(self, token: StoredToken) -> None:
        path = self._token_path(token.tenant_id, token.connector_type)
        
        with self._lock:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(token.to_dict(), f, indent=2)
            
            # Set restrictive permissions on token file
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    
    async def get(self, tenant_id: str, connector_type: str) -> Optional[StoredToken]:
        path = self._token_path(tenant_id, connector_type)
        
        if not path.exists():
            return None
        
        with self._lock:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return StoredToken.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error reading token file: {e}")
                return None
    
    async def delete(self, tenant_id: str, connector_type: str) -> bool:
        path = self._token_path(tenant_id, connector_type)
        
        with self._lock:
            if path.exists():
                path.unlink()
                return True
            return False
    
    async def list_tenants(self, connector_type: str) -> List[str]:
        connector_dir = self._base_path / connector_type
        
        if not connector_dir.exists():
            return []
        
        tenants = []
        for path in connector_dir.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tenants.append(data.get("tenant_id", path.stem))
            except (json.JSONDecodeError, KeyError):
                continue
        
        return tenants
