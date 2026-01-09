"""Entity Resolver Data Models.

This module defines the Pydantic models for entity resolution:
- EntityProfile: Represents a BC company with aliases and default settings
- EntityRoutingKey: Maps routing keys to entities
- EntityCandidate: A scored entity candidate
- EntityResolution: The result of entity resolution
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RoutingKeyType(str, Enum):
    """Types of routing keys for entity resolution.
    
    Each key type has different matching logic and scoring weight.
    """
    OWNER_NUMBER = "owner_number"      # Owner/customer number from invoice (strong signal)
    REMIT_STATE = "remit_state"        # State from remit-to address (medium signal)
    LOT_PREFIX = "lot_prefix"          # Lot number prefix pattern (weak signal)
    FEEDLOT_NAME = "feedlot_name"      # Feedlot name pattern (medium signal)
    VENDOR_NAME = "vendor_name"        # Vendor name for matching (strong signal)


class ConfidenceLevel(str, Enum):
    """Confidence level for a routing key match.
    
    HARD: This key definitively identifies the entity (no ambiguity)
    SOFT: This key suggests the entity but may have overlap
    """
    HARD = "hard"  # Definitive match (e.g., unique owner number)
    SOFT = "soft"  # Suggestive match (e.g., state, lot prefix)


class EntityProfile(BaseModel):
    """Profile for a BC company/entity.
    
    Contains the entity identification, aliases for fuzzy matching,
    routing rules, and default dimensions for posting.
    
    Attributes:
        customer_id: Customer tenant/subscription identifier
        entity_id: BC company ID (GUID) for API calls
        entity_name: Human-readable company name
        entity_code: Short code for the entity (for display)
        aliases: Alternative names/spellings for fuzzy matching
        routing_rules: JSON rules for complex routing logic
        default_dimensions: Default dimension values for this entity
        is_active: Whether this entity is currently active
        created_at: When this profile was created
        updated_at: When this profile was last modified
    """
    id: Optional[int] = None
    customer_id: str = Field(..., description="Customer/tenant identifier")
    entity_id: str = Field(..., description="BC company GUID for API calls")
    entity_name: str = Field(..., description="Full company name")
    entity_code: Optional[str] = Field(default=None, description="Short code (e.g., 'BF2', 'MESQ')")
    aliases: List[str] = Field(default_factory=list, description="Alternative names for matching")
    routing_rules: Dict[str, Any] = Field(default_factory=dict, description="Complex routing rules")
    default_dimensions: Dict[str, str] = Field(default_factory=dict, description="Default dimension values")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EntityRoutingKey(BaseModel):
    """A routing key that maps to an entity.
    
    Routing keys are indexed values that help identify which entity
    should process a document. Multiple keys can point to the same entity.
    
    Attributes:
        id: Database row ID
        key_type: Type of routing key (owner_number, remit_state, etc.)
        key_value: The actual value to match (e.g., "531", "TX", "20-")
        entity_id: BC company GUID this key maps to
        confidence: Whether this is a hard (definitive) or soft (suggestive) match
        priority: For tie-breaking when multiple keys match (higher = preferred)
        notes: Optional notes about this routing key
    """
    id: Optional[int] = None
    key_type: RoutingKeyType
    key_value: str = Field(..., description="Value to match against")
    entity_id: str = Field(..., description="BC company GUID")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.SOFT)
    priority: int = Field(default=100, description="Priority for tie-breaking (higher wins)")
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EntityCandidate(BaseModel):
    """A candidate entity with scoring information.
    
    Used in resolution results when automatic assignment isn't possible.
    Contains the entity profile, score, and reasons for the score.
    """
    entity: EntityProfile
    score: Decimal = Field(..., description="Total score (0-100)")
    reasons: List[str] = Field(default_factory=list, description="Why this entity was selected")
    matched_keys: List[EntityRoutingKey] = Field(default_factory=list, description="Keys that matched")
    
    # Score breakdown for transparency
    owner_number_score: Decimal = Field(default=Decimal("0"))
    vendor_existence_score: Decimal = Field(default=Decimal("0"))
    remit_state_score: Decimal = Field(default=Decimal("0"))
    lot_pattern_score: Decimal = Field(default=Decimal("0"))
    feedlot_name_score: Decimal = Field(default=Decimal("0"))
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class EntityResolution(BaseModel):
    """Result of entity resolution.
    
    If is_auto_assigned is True, the entity field contains the selected entity.
    Otherwise, candidates contains the top N possibilities for user confirmation.
    
    Attributes:
        is_auto_assigned: Whether an entity was automatically assigned
        entity: The selected entity (if auto-assigned)
        entity_id: BC company GUID of selected entity (convenience)
        candidates: Top N candidates if not auto-assigned
        resolution_method: How the entity was resolved
        confidence_score: Overall confidence in the resolution
        reasons: Explanation of the resolution
        requires_confirmation: Whether user confirmation is needed
    """
    is_auto_assigned: bool = Field(default=False)
    entity: Optional[EntityProfile] = None
    entity_id: Optional[str] = Field(default=None, description="BC company GUID if resolved")
    
    candidates: List[EntityCandidate] = Field(default_factory=list)
    
    resolution_method: str = Field(default="scoring", description="How entity was resolved")
    confidence_score: Decimal = Field(default=Decimal("0"), description="Overall confidence (0-100)")
    reasons: List[str] = Field(default_factory=list, description="Explanation of resolution")
    requires_confirmation: bool = Field(default=True)
    
    # Timing and debugging
    resolved_at: Optional[datetime] = None
    resolution_time_ms: Optional[int] = None
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# =============================================================================
# Scoring Configuration
# =============================================================================

class ScoringWeights(BaseModel):
    """Configurable weights for entity resolution scoring.
    
    These weights determine how much each signal contributes to the total score.
    Strong signals (owner_number_hard, feedlot_name) should be enough to 
    auto-assign when combined.
    
    Design: owner_number_hard (50) + feedlot_name (20) = 70 (auto-assign threshold)
    """
    owner_number_hard: Decimal = Field(default=Decimal("50"), description="Hard owner number match (definitive)")
    owner_number_soft: Decimal = Field(default=Decimal("30"), description="Soft owner number match")
    vendor_existence: Decimal = Field(default=Decimal("25"), description="Vendor exists in entity")
    remit_state_match: Decimal = Field(default=Decimal("10"), description="Remit-to state matches (often ambiguous)")
    lot_prefix_match: Decimal = Field(default=Decimal("10"), description="Lot prefix pattern match")
    feedlot_name_match: Decimal = Field(default=Decimal("20"), description="Feedlot name match (strong signal)")
    
    # Thresholds
    auto_assign_threshold: Decimal = Field(default=Decimal("70"), description="Min score for auto-assign")
    margin_threshold: Decimal = Field(default=Decimal("15"), description="Min margin over 2nd place")
    
    max_candidates: int = Field(default=3, description="Max candidates to return")


# Default scoring weights
DEFAULT_SCORING_WEIGHTS = ScoringWeights()
