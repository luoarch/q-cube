import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { ThrottlerGuard, ThrottlerModule } from "@nestjs/throttler";
import { APP_GUARD } from "@nestjs/core";
import { validateEnv } from "./config/env.schema.js";
import { DatabaseModule } from "./database/database.module.js";
import { RedisModule } from "./redis/redis.module.js";
import { CommonModule } from "./common/common.module.js";
import { HealthModule } from "./health/health.module.js";
import { StrategyModule } from "./strategy/strategy.module.js";
import { RankingModule } from "./ranking/ranking.module.js";
import { DashboardModule } from "./dashboard/dashboard.module.js";
import { UniverseModule } from "./universe/universe.module.js";
import { AssetModule } from "./asset/asset.module.js";
import { PortfolioModule } from "./portfolio/portfolio.module.js";
import { AIModule } from "./ai/ai.module.js";
import { AuthModule } from "./auth/auth.module.js";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      validate: validateEnv
    }),
    ThrottlerModule.forRoot({
      throttlers: [{ ttl: 60_000, limit: 100 }]
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
    AIModule
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard
    }
  ]
})
export class AppModule {}
