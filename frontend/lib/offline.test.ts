import { describe, it, expect, vi, beforeEach } from "vitest";
import { enqueue, listOutbox, subscribeToOutbox, flushOutbox, startOutboxSync, isOnline, removeFromOutbox } from "./offline";
import * as api from "@/lib/api";
import "fake-indexeddb/auto";

vi.mock("@/lib/api", () => {
  return {
    ApiError: class ApiError extends Error {
      status: number;
      isOffline: boolean;
      detail?: string;
      constructor(message: string, status: number, isOffline = false, detail?: string) {
        super(message);
        this.status = status;
        this.isOffline = isOffline;
        this.detail = detail;
      }
    },
    createDailyLog: vi.fn(),
    createProjectTask: vi.fn(),
  };
});

describe("offline sync hook/functions", () => {
  beforeEach(async () => {
    vi.clearAllMocks();

    // Clear outbox
    const items = await listOutbox();
    for (const item of items) {
      await removeFromOutbox(item.id);
    }
  });

  describe("subscribeToOutbox", () => {
    it("should call listeners when outbox changes", async () => {
      const listener = vi.fn();
      const unsubscribe = subscribeToOutbox(listener);

      await enqueue("daily_log", "proj1", { text: "test" }, "Proj 1");
      expect(listener).toHaveBeenCalled();

      unsubscribe();
    });
  });

  describe("enqueue and listOutbox", () => {
    it("should enqueue and list items", async () => {
      await enqueue("daily_log", "proj1", { text: "test1" });
      await enqueue("task", "proj1", { title: "test2" });

      const items = await listOutbox();
      expect(items).toHaveLength(2);
      expect(items[0].kind).toBe("daily_log");
      expect(items[0].payload).toHaveProperty("client_token");
      expect(items[1].kind).toBe("task");
    });
  });

  describe("flushOutbox", () => {
    it("should successfully flush items and remove them", async () => {
      await enqueue("daily_log", "proj1", { text: "test1" });
      await enqueue("task", "proj1", { title: "test2" });

      vi.mocked(api.createDailyLog).mockResolvedValue(undefined as never);
      vi.mocked(api.createProjectTask).mockResolvedValue(undefined as never);

      const report = await flushOutbox();
      expect(report.sent).toBe(2);
      expect(report.failed).toBe(0);
      expect(report.remaining).toBe(0);

      const items = await listOutbox();
      expect(items).toHaveLength(0);
    });

    it("should mark as failed if api returns 4xx error (except 401)", async () => {
      await enqueue("daily_log", "proj1", { text: "test1" });

      vi.mocked(api.createDailyLog).mockRejectedValue(new api.ApiError("Bad request", 400));

      const report = await flushOutbox();
      expect(report.sent).toBe(0);
      expect(report.failed).toBe(1);
      expect(report.remaining).toBe(1);

      const items = await listOutbox();
      expect(items[0].status).toBe("falhou");
    });

    it("should keep as pending if api returns 5xx error", async () => {
      await enqueue("daily_log", "proj1", { text: "test1" });

      vi.mocked(api.createDailyLog).mockRejectedValue(new api.ApiError("Server error", 500));

      const report = await flushOutbox();
      expect(report.sent).toBe(0);
      expect(report.failed).toBe(1);
      expect(report.remaining).toBe(1);

      const items = await listOutbox();
      expect(items[0].status).toBe("pendente");
      expect(items[0].attempts).toBe(1);
    });

    it("should stop retrying if offline error occurs", async () => {
      await enqueue("daily_log", "proj1", { text: "test1" });
      await enqueue("daily_log", "proj1", { text: "test2" });

      vi.mocked(api.createDailyLog).mockRejectedValueOnce(new api.ApiError("Offline", 0, true));

      const report = await flushOutbox();

      // Only 1 failed attempt, because it breaks the loop
      expect(report.sent).toBe(0);
      expect(report.failed).toBe(1);
      expect(report.remaining).toBe(2);

      // The second API call shouldn't even happen
      expect(api.createDailyLog).toHaveBeenCalledTimes(1);
    });
  });

  describe("connectivity", () => {
    it("isOnline returns navigator status", () => {
      const originalNavigator = global.navigator;
      Object.defineProperty(global, "navigator", {
        value: { onLine: true },
        configurable: true
      });
      expect(isOnline()).toBe(true);

      Object.defineProperty(global, "navigator", {
        value: { onLine: false },
        configurable: true
      });
      expect(isOnline()).toBe(false);

      Object.defineProperty(global, "navigator", {
        value: originalNavigator,
        configurable: true
      });
    });

    it("startOutboxSync adds event listener", () => {
      const addEventListenerSpy = vi.spyOn(window, "addEventListener");
      const removeEventListenerSpy = vi.spyOn(window, "removeEventListener");

      const unsubscribe = startOutboxSync();
      expect(addEventListenerSpy).toHaveBeenCalledWith("online", expect.any(Function));

      unsubscribe();
      expect(removeEventListenerSpy).toHaveBeenCalledWith("online", expect.any(Function));
    });
  });
});
