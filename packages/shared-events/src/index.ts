export type StrategyCompletedEvent = {
  type: "strategy.completed";
  tenantId: string;
  runId: string;
  createdAt: string;
};

export type StrategyFailedEvent = {
  type: "strategy.failed";
  tenantId: string;
  runId: string;
  reason: string;
  createdAt: string;
};

export type Q3Event = StrategyCompletedEvent | StrategyFailedEvent;
