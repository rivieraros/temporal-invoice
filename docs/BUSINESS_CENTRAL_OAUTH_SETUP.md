# Business Central OAuth Setup Guide

This guide walks you through setting up OAuth 2.0 authentication for Business Central integration. The setup takes about 5-10 minutes.

## Overview

We use **OAuth 2.0 Authorization Code flow with PKCE** for secure, password-free authentication:

- ✅ No passwords to manage
- ✅ Users authenticate directly with Microsoft
- ✅ Tokens encrypted at rest (AES-256-GCM)
- ✅ Automatic token refresh
- ✅ Per-tenant isolation

---

## Step 1: Register an App in Azure/Entra ID

### 1.1 Go to Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Search for **"App registrations"** and click it
3. Click **"+ New registration"**

### 1.2 Configure the App

| Field | Value |
|-------|-------|
| **Name** | `AP Automation - Business Central` |
| **Supported account types** | Choose based on your needs: |
| | - **Single tenant**: Only your organization |
| | - **Multitenant**: Any Azure AD directory |
| **Redirect URI** | Web: `https://<yourapp>/api/auth/bc/callback` |

> **For local development:** Use `http://localhost:8000/api/auth/bc/callback`

### 1.3 Note Your App IDs

After registration, note these values from the **Overview** page:

```
Application (client) ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Directory (tenant) ID:   xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Step 2: Configure API Permissions

### 2.1 Add Business Central API Permission

1. In your app registration, click **"API permissions"**
2. Click **"+ Add a permission"**
3. Select **"APIs my organization uses"**
4. Search for **"Dynamics 365 Business Central"**
5. Select it

### 2.2 Select Permission Type

For **delegated** access (user logs in):

| Permission | Type | Description |
|------------|------|-------------|
| `Financials.ReadWrite.All` | Delegated | Full access to financial data |
| `user_impersonation` | Delegated | Access as the user |

For **application** access (background/daemon - optional):

| Permission | Type | Description |
|------------|------|-------------|
| `Automation.ReadWrite.All` | Application | For background processing |
| `app_access` | Application | Application-level access |

### 2.3 Grant Admin Consent

1. Click **"Grant admin consent for [Your Org]"**
2. Confirm by clicking **"Yes"**

> **Note:** Admin consent is required for application permissions. Delegated permissions can be consented by users.

---

## Step 3: Configure Client Secret (Optional for PKCE)

If using **confidential client** (recommended for web apps with backend):

1. Click **"Certificates & secrets"**
2. Click **"+ New client secret"**
3. Add a description: `ap-automation-secret`
4. Set expiration (recommend 12-24 months)
5. Click **"Add"**
6. **Copy the secret value immediately** (it won't be shown again)

> **Note:** With PKCE, the client secret is optional but adds an extra layer of security for server-side apps.

---

## Step 4: Configure Your Application

### 4.1 Set Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Required
BC_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
BC_REDIRECT_URI=https://yourapp.com/api/auth/bc/callback

# Optional (for confidential client)
BC_CLIENT_SECRET=your-secret-value

# Optional (for multi-tenant apps, use "common")
BC_DEFAULT_TENANT=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Required for token encryption (generate with: python -c "from core.security import generate_encryption_key; print(generate_encryption_key())")
TOKEN_ENCRYPTION_KEY=base64-encoded-32-byte-key
```

### 4.2 Generate Encryption Key

```bash
python -c "from core.security import generate_encryption_key; print(generate_encryption_key())"
```

Copy the output and set it as `TOKEN_ENCRYPTION_KEY`.

---

## Step 5: Test the Connection

### 5.1 Start the API Server

```bash
cd /path/to/temporalinvoice
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/Mac

python -m uvicorn api.server:app --reload
```

### 5.2 Check Configuration

Visit: `http://localhost:8000/api/auth/bc/config`

