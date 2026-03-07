import { Module } from "@nestjs/common";
import { AppController } from "./app.controller.js";
import { AppService } from "./app.service.js";
import { StrategyController } from "./strategy.controller.js";
import { StrategyService } from "./strategy.service.js";

@Module({
  imports: [],
  controllers: [AppController, StrategyController],
  providers: [AppService, StrategyService]
})
export class AppModule {}
