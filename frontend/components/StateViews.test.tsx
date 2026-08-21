import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBanner } from "./StateViews";
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
