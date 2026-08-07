import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchProjects } from './api';

describe('fetchProjects', () => {
  const mockProjects = [
    { id: '1', name: 'Project 1' },
    { id: '2', name: 'Project 2' }
  ];

  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fetch projects successfully', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockProjects
    });

    const result = await fetchProjects();
    expect(result).toEqual(mockProjects);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects'),
      expect.objectContaining({
        cache: 'no-store'
      })
    );
  });

  it('should fallback to empty array on network errors', async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const result = await fetchProjects();
    expect(result).toEqual([]);
    expect(consoleSpy).toHaveBeenCalledWith(
      "FastAPI backend unreachable, fallback to initial state",
      expect.any(Error)
    );

    consoleSpy.mockRestore();
  });

  it('should fallback to empty array on API errors', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal Server Error' })
    });

    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const result = await fetchProjects();
    expect(result).toEqual([]);
    expect(consoleSpy).toHaveBeenCalledWith(
      "FastAPI backend unreachable, fallback to initial state",
      expect.any(Error)
    );

    consoleSpy.mockRestore();
  });
});
