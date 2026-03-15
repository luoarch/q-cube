import { Controller, Get, NotFoundException, Param, Query, UseGuards } from '@nestjs/common';

import { ThesisService } from './thesis.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('thesis')
@UseGuards(AuthGuard)
export class ThesisController {
  constructor(private readonly thesisService: ThesisService) {}

  @Get('ranking')
  async getRanking(
    @CurrentUser() user: JwtPayload,
    @Query('bucket') bucket?: string,
    @Query('search') search?: string,
  ) {
    const result = await this.thesisService.getRanking(user.tenantId, { bucket, search });
    if (!result) throw new NotFoundException('No completed Plan 2 run found');
    return result;
  }

  @Get('breakdown/:ticker')
  async getBreakdown(
    @Param('ticker') ticker: string,
    @CurrentUser() user: JwtPayload,
  ) {
    const normalized = ticker.toUpperCase();
    const result = await this.thesisService.getBreakdown(user.tenantId, normalized);
    if (!result) throw new NotFoundException(`No thesis breakdown found for ${normalized}`);
    return result;
  }
}
