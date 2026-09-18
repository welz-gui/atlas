import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import AppShell from "./AppShell";
import { useAuth } from "@/lib/auth";
import { usePathname } from "next/navigation";

// Mock dependencies
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/components/Navbar", () => ({
  default: () => <div data-testid="mock-navbar">Navbar</div>,
}));

vi.mock("@/components/Sidebar", () => ({
  default: () => <div data-testid="mock-sidebar">Sidebar</div>,
}));

vi.mock("@/components/OfflineBar", () => ({
  default: () => <div data-testid="mock-offline-bar">OfflineBar</div>,
}));

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a loading spinner when auth is loading", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: true,
      error: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      can: vi.fn(),
      refresh: vi.fn(),
    });
    vi.mocked(usePathname).mockReturnValue("/");

    const { container } = render(
      <AppShell>
        <div data-testid="child-content">Child Content</div>
      </AppShell>
    );

    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
    expect(screen.queryByTestId("child-content")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mock-navbar")).not.toBeInTheDocument();
  });

  it("renders children without shell when user is not authenticated", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      error: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      can: vi.fn(),
      refresh: vi.fn(),
    });
    vi.mocked(usePathname).mockReturnValue("/");

    render(
      <AppShell>
        <div data-testid="child-content">Child Content</div>
      </AppShell>
    );

    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByTestId("mock-navbar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mock-sidebar")).not.toBeInTheDocument();
  });

  it("renders children without shell when route is /login, even if user is authenticated", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "User", email: "user@example.com", role: "admin", organization_id: "org1" },
      isLoading: false,
      error: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      can: vi.fn(),
      refresh: vi.fn(),
    });
    vi.mocked(usePathname).mockReturnValue("/login");

    render(
      <AppShell>
        <div data-testid="child-content">Child Content</div>
      </AppShell>
    );

    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByTestId("mock-navbar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mock-sidebar")).not.toBeInTheDocument();
  });

  it("renders shell components and children when user is authenticated and not on /login", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "User", email: "user@example.com", role: "admin", organization_id: "org1" },
      isLoading: false,
      error: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      can: vi.fn(),
      refresh: vi.fn(),
    });
    vi.mocked(usePathname).mockReturnValue("/dashboard");

    render(
      <AppShell>
        <div data-testid="child-content">Child Content</div>
      </AppShell>
    );

    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.getByTestId("mock-navbar")).toBeInTheDocument();
    expect(screen.getByTestId("mock-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("mock-offline-bar")).toBeInTheDocument();
  });
});
