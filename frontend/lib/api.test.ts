import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchProjects, setToken, ApiError, request } from './api';

describe('fetchProjects', () => {
  const mockToken = 'mock-token';
  const mockProjects = [
    { id: '1', name: 'Project 1' },
    { id: '2', name: 'Project 2' }
  ];

  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn();
    setToken(mockToken);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setToken(null);
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
        headers: { Authorization: `Bearer ${mockToken}` },
        cache: 'no-store'
      })
    );
  });

  it('should throw ApiError on network errors', async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

    await expect(fetchProjects()).rejects.toThrow(ApiError);
  });

  it('should throw ApiError on API errors', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal Server Error' })
    });

    await expect(fetchProjects()).rejects.toThrow(ApiError);
  });
});
