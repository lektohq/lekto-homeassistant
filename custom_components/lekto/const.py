"""Constants of the Lekto integration."""

from typing import Final

DOMAIN: Final = "lekto"

# Each right with the rights that include it; GET /auth/me names only the rights a token was given.
REQUIRED_RIGHTS: Final = {
    "admin:count_all": frozenset({"admin:count_all"}),
    "documents:count": frozenset({"documents:count", "documents:read"}),
}
