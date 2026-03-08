"""Graham-inspired agent — margem de seguranca, preco vs valor."""

from __future__ import annotations

import json

from q3_ai_assistant.council.agent_base import BaseCouncilAgent, HardReject
from q3_ai_assistant.council.packet import AssetAnalysisPacket

PROFILE_VERSION = 1
PROMPT_VERSION = 1


def _high_leverage_and_expensive(packet: AssetAnalysisPacket) -> bool:
    if packet.classification in ("bank", "insurer", "holding"):
        return False
    dte = packet.fundamentals.get("debt_to_ebitda")
    ey = packet.fundamentals.get("earnings_yield")
    if dte is not None and ey is not None:
        return dte > 5.0 and ey < 0.05
    return False


def _negative_equity(packet: AssetAnalysisPacket) -> bool:
    equity = packet.fundamentals.get("equity")
    return equity is not None and equity < 0


class GrahamAgent(BaseCouncilAgent):
    agent_id = "graham"
    profile_version = PROFILE_VERSION
    prompt_version = PROMPT_VERSION

    def get_hard_rejects(self) -> list[HardReject]:
        return [
            HardReject(
                "high_leverage_expensive",
                "Divida/EBITDA > 5x combinada com earnings yield < 5%",
                _high_leverage_and_expensive,
            ),
            HardReject(
                "negative_equity",
                "Patrimonio liquido negativo",
                _negative_equity,
            ),
        ]

    def get_system_prompt(self) -> str:
        return """Voce e um analista de investimentos inspirado na filosofia de Benjamin Graham.

Principios centrais:
- Margem de seguranca: so investe quando preco << valor intrinseco
- Conservadorismo: prefere empresas com baixo endividamento
- Analise quantitativa: P/L, P/VPA, divida liquida, current ratio
- Desconfia de "growth stories" sem lastro financeiro
- Horizonte: medio-longo prazo com disciplina de valor

Estilo: cetico, conservador, quantitativo.

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
- Use "-inspired" — voce NAO e Benjamin Graham"""

    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        return f"""Analise este ativo sob a otica Graham-inspired (margem de seguranca e valor):

{json.dumps(packet.to_dict(), indent=2, default=str)}

Retorne APENAS o JSON estruturado, sem texto adicional."""
