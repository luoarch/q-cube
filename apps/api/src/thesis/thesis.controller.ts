import { Body, Controller, Get, NotFoundException, Param, Post, Query, UseGuards } from '@nestjs/common';
import { rubricScoreInputSchema } from '@q3/shared-contracts';

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

  @Get('rubrics/:ticker')
  async getRubrics(
    @Param('ticker') ticker: string,
    @CurrentUser() user: JwtPayload,
  ) {
    const normalized = ticker.toUpperCase();
    const result = await this.thesisService.getRubrics(user.tenantId, normalized);
    if (!result) throw new NotFoundException(`Ticker ${normalized} not found`);
    return result;
  }

  @Post('rubrics')
  async upsertRubric(
    @Body() body: unknown,
    @CurrentUser() user: JwtPayload,
  ) {
    const input = rubricScoreInputSchema.parse(body);
    return this.thesisService.upsertRubric(user.tenantId, input);
  }

  @Post('rubrics/suggest/:ticker')
  async suggestRubric(
    @Param('ticker') ticker: string,
    @CurrentUser() user: JwtPayload,
    @Query('dimension') dimension?: string,
  ) {
    const normalized = ticker.toUpperCase();
    const dimensionKey = dimension ?? 'usd_debt_exposure';
    return this.thesisService.suggestRubric(user.tenantId, normalized, dimensionKey);
  }

  // F3.2 — Monitoring endpoints

  @Get('monitoring')
  async getMonitoring(@CurrentUser() user: JwtPayload) {
    const result = await this.thesisService.getMonitoringSummary(user.tenantId);
    if (!result) throw new NotFoundException('No completed Plan 2 run found');
    return result;
  }

  @Get('monitoring/drift')
  async getDrift(
    @CurrentUser() user: JwtPayload,
    @Query('vs_run_id') vsRunId?: string,
  ) {
    const result = await this.thesisService.getDrift(user.tenantId, vsRunId);
    if (!result) throw new NotFoundException('No completed Plan 2 run found');
    return result;
  }

  @Get('monitoring/rubric-aging')
  async getRubricAging(@Query('stale_days') staleDays?: string) {
    return this.thesisService.getRubricAging(staleDays ? Number(staleDays) : 30);
  }

  @Get('monitoring/review-queue')
  async getReviewQueue(@Query('stale_days') staleDays?: string) {
    return this.thesisService.getReviewQueue(staleDays ? Number(staleDays) : 30);
  }

  @Get('monitoring/alerts')
  async getAlerts(
    @CurrentUser() user: JwtPayload,
    @Query('stale_days') staleDays?: string,
  ) {
    const result = await this.thesisService.getAlerts(user.tenantId, staleDays ? Number(staleDays) : 30);
    if (!result) throw new NotFoundException('No completed Plan 2 run found');
    return result;
  }
}
