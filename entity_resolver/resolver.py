"""Entity Resolver Algorithm.

This module implements the core entity resolution algorithm that automatically
selects the correct BC company for an invoice based on multiple signals.

The algorithm scores each candidate entity based on:
1. Owner number routing key (strong signal, 25-40 points)
2. Vendor existence in entity (strong signal, 30 points)
3. Remit-to state match (medium signal, 15 points)
4. Lot number patterns (weak signal, 10 points)
5. Feedlot name match (medium signal, 15 points)

Decision logic:
- If top score >= 70 AND margin over 2nd place >= 15 → auto-assign
- Otherwise → return top 3 candidates for user confirmation
"""

import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from entity_resolver.models import (
    EntityProfile,
    EntityRoutingKey,
    RoutingKeyType,
    ConfidenceLevel,
    EntityCandidate,
    EntityResolution,
    ScoringWeights,
    DEFAULT_SCORING_WEIGHTS,
)
from entity_resolver.db import (
    DEFAULT_DB_PATH,
    get_all_entity_profiles,
    get_routing_keys,
    get_routing_keys_by_value_pattern,
    get_entity_profile,
)


class VendorCache(Protocol):
    """Protocol for vendor existence checks.
    
    The BC connector should implement this protocol to allow
    checking if a vendor exists in a specific entity.
    """
    
    async def vendor_exists_in_entity(
        self,
        vendor_name: str,
        entity_id: str
    ) -> bool:
        """Check if a vendor with the given name exists in the entity.
        
        Args:
            vendor_name: Vendor name to search for
            entity_id: BC company GUID
            
        Returns:
            True if vendor exists, False otherwise
        """
        ...


