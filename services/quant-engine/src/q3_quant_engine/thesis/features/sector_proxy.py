"""Sector proxy maps for commodity exposure dimensions.

Maps CVM SETOR_ATIV values to 0-100 proxy scores for direct and indirect
commodity exposure. Includes "Emp. Adm. Part." (holding company) variants.

CVM cadastro only provides sector (SETOR_ATIV), not subsector. So lookups
are sector-only. Subsector is accepted for interface compatibility but
currently unused.

Maps are versioned. The version string is included in ScoreProvenance so
changes are traceable across runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_quant_engine.thesis.types import ScoreConfidence, ScoreProvenance, ScoreSourceType

SECTOR_PROXY_VERSION = "sector-proxy-v2"

DEFAULT_PROXY_SCORE = 10.0


@dataclass(frozen=True)
class SectorProxyEntry:
    sector: str
    score: float
    rationale: str


# ---------------------------------------------------------------------------
# Direct commodity exposure proxy map
# Conservative: only sectors with clear commodity production/extraction.
# Each CVM SETOR_ATIV has a plain and "Emp. Adm. Part." variant.
# ---------------------------------------------------------------------------

DIRECT_COMMODITY_MAP: list[SectorProxyEntry] = [
    # Mining
    SectorProxyEntry("Extração Mineral", 90.0,
                     "Extracao direta de minerio — exposicao pura a commodities"),
    SectorProxyEntry("Emp. Adm. Part. - Extração Mineral", 90.0,
                     "Holding de extracao mineral — exposicao direta"),

    # Oil & gas
    SectorProxyEntry("Petróleo e Gás", 85.0,
                     "Producao/refino de petroleo/gas — exposicao direta forte"),
    SectorProxyEntry("Emp. Adm. Part. - Petróleo e Gás", 85.0,
                     "Holding de petroleo/gas — exposicao direta"),

    # Steel & metals
    SectorProxyEntry("Metalurgia e Siderurgia", 80.0,
                     "Producao de aco/metais — exposicao direta a commodities metalicas"),
    SectorProxyEntry("Emp. Adm. Part. - Metalurgia e Siderurgia", 80.0,
                     "Holding de metalurgia/siderurgia — exposicao direta"),

    # Pulp & paper
    SectorProxyEntry("Papel e Celulose", 75.0,
                     "Producao de celulose — commodity florestal com preco global"),
    SectorProxyEntry("Emp. Adm. Part. - Papel e Celulose", 75.0,
                     "Holding de papel/celulose — exposicao direta"),

    # Agriculture / sugar & ethanol
    SectorProxyEntry("Agricultura (Açúcar, Álcool e Cana)", 70.0,
                     "Producao agropecuaria — exposicao direta a commodities agricolas"),
    SectorProxyEntry("Emp. Adm. Part. - Agricultura (Açúcar, Álcool e Cana)", 70.0,
                     "Holding de agricultura — exposicao direta"),

    # Petrochemicals
    SectorProxyEntry("Petroquímicos e Borracha", 65.0,
                     "Industria petroquimica — parcialmente ligada a commodities"),

    # Forestry
    SectorProxyEntry("Reflorestamento", 60.0,
                     "Silvicultura/reflorestamento — commodity florestal"),

    # Food processing (partially commodity-linked)
    SectorProxyEntry("Alimentos", 55.0,
                     "Processamento de alimentos — insumos de commodities agricolas"),
    SectorProxyEntry("Emp. Adm. Part. - Alimentos", 55.0,
                     "Holding de alimentos — insumos de commodities"),
]

# ---------------------------------------------------------------------------
# Indirect commodity exposure proxy map
# Less conservative: captures logistics, infra, equipment linked to cycle.
# ---------------------------------------------------------------------------

INDIRECT_COMMODITY_MAP: list[SectorProxyEntry] = [
    # Transport & logistics
    SectorProxyEntry("Serviços Transporte e Logística", 55.0,
                     "Logistica e transporte — captura volume de commodities movimentadas"),
    SectorProxyEntry("Emp. Adm. Part. - Serviços Transporte e Logística", 55.0,
                     "Holding de transporte — logistica de commodities"),

    # Machinery & equipment
    SectorProxyEntry("Máquinas, Equipamentos, Veículos e Peças", 50.0,
                     "Equipamentos industriais — demanda correlacionada com ciclo"),
    SectorProxyEntry("Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças", 50.0,
                     "Holding de maquinas/equipamentos — ciclo industrial"),

    # Packaging (commodity-linked inputs)
    SectorProxyEntry("Embalagens", 35.0,
                     "Embalagens — insumos parcialmente ligados a commodities"),

    # Sanitation / water / gas (energy infra)
    SectorProxyEntry("Saneamento, Serv. Água e Gás", 30.0,
                     "Infraestrutura de gas/agua — parcialmente ligada ao ciclo"),
    SectorProxyEntry("Emp. Adm. Part. - Saneamento, Serv. Água e Gás", 30.0,
                     "Holding de saneamento/gas"),
]


def _build_lookup(entries: list[SectorProxyEntry]) -> dict[str, SectorProxyEntry]:
    return {e.sector: e for e in entries}


_DIRECT_LOOKUP = _build_lookup(DIRECT_COMMODITY_MAP)
_INDIRECT_LOOKUP = _build_lookup(INDIRECT_COMMODITY_MAP)


def _make_provenance(
    entry: SectorProxyEntry | None,
    as_of_date: str,
) -> ScoreProvenance:
    if entry is not None:
        return ScoreProvenance(
            source_type=ScoreSourceType.SECTOR_PROXY,
            source_version=SECTOR_PROXY_VERSION,
            assessed_at=as_of_date,
            assessed_by=None,
            confidence=ScoreConfidence.LOW,
            evidence_ref=f"sector={entry.sector}",
        )
    return ScoreProvenance(
        source_type=ScoreSourceType.SECTOR_PROXY,
        source_version=SECTOR_PROXY_VERSION,
        assessed_at=as_of_date,
        assessed_by=None,
        confidence=ScoreConfidence.LOW,
        evidence_ref=None,
    )


def lookup_direct_commodity_proxy(
    sector: str | None,
    subsector: str | None,
    as_of_date: str,
) -> tuple[float, ScoreProvenance]:
    """Look up direct commodity exposure proxy score for a CVM sector.

    Returns (score, provenance). Unknown sectors get DEFAULT_PROXY_SCORE.
    """
    if sector is None:
        return DEFAULT_PROXY_SCORE, _make_provenance(None, as_of_date)

    entry = _DIRECT_LOOKUP.get(sector)
    score = entry.score if entry is not None else DEFAULT_PROXY_SCORE
    return score, _make_provenance(entry, as_of_date)


def lookup_indirect_commodity_proxy(
    sector: str | None,
    subsector: str | None,
    as_of_date: str,
) -> tuple[float, ScoreProvenance]:
    """Look up indirect commodity exposure proxy score for a CVM sector.

    Returns (score, provenance). Unknown sectors get DEFAULT_PROXY_SCORE.
    """
    if sector is None:
        return DEFAULT_PROXY_SCORE, _make_provenance(None, as_of_date)

    entry = _INDIRECT_LOOKUP.get(sector)
    score = entry.score if entry is not None else DEFAULT_PROXY_SCORE
    return score, _make_provenance(entry, as_of_date)
