"""Core storage - artifact storage abstraction."""

from core.storage.artifacts import (
    put_json,
    get_json,
    put_binary,
    get_binary,
    ArtifactStore,
)

__all__ = [
    "put_json",
    "get_json",
    "put_binary",
    "get_binary",
    "ArtifactStore",
]
