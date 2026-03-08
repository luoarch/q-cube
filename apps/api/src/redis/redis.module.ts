import { Global, Logger, Module, type OnModuleDestroy, Inject } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';

import { REDIS } from './redis.constants.js';

import type { EnvConfig } from '../config/env.schema.js';

@Global()
@Module({
  providers: [
    {
      provide: REDIS,
      inject: [ConfigService],
      useFactory: (config: ConfigService<EnvConfig>) => {
        return new Redis(config.get('REDIS_URL', { infer: true })!, {
          maxRetriesPerRequest: 2,
          lazyConnect: true,
        });
      },
    },
  ],
  exports: [REDIS],
})
export class RedisModule implements OnModuleDestroy {
  private readonly logger = new Logger(RedisModule.name);

  constructor(@Inject(REDIS) private readonly redis: Redis) {}

  async onModuleDestroy() {
    this.logger.log('Closing Redis connection…');
    await this.redis.quit();
  }
}
