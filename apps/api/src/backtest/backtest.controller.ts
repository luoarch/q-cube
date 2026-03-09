import {
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import { createBacktestRunSchema } from '@q3/shared-contracts';

import { type BacktestService } from './backtest.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('backtest-runs')
@UseGuards(AuthGuard)
export class BacktestController {
  constructor(private readonly backtestService: BacktestService) {}

  @Post()
  async create(@Body() body: unknown, @CurrentUser() user: JwtPayload) {
    const input = createBacktestRunSchema.parse({
      ...(body as object),
      tenantId: user.tenantId,
    });
    return this.backtestService.createRun(user.tenantId, input);
  }

  @Get()
  async list(@CurrentUser() user: JwtPayload) {
    return this.backtestService.listRuns(user.tenantId);
  }

  @Get(':id')
  async getById(@Param('id', new ParseUUIDPipe()) id: string, @CurrentUser() user: JwtPayload) {
    const run = await this.backtestService.getRun(id, user.tenantId);
    if (!run) {
      throw new NotFoundException('Backtest run not found');
    }
    return run;
  }
}
