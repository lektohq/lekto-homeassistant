# Lekto for Home Assistant

The integration brings [Lekto](https://github.com/lektohq/lekto), a self-hosted document
management system, into Home Assistant. It reports the numbers of the household's documents,
such as how many wait in the inbox. It is being built: it will react to new documents, start
actions in Lekto and tell when a new release of Lekto is out. It talks to Lekto's REST API
through [pylekto](https://github.com/lektohq/pylekto), in the local network; nothing leaves it.

One entry sets up one Lekto instance, with an API token made for Home Assistant.

- [Installation](installation.md)
- [Setup](setup.md): the token and its rights, the parameters
- [Sensors](sensors.md): what they count
- [Removal](removal.md)
