# Installation

## Requirements

- Home Assistant 2026.11 or newer
- Lekto 0.17 (its API 0.3), reachable from Home Assistant; while Lekto is in beta, a newer Lekto
  may need a newer version of the integration
- An admin of Lekto, to make the API token ([Setup](setup.md))

## Installing

The integration is not in the Marketplace's catalog yet; add this repository to it yourself
(the Marketplace asks you to connect GitHub for that):

1. In Home Assistant, go to **Settings → Marketplace** and select **Add from link**.
2. Under **GitHub link**, enter `lektohq/lekto-homeassistant`, select the type **Integration** if
   asked, and select **Add**.
3. Open **Lekto** in the list and select **Install**.
4. Restart Home Assistant.

Then [set it up](setup.md).
