"""Official Q3 temporal split definitions.

Defines canonical IS/OOS periods for the Q3 platform.
These splits are the ONLY valid configurations for research.
Using OOS data for parameter tuning is explicitly forbidden.

Reference: docs/research-validation-protocol.md, Section 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TemporalSplit:
    """An immutable temporal split definition."""
    name: str
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date
    embargo_days: int = 21  # gap between IS and OOS

    def validate(self) -> None:
        """Raise ValueError if the split is inconsistent."""
        if self.is_start >= self.is_end:
            raise ValueError(f"IS start ({self.is_start}) must be before IS end ({self.is_end})")
        if self.oos_start >= self.oos_end:
            raise ValueError(f"OOS start ({self.oos_start}) must be before OOS end ({self.oos_end})")
        if self.is_end >= self.oos_start:
            raise ValueError(f"IS end ({self.is_end}) must be before OOS start ({self.oos_start})")
        gap = (self.oos_start - self.is_end).days
        if gap < self.embargo_days:
            raise ValueError(f"Gap between IS and OOS ({gap}d) is less than embargo ({self.embargo_days}d)")


# --- Official Q3 Splits ---
# These are the canonical splits. Research must use one of these.
# OOS periods are FROZEN — never tune parameters on OOS data.

SPLIT_FULL = TemporalSplit(
    name="full",
    is_start=date(2015, 1, 1),
    is_end=date(2023, 12, 31),
    oos_start=date(2024, 2, 1),
    oos_end=date(2025, 12, 31),
    embargo_days=21,
)

SPLIT_SHORT = TemporalSplit(
    name="short",
    is_start=date(2019, 1, 1),
    is_end=date(2023, 6, 30),
    oos_start=date(2023, 8, 1),
    oos_end=date(2025, 12, 31),
    embargo_days=21,
)

SPLIT_RECENT = TemporalSplit(
    name="recent",
    is_start=date(2021, 1, 1),
    is_end=date(2024, 6, 30),
    oos_start=date(2024, 8, 1),
    oos_end=date(2025, 12, 31),
    embargo_days=21,
)

# Registry of all official splits
OFFICIAL_SPLITS: dict[str, TemporalSplit] = {
    "full": SPLIT_FULL,
    "short": SPLIT_SHORT,
    "recent": SPLIT_RECENT,
}


def get_split(name: str) -> TemporalSplit:
    """Get an official split by name. Raises KeyError if not found."""
    if name not in OFFICIAL_SPLITS:
        raise KeyError(f"Unknown split '{name}'. Valid: {list(OFFICIAL_SPLITS.keys())}")
    return OFFICIAL_SPLITS[name]


def validate_not_tuning_on_oos(
    config_start: date,
    config_end: date,
    split: TemporalSplit,
) -> bool:
    """Check that a backtest config doesn't use OOS data for tuning.

    Returns True if the config period is entirely within IS.
    Returns False if it overlaps with OOS (potential data snooping).
    """
    return config_end <= split.is_end
