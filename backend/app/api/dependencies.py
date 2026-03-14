"""
Shared API dependencies for tenant/user scoping.
"""

from typing import Optional
from fastapi import Header


def get_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract the user/tenant ID from the X-User-Id header.
    Returns None if not provided (backward-compatible; no tenant scoping).
    """
    return x_user_id
