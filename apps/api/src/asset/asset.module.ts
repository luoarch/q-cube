import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { AssetController } from "./asset.controller.js";
import { AssetService } from "./asset.service.js";

@Module({
  imports: [AuthModule],
  controllers: [AssetController],
  providers: [AssetService],
})
export class AssetModule {}
