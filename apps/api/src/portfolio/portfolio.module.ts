import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { PortfolioController } from "./portfolio.controller.js";
import { PortfolioService } from "./portfolio.service.js";

@Module({
  imports: [AuthModule],
  controllers: [PortfolioController],
  providers: [PortfolioService],
})
export class PortfolioModule {}
