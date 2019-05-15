from sdmgr.db import Hosting

import logging
_logger = logging.getLogger(__name__)

import json


class HostingAgent():
    def __init__(self, data):
        self.id = data.id
        self.label = data.label
        self.state = {}

    async def _load_state(self):
        _logger.debug(f"Restoring state for hosting '{self.label}'")
        r = await Hosting.objects.get(id = self.id)
        try:
            self.state = json.loads(r.state)
        except Exception as e:
            _logger.exception(e)

    async def _save_state(self):
        _logger.info(f"Saving state for hosting '{self.label}'")
        r = await Hosting.objects.get(id = self.id)
        try:
            await r.update(state=json.dumps(self.state))
        except Exception as e:
            _logger.exception(e)
