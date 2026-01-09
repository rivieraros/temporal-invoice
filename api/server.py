"""FastAPI server for AP Automation.

Main entry point for the API server.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    health,
    packages,
    invoices,
    connectors,
    mapping,
    auth,
    dashboard,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    print("AP Automation API starting up...")
    
    yield
    
    # Shutdown
    print("AP Automation API shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AP Automation API",
        description="API for accounts payable automation with ERP-neutral extraction and configurable connectors",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    app.include_router(packages.router, prefix="/packages", tags=["Packages"])
    app.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
    app.include_router(connectors.router, prefix="/connectors", tags=["Connectors"])
    app.include_router(mapping.router, prefix="/mapping", tags=["Mapping"])
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])
    
    return app


# Default app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
