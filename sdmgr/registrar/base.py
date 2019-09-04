from sdmgr.db import Registrar, Domain
from sdmgr.agent import BaseAgent

import logging
_logger = logging.getLogger(__name__)

import orm
import datetime


class RegistrarAgent(BaseAgent):
    async def _load_state(self):
        _logger.debug(f"Restoring state for registrar '{self.label}'")
        r = await Registrar.objects.get(id = self.id)
        self.config_id = r.config_id
        self.state = r.state

    async def _save_state(self):
        _logger.info(f"Saving state for registrar '{self.label}'")
        r = await Registrar.objects.get(id = self.id)
        await r.update(
            state=self.state,
            updated_time = datetime.datetime.now()
        )

    async def get_registered_domains(self):
        raise NotImplementedError

    async def get_refresh_method(self):
        """
        Returns the method used to refresh domain data for this registrar. Can by 'api', 'csvfile' or 'jsonfile'.
        """
        raise NotImplementedError

    async def get_status(self):
        """
        Returns a hash with attributes for 'domain_count_total' and 'domain_count_active'.
        """
        raise NotImplementedError

    async def get_status_for_domain(self, domainname):
        raise NotImplementedError

    async def _populate_domains(self):
        try:
            registrar = await Registrar.objects.get(id = self.id)
            domainnames = await self.get_registered_domains()
            _logger.info(f"Checking for new domains in {len(domainnames)} domains from recent update...")
            for domainname in domainnames:
                _logger.debug(f"Checking {domainname}...")
                try:
                    domain = await Domain.objects.get(name=domainname)
                    if domain.registrar.id == registrar.id:
                        _logger.debug(f"Found {domainname}.")
                    else:
                        await domain.update(registrar = registrar.id)
                        _logger.info(f"Reassociating '{domainname}' with registrar '{registrar.label}'.")
                except orm.exceptions.NoMatch:
                    domain = await Domain.objects.create(
                        name = domainname,
                        registrar = registrar,
                    )
                    _logger.info(f"Created domain '{domainname}' from registrar '{registrar.label}'.")
        except Exception as e:
            _logger.exception(e)

    async def set_ns_records(self, domain, nameservers):
        # TODO: Abstract notification service away at some point. For now,
        # where registrar's entries can't be managed via API, tell an admin.
        try:
            from sdmgr.discord import Discord
            await Discord().notify_registrar_ns_update(self, domain, nameservers)
        except Exception as e:
            _logger.exception(e)
