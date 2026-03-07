import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { RankingController } from "./ranking.controller.js";
import { RankingService } from "./ranking.service.js";

@Module({
  imports: [AuthModule],
  controllers: [RankingController],
  providers: [RankingService],
  exports: [RankingService]
})
export class RankingModule {}
