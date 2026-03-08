"""Greenblatt-inspired agent — earnings yield, return on capital."""

from __future__ import annotations

import json

from q3_ai_assistant.council.agent_base import BaseCouncilAgent, HardReject
from q3_ai_assistant.council.packet import AssetAnalysisPacket

PROFILE_VERSION = 1
PROMPT_VERSION = 1


def _negative_ebit(packet: AssetAnalysisPacket) -> bool:
    ebit = packet.fundamentals.get("ebit")
    return ebit is not None and ebit <= 0


def _roic_consistently_low(packet: AssetAnalysisPacket) -> bool:
    roic_series = packet.trends.get("roic", [])
    if len(roic_series) < 2:
        return False
    vals = [pv.value for pv in roic_series if pv.value is not None]
    return len(vals) >= 2 and all(v < 0.05 for v in vals)


class GreenblattAgent(BaseCouncilAgent):
    agent_id = "greenblatt"
    profile_version = PROFILE_VERSION
    prompt_version = PROMPT_VERSION

    def get_hard_rejects(self) -> list[HardReject]:
        return [
            HardReject(
                "negative_ebit",
                "EBIT negativo — nao atende criterio Magic Formula",
                _negative_ebit,
            ),
            HardReject(
                "roic_consistently_low",
                "ROIC abaixo de 5% nos ultimos periodos",
                _roic_consistently_low,
            ),
        ]

    def get_system_prompt(self) -> str:
        return """Voce e um analista de investimentos inspirado na filosofia de Joel Greenblatt.

Principios centrais:
- Magic Formula: earnings yield + return on capital
- Empresas boas a precos bons
- Foco quantitativo: EY, ROIC, EBIT margin
- Rotacao sistematica baseada em ranking
- Desconfia de narrativas — numeros sao o que importam

Estilo: direto, quantitativo, sem rodeios.

Voce DEVE retornar um JSON valido com este schema exato:
{
  "verdict": "buy" | "watch" | "avoid" | "insufficient_data",
  "confidence": 0-100,
  "thesis": "string com a tese principal",
  "reasonsFor": ["razao 1"],
  "reasonsAgainst": ["risco 1"],
  "keyMetricsUsed": ["metric_code1"],
  "unknowns": ["dado faltante"],
  "whatWouldChangeMyMind": ["condicao 1"],
  "investorFit": ["perfil adequado"]
}

Regras:
- Cite apenas metricas presentes no pacote de dados
- Nao invente dados financeiros
- Use "-inspired" — voce NAO e Joel Greenblatt"""

    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        return f"""Analise este ativo sob a otica Greenblatt-inspired (Magic Formula):

{json.dumps(packet.to_dict(), indent=2, default=str)}

Retorne APENAS o JSON estruturado, sem texto adicional."""
