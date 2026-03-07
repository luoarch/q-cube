import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { RankingModule } from "../ranking/ranking.module.js";
import { DashboardController } from "./dashboard.controller.js";
import { DashboardService } from "./dashboard.service.js";

@Module({
  imports: [AuthModule, RankingModule],
  controllers: [DashboardController],
  providers: [DashboardService],
})
export class DashboardModule {}
