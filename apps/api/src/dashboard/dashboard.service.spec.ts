import { describe, it, expect, vi } from 'vitest';

import { DashboardService } from './dashboard.service.js';

function createMockCache() {
  return {
    get: vi.fn().mockResolvedValue(null),
    set: vi.fn().mockResolvedValue(undefined),
    del: vi.fn().mockResolvedValue(undefined),
  };
}

function createMockRankingService(ranking: any[] = []) {
  return {
    getRanking: vi.fn().mockResolvedValue(ranking),
  };
}

describe('DashboardService', () => {
  it('should return cached data when available', async () => {
    const cached = { kpis: [], pipelineStatus: {}, topRanked: [], sectorDistribution: [] };
    const mockCache = createMockCache();
    mockCache.get.mockResolvedValue(cached);

    const service = new DashboardService({} as any, {} as any, mockCache as any);
    const result = await service.getSummary('tenant-1');

    expect(result).toEqual(cached);
  });

  it("should format sector distribution with 'value' field (not 'count')", async () => {
    const ranking = [
      { ticker: 'A', name: 'A', sector: 'Tech', magicFormulaRank: 1, price: null, change: null },
      { ticker: 'B', name: 'B', sector: 'Tech', magicFormulaRank: 2, price: null, change: null },
      { ticker: 'C', name: 'C', sector: 'Finance', magicFormulaRank: 3, price: null, change: null },
    ];

    let queryIdx = 0;
    const mockDb = {
      select: vi.fn().mockImplementation(() => ({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockImplementation(() => {
            queryIdx++;
            if (queryIdx <= 3) {
              // asset count, avg metrics, run count
              return Promise.resolve([{ count: 3, avgRoic: 0.15, avgEY: 0.08 }]);
            }
            // latest run
            return {
              orderBy: vi.fn().mockReturnValue({
                limit: vi.fn().mockResolvedValue([]),
              }),
            };
          }),
        }),
      })),
    };

    const mockCache = createMockCache();
    const mockRanking = createMockRankingService(ranking);

    const service = new DashboardService(mockDb as any, mockRanking as any, mockCache as any);
    const result = await service.getSummary('tenant-1');

    // Verify sectorDistribution uses 'value' not 'count'
    expect(result.sectorDistribution).toBeDefined();
    const tech = result.sectorDistribution.find((s: any) => s.name === 'Tech');
    expect(tech).toHaveProperty('value', 2);
    expect(tech).not.toHaveProperty('count');

    const finance = result.sectorDistribution.find((s: any) => s.name === 'Finance');
    expect(finance).toHaveProperty('value', 1);
  });
});
