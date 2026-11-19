"""Constants of the Lekto integration."""

from typing import Final

DOMAIN: Final = "lekto"

# GET /auth/me names the rights in effect: documents:read brings documents:count, and an admin
# right counts only while the token's user is an active admin.
REQUIRED_RIGHTS: Final = frozenset({"admin:count_all", "documents:count", "system:read"})
