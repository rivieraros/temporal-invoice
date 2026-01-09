# Temporal Invoice

AP (Accounts Payable) automation pipeline for feedlot invoice processing, powered by Temporal Cloud and GPT-4o vision extraction.

## Overview

This system extracts, validates, and reconciles invoice and statement data from PDF documents for **Bovina** and **Mesquite** feedlots. It uses:

- **Temporal Cloud** for durable workflow orchestration
- **GPT-4o Vision** for document extraction
- **Pydantic** for data validation
- **SQLite** for persistent state

## Project Status

### Backend Pipeline (Temporal Workflows)

| Step | Description | Status |
|------|-------------|--------|
| Step 0 | Repo Readiness - Module Interfaces | ✅ Complete |
| Step 1 | Temporal Cloud Connectivity + Worker | ✅ Complete |
| Step 2 | Minimal AP Package Workflow | ✅ Complete |
| Step 3 | Extraction Activities (LLM) | ✅ Complete |
| Step 4 | Invoice Validation (B1/B2) | ✅ Complete |
| Step 5 | Statement ↔ Invoice Reconciliation (A1/A5/A6) | ✅ Complete |

### Frontend Dashboard (React + TypeScript)

| Step | Description | Status |
|------|-------------|--------|
| Step 3 | Server Setup + API Proxy | ✅ Complete |
| Step 4 | Mission Control Implementation | ✅ Complete |
| Step 5 | Package Detail 3-Panel Layout | ✅ Complete |
| Step 6 | Drilldown Context Wiring | ✅ Complete |
| Step 7 | API Contract Validation | ✅ Complete |
| Step 8 | Acceptance Criteria Testing | ✅ Complete |

## Quick Start

### Prerequisites

- Python 3.11+
- Temporal Cloud account (or local Temporal server)
- OpenAI API key (for extraction)

### Setup

```bash
# Clone repository
git clone https://github.com/rivieraros/temporal-invoice.git
cd temporal-invoice

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

```env
# Temporal Cloud
TEMPORAL_ENDPOINT=us-central1.gcp.api.temporal.io:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_API_KEY=your-api-key

# OpenAI (for extraction)
OPENAI_API_KEY=sk-...
```

### Running

```bash
# 1. Check configuration
python scripts/check_temporal_config.py

# 2. Start worker (in separate terminal)
python workers/worker.py

# 3. Run workflows
python scripts/start_ping.py              # Test connectivity
python scripts/start_ap_package.py        # Start AP package workflow

# 4. Check database
python scripts/check_packages.py
```

### Running the Frontend (Mission Control)

```bash
# Terminal 1: Start FastAPI backend
cd temporalinvoice
.\.venv\Scripts\activate  # Windows
python -m uvicorn api.server:app --host 127.0.0.1 --port 8001

# Terminal 2: Start Vite dev server
cd temporalinvoice/frontend
npm run dev

# Open browser: http://localhost:5173/mission-control
```

**Note:** The Vite dev server proxies `/dashboard` and `/api` routes to the FastAPI backend.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TEMPORAL CLOUD                            │
│                    Task Queue: ap-default                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      WORKER                                  │
│                                                              │
│  Workflows:               Activities:                        │
│  ├── PingWorkflow         ├── persist_package_started       │
│  └── APPackageWorkflow    └── (more coming...)              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CORE MODULES                               │
│                                                              │
│  extraction/    - PDF → JSON via GPT-4o vision              │
│  reconciliation/ - Finance-grade validation                 │
│  storage/       - Artifact persistence                      │
│  models/        - Pydantic schemas                          │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
temporalinvoice/
├── activities/           # Temporal activities
│   ├── __init__.py
│   └── persist.py        # Database persistence
├── workflows/            # Temporal workflows
│   ├── __init__.py
│   ├── ping_workflow.py  # Connectivity test
│   └── ap_package_workflow.py  # Main workflow
├── workers/              # Temporal workers
│   └── worker.py
├── extraction/           # Document extraction
│   └── runner.py
├── reconciliation/       # Validation engine
│   └── engine.py
├── models/               # Pydantic models
│   ├── canonical.py      # Invoice/Statement schemas
│   └── refs.py           # Reference models
├── storage/              # Artifact storage
│   └── artifacts.py
├── scripts/              # CLI utilities
│   ├── start_ping.py
│   ├── start_ap_package.py
│   ├── check_packages.py
│   └── check_temporal_config.py
├── prompts/              # LLM prompts
├── artifacts/            # Extracted data
├── temporal_client.py    # Cloud connection factory
└── ap_automation.db      # SQLite database
```

## Documentation

| Document | Description |
|----------|-------------|
| [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) | **All steps consolidated** - Complete project progress |
| [ARCHITECTURE_AND_METHODOLOGY.md](ARCHITECTURE_AND_METHODOLOGY.md) | System architecture, issues & solutions |
| [docs/FRONTEND_ARCHITECTURE.md](docs/FRONTEND_ARCHITECTURE.md) | **Frontend design** - Navigation, components, API contracts |
| [COMPREHENSIVE_DOCUMENTATION.md](COMPREHENSIVE_DOCUMENTATION.md) | Full system documentation |
| [docs/BUSINESS_CENTRAL_OAUTH_SETUP.md](docs/BUSINESS_CENTRAL_OAUTH_SETUP.md) | Business Central OAuth setup |
| [MODULE_INTERFACES.md](MODULE_INTERFACES.md) | Complete API documentation |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Quick start guide |
| [TEMPORAL_QUICK_REFERENCE.md](TEMPORAL_QUICK_REFERENCE.md) | Temporal commands |

### Step Completion Files

| File | Description |
|------|-------------|
| [STEP_0_COMPLETION.md](STEP_0_COMPLETION.md) | Module interfaces refactoring |
| [STEP_1_COMPLETION.md](STEP_1_COMPLETION.md) | Temporal Cloud connectivity |
| [STEP_2_COMPLETION.md](STEP_2_COMPLETION.md) | Minimal AP Package workflow |
| [STEP_3_COMPLETION.md](STEP_3_COMPLETION.md) | Extraction activities |
| [STEP_4_COMPLETION.md](STEP_4_COMPLETION.md) | Invoice validation |
| [STEP_5_COMPLETION.md](STEP_5_COMPLETION.md) | Statement reconciliation |
| [STEP_6_COMPLETION.md](STEP_6_COMPLETION.md) | Frontend drilldown context |
| [STEP_7_COMPLETION.md](STEP_7_COMPLETION.md) | API contract validation |
| [STEP_8_COMPLETION.md](STEP_8_COMPLETION.md) | Acceptance testing |

## ERP Integration

### Business Central (OAuth 2.0 + PKCE)

Connect to Microsoft Dynamics 365 Business Central with secure OAuth:

```bash
# 1. Configure environment
export BC_CLIENT_ID="your-app-id"
export BC_REDIRECT_URI="http://localhost:8000/api/auth/bc/callback"
export TOKEN_ENCRYPTION_KEY=$(python -c "from core.security import generate_encryption_key; print(generate_encryption_key())")

# 2. Start API server
python -m uvicorn api.server:app --reload

# 3. Connect (browser)
# Navigate to: http://localhost:8000/api/auth/bc/start-redirect
```

See [Business Central OAuth Setup Guide](docs/BUSINESS_CENTRAL_OAUTH_SETUP.md) for full instructions.

## License

MIT
