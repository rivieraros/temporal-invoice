"""Artifact storage abstraction for JSON and binary data.

Provides a consistent interface for storing and retrieving artifacts
with integrity verification and metadata tracking.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models.refs import DataReference


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


def list_artifacts(directory: Path, extension: str = "*.json") -> list[DataReference]:
    """List all artifacts in a directory.
    
    Args:
        directory: Directory to search
        extension: File pattern to match (default "*.json")
        
    Returns:
        List of DataReference objects for all matching artifacts
    """
    if not directory.exists():
        return []
    
    refs = []
    for path in directory.glob(extension):
        if path.is_file():
            json_bytes = path.read_bytes()
            refs.append(DataReference(
                storage_uri=str(path.absolute()),
                content_hash=_compute_sha256(json_bytes),
                content_type="application/json",
                size_bytes=len(json_bytes),
                stored_at=datetime.fromtimestamp(path.stat().st_mtime),
            ))
    
    return sorted(refs, key=lambda r: r.stored_at, reverse=True)


def delete_artifact(ref: DataReference) -> bool:
    """Delete an artifact by reference.
    
    Args:
        ref: DataReference pointing to the artifact
        
    Returns:
        True if deleted, False if not found
    """
    path = Path(ref.storage_uri)
    if path.exists():
        path.unlink()
        return True
    return False


def artifact_exists(ref: DataReference) -> bool:
    """Check if an artifact exists.
    
    Args:
        ref: DataReference to check
        
    Returns:
        True if artifact exists at the referenced path
    """
    return Path(ref.storage_uri).exists()
