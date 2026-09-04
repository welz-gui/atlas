import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ErrorBanner, StatusChip } from "./StateViews";
import { ApiError } from "@/lib/api";

describe("ErrorBanner", () => {
  it("renders standard Error object correctly", () => {
    const error = new Error("Standard error message");

    render(<ErrorBanner error={error} />);

    expect(screen.getByText("Falha ao carregar os dados")).toBeInTheDocument();
    expect(screen.getByText("Standard error message")).toBeInTheDocument();
  });

  it("renders ApiError with detail correctly", () => {
    const error = new ApiError("API error message", 500, "Some detail string");

    render(<ErrorBanner error={error} />);

    expect(screen.getByText("Falha ao carregar os dados")).toBeInTheDocument();
    expect(screen.getByText("API error message")).toBeInTheDocument();
    expect(screen.getByText("Some detail string")).toBeInTheDocument();
  });

  it("renders offline errors correctly", () => {
    const error = new ApiError("Network error", 0); // 0 means offline in ApiError

    render(<ErrorBanner error={error} />);

    expect(screen.getByText("Backend do Atlas indisponível")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders retry button and calls onRetry when clicked", async () => {
    const error = new Error("Error");
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(<ErrorBanner error={error} onRetry={onRetry} />);

    const retryButton = screen.getByRole("button", { name: /tentar novamente/i });
    expect(retryButton).toBeInTheDocument();

    await user.click(retryButton);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("does not render retry button if onRetry is absent", () => {
    const error = new Error("Error");

    render(<ErrorBanner error={error} />);

    expect(screen.queryByRole("button", { name: /tentar novamente/i })).not.toBeInTheDocument();
  });
});

describe("StatusChip", () => {
  it("renders 'conforme' status correctly", () => {
    render(<StatusChip status="conforme" />);
    expect(screen.getByText("Conforme")).toBeInTheDocument();
  });

  it("renders 'nao_conforme' status correctly", () => {
    render(<StatusChip status="nao_conforme" />);
    expect(screen.getByText("Não conforme (bloqueio)")).toBeInTheDocument();
  });

  it("renders 'atencao' status correctly", () => {
    render(<StatusChip status="atencao" />);
    expect(screen.getByText("Atenção (alerta)")).toBeInTheDocument();
  });

  it("renders 'nao_aplicavel' status correctly", () => {
    render(<StatusChip status="nao_aplicavel" />);
    expect(screen.getByText("Não aplicável")).toBeInTheDocument();
  });

  it("renders 'nao_verificavel' status correctly", () => {
    render(<StatusChip status="nao_verificavel" />);
    expect(screen.getByText("Não verificável")).toBeInTheDocument();
  });

  it("renders fallback 'nao_aplicavel' for unknown status", () => {
    // @ts-expect-error - testing invalid input
    render(<StatusChip status="unknown_status" />);
    expect(screen.getByText("Não aplicável")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders title and description correctly", () => {
    render(<EmptyState title="No Items" description="There are no items to display." />);

    expect(screen.getByText("No Items")).toBeInTheDocument();
    expect(screen.getByText("There are no items to display.")).toBeInTheDocument();
  });

  it("renders action node correctly when provided", () => {
    const actionButton = <button>Create Item</button>;
    render(<EmptyState title="Empty" description="Nothing here." action={actionButton} />);

    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Item" })).toBeInTheDocument();
  });

  it("renders correctly without an action node", () => {
    render(<EmptyState title="Empty" description="Nothing here." />);

    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
