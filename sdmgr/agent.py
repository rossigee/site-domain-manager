from sdmgr.db import Setting

import sdmgr.settings as settings

import importlib

import logging
_logger = logging.getLogger(__name__)


class BaseAgent():
    _settings_ = []

    def __init__(self, data):
        self.id = data.id
        self.label = data.label
        self.config_id = f"{self._agent_type_}:{data.id}"
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

# Ensure all expected modules are imported/registered...
async def load_and_register_agents():
    for module_name in settings.agents_to_import:
        _logger.info(f"Loading agent module '{module_name}'...")
        agent_module = importlib.import_module(module_name)

# Provide a list of all available agents and their settings
async def fetch_available_agents_and_settings():
    from sdmgr.registrar import available_agents as registrar_agents
    from sdmgr.dns_provider import available_agents as dns_agents
    from sdmgr.waf import available_agents as waf_agents
    from sdmgr.sites import available_agents as hosting_agents

    def agent_info(cls):
        return {
            "class": str(cls.__module__),
            "label": cls._label_,
            "settings": cls._settings_
        }

    return {
        'registrar': [agent_info(cls) for cls in registrar_agents],
        'dns': [agent_info(cls) for cls in dns_agents],
        'waf': [agent_info(cls) for cls in waf_agents],
        'hosting': [agent_info(cls) for cls in hosting_agents],
    }
