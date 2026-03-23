"""Universe classification policy — sector mapping and issuer overrides.

POLICY_VERSION tracks breaking changes to classification rules.
Any change that reclassifies an issuer MUST bump this version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import (
    ClassificationRuleCode,
    DedicatedStrategyType,
    PermanentExclusionReason,
    UniverseClass,
)

POLICY_VERSION = "v1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnmatchedSectorError(Exception):
    """Raised when a SETOR_ATIV value has no entry in SECTOR_UNIVERSE_MAP."""

    def __init__(self, sector: str, cvm_code: str) -> None:
        self.sector = sector
        self.cvm_code = cvm_code
        super().__init__(
            f"No universe mapping for sector {sector!r} (issuer {cvm_code})"
        )


class NullSectorWithoutOverrideError(Exception):
    """Raised when an issuer has NULL sector and no issuer override."""

    def __init__(self, cvm_code: str) -> None:
        self.cvm_code = cvm_code
        super().__init__(
            f"Issuer {cvm_code} has NULL sector and no override defined"
        )


# ---------------------------------------------------------------------------
# SectorPolicy dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectorPolicy:
    universe_class: UniverseClass
    dedicated_strategy_type: Optional[DedicatedStrategyType] = None
    permanent_exclusion_reason: Optional[PermanentExclusionReason] = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Helpers for building policies (reduce verbosity)
# ---------------------------------------------------------------------------


def _core(reason: str) -> SectorPolicy:
    return SectorPolicy(
        universe_class=UniverseClass.CORE_ELIGIBLE,
        reason=reason,
    )


def _dedicated(
    strategy: DedicatedStrategyType, reason: str
) -> SectorPolicy:
    return SectorPolicy(
        universe_class=UniverseClass.DEDICATED_STRATEGY_ONLY,
        dedicated_strategy_type=strategy,
        reason=reason,
    )


def _excluded(
    exclusion: PermanentExclusionReason, reason: str
) -> SectorPolicy:
    return SectorPolicy(
        universe_class=UniverseClass.PERMANENTLY_EXCLUDED,
        permanent_exclusion_reason=exclusion,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# SECTOR_UNIVERSE_MAP — 56 entries (exact SETOR_ATIV strings from CVM)
# ---------------------------------------------------------------------------

SECTOR_UNIVERSE_MAP: dict[str, SectorPolicy] = {
    # ── CORE_ELIGIBLE (37) ────────────────────────────────────────────
    "Agricultura (Açúcar, Álcool e Cana)": _core(
        "Agribusiness — standard operating company"
    ),
    "Alimentos": _core("Food production — standard operating company"),
    "Bebidas e Fumo": _core(
        "Beverages & tobacco — standard operating company"
    ),
    "Brinquedos e Lazer": _core(
        "Toys & leisure — standard operating company"
    ),
    "Comunicação e Informática": _core(
        "IT & communications — standard operating company"
    ),
    "Educação": _core("Education — standard operating company"),
    "Embalagens": _core("Packaging — standard operating company"),
    "Emp. Adm. Part. - Agricultura (Açúcar, Álcool e Cana)": _core(
        "Holding — agribusiness subsidiary"
    ),
    "Emp. Adm. Part. - Alimentos": _core("Holding — food subsidiary"),
    "Emp. Adm. Part. - Brinquedos e Lazer": _core(
        "Holding — toys & leisure subsidiary"
    ),
    "Emp. Adm. Part. - Comunicação e Informática": _core(
        "Holding — IT & communications subsidiary"
    ),
    "Emp. Adm. Part. - Educação": _core("Holding — education subsidiary"),
    "Emp. Adm. Part. - Energia Elétrica": _core(
        "Holding — electric utility subsidiary"
    ),
    "Emp. Adm. Part. - Extração Mineral": _core(
        "Holding — mining subsidiary"
    ),
    "Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças": _core(
        "Holding — machinery & vehicles subsidiary"
    ),
    "Emp. Adm. Part. - Metalurgia e Siderurgia": _core(
        "Holding — metals & steel subsidiary"
    ),
    "Emp. Adm. Part. - Papel e Celulose": _core(
        "Holding — pulp & paper subsidiary"
    ),
    "Emp. Adm. Part. - Petróleo e Gás": _core(
        "Holding — oil & gas subsidiary"
    ),
    "Emp. Adm. Part. - Saneamento, Serv. Água e Gás": _core(
        "Holding — water & gas utility subsidiary"
    ),
    "Emp. Adm. Part. - Serviços médicos": _core(
        "Holding — healthcare subsidiary"
    ),
    "Emp. Adm. Part. - Serviços Transporte e Logística": _core(
        "Holding — transport & logistics subsidiary"
    ),
    "Emp. Adm. Part. - Telecomunicações": _core(
        "Holding — telecom subsidiary"
    ),
    "Emp. Adm. Part. - Têxtil e Vestuário": _core(
        "Holding — textile & apparel subsidiary"
    ),
    "Energia Elétrica": _core(
        "Electric utility — standard operating company"
    ),
    "Extração Mineral": _core("Mining — standard operating company"),
    "Farmacêutico e Higiene": _core(
        "Pharma & hygiene — standard operating company"
    ),
    "Máquinas, Equipamentos, Veículos e Peças": _core(
        "Machinery & vehicles — standard operating company"
    ),
    "Metalurgia e Siderurgia": _core(
        "Metals & steel — standard operating company"
    ),
    "Papel e Celulose": _core(
        "Pulp & paper — standard operating company"
    ),
    "Petróleo e Gás": _core("Oil & gas — standard operating company"),
    "Petroquímicos e Borracha": _core(
        "Petrochemicals & rubber — standard operating company"
    ),
    "Reflorestamento": _core(
        "Reforestation — standard operating company"
    ),
    "Saneamento, Serv. Água e Gás": _core(
        "Water & gas utility — standard operating company"
    ),
    "Serviços Médicos": _core(
        "Healthcare services — standard operating company"
    ),
    "Serviços Transporte e Logística": _core(
        "Transport & logistics — standard operating company"
    ),
    "Telecomunicações": _core("Telecom — standard operating company"),
    "Têxtil e Vestuário": _core(
        "Textile & apparel — standard operating company"
    ),
    # ── DEDICATED_STRATEGY_ONLY / FINANCIAL (12) ─────────────────────
    "Arrendamento Mercantil": _dedicated(
        DedicatedStrategyType.FINANCIAL, "Leasing — financial institution"
    ),
    "Bancos": _dedicated(
        DedicatedStrategyType.FINANCIAL, "Banks — financial institution"
    ),
    "Bolsas de Valores/Mercadorias e Futuros": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Exchanges — financial institution",
    ),
    "Crédito Imobiliário": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Real-estate credit — financial institution",
    ),
    "Emp. Adm. Part. - Bancos": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Holding — bank subsidiary",
    ),
    "Emp. Adm. Part. - Crédito Imobiliário": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Holding — real-estate credit subsidiary",
    ),
    "Emp. Adm. Part. - Intermediação Financeira": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Holding — financial intermediation subsidiary",
    ),
    "Emp. Adm. Part. - Securitização de Recebíveis": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Holding — securitization subsidiary",
    ),
    "Emp. Adm. Part. - Seguradoras e Corretoras": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Holding — insurance & brokerage subsidiary",
    ),
    "Intermediação Financeira": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Financial intermediation — financial institution",
    ),
    "Securitização de Recebíveis": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Securitization — financial institution",
    ),
    "Seguradoras e Corretoras": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Insurance & brokerage — financial institution",
    ),
    # ── DEDICATED_STRATEGY_ONLY / REAL_ESTATE_DEVELOPMENT (2) ────────
    "Construção Civil, Mat. Constr. e Decoração": _dedicated(
        DedicatedStrategyType.REAL_ESTATE_DEVELOPMENT,
        "Construction & building materials — real-estate development",
    ),
    "Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração": _dedicated(
        DedicatedStrategyType.REAL_ESTATE_DEVELOPMENT,
        "Holding — construction subsidiary",
    ),
    # ── DEDICATED_STRATEGY_ONLY / UNCLASSIFIED_HOLDING (1) ───────────
    "Emp. Adm. Part. - Sem Setor Principal": _dedicated(
        DedicatedStrategyType.UNCLASSIFIED_HOLDING,
        "Holding without main sector — needs manual review",
    ),
    # ── PERMANENTLY_EXCLUDED (4) ─────────────────────────────────────
    "Comércio (Atacado e Varejo)": _excluded(
        PermanentExclusionReason.RETAIL_WHOLESALE,
        "Retail & wholesale — structurally incompatible with value metrics",
    ),
    "Emp. Adm. Part. - Comércio (Atacado e Varejo)": _excluded(
        PermanentExclusionReason.RETAIL_WHOLESALE,
        "Holding — retail & wholesale subsidiary",
    ),
    "Hospedagem e Turismo": _excluded(
        PermanentExclusionReason.TOURISM_HOSPITALITY,
        "Hospitality & tourism — structurally incompatible with value metrics",
    ),
    "Emp. Adm. Part. - Hospedagem e Turismo": _excluded(
        PermanentExclusionReason.TOURISM_HOSPITALITY,
        "Holding — hospitality & tourism subsidiary",
    ),
}

assert len(SECTOR_UNIVERSE_MAP) == 56, (
    f"Expected 56 sector entries, got {len(SECTOR_UNIVERSE_MAP)}"
)


# ---------------------------------------------------------------------------
# ISSUER_OVERRIDES — keyed by CVM code (str)
# ---------------------------------------------------------------------------

ISSUER_OVERRIDES: dict[str, SectorPolicy] = {
    # Airlines → PERMANENTLY_EXCLUDED
    "019569": _excluded(
        PermanentExclusionReason.AIRLINE,
        "GOL — airline, structurally incompatible",
    ),
    "024112": _excluded(
        PermanentExclusionReason.AIRLINE,
        "Azul — airline, structurally incompatible",
    ),
    # NULL-sector issuers
    "080225": _excluded(
        PermanentExclusionReason.FOREIGN_RETAIL,
        "Éxito — Colombian retail, foreign listing",
    ),
    "080187": _core("Aura Minerals — mining, NULL sector override"),
    "080195": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "G2D — investment vehicle, NULL sector override",
    ),
    "080020": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "GP — investment vehicle, NULL sector override",
    ),
    "080217": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "Inter&Co — digital bank, NULL sector override",
    ),
    "IBOV": _excluded(
        PermanentExclusionReason.NOT_A_COMPANY,
        "IBOV index — not a company",
    ),
    "080233": _core("JBS NV — food production, NULL sector override"),
    "080152": _dedicated(
        DedicatedStrategyType.FINANCIAL,
        "PPLA — investment vehicle, NULL sector override",
    ),
    # Construction allowlist — override REAL_ESTATE_DEVELOPMENT → CORE_ELIGIBLE
    "021091": _core("Dexco — building materials, construction override"),
    "005762": _core("Eternit — building materials, construction override"),
    "005770": _core("Eucatex — building materials, construction override"),
    "025992": _core(
        "Intercement — cement producer, construction override"
    ),
    "009717": _core(
        "Portuense — building materials, construction override"
    ),
    "024236": _core(
        "Priner — industrial services, construction override"
    ),
    "010880": _core(
        "Sondotecnica — engineering services, construction override"
    ),
    "026255": _core("Tigre — building materials, construction override"),
    "022780": _core(
        "Unicasa — furniture/cabinetry, construction override"
    ),
    "027189": _core(
        "Votorantim Cimentos — cement producer, construction override"
    ),
    # Sem Setor allowlist — override UNCLASSIFIED_HOLDING → CORE_ELIGIBLE
    "020044": _core(
        "CSU Digital — tech services, sem-setor override"
    ),
    "016632": _core(
        "Dexxos — chemicals, sem-setor override"
    ),
    "025712": _core(
        "GPS — facility services, sem-setor override"
    ),
    "022586": _core(
        "MLOG — logistics, sem-setor override"
    ),
    "027600": _core(
        "Porto Serviço — services, sem-setor override"
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_sector(sector: str | None) -> str | None:
    """Strip whitespace from sector string. Returns None for None."""
    if sector is None:
        return None
    return sector.strip()


def lookup_policy(
    cvm_code: str, sector: str | None
) -> tuple[SectorPolicy, ClassificationRuleCode]:
    """Classify an issuer by CVM code and SETOR_ATIV.

    Resolution order:
        1. ISSUER_OVERRIDES (by cvm_code)
        2. SECTOR_UNIVERSE_MAP (by normalized sector)

    Returns:
        (SectorPolicy, ClassificationRuleCode) tuple.

    Raises:
        NullSectorWithoutOverrideError: if sector is None and no override exists.
        UnmatchedSectorError: if sector has no entry in SECTOR_UNIVERSE_MAP.
    """
    # 1. Check issuer overrides first
    if cvm_code in ISSUER_OVERRIDES:
        return ISSUER_OVERRIDES[cvm_code], ClassificationRuleCode.ISSUER_OVERRIDE

    # 2. Normalize and check sector map
    normalized = normalize_sector(sector)

    if normalized is None:
        raise NullSectorWithoutOverrideError(cvm_code)

    policy = SECTOR_UNIVERSE_MAP.get(normalized)
    if policy is None:
        raise UnmatchedSectorError(normalized, cvm_code)

    return policy, ClassificationRuleCode.SECTOR_MAP
