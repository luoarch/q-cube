import { Global, Inject, Logger, Module, type OnModuleDestroy } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "../db/schema.js";
import { DB, DB_POOL } from "./database.constants.js";
import type { EnvConfig } from "../config/env.schema.js";

@Global()
@Module({
  providers: [
    {
      provide: DB_POOL,
      inject: [ConfigService],
      useFactory: (config: ConfigService<EnvConfig>) => {
        return new Pool({
          connectionString: config.get("DATABASE_URL", { infer: true })
        });
      }
    },
    {
      provide: DB,
      inject: [DB_POOL],
      useFactory: (pool: Pool) => drizzle(pool, { schema })
    }
  ],
  exports: [DB, DB_POOL]
})
export class DatabaseModule implements OnModuleDestroy {
  private readonly logger = new Logger(DatabaseModule.name);

  constructor(@Inject(DB_POOL) private readonly pool: Pool) {}

  async onModuleDestroy() {
    this.logger.log("Closing database pool…");
    await this.pool.end();
  }
}
