from sdmgr.db import DNSProvider, Domain, Registrar
from sdmgr.agent import BaseAgent

import logging
_logger = logging.getLogger(__name__)

import json
import orm


class DNSProviderAgent(BaseAgent):
    _agent_type_ = "dns"

    async def _load_state(self):
        _logger.debug(f"Restoring state for DNS provider '{self.label}'")
        r = await DNSProvider.objects.get(id = self.id)
        self.state = r.state

    async def _save_state(self):
        _logger.info(f"Saving state for DNS provider '{self.label}'")
        r = await DNSProvider.objects.get(id = self.id)
        await r.update(
            state = self.state
        )

    async def get_hosted_domains(self):
        raise NotImplementedError

    async def get_status_for_domain(self, domainname):
        raise NotImplementedError

    async def _populate_domains(self):
        try:
            dns = await DNSProvider.objects.get(id = self.id)
            # HACK: Assume that domain is registered with IONOS
            ionos = await Registrar.objects.get(id = 3)
            for domainname in await self.get_hosted_domains():
                _logger.debug(f"Checking {domainname}...")
                try:
                    domain = await Domain.objects.get(name=domainname)
                    _logger.debug(f"Found {domainname}.")
                    if domain.dns.id != dns.id:
                        _logger.info(f"Updating DNS provider for domain {domainname} to {dns.label}.")
                        await domain.update(dns = dns)
                except orm.exceptions.NoMatch:
                    domain = await Domain.objects.create(
                        name = domainname,
                        registrar = ionos,
                        dns = dns,
                    )
                    _logger.info(f"Created domain {domainname}...")
        except Exception as e:
            _logger.exception(e)

    async def check_google_site_verification(self, domain):
        raise NotImplementedError

    async def set_google_site_verification(self, domain):
        raise NotImplementedError
