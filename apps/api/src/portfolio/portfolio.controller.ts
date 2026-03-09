import { Controller, Get, UseGuards } from '@nestjs/common';

import { type PortfolioService } from './portfolio.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('portfolio')
@UseGuards(AuthGuard)
export class PortfolioController {
  constructor(private readonly portfolioService: PortfolioService) {}

  @Get()
  async get(@CurrentUser() user: JwtPayload) {
    return this.portfolioService.getPortfolio(user.tenantId);
  }
}
