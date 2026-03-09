import { Inject, Injectable, Logger } from '@nestjs/common';
import { ThrottlerGuard } from '@nestjs/throttler';
import { eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { tenants } from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { ExecutionContext } from '@nestjs/common';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';
import type { ThrottlerRequest } from '@nestjs/throttler';

/**
 * Per-tenant rate limiter that reads `rate_limit_rpm` from the tenants table.
 *
 * Falls back to the global ThrottlerModule default (100 rpm) when tenant
 * config is missing or the request is unauthenticated.
 *
 * NestJS Throttler v6 resolves `limit` before calling `handleRequest`,
 * so we override `handleRequest` to substitute the per-tenant limit.
 */
@Injectable()
export class TenantThrottlerGuard extends ThrottlerGuard {
  private readonly log = new Logger(TenantThrottlerGuard.name);

  /** Tenant RPM cache: tenantId → { rpm, fetchedAt } */
  private readonly cache = new Map<string, { rpm: number; fetchedAt: number }>();

  private static readonly CACHE_TTL_MS = 60_000; // 1 min

  @Inject(DB) private readonly drizzle!: NodePgDatabase<typeof schema>;

  /**
   * Override handleRequest to substitute per-tenant limit before
   * delegating to the parent guard's storage + header logic.
   */
  protected async handleRequest(requestProps: ThrottlerRequest): Promise<boolean> {
    const req = requestProps.context.switchToHttp().getRequest();
    const tenantId = req.tenantId as string | undefined;

    if (tenantId) {
      const rpm = await this.getTenantRpm(tenantId);
      requestProps = { ...requestProps, limit: rpm };
    }

    return super.handleRequest(requestProps);
  }

  private async getTenantRpm(tenantId: string): Promise<number> {
    const now = Date.now();
    const cached = this.cache.get(tenantId);
    if (cached && now - cached.fetchedAt < TenantThrottlerGuard.CACHE_TTL_MS) {
      return cached.rpm;
    }

    try {
      const rows = await this.drizzle
        .select({ rateLimitRpm: tenants.rateLimitRpm })
        .from(tenants)
        .where(eq(tenants.id, tenantId))
        .limit(1);

      const rpm = rows[0]?.rateLimitRpm ?? 100;
      this.cache.set(tenantId, { rpm, fetchedAt: now });
      return rpm;
    } catch (err) {
      this.log.warn(`Failed to fetch tenant rate limit: ${err}`);
      return 100;
    }
  }
}
