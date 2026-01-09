"""Token encryption using AES-GCM.

Provides secure encryption for OAuth tokens at rest.
Uses AES-256-GCM for authenticated encryption.
"""

import base64
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

# Use cryptography library for proper AES-GCM
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def generate_encryption_key() -> str:
    """Generate a new 256-bit encryption key.
    
    Returns:
        Base64-encoded 32-byte key suitable for AES-256
    """
    key = secrets.token_bytes(32)
    return base64.b64encode(key).decode('utf-8')


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive an encryption key from a password using PBKDF2.
    
    Args:
        password: User-provided password or passphrase
        salt: Random salt (should be stored with encrypted data)
        
    Returns:
        32-byte derived key
    """
    if not HAS_CRYPTOGRAPHY:
        raise ImportError("cryptography package required for key derivation")
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,  # OWASP recommended minimum
    )
    return kdf.derive(password.encode('utf-8'))


@dataclass
class EncryptedToken:
    """Encrypted token with metadata."""
    ciphertext: str  # Base64-encoded encrypted data
    nonce: str       # Base64-encoded nonce/IV
    tag: str         # Base64-encoded authentication tag (included in ciphertext for GCM)
    created_at: str  # ISO timestamp
    tenant_id: str   # For tenant isolation
    key_version: int = 1  # For key rotation support
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": self.ciphertext,
            "nonce": self.nonce,
            "tag": self.tag,
            "created_at": self.created_at,
            "tenant_id": self.tenant_id,
            "key_version": self.key_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedToken":
        return cls(
            ciphertext=data["ciphertext"],
            nonce=data["nonce"],
            tag=data.get("tag", ""),  # GCM includes tag in ciphertext
            created_at=data["created_at"],
            tenant_id=data["tenant_id"],
            key_version=data.get("key_version", 1),
        )


class TokenEncryption:
    """AES-256-GCM encryption for OAuth tokens.
    
    Security properties:
    - Confidentiality: AES-256 encryption
    - Integrity: GCM authentication tag
    - Uniqueness: Random 96-bit nonce per encryption
    
    Usage:
        # Generate and store key securely (e.g., env var, KMS)
        key = generate_encryption_key()
        
        # Encrypt tokens
        enc = TokenEncryption(key)
        encrypted = enc.encrypt({"access_token": "...", "refresh_token": "..."}, tenant_id="abc")
        
        # Decrypt when needed
        tokens = enc.decrypt(encrypted)
    """
    
    def __init__(self, encryption_key: str):
        """Initialize with base64-encoded encryption key.
        
        Args:
            encryption_key: Base64-encoded 32-byte key (from generate_encryption_key())
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package required. Install with: pip install cryptography"
            )
        
        try:
            self._key = base64.b64decode(encryption_key)
            if len(self._key) != 32:
                raise ValueError("Key must be 32 bytes (256 bits)")
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
        
        self._aesgcm = AESGCM(self._key)
    
    def encrypt(
        self,
        token_data: Dict[str, Any],
        tenant_id: str,
        key_version: int = 1,
    ) -> EncryptedToken:
        """Encrypt token data.
        
        Args:
            token_data: Dictionary containing tokens (access_token, refresh_token, etc.)
            tenant_id: Tenant identifier for isolation
            key_version: Key version for rotation support
            
        Returns:
            EncryptedToken with encrypted data and metadata
        """
        # Serialize token data
        plaintext = json.dumps(token_data).encode('utf-8')
        
        # Generate random 96-bit nonce (recommended for GCM)
        nonce = os.urandom(12)
        
        # Include tenant_id as additional authenticated data (AAD)
        # This ensures tokens can only be decrypted for the correct tenant
        aad = tenant_id.encode('utf-8')
        
        # Encrypt with AES-GCM (ciphertext includes auth tag)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)
        
        return EncryptedToken(
            ciphertext=base64.b64encode(ciphertext).decode('utf-8'),
            nonce=base64.b64encode(nonce).decode('utf-8'),
            tag="",  # GCM includes tag in ciphertext
            created_at=datetime.utcnow().isoformat(),
            tenant_id=tenant_id,
            key_version=key_version,
        )
    
    def decrypt(self, encrypted: EncryptedToken) -> Dict[str, Any]:
        """Decrypt token data.
        
        Args:
            encrypted: EncryptedToken from encrypt()
            
        Returns:
            Original token data dictionary
            
        Raises:
            ValueError: If decryption fails (wrong key, tampered data, wrong tenant)
        """
        try:
            ciphertext = base64.b64decode(encrypted.ciphertext)
            nonce = base64.b64decode(encrypted.nonce)
            aad = encrypted.tenant_id.encode('utf-8')
            
            # Decrypt and verify authentication tag
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, aad)
            
            return json.loads(plaintext.decode('utf-8'))
            
        except Exception as e:
            raise ValueError(f"Token decryption failed: {e}")
    
    def rotate_key(
        self,
        encrypted: EncryptedToken,
        new_encryption: "TokenEncryption",
        new_key_version: int,
    ) -> EncryptedToken:
        """Re-encrypt token with a new key.
        
        Use this during key rotation to migrate tokens to a new key.
        
        Args:
            encrypted: Token encrypted with current key
            new_encryption: TokenEncryption instance with new key
            new_key_version: Version number for new key
            
        Returns:
            Token re-encrypted with new key
        """
        # Decrypt with old key
        token_data = self.decrypt(encrypted)
        
        # Re-encrypt with new key
        return new_encryption.encrypt(
            token_data,
            tenant_id=encrypted.tenant_id,
            key_version=new_key_version,
        )
