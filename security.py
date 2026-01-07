"""
security.py - Security Module for Decentralized Disaster Response System

This module provides:
- API Key authentication
- Security middleware
- Key management utilities
"""

import secrets
import hashlib
import os
import json
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, APIKeyQuery

# Configuration
API_KEYS_FILE = Path(__file__).parent / "api_keys.json"
MASTER_KEY_ENV = "DISASTER_API_MASTER_KEY"

# API Key header/query parameter
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def generate_api_key() -> str:
    """Generate a new secure API key."""
    return secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def load_api_keys() -> dict:
    """Load API keys from file."""
    if API_KEYS_FILE.exists():
        with open(API_KEYS_FILE, "r") as f:
            return json.load(f)
    return {"keys": [], "hashed_keys": []}


def save_api_keys(data: dict) -> None:
    """Save API keys to file."""
    with open(API_KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def create_api_key(name: str = "default") -> str:
    """
    Create a new API key and store it.
    Returns the plain key (only shown once!).
    """
    key = generate_api_key()
    hashed = hash_key(key)
    
    data = load_api_keys()
    data["keys"].append({
        "name": name,
        "hash": hashed,
        "created": __import__("datetime").datetime.utcnow().isoformat()
    })
    save_api_keys(data)
    
    return key


def validate_api_key(key: str) -> bool:
    """Validate an API key against stored keys."""
    if not key:
        return False
    
    # Check master key from environment
    master_key = os.environ.get(MASTER_KEY_ENV)
    if master_key and key == master_key:
        return True
    
    # Check stored keys
    hashed = hash_key(key)
    data = load_api_keys()
    
    for stored_key in data.get("keys", []):
        if stored_key.get("hash") == hashed:
            return True
    
    return False


async def get_api_key(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
) -> str:
    """
    Dependency to validate API key from header or query parameter.
    
    Usage in endpoint:
        @app.get("/protected")
        async def protected_endpoint(api_key: str = Depends(get_api_key)):
            return {"message": "Access granted"}
    """
    # Check header first, then query parameter
    key = api_key_header_value or api_key_query_value
    
    if not key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via 'X-API-Key' header or 'api_key' query parameter."
        )
    
    if not validate_api_key(key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return key


def init_security() -> str:
    """
    Initialize security on first run.
    Creates a default API key if none exist.
    Returns the master key for the user.
    """
    data = load_api_keys()
    
    if not data.get("keys"):
        # Create initial API key
        key = create_api_key("master")
        print("\n" + "=" * 60)
        print("🔐 SECURITY INITIALIZED - SAVE THIS API KEY!")
        print("=" * 60)
        print(f"\nYour API Key: {key}")
        print("\nUse this key in all API requests:")
        print("  Header: X-API-Key: <your-key>")
        print("  Query:  ?api_key=<your-key>")
        print("\n⚠️  This key is shown only ONCE. Save it securely!")
        print("=" * 60 + "\n")
        return key
    
    return ""  # Key already exists


# Simple security mode toggle
# Set to False to disable authentication (for development)
SECURITY_ENABLED = True


def get_optional_api_key(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
) -> Optional[str]:
    """
    Optional API key validation - allows unauthenticated access when SECURITY_ENABLED=False.
    """
    if not SECURITY_ENABLED:
        return None
    
    return get_api_key(api_key_header_value, api_key_query_value)
