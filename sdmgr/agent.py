from sdmgr.db import Setting

class BaseAgent():
    def __init__(self, data):
        self.id = data.id
        self.label = data.label
        self.config_id = data.config_id
        self.config = {}
        self.state = {}
        self.updated_time = None

    def _config(self, key: str):
        return self.config[key]

    async def start(self):
        settings = Setting.objects.filter(config_id = self.config_id)
        for setting in await settings.all():
            self.config[setting.s_key] = setting.s_value

        await self._load_state()
