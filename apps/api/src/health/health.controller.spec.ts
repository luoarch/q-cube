import { describe, it, expect, vi } from "vitest";

describe("HealthController", () => {
  it("should be instantiable with proper dependencies", async () => {
    // Dynamically import to avoid NestJS module initialization issues in unit tests
    const { HealthController } = await import("./health.controller.js");

    const mockHealthService = {
      check: vi.fn().mockResolvedValue({
        status: "ok",
        info: {
          database: { status: "up" },
          redis: { status: "up" },
        },
      }),
    };

    const mockDb = { execute: vi.fn().mockResolvedValue([]) };
    const mockRedis = { status: "ready", ping: vi.fn().mockResolvedValue("PONG") };

    const controller = new HealthController(
      mockHealthService as any,
      mockDb as any,
      mockRedis as any,
    );

    expect(controller).toBeDefined();
  });

  it("should call health.check with indicators", async () => {
    const { HealthController } = await import("./health.controller.js");

    const mockResult = {
      status: "ok",
      info: { database: { status: "up" }, redis: { status: "up" } },
    };

    const mockHealthService = {
      check: vi.fn().mockResolvedValue(mockResult),
    };

    const controller = new HealthController(
      mockHealthService as any,
      { execute: vi.fn() } as any,
      { status: "ready", ping: vi.fn().mockResolvedValue("PONG") } as any,
    );

    const result = await controller.check();
    expect(result).toEqual(mockResult);
    expect(mockHealthService.check).toHaveBeenCalledOnce();
  });
});
