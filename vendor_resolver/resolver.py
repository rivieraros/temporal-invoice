"""Vendor Resolver Algorithm.

This module implements the core vendor resolution algorithm that:
1. Checks alias table for exact match (fast path)
2. Falls back to fuzzy matching against vendor list
3. Considers address similarity for disambiguation

The algorithm is designed for minimal user input:
- First resolution requires confirmation
- Confirmation creates an alias for instant future matches
"""

import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from vendor_resolver.models import (
    VendorAlias,
    VendorCandidate,
    VendorResolution,
    MatchType,
    MatchingConfig,
    DEFAULT_MATCHING_CONFIG,
)
from vendor_resolver.normalize import (
    normalize_vendor_name,
    tokenize_name,
    calculate_token_similarity,
    calculate_string_similarity,
    extract_address_components,
    calculate_address_similarity,
)
from vendor_resolver.db import (
    DEFAULT_DB_PATH,
    get_vendor_alias,
    add_vendor_alias,
)


class VendorListProvider(Protocol):
    """Protocol for vendor list retrieval.
    
    The BC connector should implement this to provide vendor lists.
    """
    
    async def list_vendors(
        self,
        entity_id: str,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get list of vendors for an entity.
        
        Expected dict fields:
        - id: Vendor GUID
        - code/number: Vendor code
        - name: Display name
        - address_line1, city, state (optional)
        """
        ...


class VendorResolver:
    """Resolves extracted vendor/feedlot names to BC vendors.
    
    Resolution strategy:
    1. Normalize the extracted name
    2. Check alias table for exact match (instant return)
    3. Fuzzy match against vendor list from BC
    4. Score candidates and decide auto-match or return options
    
    Example:
        resolver = VendorResolver()
        
        # With vendor list
        vendors = await bc_connector.list_vendors(entity_id)
        resolution = await resolver.resolve_vendor(
            extracted_name="BOVINA FEEDERS INC. DBA BF2",
            entity_id="bf2-company-guid-001",
            vendor_list=vendors,
        )
        
        if resolution.is_auto_matched:
            print(f"Matched to: {resolution.vendor_name}")
        else:
            print(f"Choose from {len(resolution.candidates)} candidates")
    """
    
    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        config: MatchingConfig = DEFAULT_MATCHING_CONFIG,
        customer_id: str = "default",
    ):
        """Initialize the resolver.
        
        Args:
            db_path: Path to SQLite database
            config: Matching configuration
            customer_id: Customer/tenant identifier
        """
        self.db_path = db_path
        self.config = config
        self.customer_id = customer_id
    
    async def resolve_vendor(
        self,
        extracted_name: str,
        entity_id: str,
        vendor_list: Optional[List[Dict[str, Any]]] = None,
        extracted_address: Optional[Dict[str, str]] = None,
    ) -> VendorResolution:
        """Resolve a vendor name to a BC vendor.
        
        Args:
            extracted_name: Vendor/feedlot name from extraction
            entity_id: BC company GUID
            vendor_list: List of vendor dicts from BC (required for fuzzy matching)
            extracted_address: Optional address from extraction
                Expected keys: address_line1, city, state
        
        Returns:
            VendorResolution with match result or candidates
        """
        start_time = time.time()
        
        # Step 1: Normalize the extracted name
        normalized = normalize_vendor_name(extracted_name)
        
        if not normalized:
            return VendorResolution(
                is_auto_matched=False,
                extracted_name=extracted_name,
                normalized_name="",
                entity_id=entity_id,
                match_type=MatchType.NO_MATCH,
                reasons=["Empty or invalid vendor name"],
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        
        # Step 2: Check alias table for exact match (fast path)
        alias = get_vendor_alias(
            normalized_name=normalized,
            entity_id=entity_id,
            customer_id=self.customer_id,
            db_path=self.db_path,
        )
        
        if alias:
            return VendorResolution(
                is_auto_matched=True,
                vendor_id=alias.vendor_id,
                vendor_number=alias.vendor_number,
                vendor_name=alias.vendor_name,
                match_type=MatchType.EXACT_ALIAS,
                confidence_score=Decimal("100"),
                extracted_name=extracted_name,
                normalized_name=normalized,
                entity_id=entity_id,
                requires_confirmation=False,
                reasons=[f"Exact alias match: '{normalized}'"],
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        
        # Step 3: Fuzzy match against vendor list
        if not vendor_list:
            return VendorResolution(
                is_auto_matched=False,
                extracted_name=extracted_name,
                normalized_name=normalized,
                entity_id=entity_id,
                match_type=MatchType.NO_MATCH,
                reasons=["No alias found and no vendor list provided for fuzzy matching"],
                requires_confirmation=True,
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        
        # Score all vendors
        candidates = self._score_vendors(
            normalized_name=normalized,
            vendor_list=vendor_list,
            extracted_address=extracted_address,
        )
        
        # Filter by threshold and sort
        candidates = [c for c in candidates if c.score >= self.config.fuzzy_match_threshold]
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # Limit to max candidates
        candidates = candidates[:self.config.max_candidates]
        
        # Step 4: Decide auto-match or return candidates
        if candidates and candidates[0].score >= self.config.auto_match_threshold:
            best = candidates[0]
            return VendorResolution(
                is_auto_matched=True,
                vendor_id=best.vendor_id,
                vendor_number=best.vendor_number,
                vendor_name=best.vendor_name,
                match_type=best.match_type,
                confidence_score=best.score,
                candidates=candidates,
                extracted_name=extracted_name,
                normalized_name=normalized,
                entity_id=entity_id,
                requires_confirmation=False,
                reasons=[f"High confidence match ({float(best.score):.1f}%)"] + best.reasons,
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        elif candidates:
            return VendorResolution(
                is_auto_matched=False,
                candidates=candidates,
                extracted_name=extracted_name,
                normalized_name=normalized,
                entity_id=entity_id,
                confidence_score=candidates[0].score if candidates else Decimal("0"),
                match_type=MatchType.FUZZY_NAME,
                requires_confirmation=True,
                reasons=[f"Best match score ({float(candidates[0].score):.1f}%) below auto-match threshold"],
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        else:
            return VendorResolution(
                is_auto_matched=False,
                candidates=[],
                extracted_name=extracted_name,
                normalized_name=normalized,
                entity_id=entity_id,
                match_type=MatchType.NO_MATCH,
                requires_confirmation=True,
                reasons=[f"No vendors matched above threshold ({float(self.config.fuzzy_match_threshold):.0f}%)"],
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def _score_vendors(
        self,
        normalized_name: str,
        vendor_list: List[Dict[str, Any]],
        extracted_address: Optional[Dict[str, str]] = None,
    ) -> List[VendorCandidate]:
        """Score all vendors against the extracted name.
        
        Args:
            normalized_name: Normalized extracted name
            vendor_list: List of vendor dicts from BC
            extracted_address: Optional extracted address
            
        Returns:
            List of scored VendorCandidate objects
        """
        extracted_tokens = tokenize_name(normalized_name)
        
        # Extract address components if available
        extracted_addr = None
        if extracted_address:
            extracted_addr = extract_address_components(
                address_line1=extracted_address.get("address_line1"),
                city=extracted_address.get("city"),
                state=extracted_address.get("state"),
            )
        
        candidates = []
        
        for vendor in vendor_list:
            # Get vendor name
            vendor_name = vendor.get("name") or vendor.get("displayName") or ""
            if not vendor_name:
                continue
            
            # Normalize vendor name
            vendor_normalized = normalize_vendor_name(vendor_name)
            vendor_tokens = tokenize_name(vendor_normalized)
            
            # Calculate name similarity
            token_sim = calculate_token_similarity(extracted_tokens, vendor_tokens)
            string_sim = calculate_string_similarity(normalized_name, vendor_normalized)
            
            # Combine name scores (token matching is more reliable)
            name_score = Decimal(str(token_sim * 0.7 + string_sim * 0.3)) * 100
            
            # Calculate address similarity if we have both
            address_score = Decimal("0")
            if extracted_addr:
                vendor_addr = extract_address_components(
                    address_line1=vendor.get("address_line1") or vendor.get("addressLine1"),
                    city=vendor.get("city"),
                    state=vendor.get("state"),
                )
                addr_sim = calculate_address_similarity(extracted_addr, vendor_addr)
                address_score = Decimal(str(addr_sim)) * 100
            
            # Calculate total score
            name_weight = float(self.config.name_weight) / 100
            address_weight = float(self.config.address_weight) / 100
            
            if extracted_addr and address_score > 0:
                total_score = (name_score * Decimal(str(name_weight)) + 
                              address_score * Decimal(str(address_weight)))
            else:
                # If no address to compare, use name score only
                total_score = name_score
            
            # Build reasons
            reasons = []
            if token_sim >= 0.8:
                reasons.append(f"Strong name match: '{vendor_normalized}'")
            elif token_sim >= 0.6:
                reasons.append(f"Moderate name match: '{vendor_normalized}'")
            
            if address_score >= Decimal("50"):
                reasons.append("Address matches")
            
            # Determine match type
            match_type = MatchType.FUZZY_NAME
            if address_score >= Decimal("50") and name_score >= Decimal("60"):
                match_type = MatchType.ADDRESS_MATCH
            
            candidate = VendorCandidate(
                vendor_id=vendor.get("id") or vendor.get("systemId") or "",
                vendor_number=vendor.get("code") or vendor.get("number") or vendor.get("no") or "",
                vendor_name=vendor_name,
                address_line1=vendor.get("address_line1") or vendor.get("addressLine1"),
                city=vendor.get("city"),
                state=vendor.get("state"),
                score=total_score,
                name_score=name_score,
                address_score=address_score,
                match_type=match_type,
                matched_tokens=list(set(extracted_tokens) & set(vendor_tokens)),
                reasons=reasons,
            )
            
            candidates.append(candidate)
        
        return candidates
    
    async def confirm_match(
        self,
        extracted_name: str,
        entity_id: str,
        vendor_id: str,
        vendor_number: str,
        vendor_name: str,
        created_by: str = "user",
    ) -> VendorAlias:
        """Confirm a vendor match and create an alias for future lookups.
        
        This is called when a user confirms a candidate match.
        The alias is stored so future invoices with the same extracted name
        resolve instantly.
        
        Args:
            extracted_name: Original extracted name
            entity_id: BC company GUID
            vendor_id: BC vendor GUID
            vendor_number: Vendor code
            vendor_name: Vendor display name
            created_by: Who confirmed this match
            
        Returns:
            Created VendorAlias
        """
        normalized = normalize_vendor_name(extracted_name)
        
        alias = VendorAlias(
            customer_id=self.customer_id,
            entity_id=entity_id,
            alias_normalized=normalized,
            alias_original=extracted_name,
            vendor_id=vendor_id,
            vendor_number=vendor_number,
            vendor_name=vendor_name,
            created_by=created_by,
        )
        
        return add_vendor_alias(alias, db_path=self.db_path)
    
    def explain_resolution(self, resolution: VendorResolution) -> str:
        """Generate a human-readable explanation of the resolution.
        
        Args:
            resolution: The resolution to explain
            
        Returns:
            Formatted explanation string
        """
        lines = ["=" * 60, "Vendor Resolution Explanation", "=" * 60]
        
        lines.append(f"Extracted name: '{resolution.extracted_name}'")
        lines.append(f"Normalized: '{resolution.normalized_name}'")
        lines.append(f"Entity ID: {resolution.entity_id}")
        lines.append("")
        
        if resolution.is_auto_matched:
            lines.append(f"✓ AUTO-MATCHED to: {resolution.vendor_name}")
            lines.append(f"  Vendor ID: {resolution.vendor_id}")
            lines.append(f"  Vendor #: {resolution.vendor_number}")
            lines.append(f"  Match type: {resolution.match_type.value}")
            lines.append(f"  Confidence: {float(resolution.confidence_score):.1f}%")
        else:
            lines.append("⚠ REQUIRES CONFIRMATION")
            lines.append(f"  Match type: {resolution.match_type.value}")
        
        lines.append("")
        lines.append("Reasons:")
        for reason in resolution.reasons:
            lines.append(f"  • {reason}")
        
        if resolution.candidates:
            lines.append("")
            lines.append("Candidates:")
            for i, c in enumerate(resolution.candidates):
                lines.append(f"  {i+1}. {c.vendor_name} ({c.vendor_number})")
                lines.append(f"     Score: {float(c.score):.1f}%")
                lines.append(f"     Name: {float(c.name_score):.1f}%, Address: {float(c.address_score):.1f}%")
                if c.matched_tokens:
                    lines.append(f"     Matched tokens: {', '.join(c.matched_tokens)}")
        
        lines.append("")
        lines.append(f"Resolved in {resolution.resolution_time_ms}ms")
        lines.append("=" * 60)
        
        return "\n".join(lines)
