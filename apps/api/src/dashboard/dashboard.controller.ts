import { Controller, Get, UseGuards } from '@nestjs/common';

import { DashboardService } from './dashboard.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('dashboard')
@UseGuards(AuthGuard)
export class DashboardController {
  constructor(private readonly dashboardService: DashboardService) {}

  @Get('summary')
  async summary(@CurrentUser() user: JwtPayload) {
    return this.dashboardService.getSummary(user.tenantId);
  }
}
