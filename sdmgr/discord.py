import os
import aiohttp

import logging
_logger = logging.getLogger(__name__)


class Discord():
    def __init__(self, url = None):
        self.url = url if url != None else os.getenv('DISCORD_URL')

    async def notify_registrar_ns_update(self, registrar, domain, nameservers):
        content = f"Please update NS records for domain '{domain.name}' to: "
        content += "```" + ("\n".join(nameservers)) + "```"
        data = {
            'username': registrar.label,
            'content': content
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=data) as response:
                output = await response.text()
                if response.status != 204:
                    _logger.error(f"Unexpected response from Discord API ({response.status}): {output}")
