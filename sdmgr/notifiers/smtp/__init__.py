from .agent import SMTP as Agent
from .. import register_agent

register_agent(Agent)
