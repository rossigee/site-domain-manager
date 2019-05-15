from sdmgr.db import WAFProvider, Domain, Registrar

import logging
_logger = logging.getLogger(__name__)

import json
import orm


class WAFProviderAgent():
    def __init__(self, data):
        self.id = data.id
        self.label = data.label
        self.state = {}

    async def _load_state(self):
        _logger.debug(f"Restoring state for WAF provider '{self.label}'")
        r = await WAFProvider.objects.get(id = self.id)
        try:
            self.state = json.loads(r.state)
        except Exception as e:
            _logger.exception(e)

    async def _save_state(self):
        _logger.info(f"Saving state for WAF provider '{self.label}'")
        r = await WAFProvider.objects.get(id = self.id)
        try:
            await r.update(state=json.dumps(self.state))
        except Exception as e:
            _logger.exception(e)

    async def deploy_certificate(self, sitename, hostname, aliases):
        raise NotImplementedError
