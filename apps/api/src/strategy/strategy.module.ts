import { Module } from '@nestjs/common';

import { StrategyController } from './strategy.controller.js';
import { StrategyService } from './strategy.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [StrategyController],
  providers: [StrategyService],
  exports: [StrategyService],
})
export class StrategyModule {}
