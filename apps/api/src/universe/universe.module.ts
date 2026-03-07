import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module.js";
import { UniverseController } from "./universe.controller.js";
import { UniverseService } from "./universe.service.js";

@Module({
  imports: [AuthModule],
  controllers: [UniverseController],
  providers: [UniverseService],
})
export class UniverseModule {}
