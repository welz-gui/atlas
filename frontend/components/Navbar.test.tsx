import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Navbar from "./Navbar";
import { fetchOrganization } from "@/lib/api";
import { useAuth, ROLE_LABELS } from "@/lib/auth";

// Mock dependencies
vi.mock("@/lib/api", () => ({
  fetchOrganization: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
  ROLE_LABELS: {
    owner: "Responsável",
    admin: "Administrador",
    validator: "Validador técnico",
    engineer: "Engenharia",
    inspector: "Campo",
    client: "Cliente",
  },
}));

const mockSignOut = vi.fn();

describe("Navbar component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null if no user is authenticated", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      signOut: mockSignOut,
      token: null,
      login: vi.fn(),
      setOrganization: vi.fn(),
    } as any);

    const { container } = render(<Navbar />);
    expect(container.firstChild).toBeNull();
  });

  it("renders user information and default organization text initially", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "John Doe", role: "admin", email: "john@example.com", organization_id: "org_1" },
      signOut: mockSignOut,
    } as any);

    // Mock an unresolved promise to test initial state
    let resolvePromise: any;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(fetchOrganization).mockReturnValue(promise as any);

    render(<Navbar />);

    expect(screen.getByText("Organização")).toBeInTheDocument();
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();

    // Clean up inside act to avoid warnings
    await act(async () => {
      resolvePromise({ id: "org_1", name: "My Org" });
    });
  });

  it("updates organization text when fetch resolves successfully", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "John Doe", role: "admin", email: "john@example.com", organization_id: "org_1" },
      signOut: mockSignOut,
    } as any);

    vi.mocked(fetchOrganization).mockResolvedValue({ id: "org_1", name: "Test Organization" } as any);

    render(<Navbar />);

    // Wait for update
    await waitFor(() => {
      expect(screen.getByText("Test Organization")).toBeInTheDocument();
    });
    expect(screen.queryByText("Organização")).not.toBeInTheDocument();
  });

  it("keeps default organization text if fetch rejects", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "John Doe", role: "admin", email: "john@example.com", organization_id: "org_1" },
      signOut: mockSignOut,
    } as any);

    vi.mocked(fetchOrganization).mockRejectedValue(new Error("Failed to fetch"));

    render(<Navbar />);

    // Wait a bit to ensure the component handled the error
    await waitFor(() => {
      expect(screen.getByText("Organização")).toBeInTheDocument();
    });
  });

  it("invokes signOut when the logout button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue({
      user: { id: "1", name: "John Doe", role: "admin", email: "john@example.com", organization_id: "org_1" },
      signOut: mockSignOut,
    } as any);

    vi.mocked(fetchOrganization).mockResolvedValue({ id: "org_1", name: "Test Organization" } as any);

    render(<Navbar />);

    const logoutButton = screen.getByTitle("Sair");
    await user.click(logoutButton);

    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });
});
