from .agent import K8S as Agent
from .. import register_agent

register_agent(Agent)
