"""Constants of the Lekto integration."""

from typing import Final

DOMAIN: Final = "lekto"

# The household's numbers are the least the integration does; everything else is optional.
REQUIRED_RIGHTS: Final = frozenset({"admin:count_all", "documents:count"})

# The capabilities an entry has had, so that one the token lost can be named.
CONF_CAPABILITIES: Final = "capabilities"

# What the document event may carry beside the document's id; the user picks in the options.
CONF_EVENT_FIELDS: Final = "event_fields"
EVENT_FIELDS: Final = ("title", "document_date", "contact", "document_type", "tags", "space")
