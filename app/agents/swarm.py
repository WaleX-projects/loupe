import logging
import os
import sys

from strands.multiagent import Status, Swarm
from strands.sandbox.docker import DockerSandbox

from .factory import ENTRY_AGENT, build_agents
import logging
#logging.basicConfig(level=logging.INFO)
#logging.getLogger("strands").setLevel(logging.DEBUG)

def build_swarm(sandbox, hooks=None) -> Swarm:
    agents = build_agents(sandbox)
    entry = next(a for a in agents if a.name == ENTRY_AGENT)
    extra = {"hooks": hooks} if hooks else {}
    return Swarm(
        agents,
        entry_point=entry,
        max_handoffs=30,
        max_iterations=30,
        execution_timeout=1800.0,  # 30 min total
        node_timeout=900.0,        # 5 min per agent turn
        repetitive_handoff_detection_window=8,
        repetitive_handoff_min_unique_agents=3,
        **extra,
    )
