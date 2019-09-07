from sdmgr.db import WAFProvider, Domain, Registrar
from sdmgr.agent import BaseAgent

import logging
_logger = logging.getLogger(__name__)

import json
import orm


class WAFProviderAgent(BaseAgent):
    _agent_type_ = "waf"

    async def _load_state(self):
        _logger.debug(f"Restoring state for WAF provider '{self.label}'")
        r = await WAFProvider.objects.get(id = self.id)
        self.config_id = r.config_id
        self.state = r.state

    async def _save_state(self):
        _logger.info(f"Saving state for WAF provider '{self.label}'")
        r = await WAFProvider.objects.get(id = self.id)
        await r.update(
            state = self.state
        )

    async def deploy_certificate(self, sitename, hostname, aliases):
        raise NotImplementedError
