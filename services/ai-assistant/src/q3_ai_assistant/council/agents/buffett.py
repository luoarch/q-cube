"""Buffett-inspired agent — qualidade, moat, alocacao de capital."""

from __future__ import annotations

import json

from q3_ai_assistant.council.agent_base import BaseCouncilAgent, HardReject
from q3_ai_assistant.council.packet import AssetAnalysisPacket

PROFILE_VERSION = 1
PROMPT_VERSION = 1


def _roe_consistently_low(packet: AssetAnalysisPacket) -> bool:
    roe_series = packet.trends.get("roe", [])
    if len(roe_series) < 2:
        return False
    vals = [pv.value for pv in roe_series if pv.value is not None]
    return len(vals) >= 2 and all(v < 0.08 for v in vals)


def _margin_collapse(packet: AssetAnalysisPacket) -> bool:
    gm = packet.trends.get("gross_margin", [])
    if len(gm) < 3:
        return False
    vals = [pv.value for pv in gm if pv.value is not None]
    if len(vals) < 3:
        return False
    return vals[-1] < vals[0] * 0.7  # 30%+ margin erosion


class BuffettAgent(BaseCouncilAgent):
    agent_id = "buffett"
    profile_version = PROFILE_VERSION
    prompt_version = PROMPT_VERSION

    def get_hard_rejects(self) -> list[HardReject]:
        return [
            HardReject(
                "roe_consistently_low",
                "ROE abaixo de 8% de forma consistente",
                _roe_consistently_low,
            ),
            HardReject(
                "margin_collapse",
                "Margem bruta caiu mais de 30% no periodo",
                _margin_collapse,
            ),
        ]

    def get_system_prompt(self) -> str:
        return """Voce e um analista de investimentos inspirado na filosofia de Warren Buffett.

Principios centrais:
- Qualidade do negocio: moat competitivo, vantagens duraveis
- ROE consistente e alto
- Margens estaveis ou crescentes
- Boa alocacao de capital (management competente)
- FCF forte e previsivel
- Horizonte: muito longo prazo ("nosso periodo de holding favorito e para sempre")

Estilo: reflexivo, longo-prazo, focado em qualidade.

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
- Use "-inspired" — voce NAO e Warren Buffett"""

    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        return f"""Analise este ativo sob a otica Buffett-inspired (qualidade e moat):

{json.dumps(packet.to_dict(), indent=2, default=str)}

Retorne APENAS o JSON estruturado, sem texto adicional."""
