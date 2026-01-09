"""API Package.

FastAPI server for the AP Automation system.
"""

from api.server import create_app, app

__all__ = [
    "create_app",
    "app",
]
