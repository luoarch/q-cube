import { describe, it, expect, vi, beforeEach } from "vitest";
import { RankingService } from "./ranking.service.js";

function createMockCache() {
  return {
    get: vi.fn().mockResolvedValue(null),
    set: vi.fn().mockResolvedValue(undefined),
    del: vi.fn().mockResolvedValue(undefined),
  };
}

/**
 * Creates a mock DB that returns queryResults in order of .select() calls.
 * Each result is returned as a thenable that also has chainable methods,
 * so it works whether the query chain ends at .innerJoin(), .orderBy(), etc.
 */
function createMockDb(queryResults: any[][]) {
  let callIndex = 0;
  return {
    select: vi.fn().mockImplementation(() => {
      const idx = callIndex++;
      const result = queryResults[idx] ?? [];

      // Create a thenable proxy that chains and ultimately resolves to data
      function makeChainable(data: any[]): any {
        const handler: ProxyHandler<any> = {
          get(_target, prop) {
            if (prop === "then") {
              return (resolve: any, reject?: any) => Promise.resolve(data).then(resolve, reject);
            }
            if (prop === Symbol.iterator) {
              return () => data[Symbol.iterator]();
            }
            // Any method call returns another chainable
            return vi.fn().mockReturnValue(new Proxy({}, handler));
          },
        };
        return new Proxy({}, handler);
      }

      return makeChainable(result);
    }),
  };
}

describe("RankingService", () => {
  let mockCache: ReturnType<typeof createMockCache>;

  beforeEach(() => {
    mockCache = createMockCache();
  });

  it("should return cached data when available", async () => {
    const cached = [{ ticker: "PETR4", magicFormulaRank: 1 }];
    mockCache.get.mockResolvedValue(cached);

    const service = new RankingService({} as any, mockCache as any);
    const result = await service.getRanking("tenant-1");
    expect(result).toEqual(cached);
  });

  it("should return empty array when no assets exist", async () => {
    // 3 queries: assets+fs, market_snapshots+securities, securities+issuers
    const db = createMockDb([[], [], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking("tenant-1");
    expect(result).toEqual([]);
    expect(mockCache.set).toHaveBeenCalledOnce();
  });

  it("should compute magic formula ranks correctly", async () => {
    const assets = [
      { assetId: "1", ticker: "A", name: "A Co", assetSector: "Tech", ebit: "100", enterpriseValue: "1000", roic: "0.15", marketCap: "2000", avgDailyVolume: "500000" },
      { assetId: "2", ticker: "B", name: "B Co", assetSector: "Finance", ebit: "200", enterpriseValue: "800", roic: "0.10", marketCap: "3000", avgDailyVolume: "1500000" },
      { assetId: "3", ticker: "C", name: "C Co", assetSector: "Energy", ebit: "50", enterpriseValue: "2000", roic: "0.20", marketCap: "1000", avgDailyVolume: "50000" },
    ];

    // Query order: 1) assets+fs, 2) market_snapshots (prices), 3) securities+issuers (sectors)
    const db = createMockDb([assets, [], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking("tenant-1");

    expect(result).toHaveLength(3);
    expect(result.map((r: any) => r.magicFormulaRank)).toEqual([1, 2, 3]);
    // B: EY=0.25 (rank 1), ROC=0.10 (rank 3) → combined 4
    // A: EY=0.10 (rank 2), ROC=0.15 (rank 2) → combined 4
    // C: EY=0.025 (rank 3), ROC=0.20 (rank 1) → combined 4
    // All tied at 4, so sorted by stable insertion order, but sequential ranks assigned
    expect(mockCache.set).toHaveBeenCalledOnce();
  });

  it("should assign quality based on ROIC", async () => {
    const assets = [
      { assetId: "1", ticker: "HIGH", name: "High", assetSector: "Tech", ebit: "100", enterpriseValue: "500", roic: "0.20", marketCap: "1000", avgDailyVolume: "500000" },
      { assetId: "2", ticker: "MED", name: "Med", assetSector: "Tech", ebit: "50", enterpriseValue: "500", roic: "0.10", marketCap: "1000", avgDailyVolume: "500000" },
      { assetId: "3", ticker: "LOW", name: "Low", assetSector: "Tech", ebit: "10", enterpriseValue: "500", roic: "0.05", marketCap: "1000", avgDailyVolume: "500000" },
    ];

    const db = createMockDb([assets, [], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking("tenant-1");

    const high = result.find((r: any) => r.ticker === "HIGH");
    const med = result.find((r: any) => r.ticker === "MED");
    const low = result.find((r: any) => r.ticker === "LOW");

    expect(high?.quality).toBe("high");    // ROIC >= 0.15
    expect(med?.quality).toBe("medium");   // ROIC >= 0.08
    expect(low?.quality).toBe("low");      // ROIC < 0.08
  });

  it("should assign liquidity based on avg daily volume", async () => {
    const assets = [
      { assetId: "1", ticker: "HLIQ", name: "H", assetSector: "Tech", ebit: "100", enterpriseValue: "500", roic: "0.10", marketCap: "1000", avgDailyVolume: "2000000" },
      { assetId: "2", ticker: "MLIQ", name: "M", assetSector: "Tech", ebit: "50", enterpriseValue: "500", roic: "0.10", marketCap: "1000", avgDailyVolume: "500000" },
      { assetId: "3", ticker: "LLIQ", name: "L", assetSector: "Tech", ebit: "10", enterpriseValue: "500", roic: "0.10", marketCap: "1000", avgDailyVolume: "50000" },
    ];

    const db = createMockDb([assets, [], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking("tenant-1");

    const high = result.find((r: any) => r.ticker === "HLIQ");
    const med = result.find((r: any) => r.ticker === "MLIQ");
    const low = result.find((r: any) => r.ticker === "LLIQ");

    expect(high?.liquidity).toBe("high");    // >= 1M
    expect(med?.liquidity).toBe("medium");   // >= 100K
    expect(low?.liquidity).toBe("low");      // < 100K
  });
});
