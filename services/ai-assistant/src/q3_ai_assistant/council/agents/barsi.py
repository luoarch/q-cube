"""Barsi-inspired agent — dividendos, renda passiva, perenidade."""

from __future__ import annotations

import json

from q3_ai_assistant.council.agent_base import BaseCouncilAgent, HardReject
from q3_ai_assistant.council.packet import AssetAnalysisPacket

PROFILE_VERSION = 1
PROMPT_VERSION = 1


def _negative_fcf_3_years(packet: AssetAnalysisPacket) -> bool:
    cfo = packet.trends.get("cash_from_operations", [])
    cfi = packet.trends.get("cash_from_investing", [])
    if len(cfo) < 3 or len(cfi) < 3:
        return False
    for c, i in zip(cfo[-3:], cfi[-3:]):
        if c.value is None or i.value is None:
            return False
        if c.value + i.value >= 0:
            return False
    return True


def _negative_net_income_recurring(packet: AssetAnalysisPacket) -> bool:
    ni = packet.trends.get("net_income", [])
    if len(ni) < 2:
        return False
    negatives = sum(1 for pv in ni[-3:] if pv.value is not None and pv.value < 0)
    return negatives >= 2


class BarsiAgent(BaseCouncilAgent):
    agent_id = "barsi"
    profile_version = PROFILE_VERSION
    prompt_version = PROMPT_VERSION

    def get_hard_rejects(self) -> list[HardReject]:
        return [
            HardReject(
                "negative_fcf_3y",
                "Fluxo de caixa livre negativo nos ultimos 3 anos",
                _negative_fcf_3_years,
            ),
            HardReject(
                "negative_ni_recurring",
                "Prejuizo recorrente (2+ dos ultimos 3 anos)",
                _negative_net_income_recurring,
            ),
        ]

    def get_system_prompt(self) -> str:
        return """Voce e um analista de investimentos inspirado na filosofia de Luiz Barsi Filho.

Principios centrais:
- Foco em dividendos consistentes e renda passiva
- Preferencia por empresas perenes (utilities, bancos, seguradoras)
- Valoriza receita recorrente e previsivel
- Desconfia de empresas que nao distribuem lucros
- Horizonte de investimento: decadas, nao meses
- Nunca recomenda compra ou venda — apenas analise educacional

Estilo: conservador, didatico, focado em renda.

Voce DEVE retornar um JSON valido com este schema exato:
{
  "verdict": "buy" | "watch" | "avoid" | "insufficient_data",
  "confidence": 0-100,
  "thesis": "string com a tese principal",
  "reasonsFor": ["razao 1", "razao 2"],
  "reasonsAgainst": ["risco 1", "risco 2"],
  "keyMetricsUsed": ["metric_code1", "metric_code2"],
  "unknowns": ["dado faltante ou incerto"],
  "whatWouldChangeMyMind": ["condicao 1"],
  "investorFit": ["perfil de investidor adequado"]
}

Regras:
- Cite apenas metricas presentes no pacote de dados
- Nao invente dados financeiros
- Use "-inspired" — voce NAO e Luiz Barsi
- Inclua disclaimer educacional na tese"""

    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        return f"""Analise este ativo sob a otica Barsi-inspired (dividendos e perenidade):

{json.dumps(packet.to_dict(), indent=2, default=str)}

Retorne APENAS o JSON estruturado, sem texto adicional."""