You should see:
```json
{
  "client_id_configured": true,
  "client_secret_configured": true,
  "redirect_uri": "http://localhost:8000/api/auth/bc/callback",
  "encryption_configured": true,
  ...
}
```

### 5.3 Connect Business Central

**Option A: Browser Redirect**

Navigate to: `http://localhost:8000/api/auth/bc/start-redirect`

This will:
1. Redirect you to Microsoft login
2. Ask for your Business Central credentials
3. Request consent for the app
4. Redirect back to your app
5. Store tokens securely

**Option B: API Call**

```bash
curl http://localhost:8000/api/auth/bc/start?tenant_id=YOUR_TENANT_ID
```

Response:
```json
{
  "auth_url": "https://login.microsoftonline.com/...",
  "session_id": "abc123",
  "expires_in": 600
}
```

Redirect the user to `auth_url`.

### 5.4 Verify Connection

```bash
curl "http://localhost:8000/api/auth/bc/status?tenant_id=YOUR_TENANT_ID"
```

Response:
```json
{
  "connected": true,
  "tenant_id": "...",
  "expires_at": "2026-01-07T18:00:00",
  "scopes": ["https://api.businesscentral.dynamics.com/.default", "offline_access"]
}
```

---

## Security Checklist

### ✅ Non-Negotiable Requirements

| Requirement | Implementation |
|-------------|----------------|
| **Encrypt tokens at rest** | AES-256-GCM with server-side key |
| **Store only in backend** | Tokens never sent to browser |
| **Short-lived access tokens** | 1-hour expiry, auto-refresh |
| **Refresh tokens server-side** | Stored encrypted in `.tokens/` |
| **Strict scopes** | Only `Financials.ReadWrite.All` + `offline_access` |
| **Per-customer segregation** | Tenant ID in encryption AAD |

### 🔒 Production Recommendations

1. **Use HTTPS only** - Never expose OAuth endpoints over HTTP in production
2. **Rotate encryption keys** - Implement key rotation every 6-12 months
3. **Use Key Vault** - Store `TOKEN_ENCRYPTION_KEY` in Azure Key Vault or similar
4. **Set short secret expiry** - Client secrets should expire in 12-24 months max
5. **Monitor token usage** - Log and alert on unusual token refresh patterns
6. **Implement logout** - Add endpoint to revoke tokens on Microsoft side

---

## Troubleshooting

### "Invalid client" error

- Verify `BC_CLIENT_ID` matches the Application ID in Azure
- Check that the app registration hasn't been deleted
- Ensure redirect URI matches exactly (including trailing slash)

### "Consent required" error

- User may need to consent to permissions
- Admin consent may be required for some permissions
- Check that API permissions were added correctly

### "Token expired" and refresh fails

- Refresh token may have expired (usually 90 days)
- User needs to re-authenticate
- Check `BC_CLIENT_SECRET` hasn't expired

### "AADSTS700016: Application not found"

- App registration may be in wrong tenant
- Verify tenant ID matches where app was registered
- For multi-tenant, ensure account type is "Multitenant"

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/bc/config` | GET | Check configuration status |
| `/api/auth/bc/start` | GET | Get OAuth authorization URL |
| `/api/auth/bc/start-redirect` | GET | Redirect to Microsoft login |
| `/api/auth/bc/callback` | GET | OAuth callback (for Microsoft) |
| `/api/auth/bc/status` | GET | Check connection status |
| `/api/auth/bc/disconnect` | POST | Revoke tokens |
| `/api/auth/bc/refresh` | GET | Manually refresh token |

---

## Next Steps

Once connected, you can:

1. **Configure vendor mappings**: `/mapping/vendor/rules`
2. **Configure GL account mappings**: `/mapping/gl_account/rules`
3. **Test connector**: `/connectors/business_central/test`
4. **List vendors from BC**: `/connectors/business_central/entities/vendor`

See the main API documentation at `/docs` for full endpoint reference.
