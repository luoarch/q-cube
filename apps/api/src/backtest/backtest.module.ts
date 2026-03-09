import { Module } from '@nestjs/common';

import { BacktestController } from './backtest.controller.js';
import { BacktestService } from './backtest.service.js';
import { AuthModule } from '../auth/auth.module.js';
import { RedisModule } from '../redis/redis.module.js';

@Module({
  imports: [AuthModule, RedisModule],
  controllers: [BacktestController],
  providers: [BacktestService],
  exports: [BacktestService],
})
export class BacktestModule {}
