"""Free chat module — RAG + internal tools + LLM synthesis.

Handles conversational queries about companies, strategies, data lineage,
and general Q3 usage. Uses internal tools for structured data lookup and
RAG for contextual enrichment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from q3_ai_assistant.council.tools.internal import (
    ToolResult,
    get_company_financials_3p,
    get_company_flags,
    get_company_summary,
    get_data_lineage,
    get_market_snapshot,
    get_strategy_definition,
)
from q3_ai_assistant.llm.cascade import CascadeRouter

logger = logging.getLogger(__name__)

FREE_CHAT_SYSTEM_PROMPT = """\
Voce e o assistente Q³, um especialista em analise quantitativa de acoes \
brasileiras. Voce ajuda investidores a entender rankings, metricas, \
estrategias e dados financeiros de empresas listadas na B3.

Regras:
- Responda sempre em portugues (pt-BR)
- Use dados factuais das ferramentas internas quando disponiveis
- Nunca fabrique numeros ou metricas — se nao tiver dados, diga
- Nunca recomende compra ou venda direta — voce e educacional/analitico
- Cite a fonte quando usar dados (ex: "Segundo os dados da CVM...")
- Seja conciso e direto

Contexto adicional (se disponivel):
{context}
"""


@dataclass(frozen=True)
class FreeChatResult:
    response: str
    tools_used: list[str]
    provider_used: str
    model_used: str
    tokens_used: int
    cost_usd: float


def _detect_intent(query: str) -> dict:
    """Detect what the user is asking about from keywords."""
    q = query.lower()
    intent: dict = {"type": "general", "tickers": [], "metrics": []}

    # Detect tickers (4-6 letter codes ending in digit)
    import re
    ticker_matches = re.findall(r'\b([A-Z]{4}\d{1,2})\b', query.upper())
    intent["tickers"] = list(set(ticker_matches))

    # Detect strategy mentions
    strategy_keywords = ["magic formula", "greenblatt", "ranking", "estrategia"]
    if any(kw in q for kw in strategy_keywords):
        intent["type"] = "strategy"

    # Detect company-specific queries
    elif intent["tickers"]:
        company_keywords = ["empresa", "companhia", "sobre", "analise", "dados", "financeiro"]
        lineage_keywords = ["lineage", "linhagem", "origem", "fonte", "de onde", "como calcula"]
        if any(kw in q for kw in lineage_keywords):
            intent["type"] = "lineage"
        elif any(kw in q for kw in company_keywords) or len(intent["tickers"]) == 1:
            intent["type"] = "company"

    # Detect metric queries
    metric_keywords = [
        "roic", "roe", "earnings yield", "ebit", "margem", "margin",
        "divida", "debt", "ebitda", "p/l", "pe ratio",
    ]
    for kw in metric_keywords:
        if kw in q:
            intent["metrics"].append(kw)
    if intent["metrics"] and not intent["tickers"]:
        intent["type"] = "metric_concept"

    return intent


def _gather_tool_context(
    session: Session,
    intent: dict,
) -> tuple[str, list[str]]:
    """Run relevant internal tools and build context string."""
    context_parts: list[str] = []
    tools_used: list[str] = []

    tickers: list[str] = intent.get("tickers", [])

    if intent["type"] == "strategy":
        result = get_strategy_definition("magic_formula")
        if result.data:
            context_parts.append(f"Estrategia: {result.data}")
            tools_used.append("get_strategy_definition")

    if intent["type"] == "lineage" and tickers:
        metric_code = intent["metrics"][0] if intent["metrics"] else "roic"
        result = get_data_lineage(session, tickers[0], metric_code)
        if result.data:
            context_parts.append(f"Linhagem de dados ({tickers[0]}, {metric_code}): {result.data}")
            tools_used.append("get_data_lineage")

    for ticker in tickers[:2]:
        # Company summary
        result = get_company_summary(session, ticker)
        if result.data:
            context_parts.append(f"Empresa {ticker}: {result.data}")
            tools_used.append("get_company_summary")

        # Financials (3-period)
        result = get_company_financials_3p(session, ticker)
        if result.data:
            context_parts.append(f"Financeiros {ticker} (3 periodos): {_summarize_financials(result)}")
            tools_used.append("get_company_financials_3p")

        # Flags
        result = get_company_flags(session, ticker)
        if result.data:
            context_parts.append(f"Flags {ticker}: {result.data}")
            tools_used.append("get_company_flags")

        # Market snapshot
        result = get_market_snapshot(session, ticker)
        if result.data:
            context_parts.append(f"Mercado {ticker}: {result.data}")
            tools_used.append("get_market_snapshot")

    context = "\n".join(context_parts) if context_parts else "Nenhum dado especifico encontrado."
    return context, tools_used


def _summarize_financials(result: ToolResult) -> str:
    """Summarize financials to avoid oversized context."""
    if not result.data or not isinstance(result.data, dict):
        return str(result.data)
    # Show only the most important metrics
    important = [
        "roic", "roe", "earnings_yield", "ebit_margin", "net_margin",
        "gross_margin", "debt_to_ebitda", "cash_conversion",
    ]
    summary = {}
    for key in important:
        if key in result.data:
            summary[key] = result.data[key]
    return str(summary) if summary else str(dict(list(result.data.items())[:8]))


def _gather_rag_context(
    session: Session,
    query: str,
) -> str:
    """Retrieve relevant chunks from RAG embeddings store."""
    try:
        from q3_ai_assistant.config import settings
        from q3_ai_assistant.rag.embedder import Embedder
        from q3_ai_assistant.rag.retriever import Retriever

        if not settings.openai_api_key:
            return ""

        embedder = Embedder(settings)
        retriever = Retriever(embedder)
        results = retriever.search(session, query, top_k=3, threshold=0.4)

        if not results:
            return ""

        chunks = [
            f"[{r.entity_type}/{r.entity_id}] {r.chunk_text}"
            for r in results
        ]
        return "Contexto RAG:\n" + "\n---\n".join(chunks)
    except Exception:
        logger.debug("RAG retrieval skipped (not available)")
        return ""


def handle_free_chat(
    db_session: Session,
    user_message: str,
    cascade: CascadeRouter,
    *,
    history: list[dict] | None = None,
) -> FreeChatResult:
    """Process a free-chat message using tools + RAG + LLM synthesis."""
    # 1. Detect intent
    intent = _detect_intent(user_message)
    logger.info("Free chat intent: %s", intent)

    # 2. Gather internal tool context
    tool_context, tools_used = _gather_tool_context(db_session, intent)

    # 3. Gather RAG context
    rag_context = _gather_rag_context(db_session, user_message)

    # 4. Build context block
    full_context = tool_context
    if rag_context:
        full_context += "\n\n" + rag_context

    # 5. Build conversation prompt
    system_prompt = FREE_CHAT_SYSTEM_PROMPT.format(context=full_context)

    # Include recent history for conversational continuity
    user_prompt = user_message
    if history:
        history_text = "\n".join(
            f"{'Usuario' if h['role'] == 'user' else 'Assistente'}: {h['content']}"
            for h in history[-6:]  # Last 3 exchanges
        )
        user_prompt = f"Historico recente:\n{history_text}\n\nUsuario: {user_message}"

    # 6. Call LLM
    result = cascade.generate(system_prompt, user_prompt)

    return FreeChatResult(
        response=result.response.text,
        tools_used=tools_used,
        provider_used=result.provider_used,
        model_used=result.model_used,
        tokens_used=result.response.tokens_used,
        cost_usd=result.response.cost_usd,
    )
