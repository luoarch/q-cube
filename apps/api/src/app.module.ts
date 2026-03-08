import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';

import { AIModule } from './ai/ai.module.js';
import { AssetModule } from './asset/asset.module.js';
import { AuthModule } from './auth/auth.module.js';
import { CommonModule } from './common/common.module.js';
import { validateEnv } from './config/env.schema.js';
import { DashboardModule } from './dashboard/dashboard.module.js';
import { DatabaseModule } from './database/database.module.js';
import { HealthModule } from './health/health.module.js';
import { PortfolioModule } from './portfolio/portfolio.module.js';
import { RankingModule } from './ranking/ranking.module.js';
import { RedisModule } from './redis/redis.module.js';
import { StrategyModule } from './strategy/strategy.module.js';
import { UniverseModule } from './universe/universe.module.js';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      validate: validateEnv,
    }),
    ThrottlerModule.forRoot({
      throttlers: [{ ttl: 60_000, limit: 100 }],
    }),
    DatabaseModule,
    RedisModule,
    CommonModule,
    HealthModule,
    AuthModule,
    StrategyModule,
    RankingModule,
    DashboardModule,
    UniverseModule,
    AssetModule,
    PortfolioModule,
    AIModule,
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
  ],
})
export class AppModule {}
