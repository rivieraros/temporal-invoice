"""Artifact storage abstraction for JSON and binary data.

Provides a consistent interface for storing and retrieving artifacts
with integrity verification and metadata tracking.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from core.models.refs import DataReference


def _compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def put_json(obj: Any, path: Path, ensure_parent: bool = True) -> DataReference:
    """Store a JSON-serializable object and return a DataReference.
    
    Args:
        obj: Object to serialize to JSON (dict, Pydantic model, etc.)
        path: Absolute file path where artifact will be stored
        ensure_parent: Create parent directories if they don't exist
        
    Returns:
        DataReference with artifact metadata for retrieval
        
    Raises:
        ValueError: If object is not JSON-serializable
    """
    if ensure_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle Pydantic models
    if hasattr(obj, "model_dump"):
        obj_dict = obj.model_dump(mode="json", by_alias=True)
    elif hasattr(obj, "dict"):
        obj_dict = obj.dict()
    else:
        obj_dict = obj
    
    # Serialize to JSON bytes
    json_str = json.dumps(obj_dict, indent=2)
    json_bytes = json_str.encode("utf-8")
    
    # Write to disk
    path.write_bytes(json_bytes)
    
    # Compute metadata
    content_hash = _compute_sha256(json_bytes)
    size_bytes = len(json_bytes)
    stored_at = datetime.utcnow()
    
    return DataReference(
        storage_uri=str(path.absolute()),
        content_hash=content_hash,
        content_type="application/json",
        size_bytes=size_bytes,
        stored_at=stored_at,
    )


def get_json(ref: DataReference, validate_hash: bool = True) -> dict:
    """Retrieve JSON artifact from a DataReference.
    
    Args:
        ref: DataReference pointing to the artifact
        validate_hash: Verify content hash matches reference (security check)
        
    Returns:
        Deserialized JSON object
        
    Raises:
        FileNotFoundError: If artifact path doesn't exist
        ValueError: If hash validation fails
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(ref.storage_uri)
    
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {ref.storage_uri}")
    
    json_bytes = path.read_bytes()
    
    # Validate hash if requested
    if validate_hash:
        actual_hash = _compute_sha256(json_bytes)
        if actual_hash != ref.content_hash:
            raise ValueError(
                f"Hash mismatch for {ref.storage_uri}: "
                f"expected {ref.content_hash}, got {actual_hash}"
            )
    
    # Deserialize
    json_str = json_bytes.decode("utf-8")
    return json.loads(json_str)


def put_binary(data: bytes, path: Path, content_type: str = "application/octet-stream", 
               ensure_parent: bool = True) -> DataReference:
    """Store binary data and return a DataReference.
    
    Args:
        data: Binary data to store
        path: Absolute file path where artifact will be stored
        content_type: MIME type of the data
        ensure_parent: Create parent directories if they don't exist
        
    Returns:
        DataReference with artifact metadata for retrieval
    """
    if ensure_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to disk
    path.write_bytes(data)
    
    # Compute metadata
    content_hash = _compute_sha256(data)
    size_bytes = len(data)
    stored_at = datetime.utcnow()
    
    return DataReference(
        storage_uri=str(path.absolute()),
        content_hash=content_hash,
        content_type=content_type,
        size_bytes=size_bytes,
        stored_at=stored_at,
    )


def get_binary(ref: DataReference, validate_hash: bool = True) -> bytes:
    """Retrieve binary artifact from a DataReference.
    
    Args:
        ref: DataReference pointing to the artifact
        validate_hash: Verify content hash matches reference
        
    Returns:
        Binary data
        
    Raises:
        FileNotFoundError: If artifact path doesn't exist
        ValueError: If hash validation fails
    """
    path = Path(ref.storage_uri)
    
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {ref.storage_uri}")
    
    data = path.read_bytes()
    
    if validate_hash:
        actual_hash = _compute_sha256(data)
        if actual_hash != ref.content_hash:
            raise ValueError(
                f"Hash mismatch for {ref.storage_uri}: "
                f"expected {ref.content_hash}, got {actual_hash}"
            )
    
    return data


class ArtifactStore:
    """Artifact store with configurable base path.
    
    Provides a convenient wrapper around the put/get functions
    with a consistent base directory.
    """
    
    def __init__(self, base_path: Union[str, Path]):
        """Initialize artifact store.
        
        Args:
            base_path: Base directory for all artifacts
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def put_json(self, obj: Any, relative_path: str) -> DataReference:
        """Store JSON artifact relative to base path."""
        path = self.base_path / relative_path
        return put_json(obj, path)
    
    def get_json(self, ref: DataReference, validate_hash: bool = True) -> dict:
        """Retrieve JSON artifact."""
        return get_json(ref, validate_hash)
    
    def put_binary(self, data: bytes, relative_path: str, 
                   content_type: str = "application/octet-stream") -> DataReference:
        """Store binary artifact relative to base path."""
        path = self.base_path / relative_path
        return put_binary(data, path, content_type)
    
    def get_binary(self, ref: DataReference, validate_hash: bool = True) -> bytes:
        """Retrieve binary artifact."""
        return get_binary(ref, validate_hash)
    
    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path to absolute path."""
        return self.base_path / relative_path
