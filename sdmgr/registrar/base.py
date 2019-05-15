from sdmgr.db import Registrar, Domain

import logging
_logger = logging.getLogger(__name__)

import json
import orm


class RegistrarAgent():
    def __init__(self, data):
        self.id = data.id
        self.label = data.label
        self.state = {}

    async def _load_state(self):
        _logger.debug(f"Restoring state for registrar '{self.label}'")
        r = await Registrar.objects.get(id = self.id)
        try:
            self.state = json.loads(r.state)
        except Exception as e:
            _logger.exception(e)

    async def _save_state(self):
        _logger.info(f"Saving state for registrar '{self.label}'")
        r = await Registrar.objects.get(id = self.id)
        try:
            await r.update(state=json.dumps(self.state))
        except Exception as e:
            _logger.exception(e)

    async def get_registered_domains(self):
        raise NotImplementedError

    async def _populate_domains(self):
        registrar = await Registrar.objects.get(id = self.id)
        for domainname in await self.get_registered_domains():
            _logger.debug(f"Checking {domainname}...")
            try:
                domain = await Domain.objects.get(name=domainname)
                _logger.debug(f"Found {domainname}.")
            except orm.exceptions.NoMatch:
                domain = await Domain.objects.create(
                    name = domainname,
                    registrar = registrar,
                )
                _logger.debug(f"Created {domainname}.")

    async def set_ns_records(self, domain, nameservers):
        raise NotImplementedError
