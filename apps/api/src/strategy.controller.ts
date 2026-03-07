import {
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Post
} from "@nestjs/common";
import { createStrategyRunSchema } from "@q3/shared-contracts";
import { StrategyService } from "./strategy.service.js";

@Controller("strategy-runs")
export class StrategyController {
  constructor(private readonly strategyService: StrategyService) {}

  @Post()
  async create(@Body() body: unknown) {
    const input = createStrategyRunSchema.parse(body);
    return this.strategyService.createRun(input);
  }

  @Get(":id")
  async getById(@Param("id", new ParseUUIDPipe()) id: string) {
    const run = await this.strategyService.getRun(id);
    if (!run) {
      throw new NotFoundException("strategy run not found");
    }
    return run;
  }
}
