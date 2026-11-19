"""Constants of the Lekto integration."""

from typing import Final

DOMAIN: Final = "lekto"

# GET /auth/me names the rights in effect: an admin right counts only while the token's user is
# an active admin. documents:read brings documents:count, which the numbers need.
REQUIRED_RIGHTS: Final = frozenset(
    {"admin:count_all", "admin:documents_all", "documents:read", "system:read"}
)
