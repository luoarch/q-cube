import "reflect-metadata";
import { NestFactory } from "@nestjs/core";
import { Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { AppModule } from "./app.module.js";
import { ZodExceptionFilter } from "./common/filters/zod-exception.filter.js";
import type { EnvConfig } from "./config/env.schema.js";

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: ["error", "warn", "log", "debug", "verbose"]
  });

  app.enableCors({
    origin: process.env.CORS_ORIGIN ?? "http://localhost:3001",
    credentials: true,
  });
  app.useGlobalFilters(new ZodExceptionFilter());
  app.enableShutdownHooks();

  const config = app.get(ConfigService<EnvConfig>);
  const port = config.get("PORT", { infer: true })!;

  await app.listen(port);
  Logger.log(`Q³ API listening on :${port}`, "Bootstrap");
}

void bootstrap();
