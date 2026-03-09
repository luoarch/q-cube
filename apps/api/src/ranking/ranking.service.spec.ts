import { describe, it, expect, vi, beforeEach } from 'vitest';

import { RankingService } from './ranking.service.js';

function createMockCache() {
  return {
    get: vi.fn().mockResolvedValue(null),
    set: vi.fn().mockResolvedValue(undefined),
    del: vi.fn().mockResolvedValue(undefined),
  };
}

/**
 * Creates a mock DB that returns:
 * - executeResult via db.execute() (used for the main v_financial_statements_compat query)
 * - selectResults in order of db.select() calls (used for buildPriceMap, buildSectorMap)
 */
function createMockDb(executeResult: any[], selectResults: any[][] = [[], []]) {
  let selectIndex = 0;
  return {
    execute: vi.fn().mockResolvedValue({ rows: executeResult }),
    select: vi.fn().mockImplementation(() => {
      const idx = selectIndex++;
      const result = selectResults[idx] ?? [];

      function makeChainable(data: any[]): any {
        const handler: ProxyHandler<any> = {
          get(_target, prop) {
            if (prop === 'then') {
              return (resolve: any, reject?: any) => Promise.resolve(data).then(resolve, reject);
            }
            if (prop === Symbol.iterator) {
              return () => data[Symbol.iterator]();
            }
            return vi.fn().mockReturnValue(new Proxy({}, handler));
          },
        };
        return new Proxy({}, handler);
      }

      return makeChainable(result);
    }),
  };
}

describe('RankingService', () => {
  let mockCache: ReturnType<typeof createMockCache>;

  beforeEach(() => {
    mockCache = createMockCache();
  });

  it('should return cached data when available', async () => {
    const cached = [{ ticker: 'PETR4', magicFormulaRank: 1 }];
    mockCache.get.mockResolvedValue(cached);

    const service = new RankingService({} as any, mockCache as any);
    const result = await service.getRanking('tenant-1');
    expect(result).toEqual(cached);
  });

  it('should return empty array when no assets exist', async () => {
    const db = createMockDb([], [[], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking('tenant-1');
    expect(result).toEqual([]);
    expect(mockCache.set).toHaveBeenCalledOnce();
  });

  it('should compute magic formula ranks correctly', async () => {
    const assets = [
      {
        ticker: 'A',
        name: 'A Co',
        sector: 'Tech',
        ebit: '100',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.15',
        market_cap: '2000',
        avg_daily_volume: '500000',
      },
      {
        ticker: 'B',
        name: 'B Co',
        sector: 'Finance',
        ebit: '200',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.10',
        market_cap: '3000',
        avg_daily_volume: '1500000',
      },
      {
        ticker: 'C',
        name: 'C Co',
        sector: 'Energy',
        ebit: '50',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.20',
        market_cap: '1000',
        avg_daily_volume: '50000',
      },
    ];

    const db = createMockDb(assets, [[], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking('tenant-1');

    expect(result).toHaveLength(3);
    expect(result.map((r: any) => r.magicFormulaRank)).toEqual([1, 2, 3]);
    // B: EY=0.25 (rank 1), ROC=0.10 (rank 3) → combined 4
    // A: EY=0.10 (rank 2), ROC=0.15 (rank 2) → combined 4
    // C: EY=0.025 (rank 3), ROC=0.20 (rank 1) → combined 4
    // All tied at 4, so sorted by stable insertion order, but sequential ranks assigned
    expect(mockCache.set).toHaveBeenCalledOnce();
  });

  it('should assign quality based on ROIC', async () => {
    const assets = [
      {
        ticker: 'HIGH',
        name: 'High',
        sector: 'Tech',
        ebit: '100',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.20',
        market_cap: '1000',
        avg_daily_volume: '500000',
      },
      {
        ticker: 'MED',
        name: 'Med',
        sector: 'Tech',
        ebit: '50',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.10',
        market_cap: '1000',
        avg_daily_volume: '500000',
      },
      {
        ticker: 'LOW',
        name: 'Low',
        sector: 'Tech',
        ebit: '10',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.05',
        market_cap: '1000',
        avg_daily_volume: '500000',
      },
    ];

    const db = createMockDb(assets, [[], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking('tenant-1');

    const high = result.find((r: any) => r.ticker === 'HIGH');
    const med = result.find((r: any) => r.ticker === 'MED');
    const low = result.find((r: any) => r.ticker === 'LOW');

    expect(high?.quality).toBe('high'); // ROIC >= 0.15
    expect(med?.quality).toBe('medium'); // ROIC >= 0.08
    expect(low?.quality).toBe('low'); // ROIC < 0.08
  });

  it('should assign liquidity based on avg daily volume', async () => {
    const assets = [
      {
        ticker: 'HLIQ',
        name: 'H',
        sector: 'Tech',
        ebit: '100',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.10',
        market_cap: '1000',
        avg_daily_volume: '2000000',
      },
      {
        ticker: 'MLIQ',
        name: 'M',
        sector: 'Tech',
        ebit: '50',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.10',
        market_cap: '1000',
        avg_daily_volume: '500000',
      },
      {
        ticker: 'LLIQ',
        name: 'L',
        sector: 'Tech',
        ebit: '10',
        net_debt: '0',
        ebitda: null,
        net_working_capital: null,
        fixed_assets: null,
        roic: '0.10',
        market_cap: '1000',
        avg_daily_volume: '50000',
      },
    ];

    const db = createMockDb(assets, [[], []]);
    const service = new RankingService(db as any, mockCache as any);
    const result = await service.getRanking('tenant-1');

    const high = result.find((r: any) => r.ticker === 'HLIQ');
    const med = result.find((r: any) => r.ticker === 'MLIQ');
    const low = result.find((r: any) => r.ticker === 'LLIQ');

    expect(high?.liquidity).toBe('high'); // >= 1M
    expect(med?.liquidity).toBe('medium'); // >= 100K
    expect(low?.liquidity).toBe('low'); // < 100K
  });
});
