# Diagnostics

For a problem report, download the integration's diagnostics: under
**Settings → Devices & services**, open **Lekto** and select **Download diagnostics** from the
entry's menu (⋮).

The integration's part of the file holds Lekto's version and that of its API, the token's rights and
what they allow, and what the sensors show: the inbox's numbers, the health of Lekto's services, the
jobs by kind, the search index, the classifier and the newest release. It leaves out the token,
Lekto's address, the instance's id and the entry's title, and holds no name of a user, contact or
document. Home Assistant adds its own part: its version, the system it runs on and its custom
integrations.
