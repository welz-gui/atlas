import { updateProjectParameters } from '../../lib/api';

describe('updateProjectParameters', () => {
  beforeEach(() => {
    // Limpa os mocks antes de cada teste
    global.fetch = jest.fn();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should return project data on success', async () => {
    const mockProject = { id: '1', name: 'Test Project' };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockProject,
    });

    const result = await updateProjectParameters('1', { name: 'Test Project' });
    expect(result).toEqual(mockProject);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/1'),
      expect.objectContaining({
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Test Project' }),
      })
    );
  });

  it('should return null and log errors when response is not ok', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
    });

    const result = await updateProjectParameters('1', { name: 'Test Project' });

    expect(result).toBeNull();
    expect(console.error).toHaveBeenCalledWith(
      "Error updating project:",
      expect.any(Error)
    );
  });

  it('should return null and log errors when fetch throws an exception', async () => {
    const error = new Error('Network error');
    (global.fetch as jest.Mock).mockRejectedValue(error);

    const result = await updateProjectParameters('1', { name: 'Test Project' });

    expect(result).toBeNull();
    expect(console.error).toHaveBeenCalledWith(
      "Error updating project:",
      error
    );
  });
});
