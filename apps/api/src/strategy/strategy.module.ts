import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { StrategyController } from "./strategy.controller.js";
import { StrategyService } from "./strategy.service.js";

@Module({
  imports: [AuthModule],
  controllers: [StrategyController],
  providers: [StrategyService],
  exports: [StrategyService]
})
export class StrategyModule {}
