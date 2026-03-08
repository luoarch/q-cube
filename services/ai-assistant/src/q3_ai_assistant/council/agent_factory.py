"""Factory Method — creates council agents from profile IDs."""

from __future__ import annotations

from q3_ai_assistant.council.agent_base import BaseCouncilAgent
from q3_ai_assistant.council.agents.barsi import BarsiAgent
from q3_ai_assistant.council.agents.buffett import BuffettAgent
from q3_ai_assistant.council.agents.graham import GrahamAgent
from q3_ai_assistant.council.agents.greenblatt import GreenblattAgent
from q3_ai_assistant.council.agents.moderator import ModeratorAgent

_AGENT_REGISTRY: dict[str, type[BaseCouncilAgent]] = {
    "barsi": BarsiAgent,
    "graham": GrahamAgent,
    "greenblatt": GreenblattAgent,
    "buffett": BuffettAgent,
    "moderator": ModeratorAgent,
}

SPECIALIST_IDS = ["barsi", "graham", "greenblatt", "buffett"]
ALL_AGENT_IDS = SPECIALIST_IDS + ["moderator"]


def create_agent(agent_id: str) -> BaseCouncilAgent:
    cls = _AGENT_REGISTRY.get(agent_id)
    if cls is None:
        raise ValueError(f"Unknown agent: {agent_id}. Available: {list(_AGENT_REGISTRY.keys())}")
    return cls()


def create_specialists() -> list[BaseCouncilAgent]:
    return [create_agent(aid) for aid in SPECIALIST_IDS]
