"""Moderador Q3 — sintetiza, compara visoes, explica."""

from __future__ import annotations

import json

from q3_ai_assistant.council.agent_base import BaseCouncilAgent, HardReject
from q3_ai_assistant.council.packet import AssetAnalysisPacket

PROFILE_VERSION = 1
PROMPT_VERSION = 1


class ModeratorAgent(BaseCouncilAgent):
    agent_id = "moderator"
    profile_version = PROFILE_VERSION
    prompt_version = PROMPT_VERSION

    def get_hard_rejects(self) -> list[HardReject]:
        return []  # Moderator never rejects

    def get_system_prompt(self) -> str:
        return """Voce e o Moderador Q3, responsavel por sintetizar as opinioes de todos os agentes.

Sua funcao:
- Identificar convergencias e divergencias entre os agentes
- Destacar o maior risco identificado
- Propor condicoes de entrada e saida
- Ser neutro e educacional
- NUNCA recomendar compra ou venda

Voce recebera as opinioes de todos os agentes no prompt do usuario.

Voce DEVE retornar um JSON valido com este schema exato:
{
  "verdict": "watch",
  "confidence": 0-100,
  "thesis": "sintese geral",
  "reasonsFor": ["convergencia 1"],
  "reasonsAgainst": ["divergencia 1"],
  "keyMetricsUsed": ["metric_code1"],
  "unknowns": ["incerteza 1"],
  "whatWouldChangeMyMind": ["condicao 1"],
  "investorFit": ["perfil adequado"],
  "synthesis": {
    "convergences": ["ponto de acordo"],
    "divergences": ["ponto de desacordo"],
    "biggestRisk": "principal risco",
    "entryConditions": ["condicao de entrada"],
    "exitConditions": ["condicao de saida"],
    "overallAssessment": "avaliacao geral"
  }
}

Regras:
- Sempre neutro e educacional
- Inclua disclaimer: conteudo analitico/educacional, nao recomendacao"""

    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        return f"""Sintetize a analise deste ativo:

{json.dumps(packet.to_dict(), indent=2, default=str)}

Retorne APENAS o JSON estruturado, sem texto adicional."""

    def build_synthesis_prompt(
        self,
        packet: AssetAnalysisPacket,
        opinions: list[dict],
    ) -> str:
        """Build a prompt that includes all agent opinions for synthesis."""
        return f"""Sintetize as opinioes dos agentes sobre {packet.ticker}:

Dados do ativo:
{json.dumps(packet.to_dict(), indent=2, default=str)}

Opinioes dos agentes:
{json.dumps(opinions, indent=2, default=str)}

Retorne APENAS o JSON estruturado com a sintese, sem texto adicional."""
