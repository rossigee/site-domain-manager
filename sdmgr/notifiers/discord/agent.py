from ..base import NotifierAgent

import logging
_logger = logging.getLogger(__name__)

import os
import aiohttp


class Discord(NotifierAgent):
    _label_ = "Discord"

    _settings_ = [
        {
            'key': "webhook_url",
            'description': "URL of webhook to send notifications to",
        },
    ]

    def __init__(self, data, manager):
        _logger.info(f"Loading Discord notifier agent (id: {data.id}): {data.label})")
        NotifierAgent.__init__(self, data, manager)

    async def notify_registrar_ns_update(self, registrar, domain, nameservers):
        content = f"Please update NS records for domain `{domain.name}` to: "
        content += "```" + ("\n".join(nameservers)) + "```"
        data = {
            'username': registrar.label,
            'content': content
        }
        async with aiohttp.ClientSession() as session:
            webhook_url = self._config("webhook_url")
            async with session.post(webhook_url, data=data) as response:
                output = await response.text()
                if response.status != 204:
                    _logger.error(f"Unexpected response from Discord API ({response.status}): {output}")

    async def notify_domain_transfer_out(self, domain, old_registrar, new_registrar):
        content = f"Domain `{domain.name}` has been transfered out of '{old_registrar.label}' to '{new_registrar.label}'."
        data = {
            'username': old_registrar.label,
            'content': content
        }
        async with aiohttp.ClientSession() as session:
            webhook_url = self._config("webhook_url")
            async with session.post(webhook_url, data=data) as response:
                output = await response.text()
                if response.status != 204:
                    _logger.error(f"Unexpected response from Discord API ({response.status}): {output}")

    async def notify_domain_transfer_in(self, domain, old_registrar, new_registrar):
        content = f"Domain `{domain.name}` has been transfered in from '{old_registrar.label}' to '{new_registrar.label}'."
        data = {
            'username': new_registrar.label,
            'content': content
        }
        async with aiohttp.ClientSession() as session:
            webhook_url = self._config("webhook_url")
            async with session.post(webhook_url, data=data) as response:
                output = await response.text()
                if response.status != 204:
                    _logger.error(f"Unexpected response from Discord API ({response.status}): {output}")
