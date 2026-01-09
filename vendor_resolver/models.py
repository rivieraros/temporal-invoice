"""Vendor Resolver Data Models.

This module defines the Pydantic models for vendor resolution:
- VendorAlias: Mapping from normalized name to vendor ID
- VendorCandidate: A scored vendor match candidate
- VendorResolution: The result of vendor resolution
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    """How the vendor was matched."""
    EXACT_ALIAS = "exact_alias"      # Matched via alias table
    FUZZY_NAME = "fuzzy_name"        # Fuzzy name match
    ADDRESS_MATCH = "address_match"  # Address helped disambiguate
    MANUAL = "manual"                # User manually selected
    NO_MATCH = "no_match"            # No match found


class VendorAlias(BaseModel):
    """Mapping from a normalized name to a vendor.
    
    Once a user confirms a vendor match, an alias is created so future
    invoices with the same extracted name auto-resolve instantly.
    
    Attributes:
        id: Database row ID
        customer_id: Customer/tenant identifier
        entity_id: BC company GUID this alias belongs to
        alias_normalized: Normalized extracted name (used for lookup)
        alias_original: Original extracted name (for reference)
        vendor_id: BC vendor GUID
        vendor_number: Human-readable vendor code (e.g., "V00010")
        vendor_name: Vendor display name (for reference)
        created_by: Who created this alias (user or system)
        created_at: When this alias was created
    """
    id: Optional[int] = None
    customer_id: str = Field(..., description="Customer/tenant identifier")
    entity_id: str = Field(..., description="BC company GUID")
    alias_normalized: str = Field(..., description="Normalized name for lookup")
    alias_original: Optional[str] = Field(default=None, description="Original extracted name")
    vendor_id: str = Field(..., description="BC vendor GUID")
    vendor_number: str = Field(..., description="Vendor code (e.g., 'V00010')")
    vendor_name: Optional[str] = Field(default=None, description="Vendor display name")
    created_by: str = Field(default="system", description="Who created this alias")
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VendorCandidate(BaseModel):
    """A candidate vendor with matching score.
    
    Used when exact alias match fails and fuzzy matching is needed.
    """
    vendor_id: str = Field(..., description="BC vendor GUID")
    vendor_number: str = Field(..., description="Vendor code")
    vendor_name: str = Field(..., description="Vendor display name")
    
    # Address info (if available)
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    
    # Scoring
    score: Decimal = Field(default=Decimal("0"), description="Match score (0-100)")
    name_score: Decimal = Field(default=Decimal("0"), description="Name similarity score")
    address_score: Decimal = Field(default=Decimal("0"), description="Address similarity score")
    
    # Match details
    match_type: MatchType = Field(default=MatchType.FUZZY_NAME)
    matched_tokens: List[str] = Field(default_factory=list, description="Tokens that matched")
    reasons: List[str] = Field(default_factory=list, description="Why this vendor matched")
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class VendorResolution(BaseModel):
    """Result of vendor resolution.
    
    If is_auto_matched is True, the vendor fields contain the matched vendor.
    Otherwise, candidates contains top N options for user confirmation.
    
    Attributes:
        is_auto_matched: Whether a vendor was automatically matched
        vendor_id: BC vendor GUID (if matched)
        vendor_number: Vendor code (if matched)
        vendor_name: Vendor name (if matched)
        match_type: How the match was made
        confidence_score: Match confidence (0-100)
        candidates: Top candidates if not auto-matched
        extracted_name: The original extracted name
        normalized_name: The normalized version used for matching
        entity_id: The entity this resolution is for
        requires_confirmation: Whether user confirmation is needed
        reasons: Explanation of the resolution
    """
    is_auto_matched: bool = Field(default=False)
    
    # Matched vendor info
    vendor_id: Optional[str] = Field(default=None, description="BC vendor GUID")
    vendor_number: Optional[str] = Field(default=None, description="Vendor code")
    vendor_name: Optional[str] = Field(default=None, description="Vendor display name")
    
    match_type: MatchType = Field(default=MatchType.NO_MATCH)
    confidence_score: Decimal = Field(default=Decimal("0"), description="Match confidence (0-100)")
    
    # Candidates for manual selection
    candidates: List[VendorCandidate] = Field(default_factory=list)
    
    # Input context
    extracted_name: str = Field(..., description="Original extracted name")
    normalized_name: str = Field(..., description="Normalized name used for matching")
    entity_id: str = Field(..., description="Entity this resolution is for")
    
    # Resolution metadata
    requires_confirmation: bool = Field(default=True)
    reasons: List[str] = Field(default_factory=list)
    resolved_at: Optional[datetime] = None
    resolution_time_ms: Optional[int] = None
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# =============================================================================
# Matching Configuration
# =============================================================================

class MatchingConfig(BaseModel):
    """Configuration for vendor matching algorithm.
    
    Controls thresholds and weights for fuzzy matching.
    """
    # Score thresholds
    auto_match_threshold: Decimal = Field(
        default=Decimal("85"), 
        description="Min score for auto-match"
    )
    fuzzy_match_threshold: Decimal = Field(
        default=Decimal("60"), 
        description="Min score to be a candidate"
    )
    
    # Weights
    name_weight: Decimal = Field(default=Decimal("80"), description="Weight for name similarity")
    address_weight: Decimal = Field(default=Decimal("20"), description="Weight for address match")
    
    # Behavior
    max_candidates: int = Field(default=3, description="Max candidates to return")
    require_state_match: bool = Field(default=False, description="Require state to match if present")


# Default matching config
DEFAULT_MATCHING_CONFIG = MatchingConfig()
