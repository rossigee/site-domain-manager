from sdmgr.db import Hosting
from sdmgr.agent import BaseAgent

import logging
_logger = logging.getLogger(__name__)

import json


class HostingAgent(BaseAgent):
    _agent_type_ = "hosting"

    async def _load_state(self):
        _logger.debug(f"Restoring state for hosting '{self.label}'")
        r = await Hosting.objects.get(id = self.id)
        self.config_id = r.config_id
        self.state = r.state

    async def _save_state(self):
        _logger.info(f"Saving state for hosting '{self.label}'")
        r = await Hosting.objects.get(id = self.id)
        await r.update(
            state = self.state
        )
