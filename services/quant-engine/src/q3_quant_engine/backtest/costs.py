"""Transaction cost and slippage models for backtesting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    fixed_cost_per_trade: float = 0.0
    proportional_cost: float = 0.0005  # 5 bps (B3 realistic)
    slippage_bps: float = 10.0  # 10 bps

    def total_cost(self, trade_value: float) -> float:
        return (
            self.fixed_cost_per_trade
            + abs(trade_value) * self.proportional_cost
            + abs(trade_value) * (self.slippage_bps / 10_000)
        )


BRAZIL_REALISTIC = CostModel(proportional_cost=0.0005, slippage_bps=10.0)
CONSERVATIVE = CostModel(fixed_cost_per_trade=5.0, proportional_cost=0.001, slippage_bps=20.0)
