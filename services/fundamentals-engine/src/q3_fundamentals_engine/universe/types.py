"""Universe classification types for the investable universe engine."""
from __future__ import annotations

import enum


class UniverseClass(str, enum.Enum):
    CORE_ELIGIBLE = "CORE_ELIGIBLE"
    DEDICATED_STRATEGY_ONLY = "DEDICATED_STRATEGY_ONLY"
    PERMANENTLY_EXCLUDED = "PERMANENTLY_EXCLUDED"


class DedicatedStrategyType(str, enum.Enum):
    FINANCIAL = "FINANCIAL"
    REAL_ESTATE_DEVELOPMENT = "REAL_ESTATE_DEVELOPMENT"
    UNCLASSIFIED_HOLDING = "UNCLASSIFIED_HOLDING"


class PermanentExclusionReason(str, enum.Enum):
    RETAIL_WHOLESALE = "RETAIL_WHOLESALE"
    AIRLINE = "AIRLINE"
    TOURISM_HOSPITALITY = "TOURISM_HOSPITALITY"
    FOREIGN_RETAIL = "FOREIGN_RETAIL"
    NOT_A_COMPANY = "NOT_A_COMPANY"


class ClassificationRuleCode(str, enum.Enum):
    SECTOR_MAP = "SECTOR_MAP"
    ISSUER_OVERRIDE = "ISSUER_OVERRIDE"
