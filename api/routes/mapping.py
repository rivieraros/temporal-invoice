"""Mapping management endpoints.

Handles mapping rules for vendors, GL accounts, and dimensions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.mapping import MappingEngine, MappingType, MappingRule


router = APIRouter()


# Global mapping engine instance
_mapping_engine = MappingEngine()


class MappingRuleRequest(BaseModel):
    """Request to create/update a mapping rule."""
    source_pattern: str = Field(..., description="Source value to match (exact or regex)")
    target_code: str = Field(..., description="Target ERP code")
    target_name: Optional[str] = Field(None, description="Target name for reference")
    is_regex: bool = Field(False, description="Whether source_pattern is a regex")
    is_default: bool = Field(False, description="Whether this is a default fallback rule")
    priority: int = Field(0, description="Rule priority (higher = evaluated first)")
    notes: Optional[str] = None


class MappingRuleResponse(BaseModel):
    """Mapping rule response."""
    id: str
    mapping_type: str
    source_pattern: str
    target_code: str
    target_name: Optional[str]
    is_regex: bool
    is_default: bool
    priority: int
    created_at: datetime
    notes: Optional[str]


class MappingTestRequest(BaseModel):
    """Request to test a mapping."""
    source_value: str = Field(..., description="Value to look up")


class MappingTestResponse(BaseModel):
    """Mapping test response."""
    source_value: str
    found: bool
    target_code: Optional[str]
    target_name: Optional[str]
    rule_id: Optional[str]
    match_type: str  # exact, regex, default, none


class MappingStatsResponse(BaseModel):
    """Mapping statistics."""
    mapping_type: str
    total_rules: int
    exact_rules: int
    regex_rules: int
    default_rules: int


@router.get("/types")
async def list_mapping_types() -> List[Dict[str, str]]:
    """List available mapping types."""
    return [
        {
            "type": "vendor",
            "description": "Map document vendor names to ERP vendor codes"
        },
        {
            "type": "gl_account",
            "description": "Map line item descriptions to GL account codes"
        },
        {
            "type": "dimension",
            "description": "Map values to ERP dimension codes"
        },
        {
            "type": "location",
            "description": "Map feedlot/location names to ERP location codes"
        },
        {
            "type": "cost_center",
            "description": "Map to cost center dimension values"
        },
    ]


@router.get("/{mapping_type}/rules", response_model=List[MappingRuleResponse])
async def list_mapping_rules(
    mapping_type: str,
    include_defaults: bool = True,
) -> List[MappingRuleResponse]:
    """List all mapping rules for a type."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mapping type. Valid types: {[t.value for t in MappingType]}"
        )
    
    rules = _mapping_engine.get_rules(mt)
    
    if not include_defaults:
        rules = [r for r in rules if not r.is_default]
    
    return [
        MappingRuleResponse(
            id=r.id,
            mapping_type=mt.value,
            source_pattern=r.source_pattern,
            target_code=r.target_code,
            target_name=r.target_name,
            is_regex=r.is_regex,
            is_default=r.is_default,
            priority=r.priority,
            created_at=r.created_at,
            notes=r.notes,
        )
        for r in rules
    ]


