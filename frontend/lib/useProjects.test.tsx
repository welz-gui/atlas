import React, { ReactNode } from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useProjects, projectShortLabel } from "./useProjects";
import * as api from "./api";

vi.mock("./api", () => ({
  fetchProjects: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

const mockProjects = [
  { id: "p1", name: "Residencial Alpha", city_name: "São Paulo", state: "SP" },
  { id: "p2", name: "Edifício Beta Master", city_name: "Rio de Janeiro", state: "RJ" },
] as api.Project[];

describe("useProjects hook", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it("fetches and returns projects correctly", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);

    const { result } = renderHook(() => useProjects(), { wrapper });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.projects).toEqual(mockProjects);
    expect(result.current.error).toBeNull();

    // First project is selected by default
    expect(result.current.selectedProjectId).toBe("p1");
    expect(result.current.selectedProject).toEqual(mockProjects[0]);
  });

  it("handles empty project list correctly", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce([]);

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.projects).toEqual([]);
    expect(result.current.selectedProjectId).toBe("");
    expect(result.current.selectedProject).toBeNull();
  });

  it("exposes error from failed fetch", async () => {
    const error = new api.ApiError("Falha", 500);
    vi.mocked(api.fetchProjects).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.projects).toEqual([]);
    expect(result.current.error).toBe(error);
  });

  it("updates selected project", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.setSelectedProjectId("p2");
    });

    await waitFor(() => {
      expect(result.current.selectedProjectId).toBe("p2");
      expect(result.current.selectedProject).toEqual(mockProjects[1]);
    });
  });

  it("reverts to first project if selected project disappears", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.setSelectedProjectId("p2");
    });

    await waitFor(() => {
      expect(result.current.selectedProjectId).toBe("p2");
    });

    // Simulate fetch returning new list without p2
    vi.mocked(api.fetchProjects).mockResolvedValueOnce([mockProjects[0]]);

    act(() => {
      // invalidate to trigger refetch
      result.current.reload();
    });

    await waitFor(() => {
       // Should fallback to first item
       expect(result.current.selectedProjectId).toBe("p1");
       expect(result.current.selectedProject).toEqual(mockProjects[0]);
    });
  });

  it("allows replacing a project in cache without fetching", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const updatedProject = { ...mockProjects[0], name: "Alpha Renovado" };

    act(() => {
      result.current.replaceProject(updatedProject);
    });

    await waitFor(() => {
      expect(result.current.projects[0].name).toBe("Alpha Renovado");
      // ensure it didn't trigger network request
      expect(api.fetchProjects).toHaveBeenCalledTimes(1);
    });
  });

  it("reload invalidates query", async () => {
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);
    // ensure second call returns something to prevent undefined query error
    vi.mocked(api.fetchProjects).mockResolvedValueOnce(mockProjects);

    // spy on invalidateQueries
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.reload();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("projectShortLabel", () => {
  it("extracts first two words of project name", () => {
    expect(projectShortLabel({ name: "Residencial Jardim das Flores" } as api.Project)).toBe("Residencial Jardim");
    expect(projectShortLabel({ name: "Edifício A" } as api.Project)).toBe("Edifício A");
    expect(projectShortLabel({ name: "Unico" } as api.Project)).toBe("Unico");
  });
});
