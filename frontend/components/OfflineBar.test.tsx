import React from "react";
import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import OfflineBar from "./OfflineBar";
import * as offlineLib from "@/lib/offline";

vi.mock("@/lib/offline", () => ({
  isOnline: vi.fn(),
  listOutbox: vi.fn(),
  subscribeToOutbox: vi.fn(),
  startOutboxSync: vi.fn(),
  flushOutbox: vi.fn(),
  QUEUEABLE: {
    daily_log: "Diário de obra",
    task: "Tarefa",
  },
}));

describe("OfflineBar", () => {
  beforeEach(() => {
    vi.mocked(offlineLib.subscribeToOutbox).mockReturnValue(vi.fn());
    vi.mocked(offlineLib.startOutboxSync).mockReturnValue(vi.fn());
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([]);
    vi.mocked(offlineLib.isOnline).mockReturnValue(true);
    vi.mocked(offlineLib.flushOutbox).mockResolvedValue({ sent: 1, failed: 0, remaining: 0 });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when online and queue is empty", async () => {
    await act(async () => {
      render(<OfflineBar />);
    });
    expect(screen.queryByText(/Sem conexão/i)).not.toBeInTheDocument();
  });

  it("renders when offline even if queue is empty", async () => {
    vi.mocked(offlineLib.isOnline).mockReturnValue(false);

    await act(async () => {
      render(<OfflineBar />);
    });

    expect(screen.getByText(/Sem conexão/i)).toBeInTheDocument();
    expect(screen.getByText(/Análise, laudo e assistente exigem conexão/i)).toBeInTheDocument();
  });

  it("displays the correct number of items in the outbox", async () => {
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([
      { id: "1", kind: "daily_log", projectId: "p1", payload: {}, createdAt: new Date().toISOString(), status: "pendente", attempts: 0 },
      { id: "2", kind: "task", projectId: "p1", payload: {}, createdAt: new Date().toISOString(), status: "falhou", attempts: 1 }
    ]);

    await act(async () => {
      render(<OfflineBar />);
    });

    expect(screen.getByText(/2 registro\(s\) ainda no aparelho/i)).toBeInTheDocument();
  });

  it("toggles the outbox items list when 'ver' / 'ocultar' button is clicked", async () => {
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([
      { id: "1", kind: "daily_log", projectId: "p1", projectName: "Projeto Teste", payload: {}, createdAt: new Date().toISOString(), status: "pendente", attempts: 0 },
    ]);
    const user = userEvent.setup();

    await act(async () => {
      render(<OfflineBar />);
    });

    const toggleButton = screen.getByRole("button", { name: /ver/i });
    expect(toggleButton).toBeInTheDocument();

    await user.click(toggleButton);

    expect(screen.getByText(/Diário de obra • Projeto Teste/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ocultar/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /ocultar/i }));

    expect(screen.queryByText(/Diário de obra • Projeto Teste/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ver/i })).toBeInTheDocument();
  });

  it("calls flushOutbox when 'Enviar agora' is clicked", async () => {
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([
      { id: "1", kind: "daily_log", projectId: "p1", payload: {}, createdAt: new Date().toISOString(), status: "pendente", attempts: 0 },
    ]);
    const user = userEvent.setup();

    await act(async () => {
      render(<OfflineBar />);
    });

    const sendButton = screen.getByRole("button", { name: /Enviar agora/i });
    expect(sendButton).toBeInTheDocument();

    await user.click(sendButton);

    expect(offlineLib.flushOutbox).toHaveBeenCalledOnce();
  });

  it("does not show 'Enviar agora' if all items are 'falhou'", async () => {
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([
      { id: "1", kind: "daily_log", projectId: "p1", payload: {}, createdAt: new Date().toISOString(), status: "falhou", attempts: 1, lastError: "Error" },
    ]);

    await act(async () => {
      render(<OfflineBar />);
    });

    expect(screen.queryByRole("button", { name: /Enviar agora/i })).not.toBeInTheDocument();
  });

  it("displays error details for 'falhou' items", async () => {
    vi.mocked(offlineLib.listOutbox).mockResolvedValue([
      { id: "1", kind: "daily_log", projectId: "p1", payload: {}, createdAt: new Date().toISOString(), status: "falhou", attempts: 1, lastError: "Erro muito específico" },
    ]);
    const user = userEvent.setup();

    await act(async () => {
      render(<OfflineBar />);
    });

    await user.click(screen.getByRole("button", { name: /ver/i }));

    expect(screen.getByText(/Erro muito específico/i)).toBeInTheDocument();
    expect(screen.getByText("recusado")).toBeInTheDocument();
  });
});