@router.post("/{mapping_type}/rules", response_model=MappingRuleResponse, status_code=201)
async def create_mapping_rule(
    mapping_type: str,
    request: MappingRuleRequest,
) -> MappingRuleResponse:
    """Create a new mapping rule."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mapping type. Valid types: {[t.value for t in MappingType]}"
        )
    
    rule = _mapping_engine.add_rule(
        mapping_type=mt,
        source_pattern=request.source_pattern,
        target_code=request.target_code,
        target_name=request.target_name,
        is_regex=request.is_regex,
        is_default=request.is_default,
        priority=request.priority,
        notes=request.notes,
    )
    
    return MappingRuleResponse(
        id=rule.id,
        mapping_type=mt.value,
        source_pattern=rule.source_pattern,
        target_code=rule.target_code,
        target_name=rule.target_name,
        is_regex=rule.is_regex,
        is_default=rule.is_default,
        priority=rule.priority,
        created_at=rule.created_at,
        notes=rule.notes,
    )


@router.delete("/{mapping_type}/rules/{rule_id}")
async def delete_mapping_rule(
    mapping_type: str,
    rule_id: str,
) -> Dict[str, str]:
    """Delete a mapping rule."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping type")
    
    success = _mapping_engine.remove_rule(mt, rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": "Rule deleted"}


@router.post("/{mapping_type}/test", response_model=MappingTestResponse)
async def test_mapping(
    mapping_type: str,
    request: MappingTestRequest,
) -> MappingTestResponse:
    """Test a mapping lookup."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping type")
    
    result = _mapping_engine.lookup(mt, request.source_value)
    
    return MappingTestResponse(
        source_value=request.source_value,
        found=result.found,
        target_code=result.target_code,
        target_name=result.target_name,
        rule_id=result.rule_id,
        match_type=result.match_type.value if result.match_type else "none",
    )


@router.get("/{mapping_type}/stats", response_model=MappingStatsResponse)
async def get_mapping_stats(mapping_type: str) -> MappingStatsResponse:
    """Get statistics for a mapping type."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping type")
    
    rules = _mapping_engine.get_rules(mt)
    
    return MappingStatsResponse(
        mapping_type=mapping_type,
        total_rules=len(rules),
        exact_rules=sum(1 for r in rules if not r.is_regex and not r.is_default),
        regex_rules=sum(1 for r in rules if r.is_regex),
        default_rules=sum(1 for r in rules if r.is_default),
    )


@router.post("/{mapping_type}/import")
async def import_rules(
    mapping_type: str,
    rules: List[MappingRuleRequest],
    replace: bool = Query(False, description="Replace existing rules if true"),
) -> Dict[str, Any]:
    """Import multiple mapping rules."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping type")
    
    if replace:
        # Clear existing rules
        existing = _mapping_engine.get_rules(mt)
        for rule in existing:
            _mapping_engine.remove_rule(mt, rule.id)
    
    imported = 0
    errors = []
    
    for i, req in enumerate(rules):
        try:
            _mapping_engine.add_rule(
                mapping_type=mt,
                source_pattern=req.source_pattern,
                target_code=req.target_code,
                target_name=req.target_name,
                is_regex=req.is_regex,
                is_default=req.is_default,
                priority=req.priority,
                notes=req.notes,
            )
            imported += 1
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    return {
        "imported": imported,
        "errors": errors,
        "total": len(rules),
    }


@router.get("/{mapping_type}/export")
async def export_rules(mapping_type: str) -> List[Dict[str, Any]]:
    """Export mapping rules as JSON."""
    try:
        mt = MappingType(mapping_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping type")
    
    rules = _mapping_engine.get_rules(mt)
    
    return [
        {
            "source_pattern": r.source_pattern,
            "target_code": r.target_code,
            "target_name": r.target_name,
            "is_regex": r.is_regex,
            "is_default": r.is_default,
            "priority": r.priority,
            "notes": r.notes,
        }
        for r in rules
    ]


@router.post("/batch-lookup")
async def batch_lookup(
    lookups: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Perform multiple mapping lookups at once.
    
    Each lookup should have 'mapping_type' and 'source_value' keys.
    """
    results = []
    
    for lookup in lookups:
        mapping_type = lookup.get("mapping_type")
        source_value = lookup.get("source_value")
        
        if not mapping_type or not source_value:
            results.append({
                "source_value": source_value,
                "error": "Missing mapping_type or source_value",
            })
            continue
        
        try:
            mt = MappingType(mapping_type)
            result = _mapping_engine.lookup(mt, source_value)
            
            results.append({
                "mapping_type": mapping_type,
                "source_value": source_value,
                "found": result.found,
                "target_code": result.target_code,
                "target_name": result.target_name,
            })
        except ValueError:
            results.append({
                "source_value": source_value,
                "error": f"Invalid mapping type: {mapping_type}",
            })
    
    return results
