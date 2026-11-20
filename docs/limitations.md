# Known limitations

- **No discovery.** Lekto does not announce itself on the network; enter its address by hand.
- **The household needs an admin's token.** The numbers count every user's documents, which only
  an admin's token may do (`admin:count_all`); the document event and the list of documents need
  `admin:documents_all`.
- **No missed events.** Lekto does not send events that happened while the integration was not
  connected; the sensors catch up, the document event does not fire for them.
- **The document event carries little by default.** Without fields picked in the options, it
  carries only the document's id; names need `master_data:read` or `spaces:read`.
- **Updates are not installed from Home Assistant.** The update entity tells about a new release;
  Lekto is updated where it runs.
- **One version of the API.** During Lekto's beta, each release of the integration speaks one
  version of Lekto's API; a Lekto with another one raises a repair, and some functions may fail
  until both are updated.
- **Numbers every 60 seconds.** Without the rights of the document event, the sensors change only
  at the next fetch.
