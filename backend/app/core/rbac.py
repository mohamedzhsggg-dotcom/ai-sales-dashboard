"""Role-based access control: permission catalog + enforcement dependency.

Roles map to permission sets. The current production behavior is preserved:
- admin    -> every permission
- agent    -> operational permissions (confirm orders, update status, stock)
- support  -> read-only + a few status updates (matches today's read-only support)

New permissions must be added to PERMISSIONS and to the role map explicitly.
"""

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models import User

# Central permission catalog. Format: "domain.action".
PERMISSIONS = frozenset(
    {
        # Orders
        "orders.read",
        "orders.confirm",
        "orders.update_status",
        # Customers
        "customers.read",
        # Products & inventory
        "products.read",
        "inventory.read",
        "inventory.update",
        # System
        "audit.read",
        "dashboard.read",
    }
)

# Role -> allowed permissions (subset of PERMISSIONS).
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(PERMISSIONS),
    "agent": {
        "orders.read",
        "orders.confirm",
        "orders.update_status",
        "customers.read",
        "products.read",
        "inventory.read",
        "inventory.update",
        "dashboard.read",
    },
    "support": {
        "orders.read",
        "customers.read",
        "products.read",
        "inventory.read",
        "dashboard.read",
    },
}

# Back-compat: roles are also valid as "all implied" only if listed above.
VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())


def has_permission(user: User, permission: str) -> bool:
    if permission not in PERMISSIONS:
        raise ValueError(f"Unknown permission: {permission}")
    return permission in ROLE_PERMISSIONS.get(user.role, set())


def require_permission(*permissions: str):
    """Dependency factory: require ANY of the given permissions."""

    def checker(user: User = Depends(get_current_user)) -> User:
        for p in permissions:
            if has_permission(user, p):
                return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return checker