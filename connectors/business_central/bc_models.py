"""Business Central data models.

These are BC-specific models that map to the BC API schema.
They are separate from the canonical models in /core/models/.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Business Central API Models
# =============================================================================

class BCBaseModel(BaseModel):
    """Base model for BC API entities."""
    
    class Config:
        populate_by_name = True


class BCVendor(BCBaseModel):
    """Business Central Vendor entity.
    
    Maps to: /companies({id})/vendors
    """
    id: Optional[str] = Field(None, alias="id")
    number: Optional[str] = Field(None, alias="number")
    displayName: Optional[str] = Field(None, alias="displayName")
    addressLine1: Optional[str] = Field(None, alias="addressLine1")
    addressLine2: Optional[str] = Field(None, alias="addressLine2")
    city: Optional[str] = Field(None, alias="city")
    state: Optional[str] = Field(None, alias="state")
    postalCode: Optional[str] = Field(None, alias="postalCode")
    country: Optional[str] = Field(None, alias="country")
    phoneNumber: Optional[str] = Field(None, alias="phoneNumber")
    email: Optional[str] = Field(None, alias="email")
    website: Optional[str] = Field(None, alias="website")
    taxRegistrationNumber: Optional[str] = Field(None, alias="taxRegistrationNumber")
    currencyCode: Optional[str] = Field(None, alias="currencyCode")
    paymentTermsId: Optional[str] = Field(None, alias="paymentTermsId")
    paymentMethodId: Optional[str] = Field(None, alias="paymentMethodId")
    blocked: Optional[str] = Field(None, alias="blocked")
    balance: Optional[Decimal] = Field(None, alias="balance")
    lastModifiedDateTime: Optional[datetime] = Field(None, alias="lastModifiedDateTime")


class BCGLAccount(BCBaseModel):
    """Business Central G/L Account entity.
    
    Maps to: /companies({id})/accounts
    """
    id: Optional[str] = Field(None, alias="id")
    number: Optional[str] = Field(None, alias="number")
    displayName: Optional[str] = Field(None, alias="displayName")
    category: Optional[str] = Field(None, alias="category")
    subCategory: Optional[str] = Field(None, alias="subCategory")
    blocked: Optional[bool] = Field(None, alias="blocked")
    accountType: Optional[str] = Field(None, alias="accountType")
    directPosting: Optional[bool] = Field(None, alias="directPosting")
    netChange: Optional[Decimal] = Field(None, alias="netChange")
    lastModifiedDateTime: Optional[datetime] = Field(None, alias="lastModifiedDateTime")


class BCDimension(BCBaseModel):
    """Business Central Dimension entity.
    
    Maps to: /companies({id})/dimensions
    """
    id: Optional[str] = Field(None, alias="id")
    code: Optional[str] = Field(None, alias="code")
    displayName: Optional[str] = Field(None, alias="displayName")
    lastModifiedDateTime: Optional[datetime] = Field(None, alias="lastModifiedDateTime")


class BCDimensionValue(BCBaseModel):
    """Business Central Dimension Value entity.
    
    Maps to: /companies({id})/dimensionValues
    """
    id: Optional[str] = Field(None, alias="id")
    code: Optional[str] = Field(None, alias="code")
    dimensionId: Optional[str] = Field(None, alias="dimensionId")
    displayName: Optional[str] = Field(None, alias="displayName")
    lastModifiedDateTime: Optional[datetime] = Field(None, alias="lastModifiedDateTime")


class BCPurchaseInvoiceLine(BCBaseModel):
    """Business Central Purchase Invoice Line.
    
    Maps to: /companies({id})/purchaseInvoices({id})/purchaseInvoiceLines
    """
    id: Optional[str] = Field(None, alias="id")
    documentId: Optional[str] = Field(None, alias="documentId")
    sequence: Optional[int] = Field(None, alias="sequence")
    itemId: Optional[str] = Field(None, alias="itemId")
    accountId: Optional[str] = Field(None, alias="accountId")
    lineType: Optional[str] = Field(None, alias="lineType")  # "Item", "Account", "Resource"
    lineObjectNumber: Optional[str] = Field(None, alias="lineObjectNumber")
    description: Optional[str] = Field(None, alias="description")
    description2: Optional[str] = Field(None, alias="description2")
    unitOfMeasureId: Optional[str] = Field(None, alias="unitOfMeasureId")
    unitOfMeasureCode: Optional[str] = Field(None, alias="unitOfMeasureCode")
    quantity: Optional[Decimal] = Field(None, alias="quantity")
    directUnitCost: Optional[Decimal] = Field(None, alias="directUnitCost")
    discountAmount: Optional[Decimal] = Field(None, alias="discountAmount")
    discountPercent: Optional[Decimal] = Field(None, alias="discountPercent")
    discountAppliedBeforeTax: Optional[bool] = Field(None, alias="discountAppliedBeforeTax")
    amountExcludingTax: Optional[Decimal] = Field(None, alias="amountExcludingTax")
    taxCode: Optional[str] = Field(None, alias="taxCode")
    taxPercent: Optional[Decimal] = Field(None, alias="taxPercent")
    totalTaxAmount: Optional[Decimal] = Field(None, alias="totalTaxAmount")
    amountIncludingTax: Optional[Decimal] = Field(None, alias="amountIncludingTax")
    invoiceDiscountAllocation: Optional[Decimal] = Field(None, alias="invoiceDiscountAllocation")
    netAmount: Optional[Decimal] = Field(None, alias="netAmount")
    netTaxAmount: Optional[Decimal] = Field(None, alias="netTaxAmount")
    netAmountIncludingTax: Optional[Decimal] = Field(None, alias="netAmountIncludingTax")
    expectedReceiptDate: Optional[date] = Field(None, alias="expectedReceiptDate")
    itemVariantId: Optional[str] = Field(None, alias="itemVariantId")
    locationId: Optional[str] = Field(None, alias="locationId")


class BCPurchaseInvoice(BCBaseModel):
    """Business Central Purchase Invoice entity.
    
    Maps to: /companies({id})/purchaseInvoices
    """
    id: Optional[str] = Field(None, alias="id")
    number: Optional[str] = Field(None, alias="number")
    invoiceDate: Optional[date] = Field(None, alias="invoiceDate")
    postingDate: Optional[date] = Field(None, alias="postingDate")
    dueDate: Optional[date] = Field(None, alias="dueDate")
    vendorId: Optional[str] = Field(None, alias="vendorId")
    vendorNumber: Optional[str] = Field(None, alias="vendorNumber")
    vendorName: Optional[str] = Field(None, alias="vendorName")
    payToVendorId: Optional[str] = Field(None, alias="payToVendorId")
    payToVendorNumber: Optional[str] = Field(None, alias="payToVendorNumber")
    payToName: Optional[str] = Field(None, alias="payToName")
    shipToName: Optional[str] = Field(None, alias="shipToName")
    shipToContact: Optional[str] = Field(None, alias="shipToContact")
    buyFromAddressLine1: Optional[str] = Field(None, alias="buyFromAddressLine1")
    buyFromAddressLine2: Optional[str] = Field(None, alias="buyFromAddressLine2")
    buyFromCity: Optional[str] = Field(None, alias="buyFromCity")
    buyFromState: Optional[str] = Field(None, alias="buyFromState")
    buyFromPostCode: Optional[str] = Field(None, alias="buyFromPostCode")
    buyFromCountry: Optional[str] = Field(None, alias="buyFromCountry")
    currencyCode: Optional[str] = Field(None, alias="currencyCode")
    currencyId: Optional[str] = Field(None, alias="currencyId")
    pricesIncludeTax: Optional[bool] = Field(None, alias="pricesIncludeTax")
    discountAmount: Optional[Decimal] = Field(None, alias="discountAmount")
    discountAppliedBeforeTax: Optional[bool] = Field(None, alias="discountAppliedBeforeTax")
    totalAmountExcludingTax: Optional[Decimal] = Field(None, alias="totalAmountExcludingTax")
    totalTaxAmount: Optional[Decimal] = Field(None, alias="totalTaxAmount")
    totalAmountIncludingTax: Optional[Decimal] = Field(None, alias="totalAmountIncludingTax")
    status: Optional[str] = Field(None, alias="status")  # "Draft", "Open", "Paid"
    lastModifiedDateTime: Optional[datetime] = Field(None, alias="lastModifiedDateTime")
    
    # Vendor invoice number (external document)
    vendorInvoiceNumber: Optional[str] = Field(None, alias="vendorInvoiceNumber")
    
    # Lines (populated separately)
    purchaseInvoiceLines: List[BCPurchaseInvoiceLine] = Field(default_factory=list)


class BCLocation(BCBaseModel):
    """Business Central Location entity."""
    id: Optional[str] = Field(None, alias="id")
    code: Optional[str] = Field(None, alias="code")
    displayName: Optional[str] = Field(None, alias="displayName")
    contact: Optional[str] = Field(None, alias="contact")
    addressLine1: Optional[str] = Field(None, alias="addressLine1")
    addressLine2: Optional[str] = Field(None, alias="addressLine2")
    city: Optional[str] = Field(None, alias="city")
    state: Optional[str] = Field(None, alias="state")
    postalCode: Optional[str] = Field(None, alias="postalCode")
    country: Optional[str] = Field(None, alias="country")


class BCPaymentTerms(BCBaseModel):
    """Business Central Payment Terms entity."""
    id: Optional[str] = Field(None, alias="id")
    code: Optional[str] = Field(None, alias="code")
    displayName: Optional[str] = Field(None, alias="displayName")
    dueDateCalculation: Optional[str] = Field(None, alias="dueDateCalculation")
    discountDateCalculation: Optional[str] = Field(None, alias="discountDateCalculation")
    discountPercent: Optional[Decimal] = Field(None, alias="discountPercent")
    calculateDiscountOnCreditMemos: Optional[bool] = Field(None, alias="calculateDiscountOnCreditMemos")
