from sdmgr.db import Notifier, Domain
from sdmgr.agent import BaseAgent

import logging
_logger = logging.getLogger(__name__)

import orm
import datetime


class NotifierAgent(BaseAgent):
    _agent_type_ = "notifier"

    async def _load_state(self):
        _logger.debug(f"Restoring state for notifier '{self.label}'")
        n = await Notifier.objects.get(id = self.id)
        self.state = n.state

    async def _save_state(self):
        _logger.info(f"Saving state for notifier '{self.label}'")
        n = await Notifier.objects.get(id = self.id)
        await n.update(
            state=self.state,
            updated_time = datetime.datetime.now()
        )
