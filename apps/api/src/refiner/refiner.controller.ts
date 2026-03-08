import {
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  UseGuards,
} from '@nestjs/common';

import { RefinerService } from './refiner.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('refiner')
@UseGuards(AuthGuard)
export class RefinerController {
  constructor(private readonly refinerService: RefinerService) {}

  @Get(':strategyRunId')
  async getByRunId(
    @Param('strategyRunId', new ParseUUIDPipe()) strategyRunId: string,
    @CurrentUser() user: JwtPayload,
  ) {
    return this.refinerService.getByRunId(strategyRunId, user.tenantId);
  }

  @Get(':strategyRunId/:ticker')
  async getByRunIdAndTicker(
    @Param('strategyRunId', new ParseUUIDPipe()) strategyRunId: string,
    @Param('ticker') ticker: string,
    @CurrentUser() user: JwtPayload,
  ) {
    const result = await this.refinerService.getByRunIdAndTicker(
      strategyRunId,
      ticker.toUpperCase(),
      user.tenantId,
    );
    if (!result) {
      throw new NotFoundException(`Refinement result not found for ticker ${ticker}`);
    }
    return result;
  }
}
