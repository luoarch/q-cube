import { Module } from '@nestjs/common';

import { PortfolioController } from './portfolio.controller.js';
import { PortfolioService } from './portfolio.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [PortfolioController],
  providers: [PortfolioService],
})
export class PortfolioModule {}
