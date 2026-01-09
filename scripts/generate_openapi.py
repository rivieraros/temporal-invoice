"""
Generate OpenAPI specification from FastAPI application.

Outputs the OpenAPI JSON spec to stdout or a file.

Usage:
    python scripts/generate_openapi.py                  # Print to stdout
    python scripts/generate_openapi.py --output api.json  # Save to file
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.server import app


def generate_openapi_spec(output_path: str = None) -> dict:
    """Generate OpenAPI spec from FastAPI app.
    
    Args:
        output_path: Optional file path to save spec
        
    Returns:
        OpenAPI specification dict
    """
    openapi_spec = app.openapi()
    
    if output_path:
        with open(output_path, "w") as f:
            json.dump(openapi_spec, f, indent=2)
        print(f"OpenAPI spec written to: {output_path}")
    else:
        print(json.dumps(openapi_spec, indent=2))
    
    return openapi_spec


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate OpenAPI specification")
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the spec after generation"
    )
    
    args = parser.parse_args()
    
    spec = generate_openapi_spec(args.output)
    
    if args.validate:
        # Basic validation
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            if field not in spec:
                print(f"ERROR: Missing required field: {field}", file=sys.stderr)
                sys.exit(1)
        
        # Count endpoints
        paths = spec.get("paths", {})
        total_endpoints = sum(len(methods) for methods in paths.values())
        
        # Count schemas
        schemas = spec.get("components", {}).get("schemas", {})
        
        print(f"\n✓ OpenAPI spec valid")
        print(f"  Version: {spec['openapi']}")
        print(f"  Title: {spec['info']['title']}")
        print(f"  Paths: {len(paths)}")
        print(f"  Endpoints: {total_endpoints}")
        print(f"  Schemas: {len(schemas)}")


if __name__ == "__main__":
    main()
