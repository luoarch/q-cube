import { describe, it, expect, vi } from 'vitest';

import { CacheService } from './cache.service.js';

function createMockRedis() {
  return {
    get: vi.fn().mockResolvedValue(null),
    set: vi.fn().mockResolvedValue('OK'),
    keys: vi.fn().mockResolvedValue([]),
    del: vi.fn().mockResolvedValue(0),
  };
}

describe('CacheService', () => {
  it('should return null for cache miss', async () => {
    const redis = createMockRedis();
    const service = new CacheService(redis as any);
    const result = await service.get('missing-key');
    expect(result).toBeNull();
  });

  it('should return parsed JSON for cache hit', async () => {
    const redis = createMockRedis();
    const data = { foo: 'bar', count: 42 };
    redis.get.mockResolvedValue(JSON.stringify(data));

    const service = new CacheService(redis as any);
    const result = await service.get('my-key');
    expect(result).toEqual(data);
  });

  it('should set value with TTL', async () => {
    const redis = createMockRedis();
    const service = new CacheService(redis as any);
    await service.set('key', { data: true }, 300);

    expect(redis.set).toHaveBeenCalledWith('key', JSON.stringify({ data: true }), 'EX', 300);
  });

  it('should delete keys matching pattern', async () => {
    const redis = createMockRedis();
    redis.keys.mockResolvedValue(['q3:ranking:t1', 'q3:ranking:t2']);

    const service = new CacheService(redis as any);
    await service.del('q3:ranking:*');

    expect(redis.keys).toHaveBeenCalledWith('q3:ranking:*');
    expect(redis.del).toHaveBeenCalledWith('q3:ranking:t1', 'q3:ranking:t2');
  });

  it('should not call del when no keys match', async () => {
    const redis = createMockRedis();
    redis.keys.mockResolvedValue([]);

    const service = new CacheService(redis as any);
    await service.del('nonexistent:*');

    expect(redis.del).not.toHaveBeenCalled();
  });

  it('should return null on parse error', async () => {
    const redis = createMockRedis();
    redis.get.mockResolvedValue('not-valid-json{');

    const service = new CacheService(redis as any);
    const result = await service.get('bad-key');
    expect(result).toBeNull();
  });
});
