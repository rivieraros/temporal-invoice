"""Connector management endpoints.

Handles ERP connector configuration and testing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from connectors.erp_base import list_available_connectors, create_connector


router = APIRouter()


class ConnectorStatus(str, Enum):
    """Connector status."""
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ConnectorInfo(BaseModel):
    """Information about an available connector."""
    type: str
    name: str
    description: str
    status: ConnectorStatus
    is_configured: bool
    last_connected: Optional[datetime] = None


class ConnectorConfigRequest(BaseModel):
    """Request to configure a connector."""
    base_url: Optional[str] = None
    company_id: str = Field(..., description="Company/tenant identifier in ERP")
    auth_config: Dict[str, str] = Field(
        ...,
        description="Authentication configuration (varies by connector type)"
    )
    custom_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific settings"
    )


class ConnectorConfigResponse(BaseModel):
    """Response after configuring a connector."""
    connector_type: str
    status: ConnectorStatus
    message: str


class ConnectionTestResult(BaseModel):
    """Result of a connection test."""
    success: bool
    message: str
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = {}


# In-memory config store (replace with database)
_connector_configs: Dict[str, Dict[str, Any]] = {}


@router.get("", response_model=List[ConnectorInfo])
async def list_connectors() -> List[ConnectorInfo]:
    """List all available connectors and their status."""
    available = list_available_connectors()
    
    connectors = []
    for connector_type in available:
        config = _connector_configs.get(connector_type)
        
        if connector_type == "business_central":
            name = "Microsoft Dynamics 365 Business Central"
            description = "Connect to Business Central for vendor, GL account, and purchase invoice operations"
        else:
            name = connector_type.replace("_", " ").title()
            description = f"ERP connector for {name}"
        
        connectors.append(ConnectorInfo(
            type=connector_type,
            name=name,
            description=description,
            status=ConnectorStatus.CONFIGURED if config else ConnectorStatus.NOT_CONFIGURED,
            is_configured=config is not None,
            last_connected=config.get("last_connected") if config else None,
        ))
    
    return connectors


@router.get("/{connector_type}", response_model=ConnectorInfo)
async def get_connector_info(connector_type: str) -> ConnectorInfo:
    """Get information about a specific connector."""
    available = list_available_connectors()
    
    if connector_type not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Connector type '{connector_type}' not found"
        )
    
    config = _connector_configs.get(connector_type)
    
    if connector_type == "business_central":
        name = "Microsoft Dynamics 365 Business Central"
        description = "Connect to Business Central for vendor, GL account, and purchase invoice operations"
    else:
        name = connector_type.replace("_", " ").title()
        description = f"ERP connector for {name}"
    
    return ConnectorInfo(
        type=connector_type,
        name=name,
        description=description,
        status=ConnectorStatus.CONFIGURED if config else ConnectorStatus.NOT_CONFIGURED,
        is_configured=config is not None,
        last_connected=config.get("last_connected") if config else None,
    )


@router.post("/{connector_type}/configure", response_model=ConnectorConfigResponse)
async def configure_connector(
    connector_type: str,
    request: ConnectorConfigRequest,
) -> ConnectorConfigResponse:
    """Configure an ERP connector.
    
    For Business Central, auth_config should include:
    - tenant_id: Azure AD tenant ID
    - client_id: Application client ID
    - client_secret: Client secret
    
    custom_settings can include:
    - environment: BC environment name (default: "production")
    - api_version: API version (default: "v2.0")
    """
    available = list_available_connectors()
    
    if connector_type not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Connector type '{connector_type}' not found"
        )
    
    # Store configuration
    _connector_configs[connector_type] = {
        "base_url": request.base_url,
        "company_id": request.company_id,
        "auth_config": request.auth_config,
        "custom_settings": request.custom_settings,
        "configured_at": datetime.utcnow(),
        "last_connected": None,
    }
    
    return ConnectorConfigResponse(
        connector_type=connector_type,
        status=ConnectorStatus.CONFIGURED,
        message="Connector configured successfully",
    )


@router.post("/{connector_type}/test", response_model=ConnectionTestResult)
async def test_connection(connector_type: str) -> ConnectionTestResult:
    """Test the connection to the ERP system."""
    if connector_type not in _connector_configs:
        raise HTTPException(
            status_code=400,
            detail=f"Connector '{connector_type}' is not configured"
        )
    
    config = _connector_configs[connector_type]
    
    try:
        from connectors.erp_base import ERPConfig
        
        erp_config = ERPConfig(
            connector_type=connector_type,
            base_url=config.get("base_url", ""),
            company_id=config["company_id"],
            auth_config=config["auth_config"],
            custom_settings=config.get("custom_settings", {}),
        )
        
        connector = create_connector(erp_config)
        
        start = datetime.utcnow()
        success = await connector.connect()
        end = datetime.utcnow()
        
        latency_ms = (end - start).total_seconds() * 1000
        
        if success:
            # Test a simple operation
            test_ok = await connector.test_connection()
            await connector.disconnect()
            
            _connector_configs[connector_type]["last_connected"] = datetime.utcnow()
            
            return ConnectionTestResult(
                success=test_ok,
                message="Connection successful" if test_ok else "Connection established but health check failed",
                latency_ms=latency_ms,
                details={"status": "connected"},
            )
        else:
            return ConnectionTestResult(
                success=False,
                message="Failed to establish connection",
                latency_ms=latency_ms,
            )
            
    except Exception as e:
        return ConnectionTestResult(
            success=False,
            message=f"Connection error: {str(e)}",
            details={"error_type": type(e).__name__},
        )


@router.delete("/{connector_type}/configure")
async def remove_configuration(connector_type: str) -> Dict[str, str]:
    """Remove connector configuration."""
    if connector_type not in _connector_configs:
        raise HTTPException(
            status_code=404,
            detail=f"Connector '{connector_type}' is not configured"
        )
    
    del _connector_configs[connector_type]
    
    return {"message": f"Configuration for {connector_type} removed"}


@router.get("/{connector_type}/entities/{entity_type}")
async def list_erp_entities(
    connector_type: str,
    entity_type: str,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """List entities (vendors, GL accounts, etc.) from the ERP.
    
    Entity types: vendor, gl_account, location, dimension
    """
    if connector_type not in _connector_configs:
        raise HTTPException(
            status_code=400,
            detail=f"Connector '{connector_type}' is not configured"
        )
    
    config = _connector_configs[connector_type]
    
    try:
        from connectors.erp_base import ERPConfig, ERPEntityType
        
        # Map string to enum
        entity_type_map = {
            "vendor": ERPEntityType.VENDOR,
            "gl_account": ERPEntityType.GL_ACCOUNT,
            "location": ERPEntityType.LOCATION,
            "dimension": ERPEntityType.DIMENSION,
        }
        
        if entity_type not in entity_type_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid entity type. Valid types: {list(entity_type_map.keys())}"
            )
        
        erp_config = ERPConfig(
            connector_type=connector_type,
            base_url=config.get("base_url", ""),
            company_id=config["company_id"],
            auth_config=config["auth_config"],
            custom_settings=config.get("custom_settings", {}),
        )
        
        connector = create_connector(erp_config)
        await connector.connect()
        
        entities = await connector.list_entities(
            entity_type=entity_type_map[entity_type],
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        
        await connector.disconnect()
        
        return {
            "entity_type": entity_type,
            "count": len(entities),
            "entities": [
                {
                    "erp_id": e.erp_id,
                    "code": e.code,
                    "name": e.name,
                    "is_active": e.is_active,
                }
                for e in entities
            ],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{connector_type}/lookup/{entity_type}")
async def lookup_entity(
    connector_type: str,
    entity_type: str,
    code: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Lookup a specific entity in the ERP."""
    if connector_type not in _connector_configs:
        raise HTTPException(
            status_code=400,
            detail=f"Connector '{connector_type}' is not configured"
        )
    
    if not code and not name:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'code' or 'name' query parameter"
        )
    
    config = _connector_configs[connector_type]
    
    try:
        from connectors.erp_base import ERPConfig, ERPEntityType
        
        entity_type_map = {
            "vendor": ERPEntityType.VENDOR,
            "gl_account": ERPEntityType.GL_ACCOUNT,
            "location": ERPEntityType.LOCATION,
            "dimension": ERPEntityType.DIMENSION,
        }
        
        if entity_type not in entity_type_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid entity type. Valid types: {list(entity_type_map.keys())}"
            )
        
        erp_config = ERPConfig(
            connector_type=connector_type,
            base_url=config.get("base_url", ""),
            company_id=config["company_id"],
            auth_config=config["auth_config"],
            custom_settings=config.get("custom_settings", {}),
        )
        
        connector = create_connector(erp_config)
        await connector.connect()
        
        result = await connector.lookup_entity(
            entity_type=entity_type_map[entity_type],
            code=code,
            name=name,
        )
        
        await connector.disconnect()
        
        if not result.found:
            return {
                "found": False,
                "error": result.error_message,
            }
        
        return {
            "found": True,
            "entity": {
                "erp_id": result.entity.erp_id if result.entity else None,
                "code": result.entity.code if result.entity else None,
                "name": result.entity.name if result.entity else None,
                "is_active": result.entity.is_active if result.entity else None,
            },
            "suggestions": [
                {"code": s.code, "name": s.name}
                for s in (result.suggestions or [])
            ],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
