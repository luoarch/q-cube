import { Module } from '@nestjs/common';

import { RankingController } from './ranking.controller.js';
import { RankingService } from './ranking.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [RankingController],
  providers: [RankingService],
  exports: [RankingService],
})
export class RankingModule {}
