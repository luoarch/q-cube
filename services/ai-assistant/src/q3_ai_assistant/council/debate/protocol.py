"""4-round debate protocol.

Round 1: Initial verdict (each agent independently)
Round 2: Contestation (each agent may contest max 2 points from others)
Round 3: Brief reply (objective responses to contestations)
Round 4: Moderator synthesis (convergences, divergences, biggest risk)
"""

from __future__ import annotations

import json
import logging

from q3_ai_assistant.council.types import AgentOpinion

logger = logging.getLogger(__name__)

MAX_ROUNDS = 4
MAX_CONTESTATIONS_PER_AGENT = 2
ROUND_TIMEOUT_SECONDS = 60
DEBATE_TIMEOUT_SECONDS = 300


def validate_debate_config(agent_ids: list[str]) -> None:
    if len(agent_ids) < 2:
        raise ValueError("Debate requires at least 2 agents")
    if len(agent_ids) > 4:
        raise ValueError("Debate supports at most 4 agents")
    if "moderator" in agent_ids:
        raise ValueError("Moderator is added automatically to round 4")


def build_contestation_prompt(
    agent_id: str,
    own_opinion: AgentOpinion,
    other_opinions: list[AgentOpinion],
) -> str:
    """Build round 2 prompt: agent contests up to 2 points from others.

    Returns user prompt to be paired with the agent's system prompt.
    """
    others_summary = []
    for o in other_opinions:
        others_summary.append({
            "agentId": o.agent_id,
            "verdict": o.verdict.value,
            "confidence": o.confidence,
            "thesis": o.thesis,
            "reasonsFor": o.reasons_for,
            "reasonsAgainst": o.reasons_against,
        })

    return f"""RODADA DE CONTESTACAO — voce e {agent_id}.

Sua posicao inicial:
- Veredicto: {own_opinion.verdict.value}
- Tese: {own_opinion.thesis}

Posicoes dos outros agentes:
{json.dumps(others_summary, indent=2, default=str)}

Conteste no maximo {MAX_CONTESTATIONS_PER_AGENT} pontos dos outros agentes.
Para cada contestacao, identifique:
1. Qual agente voce contesta
2. Qual ponto especifico voce contesta
3. Seu contra-argumento (baseado em dados do pacote)

Retorne APENAS um JSON:
{{
  "contestations": [
    {{
      "targetAgent": "agent_id",
      "point": "ponto contestado",
      "counterArgument": "seu contra-argumento"
    }}
  ]
}}"""


def build_reply_prompt(
    agent_id: str,
    own_opinion: AgentOpinion,
    contestations_against: list[dict],
) -> str:
    """Build round 3 prompt: agent replies objectively to contestations against them.

    Returns user prompt to be paired with the agent's system prompt.
    """
    return f"""RODADA DE REPLICA — voce e {agent_id}.

Sua posicao:
- Veredicto: {own_opinion.verdict.value}
- Tese: {own_opinion.thesis}

Contestacoes recebidas:
{json.dumps(contestations_against, indent=2, default=str)}

Responda de forma objetiva a cada contestacao.
Voce pode:
- Manter sua posicao com novo argumento
- Reconhecer parcialmente o ponto contestado
- Ajustar sua confianca (mas nao seu veredicto)

Retorne APENAS um JSON:
{{
  "replies": [
    {{
      "fromAgent": "agent_id que contestou",
      "response": "sua resposta objetiva",
      "confidenceAdjustment": 0
    }}
  ],
  "adjustedConfidence": {own_opinion.confidence}
}}"""


def parse_contestations(raw_text: str) -> list[dict]:
    """Parse contestation JSON from LLM response.

    Returns list of contestation dicts, or empty list on parse failure.
    """
    try:
        # Try to extract JSON from response
        import re
        match = re.search(r'\{[\s\S]*\}', raw_text)
        if not match:
            return []
        parsed = json.loads(match.group())
        contestations = parsed.get("contestations", [])
        # Validate and limit
        return contestations[:MAX_CONTESTATIONS_PER_AGENT]
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse contestation response")
        return []


def parse_replies(raw_text: str, default_confidence: int) -> tuple[list[dict], int]:
    """Parse reply JSON from LLM response.

    Returns (list of reply dicts, adjusted confidence).
    """
    try:
        import re
        match = re.search(r'\{[\s\S]*\}', raw_text)
        if not match:
            return [], default_confidence
        parsed = json.loads(match.group())
        replies = parsed.get("replies", [])
        adjusted = min(100, max(0, int(parsed.get("adjustedConfidence", default_confidence))))
        return replies, adjusted
    except (json.JSONDecodeError, AttributeError, ValueError):
        logger.warning("Failed to parse reply response")
        return [], default_confidence
