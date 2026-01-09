"""Business Central HTTP Client.

Low-level HTTP client for Business Central API calls.
Handles authentication headers, pagination, retries, and error handling.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class BCApiError(Exception):
    """Base exception for BC API errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BCAuthenticationError(BCApiError):
    """Authentication failed (401/403)."""
    pass


class BCNotFoundError(BCApiError):
    """Resource not found (404)."""
    pass


class BCRateLimitError(BCApiError):
    """Rate limit exceeded (429)."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, 429)
        self.retry_after = retry_after


class BCValidationError(BCApiError):
    """Validation error from BC (400)."""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    retry_on_status: Tuple[int, ...] = (429, 500, 502, 503, 504)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt (exponential backoff)."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class BCApiConfig:
    """Configuration for BC API client."""
    base_url: str = "https://api.businesscentral.dynamics.com"
    api_version: str = "v2.0"
    environment: str = "production"
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    timeout_seconds: int = 30
    
    def get_base_url(self, tenant_id: str) -> str:
        """Get the base URL for API calls."""
        return f"{self.base_url}/{self.api_version}/{tenant_id}/{self.environment}"
    
    def get_company_url(self, tenant_id: str, company_id: Optional[str] = None) -> str:
        """Get the URL for company-scoped API calls.
        
        Args:
            tenant_id: Azure AD tenant ID
            company_id: Override company ID (if None, uses config default)
        """
        base = self.get_base_url(tenant_id)
        cid = company_id or self.company_id
        if cid:
            return f"{base}/companies({cid})"
        elif self.company_name:
            # URL encode company name
            import urllib.parse
            encoded_name = urllib.parse.quote(self.company_name)
            return f"{base}/companies(name='{encoded_name}')"
        else:
            raise ValueError("Either company_id or company_name must be set")
    
    def get_companies_url(self, tenant_id: str) -> str:
        """Get the URL for listing companies (not company-scoped)."""
        return f"{self.get_base_url(tenant_id)}/companies"


class BCApiClient:
    """HTTP client for Business Central API.
    
    Provides:
    - Authenticated API calls
    - Automatic pagination
    - Error handling and retries
    - OData query support
    
    Usage:
        client = BCApiClient(auth_provider, api_config)
        await client.connect()
        vendors = await client.list("vendors")
        vendor = await client.get("vendors", vendor_id)
    """
    
    def __init__(self, auth_provider, api_config: BCApiConfig, tenant_id: str):
        """Initialize API client.
        
        Args:
            auth_provider: BCAuthProvider for authentication
            api_config: API configuration
            tenant_id: Azure AD tenant ID
        """
        from connectors.business_central.bc_auth import BCAuthProvider
        
        self.auth_provider: BCAuthProvider = auth_provider
        self.api_config = api_config
        self.tenant_id = tenant_id
        self._session = None
    
    async def connect(self) -> bool:
        """Initialize HTTP session and authenticate."""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession()
            return await self.auth_provider.ensure_valid_token()
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        auth_header = self.auth_provider.get_authorization_header()
        if not auth_header:
            raise Exception("Not authenticated")
        
        return {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _build_url(self, endpoint: str, company_id: Optional[str] = None) -> str:
        """Build full URL for an endpoint.
        
        Args:
            endpoint: API endpoint
            company_id: Override company ID (if None, uses config default)
        """
        base = self.api_config.get_company_url(self.tenant_id, company_id)
        return f"{base}/{endpoint}"
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        company_id: Optional[str] = None,
        use_raw_url: bool = False,
    ) -> Dict[str, Any]:
        """Make an authenticated API request with automatic retries.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            company_id: Override company ID
            use_raw_url: If True, endpoint is a complete URL
            
        Returns:
            Response JSON
            
        Raises:
            BCAuthenticationError: Authentication failed
            BCNotFoundError: Resource not found
            BCRateLimitError: Rate limit exceeded
            BCValidationError: Validation error
            BCApiError: Other API errors
        """
        if not self._session:
            raise BCApiError("Not connected. Call connect() first.")
        
        # Ensure we have a valid token
        if not await self.auth_provider.ensure_valid_token():
            raise BCAuthenticationError("Failed to authenticate")
        
        if use_raw_url:
            url = endpoint
        else:
            url = self._build_url(endpoint, company_id)
        
        retry_config = self.api_config.retry_config
        last_error: Optional[Exception] = None
        
        for attempt in range(retry_config.max_retries + 1):
            try:
                headers = self._get_headers()
                
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=self.api_config.timeout_seconds)
                
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout,
                ) as response:
                    response_text = await response.text()
                    
                    # Success
                    if response.status < 400:
                        if response.status == 204:  # No content
                            return {}
                        return json.loads(response_text) if response_text else {}
                    
                    # Handle specific error codes
                    if response.status == 401 or response.status == 403:
                        # Try to refresh token once
                        if attempt == 0:
                            logger.warning("Got 401/403, attempting token refresh...")
                            if await self.auth_provider.ensure_valid_token():
                                continue  # Retry with new token
                        raise BCAuthenticationError(
                            f"Authentication failed: {response_text}",
                            response.status,
                            response_text
                        )
                    
                    if response.status == 404:
                        raise BCNotFoundError(
                            f"Resource not found: {url}",
                            response.status,
                            response_text
                        )
                    
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        if attempt < retry_config.max_retries:
                            logger.warning(f"Rate limited, waiting {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue
                        raise BCRateLimitError(
                            "Rate limit exceeded",
                            retry_after
                        )
                    
                    if response.status == 400:
                        raise BCValidationError(
                            f"Validation error: {response_text}",
                            response.status,
                            response_text
                        )
                    
                    # Retry on server errors
                    if response.status in retry_config.retry_on_status:
                        if attempt < retry_config.max_retries:
                            delay = retry_config.get_delay(attempt)
                            logger.warning(
                                f"Request failed with {response.status}, "
                                f"retrying in {delay:.1f}s (attempt {attempt + 1}/{retry_config.max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    # Non-retryable error
                    raise BCApiError(
                        f"API error {response.status}: {response_text}",
                        response.status,
                        response_text
                    )
                    
            except (asyncio.TimeoutError, Exception) as e:
                if isinstance(e, (BCApiError,)):
                    raise  # Don't retry our own exceptions
                
                last_error = e
                if attempt < retry_config.max_retries:
                    delay = retry_config.get_delay(attempt)
                    logger.warning(
                        f"Request failed with {type(e).__name__}: {e}, "
                        f"retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise BCApiError(f"Request failed after {retry_config.max_retries} retries: {e}")
        
        raise BCApiError(f"Request failed: {last_error}")
    
    async def list_companies(self) -> List[Dict[str, Any]]:
        """List all companies in the BC environment.
        
        This is not company-scoped, so it uses a different URL.
        """
        url = self.api_config.get_companies_url(self.tenant_id)
        response = await self._request("GET", url, use_raw_url=True)
        return response.get("value", [])
    
    async def get(
        self,
        endpoint: str,
        entity_id: str,
        company_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a single entity by ID.
        
        Args:
            endpoint: Entity endpoint (e.g., "vendors")
            entity_id: Entity ID (GUID)
            company_id: Override company ID
            
        Returns:
            Entity data
        """
        full_endpoint = f"{endpoint}({entity_id})"
        return await self._request("GET", full_endpoint, company_id=company_id)
    
    async def list(
        self,
        endpoint: str,
        filter: Optional[str] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List entities with OData query options.
        
        Args:
            endpoint: Entity endpoint
            filter: OData $filter expression
            select: Fields to include
            expand: Related entities to expand
            orderby: Sort order
            top: Maximum number to return
            skip: Number to skip (pagination)
            company_id: Override company ID
            
        Returns:
            List of entities
        """
        params = {}
        
        if filter:
            params["$filter"] = filter
        if select:
            params["$select"] = ",".join(select)
        if expand:
            params["$expand"] = ",".join(expand)
        if orderby:
            params["$orderby"] = orderby
        if top:
            params["$top"] = str(top)
        if skip:
            params["$skip"] = str(skip)
        
        response = await self._request("GET", endpoint, params=params, company_id=company_id)
        return response.get("value", [])
    
    async def list_all(
        self,
        endpoint: str,
        filter: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all entities with automatic pagination.
        
        Args:
            endpoint: Entity endpoint
            filter: OData $filter expression
            page_size: Page size for pagination
            
        Returns:
            All matching entities
        """
        all_results = []
        skip = 0
        
        while True:
            results = await self.list(
                endpoint,
                filter=filter,
                top=page_size,
                skip=skip,
            )
            
            if not results:
                break
            
            all_results.extend(results)
            
            if len(results) < page_size:
                break
            
            skip += page_size
        
        return all_results
    
    async def create(
        self,
        endpoint: str,
        data: Dict[str, Any],
        company_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new entity.
        
        Args:
            endpoint: Entity endpoint
            data: Entity data
            company_id: Override company ID
            
        Returns:
            Created entity with ID
        """
        return await self._request("POST", endpoint, data=data, company_id=company_id)
    
    async def update(
        self,
        endpoint: str,
        entity_id: str,
        data: Dict[str, Any],
        etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an entity.
        
        Args:
            endpoint: Entity endpoint
            entity_id: Entity ID
            data: Updated data
            etag: Optional ETag for optimistic concurrency
            
        Returns:
            Updated entity
        """
        full_endpoint = f"{endpoint}({entity_id})"
        # Note: BC API uses PATCH for updates
        return await self._request("PATCH", full_endpoint, data=data)
    
    async def delete(self, endpoint: str, entity_id: str) -> None:
        """Delete an entity.
        
        Args:
            endpoint: Entity endpoint
            entity_id: Entity ID
        """
        full_endpoint = f"{endpoint}({entity_id})"
        await self._request("DELETE", full_endpoint)
    
    async def post_action(
        self,
        endpoint: str,
        entity_id: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
        company_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a bound action on an entity.
        
        Args:
            endpoint: Entity endpoint
            entity_id: Entity ID
            action: Action name (e.g., "post")
            data: Action parameters
            company_id: Override company ID
            
        Returns:
            Action result
        """
        full_endpoint = f"{endpoint}({entity_id})/Microsoft.NAV.{action}"
        return await self._request("POST", full_endpoint, data=data, company_id=company_id)
