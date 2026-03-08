import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { AIController } from "./ai.controller.js";
import { AIService } from "./ai.service.js";

@Module({
  imports: [AuthModule],
  controllers: [AIController],
  providers: [AIService],
  exports: [AIService],
})
export class AIModule {}
