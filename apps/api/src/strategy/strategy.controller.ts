import {
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Post,
  UseGuards
} from "@nestjs/common";
import { createStrategyRunSchema } from "@q3/shared-contracts";
import { AuthGuard } from "../auth/auth.guard.js";
import { CurrentUser } from "../auth/current-user.decorator.js";
import type { JwtPayload } from "../auth/auth.service.js";
import { StrategyService } from "./strategy.service.js";

@Controller("strategy-runs")
@UseGuards(AuthGuard)
export class StrategyController {
  constructor(private readonly strategyService: StrategyService) {}

  @Post()
  async create(@Body() body: unknown, @CurrentUser() user: JwtPayload) {
    const input = createStrategyRunSchema.parse({
      ...(body as object),
      tenantId: user.tenantId,
    });
    return this.strategyService.createRun(input);
  }

  @Get()
  async list(@CurrentUser() user: JwtPayload) {
    return this.strategyService.listRuns(user.tenantId);
  }

  @Get(":id")
  async getById(
    @Param("id", new ParseUUIDPipe()) id: string,
    @CurrentUser() user: JwtPayload,
  ) {
    const run = await this.strategyService.getRun(id, user.tenantId);
    if (!run) {
      throw new NotFoundException("Strategy run not found");
    }
    return run;
  }
}