class EntityResolver:
    """Resolves the correct BC entity for an invoice.
    
    Uses a scoring algorithm based on multiple signals to either:
    1. Auto-assign an entity (if confidence is high enough)
    2. Return top N candidates for user confirmation
    
    Example:
        resolver = EntityResolver()
        resolution = await resolver.resolve_entity(invoice, statement)
        
        if resolution.is_auto_assigned:
            print(f"Auto-assigned to: {resolution.entity.entity_name}")
        else:
            print(f"Choose from {len(resolution.candidates)} candidates")
    """
    
    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        weights: ScoringWeights = DEFAULT_SCORING_WEIGHTS,
        customer_id: Optional[str] = None,
    ):
        """Initialize the resolver.
        
        Args:
            db_path: Path to SQLite database
            weights: Scoring weights configuration
            customer_id: Optional customer filter for multi-tenant
        """
        self.db_path = db_path
        self.weights = weights
        self.customer_id = customer_id
    
    async def resolve_entity(
        self,
        invoice: Dict[str, Any],
        statement: Optional[Dict[str, Any]] = None,
        vendor_cache: Optional[VendorCache] = None,
    ) -> EntityResolution:
        """Resolve the correct entity for an invoice.
        
        Args:
            invoice: Invoice document (dict or InvoiceDocument-like)
            statement: Optional statement document for additional context
            vendor_cache: Optional vendor cache for existence checks
            
        Returns:
            EntityResolution with either auto-assigned entity or candidates
        """
        start_time = time.time()
        
        # Get all active entity profiles
        profiles = get_all_entity_profiles(
            customer_id=self.customer_id,
            active_only=True,
            db_path=self.db_path,
        )
        
        if not profiles:
            return EntityResolution(
                is_auto_assigned=False,
                candidates=[],
                resolution_method="no_entities",
                reasons=["No active entity profiles configured"],
                resolved_at=datetime.utcnow(),
                resolution_time_ms=int((time.time() - start_time) * 1000),
            )
        
        # Extract signals from invoice and statement
        signals = self._extract_signals(invoice, statement)
        
        # Score each entity
        candidates: List[EntityCandidate] = []
        for profile in profiles:
            candidate = await self._score_entity(profile, signals, vendor_cache)
            candidates.append(candidate)
        
        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # Limit to max candidates
        top_candidates = candidates[:self.weights.max_candidates]
        
        # Decide: auto-assign or return candidates
        resolution = self._make_decision(top_candidates, signals)
        
        # Add timing
        resolution.resolved_at = datetime.utcnow()
        resolution.resolution_time_ms = int((time.time() - start_time) * 1000)
        
        return resolution
    
    def _extract_signals(
        self,
        invoice: Dict[str, Any],
        statement: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract routing signals from invoice and statement.
        
        Args:
            invoice: Invoice document
            statement: Optional statement document
            
        Returns:
            Dict of signal names to values
        """
        signals = {
            "owner_number": None,
            "owner_name": None,
            "feedlot_name": None,
            "feedlot_state": None,
            "lot_number": None,
            "remit_state": None,
            "invoice_number": None,
        }
        
        # Extract from invoice
        if invoice:
            # Owner info
            owner = invoice.get("owner", {}) or {}
            signals["owner_number"] = owner.get("owner_number")
            signals["owner_name"] = owner.get("name")
            signals["remit_state"] = owner.get("state")  # Remit-to state
            
            # Feedlot info
            feedlot = invoice.get("feedlot", {}) or {}
            signals["feedlot_name"] = feedlot.get("name")
            signals["feedlot_state"] = feedlot.get("state")
            
            # Lot info
            lot = invoice.get("lot", {}) or {}
            signals["lot_number"] = lot.get("lot_number")
            
            # Invoice number
            signals["invoice_number"] = invoice.get("invoice_number")
        
        # Override/supplement from statement if available
        if statement:
            stmt_owner = statement.get("owner", {}) or {}
            if not signals["owner_number"]:
                signals["owner_number"] = stmt_owner.get("owner_number")
            if not signals["owner_name"]:
                signals["owner_name"] = stmt_owner.get("name")
            if not signals["remit_state"]:
                signals["remit_state"] = stmt_owner.get("state")
            
            stmt_feedlot = statement.get("feedlot", {}) or {}
            if not signals["feedlot_name"]:
                signals["feedlot_name"] = stmt_feedlot.get("name")
        
        return signals
    
    async def _score_entity(
        self,
        profile: EntityProfile,
        signals: Dict[str, Any],
        vendor_cache: Optional[VendorCache] = None,
    ) -> EntityCandidate:
        """Score an entity against the extracted signals.
        
        Args:
            profile: Entity profile to score
            signals: Extracted signals from invoice/statement
            vendor_cache: Optional vendor cache for existence checks
            
        Returns:
            EntityCandidate with score and breakdown
        """
        candidate = EntityCandidate(
            entity=profile,
            score=Decimal("0"),
            reasons=[],
            matched_keys=[],
        )
        
        total_score = Decimal("0")
        
        # 1. Owner number match (strong signal)
        owner_score, owner_keys = self._score_owner_number(profile, signals)
        candidate.owner_number_score = owner_score
        total_score += owner_score
        candidate.matched_keys.extend(owner_keys)
        if owner_score > 0:
            confidence = "hard" if owner_score >= self.weights.owner_number_hard else "soft"
            candidate.reasons.append(
                f"Owner number '{signals.get('owner_number')}' matches ({confidence})"
            )
        
        # 2. Vendor existence check (strong signal)
        if vendor_cache and signals.get("owner_name"):
            try:
                exists = await vendor_cache.vendor_exists_in_entity(
                    signals["owner_name"],
                    profile.entity_id,
                )
                if exists:
                    candidate.vendor_existence_score = self.weights.vendor_existence
                    total_score += self.weights.vendor_existence
                    candidate.reasons.append(
                        f"Vendor '{signals['owner_name']}' exists in entity"
                    )
            except Exception:
                pass  # Skip vendor check on error
        
        # 3. Feedlot name match (medium signal)
        feedlot_score, feedlot_keys = self._score_feedlot_name(profile, signals)
        candidate.feedlot_name_score = feedlot_score
        total_score += feedlot_score
        candidate.matched_keys.extend(feedlot_keys)
        if feedlot_score > 0:
            candidate.reasons.append(
                f"Feedlot name matches '{profile.entity_code or profile.entity_name}'"
            )
        
        # 4. Remit state match (medium signal)
        remit_score, remit_keys = self._score_remit_state(profile, signals)
        candidate.remit_state_score = remit_score
        total_score += remit_score
        candidate.matched_keys.extend(remit_keys)
        if remit_score > 0:
            candidate.reasons.append(
                f"Remit state '{signals.get('remit_state')}' matches"
            )
        
        # 5. Lot prefix match (weak signal)
        lot_score, lot_keys = self._score_lot_pattern(profile, signals)
        candidate.lot_pattern_score = lot_score
        total_score += lot_score
        candidate.matched_keys.extend(lot_keys)
        if lot_score > 0:
            candidate.reasons.append(
                f"Lot '{signals.get('lot_number')}' matches pattern"
            )
        
        candidate.score = total_score
        return candidate
    
    def _score_owner_number(
        self,
        profile: EntityProfile,
        signals: Dict[str, Any],
    ) -> Tuple[Decimal, List[EntityRoutingKey]]:
        """Score based on owner number routing key.
        
        Args:
            profile: Entity profile
            signals: Extracted signals
            
        Returns:
            Tuple of (score, matched_keys)
        """
        owner_num = signals.get("owner_number")
        if not owner_num:
            return Decimal("0"), []
        
        # Look up routing keys for this owner number
        keys = get_routing_keys(
            key_type=RoutingKeyType.OWNER_NUMBER,
            key_value=str(owner_num),
            entity_id=profile.entity_id,
            db_path=self.db_path,
        )
        
        if not keys:
            return Decimal("0"), []
        
        # Use highest priority key
        best_key = max(keys, key=lambda k: k.priority)
        if best_key.confidence == ConfidenceLevel.HARD:
            return self.weights.owner_number_hard, [best_key]
        else:
            return self.weights.owner_number_soft, [best_key]
    
    def _score_feedlot_name(
        self,
        profile: EntityProfile,
        signals: Dict[str, Any],
    ) -> Tuple[Decimal, List[EntityRoutingKey]]:
        """Score based on feedlot name match.
        
        Args:
            profile: Entity profile
            signals: Extracted signals
            
        Returns:
            Tuple of (score, matched_keys)
        """
        feedlot_name = signals.get("feedlot_name")
        if not feedlot_name:
            return Decimal("0"), []
        
        feedlot_upper = feedlot_name.upper()
        
        # Check against routing keys
        all_feedlot_keys = get_routing_keys(
            key_type=RoutingKeyType.FEEDLOT_NAME,
            entity_id=profile.entity_id,
            db_path=self.db_path,
        )
        
        matched_keys = []
        for key in all_feedlot_keys:
            if key.key_value.upper() in feedlot_upper:
                matched_keys.append(key)
        
        if matched_keys:
            best_key = max(matched_keys, key=lambda k: k.priority)
            if best_key.confidence == ConfidenceLevel.HARD:
                return self.weights.feedlot_name_match, matched_keys
            else:
                return self.weights.feedlot_name_match / 2, matched_keys
        
        # Also check against profile aliases
        for alias in profile.aliases:
            if alias.upper() in feedlot_upper or feedlot_upper in alias.upper():
                return self.weights.feedlot_name_match / 2, []
        
        return Decimal("0"), []
    
    def _score_remit_state(
        self,
        profile: EntityProfile,
        signals: Dict[str, Any],
    ) -> Tuple[Decimal, List[EntityRoutingKey]]:
        """Score based on remit-to state match.
        
        Args:
            profile: Entity profile
            signals: Extracted signals
            
        Returns:
            Tuple of (score, matched_keys)
        """
        remit_state = signals.get("remit_state")
        if not remit_state:
            return Decimal("0"), []
        
        # Look up routing keys for this state
        keys = get_routing_keys(
            key_type=RoutingKeyType.REMIT_STATE,
            key_value=remit_state.upper(),
            entity_id=profile.entity_id,
            db_path=self.db_path,
        )
        
        if not keys:
            return Decimal("0"), []
        
        best_key = max(keys, key=lambda k: k.priority)
        return self.weights.remit_state_match, [best_key]
    
    def _score_lot_pattern(
        self,
        profile: EntityProfile,
        signals: Dict[str, Any],
    ) -> Tuple[Decimal, List[EntityRoutingKey]]:
        """Score based on lot number prefix pattern.
        
        Args:
            profile: Entity profile
            signals: Extracted signals
            
        Returns:
            Tuple of (score, matched_keys)
        """
        lot_number = signals.get("lot_number")
        if not lot_number:
            return Decimal("0"), []
        
        # Get all lot prefix keys for this entity
        entity_keys = get_routing_keys(
            key_type=RoutingKeyType.LOT_PREFIX,
            entity_id=profile.entity_id,
            db_path=self.db_path,
        )
        
        matched_keys = []
        for key in entity_keys:
            if lot_number.startswith(key.key_value):
                matched_keys.append(key)
        
        if not matched_keys:
            return Decimal("0"), []
        
        best_key = max(matched_keys, key=lambda k: (len(k.key_value), k.priority))
        return self.weights.lot_prefix_match, [best_key]
    
    def _make_decision(
        self,
        candidates: List[EntityCandidate],
        signals: Dict[str, Any],
    ) -> EntityResolution:
        """Make the final resolution decision.
        
        Auto-assigns if:
        1. Top score >= auto_assign_threshold (70)
        2. Margin over 2nd place >= margin_threshold (15)
        
        Args:
            candidates: Sorted list of candidates (descending by score)
            signals: Extracted signals (for debugging)
            
        Returns:
            EntityResolution with decision
        """
        if not candidates:
            return EntityResolution(
                is_auto_assigned=False,
                candidates=[],
                resolution_method="no_candidates",
                reasons=["No candidate entities found"],
            )
        
        top = candidates[0]
        second_score = candidates[1].score if len(candidates) > 1 else Decimal("0")
        margin = top.score - second_score
        
        # Check auto-assign conditions
        auto_assign = (
            top.score >= self.weights.auto_assign_threshold and
            margin >= self.weights.margin_threshold
        )
        
        if auto_assign:
            return EntityResolution(
                is_auto_assigned=True,
                entity=top.entity,
                entity_id=top.entity.entity_id,
                candidates=candidates,
                resolution_method="auto_scored",
                confidence_score=top.score,
                reasons=[
                    f"Top score {float(top.score):.1f} >= threshold {float(self.weights.auto_assign_threshold):.1f}",
                    f"Margin {float(margin):.1f} >= required {float(self.weights.margin_threshold):.1f}",
                ] + top.reasons,
                requires_confirmation=False,
            )
        else:
            reasons = []
            if top.score < self.weights.auto_assign_threshold:
                reasons.append(
                    f"Top score {float(top.score):.1f} < threshold {float(self.weights.auto_assign_threshold):.1f}"
                )
            if margin < self.weights.margin_threshold:
                reasons.append(
                    f"Margin {float(margin):.1f} < required {float(self.weights.margin_threshold):.1f}"
                )
            
            return EntityResolution(
                is_auto_assigned=False,
                entity=None,
                entity_id=None,
                candidates=candidates,
                resolution_method="manual_confirmation",
                confidence_score=top.score,
                reasons=reasons,
                requires_confirmation=True,
            )
    
    def explain_resolution(self, resolution: EntityResolution) -> str:
        """Generate a human-readable explanation of the resolution.
        
        Args:
            resolution: The resolution to explain
            
        Returns:
            Formatted explanation string
        """
        lines = ["=" * 60, "Entity Resolution Explanation", "=" * 60]
        
        if resolution.is_auto_assigned:
            lines.append(f"✓ AUTO-ASSIGNED to: {resolution.entity.entity_name}")
            lines.append(f"  Entity ID: {resolution.entity_id}")
            lines.append(f"  Confidence: {float(resolution.confidence_score):.1f}/100")
        else:
            lines.append("⚠ MANUAL CONFIRMATION REQUIRED")
            lines.append(f"  Top score: {float(resolution.confidence_score):.1f}/100")
        
        lines.append("")
        lines.append("Reasons:")
        for reason in resolution.reasons:
            lines.append(f"  • {reason}")
        
        if resolution.candidates:
            lines.append("")
            lines.append("Candidates:")
            for i, c in enumerate(resolution.candidates):
                lines.append(f"  {i+1}. {c.entity.entity_name}")
                lines.append(f"     Score: {float(c.score):.1f}")
                lines.append(f"     Breakdown: owner={float(c.owner_number_score):.0f}, "
                           f"vendor={float(c.vendor_existence_score):.0f}, "
                           f"feedlot={float(c.feedlot_name_score):.0f}, "
                           f"state={float(c.remit_state_score):.0f}, "
                           f"lot={float(c.lot_pattern_score):.0f}")
                if c.reasons:
                    for reason in c.reasons[:3]:
                        lines.append(f"       - {reason}")
        
        lines.append("")
        lines.append(f"Resolved in {resolution.resolution_time_ms}ms")
        lines.append("=" * 60)
        
        return "\n".join(lines)
