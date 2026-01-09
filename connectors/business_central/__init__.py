"""Business Central Connector Package.

Implements the ERPConnector interface for Microsoft Dynamics 365 Business Central.
"""

from connectors.business_central.bc_connector import BusinessCentralConnector
from connectors.business_central.bc_models import (
    BCVendor,
    BCGLAccount,
    BCPurchaseInvoice,
    BCPurchaseInvoiceLine,
    BCDimension,
)
from connectors.business_central.bc_auth import BCAuthProvider, BCAuthConfig, BCToken
from connectors.business_central.bc_oauth import (
    BCOAuthProvider,
    BCOAuthConfig,
    OAuthTokens,
    PKCEChallenge,
    OAuthFlowSession,
)

__all__ = [
    # Connector
    "BusinessCentralConnector",
    # Client credentials auth
    "BCAuthProvider",
    "BCAuthConfig",
    "BCToken",
    # OAuth PKCE auth
    "BCOAuthProvider",
    "BCOAuthConfig",
    "OAuthTokens",
    "PKCEChallenge",
    "OAuthFlowSession",
    # Models
    "BCVendor",
    "BCGLAccount",
    "BCPurchaseInvoice",
    "BCPurchaseInvoiceLine",
    "BCDimension",
]
